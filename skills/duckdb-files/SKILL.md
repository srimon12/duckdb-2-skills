---
name: duckdb-files
description: >
  Read, preview, convert, and batch-ingest data files with DuckDB 2.0. Covers
  CSV, Parquet, JSON, Avro, Excel, SQLite, HTTP, object storage, rejected rows,
  partitioned writes, secrets, and asynchronous I/O. Use when the user points
  at a data file or an s3://, https://, gs://, or az:// URL, asks for parquet,
  csv, json, or xlsx output, or wants a repeatable batch load.
---

# Data files

Run DuckDB with the `duckdb` skill. For Shapefile and GeoPackage, see `duckdb-spatial`. GeoJSON reads natively through the JSON reader. To attach or manage native database files, see `duckdb-session`. For Lakehouse catalogs, see `duckdb-lakehouse`. For `VARIANT` columns, see `duckdb-variant`.

Do not build one macro that mentions every reader. A missing extension then fails the whole statement. Pick the reader from the path.

## Reader

| Path | Statement |
| --- | --- |
| `.csv`, `.tsv` | `FROM read_csv('path')`; `.tsv` sniffs the tab |
| `.tab`, `.txt` | `FROM read_csv('path')`; bare paths do not dispatch |
| `.json` | `FROM read_json('path')`; array or NDJSON, auto-detected |
| `.jsonl`, `.ndjson` | `FROM read_json('path', format = 'newline_delimited')` |
| `.parquet`, `.pq`, or a directory of Parquet | `FROM read_parquet('path')`; `.parquet` bare-reads, `.pq` needs explicit function |
| `.avro` | `FROM read_avro('path')`; autoloads |
| `.xlsx` | `FROM read_xlsx('path')`; autoloads |
| `.sqlite`, `.sqlite3` | `ATTACH 'path' AS s (TYPE sqlite);` then `SHOW TABLES` |
| `.db`, `.duckdb` | `FROM read_duckdb('path', table_name = '...')` or `FROM 'path'`; a bare read works only for a single-table file. `schema_name` selects a schema in a multi-schema file. `.db` is DuckDB, not SQLite |
| `.geojson`, `.geojsonl` | `FROM read_json('path', geojson := true)` or `FROM 'path'` |
| `.shp`, `.gpkg`, `.fgb` | `LOAD spatial;` then `ST_Read('path')` |
| anything else | `DESCRIBE FROM 'path'` and switch to the reader the error names |

`read_json_auto`, `read_csv_auto`, and `parquet_scan` still exist as aliases. Write the short name in new SQL.

A bare filename resolves under the working tree. Skip `.git`.

## Preview

```sql
DESCRIBE FROM read_parquet('path');
FROM read_parquet('path') LIMIT 20;
SELECT count(*) AS n FROM read_parquet('path');
```

On a large remote Parquet file, skip `count(*)` and use metadata:

```sql
SELECT num_rows, file_size_bytes
FROM parquet_file_metadata('path');
```

Do not sum `row_group_num_rows` from `parquet_metadata`: it repeats once per column in a row group, so a 5-row 3-column file reports 15. Use `parquet_file_metadata`, `count(*)`, or `DISTINCT file_name, row_group_id, row_group_num_rows`.

For a directory or bucket, list names and sizes without downloading bodies:

```sql
SELECT filename, size, last_modified
FROM read_blob('s3://bucket/prefix/*')
ORDER BY filename
LIMIT 50;
```

## Convert

```sql
COPY (FROM 'input.csv') TO 'output.parquet' (FORMAT parquet);
```

| Extension | Clause |
| --- | --- |
| `.parquet`, `.pq` | `(FORMAT parquet)` |
| `.csv` | `(FORMAT csv, HEADER)` |
| `.tsv` | `(FORMAT csv, HEADER, DELIMITER '\t')` |
| `.json` | `(FORMAT json, ARRAY true)` |
| `.jsonl`, `.ndjson` | `(FORMAT json, ARRAY false)` |
| `.xlsx` | `(FORMAT xlsx)` after `INSTALL excel; LOAD excel;` |

`PARTITION_BY (col)` writes a partitioned directory of Parquet, CSV, or JSON. Use `OVERWRITE` for a full rebuild, `OVERWRITE_OR_IGNORE` only when the partition set is unchanged, and `APPEND` to keep old files. `FILENAME_PATTERN` names the files, `PER_THREAD_OUTPUT` parallelizes writes, and `FILE_SIZE_BYTES` caps each file. `ORDER_BY (...)` sorts rows inside each partition. `RETURN_FILES` returns `Count` and `Files`.

The format matrix, the CSV/JSON/Parquet parameters, and the secrets table are in [references/formats.md](references/formats.md).

