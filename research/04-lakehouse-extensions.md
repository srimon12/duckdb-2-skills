# DuckDB 2.0.0 lakehouse and extension changes

Factual briefing from official DuckDB and DuckLake pages, dated with the 2026-10-21 releases. DuckDB 2.0.0 LTS (“Cinnamon Teal”) and DuckLake specification 1.1 shipped together. Core-extension highlights in the release post: DuckLake 1.1, Iceberg REST `ATTACH` options, and Delta `CREATE TABLE`, partitioning, time travel, and `VARIANT`.

Sources:

- https://duckdb.org/2026/10/21/announcing-duckdb-200.html
- https://ducklake.select/2026/10/21/ducklake-11/
- https://ducklake.select/docs/stable/specification/introduction.html
- https://ducklake.select/docs/stable/duckdb/migrations/upgrading_to_ducklake_1_1.html
- https://ducklake.select/docs/stable/duckdb/advanced_features/nested_schemas.html
- https://ducklake.select/docs/stable/duckdb/advanced_features/partitioning.html
- https://ducklake.select/docs/stable/specification/data_types.html
- https://ducklake.select/docs/stable/specification/tables/ducklake_schema.html
- https://ducklake.select/docs/stable/specification/tables/ducklake_data_file.html
- https://ducklake.select/docs/stable/specification/tables/ducklake_delete_file.html
- https://ducklake.select/docs/stable/specification/tables/ducklake_file_column_stats.html
- https://ducklake.select/docs/stable/specification/tables/ducklake_inlined_data_tables.html
- https://duckdb.org/docs/2.0/core_extensions/ducklake.html
- https://duckdb.org/docs/2.0/core_extensions/iceberg/overview.html
- https://duckdb.org/docs/2.0/core_extensions/iceberg/iceberg_options.html
- https://duckdb.org/docs/2.0/core_extensions/delta.html
- https://duckdb.org/docs/2.0/extensions/extension_repositories.html
- https://duckdb.org/docs/2.0/sql/statements/load_and_install.html
- https://duckdb.org/docs/2.0/sql/statements/update_extensions.html
- https://duckdb.org/docs/2.0/extensions/community_extensions.html
- https://duckdb.org/docs/2.0/configuration/secrets_manager.html
- https://duckdb.org/docs/2.0/core_extensions/httpfs/authentication.html
- https://duckdb.org/docs/2.0/core_extensions/azure.html
- https://duckdb.org/docs/2.0/data/io.html

