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

Execute DuckDB with `duckdb`. For Shapefile, GeoPackage, or FlatGeobuf, see `duckdb-spatial`. GeoJSON reads natively through `read_json`. For database catalogs and multi-database attachments, see `duckdb-session` or `duckdb-lakehouse`. For semi-structured `VARIANT` columns, see `duckdb-variant`.

Never build a single unified macro for all readers. A missing extension fails the entire statement. Pick the reader from the file path. When resolving a bare filename, search under the working tree and skip `.git`. In new SQL, write canonical names `read_csv`, `read_json`, and `read_parquet`; `read_csv_auto`, `read_json_auto`, and `parquet_scan` are legacy aliases.

## Reader dispatch

| Path | Statement |
| --- | --- |
| `.csv`, `.tsv` | `FROM read_csv('path')`; `.tsv` sniffs the tab delimiter |
| `.tab`, `.txt` | `FROM read_csv('path')`; bare paths do not dispatch |
| `.json` | `FROM read_json('path')`; auto-detects array or NDJSON |
| `.jsonl`, `.ndjson` | `FROM read_json('path', format = 'newline_delimited')` |
| `.parquet`, `.pq`, or directory | `FROM read_parquet('path')`; `.parquet` bare-reads, `.pq` requires explicit function |
| `.avro` | `FROM read_avro('path')`; autoloads `avro` |
| `.xlsx` | `FROM read_xlsx('path')`; autoloads `excel` |
| `.sqlite`, `.sqlite3` | `ATTACH 'path' AS s (TYPE sqlite);` then `SHOW TABLES` |
| `.db`, `.duckdb` | `FROM read_duckdb('path', table_name = '...')` or bare `FROM 'path'`. Bare reads require a single-table file. Use `schema_name` for multi-schema files. `.db` is DuckDB, not SQLite |
| `.geojson`, `.geojsonl` | `FROM read_json('path', geojson := true)` or bare `FROM 'path'` |
| `.shp`, `.gpkg`, `.fgb` | `LOAD spatial;` then `FROM ST_Read('path')` |
| unknown extension | `DESCRIBE FROM 'path'` and switch to the reader named in the error |

## Preview and metadata

Inspect schema, initial rows, and total row count:

```sql
DESCRIBE FROM read_parquet('path');
FROM read_parquet('path') LIMIT 20;
SELECT count(*) AS n FROM read_parquet('path');
```

When inspecting a large remote Parquet file, skip `count(*)` to avoid downloading data pages. Query file metadata directly:

```sql
SELECT num_rows, file_size_bytes
FROM parquet_file_metadata('path');
```

Never sum `row_group_num_rows` from `parquet_metadata`. The row count repeats for every column in each row group, so a 5-row, 3-column file reports 15 rows. Use `parquet_file_metadata`, run `count(*)`, or query distinct groups:

```sql
SELECT sum(row_group_num_rows)
FROM (SELECT DISTINCT file_name, row_group_id, row_group_num_rows FROM parquet_metadata('path'));
```

To list remote bucket contents or directories without downloading payload bodies, read metadata with `read_blob`:

```sql
SELECT filename, size, last_modified
FROM read_blob('s3://bucket/prefix/*')
ORDER BY filename
LIMIT 50;
```

When `preserve_insertion_order = false` and multiple threads run, never page with bare `LIMIT` and `OFFSET`. Concurrent pipeline sinks reorder batches, causing queries to duplicate and drop rows while returning the expected row total. Page on a unique key (`WHERE id > :last_id ORDER BY id LIMIT :page_size`) or on `(filename, file_row_number)`. For the pagination contract and proof, see [references/pagination.md](references/pagination.md).

## Convert

To convert formats, write with `COPY ... TO`:

```sql
COPY (FROM 'input.csv') TO 'output.parquet' (FORMAT parquet);
```

