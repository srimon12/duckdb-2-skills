# File formats reference

Read this when the skill needs a reader option, a COPY clause, a secret field, or a metadata function. The driver is `duckdb-files/SKILL.md`.

## Readers

| Function | Format | Extension | Notes |
| --- | --- | --- | --- |
| `read_csv` | CSV, TSV, delimited text | built in | `.csv`/`.tsv` bare-read; `.tab`/`.txt` need the explicit function. |
| `read_json` | JSON array, NDJSON, unstructured, GeoJSON | `json`, statically linked | Effective `format` default is `auto`. |
| `read_ndjson` | NDJSON | `json`, statically linked | Shorthand for `read_json(..., format = 'newline_delimited')`. |
| `read_parquet` | Parquet | `parquet`, statically linked | Directory and glob aware. |
| `read_avro` | Avro | `avro` | Autoloads. `INSTALL`/`LOAD` is the fallback. |
| `read_xlsx` | Excel | `excel` | Autoloads. `COPY ... (FORMAT xlsx)` needs `LOAD excel`. |
| `read_blob` | Any file as `BLOB` | built in | Columns: `filename`, `content`, `size`, `last_modified`. |
| `read_text` | Any UTF-8 file as `VARCHAR` | built in | 3.9 GiB limit. |
| `read_duckdb` | A DuckDB database file | built in | Reads tables without attaching; views are not supported. |
| `ST_Read` | GeoJSON, Shapefile, GeoPackage, FlatGeobuf, GPX | `spatial` | See `duckdb-spatial`. |
| `sqlite_scan` | SQLite table | `sqlite_scanner` | Prefer `ATTACH ... (TYPE sqlite)`. A bare `.sqlite` path does not dispatch. |

Common synonyms: `read_csv_auto`, `read_json_auto`, `read_ndjson_auto`, `read_json_objects`, `parquet_scan`. They are separate registered overloads, not true aliases.

Path dispatch: `.db` and `.duckdb` are DuckDB files. `.sqlite` and `.sqlite3` need `ATTACH`. `.geojson` and `.geojsonl` read through `json`. `.tab` and `.txt` need `read_csv`.

## CSV parameters

| Parameter | Default | Use |
| --- | --- | --- |
| `auto_detect` | `true` | Sniff delimiter, header, and types. |
| `header` | `false` | First line holds names. |
| `delim` / `sep` | `,` | Up to 4 bytes. |
| `quote` | `"` | Quote character. |
| `escape` | `"` | Escape for the quote character. |
| `nullstr` / `null` | empty | One string or a list. |
| `force_not_null` | `[]` | Columns whose empty values stay empty strings. |
| `dateformat` | empty | `%Y-%m-%d` style. |
| `timestampformat` | empty | `%Y-%m-%d %H:%M:%S` style. |
| `sample_size` | 20480 | Lines used for detection. |
| `all_varchar` | `false` | Skip type detection. Read only. |
| `columns` | empty | `{'id': 'INTEGER', 'name': 'VARCHAR'}`. |
| `names` / `column_names` | empty | Positional names when there is no header. |
| `normalize_names` | `false` | Strip non-alphanumerics and escape keywords. |
| `null_padding` | `false` | Pad short rows with NULL. |
| `ignore_errors` | `false` | Skip malformed rows. |
| `store_rejects` | `false` | Store bad rows in a rejects table. |
| `rejects_table` | `reject_errors` | Table name for bad rows. |
| `rejects_limit` | 0 | 0 means no limit. |
| `rejects_line_size_limit` | 10000 | Truncate the stored bad line. 0 means full line. |
| `union_by_name` | `false` | Align columns by name across files. |
| `hive_partitioning` | auto | Read `key=value` directories as columns. |
| `filename` | false | Virtual column; kept for compatibility. |
| `compression` | auto | `none`, `gzip`, `zstd`. |
| `encoding` | `utf-8` | `utf-8`, `utf-16`, `latin-1`. |
| `strict_mode` | `true` | Error on structural problems. |
| `allow_empty` | `false` | Return an empty result when a glob matches nothing. New in 2.0. |

Faulty CSV:

```sql
SELECT * FROM read_csv('bad.csv', store_rejects = true);
SELECT * FROM reject_errors;
```

