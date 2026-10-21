---
name: duckdb-session
description: >
  Attach DuckDB database files and restore them on later CLI calls with a
  state.sql init file. Covers storage version checks, schema exploration,
  checkpoints, and safe detach. Use when the user says attach, open this
  database, switch database, or wants state to survive between commands.
---

# Database sessions

The CLI is one process per command. `ATTACH` dies with the process. Persist the attach in a SQL init file and pass it with `-init`.

Run commands with the `duckdb` skill's binary rules. This skill attaches native DuckDB files. SQLite is `duckdb-files`. DuckLake, Iceberg, and Delta are `duckdb-lakehouse`. Quack, Postgres, and MySQL are `duckdb-quack`.

Do not write secret values into the state file. Store `ATTACH` lines and `CREATE SECRET` statements that refer to a provider chain or an existing secret name.

## State file

Look in this order:

1. `.duckdb/state.sql` in the project.
2. `.duckdb-skills/state.sql` in the project, the path used by the upstream duckdb-skills plugin.
3. `$HOME/.duckdb-skills/<project-id>/state.sql`, where `<project-id>` is the absolute project root with `/` replaced by `-`.

If none exists, create `.duckdb/state.sql` (unless the project root is `$HOME`, where `.duckdb-skills/` avoids colliding with `~/.duckdb/`). Tell the user the path. If the file belongs outside the repo, use the home location. Offer to add `.duckdb/` to `.gitignore` when the file lives in the project.

Append. Never replace the file. It may already hold secrets, macros, and `LOAD` statements.

## Attach

Resolve the path to an absolute path. If the file is missing, ask before creating it. A new file created by DuckDB 2.0 uses storage version 69, which DuckDB 1.x cannot open. Say that before you create it. To keep a new file readable by 1.5, follow `duckdb-migrate` and set the storage version at creation.

The alias is the file name up to the first dot. `a.b.c.db` becomes `a`. Quote an alias that contains `-`, a space, or a leading digit.

`ATTACH IF NOT EXISTS` is keyed on the alias, not the path. The same alias with a different path is a silent no-op. The same path under a second alias fails with `Unique file handle conflict`. A missing path is created as a new storage-version-69 file. Before appending, check the path with `test -f`.

Only when that path is not already attached, append:

```sql
ATTACH IF NOT EXISTS '/absolute/path/analytics.duckdb' AS analytics;
```

Options that matter:

| Option | Use |
| --- | --- |
| `READ_ONLY` | Open a file that other processes only read, or a file over HTTPS or S3. |
| `STORAGE_VERSION 'v1.5.6'` | New file uses storage 68. DuckDB 1.5.6 can read it. DuckDB 1.4 cannot. `v1.5.0` writes the same header. |
| `ENCRYPTION_KEY '...'` | Open an encrypted database. Load `httpfs` first for OpenSSL speed. |
| `TYPE sqlite` | A SQLite file. Use `duckdb-files`, not this skill. |
| `ATTACH OR REPLACE` | Replace an existing alias. Destructive; ask first. |

Only when the user asked to make this database the default, or when the state file has no `USE` yet, add `USE analytics;`. A second attach should not silently change the default database. Without any `USE`, the default is `memory`, so a bare `SHOW TABLES` can look empty even after an attach.

`-init` is CLI-only. Python and other clients must issue `ATTACH` in code. The init file may hold SQL and dot commands, and a parse or SQL error aborts startup with exit 1.

Open once without `-init` to validate, then again with `-init` to prove the state file:

```bash
duckdb -json -c "ATTACH '/absolute/path/analytics.duckdb' AS analytics; SELECT database_name, path, tags['storage_version'] AS storage_version FROM duckdb_databases();"
duckdb -init .duckdb/state.sql -json -c "SHOW TABLES;"
```

`tags['storage_version']` is a compatibility floor, not the storage number. A 69 file reports `v2.0.0+`, which means 1.x cannot open it. A 68 file reports `v1.5.0+`. Opening a 1.x file does not upgrade it, and an ordinary write keeps its old version. `ATTACH existing (STORAGE_VERSION 'latest')` plus a write upgrades that file to 69. Do not pass `latest` unless the user asked to move the file.

