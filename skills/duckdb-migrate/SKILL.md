---
name: duckdb-migrate
description: >
  Move a DuckDB 1.4 or 1.5 deployment to DuckDB 2.0. Storage format, lambdas,
  integer division, S3 URL parameters, removed settings, and the order of
  work. Use when the user says migrate, upgrade to 2.0, storage version, or
  /duckdb-migrate.
---

# Migrate to DuckDB 2.0

Do this in order. Python API changes are `duckdb-python`. Lambda syntax details are `duckdb-sql`. Do not upgrade a binary that other processes still use until every process that opens the same file is on 2.0, or the file is pinned to an older storage version.

Support windows from the release calendar:

| Line | End of community support |
| --- | --- |
| 2.0.0 LTS | 2027-10-22 |
| 1.4 LTS | 2026-11-17 |
| 1.5 | 2027-03-01 |

The calendar lists 2.0.1 for 2026-11-18 and marks that date tentative. For a mission-critical workload, the migration guide says to wait for patch releases and to run a shadow copy first. 1.5 remains supported through March 2027 so that wait is possible.

## Storage

New files created by 2.0 use storage version 69. DuckDB before 2.0 cannot read them. 1.5.6 reports that it can read versions 64 through 68. 1.5.5 and earlier report version number 999 for the same file. DuckDB 2.0 can read and write older files, and those writes keep the old storage version.

Read the version you actually have:

```sql
SELECT database_name, tags['storage_version']
FROM duckdb_databases();
```

To create a file that 1.5.6 can still open:

```bash
duckdb my.db -storage-version v1.5.6 -c "CREATE TABLE t (x INT);"
```

The same choice inside SQL:

```sql
SET storage_compatibility_version = 'v1.5.6';
ATTACH 'file.db' (STORAGE_VERSION 'v1.5.6');
```

`latest` means version 69. Python uses `config={"storage_compatibility_version": "v1.5.0"}` when the file must stay readable by the 1.5 line. The string is a minimum version, not a promise that every 1.5 patch shares one storage number. Check `tags['storage_version']` after the first write.

Move an existing file onto 2.0 storage only when the user asks, and only after a backup:

```bash
# old binary
duckdb mydata.old.db -c "EXPORT DATABASE 'tmp'"
# 2.0 binary
duckdb mydata.new.db -c "IMPORT DATABASE 'tmp'"
```

`COPY FROM DATABASE` is the other documented method. See the storage page.

## SQL text

Search application SQL for these. The replacement behavior is specified in `duckdb-sql` and the migration guide.

- `x -> expr`. Disabled. Write `lambda x: expr`. The bridge setting `lambda_syntax = 'enable_single_arrow'` disappears in 2.1.
- `1 // 0` and `1 % 0`. They now raise. `TRY(expr)` or `error_on_division_by_zero = false`. `1 / 0` is still `inf`.
- `s3://bucket/key?s3_access_key_id=...`. The query string is part of the key. Use a secret. `duckdb-files` has the secret statements.
- `custom_profiling_settings`. Removed. Use `tracked_metrics`.
- `enable_http_logging` and `http_logging_output`. Removed. Use `CALL enable_logging('HTTP')`.
- `profiling_mode`. Deprecated and ignored. Use `PRAGMA enable_profiling`.
- `preserve_identifier_case` is now `'preserve_case'`, `'lowercase'`, or `'uppercase'`. `true` and `false` still map to `'preserve_case'` and `'lowercase'`.

If a query that parsed on 1.x fails on 2.0, `duckdb-sql` has the `legacy_parser` fallback. File the query. Do not turn the fallback on for a whole deployment as the first step.

ICU left the core build. Time zones and collations still come from the `icu` extension, which official binaries load. No SQL change. A custom build that used to link ICU must load the extension.

CLI logs since 1.5 use `shell_log_storage` and do not show up in `duckdb_logs`. Query them with `CALL enable_logging(storage = 'memory')`. Other clients still default to memory.

## References

- https://duckdb.org/docs/2.0/operations_manual/migration.html
- https://duckdb.org/docs/2.0/internals/storage.html
- https://duckdb.org/release_calendar.html
- https://duckdb.org/2026/10/21/announcing-duckdb-200.html
- https://duckdb.org/docs/2.0/clients/python/migration.html
