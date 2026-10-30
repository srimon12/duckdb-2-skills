# dbt v2 project reference

Read this when the skill needs an exact profile key, materialization behavior, error string, or the v1-to-v2 checklist.

## Profile keys

| Key | v2 | Meaning |
| --- | --- | --- |
| `type` | Required | `duckdb` |
| `path` | Optional | File path, `:memory:`, or `md:` connection string. Omit for in-memory. |
| `schema` | Recommended | dbt schema. Set it explicitly so hooks and models agree. |
| `threads` | Optional | Concurrent models inside one process. Default is `max_cpu`. |
| `extensions` | Optional | Extension names, or `{name, repo}` pairs. Applied at connect. |
| `settings` | Optional | DuckDB configuration map. Applied after attach. |
| `attach` | Optional | List of `{path, alias, type, read_only, is_ducklake}`. Types are `duckdb`, `sqlite`, `postgres`. |
| `secrets` | Optional | DuckDB secrets. Each appears as `__dbt_secret_N`. |
| `external_root` | Optional | Root for an `external` model that omits `location`. |
| `plugins` | v1 only | Python plugin hooks. Not read by v2. |
| `filesystems` | v1 only | fsspec filesystems. Not read by v2. |
| `database` | Derived | Basename of `path` without the suffix. |

`external_location`, `file_size`, and `overwrite` are v1 model config keys. dbt v2 fails with `UnusedConfigKey (dbt1060)`.

A profile `settings: storage_compatibility_version: v1.5.4` is accepted after attach and does not create an old file. The accepted strings come from the active driver: the bundled 1.5.4 driver rejects `v1.5.6`, and the 2.0 driver accepts it. `attach[].options` is parsed and dropped in v2; `attach[].options.storage_version` does not reach the `ATTACH`. Use `ATTACH ... (STORAGE_VERSION ...)` in the DuckDB CLI before dbt opens the file.

## Materializations

| Materialization | Status | Notes |
| --- | --- | --- |
| `table` | Works | Default build target |
| `view` | Works | Default when no materialization is set |
| `incremental` | Works | See the strategy table |
| `ephemeral` | Works | CTE, no database object |
| `seed` | Works | CSV fixture |
| `snapshot` | Works | Must live in `snapshots/`, not `models/` |
| `external` | Works | One file at `location`; parent directory must exist |
| `materialized_view` | Fails | `get_create_materialized_view_as_sql has not been implemented for this adapter` |
| Python model | Fails | `Internal Error: Python models are not supported for duckdb adapter` |
| `table_function` | Present | Macro exists; not covered by this pack |

## Incremental config

| Key | Required | Effect |
| --- | --- | --- |
| `unique_key` | `merge`, `delete+insert` | Join and delete key. A list is allowed. |
| `incremental_strategy` | No | `append`, `delete+insert`, `merge`, `microbatch`. |
| `incremental_predicates` | No | SQL conditions applied to the merge or delete. |
| `merge_update_condition` | No | Condition for the `WHEN MATCHED` branch. |
| `merge_insert_condition` | No | Condition for the `WHEN NOT MATCHED` branch. |
| `merge_update_columns` | No | Columns updated by `merge`. |
| `merge_exclude_columns` | No | Columns excluded from the update. |
| `merge_update_set_expressions` | No | Custom update expressions. |
| `on_schema_change` | No | `ignore`, `append_new_columns`, `sync_all_columns`, `fail`. |
| `event_time`, `begin`, `batch_size` | `microbatch` | Time column, start, and batch grain. |
| `partitioned_by` | No | DuckLake physical partitioning. `partition_by` is an alias. |

`merge` without `unique_key` emits `MERGE ... ON (FALSE)` and appends. `delete+insert` without `unique_key` degrades to an insert. Both look successful. Assert the row count after a rerun.

Duplicate source keys abort a merge:

```text
MERGE INTO command cannot affect the same target row more than once. A target row matched more than one source row; ensure the source rows are deduplicated or the ON condition is unique.
```

## Hooks

`this` inside a model renders the correct relation. `this` inside a hook can render `<database>.public.<model>` during compilation while the model lands in `main`. Set `schema: main` in the profile before using a hook that references `this`.

A table rebuild drops FTS and HNSW indexes. Recreate them in a post-hook. An incremental update leaves an FTS index stale because the incremental triggers cover only `INSERT` and `DELETE`.

## Artifacts and commands

| Command | Result |
| --- | --- |
| `dbt build` | Seeds, models, and tests in dependency order |
| `dbt build --full-refresh` | Rebuilds incremental targets |
| `dbt build --store-failures` | Writes test rows to `main_dbt_test__audit.<test>` |
| `dbt show --select model` | Previews a model without building it |
| `dbt show --inline "select ..."` | Ad-hoc query through the active connection |
| `dbt compile` | Compiled SQL under `target/compiled` |
| `dbt docs generate` | Executes selected nodes and writes metadata Parquet; use `--write-catalog` for `catalog.json` |
| `dbt retry` | Reruns failed nodes from `run_results.json` |

dbt v2 writes `manifest.json` and `run_results.json` to `target/`, plus a queryable metadata layer under `target/private/index/*.parquet`. Do not read `run_results.json` after `dbt docs generate`; the command can replace it with an empty run.

## Exact failures

| Situation | Error |
| --- | --- |
| Bundled 1.5.4 driver opens storage 69 | `IO Error: Trying to read a database file with version number 999, but we can only read versions between 64 and 68.` |
| Second process opens the file | `IO Error: Could not set lock on file "...": Conflicting lock is held in ... (PID ...)` |
| Duplicate merge source | `MERGE INTO command cannot affect the same target row more than once.` |
| External parent directory missing | `IO Error: Cannot open file "out/ext.parquet": No such file or directory` |
| v1 external key | `UnusedConfigKey (dbt1060)` |
| Python model | `Internal Error: Python models are not supported for duckdb adapter` |
| Materialized view | `get_create_materialized_view_as_sql has not been implemented for this adapter` |
| `--compute inline` | `` `--compute inline` is not supported for adapter 'duckdb'. Falling back to `--compute remote`. `` |
| Unknown incremental strategy | `No macro named 'get_incremental_<name>_sql'` on the second run |

DuckDB 1.5.5 and earlier print the raw header field `999` for a natively created 2.0 file. DuckDB 1.5.6 prints `69`. The storage version is 69 in both cases; read `tags['storage_version']`, not the error number.

## v1-to-v2 checklist

1. Record the v1 command output, adapter version, DuckDB build, and storage tag.
2. Install dbt v2 in a fresh environment. Do not install `dbt-duckdb` beside it; that pulls dbt-core 1.x and can overwrite the `dbt` console script.
3. Run `dbc install duckdb` when the project uses extensions or a 2.0 file.
4. Copy the profile. Set `schema`, remove `plugins` and `filesystems`, and replace v1 external configs.
5. Run `dbt debug`, then `dbt show --inline "select version()"`.
6. Convert the storage file before dbt writes to it when an old reader must open the result.
7. Run `dbt build`. Keep the v1 environment until models and tests pass.
8. Recheck Python models, materialized views, external partitioning, and adapter-specific macros.

## References

- https://docs.getdbt.com/docs/local/connect-data-platform/duckdb-setup
- https://docs.getdbt.com/reference/resource-configs/duckdb-configs
- https://docs.getdbt.com/docs/build/iceberg/catalogs-yml
- https://docs.getdbt.com/docs/dbt-versions/dbt-upgrade/upgrading-to-v2
- https://github.com/duckdb/dbt-duckdb
