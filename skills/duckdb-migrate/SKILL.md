---
name: duckdb-migrate
description: >
  Move a DuckDB 1.4 or 1.5 deployment to 2.0. Covers storage version 69, the
  lambda and regex breaks, removed settings, export/import, and the order of
  work. Use when the user says migrate, upgrade to 2.0, a 1.x binary cannot
  open the file, or the storage version needs pinning.
---

# DuckDB 2.0 migration

Do this in order. Python API changes are `duckdb-python`. Lambda syntax details are `duckdb-sql`. Do not upgrade a binary that other processes still use until every process that opens the same file is on 2.0, or the file is pinned to an older storage version.

Support windows:

| Line | End of community support |
| --- | --- |
| 2.0.0 LTS | 2027-10-22 |
| 1.4 LTS | 2026-11-17 |
| 1.5 | 2027-03-01 |

The calendar lists 2.0.1 for 2026-11-18 and marks it tentative. For a mission-critical workload, wait for patch releases and run a shadow copy first. 1.5 remains supported through March 2027, so the wait is possible.

## Order of work

1. Inventory every process, file, extension, and client that touches DuckDB.
2. Pin the output format for any file that older processes must read.
3. Build a shadow copy and run the real workload against 2.0.
4. Back up the catalog and data, or export the database.
5. Upgrade the binary and every extension together.
6. Run the SQL-text checks and the test suite.
7. Cut over, then keep the old binary until the rollback window closes.

The detailed checklist and grep patterns are in [references/checklist.md](references/checklist.md).

## Storage

New files created by 2.0 use storage version 69. DuckDB before 2.0 cannot read them. 1.5.6 reports that it can read versions 64 through 68. 1.5.5 and earlier report version number 999 for the same file. A default 1.5.6 file is storage version 64, not 68; 68 is opt-in with `-storage-version v1.5.6`.

DuckDB 2.0 can read and write older files, and those writes keep the old storage version. Opening a 1.x file does not upgrade it.

Read the version you actually have:

```sql
SELECT database_name, tags['storage_version']
FROM duckdb_databases();
```

The tag is a compatibility floor, not the exact number. A 69 file reports `v2.0.0+`; a 68 file reports `v1.5.0+`; a default 1.5.6 file reports `v1.0.0+`. The on-disk header for a 69 file holds 999, so do not read the number from `hexdump`.

Create a file that 1.5.6 can still open:

```bash
duckdb my.db -storage-version v1.5.6 -c "CREATE TABLE t (x INT);"
```

The same choice inside SQL:

```sql
SET storage_compatibility_version = 'v1.5.6';
ATTACH 'file.db' (STORAGE_VERSION 'v1.5.6');
```

`latest` means version 69. Python uses `config={"storage_compatibility_version": "v1.5.0"}`. The string is a minimum version, not a promise that every 1.5 patch shares one storage number. Check `tags['storage_version']` after the first write.

`SET storage_compatibility_version` affects later attaches, not the already-open main database. `-storage-version` affects the main file and new files attached in that session, but it is ignored for an existing main file. Use it before the file path, not in a `-c` command after the file is open.

Move an existing file onto 2.0 storage only when the user asks, and only after a backup:

```bash
# old binary
duckdb mydata.old.db -c "EXPORT DATABASE 'tmp'"
# 2.0 binary
duckdb mydata.new.db -c "IMPORT DATABASE 'tmp'"
```

`ATTACH existing (STORAGE_VERSION 'latest')` followed by a write upgrades the file to 69. A lower `STORAGE_VERSION` on an existing file errors; the version cannot be lowered in place.

`COPY FROM DATABASE` is the other documented method. The target must be attached and empty, and its `STORAGE_VERSION` controls the output:

```sql
ATTACH 'old.db' AS old (READ_ONLY);
ATTACH 'new.db' AS new (STORAGE_VERSION 'v1.5.6');
COPY FROM DATABASE old TO new;
```

A clean exit checkpoints and removes the WAL. `CHECKPOINT` and `FORCE CHECKPOINT` flush it manually. `checkpoint_on_detach` takes `ENABLED`, `DISABLED`, or `DEFAULT`, not a boolean.

`EXPORT DATABASE` writes CSV by default. Add `(FORMAT parquet)` when Parquet is expected. The directory should be empty, and `IMPORT DATABASE` needs a fresh database.

## SQL text

Search application SQL for these. The replacement behavior is specified in `duckdb-sql` and the migration guide.

