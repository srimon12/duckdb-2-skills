---
name: duckdb-files
description: >
  Read or convert local and remote data files with DuckDB 2.0: CSV, Parquet,
  JSON, Avro, Excel, SQLite, HTTP, S3, R2, GCS, Azure. Use when the user
  points at a data file or an object-storage URL, asks for a preview, or wants
  parquet, csv, json, or xlsx output. Use /duckdb-files.
---

# Read and convert files

Run DuckDB with the `duckdb` skill. GeoJSON, Shapefile, and GeoPackage go to `duckdb-spatial`. A `.duckdb` database file goes to `duckdb-session`. Lake catalogs go to `duckdb-lakehouse`.

Do not build one macro that mentions every reader. A missing extension then fails the whole statement. Pick the reader from the path.

## Reader

| Path | Statement |
| --- | --- |
| `.csv`, `.tsv`, `.tab`, `.txt` | `FROM read_csv('path')` |
| `.json`, `.jsonl`, `.ndjson` | `FROM read_json_auto('path')` |
| `.parquet`, `.pq`, or a directory of Parquet | `FROM read_parquet('path')` |
| `.avro` | `INSTALL avro; LOAD avro;` then `FROM read_avro('path')` |
| `.xlsx` | `INSTALL excel; LOAD excel;` then `FROM read_xlsx('path')` |
| `.db`, `.sqlite`, `.sqlite3` | `INSTALL sqlite_scanner; LOAD sqlite_scanner;` then `ATTACH 'path' AS s (TYPE sqlite);` and `SHOW TABLES` |
| anything else | `DESCRIBE FROM 'path'` and switch to the reader the error names |

For a bare filename, resolve it under the working tree before you query it. Skip `.git`.

Preview:

```sql
DESCRIBE FROM read_parquet('path');
SELECT count(*) AS n FROM read_parquet('path');
FROM read_parquet('path') LIMIT 20;
```

Skip the `count(*)` when the file is a large remote Parquet. Use metadata instead:

```sql
SELECT file_name,
       sum(row_group_num_rows) AS rows,
       sum(row_group_compressed_bytes) AS compressed_bytes
FROM parquet_metadata('path')
GROUP BY file_name;
```

On a local file the user did not ask to join with the network, install any extension first, then restrict the process:

```sql
SET allowed_paths = ['/absolute/file'];
SET enable_external_access = false;
SET allow_persistent_secrets = false;
SET lock_configuration = true;
```

Skip that sandbox for `s3://`, `gs://`, `gcs://`, `r2://`, `az://`, `azure://`, `abfs://`, `abfss://`, `http://`, and `https://`.

## Remote paths

```sql
LOAD httpfs;
```

| Store | Secret |
| --- | --- |
| S3, when AWS credentials already exist | `CREATE OR REPLACE SECRET (TYPE s3, PROVIDER credential_chain);` |
| S3 with keys | `CREATE OR REPLACE SECRET (TYPE s3, PROVIDER config, KEY_ID '...', SECRET '...', REGION 'us-east-1');` |
| Public bucket that only needs a region | `CREATE OR REPLACE SECRET (TYPE s3, PROVIDER config, REGION 'us-west-2');` |
| Cloudflare R2 | `CREATE OR REPLACE SECRET (TYPE r2, PROVIDER credential_chain);` or a config secret. Rewrite `r2://bucket/key` to `s3://bucket/key` and set the R2 endpoint. |
| GCS | `CREATE OR REPLACE SECRET (TYPE gcs, KEY_ID '...', SECRET '...');` and use `gs://` |
| Azure | `INSTALL azure; LOAD azure;` then `CREATE OR REPLACE SECRET (TYPE azure, PROVIDER credential_chain, ACCOUNT_NAME '...');` |
| HTTPS | `LOAD httpfs;` and no secret unless the server requires one |

`credential_chain` for S3 autoloads the `aws` extension. Do not put access keys in the URL. DuckDB 2.0 treats `?s3_access_key_id=...` as part of the object key. The old behavior is `SET s3_enable_deprecated_url_parameters = true` after `LOAD httpfs`.

List a prefix without downloading bodies. Select `filename`, `size`, and `last_modified` only:

```sql
SELECT filename, size, last_modified
FROM read_blob('s3://bucket/prefix/*')
ORDER BY filename
LIMIT 50;
```

Async I/O is already on for Parquet and for uncompressed, seekable, UTF-8 CSV, including those files read through DuckLake. JSON and DuckDB database files stay synchronous. Leave `async_threads` and `read_ahead_depth` alone unless the user asks to tune a fast network. The I/O page has the knobs.

## Convert

```sql
COPY (FROM 'input.csv') TO 'output.parquet';
```

| Extension | Copy clause |
| --- | --- |
| `.parquet`, `.pq` | none |
| `.csv` | `(FORMAT csv, HEADER)` |
| `.tsv` | `(FORMAT csv, HEADER, DELIMITER '\t')` |
| `.json` | `(FORMAT json, ARRAY true)` |
| `.jsonl`, `.ndjson` | `(FORMAT json, ARRAY false)` |
| `.xlsx` | `(FORMAT xlsx)` after `INSTALL excel; LOAD excel;` |

`PARTITION_BY (col)` works for Parquet and CSV directory output. `CODEC 'zstd'` is the Parquet compression option when the user asks for zstd. Load `httpfs` and the secret before a remote input. Report input, output, byte size, and a row count when it is cheap.

## References

- https://duckdb.org/docs/2.0/data/io.html
- https://duckdb.org/docs/2.0/core_extensions/httpfs/authentication.html
- https://duckdb.org/docs/2.0/configuration/secrets_manager.html
- https://duckdb.org/docs/2.0/operations_manual/migration.html (S3 URL parameters)
- Reader dispatch replaces the `read_any` macro in https://github.com/duckdb/duckdb-skills (MIT). The keyless `TYPE s3, PROVIDER config, REGION` secret was accepted by DuckDB 2.0.0.