| Format | Extension | COPY options |
| --- | --- | --- |
| Parquet | `.parquet`, `.pq` | `(FORMAT parquet)` |
| CSV | `.csv` | `(FORMAT csv, HEADER)` |
| TSV | `.tsv` | `(FORMAT csv, HEADER, DELIMITER '\t')` |
| JSON array | `.json` | `(FORMAT json, ARRAY true)` |
| NDJSON | `.jsonl`, `.ndjson` | `(FORMAT json, ARRAY false)` |
| Excel | `.xlsx` | `(FORMAT xlsx)` after `INSTALL excel; LOAD excel;` |

When writing partition directories, tune output behavior with these options:
- `PARTITION_BY (col)` splits writes into hive-partitioned directory trees for Parquet, CSV, or JSON.
- `OVERWRITE` deletes the target directory before writing a full rebuild.
- `OVERWRITE_OR_IGNORE` overwrites matching paths and leaves stale partitions from earlier runs. Use it only when the partition set is unchanged.
- `APPEND` adds files into existing partition directories without deleting prior files.
- `FILENAME_PATTERN 'data_{i}'` sets the output filename template.
- `PER_THREAD_OUTPUT true` writes one file per thread concurrently.
- `FILE_SIZE_BYTES 134217728` rolls to a new file when the target size (e.g. 128 MB) is reached.
- `ORDER_BY (col)` sorts rows within each output file.
- `RETURN_FILES true` returns written file paths and row counts in the query result.

For full parameter listings, reader options, and types, see [references/formats.md](references/formats.md).

## Ingest a batch

When running a repeatable production load instead of a one-off conversion, follow the batch pipeline in [references/ingest.md](references/ingest.md).

Follow the six-step ingest contract:
1. **Read raw**: Read text inputs with `all_varchar = true` and `store_rejects = true` to preserve original strings and capture syntax errors.
2. **Cast explicitly**: Define schema types in SQL; avoid automatic type sniffing in production pipelines.
3. **Split rows**: Route valid records to `good` and failed casts or business-rule violations to `bad` alongside failure reasons.
4. **Persist valid data**: Write `good` rows to hive-partitioned Parquet files.
5. **Persist quarantined data**: Store `bad` rows and parser rejects in separate quarantine tables or files.
6. **Prove row conservation**: Confirm that `input_rows = good_rows + bad_rows + count(DISTINCT reject_line)`.

Never use `ignore_errors = true` to repair a pipeline. Silently dropping malformed rows invalidates data completeness proofs.

## Remote files and secrets

Load the remote file extension before accessing cloud storage or HTTP:

```sql
LOAD httpfs;
```

Configure credentials using secrets:

| Target | Secret command |
| --- | --- |
| S3 with AWS CLI profile | `CREATE OR REPLACE SECRET (TYPE s3, PROVIDER credential_chain);` |
| S3 with explicit keys | `CREATE OR REPLACE SECRET (TYPE s3, PROVIDER config, KEY_ID '...', SECRET '...', REGION 'us-east-1');` |
| S3 public bucket with region | `CREATE OR REPLACE SECRET (TYPE s3, PROVIDER config, REGION 'us-west-2');` |
| Cloudflare R2 | `CREATE OR REPLACE SECRET (TYPE r2, ACCOUNT_ID '...', KEY_ID '...', SECRET '...');` prefix `r2://` |
| Google Cloud Storage | `CREATE OR REPLACE SECRET (TYPE gcs, KEY_ID '...', SECRET '...');` prefix `gs://` or `gcs://` |
| Azure Blob / Data Lake | `CREATE OR REPLACE SECRET (TYPE azure, PROVIDER config, ACCOUNT_NAME '...');` prefix `azure://` or `az://` |
| HTTPS / HTTP | `LOAD httpfs;` without a secret unless basic or bearer authentication is required |

