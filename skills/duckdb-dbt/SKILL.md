---
name: duckdb-dbt
description: >
  Run dbt v2 on DuckDB with the built-in adapter. Covers the v1 package split,
  driver and storage proof, profiles, extensions, materializations, incremental
  strategies, hooks, concurrency, catalogs, and migration. Use when the user
  mentions dbt, dbt-duckdb, a dbt profile, or a dbt project on DuckDB.
---

# dbt on DuckDB

Two products share the name. `dbt-duckdb` is the v1 Python adapter. dbt v2 ships its own DuckDB adapter inside the `dbt` package and does not use `dbt-duckdb`.

Check the package before writing a profile:

```bash
dbt --version
```

dbt v2 prints one line, for example `dbt 2.0.9`, with no `Core` or `Plugins` block. dbt v1 prints `dbt-core` and a separate `dbt-duckdb` plugin. `dbt debug` names the adapter as `duckdb (remote)`.

## Contract

```text
Inputs:      dbt project, profiles.yml, DuckDB driver, target storage
Outputs:     models, tests, target artifacts, warehouse file or lake
Invariants:  dbt v2 binary, system driver build, storage version, one writer
Failure:     a driver that cannot open the file, a missing extension, a second writer
Proof:       version query, storage tag, dbt build, lock check
```

## Prove the stack

Run these before changing a project:

1. `dbt --version` must print a 2.x line. A v1 install prints `Core` and `Plugins`.
2. `dbt debug` must pass and report `duckdb (remote)`.
3. `dbt show --inline "select version()"` must return the DuckDB build you intend to use.
4. If the build is not 2.0, install the system driver with `dbc install duckdb`.
5. Check the file header with the DuckDB CLI, not with dbt.

dbt v2 downloads a bundled ADBC driver on first use. At dbt 2.0.9 that driver reports DuckDB 1.5.4, writes a `v1.0.0+` file, and cannot read storage 69:

```text
IO Error: Trying to read a database file with version number 999, but we can only read versions between 64 and 68.
```

A system driver installed by `dbc` wins over the bundled one. After `dbc install duckdb`, the same command returns `v2.0.0`, opens storage 69, and `tags['storage_version']` is `v2.0.0+`.

The vendor docs say the bundled driver cannot load extensions. At dbt 2.0.9 it loaded `httpfs`, `spatial`, `fts`, `vss`, and `ducklake` in a probe. Do not rely on that. Install the system driver for 2.0-only features and prove the engine with the version query.

`pip install duckdb==2.0.0` does not change the driver dbt uses. `STORAGE_VERSION` is an `ATTACH` option, not a dbt profile key. A dbt v2 profile cannot create a pre-2.0 file by setting `storage_compatibility_version`.

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
      extensions:
        - httpfs
        - parquet
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

Set `schema` explicitly. Without it a model lands in `main`, but `this` inside a hook renders `<database>.public.<model>` at dbt 2.0.9. A post-hook that indexes a table will target the wrong schema.

`settings` applies DuckDB configuration after the database is attached. `attach` accepts `duckdb`, `sqlite`, and `postgres` paths and uses the basename as the alias. `secrets` creates `__dbt_secret_N` entries in `duckdb_secrets()`.

`plugins` and `filesystems` are v1 adapter keys. `external_root` applies only when an external model omits `location`. See [references/project.md](references/project.md) for the full profile table.

## Models

| Materialization | dbt v2 on DuckDB | Use |
| --- | --- | --- |
| `table`, `view`, `incremental`, `ephemeral` | Supported | Normal models |
| `seed`, `snapshot` | Supported | Small fixtures and history |
| `external` | Supported | Parquet or CSV outside the warehouse |
| `materialized_view` | Not implemented | Use `table` and a refresh job |
| Python model | Not supported | Keep it in `duckdb-python` |

An external model writes one file at `location`. The parent directory must exist, and `location` cannot be a directory. `partition_by` is not applied to external models; DuckLake uses `partitioned_by` on `table` and `incremental` models.

`dbt build` runs seeds, models, and tests as one unit. A successful `dbt run` is not a test. `--store-failures` writes failed and passed test rows to `main_dbt_test__audit.<test_name>`. Model contracts work when every column has a `data_type`.

## Incremental models

| Strategy | Required | Rerun behavior | Failure |
| --- | --- | --- | --- |
| `append` | None | Inserts every source row | Duplicates on every run |
| `delete+insert` | `unique_key` | Deletes matching keys, inserts source | Without a key it silently inserts |
| `merge` | `unique_key` | `MERGE ... UPDATE BY NAME INSERT BY NAME` | Without a key it emits `ON (FALSE)` and appends |
| `microbatch` | `event_time`, `begin`, `batch_size` | Filters inputs by event-time window | Warns when no ref has `event_time` |

