# Catalog reference

Read this when the skill needs an attach option, a maintenance signature, or a format limit. The driver is `duckdb-lakehouse/SKILL.md`.

## DuckLake attach

| Form | Example |
| --- | --- |
| DuckDB-file catalog | `ATTACH 'ducklake:metadata.ducklake' AS lake;` |
| SQLite catalog | `ATTACH 'ducklake:sqlite:metadata.sqlite' AS lake (DATA_PATH 'my_files/');` |
| PostgreSQL catalog | `ATTACH 'ducklake:postgres:dbname=postgres' AS lake (DATA_PATH 's3://bucket/path/');` |
| From a secret | `CREATE SECRET (TYPE ducklake, METADATA_PATH 'metadata.ducklake', DATA_PATH 'metadata_files/'); ATTACH 'ducklake:';` |

| Option | Default | Use |
| --- | --- | --- |
| `DATA_PATH` | `<metadata>.files` for a DuckDB catalog; required for a new SQLite or PostgreSQL catalog | Where Parquet data lives. |
| `CREATE_IF_NOT_EXISTS` | `true`; `false` under `READ_ONLY` | Create the catalog if absent. |
| `READ_ONLY` | `false` | Open without creating or writing. |
| `DATA_INLINING_ROW_LIMIT` | `ducklake_default_data_inlining_row_limit` (10) | Rows inlined into the catalog. |
| `DUCKLAKE_VERSION` | `ducklake_default_version` | `'1.0'` or `'1.1'`. |
| `ENCRYPTED` | `false` | Encrypt data and delete files. Persisted in the catalog. |
| `AUTOMATIC_MIGRATION` | `false` | Migrate a 1.0 catalog to 1.1 on attach. |
| `OVERRIDE_DATA_PATH` | `false` | Override the stored data path for this connection only. |
| `SNAPSHOT_VERSION` | unset | Attach at a snapshot id. Read-only. |
| `SNAPSHOT_TIME` | unset | Attach at a timestamp. Read-only. |
| `WRITE_DELETION_VECTORS` | `ducklake_write_deletion_vectors` (false) | Experimental Puffin deletion vectors. |
| `METADATA_CATALOG` | `__ducklake_metadata_<name>` | Metadata catalog name. |
| `METADATA_SCHEMA` | backend default | Metadata schema. |
| `METADATA_PARAMETERS` | `{}` | Extra catalog parameters. |
| `META_<PARAM>` | none | Single catalog parameter, e.g. `META_SECRET`. |

`MIGRATE` is not an option. `ATTACH ... (MIGRATE true)` fails.

Backend choice: a DuckDB-file catalog allows one writing process. SQLite allows multiple local clients with one writer at a time and retries. PostgreSQL allows multi-user and remote lakehouses. MySQL is not recommended. Quack is experimental.

## DuckLake 1.1

Migration:

```sql
RESET ducklake_default_version;
ATTACH 'ducklake:metadata.ducklake' AS lake (AUTOMATIC_MIGRATION true);
SELECT value FROM lake.options() WHERE option_name = 'version';
```

Before migrating: back up the catalog and the data files, stop writes, compaction, and cleanup, and make every client 1.1-capable. The migration is irreversible. A read-only attach cannot migrate. A leftover `ducklake_default_version='1.0'` makes later plain attaches fail with `Cannot downgrade a DuckLake catalog`. `DUCKLAKE_VERSION '1.1-dev1'` is rejected.

