# Slice: lakehouse

Status: complete
Scope: DuckLake 1.1 attach/version/migration/operations/features, Iceberg, Delta, Unity Catalog, and the choice between a native `.duckdb` file and the three lakehouse formats. Object-storage secrets are owned by `duckdb-files`; this slice names only catalog-auth secret types.
Sources: `duckdb-2.0/core_extensions/{ducklake,delta,unity_catalog}.md`, `duckdb-2.0/core_extensions/iceberg/{overview,catalogs,iceberg_options,iceberg_functions,writing_to_iceberg,troubleshooting}.md`, `duckdb-2.0/lakehouse_formats.md`, `duckdb-2.0/guides/network_cloud_storage/s3_iceberg_import.md`, `duckdb-2.0/data/partitioning/{hive_partitioning,partitioned_writes}.md`, `ducklake-stable/duckdb/**` (all pages named in the brief), https://ducklake.select/2026/10/21/ducklake-11/, https://ducklake.select/docs/stable/. Binary: `duckdb v2.0.0 (Cyanoptera) d54cbbe3df`; `ducklake` extension build `417a9117f5`.

## Verified facts

### DuckLake attach

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| D1 | DuckDB-file catalog: `ATTACH 'ducklake:metadata.ducklake' AS lake;` creates the catalog if absent. `DATA_PATH` defaults to `<metadata_file>.files` in the same directory. | `usage/connecting.md`, `introduction.md`; P1 | Probed |
| D2 | SQLite catalog: `ATTACH 'ducklake:sqlite:metadata.sqlite' AS lake (DATA_PATH 'my_files/');`. The `sqlite:` prefix is required; an unprefixed SQLite file is not reliably detected. A new SQLite catalog requires `DATA_PATH`. | `usage/connecting.md`, `usage/choosing_a_catalog_database.md`; P2 | Probed |
| D3 | PostgreSQL catalog: `ATTACH 'ducklake:postgres:dbname=postgres' AS lake (DATA_PATH 's3://bucket/path/');`. PostgreSQL 12+; migration needs the owner of the metadata tables. | `usage/connecting.md`, `usage/choosing_a_catalog_database.md`, `migrations/upgrading_to_ducklake_1_1.md` | Documented |
| D4 | Options: `CREATE_IF_NOT_EXISTS` default `true` (`false` under `READ_ONLY`); `READ_ONLY` default `false`; `DATA_INLINING_ROW_LIMIT` default `ducklake_default_data_inlining_row_limit` (10); `DUCKLAKE_VERSION` default `ducklake_default_version` (default `NULL`); `ENCRYPTED` default `false`; `AUTOMATIC_MIGRATION` default `false`; `OVERRIDE_DATA_PATH` default `false`; `SNAPSHOT_VERSION`/`SNAPSHOT_TIME` unset; `WRITE_DELETION_VECTORS` default `ducklake_write_deletion_vectors` (false, experimental); `METADATA_CATALOG` default `__ducklake_metadata_<name>`; `METADATA_SCHEMA` backend default (`main` DuckDB/SQLite, usually `public` PostgreSQL); `METADATA_PARAMETERS` default `{}`. | `usage/connecting.md`; P1, P2 | Documented |
| D5 | `READ_ONLY` attaches without creating a catalog. `CREATE_IF_NOT_EXISTS` flips to `false`, and writes fail with `Cannot execute statement of type "INSERT" on database ... attached in read-only mode`. | `usage/connecting.md`; P3 | Probed |
| D6 | `SNAPSHOT_VERSION n` / `SNAPSHOT_TIME '...'` attach at a historical snapshot and are read-only for the connection. | `usage/time_travel.md`; P3 | Probed |
| D7 | `ENCRYPTED` is persisted in the catalog. Later attaches may omit it; requesting `ENCRYPTED false` against an encrypted catalog fails with `Failed to set encryption ...`. | `advanced_features/encryption.md`; P2 | Probed |
| D8 | `OVERRIDE_DATA_PATH true` overrides the stored path only for the current connection; data under the original path is not queryable in that connection. | `usage/connecting.md`, `guides/backups_and_recovery.md` | Documented |
| D9 | `MIGRATE` is not a DuckLake option: `ATTACH ... (MIGRATE true)` returns `Not implemented Error: Unsupported option migrate for DuckLake`. Only `AUTOMATIC_MIGRATION` exists. | P2 | Probed |
| D10 | `META_<PARAM>` passes parameters to the catalog server, e.g. `META_SECRET` for PostgreSQL; `METADATA_PARAMETERS` is the map form. | `usage/connecting.md` | Documented |
| D10b | Secrets can hold the connection: `CREATE SECRET (TYPE ducklake, METADATA_PATH 'metadata.duckdb', DATA_PATH 'metadata_files/'); ATTACH 'ducklake:';`; a named secret is `ATTACH 'ducklake:my_secret';`. `READ_ONLY` and `AUTOMATIC_MIGRATION` cannot be stored in the secret. | `usage/connecting.md` | Documented |
| D11 | The metadata file is a DuckDB database holding the `ducklake_*` catalog tables plus any inlined rows. It is not the Parquet data, not a native database of user tables, and not portable across DuckDB storage versions. | `introduction.md`, `usage/choosing_a_catalog_database.md`, `migrations/upgrading_to_ducklake_1_1.md`; P8 | Probed |
| D12 | Catalog choice: DuckDB file = one process at a time unless every process is read-only; SQLite = multiple local clients, one writer at a time with retries; PostgreSQL = multi-user/remote lakehouse. MySQL is explicitly not recommended; Quack is experimental. | `usage/choosing_a_catalog_database.md` | Documented |

