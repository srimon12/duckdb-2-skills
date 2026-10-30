---
name: duckdb-session
description: >
  Attach native DuckDB database files and persist session state across CLI calls
  with a state.sql init file. Covers storage version detection, schema
  introspection, WAL checkpoints, locking, and safe detach. Use when attaching
  or opening a database, switching catalogs, or persisting state across commands.
---

# Database sessions

DuckDB CLI executions terminate after each command, discarding runtime `ATTACH` bindings. To persist attached databases across invocations, record attachment statements in an initialization script and pass `-init <path>` on startup.

For execution binary rules, see `duckdb`. For SQLite databases, see `duckdb-files`. For DuckLake, Iceberg, and Delta catalogs, see `duckdb-lakehouse`. For Quack, Postgres, and MySQL connections, see `duckdb-quack`.

Never store raw secrets in the state file. Record only `ATTACH` commands and `CREATE SECRET` statements referencing an external provider chain or pre-existing secret name.

## State file discovery

Search for a state file in this exact sequence:

1. `.duckdb/state.sql` in the project root.
2. `.duckdb-skills/state.sql` in the project root (upstream duckdb-skills plugin convention).
3. `$HOME/.duckdb-skills/<project-id>/state.sql` (`<project-id>` replaces `/` with `-` in the absolute project root).

If no state file exists:
- When the project root is `$HOME`, create `$HOME/.duckdb-skills/state.sql` to avoid colliding with `~/.duckdb/`.
- When session persistence belongs outside the repository, write to the `$HOME/.duckdb-skills/<project-id>/` location.
- Otherwise, create `.duckdb/state.sql`, report the path to the user, and offer to add `.duckdb/` to `.gitignore`.

## State file reconciliation

Treat the state file as append-only. Never overwrite or truncate it, as it may contain user macros, variables, and `LOAD` statements. Before appending, execute this reconciliation procedure:

1. **Read existing statements**: Parse the file for existing `ATTACH`, `USE`, `LOAD`, `SET`, and `CREATE SECRET` commands. Never echo or display secret credentials.
2. **Resolve and compare**: Resolve each `ATTACH` path to an absolute path. Derive the alias from the filename up to the first dot (`a.b.c.db` becomes `a`). If the alias contains hyphens, spaces, or leading digits, enclose it in double quotes. Inspect attached catalogs via `duckdb_databases()`.
3. **Handle collisions**:
   - If alias and path match: skip the attachment.
   - If alias matches but points to a different path: halt and ask the user. `ATTACH IF NOT EXISTS` keys on alias and silently retains the original path.
   - If path matches under a second alias: halt. DuckDB rejects duplicate paths with `Unique file handle conflict`.
4. **Guard missing files**: Before attaching a nonexistent path, verify with `test -f`. DuckDB 2.0 creates missing files as storage version 69, unreadable by DuckDB 1.x. Confirm with the user before generating new files.
5. **Append missing delta**: Append only missing `ATTACH` statements. Maintain at most one `USE <alias>;` in the state file so subsequent attachments do not alter the active catalog.
6. **Validate lifecycle**: Test the state file in a fresh process without `-init`, then with `-init`. Confirm expected catalogs appear in `duckdb_databases()`. If external processes require file access, checkpoint and detach before handoff.

## Attach semantics and options

To persist a database without mutating existing aliases, append:

```sql
ATTACH IF NOT EXISTS '/absolute/path/analytics.duckdb' AS analytics;
```

Common attach options:

| Option | Function |
| --- | --- |
| `READ_ONLY` | Mount files for concurrent readers or remote storage over HTTPS/S3. |
| `STORAGE_VERSION 'v1.5.6'` | Create new storage version 68 files readable by DuckDB 1.5.6. DuckDB 1.4 cannot read them. `v1.5.0` writes an identical header. |
| `ENCRYPTION_KEY '...'` | Open an encrypted database. Load `httpfs` first for OpenSSL hardware acceleration. |
| `TYPE sqlite` | Open a SQLite file. Hand off to `duckdb-files`. |
| `ATTACH OR REPLACE` | Forcefully rebind an existing alias. Destructive; confirm with user first. |

If the user requested a default catalog or the state file lacks a `USE` command, append `USE analytics;`. Without an explicit `USE`, DuckDB defaults to `memory`, causing bare `SHOW TABLES;` to appear empty despite valid attachments.

The `-init` flag is CLI-specific; Python and client drivers must issue `ATTACH` programmatically. Init files execute both SQL and dot commands; any SQL or syntax error immediately aborts startup with exit code 1.

To validate attachment in isolation before persisting, run once directly, then verify with `-init`:

```bash
duckdb -json -c "ATTACH '/absolute/path/analytics.duckdb' AS analytics; SELECT database_name, path, tags['storage_version'] AS storage_version FROM duckdb_databases();"
duckdb -init .duckdb/state.sql -json -c "SHOW TABLES;"
```

## Storage version management

Inspect active storage versions via:

```sql
SELECT database_name, path, tags['storage_version'] AS storage_version, readonly, type
FROM duckdb_databases()
WHERE NOT internal;
```

`tags['storage_version']` reports the minimum compatibility floor, not raw internal integers. Storage version 69 reports `v2.0.0+` (DuckDB 1.x cannot open). Storage version 68 reports `v1.5.0+`.

Opening a legacy 1.x file in DuckDB 2.0 does not upgrade it; standard reads and writes preserve existing storage versions in place. Upgrading an existing file to storage 69 occurs only when mounting via `ATTACH '<path>' AS alias (STORAGE_VERSION 'latest');` followed by a write. Never pass `STORAGE_VERSION 'latest'` unless the user explicitly requested a file format upgrade. To pin formats for older readers, follow `duckdb-migrate`.

