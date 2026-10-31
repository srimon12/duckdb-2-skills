---
name: duckdb-migrate
description: >
  Migrate DuckDB 1.4 or 1.5 deployments to 2.0. Covers storage version 69,
  lambda and regex breaks, removed settings, export/import, and phased cutover.
  Use when the user asks to migrate or upgrade to DuckDB 2.0, when 1.x binaries
  cannot open a file, or to pin backward-compatible storage versions.
---

# DuckDB 2.0 migration

Execute migration steps sequentially. For Python API breaking changes, see `duckdb-python`. For lambda syntax rules, see `duckdb-sql`. Before upgrading a binary shared across processes, upgrade all readers to 2.0 or pin new files to a legacy storage version.

Support windows:

| Line | End of community support |
| --- | --- |
| 2.0.0 LTS | 2027-10-22 |
| 1.4 LTS | 2026-11-17 |
| 1.5 | 2027-03-01 |

The release calendar tentatively schedules 2.0.1 for 2026-11-18. For mission-critical workloads, wait for patch releases and validate on a shadow copy; 1.5 community support continues through 2027-03-01.

## Order of work

1. **Inventory**: Catalog every process, database file, client library, and extension accessing DuckDB.
2. **Pin format**: Enforce backward-compatible storage versions on any file that older readers must open.
3. **Back up**: Create file backups or export catalogs and data; verify the restore procedure.
4. **Shadow run**: Spin up a shadow database and replay production workloads against DuckDB 2.0.
5. **Upgrade**: Install the 2.0 binary and update all extensions concurrently.
6. **SQL checks**: Scan queries for syntax and semantic breaks, then run the full test suite.
7. **Cut over**: Shift live workloads to 2.0, retaining previous binaries and backups until verification completes.

For step-by-step gate criteria and automated search patterns, see [references/checklist.md](references/checklist.md).

## Storage

DuckDB 2.0 creates files using storage version 69 by default. DuckDB 1.x binaries cannot read version 69 files. DuckDB 1.5.6 reads versions 64 through 68; DuckDB 1.5.5 and earlier print version number `999`. A default 1.5.6 file uses storage version 64, not 68 (version 68 requires explicit `-storage-version v1.5.6`). DuckDB 2.0 reads and writes older storage versions without automatic upgrade; writes preserve the file's existing storage version.

| Reader floor | Startup pin | Compatibility tag | Storage version |
| --- | --- | --- | --- |
| 2.0 only | default or `latest` | `v2.0.0+` | 69 |
| 1.5.6 | `-storage-version v1.5.6` | `v1.5.0+` | 68 |
| 1.4 | `-storage-version v1.4.0` | `v1.4.0+` | 67 |

A 1.4 reader cannot open storage 68. A 1.5 reader cannot open storage 69. For client, BI, dbt, Ibis, and MCP compatibility, see [references/clients.md](references/clients.md).

To inspect the compatibility floor of an attached database:

```sql
SELECT database_name, tags['storage_version']
FROM duckdb_databases();
```

The tag reflects the compatibility floor: version 69 reports `v2.0.0+`, version 68 reports `v1.5.0+`, and default 1.5.6 reports `v1.0.0+`. The on-disk header for version 69 stores `999`; never parse versions via `hexdump`.

### Storage version pinning

To create a new database accessible to 1.5.6 readers:

```bash
duckdb my.db -storage-version v1.5.6 -c "CREATE TABLE t (x INT);"
```

If the oldest reader is 1.4, use `-storage-version v1.4.0`. To pin storage version within SQL:

```sql
SET storage_compatibility_version = 'v1.5.6';
ATTACH 'file.db' (STORAGE_VERSION 'v1.5.6');
```

In Python connections, supply `config={"storage_compatibility_version": "v1.5.0"}` (or `"v1.4.0"` for 1.4). The configuration sets the minimum compatibility floor; check `tags['storage_version']` after the first write. `latest` resolves to version 69.

