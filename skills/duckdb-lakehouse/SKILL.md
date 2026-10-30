---
name: duckdb-lakehouse
description: >
  Use DuckLake 1.1, Iceberg, Delta, and Unity Catalog from DuckDB 2.0. Covers
  catalog choice, attach options, snapshots and time travel, maintenance, and
  write limits. Use when the user mentions DuckLake, Iceberg, Delta, a
  lakehouse catalog, or asks which open table format to use.
---

# Lakehouse catalogs

For raw Parquet or CSV on object storage without a catalog, hand off to `duckdb-files`. This skill governs table formats and catalogs: DuckLake, Iceberg, Delta Lake, and Unity Catalog.

Run SQL with `duckdb`. Extensions (`ducklake`, `iceberg`, `delta`, `unity_catalog`) autoload on first use when installation is permitted; otherwise execute `INSTALL AND LOAD <extension>;`.

## Identify the path first

Before selecting an extension, identify the path format by inspecting directory signals. If no signal matches, list the directory and halt. Never glob data files when a catalog is authoritative.

| Signal | Format | First move |
| --- | --- | --- |
| `_delta_log/` | Delta | Run `delta_scan` or `ATTACH ... (TYPE delta)` |
| `metadata/version-hint.text` and `metadata/*.metadata.json` | Iceberg | Run `iceberg_scan` or attach a REST catalog |
| `ducklake:` URI or `ducklake_*` metadata tables | DuckLake | Run `ATTACH 'ducklake:...'` |
| Parquet or CSV files only | Plain files | Hand off to `duckdb-files` |

## Choose the format

| Format | Concurrent writers | Catalog | Time travel | DuckDB write support | Best fit |
| --- | --- | --- | --- | --- | --- |
| Native `.duckdb` | Single process | None | No | Full DDL and DML | Single-process analytics, embedded app state |
| DuckLake | Multi-writer (catalog DB) | DuckDB file, SQLite, or PostgreSQL | Snapshot ID or timestamp | DDL, DML, `MERGE`, ACID transactions | DuckDB-native lakehouse, multi-writer ACID |
| Iceberg | Multi-writer (REST catalog) | REST catalog for writes | Snapshot ID or timestamp | Create, insert, update, delete, merge, alter (merge-on-read) | Cross-engine lakehouse with existing REST catalog |
| Delta | Optimistic log (Unity for managed) | None for path-based tables | Table version or timestamp | Create and append only | Reading existing Delta, append-only ingestion |

Select by write requirements and concurrency architecture, not file layout.

## DuckLake

DuckLake 1.1 requires DuckDB 2.0.0+. DuckDB 2.0 reads and writes 1.0 catalogs seamlessly. New catalogs default to 1.1 unless configured otherwise by `ducklake_default_version`.

```sql
ATTACH 'ducklake:metadata.ducklake' AS lake;
ATTACH 'ducklake:sqlite:metadata.sqlite' AS lake (DATA_PATH 'my_files/');
ATTACH 'ducklake:postgres:dbname=postgres' AS lake (DATA_PATH 's3://bucket/path/');
```

When attaching DuckDB-file catalogs, `DATA_PATH` defaults to `<metadata>.files`. When creating SQLite or PostgreSQL catalogs, provide `DATA_PATH` explicitly. The metadata target is a catalog store, not a native database of user tables.
Key attach options: `READ_ONLY`, `CREATE_IF_NOT_EXISTS`, `DATA_INLINING_ROW_LIMIT`, `DUCKLAKE_VERSION '1.0'`, `ENCRYPTED`, `AUTOMATIC_MIGRATION`, `OVERRIDE_DATA_PATH`, `SNAPSHOT_VERSION`, and `SNAPSHOT_TIME` (see [references/catalogs.md](references/catalogs.md)).

When upgrading a 1.0 catalog for 1.1 features, back up metadata and data files, halt active writes, compaction, and cleanup, and verify client support. Reset the default version, then attach with write access:

```sql
RESET ducklake_default_version;
ATTACH 'ducklake:metadata.ducklake' AS lake (AUTOMATIC_MIGRATION true);
SELECT value FROM lake.options() WHERE option_name = 'version';
```

Migration is irreversible. If `ducklake_default_version='1.0'` remains set, subsequent normal attaches fail with `Cannot downgrade a DuckLake catalog`. Once migrated, omit `AUTOMATIC_MIGRATION` on routine attaches.
Version 1.1 enables nested schemas, the `"NULL"` type, epoch transforms (`epoch_year`, `epoch_month`, `epoch_day`, `epoch_hour`), `VARIANT` inlining into PostgreSQL or SQLite, multi-snapshot Puffin deletes, exact string statistics, `row_group_count`, and cross-schema compaction after `ADD COLUMN`.

Query snapshots and time travel:

```sql
SELECT * FROM lake.t AT (VERSION => 3);
SELECT * FROM lake.t AT (TIMESTAMP => TIMESTAMPTZ '2026-10-20 12:00:00+00');
SELECT * FROM ducklake_snapshots('lake');
SELECT ducklake_current_snapshot('lake');
```

`VERSION` specifies a snapshot ID, not a sequential commit number. Timestamps before the initial snapshot or in the future fail. The `AT` expression rejects subqueries.
Constraints support `NOT NULL` only. Primary keys, unique keys, check constraints, and secondary indexes are unsupported. Use `MERGE INTO` for upserts. DuckLake provides row lineage and an incremental change feed.

During `CHECKPOINT`, maintenance executes in strict order: (1) flush inlined data, (2) expire snapshots, (3) merge adjacent files, (4) rewrite data files, (5) cleanup old files, (6) delete orphaned files.
Before running maintenance, back up catalog files. Configure options via `CALL lake.set_option(...)`: `rewrite_delete_threshold`, `expire_older_than`, and `delete_older_than`. Set `auto_compact=false` to skip compaction; override target file size with `ducklake_target_file_size`.

```sql
CALL ducklake_merge_adjacent_files('lake', 'orders', schema => 'sales', max_compacted_files => 10);
CALL ducklake_rewrite_data_files('lake', 'orders', max_compacted_files => 5);
CALL ducklake_expire_snapshots('lake', older_than => now() - INTERVAL '30 days', dry_run => true);
CALL ducklake_cleanup_old_files('lake', older_than => now() - INTERVAL '7 days', dry_run => true);
```

While `ducklake_cleanup_old_files` removes only scheduled expired files, `ducklake_delete_orphaned_files` scans storage and deletes unreferenced files DuckLake never wrote. Always pass `dry_run => true` first. Never run orphan deletion on a shared directory.

## Iceberg

Direct scans via `iceberg_scan(path)` are read-only. For writes, attach an Iceberg REST catalog:

```sql
CREATE SECRET iceberg_auth (TYPE iceberg, CLIENT_ID '...', CLIENT_SECRET '...',
    OAUTH2_SERVER_URI 'https://auth.example.com/oauth/token');
ATTACH 'my_warehouse' AS ice (TYPE iceberg, SECRET iceberg_auth, URI 'https://catalog.example.com/v1');
```

Specify catalog URL with `URI`. `ENDPOINT` is deprecated; passing both fails. For AWS Glue, specify `ENDPOINT_TYPE 'glue'` and `AUTHORIZATION_TYPE 'sigv4'`; Glue requires `DEFAULT_TABLE_LOCATION_FROM_NAMESPACE true` or explicit `WITH ('location' = '...')`. For Amazon S3 Tables, specify `ENDPOINT_TYPE 's3_tables'`.

Writes require a REST catalog. `UPDATE`, `DELETE`, and `MERGE` employ merge-on-read positional deletes. Writes fail on sorted tables; copy-on-write is unsupported; table properties `write.update.mode` and `write.delete.mode` must be `merge-on-read`. Iceberg v3 adds `VARIANT`, `TIMESTAMP_NS`, and binary deletion vectors. `GEOGRAPHY` is unsupported.

Query historical state by snapshot ID or timestamp:

```sql
SELECT * FROM ice.t AT (VERSION => 7635660646343998149);
SELECT * FROM iceberg_snapshots('ice.t');
```

Before copying a version number from Delta, inspect `iceberg_snapshots`. `VERSION` expects a 64-bit snapshot ID, not a sequential table version.

## Delta

```sql
INSTALL AND LOAD delta;
ATTACH 's3://my_bucket/path' AS events (TYPE delta);
SELECT * FROM events;
CREATE TABLE events.events (id BIGINT, region VARCHAR) PARTITIONED BY (region);
INSERT INTO events VALUES (1, 'eu');
```

Before attaching, confirm `_delta_log/` exists. `ATTACH` performs no metadata validation; an invalid path mounts an empty database that fails only on first read.
When creating tables, the table name must match the attached database name exactly: `CREATE TABLE events.events (...)`. Executing `CREATE TABLE events.other` fails.

Delta writes from DuckDB are append-only. DuckDB rejects `UPDATE`, `DELETE`, `MERGE INTO`, `ALTER TABLE`, `DROP TABLE`, `CREATE TABLE AS`, `CREATE OR REPLACE TABLE`, `RETURNING`, and `ON CONFLICT`. Constraints, `DEFAULT`, generated columns, `SORTED BY`, `TIME`, and unsigned integers are unsupported.

Time travel:

```sql
SELECT * FROM events.events AT (VERSION => 5);
SELECT * FROM events.events AT (TIMESTAMP => TIMESTAMPTZ '2026-09-01 12:00:00+00');
ATTACH 's3://my_bucket/path' AS events_v5 (TYPE delta, VERSION 5);
```