### DuckLake 1.1 and migration

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| V1 | DuckLake 1.1 requires DuckDB 2.0.0+. The 2.0 extension reads and writes 1.0 catalogs without migrating; new catalogs default to 1.1. | `introduction.md`, `migrations/upgrading_to_ducklake_1_1.md`; P1 | Probed |
| V2 | Migration: back up catalog and data files, stop writes/compaction/cleanup, ensure every client supports 1.1, `RESET ducklake_default_version`, then `ATTACH ... (AUTOMATIC_MIGRATION true)`. Verify with `SELECT value FROM lake.options() WHERE option_name='version'`. | `migrations/upgrading_to_ducklake_1_1.md`, `guides/backups_and_recovery.md`; P2 | Probed |
| V3 | If `ducklake_default_version='1.0'`, `AUTOMATIC_MIGRATION` leaves a 1.0 catalog at 1.0. Reset the setting before migrating. | `migrations/upgrading_to_ducklake_1_1.md`; P2 | Probed |
| V4 | After migration, a pinned `ducklake_default_version='1.0'` makes a plain attach fail: `DuckLake catalog version is '1.1', which is newer than the requested version '1.0'. Cannot downgrade...`. `DUCKLAKE_VERSION '1.1'` overrides the pin. | P2 | Probed |
| V5 | A migrated catalog cannot be downgraded. Requesting `DUCKLAKE_VERSION '1.0'` returns the exact `Cannot downgrade a DuckLake catalog` error. | `guides/troubleshooting.md`; P2 | Probed |
| V6 | `DUCKLAKE_VERSION '1.1-dev1'` is rejected: `ducklake_version must be '1.0' or '1.1', got '1.1-dev1'`. Pre-1.0 and `1.1-dev1` catalogs must be migrated through a writable attachment, even for read-only use. | `migrations/upgrading_to_ducklake_1_1.md`, `guides/troubleshooting.md`; P2 | Probed |
| V7 | `AUTOMATIC_MIGRATION` on a read-only 1.0 attachment fails while renaming inlined-data columns. Attach writable once, or attach the already-migrated copy read-only. | `guides/troubleshooting.md`; P2 | Probed |
| V8 | DuckLake format version does not pin the DuckDB metadata file's storage version. A write by a newer DuckDB can make the file unreadable to older DuckDB even at format 1.0. Use one DuckDB release for every client, or PostgreSQL/SQLite. | `migrations/upgrading_to_ducklake_1_1.md` | Documented |
| V9 | 1.1-only: nested schemas; `"NULL"` type; `epoch_year/month/day/hour` transforms; `VARIANT` inlining into PostgreSQL `BYTEA`/SQLite `BLOB`; multi-snapshot Puffin delete files; exact string statistics and `row_group_count`; `_ducklake_`-prefixed internal inlined columns; view-column comments; macro `NULL`/non-scalar defaults and nested parameter types; cross-schema compaction across `ADD COLUMN`. | `ducklake-11` post; `advanced_features/{nested_schemas,partitioning,data_inlining,deletion_vectors,comments,macros}.md`, `maintenance/merge_adjacent_files.md`; P3, P5 | Documented |
| V10 | Files written before migration keep `row_group_count = NULL`. A 1.0 catalog's `ducklake_data_file` lacks the column entirely (binder error); `min_is_exact`/`max_is_exact` are 1.1-only. | `ducklake-11` post; P11 | Probed |
| V11 | Works on a 1.0 catalog with the 2.0 extension: `CREATE TABLE ... PARTITIONED BY` / `SORTED BY`; table `WITH (...)` options; `ducklake_merge_adjacent_files` size/window/limit arguments; `ducklake_rewrite_data_files max_compacted_files`. | `ducklake-11` post; `maintenance/{merge_adjacent_files,rewrite_data_files}.md`; P3, P10 | Probed |
| V11b | Also available without migrating: `ALTER TABLE ... SET/RESET` options, broader `ducklake_add_data_files` Parquet types, wider file pruning. | `ducklake-11` post; `metadata/adding_files.md` | Documented |
| V12 | `_ducklake_` is reserved for top-level column names, case-insensitively: `_DUCKLAKE_X` fails. A nested struct field `s._ducklake_y` is accepted. | `advanced_features/data_inlining.md`; P3 | Probed |

### DuckLake operations

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| O1 | `lake.snapshots()` and `ducklake_snapshots('lake')` return `snapshot_id BIGINT, snapshot_time TIMESTAMPTZ, schema_version BIGINT, changes MAP(VARCHAR,VARCHAR[]), author, commit_message, commit_extra_info`. | `usage/snapshots.md`, `ducklake.md`; P1 | Probed |
| O2 | `ducklake_current_snapshot('lake')` returns the latest snapshot visible to the transaction (`UBIGINT`). `ducklake_last_committed_snapshot('lake')` returns the latest commit through the attachment, or `NULL` after reattach until the next commit. | `usage/snapshots.md`; P1 | Probed |
| O3 | Time travel: `SELECT ... FROM t AT (VERSION => n)` uses the snapshot id; `AT (TIMESTAMP => ...)` uses a timestamp. Future timestamps and timestamps before the first snapshot fail. The `AT` expression cannot contain a subquery. | `usage/time_travel.md`; P1, P5 | Probed |
| O4 | `ducklake_table_info('lake')` returns exactly `table_name, schema_id, table_id, table_uuid, file_count, file_size_bytes, delete_file_count, delete_file_size_bytes`; there is no `estimated_size` or `column_count`. | `ducklake.md`; P1 | Probed |
| O5 | `ducklake_list_files('lake','t', schema=>..., snapshot_version=>..., snapshot_time=>...)` returns `data_file, data_file_size_bytes, data_file_footer_size, data_file_encryption_key, delete_file, delete_file_size_bytes, delete_file_footer_size, delete_file_encryption_key`. | `metadata/list_files.md`; P1 | Probed |
| O6 | `ducklake_metadata` is **not** a table function. The catalog table is `__ducklake_metadata_<name>.ducklake_metadata(key, value, scope, scope_id)`. `ducklake_options('lake')` and `ducklake_settings('lake')` do exist. | P1 | Probed |
| O7 | `ducklake_settings` returns `catalog_type, extension_version, data_path`; the attached macro is `lake.settings()`. `lake.options()` returns `option_name, description, value, scope, scope_entry`. | `usage/configuration.md`; P1 | Probed |
| O8 | `ducklake_merge_adjacent_files(catalog, table_name, min_file_size, max_file_size, max_compacted_files, newer_than, older_than, schema)` returns one row per operation: `schema_name, table_name, files_processed, files_created`. The overload without `table_name` takes `catalog, min_file_size, max_file_size, max_compacted_files, newer_than, older_than`. | `maintenance/merge_adjacent_files.md`; P4 | Probed |
| O9 | `ducklake_flush_inlined_data(catalog, schema_name, table_name)` returns `schema_name, table_name, rows_flushed HUGEINT`; tables with nothing inlined are omitted. | `advanced_features/data_inlining.md`; P4 | Probed |
| O10 | `ducklake_rewrite_data_files(catalog, table_name, delete_threshold, max_compacted_files, schema)` returns `schema_name, table_name, files_processed, files_created`; default delete threshold is 0.95. | `maintenance/rewrite_data_files.md`; P4 | Probed |
| O11 | `ducklake_expire_snapshots(catalog, older_than, versions, dry_run)` takes `versions BIGINT[]`; `versions` and `older_than` cannot be combined. It returns the expired snapshot rows, not a `Success` table. | `maintenance/expire_snapshots.md`; P4 | Probed |
| O12 | `ducklake_cleanup_old_files(catalog, older_than, cleanup_all, dry_run)` returns a `path` column. `cleanup_all=>true` ignores file age. | `maintenance/cleanup_of_files.md`; P4 | Probed |
| O13 | `ducklake_set_option(catalog, option, value, table_name, schema)` returns `Success`; `ducklake_add_data_files(catalog, table_name, path or paths, allow_missing, ignore_extra_columns, hive_partitioning, schema)` returns `filename` and registers the file without copying it. | `usage/configuration.md`, `metadata/adding_files.md`; P4 | Probed |
| O14 | Maintenance order in `CHECKPOINT`: flush inlined data, expire snapshots, merge adjacent files, rewrite data files, cleanup old files, delete orphaned files. `CHECKPOINT` is not just compaction; it can expire history and delete files. | `maintenance/checkpoint.md`; P4 | Probed |
| O15 | Safety: `ducklake_cleanup_old_files` only removes files in `ducklake_files_scheduled_for_deletion`; `ducklake_delete_orphaned_files` scans the data path recursively for untracked `.parquet`/`.puffin` files and can delete files DuckLake never wrote. Expiring snapshots destroys time travel and limits the change feed. | `maintenance/{cleanup_of_files,expire_snapshots}.md`, `guides/backups_and_recovery.md` | Documented |
| O16 | `ducklake_merge_adjacent_files` skips files with delete files or inlined deletions; use `ducklake_rewrite_data_files` for those, then merge. Files are not deleted immediately after merge; cleanup is a separate step. | `maintenance/{merge_adjacent_files,rewrite_data_files}.md` | Documented |