The rejects table has one row per error, not one row per bad line. A line with two bad columns produces two rows. Count distinct `(file_id, line)` when the number must match the input.

## JSON parameters

| Parameter | Default | Use |
| --- | --- | --- |
| `format` | `auto` in practice | `auto`, `unstructured`, `newline_delimited`, `array`. The manual says `array`; a JSONL file reads without it. |
| `records` | `auto` | `false` returns raw JSON objects as a single `JSON` column instead of expanding keys. |
| `columns` | empty | Explicit `{'id': 'INTEGER'}` schema; unlisted keys are excluded. |
| `maximum_object_size` | 16 MiB | Reject larger array or unstructured objects; not enforced for NDJSON lines. |
| `ignore_errors` | `false` | Only for `newline_delimited`; a bad line becomes a row of `NULL`s, not a skipped row. |
| `union_by_name` | `false` | Align columns across files. |
| `hive_partitioning` | auto | Partition columns from the path. |
| `filename` | false | Virtual column. |
| `compression` | auto | `none`, `gzip`, `zstd`. |
| `maximum_sample_files` | 32 | Files sampled for detection. |
| `allow_empty` | `false` | Empty result for a no-match glob. New in 2.0. |
| `geojson` | `false` | Read GeoJSON as `GEOMETRY`; the JSON reader does this without loading `spatial`. |

Reading shapes:

```sql
FROM read_json('array.json');                                  -- [ {...}, {...} ]
FROM read_json('ndjson.json', format = 'newline_delimited');   -- {...}\n{...}
FROM read_json('lines.json', format = 'unstructured');         -- top-level values
FROM read_json_objects('ndjson.json');                         -- raw JSON objects
```

Writing:

```sql
COPY (FROM 'in.csv') TO 'out.json' (FORMAT json, ARRAY true);
COPY (FROM 'in.csv') TO 'out.jsonl' (FORMAT json, ARRAY false);
```

## Parquet parameters

| Parameter | Default | Use |
| --- | --- | --- |
| `schema` | NULL | Read as a supplied schema; map by field id or name. |
| `union_by_name` | `false` | Align columns across files. |
| `binary_as_string` | `false` | Treat legacy binary columns as strings. |
| `filename` | false | Virtual column. |
| `file_row_number` | `false` | Add the row number within the file. |
| `file_row_group_number` | virtual | Add the row group number. |
| `hive_partitioning` | auto | Partition columns from the path. |
| `encryption_config` | unset | Parquet encryption. |
| `int96_as` | `timestamp` | `timestamp`, `timestamp_ns`, `struct`. New in 2.0. |
| `prefetch_strategy` | `auto` | `auto` or `whole_group`. New in 2.0. |
| `utf8_validation` | `strict` | `strict`, `replace`, `ignore`. New in 2.0. |
| `bound_schema` | unset | Exact ordered output schema. New in 2.0. |
| `can_have_nan` | `false` | Keep min/max pushdown correct with NaN. |
| `allow_empty` | `false` | Empty result for a no-match glob. New in 2.0. |

`schema` cannot be combined with `union_by_name`.

## Metadata

```sql
SELECT * FROM parquet_metadata('file.parquet');       -- per row group and column
SELECT * FROM parquet_schema('file.parquet');         -- column types
SELECT * FROM parquet_file_metadata('file.parquet');  -- file-level row count, version, and sizes
SELECT * FROM parquet_kv_metadata('file.parquet');    -- key/value metadata
SELECT * FROM parquet_bloom_probe('file.parquet', 'col', 'value');
```

Do not sum `row_group_num_rows` from `parquet_metadata`. It repeats once per column in a row group, so a 5-row 3-column file reports 15. Use `parquet_file_metadata(path).num_rows`, `file_size_bytes`, or `count(*)`. `parquet_metadata` is for per-column statistics and sizes, not a total row count.

`parquet_file_metadata` returns file-level `num_rows`, row group count, version, encryption, and file and footer sizes. `parquet_kv_metadata` returns the key/value metadata.

## COPY options

These apply to every format unless noted.