Passing both `VERSION` and `TIMESTAMP` fails. Attachments pinned to a version or timestamp are strictly read-only.

`VARIANT` columns work at the top level. DuckDB shreds them only when `delta.enableVariantShredding` is true, which `CREATE TABLE` cannot set. Nested `VARIANT` columns can be created but not written. In DuckDB 2.0, `delta_column_mapping_policy` defaults to `strict`; set to `'lenient'` to restore DuckDB 1.5 reading for ID-mode files lacking field IDs.
For catalog-managed tables (such as Unity Catalog managed tables), do not read via `delta_scan` or `ATTACH ... (TYPE delta)`; attach through `unity_catalog`.

## Unity Catalog

```sql
CREATE SECRET (TYPE s3, PROVIDER config, REGION 'us-east-1');
CREATE SECRET uc (TYPE unity_catalog, TOKEN '...', ENDPOINT 'https://...', AWS_REGION 'us-east-1');
ATTACH 'my_catalog' AS uc (TYPE unity_catalog, DEFAULT_SCHEMA 'main');
```

Before calling `ATTACH`, create the storage secret (e.g. S3); the `unity_catalog` secret authenticates the REST endpoint only. When connecting to Unity Catalog OSS, `DEFAULT_SCHEMA 'main'` is required. Time travel accepts `AT (VERSION => 5)` or `AT (TIMESTAMP => TIMESTAMPTZ '...')`.

Unity Catalog supports reads, inserts, and table creations. Managed tables utilize catalog-managed commits. DuckDB rejects `UPDATE`, `DELETE`, `DROP TABLE`, `ALTER TABLE`, and schema or view DDL.
Standard `CHECKPOINT` does not apply; invoke `CALL unity_catalog_checkpoint_table('uc', 'schema', 'table')` instead.
To use Databricks server-side scan planning, pass `USE_IRC_SCAN_PLAN true`. If tables contain equality deletes, omit or disable this option, as equality deletes fail under IRC scan planning.

## Traps

| Condition | Consequence | Correct move |
| --- | --- | --- |
| Attaching DuckLake metadata file as native database | Only internal `ducklake_*` tables appear. | Prepend the `ducklake:` URI prefix. |
| Attaching native DuckDB database as DuckLake | DuckLake injects catalog schemas and hides existing tables. | Maintain a dedicated, isolated catalog file. |
| Globbing catalog data directories directly | Queries return stale, uncompacted, or deleted data files. | Query through the catalog or inspect via `ducklake_list_files`. |
| Mixing DuckDB versions on DuckDB-file catalog | Writes from newer releases render metadata unreadable to older clients. | Pin all clients to the same version, or back catalog by PostgreSQL/SQLite. |
| Using `AT (VERSION => 5)` across formats | DuckLake and Iceberg expect snapshot IDs; Delta expects sequential versions. | Inspect snapshot catalogs (`ducklake_snapshots`, `iceberg_snapshots`) first. |
| Running `cleanup_all => true` or orphan deletion blindly | Bypasses retention bounds or deletes untracked files in `DATA_PATH`. | Execute with `dry_run => true` first; never run orphan deletion on shared paths. |

## Verify

```bash
tmp=$(mktemp -d)
duckdb -agent -c "INSTALL ducklake; LOAD ducklake;
  ATTACH 'ducklake:$tmp/meta.ducklake' AS lake (DATA_PATH '$tmp/data');
  CREATE TABLE lake.t AS SELECT 42 AS a;
  SELECT * FROM lake.t;"
rm -rf "$tmp"
```

The output must return `42`. A catalog error indicates the `ducklake` extension failed to load or the path contains an incompatible non-DuckLake database.

## References

- [DuckLake extension](https://duckdb.org/docs/2.0/core_extensions/ducklake.html) covers extension loading and core capabilities.
- [DuckLake manual](https://ducklake.select/docs/stable/) details catalog attachment, migrations, maintenance procedures, and limits.
- [DuckLake 1.1](https://ducklake.select/2026/10/21/ducklake-11/) outlines the 1.1 specification and feature additions.
- [Iceberg options](https://duckdb.org/docs/2.0/core_extensions/iceberg/iceberg_options.html) documents REST catalog parameters and auth settings.
- [Iceberg writes](https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html) specifies merge-on-read semantics and write constraints.
- [Delta](https://duckdb.org/docs/2.0/core_extensions/delta.html) details Delta Lake attachment, time travel, and variant support.
- [Unity Catalog](https://duckdb.org/docs/2.0/core_extensions/unity_catalog.html) describes REST catalog attachment, storage secrets, and write limits.
- Complete option signatures, maintenance APIs, and version matrices are cataloged in [references/catalogs.md](references/catalogs.md).
- DuckLake attachment, migration, time travel, Delta table creation, and the exact-name rule verified on DuckDB 2.0.0 with DuckLake extension `417a9117f5`.