### DuckLake features

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| F1 | Partition transforms: `identity`, `bucket(N,col)`, `year/month/day/hour`, `epoch_year/month/day/hour`. `ALTER TABLE ... SET/RESET PARTITIONED BY`. Only new writes use the new keys. Default layout is Hive-style; `hive_file_pattern=false` opts out. | `advanced_features/partitioning.md`; P3 | Probed |
| F2 | Sorted tables: `CREATE TABLE ... SORTED BY (...)`; `ALTER TABLE ... SET/RESET SORTED BY` with `ASC/DESC NULLS FIRST/LAST` and scalar expressions. `sort_on_insert` defaults `true`. Compaction and flush use the current sort order. | `advanced_features/sorted_tables.md`; P4 | Probed |
| F3 | Nested schemas: create each parent first; `lake.sales.europe.orders` is nested; `lake."sales.europe"` is one top-level name. `USE`/`SHOW TABLES FROM` reject multi-part paths; `DROP SCHEMA ... CASCADE` is required for a non-empty schema. | `advanced_features/nested_schemas.md`; P3 | Probed |
| F4 | Constraints: only `NOT NULL`; `PRIMARY KEY`, `UNIQUE`, `CHECK`, and foreign keys are rejected. Upserts use `MERGE INTO`, not primary keys. | `advanced_features/{constraints,upserting}.md`, `unsupported_features.md`; P3 | Probed |
| F5 | Views, macros, comments: standard `CREATE VIEW`/`CREATE MACRO`/`COMMENT ON`; views are rewritten without the DuckLake catalog name so re-aliasing works; no secure views. View-column comments are 1.1-only. Macros support time travel. | `advanced_features/{views,macros,comments}.md` | Documented |
| F6 | Transactions: snapshot isolation for data and DDL; one committed `BEGIN-COMMIT` is one snapshot. Snapshot ids are sequential and primary-keyed; concurrent writers retry on non-logical conflicts and abort on logical conflicts. Retry knobs: `ducklake_max_retry_count` 10, `ducklake_retry_wait_ms` 100, `ducklake_retry_backoff` 1.5. | `advanced_features/{transactions,conflict_resolution}.md`, `usage/configuration.md` | Documented |
| F7 | Upserting: `MERGE INTO` supports `WHEN MATCHED THEN UPDATE` or `WHEN MATCHED THEN DELETE`, plus `WHEN NOT MATCHED THEN INSERT`. Only one UPDATE/DELETE action is supported. | `usage/upserting.md`; P4 | Probed |
| F8 | Data inlining: inserts and deletes up to the row limit go into catalog tables. Precedence: table/schema/global persisted option > `DATA_INLINING_ROW_LIMIT` attach option > `ducklake_default_data_inlining_row_limit` (10). `ducklake_flush_inlined_data` materializes it. | `advanced_features/data_inlining.md`; P1, P4 | Probed |
| F9 | Deletion vectors: experimental; `WRITE_DELETION_VECTORS` attach option or `write_deletion_vectors` option; 1.1 can consolidate multiple snapshots of the same data file into one Puffin file while preserving time travel. 1.0 falls back to Parquet delete files for multi-snapshot deletes. Puffin files are written unencrypted. | `advanced_features/{deletion_vectors,encryption}.md`; P5 | Probed |
| F10 | Row lineage: every row has a `rowid` unique within its table, preserved across updates, file moves, and compaction; the change feed uses it to distinguish update from delete+insert. | `advanced_features/row_lineage.md`; P5 | Probed |
| F11 | Encryption: `ENCRYPTED` at catalog creation encrypts Parquet data/delete files with Parquet encryption; keys live in the catalog. Requesting a different encryption mode on attach is rejected. | `advanced_features/encryption.md`; P2 | Probed |
| F12 | Data change feed: `lake.table_changes('t', start, end)` and `ducklake_table_changes(catalog, schema, table, start, end)`; timestamps or snapshot ids; `change_type` is `insert`, `update_preimage`, `update_postimage`, or `delete`. `table_insertions`/`table_deletions` are wrappers. | `advanced_features/data_change_feed.md`; P5 | Probed |
| F13 | Unsupported: indexes; primary/unique/foreign keys; `CHECK`; sequences; user-defined types; fixed-size `ARRAY`; `ENUM`; generated columns; `VARINT`, `BITSTRING`, `UNION`; `DROP TABLE ... CASCADE`; nested `VARIANT` written to Parquet; expression defaults in `ALTER TABLE ADD COLUMN`. | `unsupported_features.md`; P3 | Probed |

### Iceberg

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| I1 | Two modes: `iceberg_scan(path)` reads a table directly and is read-only with no catalog; `ATTACH '<warehouse>' AS c (TYPE iceberg, URI '...')` attaches a REST catalog and unlocks writes. | `iceberg/overview.md` | Documented |
| I2 | Attach syntax: `CREATE SECRET iceberg_secret (TYPE iceberg, CLIENT_ID '...', CLIENT_SECRET '...', OAUTH2_SERVER_URI '...'); ATTACH '<warehouse>' AS c (TYPE iceberg, SECRET iceberg_secret, URI 'https://...');`. A bearer token can be passed as `TOKEN`. | `iceberg/catalogs.md`, `iceberg/iceberg_options.md`; P7 | Documented |
| I3 | Attach options and defaults: `URI` (canonical; `ENDPOINT` deprecated alias, both rejected), `DEFAULT_SCHEMA` NULL, `ACCESS_DELEGATION_MODE` `vended_credentials`, `SUPPORT_NESTED_NAMESPACES` false, `STAGE_CREATE_TABLES` true, `DISABLE_MULTI_TABLE_COMMIT` false, `SKIP_CREATE_TABLE_METADATA_UPDATES` false, `REMOVE_FILES_ON_DELETE` true, `PURGE_REQUESTED` false, `ENCODE_ENTIRE_PREFIX` false, `MAX_TABLE_STALENESS` NULL, `EXTRA_HTTP_HEADERS` NULL, `DEFAULT_TABLE_LOCATION_FROM_NAMESPACE` false, `TABLE_RESOLUTION` lazy, `PREFIX` empty, `NAMESPACE_SEPARATOR` `0x1F`, `USE_METADATA_LOCATION` false. | `iceberg/iceberg_options.md`; P7 | Documented |
| I4 | `ENDPOINT_TYPE` is `S3_TABLES` or `GLUE` and cannot be combined with `URI`/`ENDPOINT` or `AUTHORIZATION_TYPE`; `AUTHORIZATION_TYPE` is `OAUTH2` (default), `SIGV4`, or `NONE`. | `iceberg/iceberg_options.md`; P7 | Documented |
| I5 | Reads: `iceberg_scan` takes `allow_moved_paths`, `metadata_compression_codec`, `snapshot_from_id`, `snapshot_from_timestamp`, `version`, `version_name_format`; a version hint or explicit `version` is required unless `unsafe_enable_version_guessing` is on. Only gzip metadata is supported. | `iceberg/iceberg_options.md`, `iceberg/overview.md`; P7 | Probed |
| I6 | `iceberg_metadata`, `iceberg_snapshots`, `iceberg_files`, `iceberg_manifests`, `iceberg_history`, `iceberg_refs`, `iceberg_partition_specs`, `iceberg_partition_stats`, `iceberg_column_stats`, `iceberg_scan_plan`, `iceberg_load_table_response`, `iceberg_view_metadata` exist. `iceberg_multi_file_reader` does not exist in 2.0.0. | `iceberg/iceberg_functions.md`; P7 | Probed |
| I7 | Writes through an attached REST catalog: `CREATE/DROP SCHEMA`, `CREATE/DROP TABLE`, `INSERT`, `UPDATE`, `DELETE`, `MERGE INTO`, `ALTER TABLE`, `SELECT`; `COPY FROM DATABASE` both directions. | `iceberg/writing_to_iceberg.md` | Documented |
| I8 | `UPDATE`/`DELETE`/`MERGE` use merge-on-read positional deletes (binary deletion vectors on v3 tables). They fail on sorted tables; copy-on-write is unsupported; `write.update.mode`/`write.delete.mode` must be `merge-on-read`. | `iceberg/writing_to_iceberg.md` | Documented |
| I9 | V3 support: `VARIANT`, `TIMESTAMP_NS`, schema-level default values, binary deletion vectors, row lineage. `format-version` is 2 by default; `iceberg_default_format_version` accepts 2 or 3. `GEOGRAPHY` is unsupported. | `iceberg/writing_to_iceberg.md`, `iceberg/iceberg_options.md` | Documented |
| I10 | Time travel on an attached catalog: `AT (VERSION => <snapshot_id>)` or `AT (TIMESTAMP => ...)`; `VERSION` is a snapshot id, not a Delta-style table version. Direct scans use `snapshot_from_id`/`snapshot_from_timestamp`, which are mutually exclusive. | `iceberg/overview.md`, `iceberg/iceberg_functions.md`; P7 | Documented |
| I11 | AWS Glue: `ATTACH '<account_id>' ... (ENDPOINT_TYPE 'glue')` or `URI 'glue.<region>.amazonaws.com/iceberg', AUTHORIZATION_TYPE 'sigv4'`; `SECRET` must name the S3/AWS secret. Glue does not assign a table location server-side, so `CREATE TABLE` needs `DEFAULT_TABLE_LOCATION_FROM_NAMESPACE true` or `WITH ('location' = '...')`. | `iceberg/catalogs.md`, `iceberg/iceberg_options.md` | Documented |
| I12 | Amazon S3 Tables: `ATTACH '<s3_tables_arn>' ... (ENDPOINT_TYPE s3_tables)`; sets SIGV4, region from the ARN, `REMOVE_FILES_ON_DELETE false`, `STAGE_CREATE_TABLES false`, `PURGE_REQUESTED true`. Explicit `URI` + `AUTHORIZATION_TYPE 'sigv4'` is the fallback for China regions. | `iceberg/catalogs.md`, `iceberg/iceberg_options.md` | Documented |
| I13 | Unity Catalog Horizon (Iceberg REST): set `STAGE_CREATE_TABLES false`, `DISABLE_MULTI_TABLE_COMMIT true`, `SKIP_CREATE_TABLE_METADATA_UPDATES true`, `REMOVE_FILES_ON_DELETE false` for endpoints with limited REST support. | `iceberg/catalogs.md` | Documented |
| I14 | REST catalogs are supported only when backed by S3, S3 Tables, or GCS; other storage backends are not yet supported. | `iceberg/catalogs.md` | Documented |

