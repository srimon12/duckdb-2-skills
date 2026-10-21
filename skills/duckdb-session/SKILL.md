---
name: duckdb-session
description: >
  Attach DuckDB database files and restore them on later CLI calls with a
  state.sql init file. Explores schemas, tables, and storage version. Use when
  the user says attach, open this database, switch database, or runs
  /duckdb-session.
---

# Attach a database and keep the session

DuckDB's CLI is one process per command. `ATTACH` dies with the process. Persist attaches in a SQL init file and pass it with `-init`.

Run commands with the `duckdb` skill's binary rules.

This skill attaches native DuckDB files. SQLite is `duckdb-files`. DuckLake, Iceberg, and Delta are `duckdb-lakehouse`. Quack, Postgres, and MySQL are `duckdb-quack`.

Do not write secret values into `state.sql`. Store `ATTACH` lines and `CREATE SECRET` statements that refer to a provider chain or an existing secret name.

## State file

Look in this order:

1. `.duckdb/state.sql` in the project.
2. `.duckdb-skills/state.sql` in the project, the path used by the older duckdb-skills plugin.
3. `$HOME/.duckdb-skills/<project-id>/state.sql`, where `<project-id>` is the absolute project root with `/` replaced by `-`.

If none of those exist, create `.duckdb/state.sql`. Tell the user the path. If they want it outside the repo, move it to the home location instead. Offer to add `.duckdb/` to `.gitignore` when the file lives in the project. Append. Never replace the file. It may already hold secrets, macros, and `LOAD` statements.

## Attach

Resolve the path to an absolute path. If the file is missing, ask before creating it. Creating it with DuckDB 2.0 writes storage version 69, which DuckDB 1.x cannot open. Say that before you create the file. To keep a new file readable by 1.5, follow `duckdb-migrate` and set the storage version at creation.

Alias is the file stem. If that alias is already in the state file, ask for another name.

Append only when that path is not already attached:

```sql
ATTACH IF NOT EXISTS '/absolute/path/analytics.duckdb' AS analytics;
```

Add `USE analytics;` only when the user asked to make this database the default, or when the state file has no `USE` yet. A second attach should not silently change the default database.

Open once without `-init` to validate, then again with `-init` to prove the state file:

```bash
duckdb -json -c "ATTACH '/absolute/path/analytics.duckdb' AS analytics; SELECT database_name, tags['storage_version'] AS storage_version FROM duckdb_databases();"
duckdb -init .duckdb/state.sql -json -c "SHOW TABLES;"
```

`tags['storage_version']` is the version to trust. A value like `v2.0.0+` means a 1.x process cannot open that file.

## Explore

```sql
SELECT schema_name, table_name, estimated_size, column_count
FROM duckdb_tables()
WHERE database_name = 'analytics' AND NOT internal
ORDER BY schema_name, table_name;
```

For each table the user cares about, up to 20:

```sql
DESCRIBE analytics.main.table_name;
```

`estimated_size` is an estimate. Use `count()` only when the user asked for an exact number or the estimate is small.

Report the absolute path, the alias, the state file path, the storage version, and the tables. Later skills in this pack should pass `-init` with the same state file.

## References

- https://duckdb.org/docs/2.0/sql/statements/attach.html
- https://duckdb.org/docs/2.0/internals/storage.html
- https://duckdb.org/docs/2.0/operations_manual/migration.html
- The shared `state.sql` init file comes from the `attach-db` skill in https://github.com/duckdb/duckdb-skills (MIT). The default path here is `.duckdb/state.sql`.