## Catalog exploration

Introspect tables within the target catalog:

```sql
SELECT schema_name, table_name, estimated_size, column_count
FROM duckdb_tables()
WHERE database_name = 'analytics' AND NOT internal
ORDER BY schema_name, table_name;
```

Inspect table schemas for up to 20 relevant tables:

```sql
DESCRIBE analytics.main.table_name;
```

`estimated_size` represents an approximation. If the user requires exact row counts or `estimated_size` is small, run `count(*)`.

If schemas are nested, join `duckdb_tables()` with `duckdb_schemas()` on both schema and database OIDs:

```sql
SELECT s.parent_schema, t.schema_name, t.table_name
FROM duckdb_tables() AS t
JOIN duckdb_schemas() AS s ON t.schema_oid = s.oid AND t.database_oid = s.database_oid
WHERE t.database_name = 'analytics' AND s.parent_schema IS NOT NULL;
```

Report the absolute path, alias, state file path, storage version, and discovered tables. Pass `-init` with the state file in subsequent skill invocations.

## Concurrency, durability, and detach

Across processes, native DuckDB files enforce single-writer or multi-reader exclusivity. A writer process locks the database against read-only processes, and an active reader blocks incoming writers. Within a single process, multiple connections share read-write access under MVCC, though opening a secondary connection with differing configuration (such as `read_only=True`) fails. For concurrent cross-process read and write access, hand off to `duckdb-quack` or `duckdb-lakehouse`.

To persist WAL changes to the database file:

```sql
CHECKPOINT analytics;        -- Flush WAL to database file; fails if transactions are active
FORCE CHECKPOINT analytics;  -- Wait for checkpoint lock, then flush (supported since 1.4)
```

On clean process termination, DuckDB checkpoints and removes the WAL. The setting `checkpoint_on_detach` accepts `ENABLED`, `DISABLED`, or `DEFAULT` (not boolean values).

`VACUUM` does not shrink database files on disk. `CHECKPOINT` frees deleted-row storage blocks for internal reuse without guaranteeing file truncation. On legacy storage versions, checkpoint vacuum skips tables containing ART indexes unless `vacuum_rebuild_indexes` was configured at startup or attach time (deprecated fallback).

To release cross-process file locks, detach the database. DuckDB prevents detaching the active catalog; switch catalogs before detaching:

```sql
ATTACH ':memory:' AS memory_db;
USE memory_db;
DETACH analytics;
```

Terminating the sole Python process releases database file locks. Because locks persist as long as any connection holds the file handle, explicitly issue `DETACH` in SQL when immediate lock release is required.

## Copy, export, and sharing

To transfer schemas and data directly between catalogs:

```sql
COPY FROM DATABASE analytics TO archive;
```

`COPY FROM DATABASE` requires an already-attached target catalog without conflicting table names; the destination database storage version governs the output file format.

To back up a database, target an empty directory: `EXPORT DATABASE 'backup_dir' (FORMAT parquet);`. Default export outputs SQL and CSV without purging existing files. To restore, ensure the target catalog contains no colliding objects and run `IMPORT DATABASE 'backup_dir';`. For cross-version format conversions, see `duckdb-migrate`.

To share datasets without distributing data files or credentials, publish a views-only catalog. A views-only catalog is a lightweight `.duckdb` file containing view definitions over remote object storage:

```sql
-- Publisher creates catalog
CREATE VIEW sales AS
SELECT * FROM read_parquet('s3://bucket/sales/*.parquet');

-- Consumer mounts catalog read-only
LOAD httpfs;
ATTACH 'https://example.com/catalog.duckdb' AS shared (READ_ONLY);
SELECT * FROM shared.sales;
```

Consumers require direct read permissions and storage credentials for the underlying object store. Local file paths inside views work only when all consumers share identical filesystem paths. For secret management, see `duckdb-files`. For a hosted writable endpoint, see `duckdb-quack`.

## Verify

Validate the state file and attached catalogs in an isolated CLI call:

```bash
duckdb -init .duckdb/state.sql -agent -c \
  "SELECT database_name, tags['storage_version'] FROM duckdb_databases() WHERE NOT internal;"
```

Confirm each configured alias appears exactly once with its expected storage version. Verify idempotency: repeated execution must not duplicate the `ATTACH` because the state file specifies `ATTACH IF NOT EXISTS`.

## References

- [ATTACH and DETACH](https://duckdb.org/docs/2.0/sql/statements/attach.html) defines syntax, flags, and storage constraints.
- [CHECKPOINT](https://duckdb.org/docs/2.0/sql/statements/checkpoint.html) documents WAL flushing and locking mechanisms.
- [Concurrency](https://duckdb.org/docs/2.0/connect/concurrency.html) covers process exclusivity and thread safety.
- [Storage](https://duckdb.org/docs/2.0/internals/storage.html) specifies storage version numbers and format compatibility.
- [Views-only database](https://duckdb.org/docs/2.0/guides/network_cloud_storage/duckdb_views_only.html) details catalog sharing architectures.
- [Reclaiming space](https://duckdb.org/docs/2.0/operations_manual/footprint_of_duckdb/reclaiming_space.html) covers WAL checkpoints and vacuum limitations.
- [duckdb_databases](https://duckdb.org/docs/2.0/sql/meta/duckdb_table_functions.html#duckdb_databases) catalogs system introspection functions.
- `duckdb_secrets()` masks secret values while displaying `key_id`. Log secret names and provider types only; never display row contents.
- The state file pattern adapts the upstream `attach-db` skill from https://github.com/duckdb/duckdb-skills (MIT).