| Feature | 1.0 | 1.1 |
| --- | --- | --- |
| Nested schemas | No | Yes |
| `"NULL"` type | No | Yes |
| `epoch_year`, `epoch_month`, `epoch_day`, `epoch_hour` | No | Yes |
| `VARIANT` inlining to PostgreSQL or SQLite | No | Yes |
| Multi-snapshot Puffin deletes | No | Yes |
| Exact string statistics, `row_group_count` | No | Yes |
| `_ducklake_` internal column rename | No | Yes |
| View-column comments | No | Yes |
| Macro `NULL` and nested-type defaults | No | Yes |
| Cross-schema compaction after `ADD COLUMN` | No | Yes |
| `PARTITIONED BY`, `SORTED BY`, table `WITH (...)` | Yes | Yes |
| `ducklake_merge_adjacent_files` size and window arguments | Yes | Yes |
| `ducklake_rewrite_data_files max_compacted_files` | Yes | Yes |

Top-level column names starting with `_ducklake_` are reserved on 1.1, case-insensitive. A nested field may use the prefix.

Files written before migration keep `row_group_count = NULL`. A 1.0 catalog's `ducklake_data_file` has no such column. The DuckLake format version does not pin the DuckDB metadata file's storage version, so a newer DuckDB write can still make the metadata file unreadable to an older DuckDB.

## DuckLake operations

| Function | Signature | Returns |
| --- | --- | --- |
| `ducklake_snapshots` | `(catalog)` | `snapshot_id`, `snapshot_time`, `schema_version`, `changes`, `author`, `commit_message`, `commit_extra_info` |
| `ducklake_current_snapshot` | `(catalog)` | Latest visible snapshot id |
| `ducklake_last_committed_snapshot` | `(catalog)` | Latest commit through the attachment |
| `ducklake_table_info` | `(catalog)` | `table_name`, `schema_id`, `table_id`, `table_uuid`, `file_count`, `file_size_bytes`, `delete_file_count`, `delete_file_size_bytes` |
| `ducklake_list_files` | `(catalog, table, schema =>, snapshot_version =>, snapshot_time =>)` | Data and delete file paths and sizes |
| `ducklake_options` | `(catalog)` | `option_name`, `description`, `value`, `scope`, `scope_entry` |
| `ducklake_settings` | `(catalog)` | `catalog_type`, `extension_version`, `data_path` |
| `ducklake_merge_adjacent_files` | `(catalog, table_name, min_file_size, max_file_size, max_compacted_files, newer_than, older_than, schema)` | `schema_name`, `table_name`, `files_processed`, `files_created` |
| `ducklake_rewrite_data_files` | `(catalog, table_name, delete_threshold, max_compacted_files, schema)` | `schema_name`, `table_name`, `files_processed`, `files_created` |
| `ducklake_flush_inlined_data` | `(catalog, schema_name, table_name)` | `schema_name`, `table_name`, `rows_flushed` |
| `ducklake_expire_snapshots` | `(catalog, older_than, versions, dry_run)` | Expired snapshot rows |
| `ducklake_cleanup_old_files` | `(catalog, older_than, cleanup_all, dry_run)` | `path` |
| `ducklake_set_option` | `(catalog, option, value, table_name, schema)` | `Success` |
| `ducklake_add_data_files` | `(catalog, table_name, path, allow_missing, ignore_extra_columns, hive_partitioning, schema)` | `filename` |

`ducklake_metadata` is not a function. The catalog table is `__ducklake_metadata_<name>.ducklake_metadata(key, value, scope, scope_id)`.

Maintenance:

```sql
CALL ducklake_flush_inlined_data('lake');
CALL ducklake_expire_snapshots('lake', older_than => now() - INTERVAL '30 days', dry_run => true);
CALL ducklake_merge_adjacent_files('lake', 'orders', schema => 'sales', max_compacted_files => 10);
CALL ducklake_rewrite_data_files('lake', 'orders', max_compacted_files => 5);
CALL ducklake_cleanup_old_files('lake', older_than => now() - INTERVAL '7 days', dry_run => true);
CALL ducklake_delete_orphaned_files('lake', dry_run => true);
```

`CHECKPOINT` runs flush, expire, merge, rewrite, cleanup, and orphan deletion. With `expire_older_than` set it destroys time travel and the change feed. `cleanup_all => true` ignores age. Orphan deletion scans the data path recursively and can delete files DuckLake never wrote. Dry-run first.