`PROVIDER credential_chain` autoloads the `aws` extension and fails closed if no AWS profile is found. Public buckets require no credential secret; a region pin is configuration, not a credential. For Azure service principals, use `PROVIDER service_principal` with `TENANT_ID`, `CLIENT_ID`, and `CLIENT_SECRET`.

Never place access keys in URLs. DuckDB 2.0 treats `?s3_access_key_id=...` as part of the object key path. To restore the legacy behavior during migrations, run `SET s3_enable_deprecated_url_parameters = true;`.

Asynchronous I/O accelerates Parquet, seekable uncompressed UTF-8 CSV, and native DuckDB storage (including DuckLake scans). JSON reads remain synchronous. Default settings are `async_threads = 4 * threads` (capped at 256), `read_ahead_depth = -1`, `http_retries = 3`, and `http_retry_backoff = 4.0`. Retain defaults unless tuning for high-bandwidth networks (see [references/formats.md](references/formats.md)).

## Sandbox local files

To restrict filesystem and network access for untrusted queries, load all necessary extensions first, then restrict the session in order:

```sql
-- Step 1: Allow specific directories or exact paths
SET allowed_directories = ['/absolute/input'];
-- or exact files: SET allowed_paths = ['/absolute/file.csv'];

-- Step 2: Disable external access and lock configuration
SET enable_external_access = false;
SET allow_persistent_secrets = false;
SET lock_configuration = true;
```

Execution order is critical:
- Always set `allowed_directories` or `allowed_paths` before setting `enable_external_access = false`. Once `enable_external_access` is false, DuckDB rejects any changes to allow-lists.
- `allowed_directories` permits an entire directory tree. `allowed_paths` permits exact files.
- To block local disk while permitting remote network reads, set `disabled_filesystems = 'LocalFileSystem'`. Preload `httpfs` before disabling local access; HTTPS operations require local disk access to read the system CA certificate bundle.
- Setting `enable_external_access = false` blocks all network operations and all local filesystem paths outside `allowed_directories` or `allowed_paths`. Remote URL schemes (`s3://`, `gs://`, `r2://`, `azure://`, `https://`) bypass the local allow-list but fail once external access is disabled.
- Never rely on the CLI `-safe` flag for fine-grained sandboxing. The `-safe` flag disables all external file access unconditionally (blocking even user-provided input files), permitting reads only from the database file opened at launch. For full security matrices, see `duckdb`.

## Verify

Run the verification pipeline to test CSV reading and Parquet writing:

```bash
tmp=$(mktemp -d)
printf 'id,name\n1,Ada\n2,Grace\n' > "$tmp/in.csv"
duckdb -agent -c "COPY (FROM '$tmp/in.csv') TO '$tmp/out.parquet' (FORMAT parquet); DESCRIBE FROM '$tmp/out.parquet'; SELECT count(*) FROM '$tmp/out.parquet';"
rm -rf "$tmp"
```

The schema must display `id` and `name`. The row count must return `2`.

## References

- [Data import](https://duckdb.org/docs/2.0/data/overview.html) documents format overviews and readers.
- [CSV](https://duckdb.org/docs/2.0/data/csv/overview.html) documents CSV sniff and import options.
- [JSON](https://duckdb.org/docs/2.0/data/json/loading_json.html) documents JSON auto-detection and shapes.
- [Parquet](https://duckdb.org/docs/2.0/data/parquet/overview.html) documents Parquet reader, writer, and compression options.
- [COPY](https://duckdb.org/docs/2.0/sql/statements/copy.html) documents output formatting and partitioning parameters.
- [Secrets manager](https://duckdb.org/docs/2.0/configuration/secrets_manager.html) documents secret scopes and cloud providers.
- [I/O](https://duckdb.org/docs/2.0/data/io.html) documents asynchronous I/O settings and tuning.
- Reader dispatch replaces the `read_any` macro in https://github.com/duckdb/duckdb-skills (MIT). DuckDB 2.0.0 supports keyless `TYPE s3, PROVIDER config, REGION` secrets.