## Ingest a batch

For a repeatable load, read [references/ingest.md](references/ingest.md). It owns the contract from inspect to typed rows, quarantine, partitioned write, and row-count proof. A one-file conversion stays in `Convert` above.

The short form is: read raw, cast explicitly, split good and bad, write `good` to partitioned Parquet, persist `bad` and any parser rejects, and prove `input = good + bad + distinct reject lines`. Do not use `ignore_errors` as a repair.

## Remote files

```sql
LOAD httpfs;
```

| Store | Secret |
| --- | --- |
| S3 with an existing AWS profile | `CREATE OR REPLACE SECRET (TYPE s3, PROVIDER credential_chain);` |
| S3 with keys | `CREATE OR REPLACE SECRET (TYPE s3, PROVIDER config, KEY_ID '...', SECRET '...', REGION 'us-east-1');` |
| Public bucket that only needs a region | `CREATE OR REPLACE SECRET (TYPE s3, PROVIDER config, REGION 'us-west-2');` |
| Cloudflare R2 | `CREATE OR REPLACE SECRET (TYPE r2, ACCOUNT_ID '...', KEY_ID '...', SECRET '...');` and use `r2://`; the endpoint is derived |
| GCS | `CREATE OR REPLACE SECRET (TYPE gcs, KEY_ID '...', SECRET '...');` HMAC keys, and `gs://` or `gcs://` |
| Azure | `CREATE OR REPLACE SECRET (TYPE azure, PROVIDER config, ACCOUNT_NAME '...');` for a public container; a service principal uses `PROVIDER service_principal` |
| HTTPS | `LOAD httpfs;` and no secret unless the server requires one |

`credential_chain` autoloads the `aws` extension and fails closed when no profile exists. A public bucket needs no credential secret. A region pin is not a credential.

Do not put access keys in the URL. DuckDB 2.0 treats `?s3_access_key_id=...` as part of the object key. The old behavior is `SET s3_enable_deprecated_url_parameters = true` after `LOAD httpfs`.

Async I/O is already on for Parquet and for uncompressed, seekable, UTF-8 CSV, including files read through DuckLake. JSON and native database files stay synchronous. Defaults are `async_threads` = four times `threads` (capped at 256), `read_ahead_depth = -1`, `http_retries = 3`, and `http_retry_backoff = 4.0`. Leave them alone unless the user asks to tune a fast network. The full option list is in [references/formats.md](references/formats.md).

## Sandbox a local file

On a local file the user did not ask to join with the network, install and load every extension first, then restrict the process:

```sql
SET allowed_paths = ['/absolute/file.csv'];
SET enable_external_access = false;
SET allow_persistent_secrets = false;
SET lock_configuration = true;
```

`allowed_paths` must come before `enable_external_access = false`; afterward the setting is rejected. The same setting blocks remote reads too. Skip the local allow-list for `s3://`, `gs://`, `gcs://`, `r2://`, `az://`, `azure://`, `abfs://`, `abfss://`, `http://`, and `https://`, but do not assume remote is unrestricted after `enable_external_access=false`.

`-safe` is not a substitute. It blocks all external file access, including the file the user named, while still opening the database path on the command line. The full safety matrix and the `-safe` ordering rule are in `duckdb`.

## Verify

```bash
tmp=$(mktemp -d)
printf 'id,name\n1,Ada\n2,Grace\n' > "$tmp/in.csv"
duckdb -agent -c "COPY (FROM '$tmp/in.csv') TO '$tmp/out.parquet' (FORMAT parquet); DESCRIBE FROM '$tmp/out.parquet'; SELECT count(*) FROM '$tmp/out.parquet';"
rm -rf "$tmp"
```

The describe must show `id` and `name`. The count must be `2`.

## References

- [Data import](https://duckdb.org/docs/2.0/data/overview.html) owns the format overview.
- [CSV](https://duckdb.org/docs/2.0/data/csv/overview.html) owns the CSV parameters.
- [JSON](https://duckdb.org/docs/2.0/data/json/loading_json.html) owns the JSON formats and parameters.
- [Parquet](https://duckdb.org/docs/2.0/data/parquet/overview.html) owns the Parquet reader and writer.
- [COPY](https://duckdb.org/docs/2.0/sql/statements/copy.html) owns the copy options.
- [Secrets manager](https://duckdb.org/docs/2.0/configuration/secrets_manager.html) owns secret creation and scope.
- [I/O](https://duckdb.org/docs/2.0/data/io.html) owns asynchronous reads and tuning.
- Reader dispatch replaces the `read_any` macro in https://github.com/duckdb/duckdb-skills (MIT). The keyless `TYPE s3, PROVIDER config, REGION` secret was accepted by DuckDB 2.0.0.