| Pattern | 2.0 behavior | Replacement |
| --- | --- | --- |
| `x -> expr` | Disabled by default | `lambda x: expr` |
| `1 // 0`, `1 % 0` | Raise | `TRY(expr)`; the setting is deprecated |
| `col ~ 'pat'`, `col !~ 'pat'` | Partial match, like PostgreSQL | `regexp_full_match` for the 1.x full-match behavior |
| `s3://bucket/key?s3_access_key_id=...` | The query string is part of the key | A secret; `s3_enable_deprecated_url_parameters` is the temporary bridge |
| `custom_profiling_settings` | Removed | `tracked_metrics` |
| `enable_http_logging`, `http_logging_output` | Removed | `CALL enable_logging('HTTP')` |
| `profiling_mode` | Deprecated and ignored | `SET enable_profiling` |
| `preserve_identifier_case = true/false` | Now a string | `'preserve_case'`, `'lowercase'`, or `'uppercase'` |
| `error_on_division_by_zero = false` | Works but deprecated | `TRY(expr)` |
| `table_function_identifier_conversion` | Works but deprecated | Quote table-function arguments |
| Unquoted `read_csv(file.csv)` | Implicit identifier conversion is deprecated | `read_csv('file.csv')` |

The regex change is easy to miss because the migration guide does not list it. A 1.x filter such as `WHERE msg ~ 'ERROR'` matched the whole string; on 2.0 it matches a substring and returns more rows.

The legacy parser is a grammar fallback, not a semantic one:

```sql
SET enable_legacy_parser = true;
```

The setting autoloads the extension. It rejected `NEAREST` in probing, and the manual's listed legacy quirks did not reproduce. Use it only to unblock a specific query, file the query, and remove it from saved SQL.

## CLI and deployment

Output mode and `max_execution_time` belong to `duckdb`. Do not restate them here.

CLI logs since 1.5 use `shell_log_storage` and do not appear in `duckdb_logs`. Enable memory storage first:

```sql
CALL enable_logging(storage = 'memory');
SELECT * FROM duckdb_logs();
```

ICU left the core build. Time zones, calendars, and collations come from the `icu` extension, which official binaries load. No SQL change. A custom build that linked ICU must load the extension.

C++17 is required to build 2.0. Amalgamation builds are deprecated; custom builds should use CMake. Linux binaries need glibc 2.28 or newer. C API v2 ships but is not stable. Do not promise ABI stability.

Community extensions are no longer built for `osx_amd64`. Core extensions still are. 2.1 drops `osx_amd64` entirely. Plan the hardware upgrade before 2.1.

## Python and extensions

Python 3.11 is required. The relation, fetch, Arrow, thread, and transaction changes are in `duckdb-python`.

Extension builds are tied to the DuckDB version. After upgrading the binary, run `UPDATE EXTENSIONS` or `FORCE INSTALL` the extensions you use, and restart the process. Statically linked `json`, `parquet`, and `icu` ship with the binary.

## Rollback

Keep the old binary and a copy of every file until the new version has passed the workload. An in-place upgrade is not reversible. If a file was created by 2.0, the rollback is the old copy, or a tested down-copy with `COPY FROM DATABASE` into a target attached with `STORAGE_VERSION 'v1.5.6'`. Do not try to open a 69 file with 1.x.

## Verify

```bash
duckdb -no-agent --version
tmp=$(mktemp -d)
duckdb -agent "$tmp/check.duckdb" -c "CREATE TABLE t AS SELECT 42 AS a; SELECT tags['storage_version'] FROM duckdb_databases();"
rm -rf "$tmp"
```

The version must be 2.0, and the new file must report `v2.0.0+`. An in-memory database has no storage tag. Then run the application test suite against the shadow copy.

## References

- [Migration guide](https://duckdb.org/docs/2.0/operations_manual/migration.html) owns the breaking changes.
- [Storage versions](https://duckdb.org/docs/2.0/internals/storage.html) owns the version table and conversion methods.
- [Release calendar](https://duckdb.org/release_calendar.html) owns support dates.
- [ATTACH](https://duckdb.org/docs/2.0/sql/statements/attach.html) owns `STORAGE_VERSION`.
- [Python migration](https://duckdb.org/docs/2.0/clients/python/migration.html) owns the client changes.
- [Regex functions](https://duckdb.org/docs/2.0/sql/functions/regular_expressions.html) owns the `~` change.
- The grep checklist and phase gates are in [references/checklist.md](references/checklist.md).
- Storage tags, the pinned 1.5 file, `COPY FROM DATABASE`, and agent-mode errors were probed on DuckDB 2.0.0.
