---
name: duckdb-lakehouse
description: >
  Use DuckLake 1.1, Iceberg, and Delta from DuckDB 2.0. Covers catalog
  migration, nested schemas, Iceberg REST ATTACH options, and Delta CREATE
  TABLE plus time travel. Use when the user mentions DuckLake, Iceberg, Delta,
  or a lakehouse catalog. Use /duckdb-lakehouse.
---

# Lakehouse catalogs

Object-storage secrets and plain Parquet or CSV on S3 live in `duckdb-files`. Load that skill for `CREATE SECRET`. This skill starts once a catalog is attached.

Run SQL with the `duckdb` skill. `INSTALL AND LOAD` the extension you need: `ducklake`, `iceberg`, or `delta`. They autoload on first use when install is allowed.

## DuckLake 1.1

DuckLake 1.1 needs DuckDB 2.0.0 or newer. The new extension reads and writes a 1.0 catalog. New catalogs are format 1.1 unless you ask for 1.0.

```sql
ATTACH 'ducklake:metadata.ducklake' AS lake;
SELECT value FROM lake.options() WHERE option_name = 'version';
```

Migrate only when the user wants a 1.1 feature. Back up the catalog and the data files first. Migration needs write access.

```sql
RESET ducklake_default_version;
ATTACH 'ducklake:metadata.ducklake' AS lake (AUTOMATIC_MIGRATION true);
```

If `ducklake_default_version` is `1.0`, migration leaves the catalog at 1.0 until you reset it. A migrated catalog cannot be downgraded. Later attaches can omit `AUTOMATIC_MIGRATION`. Keep an old catalog on 1.0 by attaching it with no migration flag. Create a new 1.0 catalog with `DUCKLAKE_VERSION '1.0'`. `DUCKLAKE_VERSION '1.1-dev1'` is rejected.

A DuckDB-file catalog written by DuckDB 2.0 can become unreadable to older DuckDB even when the DuckLake format stays 1.0. Use one DuckDB version for every client of that file, or put the catalog in PostgreSQL or SQLite.

These need format 1.1:

- Nested schemas. Same path rules as core DuckDB. `lake.sales.europe` is nested. `lake."sales.europe"` is one name with a dot. Do not `USE` a multi-part schema. `DROP SCHEMA lake.sales CASCADE` when it is not empty.
- The `"NULL"` type, so an untyped null column can later become `VARCHAR`.
- Epoch partition transforms such as `epoch_month(ts)`.
- `VARIANT` inlining into PostgreSQL `BYTEA` or SQLite `BLOB`.
- Multi-snapshot Puffin delete files. Puffin is experimental in the spec.
- Exact string statistics and `row_group_count`.

These work on a 1.0 catalog with the new extension: `PARTITIONED BY` and `SORTED BY` on `CREATE TABLE`, per-table `WITH (...)` options, and the wider file-pruning rules.

```sql
CREATE SCHEMA lake.sales;
CREATE SCHEMA lake.sales.europe;
CREATE TABLE lake.sales.europe.orders (id INTEGER, region VARCHAR, ordered_at TIMESTAMP)
    PARTITIONED BY (region)
    SORTED BY (ordered_at);
```

Top-level column names starting with `_ducklake_` are reserved on 1.1, case-insensitive.

The 1.1 blog shows extra arguments on `ducklake_merge_adjacent_files`. The DuckDB core page lists only the catalog. Read https://ducklake.select/docs/stable/duckdb/maintenance/merge_adjacent_files.html before calling it.

## Iceberg

Writes go through `ATTACH ... (TYPE iceberg)`. `iceberg_scan` is read-only and has no catalog.

REST options that matter on 2.0:

| Option | Role |
| --- | --- |
| `DEFAULT_TABLE_LOCATION_FROM_NAMESPACE` | `CREATE TABLE` without a location uses the namespace location. Default false. Glue needs this, or an explicit location. Introduced in 2.0. |
| `USE_METADATA_LOCATION` | Read metadata from the catalog's metadata-location file. Default false. |
| `PREFIX` | Path prefix after `/v1/`. |
| `NAMESPACE_SEPARATOR` | Joins nested namespace levels. Default is the ASCII unit separator. Must not be empty. |

`URI` is the catalog URL. `ENDPOINT` is a deprecated alias. Do not pass both.

## Delta

```sql
INSTALL AND LOAD delta;
ATTACH 's3://my_bucket/path' AS events (TYPE delta);
CREATE TABLE events.events (id BIGINT, region VARCHAR)
    PARTITIONED BY (region);
INSERT INTO events VALUES (1, 'eu');
```

`ATTACH` does not check that the path is a Delta table. A typo attaches an empty database and fails on the first read. The table name in `CREATE TABLE` is qualified with the attached database name. `CREATE TABLE ... AS` and `CREATE OR REPLACE TABLE` are not supported. Create, then `INSERT`. No `UPDATE`, `DELETE`, `MERGE INTO`, `ALTER TABLE`, or `DROP TABLE` through this extension. No constraints, no `DEFAULT`, no `SORTED BY`, no `TIME`, no unsigned integers.

Time travel, new for timestamps in 2.0:

```sql
SELECT * FROM events.events AT (VERSION => 5);
SELECT * FROM events.events AT (TIMESTAMP => TIMESTAMPTZ '2026-09-01 12:00:00+00');
ATTACH 's3://my_bucket/path' AS events_v5 (TYPE delta, VERSION 5);
```

A version and a timestamp together are rejected. An attach pinned to a version or timestamp is read-only.

`VARIANT` columns can be created and appended at the top level. DuckDB shreds them on write only when the table property `delta.enableVariantShredding` is `true`. `CREATE TABLE` cannot set that property, so a table DuckDB creates stores unshredded variant files. `SELECT v.a` can skip other shredded fields. It reads the whole value if any nested field is `TIMESTAMP WITH TIME ZONE`. `VARIANT` inside a struct, list, or map cannot be written.

`delta_column_mapping_policy` defaults to `strict` in 2.0. It was `lenient` in 1.5. `SET delta_column_mapping_policy = 'lenient'` restores the old read of id-mode files that lack Parquet field ids.

Catalog-managed tables, including Unity Catalog managed tables, are not readable with `delta_scan` or `ATTACH ... (TYPE delta)`. Attach the catalog.

## References

- https://ducklake.select/2026/10/21/ducklake-11/
- https://ducklake.select/docs/stable/duckdb/migrations/upgrading_to_ducklake_1_1.html
- https://duckdb.org/docs/2.0/core_extensions/ducklake.html
- https://duckdb.org/docs/2.0/core_extensions/iceberg/iceberg_options.html
- https://duckdb.org/docs/2.0/core_extensions/delta.html
- https://duckdb.org/2026/10/21/announcing-duckdb-200.html