Merge skips files with deletes or inlined deletions. Rewrite those first, then merge. Files are not removed immediately after a merge; cleanup is a separate step.

## DuckLake features

Partition transforms: `identity`, `bucket(N, col)`, `year`, `month`, `day`, `hour`, `epoch_year`, `epoch_month`, `epoch_day`, `epoch_hour`. `ALTER TABLE ... SET/RESET PARTITIONED BY` affects new writes only. The default layout is Hive-style; `hive_file_pattern=false` opts out.

`SORTED BY` supports `ASC`, `DESC`, `NULLS FIRST`, `NULLS LAST`, and scalar expressions. `sort_on_insert` defaults to `true`.

Nested schemas need each parent created first. `lake.sales.europe.orders` is nested; `lake."sales.europe"` is one name. `USE` and `SHOW TABLES FROM` reject multi-part paths. `DROP SCHEMA ... CASCADE` is required for a non-empty schema.

Constraints are `NOT NULL` only. `PRIMARY KEY`, `UNIQUE`, `CHECK`, and foreign keys are rejected. Upserts use `MERGE INTO`.

Transactions use snapshot isolation. One `BEGIN` to `COMMIT` is one snapshot. Concurrent writers retry on non-logical conflicts and abort on logical conflicts. Knobs: `ducklake_max_retry_count` 10, `ducklake_retry_wait_ms` 100, `ducklake_retry_backoff` 1.5.

Change feed: `lake.table_changes('t', start, end)` and `ducklake_table_changes(catalog, schema, table, start, end)`. `change_type` is `insert`, `update_preimage`, `update_postimage`, or `delete`. `table_insertions` and `table_deletions` are wrappers.

Unsupported: indexes, primary and unique keys, foreign keys, `CHECK`, sequences, user-defined types, fixed-size `ARRAY`, `ENUM`, generated columns, `VARINT`, `BITSTRING`, `UNION`, `DROP TABLE ... CASCADE`, nested `VARIANT` written to Parquet, and expression defaults in `ALTER TABLE ADD COLUMN`.

## Iceberg

Read-only direct scan:

```sql
SELECT * FROM iceberg_scan('path/to/table');
SELECT * FROM iceberg_scan('path/to/table', snapshot_from_id => 7635660646343998149);
SELECT * FROM iceberg_scan('path/to/table', snapshot_from_timestamp => '2023-02-15 15:08:00');
```

Writes need a REST catalog:

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

`URI` is canonical. `ENDPOINT` is deprecated. Passing both fails. A bearer token can be passed as `TOKEN`.

| Option | Default | Use |
| --- | --- | --- |
| `URI` | unset | REST catalog URL. |
| `DEFAULT_SCHEMA` | NULL | Default namespace. |
| `ACCESS_DELEGATION_MODE` | `vended_credentials` | Credential delegation. |
| `SUPPORT_NESTED_NAMESPACES` | `false` | Nested namespaces. |
| `STAGE_CREATE_TABLES` | `true` | Stage create. |
| `DISABLE_MULTI_TABLE_COMMIT` | `false` | Single-table commits only. |
| `SKIP_CREATE_TABLE_METADATA_UPDATES` | `false` | Skip metadata updates on create. |
| `REMOVE_FILES_ON_DELETE` | `true` | Remove files when a table is dropped. |
| `PURGE_REQUESTED` | `false` | Purge on drop. |
| `ENCODE_ENTIRE_PREFIX` | `false` | Encode the whole prefix. |
| `MAX_TABLE_STALENESS` | NULL | Catalog staleness bound. |
| `EXTRA_HTTP_HEADERS` | NULL | Extra headers. |
| `DEFAULT_TABLE_LOCATION_FROM_NAMESPACE` | `false` | `CREATE TABLE` without a location. |
| `TABLE_RESOLUTION` | `lazy` | Table resolution mode. |
| `PREFIX` | empty | Path prefix after `/v1/`. |
| `NAMESPACE_SEPARATOR` | `0x1F` | Nested namespace separator. |
| `USE_METADATA_LOCATION` | `false` | Read from the metadata-location file. |
| `ENDPOINT_TYPE` | unset | `S3_TABLES` or `GLUE`. |
| `AUTHORIZATION_TYPE` | `OAUTH2` | `OAUTH2`, `SIGV4`, or `NONE`. |

