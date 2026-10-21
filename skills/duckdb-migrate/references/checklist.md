# Migration checklist

Read this when running the migration from `duckdb-migrate/SKILL.md`. Each phase ends in a gate. Do not start the next phase until the gate passes.

## Phase 0: inventory

```bash
duckdb --version
which -a duckdb
```

```sql
SELECT version();
SELECT database_name, path, tags['storage_version'] AS storage_version, readonly, type
FROM duckdb_databases();

SELECT extension_name, installed, loaded, extension_version, install_mode
FROM duckdb_extensions();

SELECT name, value
FROM duckdb_settings()
WHERE name IN (
  'storage_compatibility_version', 'threads', 'max_memory',
  'temp_directory', 'preserve_insertion_order', 'checkpoint_on_detach',
  'allow_persistent_secrets', 'enable_external_access'
);
```

List every service, cron job, notebook, and library that opens a `.duckdb` file. Record the owner and the binary path for each.

**Gate:** the list is complete, and every shared file has an owner.

## Phase 1: pin the storage format

If any process stays on 1.4 or 1.5, create new files with a compatible version.

```bash
duckdb my.db -storage-version v1.5.6 -c "CREATE TABLE t (x INT);"
```

```sql
SET storage_compatibility_version = 'v1.5.6';
ATTACH 'my.db' (STORAGE_VERSION 'v1.5.6');
```

Python:

```python
duckdb.connect("my.db", config={"storage_compatibility_version": "v1.5.0"})
```

**Gate:** `tags['storage_version']` reports the expected floor, not `v2.0.0+`, for every file an older process reads.

## Phase 2: SQL text

Run these searches over application SQL, dbt models, notebooks, and saved queries.

```bash
rg -n --glob '*.sql' --glob '*.py' --glob '*.md' \
  -e 'x\s*->\s*' \
  -e '//\s*0' \
  -e '%\s*0' \
  -e '[!]?~[*]?\s*\x27' \
  -e 's3_access_key_id' \
  -e 'custom_profiling_settings' \
  -e 'enable_http_logging' \
  -e 'http_logging_output' \
  -e 'profiling_mode' \
  -e 'preserve_identifier_case' \
  -e 'error_on_division_by_zero' \
  -e 'table_function_identifier_conversion' \
  -e 'read_csv\([^'\'']' \
  .
```

| Hit | Fix |
| --- | --- |
| `x -> expr` | `lambda x: expr` |
| `// 0`, `% 0` | `TRY(expr)` |
| `~`, `!~` | Decide partial or full; use `regexp_full_match` for full |
| `s3_access_key_id` | A secret |
| `custom_profiling_settings` | `tracked_metrics` |
| `enable_http_logging`, `http_logging_output` | `CALL enable_logging('HTTP')` |
| `profiling_mode` | `SET enable_profiling` |
| `preserve_identifier_case` | `'preserve_case'`, `'lowercase'`, or `'uppercase'` |
| `error_on_division_by_zero` | `TRY(expr)` |
| `table_function_identifier_conversion` | Quote the argument |
| Unquoted `read_csv(path)` | `read_csv('path')` |

`->` also appears in JSON and in C code. Review each hit.

**Gate:** every hit is fixed or has a written reason to stay.

## Phase 3: settings and CLI

- Replace `-csv` with `-agent` for output a model reads, and `-json` for output a parser reads.
- Replace removed settings.
- Check `max_execution_time` is milliseconds.
- Check `~/.duckdbrc` for a mode or startup setting that hides agent mode. Use `-no-init` to test without it.
- Check scripts that parse errors. Agent mode writes JSON to stderr; `-json` writes text errors to stderr and can leave a partial `[` on stdout.

**Gate:** a representative command produces the expected output under the new binary.

## Phase 4: extensions and clients

```sql
UPDATE EXTENSIONS;
SELECT extension_name, installed, loaded, extension_version
FROM duckdb_extensions()
WHERE extension_name IN ('httpfs', 'spatial', 'json', 'parquet', 'icu');
```

Restart the process after the update. Python code needs the `duckdb-python` changes. A custom build that linked ICU must load the `icu` extension.

**Gate:** every extension loads, and the Python test suite runs on 3.11 or newer.

## Phase 5: back up and test the restore

Back up the file and test the restore before running a shadow workload. If the file must move to 2.0 storage:

```bash
# old binary
duckdb mydata.old.db -c "EXPORT DATABASE 'tmp'"
# 2.0 binary
duckdb mydata.new.db -c "IMPORT DATABASE 'tmp'"
```

`EXPORT DATABASE` writes CSV by default; add `(FORMAT parquet)` if you expect Parquet. The export directory should be empty, and `IMPORT DATABASE` needs a fresh database.

Or copy between attached databases. The target must be empty, and its storage version controls the output:

```sql
ATTACH 'old.db' AS old (READ_ONLY);
ATTACH 'new.db' AS new (STORAGE_VERSION 'v1.5.6');
COPY FROM DATABASE old TO new;
```

**Gate:** the restored copy opens, the row counts match, and the old file is still available.

## Phase 6: shadow run

Run the real workload against the restored copy. Compare row counts, aggregates, and a sample of results. Check query plans for scans that lost pushdown.

```bash
duckdb shadow.db -c ".read workload.sql"
```

**Gate:** the shadow run passes, and every difference is explained.

## Phase 7: cut over

Upgrade the binary and every extension together. Roll out to one process first. Keep the old binary and the backup until the rollback window closes.

**Gate:** production reads and writes work for one full cycle.

## Rollback

An in-place storage upgrade is not reversible. Roll back by restoring the file copy, switching back to the old file, or using a tested down-copy with `COPY FROM DATABASE` into a target attached with `STORAGE_VERSION 'v1.5.6'`. Do not try to open a 2.0 file with 1.x and expect a downgrade path.

**Gate:** the restore was tested, not only the backup.

## Pre-flight SQL

```sql
SELECT version() AS engine;
SELECT database_name, path, tags['storage_version'] AS storage_version
FROM duckdb_databases();
SELECT extension_name, installed, loaded, extension_version, install_mode
FROM duckdb_extensions()
ORDER BY extension_name;
SELECT schema_name, table_name, estimated_size
FROM duckdb_tables()
WHERE NOT internal
ORDER BY estimated_size DESC
LIMIT 20;
```

## References

- https://duckdb.org/docs/2.0/operations_manual/migration.html
- https://duckdb.org/docs/2.0/internals/storage.html
- https://duckdb.org/docs/2.0/release_calendar.html
- https://duckdb.org/docs/2.0/sql/functions/regular_expressions.html