Scoping rules:
- `-storage-version` sets the version for new databases and subsequent attaches within that CLI session; it is ignored on an existing main file.
- `SET storage_compatibility_version` applies only to subsequent `ATTACH` statements, never to the currently open main database.
- To upgrade an existing database to 2.0 format, run `ATTACH 'existing.db' (STORAGE_VERSION 'latest')` and execute a write.
- Specifying a lower `STORAGE_VERSION` on an existing database raises an error; storage versions cannot be downgraded in place.

### Database transfer: COPY vs EXPORT/IMPORT

To move an existing database to 2.0 storage, back up the file first. Choose the transfer method based on structure:

```sql
ATTACH 'old.db' AS old (READ_ONLY);
ATTACH 'new.db' AS new (STORAGE_VERSION 'v1.5.6');
COPY FROM DATABASE old TO new;
```

`COPY FROM DATABASE` copies schema, constraints, indexes, sequences, macros, and data into an attached target. The target's `STORAGE_VERSION` determines output format. Existing schemas are reused; same-named tables, sequences, or macros abort the operation.

For cross-version migration across different environments, use `EXPORT` and `IMPORT`:

```bash
# Export using source binary (this example writes Parquet; omit FORMAT for CSV)
duckdb old.db -c "EXPORT DATABASE 'export_dir' (FORMAT parquet);"
# Import using target binary
duckdb new.db -c "IMPORT DATABASE 'export_dir';"
```

The export directory must be empty. `IMPORT DATABASE` aborts if any same-named object or schema already exists in the target database.

To flush the write-ahead log (WAL) before copying, issue `CHECKPOINT` or `FORCE CHECKPOINT`. Clean exits remove the WAL automatically. To configure detachment checkpoint behavior, set `checkpoint_on_detach` to `ENABLED`, `DISABLED`, or `DEFAULT` (not boolean).

## SQL text

Scan application queries, dbt models, and scripts for syntax and semantic breaking changes:

| Pattern | 2.0 behavior | Replacement |
| --- | --- | --- |
| Legacy arrow (`->`) | Disabled by default | `lambda x: expr` |
| `1 // 0`, `1 % 0` | Raises division-by-zero error | `TRY(expr)`; `error_on_division_by_zero` is deprecated |
| `col ~ 'pat'`, `col !~ 'pat'` | Matches substring (PostgreSQL standard) | `regexp_full_match(col, 'pat')` for 1.x whole-string match |
| `s3://bucket/key?s3_access_key_id=...` | Query parameters treated as literal key path | Store credentials in a Secret; `s3_enable_deprecated_url_parameters` temporarily |
| `custom_profiling_settings` | Setting removed | `tracked_metrics` |
| `enable_http_logging`, `http_logging_output` | Settings removed | `CALL enable_logging('HTTP')` |
| `profiling_mode` | Deprecated and ignored | `SET enable_profiling` |
| `preserve_identifier_case` | Boolean deprecated; expects string enum | `'preserve_case'`, `'lowercase'`, or `'uppercase'` |
| `error_on_division_by_zero = false` | Deprecated | Wrap expressions in `TRY(expr)` |
| `table_function_identifier_conversion` | Deprecated | Explicitly quote table-function arguments |
| Unquoted `read_csv(file.csv)` | Implicit identifier conversion deprecated | `read_csv('file.csv')` |
| `CREATE TABLE t AS SELECT NULL AS x` | Assigns column type `"NULL"`; typed inserts fail | `SELECT NULL::INTEGER AS x`; `legacy_disable_null_type` is deprecated |
| `X'4142'`, `B'1010'` | Inferred as `BLOB` and `BIT`, not `VARCHAR` | Explicitly cast or compare matching data types |
| `2 * 3!` | Evaluates to `12` (`2 * (3!)`), not `720` | Parenthesize `(2 * 3)!` to retain 1.x factorial precedence |

When migrating regex filters (`~`, `!~`), verify match semantics. DuckDB 1.x matched entire strings; DuckDB 2.0 matches substrings. Unadjusted queries like `WHERE msg ~ 'ERROR'` return additional matching rows.