| Option | Default | Use |
| --- | --- | --- |
| `FORMAT` | from extension | `csv`, `parquet`, `json`, `blob`, or an extension format such as `xlsx` or `gdal`. |
| `USE_TMP_FILE` | auto | Write to `.tmp` first, then rename. |
| `OVERWRITE_OR_IGNORE` | `false` | Overwrite matching paths in a multi-file write; stale partitions remain. |
| `OVERWRITE` | `false` | Remove the target directory tree on a local filesystem. |
| `APPEND` | `false` | Generate a new name when the target exists. |
| `FILENAME_PATTERN` | auto | `{uuid}`, `{uuidv4}`, `{uuidv7}`, `{i}`. |
| `FILE_EXTENSION` | auto | Extension for generated files. |
| `PER_THREAD_OUTPUT` | `false` | One file per thread. |
| `FILE_SIZE_BYTES` | unset | Split output by approximate size. |
| `PARTITION_BY` | unset | Hive-style partition directories. |
| `PARTITION_PATH` | unset | Custom subdirectory expression. New in 2.0. |
| `ORDER_BY` | unset | Sort rows before writing, or within partitions. New in 2.0. |
| `PRESERVE_ORDER` | setting | Keep input order. |
| `RETURN_FILES` | `false` | Return the written paths. |
| `RETURN_STATS` | `false` | Return column statistics. |
| `WRITE_PARTITION_COLUMNS` | `false` | Keep partition columns in the files. Write it bare; `= true` is a parser error. |

CSV: `HEADER` (default true), `DELIM`/`SEP`, `QUOTE`, `ESCAPE`, `NULLSTR`, `DATEFORMAT`, `TIMESTAMPFORMAT`, `FORCE_QUOTE`, `PREFIX`, `SUFFIX`, `NEW_LINE`, `COMPRESSION`. A `.tsv` target still infers CSV, so pass `DELIMITER '\t'`. `CODEC` is Parquet-only.

Parquet: `COMPRESSION` (default `snappy`), `COMPRESSION_LEVEL` (zstd 1-22), `ROW_GROUP_SIZE` (default 122880, minimum target 2048; the final group can be smaller), `ROW_GROUP_SIZE_BYTES`, `ROW_GROUPS_PER_FILE`, `PARQUET_VERSION` (`V1`, `V2`), `KV_METADATA`, `FIELD_IDS`, `SHREDDING`, `WRITE_BLOOM_FILTER`, `BLOOM_FILTER_FALSE_POSITIVE_RATIO`, `GEOPARQUET_VERSION`, `TIMESTAMP_IS_ADJUSTED_TO_UTC`, `WRITE_TIMESTAMP_AS_INT96`, `DATA_PAGE_SIZE_LIMIT`, `DICTIONARY_SIZE_LIMIT`.

JSON: `ARRAY` (default false, so `.json` writes NDJSON), `COMPRESSION`, `DATEFORMAT`, `TIMESTAMPFORMAT`. `FORMAT jsonl` is an alias.

`ROW_GROUP_SIZE_BYTES` is ignored unless `preserve_insertion_order = false`.

## Partitioned writes

```sql
COPY (FROM 'sales.csv') TO 'out' (
    FORMAT parquet,
    PARTITION_BY (year, month),
    OVERWRITE,
    FILENAME_PATTERN 'part-{i}'
);
```

The target is a directory. The default layout is `year=2026/month=10/`. `OVERWRITE_OR_IGNORE` is safe only when the new run produces the same partition set. It does not remove a partition that disappeared. Use `OVERWRITE` for a full rebuild, or remove the root first. `PARTITION_PATH` replaces the default layout:

```sql
COPY (FROM 'sales.csv') TO 'out' (
    FORMAT parquet,
    PARTITION_BY (year, month),
    PARTITION_PATH 'y=' || year || '/m=' || month
);
```

`ORDER_BY (ts)` sorts within each partition. `WRITE_PARTITION_COLUMNS` keeps the partition columns in the files; write it bare, because `= true` is a parser error. Hive partitioning reads the directory names back as columns.

## Secrets

`CREATE SECRET` is temporary. `CREATE PERSISTENT SECRET` writes an unencrypted file under `~/.duckdb/stored_secrets`. `CREATE OR REPLACE` replaces an existing secret. `SCOPE` selects a secret for a path.

