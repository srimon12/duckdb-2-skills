---
name: duckdb-dbt
description: >
  Run dbt v2 with its built-in DuckDB adapter. Covers the dbt and dbt-duckdb
  split, driver and extension loading, storage compatibility, profiles,
  catalogs, incremental models, orchestration, and v1-to-v2 migration. Use
  when the user mentions dbt, dbt-duckdb, a dbt profile, or a dbt project on
  DuckDB.
---

# dbt on DuckDB

Two products share the name. `dbt-duckdb` is the v1 Python adapter. dbt v2 ships its own DuckDB adapter in the `dbt` package and does not use `dbt-duckdb`.

Check the package before writing a profile:

```bash
dbt --version
```

A v2 binary prints a 2.x version and a built-in DuckDB adapter. A v1 project prints `dbt-core` 1.x and a separate `dbt-duckdb` plugin.

## Contract

```text
Inputs:      dbt project, profiles.yml, DuckDB build, target storage
Outputs:     models, tests, target/ artifacts, warehouse file or lake
Invariants:  same dbt version, same driver, same DuckDB build, same storage
Failure:     a driver that cannot load the extension or open storage 69
Proof:       dbt debug connects; dbt build and dbt test pass; version query matches
```

## Install dbt v2

```bash
python -m pip install 'dbt>=2,<3'
dbc install duckdb
dbt --version
```

`dbt-duckdb` is still the v1 adapter. Installing it does not upgrade a project to dbt v2.

dbt v2 bundles a DuckDB driver, and that driver cannot load extensions. Install the system DuckDB driver with `dbc install duckdb` before a profile asks for `httpfs`, `parquet`, `spatial`, or `ducklake`.

The bundled driver is pinned. Installing `duckdb` with `pip` does not change the driver dbt uses. Check the build from inside dbt:

```bash
dbt show --inline "select version()"
```

The result must be the DuckDB build you intend to use. If it is not 2.0, either install a 2.0 system driver with `dbc install duckdb` or write the target file with `STORAGE_VERSION 'v1.5.6'`. Storage 69 is 2.0-only.

## Profile

```yaml
analytics:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: ./warehouse.duckdb
      extensions:
        - httpfs
        - parquet
```

`extensions` is read by the adapter after it loads a driver that supports extensions. A v1 profile uses the `dbt-duckdb` plugin name and the same `type: duckdb`; do not mix the plugin and the v2 binary.

```bash
dbt debug
dbt build
dbt test
```

`dbt debug` proves the profile and driver. `dbt build` runs models and tests. A successful build is not a storage proof; run the version query and check `tags['storage_version']` on the warehouse file.

## Catalogs

dbt v2 uses `catalogs.yml` for DuckLake and Iceberg, with `flags: use_catalogs_v2: true`. The v1 adapter uses an `attach:` block in the profile instead.

Keep catalog semantics in `duckdb-lakehouse`. This skill owns the dbt wiring only:

```yaml
flags:
  use_catalogs_v2: true
```

A local `.duckdb` catalog is one read-write process. A shared dbt deployment needs Postgres or another multi-user catalog, or every process must be `READ_ONLY`. See `duckdb-lakehouse` before choosing.

## Incremental models

DuckDB supports `merge`, `delete+insert`, and `append` incremental strategies. Use `merge` only when the unique key is stable and the source is deduplicated. A target row that matches two source rows is an error for `MERGE`; an `UPDATE ... FROM` picks one arbitrary row.

A dbt incremental model is not a trigger-maintained materialized view. Rebuilding is the default, and a full refresh is the proof. For trigger-based summaries, read `duckdb-sql`.

## Orchestration

A local `.duckdb` file lives on one worker. A retry or the next task can land on a different worker and see an empty path. Persist the warehouse to S3/Parquet or DuckLake, or run the whole dbt job on one worker with a mounted volume.

Airflow, Dagster, and cron should run `dbt build`, not a hand-written sequence of `dbt run` and `dbt test`. One writer per file. Do not point two concurrent jobs at the same local file.

## Move from v1

1. Record the current `dbt --version`, `dbt-duckdb` version, and DuckDB build.
2. Install dbt v2 (`dbt` package) beside the project. Do not remove the old environment yet.
3. Run `dbc install duckdb` if the project uses any extension.
4. Copy `profiles.yml` to the v2 profile. Keep the old file for rollback.
5. Run `dbt debug`, `dbt show --inline "select version()"`, then `dbt build`.
6. Check storage compatibility before pointing v2 at a production file.
7. Keep the v1 environment until one full build and test pass.

Do not assume parity. dbt v2's DuckDB adapter still has gaps around Python models, seeds, external materialization, and custom table functions. Read the adapter release notes before deleting the v1 environment.

## Stop rules

- Do not call a `dbt-duckdb` install a dbt v2 install.
- Do not ask the bundled v2 driver to load extensions; install the system driver.
- Do not assume `pip install duckdb==2.0.0` changes the driver dbt uses.
- Do not open a storage-69 file with a 1.x driver.
- Do not run two writers against one local file.
- Do not put a local warehouse on an ephemeral worker.
- Do not use `merge` when the source has duplicate keys.

## Verify

```bash
dbt --version
dbt debug
dbt show --inline "select version()"
dbt build
```

`dbt --version` must show 2.x for the v2 path. `dbt debug` must connect. The version query must show the intended DuckDB build. `dbt build` must finish with zero failed models and tests.

## References

- [dbt DuckDB setup](https://docs.getdbt.com/docs/local/connect-data-platform/duckdb-setup) owns the profile and `extensions` field.
- [dbt v2 upgrade](https://docs.getdbt.com/docs/dbt-versions/dbt-upgrade/upgrading-to-v2) owns the package split.
- [dbt v2 release](https://github.com/dbt-labs/dbt/releases/tag/v2.0.0) owns the version boundary.
- [dbt-duckdb](https://github.com/duckdb/dbt-duckdb) owns the v1 adapter.
- [DuckDB dbt announcement](https://duckdb.org/2026/09/22/dbt-fusion.html) owns the built-in adapter and driver caveat.
- [dbc](https://docs.columnar.tech/dbc/) owns the driver install.
- Read `duckdb-lakehouse` for catalog choice and `duckdb-migrate` for storage pins.