### Delta

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| L1 | Read: `delta_scan('file:///path')` or `ATTACH 's3://bucket/path' AS events (TYPE delta);` then `SELECT * FROM events`. The attachment holds one table named like the database; `events` and `events.events` both work. | `delta.md`; P6 | Probed |
| L2 | Attach options: `VERSION` (UBIGINT, latest), `TIMESTAMP` (TIMESTAMPTZ, latest), `PIN_SNAPSHOT` false, `PUSHDOWN_PARTITION_INFO` true, `PUSHDOWN_FILTERS` `all` (`none`, `constant_only`, `dynamic_only`). `VERSION` and `TIMESTAMP` are mutually exclusive; a pinned attach is read-only. | `delta.md`; P6 | Probed |
| L3 | Create/append (new in 2.0): `ATTACH '<path>' AS events (TYPE delta); CREATE TABLE events.events (...) PARTITIONED BY (...); INSERT INTO events VALUES ...`. The table name must be exactly the attached name; `CREATE TABLE events.other` fails with `must use the attached name ('events')`. | `delta.md`; P6 | Probed |
| L4 | Table properties in `WITH` are Delta properties; `location` must match the attached path. Enabling a feature can upgrade the protocol. `delta.enableVariantShredding` cannot be set at creation. | `delta.md`; P6 | Probed |
| L5 | Time travel: `AT (VERSION => 5)`, `AT (TIMESTAMP => TIMESTAMPTZ '...')`; `ATTACH ... (TYPE delta, VERSION 5)`; `delta_scan(..., version=>5)` / `timestamp=>...`. Timestamp reads the latest version at or before it; future or pre-first-commit timestamps fail; within a transaction a timestamp always reads one version. | `delta.md`; P6 | Probed |
| L6 | No `UPDATE`, `DELETE`, `MERGE INTO`, `ALTER TABLE`, `DROP TABLE`, `CREATE TABLE AS`, `CREATE OR REPLACE TABLE`, `RETURNING`, or `ON CONFLICT`. Exact errors: `Can only update base table`, `Can only delete from base table`, `Can only merge into base tables!`. | `delta.md`; P6 | Probed |
| L7 | `CREATE TABLE` rejects constraints (including `NOT NULL`), `DEFAULT`, generated columns, `SORTED BY`, `TIME`, unsigned integers, all-partition-column tables, and column-mapping tables with nested/partition columns. | `delta.md`; P6 | Probed |
| L8 | `VARIANT`: top-level columns can be created/read/appended; nested `VARIANT` inside struct/list/map can be created but not written (`Delta INSERT does not support column ... with a VARIANT nested in a STRUCT yet`). DuckDB writes shredded variant only if `delta.enableVariantShredding` is true; DuckDB-created tables are unshredded. `SELECT v.a` can skip other shredded fields unless a `TIMESTAMPTZ` field exists at any depth. | `delta.md`; P6 | Probed |
| L9 | `delta_column_mapping_policy` defaults to `strict` in 2.0 (was `lenient` in 1.5). `SET delta_column_mapping_policy='lenient'` restores matching id-mode files without Parquet field ids by name. | `delta.md`; P6 | Probed |
| L10 | Catalog-managed tables (`catalogManaged`, e.g. Unity Catalog managed) cannot be read/written through `delta_scan` or `ATTACH ... (TYPE delta)`; attach the catalog. | `delta.md` | Documented |
| L11 | Other limits: interval/geometry/geography columns cannot be read; `allowColumnDefaults` tables cannot be written; `CHAR(n)`/`VARCHAR(n)` widths on nested fields cannot be written; platforms are Linux/macOS/Windows AMD64 only. | `delta.md` | Documented |
| L12 | Extras: `CHECKPOINT` compacts the log; `delta_list_files`, `delta_domain_metadata`, `delta_set_transaction_version`/`delta_get_transaction_version` for idempotent appends. | `delta.md` | Documented |
| L13 | Local vs remote: local paths work as `file:///path` or a plain path; remote tables use `s3://`, `az://`, or `gs://` and the same `TYPE delta` attach, with the matching storage secret. No catalog is involved for external Delta tables. | `delta.md`; P6 | Probed |