To temporarily unblock legacy queries during migration:

```sql
SET enable_legacy_parser = true;
```

This setting autoloads the legacy parser extension as a syntax fallback, not a semantic time machine. It rejects simplified `FROM ... NEAREST` syntax (explicit `INNER JOIN ... NEAREST` remains supported). Use it strictly as a temporary bridge while updating query text.

## CLI and deployment

For CLI output formatting and `max_execution_time`, see `duckdb`.

CLI sessions since 1.5 route messages through `shell_log_storage`, omitting them from `duckdb_logs`. To query CLI logs via SQL, enable memory storage:

```sql
CALL enable_logging(storage = 'memory');
SELECT * FROM duckdb_logs();
```

Deployment constraints:
- **ICU collation and time zones**: ICU logic moved from core to the `icu` extension. Official binaries autoload `icu` automatically (no SQL changes required); custom builds that previously linked ICU must explicitly load the `icu` extension.
- **Build prerequisites**: Building DuckDB 2.0 requires a C++17 compiler and CMake (amalgamation builds are deprecated). Precompiled Linux binaries require glibc 2.28 or newer.
- **C API v2**: Ships with 2.0 but remains experimental; do not assume ABI stability.
- **macOS x86_64 deprecation**: Community extensions no longer build for `osx_amd64` (core extensions still build). DuckDB 2.1 will drop `osx_amd64` completely; plan hardware upgrades prior to 2.1.

## Python and extensions

Python installations require Python 3.11+. For breaking changes to relations, fetching, Arrow conversion, thread safety, and transactions, see `duckdb-python`.

Extension binaries are strictly compiled against specific DuckDB versions. After updating the DuckDB binary, run `UPDATE EXTENSIONS;` or `FORCE INSTALL <name>;` and restart the process. Core extensions `json`, `parquet`, and `icu` ship statically linked with official binaries.

## Rollback

Retain previous binaries and uncompressed file backups until the 2.0 deployment completes all workload cycles. In-place storage version upgrades cannot be reversed. If a database file was written in version 69, restore from the backup copy or execute a down-copy via `COPY FROM DATABASE` into a target attached with `STORAGE_VERSION 'v1.5.6'`. Never attempt to open a storage version 69 file with DuckDB 1.x.

## Verify

Validate the binary version and new database storage format:

```bash
duckdb -no-agent --version
tmp=$(mktemp -d)
duckdb -agent "$tmp/check.duckdb" -c "CREATE TABLE t AS SELECT 42 AS a; SELECT tags['storage_version'] FROM duckdb_databases();"
rm -rf "$tmp"
```

Verify that the CLI reports 2.0.x and the newly created database reports compatibility tag `v2.0.0+`. In-memory databases do not report a storage version tag. After binary verification, execute the full application test suite against a restored shadow database.

## References

- [DuckDB 2.0 Migration Guide](https://duckdb.org/docs/2.0/operations_manual/migration.html) (breaking changes and migration overview)
- [Storage Versions](https://duckdb.org/docs/2.0/internals/storage.html) (storage formats and compatibility matrix)
- [Release Calendar](https://duckdb.org/release_calendar.html) (release timelines and support lifecycles)
- [ATTACH Statement](https://duckdb.org/docs/2.0/sql/statements/attach.html) (`STORAGE_VERSION` syntax)
- [Python Migration Guide](https://duckdb.org/docs/2.0/clients/python/migration.html) (client-specific breaking changes)
- [Regular Expressions](https://duckdb.org/docs/2.0/sql/functions/regular_expressions.html) (`~` and `!~` match semantics)
- [Checklist & Grep Patterns](references/checklist.md) (phase gates and automated scanning patterns)
- [Client Compatibility](references/clients.md) (BI, dbt, Ibis, and MCP compatibility matrix)
- Storage tags, pinned 1.5 storage files, `COPY FROM DATABASE`, and agent-mode outputs verified on DuckDB 2.0.0.
