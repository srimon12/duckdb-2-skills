# Docs inventory

The 2.0 manual snapshot has 461 Markdown pages. The DuckLake stable snapshot has 76. Both mirror the URL path, so `sources/duckdb-2.0/clients/cli/agent_mode.md` is `https://duckdb.org/docs/2.0/clients/cli/agent_mode.html`.

| Snapshot | Files | Upstream commit |
| --- | --- | --- |
| `sources/duckdb-2.0/` | 461 | `37408677c0753c0b3607f8b77540df7f3096be95` |
| `sources/ducklake-stable/` | 76 | `1b74f10e93a3905e247c12f30b8882ca683db8f4` |

## Section sizes

| Section | Pages |
| --- | --- |
| `clients/cli` | 11 |
| `clients/python` | 12 |
| `clients/` other clients | 54 |
| `sql/statements` | 41 |
| `sql/functions` | 27 |
| `sql/data_types` | 22 |
| `sql/query_syntax` | 17 |
| `sql/dialect` | 7 |
| `data` | 30 |
| `core_extensions` | 26 |
| `extensions` | 8 |
| `operations_manual` | 17 |
| `configuration` | 3 |
| `quack` | 8 |
| `guides/file_formats` | 13 |
| `guides/network_cloud_storage` | 14 |
| `guides/python` | 18 |
| `guides/performance` | 12 |

## Pages by skill

### `duckdb`

- `clients/cli/overview.md`, `arguments.md`, `agent_mode.md`, `output_formats.md`, `dot_commands.md`, `safe_mode.md`, `friendly_cli.md`
- `configuration/overview.md`, `configuration/pragmas.md`
- `operations_manual/installing_duckdb/install_script.md`, `requirements.md`
- `operations_manual/logging/overview.md`, `operations_manual/limits.md`
- `internals/storage.md`
- `guides/troubleshooting/command_line.md`

### `duckdb-sql`

- `sql/dialect/friendly_sql.md`, `sql_quirks.md`, `keywords_and_identifiers.md`
- `sql/functions/lambda.md`
- `sql/statements/create_trigger.md`, `set_variable.md`, `create_schema.md`, `merge_into.md`, `update.md`, `create_view.md`, `show.md`, `create_sequence.md`, `alter_table.md`, `profiling.md`
- `sql/query_syntax/from.md`, `with.md`, `limit.md`, `groupby.md`, `grouping_sets.md`, `prepared_statements.md`
- `sql/expressions/star.md`
- `sql/data_types/variant.md`, `union.md`, `timestamp.md`, `struct.md`, `map.md`, `array.md`, `list.md`, `enum.md`, `numeric.md`
- `sql/meta/duckdb_table_functions.md`
- `sql/peg_parser.md`, `core_extensions/legacy_parser.md`
- `guides/sql_features/merge.md`, `graph_queries.md`, `asof_join.md`, `query_and_query_table_functions.md`, `timestamps.md`

### `duckdb-session`

- `sql/statements/attach.md`, `detach.md`, `use.md`, `checkpoint.md`
- `sql/meta/duckdb_table_functions.md`
- `connect/concurrency.md`
- `internals/storage.md`
- `operations_manual/footprint_of_duckdb/files_created_by_duckdb.md`, `gitignore_for_duckdb.md`, `reclaiming_space.md`

### `duckdb-files`

- `data/csv/overview.md`, `auto_detection.md`, `reading_faulty_csv_files.md`, `tips.md`
- `data/json/overview.md`, `loading_json.md`, `creating_json.md`, `writing_json.md`, `json_type.md`, `json_functions.md`, `format_settings.md`
- `data/parquet/overview.md`, `metadata.md`, `encryption.md`, `tips.md`
- `data/multiple_files/overview.md`, `combining_schemas.md`
- `data/partitioning/hive_partitioning.md`, `partitioned_writes.md`
- `data/io.md`, `data/insert.md`, `data/appender.md`
- `sql/statements/copy.md`
- `configuration/secrets_manager.md`
- `core_extensions/httpfs/overview.md`, `authentication.md`, `https.md`, `s3api.md`, `hugging_face.md`, `aws.md`, `azure.md`, `excel.md`, `avro.md`, `sqlite.md`
- `guides/file_formats/*.md`, `guides/network_cloud_storage/*.md`

### `duckdb-variant`

- `sql/data_types/variant.md`
- `sql/functions/variant.md`
- `data/parquet/overview.md`
- `core_extensions/delta.md`

### `duckdb-quack`

- `quack/overview.md`, `reference.md`, `security.md`, `troubleshooting.md`, `setup/*.md`
- `sql/statements/connect.md`
- `core_extensions/quack.md`, `postgres/overview.md`, `postgres/functions.md`, `postgres/secrets.md`, `postgres/connection_pool.md`, `mysql.md`
- `clients/cli/arguments.md`

### `duckdb-lakehouse`

- `core_extensions/ducklake.md`
- `core_extensions/iceberg/overview.md`, `catalogs.md`, `iceberg_options.md`, `iceberg_functions.md`, `writing_to_iceberg.md`, `troubleshooting.md`
- `core_extensions/delta.md`, `unity_catalog.md`
- `lakehouse_formats.md`
- `data/partitioning/hive_partitioning.md`, `partitioned_writes.md`
- `sources/ducklake-stable/duckdb/**` (all 76 pages)

### `duckdb-extensions`

- `extensions/overview.md`, `installing_extensions.md`, `versioning_of_extensions.md`, `extension_distribution.md`, `extension_repositories.md`, `community_extensions.md`, `troubleshooting.md`, `advanced_installation_methods.md`
- `operations_manual/securing_duckdb/securing_extensions.md`
- `sql/statements/load_and_install.md`, `update_extensions.md`

### `duckdb-docs`

- No local page. The source is the hosted index at `https://duckdb.org/data/docs-search.duckdb` and `https://ducklake.select/data/docs-search.duckdb`.
- `core_extensions/full_text_search.md` owns the `match_bm25` page, which is stale for 2.0.

### `duckdb-migrate`

- `operations_manual/migration.md`
- `internals/storage.md`
- `operations_manual/installing_duckdb/requirements.md`
- `configuration/pragmas.md`
- `sql/statements/attach.md`, `checkpoint.md`, `export.md`, `copy.md`
- `operations_manual/logging/overview.md`
- `clients/python/migration.md`
- `release_calendar.html` (live)

### `duckdb-python`

- `clients/python/overview.md`, `migration.md`, `dbapi.md`, `relational_api.md`, `expression.md`, `data_ingestion.md`, `conversion.md`, `types.md`, `appender.md`, `known_issues.md`
- `guides/python/install.md`, `execute_sql.md`, `import_pandas.md`, `export_pandas.md`, `import_arrow.md`, `export_arrow.md`, `import_polars.md`, `polars.md`, `multiple_threads.md`, `sql_on_arrow.md`

### `duckdb-spatial`

- `core_extensions/spatial/overview.md`, `functions.md`, `gdal.md`, `r-tree_indexes.md`
- `data/json/loading_json.md`, `writing_json.md`
- `data/partitioning/hive_partitioning.md`
- Overture: `https://docs.overturemaps.org/getting-data/duckdb/`, `/schema/`, `/guides/places/`, `/guides/buildings/`, `/guides/divisions/`, `/guides/transportation/`, `/release-calendar/`, `https://stac.overturemaps.org/catalog.json`

## Refresh

```bash
python3 scripts/fetch-docs.py
```

The script reads the pinned commits in `sources/MANIFEST.md`, downloads the Markdown, and reports failures. The live pages remain the source of truth. A snapshot is only a reading convenience.
