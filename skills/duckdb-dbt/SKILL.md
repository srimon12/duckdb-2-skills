---
name: duckdb-dbt
description: >
  Run dbt v2 on DuckDB with the built-in adapter. Covers the v1 package split,
  driver and storage proof, profiles, extensions, materializations, incremental
  strategies, hooks, concurrency, catalogs, and migration. Use when the user
  mentions dbt, dbt-duckdb, a dbt profile, or a dbt project on DuckDB.
---

# dbt on DuckDB

Two products share the name. `dbt-duckdb` is the v1 Python adapter. dbt v2 packages its own built-in DuckDB adapter inside `dbt` and does not use `dbt-duckdb`.

Before configuring a project, verify the installed adapter:

```bash
dbt --version
```

If dbt v2 is installed, it outputs a single line (such as `dbt 2.0.9`) with no `Core` or `Plugins` block. If `dbt-core` and `dbt-duckdb` appear, the environment runs v1. When connected, `dbt debug` reports the adapter as `duckdb (remote)`.

## Contract

```text
Inputs:      dbt project, profiles.yml, DuckDB driver, target storage
Outputs:     models, tests, target artifacts, warehouse file or lake
Invariants:  dbt v2 binary, system driver build, storage version, one writer
Failure:     a driver that cannot open the file, a missing extension, a second writer
Proof:       version query, storage tag, dbt build, lock check
```

## Prove the stack

Before modifying project code, prove the binary and driver stack:

1. Run `dbt --version`; the output must be a single 2.x line.
2. Run `dbt debug`; the output must report `duckdb (remote)`.
3. Run `dbt show --inline "select version()"` to verify the engine version.
4. If the reported engine is not 2.0, run `dbc install duckdb` to install the system driver.
5. Inspect `tags['storage_version']` via DuckDB CLI, never via dbt.

On first invocation, dbt v2 downloads a bundled ADBC driver. At dbt 2.0.9, this bundled driver reports DuckDB 1.5.4, writes storage 64 (`v1.0.0+`), and fails when reading storage 69:

```text
IO Error: Trying to read a database file with version number 999, but we can only read versions between 64 and 68.
```

The vendor docs say the bundled driver cannot load extensions. At dbt 2.0.9 it loaded `httpfs`, `spatial`, `fts`, `vss`, and `ducklake` in a probe. Do not rely on that; install the system driver for 2.0-only features.

When reading a 2.0 file, DuckDB 1.5.5 prints raw header number `999`; 1.5.6 prints `69`. Do not interpret `999` as the storage version. When `dbc install duckdb` installs the system driver, dbt returns `v2.0.0`, opens storage 69, and reports `tags['storage_version']` as `v2.0.0+`. Always verify the active driver with the version query. Running `pip install duckdb==2.0.0` does not change the driver dbt uses. `STORAGE_VERSION` is an `ATTACH` option, not a dbt profile key; setting `storage_compatibility_version` in a dbt profile cannot create a pre-2.0 file.

## Profile

```yaml
analytics:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: ./warehouse.duckdb
      schema: main
      threads: 1
      extensions: [httpfs, parquet]
      settings:
        memory_limit: 4GB
      attach:
        - path: ./other.sqlite
          type: sqlite
          read_only: true
      secrets:
        - type: s3
          provider: credential_chain
```

In `profiles.yml`, set `schema: main` explicitly. Without explicit `schema`, hook compilation renders `this` as `<database>.public.<model>` while the model builds in `main`.

For runtime settings, `settings` applies DuckDB configuration after attachment. For external data, `attach` mounts `duckdb`, `sqlite`, or `postgres` databases using the filename basename as the alias. For cloud authentication, `secrets` configures `__dbt_secret_N` entries in `duckdb_secrets()`. When migrating from v1, remove `plugins` and `filesystems`. When an `external` model omits `location`, `external_root` defines its directory prefix. See [references/project.md](references/project.md) for full profile options.

## Models

| Materialization | Status | Notes |
| --- | --- | --- |
| `table`, `view`, `incremental`, `ephemeral` | Supported | Standard SQL models |
| `seed`, `snapshot` | Supported | CSV fixtures and slowly changing dimensions |
| `external` | Supported | Single Parquet/CSV file at `location` (no `partition_by`) |
| `materialized_view` | Unimplemented | Replaced by `table` plus scheduled refresh |
| Python model | Unsupported | Delegated to `duckdb-python` |

When writing external models, `location` must name a single target file, not a directory, and its parent directory must exist. `partition_by` is not supported on external models; use `partitioned_by` on DuckLake `table` or `incremental` models. When executing transformations, run `dbt build` rather than `dbt run`; `dbt build` executes seeds, models, and tests as one unit. To inspect test failures, pass `--store-failures` to write audit rows to `main_dbt_test__audit.<test_name>`. If enforcing model contracts, define explicit `data_type` on every column in YAML.

## Incremental models

| Strategy | Required | Rerun behavior | Failure mode |
| --- | --- | --- | --- |
| `append` | None | Inserts all source rows | Duplicates rows on rerun |
| `delete+insert` | `unique_key` | Deletes matching keys, inserts source | Silently appends if `unique_key` is omitted |
| `merge` | `unique_key` | `MERGE ... UPDATE BY NAME INSERT BY NAME` | Emits `ON (FALSE)` and appends without key |
| `microbatch` | `event_time`, `begin`, `batch_size` | Filters inputs by event window | Warns if upstream ref lacks `event_time` |

