---
name: duckdb-lakehouse
description: >
  Use DuckLake 1.1, Iceberg, Delta, and Unity Catalog from DuckDB 2.0. Covers
  catalog choice, attach options, snapshots and time travel, maintenance, and
  write limits. Use when the user mentions DuckLake, Iceberg, Delta, a
  lakehouse catalog, or asks which open table format to use.
---

# Lakehouse catalogs

Object-storage secrets and plain Parquet or CSV on S3 live in `duckdb-files`. This skill starts once a catalog or lake table is involved.

Run SQL with the `duckdb` skill. `INSTALL AND LOAD` the needed extension (`ducklake`, `iceberg`, `delta`, or `unity_catalog`). They autoload on first use when install is allowed.

## Identify the path first

Identify the path before choosing the extension. If no signal is present, list the directory and stop. Do not glob the data directory to decide; a catalog is authoritative.

| Signal | Format | First move |
| --- | --- | --- |
| `_delta_log/` | Delta | `delta_scan` or `ATTACH ... (TYPE delta)` |
| `metadata/version-hint.text` and `metadata/*.metadata.json` | Iceberg | `iceberg_scan` or a REST attach |
| `ducklake:` URI or `ducklake_*` metadata tables | DuckLake | `ATTACH 'ducklake:...'` |
| Parquet or CSV files only | Files | `duckdb-files` |

## Choose the format

| Format | Concurrent writers | Catalog | Time travel | DuckDB write support | Best fit |
| --- | --- | --- | --- | --- | --- |
| Native `.duckdb` | One writer process | None | No | Full DDL and DML | Single-process analytics, app state |
| DuckLake | Yes, through the catalog database | DuckDB file, SQLite, or PostgreSQL | Snapshot id or timestamp | DDL and DML with the limits below, `MERGE`, transactions | DuckDB-native lakehouse, multi-writer ACID |
| Iceberg | Yes, through a REST catalog | REST catalog for writes | Snapshot id or timestamp | Create, insert, update, delete, merge, alter; merge-on-read only | Cross-engine lakehouse with an existing catalog |
| Delta | Optimistic log; Unity for managed tables | None for an external table by path | Table version or timestamp | Create and append only | Reading existing Delta, append-only ingestion |

Do not pick a format by habit. The write surface and the concurrency model differ more than the file layout.

## DuckLake

DuckLake 1.1 needs DuckDB 2.0.0 or newer. The 2.0 extension reads and writes a 1.0 catalog. New catalogs default to 1.1 unless `ducklake_default_version` says otherwise.

```sql
ATTACH 'ducklake:metadata.ducklake' AS lake;
ATTACH 'ducklake:sqlite:metadata.sqlite' AS lake (DATA_PATH 'my_files/');
ATTACH 'ducklake:postgres:dbname=postgres' AS lake (DATA_PATH 's3://bucket/path/');
```

A DuckDB-file catalog defaults `DATA_PATH` to `<metadata>.files`. A new SQLite or PostgreSQL catalog needs `DATA_PATH` explicitly. The metadata file is a catalog, not a native database of user tables.

Useful options: `READ_ONLY`, `CREATE_IF_NOT_EXISTS`, `DATA_INLINING_ROW_LIMIT`, `DUCKLAKE_VERSION '1.0'`, `ENCRYPTED`, `AUTOMATIC_MIGRATION`, `OVERRIDE_DATA_PATH`, `SNAPSHOT_VERSION`, and `SNAPSHOT_TIME`. The full table is in [references/catalogs.md](references/catalogs.md).

When the user wants a 1.1 feature, migrate. Back up the catalog and the data files. Stop writes, compaction, and cleanup. Make every client 1.1-capable. Reset the default, then migrate with write access:

```sql
RESET ducklake_default_version;
ATTACH 'ducklake:metadata.ducklake' AS lake (AUTOMATIC_MIGRATION true);
SELECT value FROM lake.options() WHERE option_name = 'version';
```

Migration is irreversible. A leftover `ducklake_default_version='1.0'` makes a later plain attach fail with `Cannot downgrade a DuckLake catalog`. After the migration, omit `AUTOMATIC_MIGRATION`.

Version 1.1 is required for nested schemas, the `"NULL"` type, `epoch_month` and the other epoch transforms, `VARIANT` inlining into PostgreSQL or SQLite, multi-snapshot Puffin deletes, exact string statistics, `row_group_count`, and cross-schema compaction after `ADD COLUMN`.

Snapshots and time travel:

```sql
SELECT * FROM lake.t AT (VERSION => 3);
SELECT * FROM lake.t AT (TIMESTAMP => TIMESTAMPTZ '2026-10-20 12:00:00+00');
SELECT * FROM ducklake_snapshots('lake');
SELECT ducklake_current_snapshot('lake');
```

`VERSION` is a snapshot id. A timestamp before the first snapshot or in the future fails. The `AT` expression cannot contain a subquery.

Inside `CHECKPOINT`, maintenance runs in this order: flush inlined data, expire snapshots, merge adjacent files, rewrite data files, cleanup old files, delete orphaned files. Back up first. Set `rewrite_delete_threshold`, `expire_older_than`, and `delete_older_than` with `lake.set_option`; `auto_compact=false` skips compaction; `ducklake_target_file_size` overrides `target_file_size`. Dry-run cleanup and orphan deletion. Thresholds are in [references/catalogs.md](references/catalogs.md).

```sql
CALL ducklake_merge_adjacent_files('lake', 'orders', schema => 'sales', max_compacted_files => 10);
CALL ducklake_rewrite_data_files('lake', 'orders', max_compacted_files => 5);
CALL ducklake_expire_snapshots('lake', older_than => now() - INTERVAL '30 days', dry_run => true);
CALL ducklake_cleanup_old_files('lake', older_than => now() - INTERVAL '7 days', dry_run => true);
```

`ducklake_cleanup_old_files` removes only files DuckLake scheduled for deletion. `ducklake_delete_orphaned_files` scans the data path and can delete files DuckLake never wrote. Run both with `dry_run` first, and never point orphan cleanup at a shared directory.

Constraints are `NOT NULL` only. Use `MERGE INTO` for upserts. DuckLake has row lineage and a change feed, but no primary keys, unique keys, check constraints, or indexes.

## Iceberg

`iceberg_scan(path)` reads a table directly and is read-only. Writes go through an attached REST catalog.

```sql
CREATE SECRET iceberg_auth (
    TYPE iceberg,
    CLIENT_ID '...',
    CLIENT_SECRET '...',
    OAUTH2_SERVER_URI 'https://auth.example.com/oauth/token'
);

ATTACH 'my_warehouse' AS ice
    (TYPE iceberg, SECRET iceberg_auth, URI 'https://catalog.example.com/v1');
```

`URI` is the catalog URL. `ENDPOINT` is deprecated. Passing both fails. For AWS Glue, use `ENDPOINT_TYPE 'glue'` and `AUTHORIZATION_TYPE 'sigv4'`. Glue does not assign a table location server-side, so `CREATE TABLE` needs `DEFAULT_TABLE_LOCATION_FROM_NAMESPACE true` or an explicit `WITH ('location' = '...')`. For Amazon S3 Tables, use `ENDPOINT_TYPE 's3_tables'`.

Writes require a REST catalog. `UPDATE`, `DELETE`, and `MERGE` use merge-on-read positional deletes. They fail on sorted tables, copy-on-write is unsupported, and the table's `write.update.mode` and `write.delete.mode` must be `merge-on-read`. Iceberg v3 adds `VARIANT`, `TIMESTAMP_NS`, and binary deletion vectors. `GEOGRAPHY` is unsupported.

Time travel uses a snapshot id or a timestamp, not a table version:

```sql
SELECT * FROM ice.t AT (VERSION => 7635660646343998149);
SELECT * FROM iceberg_snapshots('ice.t');
```

Before copying a version number from Delta, read `iceberg_snapshots`. The numbers mean different things.

## Delta

```sql
INSTALL AND LOAD delta;
ATTACH 's3://my_bucket/path' AS events (TYPE delta);
SELECT * FROM events;

CREATE TABLE events.events (id BIGINT, region VARCHAR) PARTITIONED BY (region);
INSERT INTO events VALUES (1, 'eu');
```

The table name in `CREATE TABLE` must be exactly the attached name. `CREATE TABLE events.other` fails. `ATTACH` does not verify that the path is a Delta table; a typo attaches an empty database and fails on the first read. Check for `_delta_log/` first.

No `UPDATE`, `DELETE`, `MERGE INTO`, `ALTER TABLE`, `DROP TABLE`, `CREATE TABLE AS`, `CREATE OR REPLACE TABLE`, `RETURNING`, or `ON CONFLICT`. No constraints, `DEFAULT`, generated columns, `SORTED BY`, `TIME`, or unsigned integers. Delta writes from DuckDB are append-only.

Time travel:

```sql
SELECT * FROM events.events AT (VERSION => 5);
SELECT * FROM events.events AT (TIMESTAMP => TIMESTAMPTZ '2026-09-01 12:00:00+00');
ATTACH 's3://my_bucket/path' AS events_v5 (TYPE delta, VERSION 5);
```

A version and a timestamp together are rejected. A pinned attach is read-only.

`VARIANT` columns work at the top level. DuckDB shreds them only when the table property `delta.enableVariantShredding` is true, and `CREATE TABLE` cannot set it. A `VARIANT` nested inside a struct, list, or map can be created but not written. `delta_column_mapping_policy` defaults to `strict` in 2.0; `SET delta_column_mapping_policy = 'lenient'` restores the 1.5 read for id-mode files without field ids.

Catalog-managed tables, including Unity Catalog managed tables, cannot be read through `delta_scan` or `ATTACH ... (TYPE delta)`. Attach the catalog.

## Unity Catalog

```sql
CREATE SECRET (TYPE s3, PROVIDER config, REGION 'us-east-1');
CREATE SECRET uc (
    TYPE unity_catalog,
    TOKEN '...',
    ENDPOINT 'https://...',
    AWS_REGION 'us-east-1'
);

ATTACH 'my_catalog' AS uc (TYPE unity_catalog, DEFAULT_SCHEMA 'main');
```

Create the storage secret for the table path before `ATTACH`; the catalog secret only authenticates the REST endpoint. `DEFAULT_SCHEMA` is required for Unity Catalog OSS. Time travel uses `AT (VERSION => 5)` or `AT (TIMESTAMP => ...)`.

Unity Catalog reads, inserts, and creates tables. It does not support `UPDATE`, `DELETE`, `DROP TABLE`, `ALTER TABLE`, or view and schema DDL. Managed tables use catalog-managed commits. `CHECKPOINT` does not apply; use `unity_catalog_checkpoint_table`. `USE_IRC_SCAN_PLAN` uses Databricks server-side planning, but tables with equality deletes fail under it.

## Traps

| Trap | Result | Move |
| --- | --- | --- |
| Attach a DuckLake metadata file as a native file | You see only `ducklake_*` tables. | Use the `ducklake:` prefix. |
| Attach a native DuckDB file as DuckLake | DuckLake adds catalog tables and hides user tables. | Use a dedicated catalog file. |
| Glob a catalog's data directory | You read stale, merged, and deleted files. Counts differ from the catalog. | Query through the catalog, or use `ducklake_list_files`. |
| Mix DuckDB versions on a DuckDB-file catalog | A newer write can make the metadata file unreadable to older DuckDB. | One release for every client, or PostgreSQL/SQLite. |
| `AT (VERSION => 5)` across formats | DuckLake and Iceberg use snapshot ids; Delta uses table version 5. | Check the snapshot list first. |
| `cleanup_all => true` or orphan deletion | Ignores age, or deletes untracked files in the data path. | Dry-run; prefer `older_than`; never target a shared directory. |

## Verify

```bash
tmp=$(mktemp -d)
duckdb -agent -c "INSTALL ducklake; LOAD ducklake;
  ATTACH 'ducklake:$tmp/meta.ducklake' AS lake (DATA_PATH '$tmp/data');
  CREATE TABLE lake.t AS SELECT 42 AS a;
  SELECT * FROM lake.t;"
rm -rf "$tmp"
```

The result must be `42`. A catalog error means the `ducklake` extension did not load or the path already held a non-DuckLake database.

## References

- [DuckLake extension](https://duckdb.org/docs/2.0/core_extensions/ducklake.html) owns the DuckDB page.
- [DuckLake manual](https://ducklake.select/docs/stable/) owns attach, migration, maintenance, and limits.
- [DuckLake 1.1](https://ducklake.select/2026/10/21/ducklake-11/) owns the 1.1 feature list.
- [Iceberg options](https://duckdb.org/docs/2.0/core_extensions/iceberg/iceberg_options.html) owns the attach matrix.
- [Iceberg writes](https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html) owns the merge-on-read limits.
- [Delta](https://duckdb.org/docs/2.0/core_extensions/delta.html) owns create, time travel, and variant.
- [Unity Catalog](https://duckdb.org/docs/2.0/core_extensions/unity_catalog.html) owns attach and write limits.
- The full option, signature, and 1.0-vs-1.1 tables are in [references/catalogs.md](references/catalogs.md).
- DuckLake attach, migration, time travel, Delta create, and the exact-name rule were probed on DuckDB 2.0.0 with DuckLake extension `417a9117f5`.