```sql
CREATE SECRET s3_creds (
    TYPE s3,
    PROVIDER config,
    KEY_ID '...',
    SECRET '...',
    REGION 'us-west-2',
    SCOPE 's3://my-bucket'
);

CREATE PERSISTENT SECRET aws_chain (
    TYPE s3,
    PROVIDER credential_chain
);

CREATE SECRET r2_creds (
    TYPE r2,
    ACCOUNT_ID '...',
    KEY_ID '...',
    SECRET '...'
);
```

| Type | Fields |
| --- | --- |
| `s3` | `KEY_ID`, `SECRET`, `SESSION_TOKEN`, `REGION`, `ENDPOINT`, `URL_STYLE`, `PROVIDER` |
| `r2` | `ACCOUNT_ID`, `KEY_ID`, `SECRET`, `SESSION_TOKEN` |
| `gcs` | `KEY_ID`, `SECRET`, `PROVIDER`; HMAC keys |
| `azure` | `ACCOUNT_NAME`, `CONNECTION_STRING`, `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET`, `PROVIDER` |
| `http` | `BEARER_TOKEN`, `EXTRA_HTTP_HEADERS` |
| `huggingface` | `TOKEN` |
| `quack` | `TOKEN`, `SCOPE` |

Inspect and test:

```sql
FROM duckdb_secrets();
FROM duckdb_secret_type_parameters();
FROM which_secret('s3://my-bucket/file.parquet', 's3');
```

`CREATE SECRET` is stored in the CLI history as plain text. `duckdb_secrets()` redacts `secret=` but still shows `key_id=`. `duckdb_secrets(redact := false)` errors unless the process started with `-unredacted`; `SET allow_unredacted_secrets` at runtime fails. `SET allow_persistent_secrets = false` blocks new persistent secrets.

## Async I/O

Automatic for Parquet and uncompressed, seekable, UTF-8 CSV, including files read through DuckLake. JSON and native DuckDB files are synchronous.

| Setting | Default | Use |
| --- | --- | --- |
| `async_threads` | 4x `threads`, cap 256 | Async pool size. |
| `read_ahead_depth` | `-1` | `-1` is memory-bounded. `0` disables. |
| `http_retries` | 3 | Retry count. |
| `http_retry_wait_ms` | 100 | Initial wait. |
| `http_retry_backoff` | 4.0 | Backoff multiplier. |
| `http_client_pool_capacity` | auto | Tracks `async_threads`; the cap applies to the default. |
| `fsync_mode` | `STANDARD` | Local write flush, not async reads. |

Do not tune these before measuring. A remote Parquet scan already reads asynchronously.

## Common errors

| Error | Cause | Fix |
| --- | --- | --- |
| `No files found that match the pattern` | Wrong path, or a glob with no match. | Check the path; use `allow_empty = true` only when an empty result is valid. |
| `Could not convert string` | Wrong type inference. | Pass `columns` or `types`. |
| `Secret Validation Failure: no profile 'default' found` | `credential_chain` with no AWS profile. | Use a config secret, or skip the secret for a public bucket. |
| `Permission Error: Cannot access file` | `enable_external_access = false` or `-safe`. | Add the path to `allowed_paths` before locking, or drop safe mode. |
| `Binder Error: ... sqlite_master` | SQLite metadata function from 1.x. | `ATTACH ... (TYPE sqlite)` and `SHOW TABLES`. |
| `HTTP 403` on S3 | Wrong region, missing credentials, or a key in the URL. | Pin `REGION`; use a secret; remove URL parameters. |
| `Conversion Error: Could not convert string to ...` in CSV | A bad row. | `store_rejects = true` and inspect `reject_errors`. |

## References

- https://duckdb.org/docs/2.0/data/csv/overview.html
- https://duckdb.org/docs/2.0/data/json/loading_json.html
- https://duckdb.org/docs/2.0/data/parquet/overview.html
- https://duckdb.org/docs/2.0/sql/statements/copy.html
- https://duckdb.org/docs/2.0/configuration/secrets_manager.html
- https://duckdb.org/docs/2.0/guides/file_formats/read_file.html
- https://duckdb.org/docs/2.0/data/io.html