### Unity Catalog

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| U1 | `unity_catalog` attaches Databricks or Unity Catalog OSS: `CREATE SECRET (TYPE unity_catalog, TOKEN '...', ENDPOINT '...', AWS_REGION '...'); ATTACH '<catalog>' AS uc (TYPE unity_catalog, DEFAULT_SCHEMA 'main');`. A storage secret is also required. | `unity_catalog.md`; P9 | Documented |
| U2 | Options: `SECRET` (unnamed secret by default), `DEFAULT_SCHEMA` (detected; OSS requires it), `READ_ONLY` false, `USE_IRC_SCAN_PLAN` false (Databricks only). | `unity_catalog.md` | Documented |
| U3 | Reads, inserts, and `CREATE TABLE` (managed without location, external with `WITH (location=...)`); time travel by version/timestamp; `unity_catalog_checkpoint_table`. | `unity_catalog.md` | Documented |
| U4 | No `UPDATE`/`DELETE`/`DROP TABLE`/`ALTER TABLE`, no view/schema DDL. Inserts into tables with `DEFAULT`/generated columns fail. `CREATE TABLE` rejects constraints, defaults/generated columns, unsupported types, `SORTED BY`, and `WITH` options other than `location`. | `unity_catalog.md` | Documented |
| U5 | Managed tables use catalog-managed commits; Unity coordinates concurrent writers. A managed table created by DuckDB uses this protocol. `CHECKPOINT` does not apply; use `unity_catalog_checkpoint_table`. | `unity_catalog.md` | Documented |
| U6 | `USE_IRC_SCAN_PLAN` uses Databricks server-side planning; time travel still reads the Delta log, and tables with equality deletes fail (reattach without the option). | `unity_catalog.md` | Documented |
| U7 | Unity Catalog is a catalog, not a fourth file format: use `unity_catalog` for Delta tables, or an Iceberg REST attach for Iceberg tables. | `unity_catalog.md`, `iceberg/catalogs.md` | Documented |

## Decision table

Synthesis of the rows above; "catalog needed" means a metadata catalog separate from the data files.

| Format | Concurrent writers | Open format | Catalog needed | Time travel | Schema evolution | Variant | Write support from DuckDB | Best fit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Native `.duckdb` | No cross-process writer; one process, many threads | No | No | No | Yes | Yes | Full DDL/DML | Single-process analytics, app state, local scratch |
| DuckLake | Yes, through the catalog DB; DuckDB-file catalog is one process unless read-only; SQLite one writer with retries; PostgreSQL multi-user | Yes (open spec, Parquet data) | Yes (DuckDB file, SQLite, or PostgreSQL) | Yes, snapshot id or timestamp | Yes, widening promotions | Yes; `VARIANT` inlining to PG/SQLite needs 1.1 | Full DDL/DML/`MERGE`, transactions | DuckDB-native lakehouse, multi-writer ACID, maintenance/change feed |
| Iceberg | Yes, through a REST catalog | Yes | Yes for writes; no for a single read-only table via `iceberg_scan` | Yes, snapshot id or timestamp | Yes, metadata-only `ALTER` | Yes on v3 | Create/insert/update/delete/merge/alter; merge-on-read only, no copy-on-write, not on sorted tables | Cross-engine open lakehouse with an existing REST catalog |
| Delta | Yes, optimistic log; Unity/catalog-managed for managed tables | Yes | No for an external table by path; yes for catalog-managed/Unity | Yes, table version or timestamp | Read yes; DuckDB write no (`ALTER` unsupported) | Top-level only | Create + append only | Reading existing Delta, append-only ingestion, Unity append |

## Existing skill audit

| Skill | Claim or omission | Verdict | Fix |
| --- | --- | --- | --- |
| `duckdb-lakehouse` L18 | "DuckLake 1.1 needs DuckDB 2.0.0 or newer." | Correct | Keep. |
| `duckdb-lakehouse` L18 | "The new extension reads and writes a 1.0 catalog. New catalogs are format 1.1 unless you ask for 1.0." | Correct | Keep; add that `ducklake_default_version` can override the default. |
| `duckdb-lakehouse` L25 | "Migrate only when the user wants a 1.1 feature. Back up the catalog and the data files first. Migration needs write access." | Thin | Add: irreversible; every client must support 1.1; pause writes/compaction/cleanup; back up catalog + data together; `RESET ducklake_default_version` first. |
| `duckdb-lakehouse` L32 | "If `ducklake_default_version` is `1.0`, migration leaves the catalog at 1.0 until you reset it." | Thin | Correct, but a leftover `1.0` pin later makes plain attaches to the migrated 1.1 catalog fail with "cannot downgrade". State that. |
| `duckdb-lakehouse` L32 | "`DUCKLAKE_VERSION '1.1-dev1'` is rejected." | Correct | Keep; add that `1.1-dev1` catalogs need a writable migration even for read-only use. |
| `duckdb-lakehouse` L34 | "A DuckDB-file catalog written by DuckDB 2.0 can become unreadable to older DuckDB even when the DuckLake format stays 1.0." | Correct | Keep; this is the reason to prefer PostgreSQL for mixed-version clients. |
| `duckdb-lakehouse` L36-43 | "These need format 1.1: Nested schemas ... `"NULL"` ... epoch transforms ... `VARIANT` inlining ... multi-snapshot Puffin ... exact string statistics and `row_group_count`." | Thin | Add the missing 1.1-only items: `_ducklake_` inlined-column rename, view-column comments, macro `NULL`/nested-type defaults, cross-schema compaction; note pre-migration files keep `row_group_count=NULL`. |
| `duckdb-lakehouse` L45 | "These work on a 1.0 catalog ... `PARTITIONED BY` and `SORTED BY` ... per-table `WITH (...)` options, and the wider file-pruning rules." | Thin | Add the new compaction arguments (`max_compacted_files`, `newer_than`/`older_than`, size filters) and broader `ducklake_add_data_files` types, which also work on 1.0. |
| `duckdb-lakehouse` L55 | "Top-level column names starting with `_ducklake_` are reserved on 1.1, case-insensitive." | Correct | Keep; nested fields are not covered, and 1.0 used `row_id`/`begin_snapshot`/`end_snapshot`. |
| `duckdb-lakehouse` L57 | "The 1.1 blog shows extra arguments on `ducklake_merge_adjacent_files`. The DuckDB core page lists only the catalog. Read ... before calling it." | Thin | Replace with the exact 8-parameter signature and 4-column return; say the core page is stale and the stable maintenance page/binary win. |
| `duckdb-lakehouse` L61 | "Writes go through `ATTACH ... (TYPE iceberg)`. `iceberg_scan` is read-only and has no catalog." | Correct | Keep; add that a REST catalog is required to commit writes. |
| `duckdb-lakehouse` L63-70 | Four REST options: `DEFAULT_TABLE_LOCATION_FROM_NAMESPACE`, `USE_METADATA_LOCATION`, `PREFIX`, `NAMESPACE_SEPARATOR`. | Thin | Move the full option/default/auth matrix to `references/catalogs.md`; keep the four that change behavior in SKILL.md. |
| `duckdb-lakehouse` L72 | "`URI` is the catalog URL. `ENDPOINT` is a deprecated alias. Do not pass both." | Correct | Keep; probe confirms `Both 'uri' and deprecated 'endpoint' were provided`. |
| `duckdb-lakehouse` L84 | "`ATTACH` does not check that the path is a Delta table. A typo attaches an empty database and fails on the first read." | Correct | Keep; name the observed error (`Table with name ... does not exist`, zero tables). |
| `duckdb-lakehouse` L84 | "The table name in `CREATE TABLE` is qualified with the attached database name." | Wrong | It must be exactly the attached name: `CREATE TABLE events.other` fails `Delta CREATE TABLE must use the attached name ('events'), found 'other'`. |
| `duckdb-lakehouse` L84 | "No `UPDATE`, `DELETE`, `MERGE INTO`, `ALTER TABLE`, or `DROP TABLE` ... No constraints, no `DEFAULT`, no `SORTED BY`, no `TIME`, no unsigned integers." | Correct | Keep; add `RETURNING`/`ON CONFLICT` and the nested-variant write limit. |
| `duckdb-lakehouse` L86-94 | Time travel by `AT (VERSION)`, `AT (TIMESTAMP)`, and `ATTACH ... VERSION`; "A version and a timestamp together are rejected. An attach pinned ... is read-only." | Correct | Keep; add timestamp-before-first-commit/future errors and `delta_scan` parameters. |
| `duckdb-lakehouse` L96 | "`VARIANT` columns can be created and appended at the top level ... shreds ... only when ... `delta.enableVariantShredding` ... `CREATE TABLE` cannot set that property ... `VARIANT` inside a struct, list, or map cannot be written." | Correct | Keep; add that `CREATE TABLE` with a nested `VARIANT` succeeds but the insert fails. |
| `duckdb-lakehouse` L98 | "`delta_column_mapping_policy` defaults to `strict` in 2.0. It was `lenient` in 1.5." | Correct | Keep. |
| `duckdb-lakehouse` L100 | "Catalog-managed tables, including Unity Catalog managed tables, are not readable with `delta_scan` or `ATTACH ... (TYPE delta)`. Attach the catalog." | Thin | Add the actual `unity_catalog` secret/attach syntax and its write limits; otherwise the agent knows the rule but not the move. |
| `duckdb-lakehouse` (omission) | No DuckLake snapshots, time travel, `ducklake_*` maintenance, inlining, upserting, change feed, encryption, or constraints. | Thin | Add a compact operations block to SKILL.md and signatures to `references/catalogs.md`. This is the largest coverage gap. |
| `duckdb-lakehouse` (omission) | No native-vs-DuckLake-vs-Iceberg-vs-Delta decision table. | Thin | Add the four-row table above to SKILL.md. |
| `duckdb-lakehouse` (omission) | No Iceberg DML/`ALTER` support or merge-on-read/no-copy-on-write limits. | Thin | Add five bullets to SKILL.md; details in reference. |
| `duckdb-lakehouse` (omission) | No attach-type/glob/cleanup traps. | Thin | Add the top traps below to SKILL.md. |