If duplicate source keys match a single target row during `merge`, the query aborts:

```text
MERGE INTO command cannot affect the same target row more than once.
```

Deduplicate incoming rows prior to merge, or select `delete+insert`. When verifying model reproducibility, run `dbt build --full-refresh` to rebuild the target table from scratch. An incremental model is not a trigger-maintained view; see `duckdb-sql` for dynamic materializations.

## Hooks and search indexes

Because a dbt `table` rebuild drops associated FTS and HNSW indexes, recreate them in a `post_hook`:

```sql
{{ config(
    materialized='table',
    post_hook="PRAGMA create_fts_index('" ~ this ~ "', 'id', 'body', overwrite=1)"
) }}
```

When updating incremental models, note that DuckDB FTS triggers capture `INSERT` and `DELETE`, but not `UPDATE`. If records update in place, rebuild the search index in a post-hook or execute `delete+insert`. See `duckdb-search` for index freshness and vector metric matching.

## Orchestration

If running on distributed workers, pin the pipeline to a single local worker with a persistent volume, or persist storage to S3, Parquet, or DuckLake; a new node will see an empty filesystem.

While multiple threads within one dbt process safely write to one DuckDB file, multiple concurrent processes cannot:

```text
IO Error: Could not set lock on file "...": Conflicting lock is held in ... (PID ...)
```

Orchestrate via Airflow, Dagster, or cron using a single `dbt build` invocation. Never run concurrent writers against the same database file, and do not separate `dbt run` and `dbt test`.

## Catalogs

In dbt v2, `catalogs.yml` with the v2 specification is active by default; `flags: use_catalogs_v2: true` is redundant and only set to `false` to revert to legacy catalogs. When a model specifies `catalog_name`, declare that catalog in `catalogs.yml`.

To attach a DuckLake catalog, configure the profile with `path: "ducklake:my_lake.ddb"`. Because a local `.duckdb` catalog allows only one writer, shared multi-writer deployments require PostgreSQL or `READ_ONLY` processes. Consult `duckdb-lakehouse` before architectural selection.

## Move from v1

1. Record `dbt --version`, `dbt-duckdb` version, DuckDB engine build, and database storage tag.
2. Install dbt v2 in an isolated environment beside the existing project without removing v1.
3. Run `dbc install duckdb` if the project uses DuckDB 2.0 files or extensions.
4. Copy `profiles.yml`, set `schema: main` explicitly, and remove `plugins`, `filesystems`, and v1 external keys.
5. Execute `dbt debug`, `dbt show --inline "select version()"`, and `dbt build`.
6. If older readers must open output files, pin storage using DuckDB CLI `ATTACH ... (STORAGE_VERSION 'v1.5.6')` and `COPY FROM DATABASE`; dbt profiles expose no storage version flag.
7. Keep the v1 environment until a complete `dbt build` passes models and tests.

Verify feature parity: Python models and materialized views are not implemented; external models write a single file and ignore `partition_by`. Seeds and snapshots remain fully supported.

## Stop rules

- Do not call a `dbt-duckdb` install a dbt v2 install.
- Do not read `dbt --version` as an adapter list; v2 prints one line.
- Do not point a 1.5.4 bundled driver at a storage-69 file.
- Do not claim a profile key controls `STORAGE_VERSION`; there is none.
- Do not use `merge` or `delete+insert` without `unique_key`.
- Do not run two writers against one local file.
- Do not put a local warehouse on an ephemeral worker.
- Do not rebuild a model with a search index without rebuilding the index.
- Do not use `--compute inline` or `sidecar` with DuckDB; it falls back with a warning and breaks ad-hoc `duckdb_*` queries.

## Verify

```bash
dbt --version
dbt debug
dbt show --inline "select version()"
dbt build
```

Confirm that the version query returns the intended DuckDB build, `dbt debug` connects, and `dbt build` finishes with zero failed models and tests. Then verify file storage:

```bash
duckdb -no-agent -json warehouse.duckdb \
  -c "SELECT tags['storage_version'] AS v FROM duckdb_databases() WHERE database_name = current_database();"
```

The tag must match the readers that open the file: `v2.0.0+` for DuckDB 2.0, or `v1.5.0+` for a file pinned to a 1.5.6 reader.

## References

- [dbt DuckDB setup](https://docs.getdbt.com/docs/local/connect-data-platform/duckdb-setup) owns the profile and `extensions` field.
- [dbt v2 upgrade](https://docs.getdbt.com/docs/dbt-versions/dbt-upgrade/upgrading-to-v2) owns the package split.
- [dbt v2 release](https://github.com/dbt-labs/dbt/releases/tag/v2.0.0) owns the version boundary.
- [dbt-duckdb](https://github.com/duckdb/dbt-duckdb) owns the v1 adapter.
- [DuckDB dbt announcement](https://duckdb.org/2026/09/22/dbt-fusion.html) owns the built-in adapter and driver caveat.
- [dbc](https://docs.columnar.tech/dbc/) owns the driver install.
- [references/project.md](references/project.md) has profile keys, materialization matrices, exact error strings, and migration details.
- Read `duckdb-lakehouse` for catalog selection, `duckdb-search` for index freshness, and `duckdb-migrate` for storage pins.
