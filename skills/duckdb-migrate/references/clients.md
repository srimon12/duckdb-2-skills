# Client compatibility reference

Read this when a BI tool, driver, dbt, Ibis, or MCP client must open a DuckDB file created by 2.0.

## Storage boundary

| Reader | New file pin | Storage |
| --- | --- | --- |
| DuckDB 2.0 | default or `latest` | 69 |
| DuckDB 1.5.6 | `-storage-version v1.5.6` | 68 |
| DuckDB 1.4 | `-storage-version v1.4.0` | 67 |

A 1.5 reader cannot open a 69 file. A 1.4 reader cannot open a 68 file. Check the bundled DuckDB build, not the Python package version.

## BI clients

| Client | Build checked | DuckDB | 2.0 file |
| --- | --- | --- | --- |
| Metabase driver | 1.5.6.0, 2026-10-20 | 1.5.6 | No |
| Grafana plugin | 0.4.6, 2026-10-22 | 1.5.6 | No |
| Superset | master, 2026-10 | `duckdb>=1.5.6,<2` | No |

These clients report the storage error:

```text
IO Error: Trying to read a database file with version number 69, but we can only read versions between 64 and 68.
```

Upgrade the client to a 2.0 build, or make a 1.5-compatible copy. Do not point a 1.5 client at a live 2.0 file.

```sql
ATTACH 'v2.duckdb' AS v2 (READ_ONLY);
ATTACH 'v15.duckdb' AS v15 (STORAGE_VERSION 'v1.5.6');
COPY FROM DATABASE v2 TO v15;
```

A BI reader and a local writer cannot share one file across processes. Point the BI tool at a copy, a read-only replica, or a DuckLake/Quack endpoint.

## dbt

dbt v2 (`dbt` package) has a built-in DuckDB adapter. Its bundled driver cannot load extensions. Install the system driver with `dbc install duckdb` before using `httpfs`, `parquet`, `spatial`, or `ducklake`.

`dbt-duckdb` is the v1 adapter. It does not become dbt v2.

The dbt v2 driver is pinned. Installing `duckdb==2.0.0` with `pip` does not change it. Check `dbt show --inline "select version()"`. If it is not 2.0, install a 2.0 system driver or write the target file with `STORAGE_VERSION 'v1.5.6'`.

Read `duckdb-dbt` for the profile, catalogs, and migration steps.

## Ibis

Ibis 12.0.0 and earlier do not support DuckDB 2.0. The documented install pins below 2.0:

```bash
pip install 'ibis-framework[duckdb]' 'duckdb<2'
```

Do not tell a user to use Ibis 12 with a 2.0 file.

## MCP

`mcp-server-motherduck` 1.1.0 requires `duckdb==1.5.6`, so its local server cannot open a 69 file. For a local 2.0 file, use the `duckdb_mcp` extension on the 2.0 binary, or down-copy the file.

Read `duckdb` for the MCP setup.

## Version check

Run the version query inside the client, not in a separate shell:

```sql
SELECT version();
SELECT database_name, tags['storage_version'] FROM duckdb_databases();
```

A client that cannot run the first query is not a DuckDB 2.0 client. A client that reports `v2.0.0+` can open the file; a client that reports `v1.5.0+` cannot.

## References

- https://duckdb.org/docs/2.0/internals/storage.html
- https://github.com/motherduckdb/metabase_duckdb_driver/releases/tag/1.5.6.0
- https://github.com/motherduckdb/grafana-duckdb-datasource/releases/tag/v0.4.6
- https://superset.apache.org/user-docs/databases/supported/duckdb/
- https://docs.getdbt.com/docs/local/connect-data-platform/duckdb-setup
- https://duckdb.org/docs/2.0/guides/python/ibis.html
- https://pypi.org/project/mcp-server-motherduck/1.1.0/