## Gaps worth adding

| Rank | Gap | Why an agent needs it | Home |
| --- | --- | --- | --- |
| 1 | Native vs DuckLake vs Iceberg vs Delta decision table | The first question is which format; a wrong pick changes concurrency, write support, and catalog requirements. | SKILL.md |
| 2 | DuckLake attach syntax for DuckDB/SQLite/PostgreSQL plus option defaults | `DATA_PATH` is required for new SQLite/PostgreSQL catalogs and defaults only for DuckDB files; `READ_ONLY` changes creation behavior. | SKILL.md one-liners; full table in `references/catalogs.md` |
| 3 | DuckLake migration safety: irreversible, all clients 1.1, backup both halves, `ducklake_default_version` pin | The current text can leave an agent with a migrated catalog that no longer attaches, or a 1.0 catalog it cannot downgrade. | SKILL.md warning; procedure in `references/catalogs.md` |
| 4 | DuckLake operations: snapshots/time travel, `ducklake_*` signatures, maintenance order | Without these an agent cannot answer "what changed", "read last week", or "compact safely". | SKILL.md short block; signatures in `references/catalogs.md` |
| 5 | DuckLake maintenance safety: `CHECKPOINT` expires/deletes; `cleanup_all`; orphan deletion scans the data path | These are destructive and irreversible; an agent that calls them casually can delete data or history. | SKILL.md warnings; details in reference |
| 6 | Iceberg REST option matrix and auth/provider recipes (Glue, S3 Tables, Unity Horizon) | Attach fails or `CREATE TABLE` fails without the right location/auth option; the current four-option table is not enough. | `references/catalogs.md` |
| 7 | Iceberg write surface and limits | Agents assume Iceberg writes are like DuckLake; merge-on-read only, no copy-on-write, not on sorted tables, no `GEOGRAPHY`. | SKILL.md bullets |
| 8 | Delta exact-name rule, append-only limits, and Unity path | `CREATE TABLE events.other` fails; managed tables need `unity_catalog`, not `delta_scan`. | SKILL.md; options in `references/catalogs.md` |
| 9 | Attach-type and glob traps | Silent wrong-type attach and globbing produce plausible but wrong results (4900 vs 1100 rows in P8). | SKILL.md |
| 10 | 1.0-vs-1.1 feature matrix | Prevents unnecessary irreversible migrations and explains why a 1.1 feature fails on an old catalog. | `references/catalogs.md` |
| 11 | Cross-format snapshot semantics | `VERSION` means snapshot id in DuckLake/Iceberg and table version in Delta; mixing them yields wrong history. | `references/catalogs.md` |
| 12 | Unity Catalog extension attach/limits | The skill only says "attach the catalog" without the secret, `DEFAULT_SCHEMA`, `AWS_REGION`, or write limits. | `references/catalogs.md` |

### Split between SKILL.md and `references/catalogs.md`

| Content | Home | Reason |
| --- | --- | --- |
| Decision table, format boundaries, "use X when" | SKILL.md | Read on every task; changes the plan. |
| DuckLake one-line attach, migration warning, snapshot/time-travel one-liners | SKILL.md | An agent must be able to act after loading one skill. |
| Iceberg read-vs-write split and five DML limits | SKILL.md | Prevents the most common wrong write attempt. |
| Delta append-only limits and exact-name rule | SKILL.md | Short, high-consequence. |
| Top traps: wrong attach type, globbing, cleanup/orphan deletion, version pin | SKILL.md | Safety-critical. |
| Full DuckLake `ATTACH` option/default table and backend choice | `references/catalogs.md` | Long lookup table, rarely needed. |
| Full Iceberg REST option/auth/provider matrix | `references/catalogs.md` | Provider-specific, long, and versioned separately. |
| Delta attach options and Unity Catalog recipe | `references/catalogs.md` | Detail without decision value. |
| DuckLake maintenance function signatures/returns and `CHECKPOINT` order | `references/catalogs.md` | Long signatures; SKILL.md keeps the order and warnings. |
| 1.0/1.1 feature matrix and pre-migration caveats | `references/catalogs.md` | Lookup table. |
| Cross-format time-travel semantics | `references/catalogs.md` | Small table, easy to get wrong. |

Do not split Iceberg and Delta into separate skills. The decision table is the product; splitting duplicates auth/attach concepts and hides the choice the user is actually making. Keep one `duckdb-lakehouse` skill with one `references/catalogs.md`.

## Traps and contradictions