A `merge` target row matched by two source rows aborts:

```text
MERGE INTO command cannot affect the same target row more than once.
```

Deduplicate the source or use `delete+insert`. `--full-refresh` rebuilds the target and is the proof that the model is reproducible. A dbt incremental model is not a trigger-maintained view; read `duckdb-sql` for that pattern.

## Hooks and search indexes

A dbt table rebuild drops FTS and HNSW indexes on the model. Recreate the index in a post-hook after the model lands:

```sql
{{ config(
    materialized='table',
    post_hook="PRAGMA create_fts_index('" ~ this ~ "', 'id', 'body', overwrite=1)"
) }}
```

An incremental update leaves an FTS index stale because incremental FTS triggers cover `INSERT` and `DELETE`, not `UPDATE`. Rebuild the index after the model, or write with delete plus insert. Read `duckdb-search` for index freshness and metric matching.

## Orchestration

A local `.duckdb` file lives on one worker. A retry or the next task can land on a different worker and see an empty path. Persist the warehouse to S3, Parquet, or DuckLake, or pin the job to one worker with a mounted volume.

Threads inside one dbt process can write one file. Two dbt processes cannot:

```text
IO Error: Could not set lock on file "...": Conflicting lock is held in ... (PID ...)
```

Run `dbt build` from Airflow, Dagster, or cron. Do not append `dbt test` by hand, and do not point two concurrent jobs at the same local file.

## Catalogs

dbt v2 uses `catalogs.yml` with the new spec by default. `flags: use_catalogs_v2: true` is redundant in v2; set it to `false` only for the old spec. A model with `catalog_name` needs the catalog in `catalogs.yml`.

A DuckLake catalog can also be attached through the profile with `path: "ducklake:my_lake.ddb"`. A local `.duckdb` catalog is one writer. A shared deployment needs PostgreSQL or every process must be `READ_ONLY`. Read `duckdb-lakehouse` before choosing.

## Move from v1

1. Record `dbt --version`, the `dbt-duckdb` version, the active DuckDB build, and the file storage tag.
2. Install dbt v2 beside the project. Do not remove the v1 environment yet.
3. Run `dbc install duckdb` if the project uses extensions or a 2.0 file.
4. Copy `profiles.yml`. Set `schema` explicitly and remove `plugins`, `filesystems`, and v1 external keys.
5. Run `dbt debug`, `dbt show --inline "select version()"`, then `dbt build`.
6. Check storage before pointing v2 at a production file. If an old reader must open the result, convert with the CLI `ATTACH ... (STORAGE_VERSION 'v1.5.6')` and `COPY FROM DATABASE`; dbt does not expose that as a profile setting.
7. Keep v1 until one full build and test pass.

Do not assume parity. Python models and materialized views are not implemented. External models write a single file and ignore partitioning. Seeds and snapshots work.

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

The version query must return the intended DuckDB build. `dbt debug` must connect. `dbt build` must finish with zero failed models and tests. Then check the file:

```bash
duckdb -no-agent -json warehouse.duckdb \
  -c "SELECT tags['storage_version'] AS v FROM duckdb_databases() WHERE database_name = current_database();"
```

The tag must match the readers that will open the file: `v2.0.0+` for DuckDB 2.0, `v1.5.0+` for a 1.5 reader.

## References

- [dbt DuckDB setup](https://docs.getdbt.com/docs/local/connect-data-platform/duckdb-setup) owns the profile and `extensions` field.
- [dbt v2 upgrade](https://docs.getdbt.com/docs/dbt-versions/dbt-upgrade/upgrading-to-v2) owns the package split.
- [dbt v2 release](https://github.com/dbt-labs/dbt/releases/tag/v2.0.0) owns the version boundary.
- [dbt-duckdb](https://github.com/duckdb/dbt-duckdb) owns the v1 adapter.
- [DuckDB dbt announcement](https://duckdb.org/2026/09/22/dbt-fusion.html) owns the built-in adapter and driver caveat.
- [dbc](https://docs.columnar.tech/dbc/) owns the driver install.
- [references/project.md](references/project.md) has the profile keys, materialization matrix, exact errors, and migration checklist.
- Read `duckdb-lakehouse` for catalog choice, `duckdb-search` for index freshness, and `duckdb-migrate` for storage pins.