DuckLake 1.1 requires DuckDB v2.0.0 or later (https://ducklake.select/docs/stable/). The DuckDB `ducklake` page points at https://ducklake.select/docs/stable/duckdb/introduction for the full extension guide. Compatibility matrix: https://ducklake.select/release_calendar#compatibility-matrix.

## 1. DuckLake 1.1

The new `ducklake` extension reads and writes DuckLake 1.0 catalogs. Migration is opt-in. New catalogs use format 1.1 unless you request 1.0.

### Migration (spec 1.1)

```sql
ATTACH 'ducklake:metadata.ducklake' AS lake
    (AUTOMATIC_MIGRATION true);
```

Check:

```sql
SELECT value FROM my_ducklake.options() WHERE option_name = 'version';
```

Expected value: `1.1`.

Rules from the upgrade page and the spec introduction:

- Back up the catalog and data files first. Migration needs write access, including `ALTER` on the metadata tables. On PostgreSQL, use the owner of those tables.
- If `ducklake_default_version` is `1.0`, `AUTOMATIC_MIGRATION` leaves the catalog at 1.0. Run `RESET ducklake_default_version;` first.
- After a successful migration, later `ATTACH` statements can omit `AUTOMATIC_MIGRATION`. A migrated catalog cannot be downgraded.
- Keep an existing catalog on 1.0 by attaching it without migration. Create a new 1.0 catalog with `DUCKLAKE_VERSION '1.0'`:

```sql
ATTACH 'ducklake:compatible.ducklake' AS my_ducklake (DUCKLAKE_VERSION '1.0');
```

- Requesting 1.1 for an existing 1.0 catalog also requires `AUTOMATIC_MIGRATION true`.
- `DUCKLAKE_VERSION '1.1-dev1'` is not accepted. Catalogs from before 1.0 and catalogs labeled `1.1-dev1` require a writable migration even for read-only use.
- Pinning the DuckLake format does not pin the DuckDB metadata file’s storage version. A newer DuckDB can write that file so older DuckDB clients cannot read it. Use the same DuckDB release for every client of a DuckDB catalog, or use PostgreSQL or SQLite.

What the migration changes (spec introduction):

- Adds the 1.1 catalog columns and the `ducklake_view_column_tag` table.
- Renames system columns of registered inlined data tables.
- Adds missing `ducklake_schema_versions` rows for inlined data tables.
- Restores defaults of renamed struct fields.
- Clears column bounds that older versions may have stored with the wrong type.
- Added columns are `NULL` on existing rows.

If migration reports a collision with an inlined table’s system columns: attach the 1.0 catalog without migration, rename the user column, run `CALL ducklake_flush_inlined_data('my_ducklake');`, detach, then migrate again.

### Needs format 1.1

These do not work on a 1.0 catalog.

**Nested schemas.** Parent first, then child. Path syntax is dotted identifiers, not one quoted name:

```sql
CREATE SCHEMA lake.sales;
CREATE SCHEMA lake.sales.europe;
CREATE TABLE lake.sales.europe.orders (id INTEGER);
```

- `lake.sales.europe` is a nested schema. `lake."sales.europe"` is one top-level schema whose name contains a dot.
- `ducklake_schema.parent_schema_id` is `NULL` for a top-level schema. `schema_name` stores only the last component. A nested schema’s relative `path` is relative to the catalog `data_path`, not the parent’s path. The data directory uses the schema UUID under the data path; it does not mirror the name hierarchy.
- Schema options apply only to tables directly in that schema. They are not inherited by child schemas.
- `SHOW ALL TABLES` lists nested tables, but its `schema` column is only the final component.
- `USE` and `SHOW TABLES FROM` do not accept a path with more than one schema component. Use fully qualified names.
- Functions that take a schema accept a dotted path, for example `schema_name => 'sales.europe'` and `schema => 'sales.europe'`.
- `DROP SCHEMA lake.sales CASCADE` is required if the schema contains tables, views, macros, or child schemas. Dropped schemas stay visible through time travel while the snapshots and data are kept.
- Views and macros can live in nested schemas.

**`"NULL"` type.** Catalog type name is `null`. In DuckDB SQL it is spelled `"NULL"`. It can appear inside a list, struct, or map. On 1.0, `CREATE TABLE ... AS` with an untyped `NULL` column stored it as `INTEGER`, and a later change to `VARCHAR` failed because only widening promotions are allowed. On 1.1:

```sql
CREATE TABLE lake.signups AS SELECT 1 AS id, NULL AS referrer;
ALTER TABLE lake.signups ALTER referrer TYPE VARCHAR;
```

**Epoch partition transforms** (require 1.1). They count whole units since 1970-01-01, rounding down, so pre-1970 values are negative. They use the UTC instant for `TIMESTAMPTZ`, independent of the session time zone. Calendar `month(ts)` is 1–12; `epoch_month` of January 2020 is 600.

| Transform | Expression |
| --- | --- |
| identity | `col_name` |
| bucket | `bucket(N, col_name)` |
| year, month, day, hour | `year(ts)` and the same for month, day, hour |
| epoch_year, epoch_month, epoch_day, epoch_hour | `epoch_month(ts)` and the same pattern |

```sql
CREATE TABLE lake.clicks (user_id INTEGER, ts TIMESTAMP)
PARTITIONED BY (epoch_month(ts));
```

**VARIANT inlining on PostgreSQL and SQLite catalogs.** Unshredded Parquet Variant encoding (metadata plus value). PostgreSQL stores it as `BYTEA`, SQLite as `BLOB`. DuckDB catalogs already inlined `VARIANT` before 1.1.

```sql
ATTACH 'ducklake:sqlite:metadata.sqlite' AS lake;
CREATE TABLE lake.events (id INTEGER, payload VARIANT);
INSERT INTO lake.events VALUES
    (1, 42::VARIANT),
    (2, {'user': 'alice', 'clicks': 3}::VARIANT);
```

**Multi-snapshot Puffin delete files.** Format 1.1 allows one Puffin file to hold cumulative deletion vectors for several snapshots of the same data file. Each vector’s `ducklake-snapshot-id` property names its snapshot. A reader uses the vector with the greatest snapshot id that does not exceed the requested snapshot. A single-snapshot file may be a bare `deletion-vector-v1` blob, whose snapshot is `begin_snapshot`. `format` is `parquet` or `puffin` (Puffin is described as experimental). Puffin files are written without encryption. `delete_count` for a cumulative Puffin vector is the latest vector’s count, not the sum. `row_group_count` is `NULL` for Puffin files.

```sql
CALL lake.set_option('write_deletion_vectors', true);
```

**Exact string statistics.** `ducklake_file_column_stats` adds `min_is_exact` and `max_is_exact` (`BOOLEAN`). `NULL` means exactness is unknown. `min_value` / `max_value` remain bounds and need not be exact. 1.1 records whether a string bound is exact so `min` / `max` on a string can be answered from the catalog when the bound is exact. Parquet writers, including DuckDB, may keep only the first 256 bytes of a string statistic.

**Row group counts.** `ducklake_data_file.row_group_count` and `ducklake_delete_file.row_group_count` are `BIGINT`, or `NULL` if unknown. Files written before migration keep `NULL`; filling them in would require reading every footer.

```sql
SELECT path, record_count, row_group_count
FROM __ducklake_metadata_lake.ducklake_data_file;
```

**Renamed inlined-table system columns.** In 1.1, inlined data tables (`ducklake_inlined_data_table_id_schema_version`) start with `_ducklake_row_id`, `_ducklake_begin_snapshot`, and `_ducklake_end_snapshot`. Top-level user column names that start with `_ducklake_` are reserved, case-insensitive. User columns named `row_id`, `begin_snapshot`, and `end_snapshot` are allowed and can be inlined. Migration renames the three system columns. Inlined deletion tables (`ducklake_inlined_delete_table_id`) keep `file_id`, `row_id`, and `begin_snapshot`.

### Available on a 1.0 catalog with the new extension

The 1.1 post says these do not need a catalog migration:

- `PARTITIONED BY` and `SORTED BY` on `CREATE TABLE` and `CREATE TABLE ... AS`, not only a later `ALTER`.

```sql
CREATE TABLE lake.orders (
    id INTEGER,
    region VARCHAR,
    ordered_at TIMESTAMP
)
PARTITIONED BY (region)
SORTED BY (ordered_at);
```

- Per-table options in DDL: `WITH (...)` on create, `ALTER TABLE ... SET`, `ALTER TABLE ... RESET`.

```sql
CREATE TABLE lake.events (id INTEGER, payload VARCHAR)
WITH (parquet_compression = 'zstd');
ALTER TABLE lake.events
    SET (skip_stats_columns = ['payload']);
ALTER TABLE lake.events RESET (parquet_compression);
```

- File pruning for more filters: `OR` across columns, `IS NULL`, fields inside `STRUCT`, and filters from the build side of a hash join.
- Compaction windows. The 1.1 post shows:

```sql
CALL ducklake_merge_adjacent_files('lake', 'orders',
    newer_than => now()::TIMESTAMP - INTERVAL 7 DAYS,
    older_than => now()::TIMESTAMP - INTERVAL 1 DAY);
```

  `ducklake_rewrite_data_files` accepts `max_compacted_files` in that post. The DuckDB 2.0 `ducklake` page lists `ducklake_merge_adjacent_files` with only `catalog`. Treat the extra arguments as documented by the DuckLake 1.1 post, not by that core parameter table.

- Broader `ducklake_add_data_files` imports: `VARIANT`, `TIME WITH TIME ZONE`, `TIME_NS`, `TIMESTAMPTZ_NS`, and Parquet `FLOAT16` into `FLOAT`.

```sql
CREATE TABLE lake.readings (temperature FLOAT);
CALL ducklake_add_data_files('lake', 'readings', 'readings.parquet');
```

Catalog operations are also faster (attach plus `SHOW ALL TABLES`, wide `STRUCT` schemas, inlined commits, bulk `CREATE TABLE`). Those are performance changes, not SQL changes.

### Breaking or easy-to-misread DuckLake SQL

- Names starting with `_ducklake_` are reserved on 1.1 (top-level user columns, case-insensitive).
- `USE` / `SHOW TABLES FROM` reject multi-component schema paths.
- A quoted dotted identifier is not a nested path.
- `DROP SCHEMA` of a non-empty nested schema needs `CASCADE`.
- `DUCKLAKE_VERSION '1.1-dev1'` is rejected.
- A migrated catalog cannot be read as 1.0.
- Unqualified `NULL` in `CREATE TABLE ... AS` is `"NULL"` on 1.1, not `INTEGER`.
- A DuckDB-file catalog written by a newer DuckDB can become unreadable by older DuckDB even if the DuckLake format stays 1.0.

DuckLake SQL in this section is not labeled work-in-progress by the spec. The merge-function argument list disagrees between the blog and the core docs page; do not treat either signature as the only one.

## 2. Iceberg `ATTACH` options called out as new

The 2.0 announcement says the Iceberg extension adds REST catalog `ATTACH` options that derive a table location from its namespace, load metadata from the catalog’s `metadata-location` file, and control the URL prefix and the namespace separator. Names on https://duckdb.org/docs/2.0/core_extensions/iceberg/iceberg_options.html:

| Option | Type | Default | Role |
| --- | --- | --- | --- |
| `DEFAULT_TABLE_LOCATION_FROM_NAMESPACE` | `BOOLEAN` | `false` | `CREATE TABLE` without `WITH ('location' = …)` uses `namespace location/table name` from the namespace `location` property. An explicit location still wins. If the namespace has no `location`, behavior is unchanged. The options page says this was introduced in DuckDB 2.0. Needed for catalogs such as AWS Glue that do not assign a table location. |
| `USE_METADATA_LOCATION` | `BOOLEAN` | `false` | Load table metadata from the file at the catalog’s `metadata-location` and treat that file as authoritative, instead of metadata embedded in the catalog response. Useful when embedded metadata omits properties such as `schema.name-mapping.default`. |
| `PREFIX` | `VARCHAR` | empty | Path prefix after `/v1/`, for example `/v1/prefix/namespaces/…`. Normally discovered from the catalog configuration; set it to override. A prefix containing `/` is split unless `ENCODE_ENTIRE_PREFIX` is set. |
| `NAMESPACE_SEPARATOR` | `VARCHAR` | `0x1F` | Joins nested-namespace levels into one REST path component. URL-decoded before use. Must not be empty. Default is the ASCII unit separator. |

Related 2.0 naming change on the same page, not one of those four features: `URI` is the canonical REST catalog URL. `ENDPOINT` is a deprecated alias. Do not supply both. `ENDPOINT_TYPE` cannot be combined with `URI`, `ENDPOINT`, or `AUTHORIZATION_TYPE`.

`ENDPOINT_TYPE 'GLUE'` still does not assign a table location. Either pass `WITH ('location' = …)` or set `DEFAULT_TABLE_LOCATION_FROM_NAMESPACE` to `true`.

Direct `iceberg_scan` remains read-only and catalog-free. Writes go through `ATTACH ... (TYPE iceberg, ...)`.

## 3. Delta

Page: https://duckdb.org/docs/2.0/core_extensions/delta.html. Install: `INSTALL AND LOAD delta;` (also autoloaded).

### `CREATE TABLE` (introduced in DuckDB 2.0)

Attach the location, then create a table with the same name as the attached database:

```sql
ATTACH 's3://my_bucket/path' AS events (TYPE delta);
CREATE TABLE events.events (id BIGINT, region VARCHAR)
PARTITIONED BY (region);
INSERT INTO events VALUES (1, 'eu');
```

Only `CREATE TABLE` needs `events.events`. Without the database name, the table is created in the default database. The table can later be read and written without attaching again.

`ATTACH` does not check that the path is a Delta table. A mistyped path attaches as an empty database and fails on the first read.

`WITH` options are stored as Delta table properties, except `location`, which must match the attached path:

```sql
ATTACH 's3://my_bucket/other_path' AS audit (TYPE delta);
CREATE TABLE audit.audit (id BIGINT, name VARCHAR)
WITH ('delta.enableDeletionVectors' = 'true', 'delta.appendOnly' = 'true');
```

Properties that enable a Delta feature also upgrade the protocol. Values may be any constant expression except `NULL`. Some properties cannot be set at creation, including `'delta.enableVariantShredding'`. Column mapping: set `'delta.columnMapping.mode'` to `'name'` or `'id'`.

`CREATE TABLE` does not support constraints (including `NOT NULL`), `DEFAULT` or generated columns, `SORTED BY`, types with no Delta equivalent (`TIME`, unsigned integers), or a table whose columns are all partition columns. A column-mapping table created this way cannot have nested or partition columns. `CREATE OR REPLACE TABLE` and `CREATE TABLE ... AS SELECT` are not supported. Create, then `INSERT`.

### Partitioning

`PARTITIONED BY (region)` in the `CREATE TABLE` above is the documented syntax. There is no separate Delta `ALTER TABLE` partition statement on this page. `UPDATE`, `DELETE`, `MERGE INTO`, `ALTER TABLE`, and `DROP TABLE` are not supported, nor are `RETURNING` and `ON CONFLICT` on `INSERT`.

### Time travel

Timestamp time travel was introduced in DuckDB 2.0. Version time travel on `delta_scan` is older (since v1.5.4).

```sql
-- Query an attached table
SELECT * FROM my_table AT (VERSION => 5);
SELECT * FROM my_table AT (TIMESTAMP => TIMESTAMPTZ '2026-09-01 12:00:00+00');

-- Attach the table at a version or point in time
ATTACH 's3://my_bucket/path' AS my_table_v5 (TYPE delta, VERSION 5);
ATTACH 's3://my_bucket/path' AS my_table_then (TYPE delta, TIMESTAMP TIMESTAMPTZ '2026-09-01 12:00:00+00');

-- Scan without attaching
SELECT * FROM delta_scan('s3://my_bucket/path', version => 5); -- since v1.5.4
SELECT * FROM delta_scan('s3://my_bucket/path', timestamp => TIMESTAMPTZ '2026-09-01 12:00:00+00');
```

- A table attached at a version or timestamp is read-only.
- An `ATTACH` version or timestamp is the default; an `AT` clause overrides it.
- A version and a timestamp cannot be given together.
- A timestamp reads the latest version committed at or before it. One later than `now()` or earlier than the first commit fails.
- A timestamp without a time zone uses the session `TimeZone`.
- Inside a transaction, a timestamp always reads the same version.

`ATTACH` options: `VERSION` (`UBIGINT`, default latest), `TIMESTAMP` (`TIMESTAMP WITH TIME ZONE`, default latest), `PIN_SNAPSHOT` (`BOOLEAN`, default `false`), `PUSHDOWN_PARTITION_INFO` (`BOOLEAN`, default `true`), `PUSHDOWN_FILTERS` (`VARCHAR`, default `all`; one of `none`, `all`, `constant_only`, `dynamic_only`).

### `VARIANT`

Delta `variant` columns are read as DuckDB `VARIANT`, shredded or not. Top-level `VARIANT` columns can be appended to.

Introduced in DuckDB 2.0:

- `SELECT v.a` reads only that field from Parquet. On a shredded table it skips other fields’ columns. This does not apply if any field at any depth is `TIMESTAMP WITH TIME ZONE`: DuckDB reads the whole value.
- `CREATE TABLE` accepts `VARIANT` columns.
- On write, DuckDB shreds `VARIANT` only if the table property `'delta.enableVariantShredding'` is `'true'`. `CREATE TABLE` cannot set that property, so a table created by DuckDB holds unshredded files.

Writing a `VARIANT` inside a struct, list, or map is not supported.

### Other Delta notes that affect SQL

- `delta_column_mapping_policy` default changed from `lenient` in 1.5 to `strict` in 2.0. `SET delta_column_mapping_policy = 'lenient';` restores the old read of `id`-mode files that lack Parquet field IDs.
- Catalog-managed tables (`catalogManaged`, including Unity Catalog managed tables) cannot be read or written with `delta_scan` or `ATTACH ... (TYPE delta)`. Attach the catalog (for example `unity_catalog`) instead.
- Credential chains inside `delta-kernel-rs` / `object_store` can differ from DuckDB’s chain. Configure exactly one credential type. Since v1.5.6, Azure workload identity is `workload_identity` in the `CHAIN` of an Azure `credential_chain` secret, with `AZURE_FEDERATED_TOKEN_FILE`, `AZURE_CLIENT_ID`, and `AZURE_TENANT_ID`.

Object-storage secrets used by the Delta page (still valid):

```sql
CREATE SECRET (
    TYPE s3,
    PROVIDER credential_chain
);

CREATE SECRET (
    TYPE azure,
    PROVIDER credential_chain,
    ACCOUNT_NAME 'storage_account_name'
);

CREATE SECRET (
    TYPE gcs,
    KEY_ID 'hmac_key_id',
    SECRET 'hmac_secret'
);
```

## 4. Extension repositories

https://duckdb.org/docs/2.0/extensions/extension_repositories.html and the 2.0 announcement.

**Syntax may change.** The docs say: “Support for custom extension repositories was introduced in DuckDB 2.0. This feature is currently work-in-progress and the syntax may still change.” The announcement repeats that.

Built-in repository names include `core`, `core_nightly`, and `community`.

`allow_extension_repositories` has three values:

- `undecided` (default): cannot add repositories; existing ones stay trusted.
- `allowed`: custom repositories can be added.
- `forbidden`: cannot add repositories, and existing custom repositories are distrusted.

While the database is running, the setting can move only from `undecided` to `allowed` or `forbidden`, or from `allowed` to `forbidden`.

```sql
SET allow_extension_repositories = 'allowed';

CREATE EXTENSION REPOSITORY my_repo
    WITH PREFIX 'https://extensions.example.org';
```

At `CREATE`, DuckDB fetches the repository’s public keys, pins them, and prints each key’s SHA-256 fingerprint.

Optional key, instead of trusting the network:

```sql
CREATE EXTENSION REPOSITORY my_repo
    WITH PREFIX 'https://extensions.example.org'
    USING PUBLIC KEY '-----BEGIN PUBLIC KEY----- ...';
```

Keys are 2048-bit RSA, PEM or the base64 body of the PEM. The prefix can be a local path, `https`, `s3`, or anything else DuckDB can read.

```sql
INSTALL AND LOAD my_ext FROM my_repo;
```

Inspect and drop:

```sql
SELECT repository_name, prefix, key_fingerprints
FROM duckdb_extension_repositories();

DROP EXTENSION REPOSITORY my_repo;
```

Pinned repositories survive restarts and can trust more than one key (rotation).

## 5. `INSTALL ... FROM community` and `UPDATE EXTENSIONS`

Both still match the 2.0 docs.

https://duckdb.org/docs/2.0/sql/statements/load_and_install.html:

```sql
INSTALL h3 FROM community;
INSTALL AND LOAD h3 FROM community;
```

`INSTALL AND LOAD` was introduced in DuckDB 2.0. It is `INSTALL` then `LOAD`. It accepts `FORCE`, `FROM`, and `VERSION`. Example from the versioning page: `FORCE INSTALL spatial FROM core VERSION 'v1.1.8';` and `INSTALL AND LOAD aws FROM core_nightly;`.

https://duckdb.org/community_extensions/ still documents `INSTALL waddle FROM community;` and says community binaries are fetched from `http(s)://community-extensions.duckdb.org` on `INSTALL` or `UPDATE EXTENSIONS`.

https://duckdb.org/docs/2.0/sql/statements/update_extensions.html:

```sql
UPDATE EXTENSIONS;
UPDATE EXTENSIONS (name_a, name_b, name_c);
```

It does not reload extensions. Restart the process to use the new binaries. Statically linked extensions (`json`, `parquet`, `icu` in official builds) are not updated. A change becomes `FORCE INSTALL` of that extension. The statement returns `extension_name`, `repository`, `update_result`, `previous_version`, `current_version`. The sample result includes `UPDATED` and `NO_UPDATE_AVAILABLE`.

https://duckdb.org/docs/2.0/extensions/community_extensions.html does not repeat the `FROM community` statement. It warns that community extensions are third-party and, starting with DuckDB 2.0, are no longer built for `osx_amd64`. Core extensions are still built for that platform in 2.0. DuckDB 2.1 will drop `osx_amd64`.

## 6. Object storage secrets

https://duckdb.org/docs/2.0/configuration/secrets_manager.html lists these secret types:

| Type | Service | Extension |
| --- | --- | --- |
| `azure` | Azure Blob Storage | `azure` |
| `ducklake` | DuckLake | `ducklake` |
| `gcs` | Google Cloud Storage | `httpfs` |
| `http` | HTTP and HTTPS | `httpfs` |
| `huggingface` | Hugging Face | `httpfs` |
| `iceberg` | Iceberg REST catalog | `httpfs`, `iceberg` |
| `mysql` | MySQL | `mysql` |
| `postgres` | PostgreSQL | `postgres` |
| `quack` | Quack | `quack` |
| `r2` | Cloudflare R2 | `httpfs` |
| `s3` | AWS S3 | `httpfs` |
| `aws` | AWS | `aws` |

For `s3`, `gcs`, `r2`, and `azure`, the documented providers are `CONFIG` (default if `PROVIDER` is omitted) and `credential_chain`.

**`CREATE SECRET (TYPE S3, PROVIDER credential_chain)` is still valid in the 2.0 docs.** https://duckdb.org/docs/2.0/core_extensions/httpfs/authentication.html:

```sql
CREATE OR REPLACE SECRET secret (
    TYPE s3,
    PROVIDER credential_chain
);
```

`config` is the static-key provider and is part of `httpfs`. `credential_chain` is AWS-specific and comes from the `aws` extension, which autoloads. `CHAIN` selects providers (`config`, `sts`, `sso`, `env`, `instance`, `process`, `web_identity` on the AWS extension page linked from that section). `load_aws_credentials` is deprecated.

Static `config` example from the same page:

```sql
CREATE OR REPLACE SECRET secret (
    TYPE s3,
    PROVIDER config,
    KEY_ID 'AKIAIOSFODNN7EXAMPLE',
    SECRET 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
    REGION 'us-east-1'
);
```

GCS on the Delta page uses HMAC keys (`TYPE gcs`, `KEY_ID`, `SECRET`) and `gs://`. The secrets page says `gcs` also has `credential_chain`. The S3-compatible path is what the Delta page documents.

Azure providers (https://duckdb.org/docs/2.0/core_extensions/azure.html): `config` (connection string, or anonymous with `ACCOUNT_NAME`), `credential_chain` (default Azure chain, or `CHAIN` of `cli`, `managed_identity`, `workload_identity`, `env`, `default`), `managed_identity`, `service_principal`, `access_token`. Schemes: `az` / `azure` for Blob, `abfss` / `abfs` for ADLS Gen2. `SET azure_*` variables still work and are deprecated.

```sql
CREATE SECRET secret3 (
    TYPE azure,
    PROVIDER credential_chain,
    ACCOUNT_NAME 'storage_account_name'
);
```

### Async I/O and object storage

https://duckdb.org/docs/2.0/data/io.html. Asynchronous I/O was introduced in DuckDB 2.0. It applies automatically to Parquet and to uncompressed, seekable, UTF-8 CSV, including when those files are read through a lake format such as DuckLake. JSON and DuckDB’s own database files stay synchronous. The release post names `s3://` as the object-storage case. The I/O page does not say that secret type or provider changes async behavior.

Settings: `async_threads` (default four times the system thread count, capped at 256), `read_ahead_depth` (`-1` unlimited but memory-bounded, `N > 0` at most N jobs, `0` off), `http_client_pool_capacity` (new in 2.0; automatic by default, capped at 256; resizing `async_threads` resizes the automatic pool). The documented high-bandwidth example also sets `http_retries`, `http_retry_wait_ms`, and `http_retry_backoff`. Parquet async I/O works best when there are at least as many row groups as threads. Azure has its own read concurrency settings (`azure_read_transfer_concurrency` and related); the I/O page does not say those replace `async_threads`.

## 7. Docs search index

`https://duckdb.org/data/docs-search.duckdb` still exists. A `HEAD` request on 2026-10-21 returned HTTP 200, `content-type: application/octet-stream`, `etag: "76d076a89f55fdcb1d6a1bb326d98163"`. The body was not downloaded.

`duckdb` is not installed on this machine (`which duckdb` found nothing), so `INSTALL httpfs`, `DESCRIBE`, and `SELECT DISTINCT version` were not run. Version labels inside the file were not verified.

No page fetched from duckdb.org describes that file’s schema or its `version` values. Do not assume the labels are `lts`, `stable`, `current`, and `2.0` until the file is queried. The documentation site itself uses path prefixes `/docs/2.0/`, `/docs/lts/`, `/docs/stable/`, and `/docs/current/`, which is a separate fact from the index’s `version` column.

## Uncertainties

- The docs-search DuckDB file’s table name, columns, and distinct `version` values were not queried. Whether it contains `lts`, `stable`, `current`, `2.0`, `blog`, or something else is unverified.
- `ducklake_merge_adjacent_files` in the 1.1 blog takes a table name plus `newer_than` and `older_than`. The DuckDB 2.0 core page lists only `catalog`. The DuckLake maintenance page was not opened. An agent should confirm the signature against https://ducklake.select/docs/stable/duckdb/maintenance/merge_adjacent_files.html before calling it.
- `ducklake_rewrite_data_files(..., max_compacted_files => ...)` is in the 1.1 blog only, among the pages read here. It is not in the core `ducklake` function list.
- Iceberg `USE_METADATA_LOCATION`, `PREFIX`, and `NAMESPACE_SEPARATOR` are the options that match the 2.0 announcement. Only `DEFAULT_TABLE_LOCATION_FROM_NAMESPACE` is explicitly labeled “introduced in DuckDB 2.0” on the options page. Other `ATTACH` options on that page were not diffed against 1.5, so they are not claimed as new.
- `TABLE_RESOLUTION` (`lazy` / `eager`) is documented for 2.0 and is required when a Quack client attaches a server whose catalog still has unresolved tables. It is not in the announcement’s “new options” sentence.
- Custom extension-repository SQL is explicitly work-in-progress. **Syntax may change.**
- The `aws` row in the secrets-manager table links to a broken docs path (`configuration/%%20link docs/...`). The working page is https://duckdb.org/docs/2.0/core_extensions/aws.html. That page was not re-read in full; `CHAIN` member names are taken from the authentication page’s links and from the 2.0-linked AWS credential-chain description cited in search snippets of the current AWS page (`config`, `sts`, `sso`, `env`, `instance`, `process`, `web_identity`).
- GCS `credential_chain` is named by the secrets manager. The only GCS SQL copied here from a 2.0 page is the HMAC `TYPE gcs` secret on the Delta page. Whether `credential_chain` for `TYPE gcs` looks up AWS credentials was not re-checked on the 2.0 S3 API page.
- Async I/O through Iceberg and Delta is not stated on the I/O page. The page names Parquet, uncompressed seekable UTF-8 CSV, and “data lake formats such as DuckLake.”
- DuckLake Puffin deletion vectors are marked experimental in the delete-file spec.