| Trap | What happens | Correct move | Evidence |
| --- | --- | --- | --- |
| Attaching a non-Delta path as Delta | `ATTACH` succeeds with zero tables; the first `SELECT` fails `Table with name ... does not exist`. | Verify `_delta_log/` exists before attaching; use `delta_scan` on a known table. | P6 |
| Attaching a DuckLake metadata file as a native DuckDB file | `ATTACH 'meta.ducklake'` succeeds and shows only `ducklake_*` catalog tables; user tables are invisible. | Attach with `ducklake:`; never treat the catalog as a native database. | P8 |
| Attaching a native DuckDB file as DuckLake | `ATTACH 'ducklake:plain.duckdb'` silently adds DuckLake catalog tables inside the file and hides existing user tables from the DuckLake attachment; the user table still exists natively. | Use `ducklake:` only on a dedicated catalog file; check the path before attaching. | P8 |
| Globbing a catalog's data directory | `read_parquet('meta.ducklake.files/**/*.parquet')` reads stale, merged, and delete files; P8 returned 4900 rows where DuckLake returned 1100. Deletes and time travel are bypassed. | Query through the DuckLake catalog, or use `ducklake_list_files` for the exact file set. | P8 |
| Mixing DuckDB versions on a DuckDB-file catalog | A write by newer DuckDB upgrades the metadata file's storage version; older DuckDB can no longer open it even if the DuckLake format is 1.0. | One DuckDB release for all clients, or use PostgreSQL/SQLite. | `migrations/upgrading_to_ducklake_1_1.md` |
| Irreversible migration | `DUCKLAKE_VERSION '1.0'` on a 1.1 catalog fails `Cannot downgrade`; there is no down-migration. | Back up both catalog and data; migrate a copy first; verify all clients. | P2 |
| `AUTOMATIC_MIGRATION` on every attach | On a read-only 1.0 catalog it fails while altering inlined-data columns; on a 1.1 catalog it is unnecessary; a pinned `ducklake_default_version='1.0'` makes plain attaches fail. | Migrate once with write access, then omit the flag; `RESET ducklake_default_version` after migration. | P2 |
| Iceberg `URI` vs `ENDPOINT` | Supplying both: `Both 'uri' and deprecated 'endpoint' were provided`; supplying neither: OAuth/token/secret error. | Use `URI`; `ENDPOINT` only for old configs. | P7 |
| Delta `UPDATE`/`DELETE`/`MERGE` | `Can only update base table`, `Can only delete from base table`, `Can only merge into base tables!`. | Rewrite the table or use another engine; DuckDB Delta is append-only. | P6 |
| `VARIANT` inside a struct/list/map in Delta | `CREATE TABLE` succeeds; `INSERT` fails `VARIANT nested in a STRUCT yet`. | Keep `VARIANT` top-level, or write with an engine that supports nested variant. | P6 |
| Delta `CREATE TABLE` name | `CREATE TABLE events.other` fails `must use the attached name ('events')`. | Create exactly `<attached_db>.<attached_db>`. | P6 |
| `ducklake_metadata` as a function | `ducklake_metadata('lake')` does not exist; the data is in `__ducklake_metadata_<name>.ducklake_metadata`. | Query the catalog table, or use `ducklake_options`/`ducklake_settings`. | P1 |
| Iceberg `VERSION` semantics | `AT (VERSION => 5)` means snapshot id 5, not the fifth table version; Delta's `VERSION 5` means table version 5. | Read `iceberg_snapshots` first; do not copy a Delta version number into Iceberg. | `iceberg/iceberg_functions.md`; P7 |
| `AT (TIMESTAMP => now() - INTERVAL '1 hour')` | Fails if no snapshot exists that early: `No snapshot found at timestamp ...`; `AT` cannot contain a subquery. | Use a timestamp inside the retained history; compute bounds in a separate query. | P1, P5 |
| `ducklake_cleanup_old_files(cleanup_all=>true)` / `ducklake_delete_orphaned_files` | `cleanup_all` ignores age; orphan cleanup recursively deletes untracked `.parquet`/`.puffin` files in the data path, including files DuckLake never wrote. | Dry-run first; prefer `older_than`; never point it at a shared directory. | `maintenance/cleanup_of_files.md`; P4 |
| `CHECKPOINT` on DuckLake | Runs flush, expire, merge, rewrite, cleanup, delete-orphaned; with `expire_older_than` set it destroys time travel and the change feed. | Set retention first; run in a maintenance window; back up before the first run. | `maintenance/checkpoint.md`; P4 |
| Core manual function returns are stale | The core `ducklake.md` says `cleanup_old_files`/`expire_snapshots` return `Success` and 0 rows, and `merge_adjacent_files` takes only `catalog`; the 2.0 binary returns `path` rows, snapshot rows, and an 8-argument merge with per-table stats. | Trust the binary/stable DuckLake manual; quote the probed signatures. | P4 |

## What not to add

- Separate `duckdb-iceberg` and `duckdb-delta` skills. The decision is comparative; splitting duplicates attach/auth and hides the choice.
- The object-storage secret table. `duckdb-files` owns S3/R2/GCS/Azure secrets; this skill only needs catalog-auth secret types (`TYPE iceberg`, `TYPE unity_catalog`) and a one-line pointer.
- Full DuckLake specification table DDL (`ducklake_column`, `ducklake_data_file`, ...). Link the spec; only `ducklake_metadata` and the user-facing functions earn space.
- Iceberg/Delta protocol internals (manifest Avro layout, Delta log JSON actions). Behavior and limits are enough.
- An exhaustive Iceberg function catalogue. Keep `iceberg_scan`, `iceberg_snapshots`, `iceberg_files`, `iceberg_rewrite_data_files`, `iceberg_rollback_to_snapshot`, `iceberg_to_ducklake`; link the rest.
- Unity Catalog REST API details beyond attach, `DEFAULT_SCHEMA`, `AWS_REGION`, `USE_IRC_SCAN_PLAN`, and write limits.
- DuckLake performance benchmarks and retry-tuning recipes. Defaults are fine; mention the knobs only in the reference.
- Per-format partitioning tutorials. One line per format plus the transform list is enough.

## Probe log