`ENDPOINT_TYPE` cannot be combined with `URI`/`ENDPOINT` or `AUTHORIZATION_TYPE`.

Glue: `ATTACH '<account_id>' ... (ENDPOINT_TYPE 'glue')`, or `URI 'glue.<region>.amazonaws.com/iceberg', AUTHORIZATION_TYPE 'sigv4'`. Glue does not assign a table location server-side, so `CREATE TABLE` needs `DEFAULT_TABLE_LOCATION_FROM_NAMESPACE true` or `WITH ('location' = '...')`.

S3 Tables: `ATTACH '<s3_tables_arn>' ... (ENDPOINT_TYPE s3_tables)`. This sets SIGV4, the region from the ARN, `REMOVE_FILES_ON_DELETE false`, `STAGE_CREATE_TABLES false`, and `PURGE_REQUESTED true`.

Unity Catalog Horizon over Iceberg REST: set `STAGE_CREATE_TABLES false`, `DISABLE_MULTI_TABLE_COMMIT true`, `SKIP_CREATE_TABLE_METADATA_UPDATES true`, `REMOVE_FILES_ON_DELETE false`.

Writes through an attached REST catalog: `CREATE/DROP SCHEMA`, `CREATE/DROP TABLE`, `INSERT`, `UPDATE`, `DELETE`, `MERGE INTO`, `ALTER TABLE`, `SELECT`, and `COPY FROM DATABASE` both ways. `UPDATE`, `DELETE`, and `MERGE` use merge-on-read positional deletes. They fail on sorted tables, copy-on-write is unsupported, and `write.update.mode`/`write.delete.mode` must be `merge-on-read`. V3 adds `VARIANT`, `TIMESTAMP_NS`, binary deletion vectors, and row lineage. `GEOGRAPHY` is unsupported.

Functions: `iceberg_metadata`, `iceberg_snapshots`, `iceberg_files`, `iceberg_manifests`, `iceberg_history`, `iceberg_refs`, `iceberg_partition_specs`, `iceberg_partition_stats`, `iceberg_column_stats`, `iceberg_scan_plan`, `iceberg_load_table_response`, `iceberg_view_metadata`, `iceberg_rewrite_data_files`, `iceberg_rollback_to_snapshot`, `iceberg_to_ducklake`. `iceberg_multi_file_reader` does not exist in 2.0.0.

Time travel on an attached catalog: `AT (VERSION => <snapshot_id>)` or `AT (TIMESTAMP => ...)`. `VERSION` is a snapshot id, not a table version. Direct scans use `snapshot_from_id` or `snapshot_from_timestamp`; they are mutually exclusive.

## Delta

| Option | Default | Use |
| --- | --- | --- |
| `VERSION` | latest | Pin a table version. Read-only. |
| `TIMESTAMP` | latest | Pin a timestamp. Read-only. |
| `PIN_SNAPSHOT` | `false` | Pin the snapshot at attach. |
| `PUSHDOWN_PARTITION_INFO` | `true` | Push partition filters. |
| `PUSHDOWN_FILTERS` | `all` | `none`, `constant_only`, `dynamic_only`. |

`VERSION` and `TIMESTAMP` are mutually exclusive. A pinned attach is read-only.

Create and append:

```sql
ATTACH 's3://bucket/path' AS events (TYPE delta);
CREATE TABLE events.events (id BIGINT, region VARCHAR) PARTITIONED BY (region);
INSERT INTO events VALUES (1, 'eu');
```

`CREATE TABLE` must use exactly `<attached_db>.<attached_db>`. `CREATE TABLE events.other` fails. `CREATE TABLE ... AS`, `CREATE OR REPLACE TABLE`, `UPDATE`, `DELETE`, `MERGE`, `ALTER`, `DROP`, `RETURNING`, and `ON CONFLICT` are not supported. Constraints, `DEFAULT`, generated columns, `SORTED BY`, `TIME`, and unsigned integers are rejected.

Time travel: `AT (VERSION => 5)`, `AT (TIMESTAMP => TIMESTAMPTZ '...')`, `ATTACH ... (VERSION 5)`, `delta_scan(..., version => 5)`, `delta_scan(..., timestamp => ...)`. A future or pre-first-commit timestamp fails.

`VARIANT`: top-level columns can be created, read, and appended. A nested `VARIANT` inside a struct, list, or map can be created but not written. DuckDB shreds only when `delta.enableVariantShredding` is true; `CREATE TABLE` cannot set it.

`delta_column_mapping_policy` defaults to `strict` in 2.0. `SET delta_column_mapping_policy = 'lenient'` restores name-based reads for id-mode files without Parquet field ids.

Catalog-managed tables, including Unity Catalog managed tables, cannot be read or written through `delta_scan` or `ATTACH ... (TYPE delta)`. Attach the catalog.

Extras: `CHECKPOINT` compacts the log, `delta_list_files`, `delta_domain_metadata`, `delta_set_transaction_version`, `delta_get_transaction_version`. Platforms are Linux, macOS, and Windows AMD64 only. Interval, geometry, and geography columns cannot be read.

## Unity Catalog

```sql
CREATE SECRET uc (
    TYPE unity_catalog,
    TOKEN '...',
    ENDPOINT 'https://...',
    AWS_REGION 'us-east-1'
);

ATTACH 'my_catalog' AS uc (TYPE unity_catalog, DEFAULT_SCHEMA 'main');
```

Options: `SECRET`, `DEFAULT_SCHEMA`, `READ_ONLY`, `USE_IRC_SCAN_PLAN`. A storage secret is also required for the data files.

Unity Catalog reads, inserts, and creates tables. Managed tables use catalog-managed commits. It does not support `UPDATE`, `DELETE`, `DROP TABLE`, `ALTER TABLE`, or view and schema DDL. Inserts into tables with `DEFAULT` or generated columns fail. `CREATE TABLE` rejects constraints, defaults, generated columns, unsupported types, `SORTED BY`, and `WITH` options other than `location`.

`USE_IRC_SCAN_PLAN` uses Databricks server-side planning. Tables with equality deletes fail under it; reattach without the option.

Unity Catalog is a catalog, not a fourth file format. Use it for Delta tables, or an Iceberg REST attach for Iceberg tables.

## Time travel semantics

| Format | `VERSION` means | Timestamp bound |
| --- | --- | --- |
| DuckLake | Snapshot id | Snapshot time |
| Iceberg | Snapshot id | Snapshot timestamp |
| Delta | Table version | Commit timestamp |

Do not copy a Delta version number into Iceberg or DuckLake. Read the format's snapshot list first.

## References

- https://ducklake.select/docs/stable/duckdb/usage/connecting.html
- https://ducklake.select/docs/stable/duckdb/migrations/upgrading_to_ducklake_1_1.html
- https://ducklake.select/docs/stable/duckdb/maintenance/checkpoint.html
- https://duckdb.org/docs/2.0/core_extensions/iceberg/iceberg_options.html
- https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html
- https://duckdb.org/docs/2.0/core_extensions/delta.html
- https://duckdb.org/docs/2.0/core_extensions/unity_catalog.html