## Explore

```sql
SELECT database_name, path, tags['storage_version'] AS storage_version, readonly, type
FROM duckdb_databases()
WHERE NOT internal;

SELECT schema_name, table_name, estimated_size, column_count
FROM duckdb_tables()
WHERE database_name = 'analytics' AND NOT internal
ORDER BY schema_name, table_name;
```

For each table the user cares about, up to 20:

```sql
DESCRIBE analytics.main.table_name;
```

`estimated_size` is an estimate. Only when the user asked for an exact number or the estimate is small, use `count()`.

Nested schemas need a join. `duckdb_tables()` carries `schema_oid`; `duckdb_schemas()` carries `oid`, `schema_name`, and `parent_schema`.

```sql
SELECT s.parent_schema, t.schema_name, t.table_name
FROM duckdb_tables() AS t
JOIN duckdb_schemas() AS s ON t.schema_oid = s.oid AND t.database_oid = s.database_oid
WHERE t.database_name = 'analytics' AND s.parent_schema IS NOT NULL;
```

Report the absolute path, the alias, the state file path, the storage version, and the tables. Later skills in this pack should pass `-init` with the same state file.

## Concurrency and durability

Across processes, a native DuckDB file allows one writer or many readers, not both. A writer process excludes read-only processes with a lock error, and a reader excludes a writer. Within one process, multiple connections can write under MVCC, but a second connection with a different configuration (for example `read_only=True`) fails. For concurrent read and write across processes, use Quack or DuckLake.

```sql
CHECKPOINT analytics;        -- flush the WAL to the data file
FORCE CHECKPOINT analytics;  -- wait for the checkpoint lock, then flush
```

`CHECKPOINT` fails if a transaction is running. `FORCE CHECKPOINT` waits from 1.4 onward. A clean exit checkpoints and removes the WAL. `checkpoint_on_detach` takes `ENABLED`, `DISABLED`, or `DEFAULT`, not a boolean.

`DETACH` releases the file lock. You cannot detach the default database; `USE` another one first.

```sql
ATTACH ':memory:' AS memory_db;
USE memory_db;
DETACH analytics;
```

Closing the only Python connection releases the cross-process lock. Locks persist while another connection or process holds the file. When the lock matters, detach the database in SQL.

## Move or copy

```sql
COPY FROM DATABASE analytics TO archive;
```

For a file-format migration, use `duckdb-migrate`. For a backup, export into an empty directory because `EXPORT DATABASE` writes SQL and CSV by default without clearing existing files; add `(FORMAT parquet)` for Parquet. `IMPORT DATABASE` needs a target database with no conflicting objects.

`COPY FROM DATABASE` needs an attached target with no conflicting table names. The target's storage version controls the output.

## Verify

```bash
duckdb -init .duckdb/state.sql -agent -c \
  "SELECT database_name, tags['storage_version'] FROM duckdb_databases() WHERE NOT internal;"
```

The alias appears once, with the expected storage version. A second run must not duplicate the `ATTACH`, because the state file uses `ATTACH IF NOT EXISTS`.

## References

- [ATTACH and DETACH](https://duckdb.org/docs/2.0/sql/statements/attach.html) owns the options and the storage-version rule.
- [CHECKPOINT](https://duckdb.org/docs/2.0/sql/statements/checkpoint.html) owns WAL behavior.
- [Concurrency](https://duckdb.org/docs/2.0/connect/concurrency.html) owns the one-writer rule.
- [Storage](https://duckdb.org/docs/2.0/internals/storage.html) owns the version table.
- [duckdb_databases](https://duckdb.org/docs/2.0/sql/meta/duckdb_table_functions.html#duckdb_databases) owns the catalog columns. The live function has more columns than the manual table; use `DESCRIBE`.
- `duckdb_secrets()` redacts `secret=` but still shows `key_id=`. Report names and types only, never the row.
- The shared `state.sql` convention comes from the `attach-db` skill in https://github.com/duckdb/duckdb-skills (MIT). The default path here is `.duckdb/state.sql`.