```text
$ duckdb --version
v2.0.0 (Cyanoptera) d54cbbe3df

### P1 — create 1.1, inspect, snapshots, time travel
$ duckdb -no-agent < p1.sql
catalog_type duckdb | extension_version 417a9117f5 | data_path .../p1/meta.ducklake.files/
snapshot_id 0..3; changes include schemas_created, tables_created, inlined_insert
ducklake_current_snapshot('lake') -> 3
SELECT count(*) FROM lake.t AT (VERSION => 1) -> 0   -- table created at snapshot 1, data at 2/3
SELECT count(*) FROM lake.t AT (TIMESTAMP => now() - INTERVAL '1 hour')
  Invalid Input Error: No snapshot found at timestamp 2026-10-21 19:02:32.976673+00
ducklake_metadata('lake')
  Catalog Error: Table Function with name ducklake_metadata does not exist

### P2 — migration / version
$ duckdb -no-agent < p2/a.sql
DUCKLAKE_VERSION '1.0' -> version 1.0
plain attach -> 1.0
SET ducklake_default_version='1.0'; AUTOMATIC_MIGRATION -> 1.0
RESET ducklake_default_version; AUTOMATIC_MIGRATION -> 1.1
ATTACH ... (DUCKLAKE_VERSION '1.0') on 1.1
  Invalid Input Error: DuckLake catalog version is '1.1', which is newer than the requested version '1.0'. Cannot downgrade a DuckLake catalog.
ATTACH ... (DUCKLAKE_VERSION '1.1-dev1')
  Invalid Input Error: ducklake_version must be '1.0' or '1.1', got '1.1-dev1'
SET ducklake_default_version='1.0'; ATTACH 'ducklake:meta.ducklake'
  Invalid Input Error: DuckLake catalog version is '1.1', which is newer than the requested version '1.0'. Cannot downgrade...
READ_ONLY + AUTOMATIC_MIGRATION on 1.0
  Invalid Input Error: Failed to rename inlined-data metadata columns ... read-only mode!
ATTACH 'ducklake:sqlite:m.sqlite' with no DATA_PATH
  Invalid Input Error: ... data_path is not set - set the DATA_PATH parameter ...
ATTACH ... (MIGRATE true)
  Not implemented Error: Unsupported option migrate for DuckLake

### P3 — 1.0 refusals and 1.1 features
1.0 CREATE SCHEMA v10.sales.europe
  Invalid Input Error: DuckLake 1.0 does not support nested schemas
1.0 PARTITIONED BY (epoch_month(ts))
  Invalid Input Error: DuckLake 1.0 does not support the epoch_month partition transform - attach with AUTOMATIC_MIGRATION...
1.0 CTAS with NULL then ALTER TYPE VARCHAR
  Invalid Input Error: DuckLake 1.0 does not support the NULL type...
1.1 nested schema -> duckdb_schemas: europe parent sales
1.1 NULL -> type "NULL" -> VARCHAR
1.1 epoch_month insert -> 1 row
1.1 CREATE TABLE lake.u (..., _DUCKLAKE_X INT)
  Binder Error: Column name "_DUCKLAKE_X" is reserved by DuckLake for internal use...
1.0 CREATE TABLE ... PARTITIONED BY (r) SORTED BY (ts) WITH (parquet_compression='zstd')
  -> count(*) = 1  (works on 1.0)

### P4 — function signatures / maintenance
duckdb_functions() -> ducklake_merge_adjacent_files params:
  [catalog, table_name, min_file_size, max_file_size, max_compacted_files, newer_than, older_than, schema]
  overload without table_name: [catalog, min_file_size, max_file_size, max_compacted_files, newer_than, older_than]
  return: schema_name | table_name | files_processed | files_created
ducklake_table_info -> 8 columns (no estimated_size/column_count)
ducklake_list_files -> 8 columns
ducklake_cleanup_old_files(dry_run=>true, cleanup_all=>true) -> path rows
ducklake_expire_snapshots(versions=>[2]) -> expired snapshot rows (not Success/0 rows)
CALL ducklake_set_option('lake','parquet_compression','zstd') -> Success
CALL ducklake_flush_inlined_data('lake') -> main | t | 3
CHECKPOINT -> Success, 0 rows

### P5 — Puffin, row lineage, change feed
WRITE_DELETION_VECTORS true; DATA_INLINING_ROW_LIMIT 0; two deletes
  ducklake_list_files -> one data_file, one ...-delete.puffin
  AT (VERSION => 2) -> 99; AT (VERSION => 3) -> 98
  SELECT id, rowid ... UPDATE id=0 -> id=100, rowid=0
  lake.table_changes('t',3,5) -> snapshot_id, rowid, change_type, id, v

### P6 — Delta
CREATE TABLE events.events; INSERT 1,eu; INSERT 2,us
  AT (VERSION => 0) -> 0 rows; AT (VERSION => 1) -> 1 row
  AT (TIMESTAMP => future) -> Invalid Input Error: Delta time travel does not accept future timestamp...
UPDATE -> Binder Error: Can only update base table
DELETE -> Binder Error: Can only delete from base table
MERGE  -> Binder Error: Can only merge into base tables!
ALTER  -> Not implemented Error: Delta tables do not support altering
DROP   -> Not implemented Error: Delta tables do not support dropping
CTAS   -> Not implemented Error: Delta tables do not support CREATE TABLE AS SELECT yet...
OR REPLACE -> Not implemented Error: Delta tables do not support CREATE OR REPLACE TABLE
CREATE TABLE events.nc -> Not implemented Error: Delta CREATE TABLE must use the attached name ('events'), found 'nc'
NOT NULL -> Not implemented Error: Delta CREATE TABLE does not support NOT NULL constraints
DEFAULT  -> Not implemented Error: Delta CREATE TABLE does not support DEFAULT values ('id')
TIME     -> Not implemented Error: Delta CREATE TABLE does not support column 'x' of type TIME
UINTEGER -> Not implemented Error: Delta CREATE TABLE does not support column 'u' of type UINTEGER
nested VARIANT insert -> Not implemented Error: Delta INSERT does not support column 's' with a VARIANT nested in a STRUCT yet...
VARIANT top-level -> SELECT v.a = 1
ATTACH non-delta path -> 0 tables; SELECT * FROM nd.nd -> Catalog Error: Table with name nd does not exist!
ATTACH VERSION 1 + TIMESTAMP -> Invalid Input Error: ATTACH: 'version' and 'timestamp' are mutually exclusive
INSERT into pinned attach -> Invalid Input Error: Can not append to a read only table
current_setting('delta_column_mapping_policy') -> strict

### P7 — Iceberg
iceberg_scan('lineitem_iceberg', allow_moved_paths=true) -> 51793
snapshot_from_id=7635660646343998149 -> 51793
snapshot_from_timestamp='2023-02-15 15:08:00' -> 60175
iceberg_scan('lineitem_iceberg/metadata/v1.metadata.json') -> 60175
iceberg_snapshots -> 2 snapshots; iceberg_files -> 1 file, 51793 records
iceberg_metadata('lineitem_iceberg', allow_moved_paths=true)
  Invalid Configuration Error: 'manifest_entry.sequence_number' is only allowed to be NULL for ADDED entries
ATTACH ... (URI ..., ENDPOINT ...) -> Invalid Configuration Error: Both 'uri' and deprecated 'endpoint' were provided...
ATTACH ... (NAMESPACE_SEPARATOR '') -> Invalid Configuration Error: 'namespace_separator' cannot be empty
ATTACH ... (URI ...) with no secret -> Invalid Configuration Error: AUTHORIZATION_TYPE is 'oauth2', yet no 'secret'...
duckdb_functions() -> no iceberg_multi_file_reader

### P8 — wrong attach type and glob
ATTACH 'meta.ducklake' AS m (READ_ONLY); SHOW ALL TABLES -> only ducklake_* tables
ATTACH 'ducklake:plain.duckdb' AS l; SHOW ALL TABLES -> 0 rows; l.x missing
  (native reattach afterwards shows x plus newly created ducklake_* tables)
SELECT count(*) FROM read_parquet('m.ducklake.files/**/*.parquet') -> 4900
SELECT count(*) FROM lake.t -> 1100

### P9 — Unity Catalog lazy attach
ATTACH 'mycat' AS uc (TYPE unity_catalog, DEFAULT_SCHEMA 'main') -> no output
SHOW ALL TABLES
  IO Error: Could not resolve hostname error for HTTP GET to '/api/2.1/unity-catalog/schemas?catalog_name=mycat'

### P10 — new compaction arguments on a 1.0 catalog
CREATE 1.0 catalog; two 100-row inserts; DATA_INLINING_ROW_LIMIT 0
ducklake_merge_adjacent_files('lake','t', max_compacted_files=>10)
  main | t | files_processed 2 | files_created 1
ducklake_rewrite_data_files('lake','t', delete_threshold=>0.5) -> 0 rows

### P11 — row_group_count before/after migration
1.0 catalog, 100-row Parquet file:
  SELECT row_group_count FROM __ducklake_metadata_lake.ducklake_data_file
  Binder Error: Referenced column "row_group_count" not found...
After AUTOMATIC_MIGRATION:
  data_file_id 0 | record_count 100 | row_group_count NULL
```

## Open questions

- Do Iceberg writes behave as documented against a local REST catalog? No REST catalog or Docker daemon was available; settle with Lakekeeper/Polaris in CI and probe `CREATE TABLE`, `INSERT`, `UPDATE`, `MERGE`, `ALTER`, and `iceberg_rewrite_data_files`.
- `iceberg_metadata` failed on the manual's sample table while `iceberg_files`/`iceberg_snapshots` worked. Is this a 2.0.0 regression or a property of that table's older manifests? Settle with a freshly written Iceberg table and a newer extension build.
- Does `WRITE_DELETION_VECTORS` on a 1.0 catalog with two deletes fall back to Parquet files as documented? P5 probed only 1.1; run the same sequence with `DUCKLAKE_VERSION '1.0'`.
- What is the exact `older_than` boundary in `ducklake_cleanup_old_files` (strict `<` vs `<=`)? P4 used `now() + 1 day`; a controlled `schedule_start` would settle it.
- Are Unity Catalog managed-table reads/writes and `USE_IRC_SCAN_PLAN` behavior as documented? No endpoint or token; settle against a Databricks workspace or Unity Catalog OSS.
- Does `CREATE TABLE IF NOT EXISTS` work in Delta and Unity Catalog? Docs mention it for Unity; Delta was not probed.
