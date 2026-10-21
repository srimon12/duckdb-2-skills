# Slice: files, object storage, and VARIANT

Status: complete
Scope: Reader dispatch and autoload; CSV/JSON/Parquet read and write options; COPY and partitioned writes; secrets, HTTP/S3, async I/O, local sandbox; VARIANT functions, storage, shredding, and JSON mutation.
Sources: `research/sources/duckdb-2.0/` (paths below), DuckDB 2.0.0 `d54cbbe3df`, probes in `research/scratch/03/`.

## Verified facts

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| 1 | Reader functions registered in 2.0.0: `read_csv`, `read_csv_auto`, `read_json`, `read_json_auto`, `read_ndjson`, `read_ndjson_auto`, `read_json_objects`, `read_ndjson_objects`, `read_json_objects_auto`, `read_parquet`, `parquet_scan`, `read_avro`, `read_xlsx`, `read_duckdb`, `read_text`, `read_blob`, `sqlite_scan`. | `P1` | Probed |
| 2 | `read_csv_auto`, `read_json_auto`, and `parquet_scan` work as synonyms but are registered as separate overloads: `duckdb_functions().alias_of` is `NULL` for each. The manual calls them aliases. | `P1`, `data/json/loading_json.md`, `data/parquet/overview.md` | Probed |
| 3 | `read_csv` and `read_json` default to auto-detection. `read_json`'s `format` parameter is documented with default `array`, but a JSONL file reads without `format`, so the effective default is `auto`. | `P3`, `data/json/loading_json.md` | Probed / doc contradiction |
| 4 | Bare paths dispatch by extension for `.csv`, `.tsv`, `.json`, `.jsonl`, `.ndjson`, `.parquet`, `.xlsx`, `.duckdb`, `.db`, `.geojson`, `.geojsonl`, `.csv.gz`, `.json.gz`. They do **not** dispatch for `.pq`, `.avro`, `.tab`, `.txt`, `.sqlite`, `.sqlite3`; those need the named function or `ATTACH`. | `P2`, `P7`, `P8`, `P9`, `P75` | Probed |
| 5 | `.tsv` bare read auto-detects the tab delimiter; `.tab` and `.txt` need explicit `read_csv('path')`. | `P2`, `P7` | Probed |
| 6 | `.db` dispatches to `read_duckdb`, not SQLite. `FROM 'conflict.db'` returned the DuckDB table. A SQLite file named `.db` gives `Not implemented Error: read_duckdb can only be used to read DuckDB files - ... is of type "sqlite"`; it must be `ATTACH ... (TYPE sqlite)`. | `P8` | Probed |
| 7 | `read_duckdb(path, table_name = '...')` reads a table without attaching; `FROM 'file.duckdb'` is equivalent. Views are not supported (`Binder Error: ... no tables matching table_name="v"`). | `P9`, `guides/file_formats/read_duckdb.md` | Probed |
| 8 | `.geojson` and `.geojsonl` are JSON replacements in 2.0: bare paths return a `GEOMETRY` column plus properties, and `read_json(..., geojson := true)` does the same. This does not require `LOAD spatial`. | `P10`, `data/json/loading_json.md#geojson`, `data/json/writing_json.md#geojson` | Probed |
| 9 | `st_read` does not autoload: it raised `Catalog Error ... exists in the spatial extension` until `INSTALL spatial; LOAD spatial;`. A `.shp` bare path did reach the spatial reader. | `P11` | Probed |
| 10 | A missing extension produces: `Catalog Error: Table Function with name "read_xlsx" is not in the catalog, but it exists in the excel extension.` followed by the exact `INSTALL excel; LOAD excel;` fix and the two `SET autoinstall_known_extensions=1; SET autoload_known_extensions=1;` hints. | `P4` | Probed |
| 11 | In a default install, `json` and `parquet` are `STATICALLY_LINKED`; `httpfs`, `aws`, `excel`, `avro`, `sqlite_scanner`, `azure`, and `spatial` are repository extensions that can autoload. `read_avro` autoloaded even though `avro` started `NOT_INSTALLED`; spatial autoloaded for `.shp`/`GEOMETRY`, but `st_read` did not (row 9). | `P1`, `P4`, `P5`, `P11` | Probed |
| 12 | Two write paths are exceptions to autoload: `COPY ... (FORMAT xlsx)` failed with `Catalog Error: Copy Function with name xlsx does not exist` until `LOAD excel`; `st_read` needed an explicit load. `ATTACH ... (TYPE sqlite)` loaded the installed SQLite extension even with `autoload_known_extensions=false`. | `P5`, `P6`, `P11` | Probed |
| 13 | `read_text`/`read_blob` return `filename VARCHAR, content VARCHAR or BLOB, size BIGINT, last_modified TIMESTAMPTZ`; `read_text` validates UTF-8 and both cap a file at 3.9 GiB. Projecting only `size`/`last_modified` avoids reading bodies, including on S3. | `P12`, `guides/file_formats/read_file.md` | Probed |
| 14 | CSV `header` default is `false` in the function signature but the sniffer sets it; `auto_detect` default `true`; an explicit option overrides only that option. `auto_detect=false` cannot infer a schema and errors unless `columns` is supplied. | `P13`, `P14`, `data/csv/overview.md` | Probed |
| 15 | CSV `delim`/`sep` accept up to 4 bytes; `quote`/`escape` default `"`; `nullstr`/`null` accept one string or a list; `force_not_null` suppresses null matching for named columns. | `P15`, `data/csv/overview.md` | Probed |
| 16 | CSV `dateformat`/`timestampformat` are applied only when the corresponding column is inferred or declared as `DATE`/`TIMESTAMP`; `%d/%m/%Y` parsed `31/12/2024` when supplied. | `P16` | Probed |
| 17 | CSV `sample_size` default 20480, `-1` reads the whole input. On a gzip file (samples only from the start), the default inferred `BIGINT` while `sample_size=-1` inferred `VARCHAR`. | `P17`, `data/csv/auto_detection.md` | Probed |
| 18 | CSV `all_varchar=true` returns every column as `VARCHAR`; `normalize_names=true` turned `Order ID` into `order_id` and the reserved word `When` into `_when`. | `P13`, `P18` | Probed |
| 19 | CSV `ignore_errors=true` skips bad rows. `store_rejects=true` implies skip and writes `reject_scans`/`reject_errors` temp tables; `rejects_limit=0` means unlimited, `rejects_line_size_limit` default 10000. A cast error is only raised for projected columns. | `P19`, `P20`, `data/csv/reading_faulty_csv_files.md` | Probed |
| 20 | CSV `null_padding=true` pads short rows but does not truncate long rows; combined with `strict_mode=false` a long row is truncated (`6,7,8,9` → `6,7,8`), while `ignore_errors=true` drops the whole row. `null_padding` alone cannot rescue a file the sniffer refuses. | `P21` | Probed |
| 21 | CSV `buffer_size=10` fails with `Maximum line size of 10 bytes exceeded` on a 14-byte header — the error blames line size, not the buffer. Default is `16 * max_line_size`. | `P22`, `data/csv/overview.md` | Probed |
| 22 | CSV `union_by_name=true` unions `a,b` and `a,c` with `NULL` fill; without it, differing column names raise `Schema mismatch between globbed files`. `filename` and `file_index` are always-available virtual columns; `filename='src'` renames the column. | `P23`, `P24` | Probed |
| 23 | CSV `hive_partitioning` is auto-detected from `key=value` directories; `hive_partitioning=false` drops the partition columns. Partition columns are appended after file columns and typed `BIGINT`/`DATE`/`TIMESTAMP` when possible. | `P25`, `data/partitioning/hive_partitioning.md` | Probed |
| 24 | JSON `format` accepts `auto`, `unstructured`, `newline_delimited`, `array`; `format='array'` on a JSONL file errors: `Expected top-level JSON array ... first character is '{'`. `records=false` returns one `JSON` column instead of unpacking keys. | `P26`, `data/json/loading_json.md` | Probed |
| 25 | JSON `"array" = true` is the quoted shorthand for `format='array'` (`array` is a keyword). `read_json('lines.jsonl', "array"=true)` fails as expected. | `P26` | Probed |
| 26 | JSON `columns={'id':'BIGINT'}` excludes unlisted keys rather than adding them. `auto_detect=false` works with `columns`. | `P27` | Probed |
| 27 | JSON `maximum_object_size` default 16777216 applies to array/unstructured objects only; a 20 MiB object failed there, but the same object on one NDJSON line read fine. | `P28` | Probed |
| 28 | JSON `ignore_errors=true` only affects `newline_delimited` and emits a row of `NULL`s for a malformed line — it does not skip the row like CSV. On `format='array'` it is accepted and ignored. | `P29` | Probed |
| 29 | JSON multi-file reads union keys and nested struct fields automatically. `union_by_name` produced no observable schema difference for either differing keys or differing types (`read_json('t*.json')` returned `JSON` for the conflicting column both ways). | `P30` | Probed |
| 30 | `read_json` cannot read directly into a `VARIANT` column: `DESCRIBE` accepts it, execution fails with `Not implemented Error: Cannot read a value of type VARIANT from a json file`. Load as `JSON` then cast `::VARIANT`. | `P31` | Probed |
| 31 | JSON writes are NDJSON by default, regardless of a `.json` extension. `ARRAY true` writes one array; `FORMAT jsonl` is an accepted copy-format alias. `.json.gz` inferred gzip; `.zst` inference is documented. | `P32`, `sql/statements/copy.md` | Probed / documented |
| 32 | JSON mutation is `json_set`, `json_insert`, `json_replace`, `json_remove`, each `(json JSON, path VARCHAR, value JSON)` (remove has no value). `json_set` creates missing intermediate objects; `json_transform(json, structure)` returns a typed value (`ANY`), and `json_transform_strict` errors on cast failure. | `P33`, `data/json/json_functions.md` | Probed |
| 33 | `json_merge_patch` deletes a key on JSON `null`; `json_deep_merge` keeps the original on `null`; `json_merge_patch_diff` returns the minimal RFC 7396 patch. | `P34` | Probed |
| 34 | Parquet read options that change behavior: `schema`, `binary_as_string`, `filename`, `file_row_number`, `hive_partitioning`, `union_by_name`, `encryption_config`, `int96_as`, `prefetch_strategy`, `utf8_validation`, `bound_schema`, `can_have_nan`, `allow_empty`. `file_row_group_number` is always available (no flag). | `P35`, `P36`, `data/parquet/overview.md` | Probed |
| 35 | `schema` is a `MAP` whose values are structs: `MAP{'i': {name:'j', type:'VARCHAR', default_value:NULL}}`. A bare type string errors (`'schema' expects a STRUCT as the value type of the map`). It can add, rename, reorder, drop, and cast columns. | `P35` | Probed |
| 36 | `binary_as_string=true` turns a `BLOB` Parquet column into `VARCHAR`. `file_row_number` is the file-relative row index; `file_row_group_number` restarts at 0 for each file. | `P36` | Probed |
| 37 | `parquet_file_metadata(path).num_rows` is the cheap row count. `parquet_metadata` repeats `row_group_num_rows` and `row_group_compressed_bytes` once per column in a row group: a 5-row, 3-column file summed to 15 rows and 447 compressed bytes. `sum(total_compressed_size)` gave 149. | `P37` | Probed |
| 38 | Metadata functions: `parquet_metadata` (row group × column: stats, sizes, bloom offsets, `min_is_exact`, `max_is_exact`, plus 2.0 `geo_bbox`, `geo_types`, `encoding_stats`, `stats_nan_count`), `parquet_schema` (adds `duckdb_type`, `column_id`), `parquet_file_metadata` (num_rows, row groups, version, encryption, file size, footer size), `parquet_kv_metadata` (`key`,`value` BLOB), `parquet_bloom_probe(filename, column_name, value)`. | `P37`, `P38`, `data/parquet/metadata.md` | Probed |
| 39 | Parquet encryption uses `PRAGMA add_parquet_key('key256', '...')` plus `encryption_config={footer_key:'key256'}`; `column_keys` is not implemented. Encrypted files cannot be inspected by `parquet_metadata`/`parquet_file_metadata` because those functions take no `encryption_config`. | `P39`, `data/parquet/encryption.md` | Probed |
| 40 | COPY write defaults: CSV `HEADER` is **true**; Parquet `COMPRESSION` snappy, `ROW_GROUP_SIZE` 122880, `PARQUET_VERSION` V1; JSON `ARRAY` false. `.tsv` target inference writes **comma**-separated CSV, so the explicit `DELIMITER '\t'` is required. | `P40`, `P41`, `sql/statements/copy.md` | Probed |
| 41 | COPY `CODEC` is accepted as a Parquet compression alias (`CODEC 'zstd'` produced `ZSTD`), but is rejected for CSV (`Unrecognized option "codec" for csv`). `FORMAT xlsx` needs `LOAD excel`; XLSX `HEADER` defaults false. | `P41`, `P42`, `core_extensions/excel.md` | Probed / documented |
| 42 | COPY option applicability: `HEADER`, `DELIMITER`, `QUOTE`, `ESCAPE`, `NULL`/`NULLSTR`, `FORCE_QUOTE`, `PREFIX`, `SUFFIX`, `NEW_LINE` are CSV-only; `DATEFORMAT`/`TIMESTAMPFORMAT` work for CSV and JSON; `ARRAY` is JSON-only; `SHREDDING` and `KV_METADATA` are Parquet-only; Parquet rejects all CSV text options; `COMPRESSION` applies to CSV/JSON/Parquet/BLOB. | `P42`, `P43`, `sql/statements/copy.md` | Probed |
| 43 | Partitioned write layout is `root/col=value/.../data_0.ext`, one file per thread per directory. `PARTITION_BY` cannot use expressions; compute columns in the query first. A `NULL` partition becomes `__HIVE_DEFAULT_PARTITION__` and reads back as `NULL`. | `P44`, `data/partitioning/partitioned_writes.md` | Probed |
| 44 | Writing into a non-empty partition root errors: `IO Error: Directory "pw2" is not empty! Enable OVERWRITE option to overwrite files`. `OVERWRITE_OR_IGNORE` only replaces directories it writes to — stale `year=2024` survived a new `year=2026` write. `OVERWRITE` cleared the whole root. `APPEND` wrote a UUID filename and kept both. | `P45` | Probed |
| 45 | `ORDER_BY (v DESC)` sorts within each partition. `PARTITION_PATH` computes the subdirectory per partition; if it does not emit Hive `key=value` segments, a later `read_parquet(..., hive_partitioning=true)` fails with `Hive partition mismatch between file ...`. | `P46` | Probed |
| 46 | `WRITE_PARTITION_COLUMNS` is a bare option or `true`; `WRITE_PARTITION_COLUMNS = true` is a parser error. With it, the partition columns are present in the files; reading with Hive partitioning does not duplicate them. | `P47` | Probed |
| 47 | `FILE_SIZE_BYTES` is approximate at row-group granularity: a 100000-byte target produced 493 KB and 309 KB files. `PER_THREAD_OUTPUT` writes a directory and one file per participating thread. | `P48` | Probed |
| 48 | Secret types in 2.0: `s3`, `r2`, `gcs`, `azure`, `http`, `huggingface`, `quack`, plus catalog/database types. `config` is the default provider; `credential_chain` exists for S3/GCS/R2/Azure. | `P49`, `configuration/secrets_manager.md` | Probed |
| 49 | A config secret with only `REGION` is valid: `CREATE SECRET (TYPE s3, PROVIDER config, REGION 'eu-central-1')`. Default S3 scope is `s3://`, `s3n://`, `s3a://`; R2 defaults to `r2://` and derives `endpoint=<account>.r2.cloudflarestorage.com`. | `P50` | Probed |
| 50 | `credential_chain` without an AWS profile fails at creation: `Secret Validation Failure: no profile 'default' found in config file ~/.aws/config`, plus a region hint. It autoloads `aws`. | `P51` | Probed |
| 51 | `duckdb_secrets()` columns are `name,type,provider,persistent,storage,scope,secret_string`; `SECRET`/tokens are redacted but `KEY_ID` is not. The table function accepts `redact` (default true); `duckdb_secrets(redact := false)` errors `Displaying unredacted secrets is disabled` unless the **startup** option `allow_unredacted_secrets` (CLI `-unredacted`) was set. `SET allow_unredacted_secrets` at runtime fails. | `P52` | Probed |
| 52 | `duckdb_secret_type_parameters()` (new in 2.0) returns `type,provider,name,parameter_type,description`; e.g. S3 config has 18 parameters and S3 credential_chain 19. `duckdb_secret_types()` returns `type,default_provider,extension`; the S3/R2/GCS/HF types register when `httpfs` loads. | `P49`, `sql/meta/duckdb_table_functions.md` | Probed |
| 53 | Persistent secrets go to `~/.duckdb/stored_secrets` (mode 600, unencrypted), or `secret_directory` set in the same session; `CREATE PERSISTENT SECRET` is blocked by `allow_persistent_secrets=false` with `Persistent secrets are disabled...`, while temporary secrets still work. `DROP [PERSISTENT] SECRET` removes them. | `P53` | Probed |
| 54 | `which_secret(path, type)` returns `name,persistent,storage` and picks the longest matching scope (`s3://bucket/a/deep` chose the deeper secret; an unrelated path returned zero rows). | `P54` | Probed |
| 55 | Default S3 handling treats `?s3_access_key_id=` as part of the key: a known public object with that suffix returned 0 rows while the plain key returned 1. `SET s3_enable_deprecated_url_parameters=true` enables query parsing; then `?region=` is rejected with the supported list (`s3_region`, `s3_access_key_id`, ...). | `P55` | Probed |
| 56 | Public reads need no secret: `read_blob('s3://noaa-ghcn-pds/ghcnd-stations.txt')`, `read_parquet` over `https://`, and `hf://datasets/...` all worked. S3 globbing needs `ListObjectsV2`; writes need multipart upload. | `P56`, `core_extensions/httpfs/s3api.md` | Probed |
| 57 | Async I/O scope is Parquet plus uncompressed, seekable, UTF-8 CSV, including DuckLake; JSON and native DuckDB files are synchronous. Defaults on this 8-core host: `threads=8`, `async_threads=32` (4× cores, default capped at 256), `read_ahead_depth=-1`, `http_retries=3`, `http_retry_wait_ms=100`, `http_retry_backoff=4.0`, `http_client_pool_capacity=32`. `SET async_threads=1000` was accepted; the 256 cap applies to the default, not to a user value. | `P57`, `data/io.md` | Probed / documented |
| 58 | `http_client_pool_capacity` is derived from threads/async threads (`RESET` re-derives: 8 fixed → `RESET` gave 16 with `threads=8, async_threads=10`); `read_ahead_depth` accepts `-1` (memory-bounded), `0` (off), `N` (jobs); `fsync_mode` accepts `STANDARD`, `FULL`, `NONE` and is global. | `P58`, `data/io.md` | Probed |
| 59 | Sandbox order is load extensions → `SET allowed_paths=[...]` (or `allowed_directories`) → `SET enable_external_access=false` → `SET allow_persistent_secrets=false` → `SET lock_configuration=true`. Setting `allowed_paths` after `enable_external_access=false` fails: `Cannot change allowed_paths when enable_external_access is disabled`. | `P59`, `operations_manual/securing_duckdb/overview.md` | Probed |
| 60 | With `enable_external_access=false`, the allowed file reads through `read_csv`, `read_text`, and `read_blob`; any other path fails `Permission Error: Cannot access file ... - file system operations are disabled by configuration`. `LOAD`/`INSTALL` also fail, so extensions must be loaded before locking. | `P59`, `P60` | Probed |
| 61 | `-safe` is stricter than the manual recipe: it starts with `enable_external_access=false` **and** `lock_configuration=true`, so `SET allowed_paths` afterwards fails `Cannot change configuration option "allowed_paths" - the configuration has been locked`. It also disables `.read`, `.output`, `.import`, `.open`, `getenv`, etc. | `P61`, `clients/cli/safe_mode.md` | Probed |
| 62 | `VARIANT` functions present in 2.0.0: `variant_typeof(v)`, `variant_type(v[,path])`, `variant_keys(v[,path])`, `variant_extract(v,field VARCHAR)`, `variant_extract(v,index UINTEGER)`, `variant_extract_string(v,path VARCHAR[])`, `variant_array_length(v[,path])`, `variant_exists(v,path)`, `variant_contains(haystack,needle)`, `variant_comparator(v)`, `variant_normalize(v)`, `variant_group_object(key,value)`, `variant_group_array(x)`. There is no `variant_equal`. | `P62` | Probed |
| 63 | `variant_extract` list indexes are **1-based**: `d[1]` and `variant_extract(d,1)` return the first element; index `0` raises `Extracting index 0 from VARIANT(ARRAY) is invalid, indexes are 1-based`; a negative index fails casting to `UINTEGER`. `variant_extract_string` accepts only `VARCHAR`/`VARCHAR[]` paths, not an integer index. | `P63` | Probed |
| 64 | `variant_type` reports physical categories, not SQL type names: `true` → `BOOL_TRUE`, `false` → `BOOL_FALSE`, `1::TINYINT` → `INT8`, `1::BIGINT` → `INT64`, `1.5::DECIMAL(3,1)` → `DECIMAL`, `TIMESTAMP` → `TIMESTAMP_MICROS`. `variant_typeof` adds structure: `OBJECT(age, name)`, `ARRAY(3)`, `DECIMAL(3, 1)`. | `P64` | Probed |
| 65 | Dot notation matches `variant_extract` and returns `VARIANT` for both object fields and list elements (`d.name`, `d[1]`). Duplicate object keys collapse in `VARIANT` (`{"a":1,"a":2}` → `{'a': 2}`), while `JSON` preserves both. | `P65` | Probed |
| 66 | `VARIANT` equality is logical: whitespace and object key order do not matter, and `1::VARIANT = 1.0::VARIANT` is true. `variant_normalize` canonicalizes but is not needed for `=`; `variant_comparator` returns a `BLOB` sort key and ordering matches numeric order (`-2,-1,0,1`). | `P66` | Probed |
| 67 | `variant_contains` is structural subset/element containment (`{'a':1,'b':2}` contains `{'a':1}`; `[1,2,3]` contains `2`; `'abcdef'` does **not** contain `'bcd'`). `variant_array_length` on an object returns `0`; `variant_keys` on an array returns `[]`; `variant_exists` on an array index returns `false`. | `P67` | Probed |
| 68 | `variant_group_object` errors exactly on `duplicate key "a"` and `key cannot be NULL`; `variant_group_array` is the macro `CAST(list(x) AS VARIANT)`, keeps order and NULLs, and works as a window function. | `P68` | Probed |
| 69 | `variant_minimum_shredding_size` default 30000 rows, `-1` disables; it controls DuckDB **database-file** row-group shredding (50k-row `pragma_storage_info` count: 20 segments with shredding, 25 with `-1`). | `P69`, `sql/data_types/variant.md` | Probed |
| 70 | Parquet auto-shredding is **not** gated by `variant_minimum_shredding_size`: with the setting at `-1`, a one-row VARIANT file still wrote the `typed_value` structure. Parquet shredding follows the first row group; `SHREDDING` forces a schema. | `P70`, `sql/data_types/variant.md` | Probed |
| 71 | `SHREDDING` mismatch is not an error. `STRUCT(name VARCHAR, age INTEGER)` with `age='notanint'` and with `[1,2]`/`42` values wrote and read back correctly; the file keeps the unshredded `value` BLOB alongside `typed_value`. Extra fields survived when the schema omitted them. Invalid type names and unknown/non-VARIANT column names error at bind. | `P71` | Probed |
| 72 | `SHREDDING` is Parquet-only (`Unrecognized option "shredding" for csv`; `Unknown option ... (FORMAT JSON)`). `variant_minimum_shredding_size` does not retroactively rewrite existing rows. | `P72` | Probed |
| 73 | `VARIANT` to `VARCHAR` yields DuckDB's literal form (`{'a': 1}`), not JSON; use `::JSON::VARCHAR` for JSON text. `VARIANT::JSON` works. A `VARIANT` written to CSV is `{'a': 1}`; written to JSON it is a real JSON object. | `P73` | Probed |
| 74 | `VARIANT` supports `GROUP BY`, `DISTINCT`, and `ORDER BY` directly; a mixed column ordered `true, 1.5, 2, 'a', NULL`, matching type-bucket ordering. | `P74` | Probed |
| 75 | Async tuning: leave defaults; only tune a high-bandwidth remote Parquet scan, and ensure files have at least as many row groups as threads. `fsync_mode=NONE` trades durability for local write speed; never use it when the database must survive a crash. | `data/io.md` | Documented |
| 76 | HTTP range requests: Parquet (and native DuckDB files) use them for partial reads; `count(*)` reads only metadata; CSV is usually downloaded whole because it is row-based. Plain HTTP(S) is read-only; writes need an S3-API store. | `core_extensions/httpfs/https.md`, `core_extensions/httpfs/overview.md` | Documented |

### CSV knobs that change a read

| Parameter | Default | Effect / trap |
|---|---|---|
| `header` | `false` (manual); sniffer decides | Force `true`/`false` when all columns are text; header detection then cannot tell. |
| `delim`/`sep` | `,` | Up to 4 bytes; `delimiter` is the COPY-only alias. |
| `quote` | `"` | Set empty to disable quoting. |
| `escape` | `"` | Escapes the quote character inside quoted values. |
| `nullstr`/`null` | empty | One string or list; `force_not_null` exempts named columns. |
| `dateformat` | empty (auto) | `%d/%m/%Y` etc.; only affects inferred/declared `DATE`. |
| `timestampformat` | empty (auto) | Same for `TIMESTAMP`. |
| `sample_size` | 20480 | `-1` scans all; compressed/stdin files only sample from the start. |
| `all_varchar` | `false` | Skips type detection; read-only option. |
| `normalize_names` | `false` | `Order ID`→`order_id`; reserved `When`→`_when`. |
| `ignore_errors` | `false` | Skips malformed rows; projection pushdown can hide the error. |
| `store_rejects` | `false` | Implies skip; creates temp `reject_scans`/`reject_errors`. |
| `rejects_table` | `reject_errors` | Rename the bad-row table. |
| `rejects_limit` | 0 | Per-file cap on recorded rows; 0 = no cap. |
| `rejects_line_size_limit` | 10000 | Truncates `csv_line`; 0 = full line. New in 2.0. |
| `null_padding` | `false` | Pads short rows only; cannot fix a sniffer dialect failure. |
| `parallel` | `true` | `false` for a single-threaded read; order still follows `preserve_insertion_order`. |
| `buffer_size` | `16 * max_line_size` | Too small gives a misleading "maximum line size" error. |
| `union_by_name` | `false` | Aligns columns by name; without it differing names error. |
| `filename` | virtual | Always present since 1.3; a string renames the column. |
| `hive_partitioning` | auto | Reads `key=value` dirs; `false` drops them. |
| `auto_detect` | `true` | Explicit options override one property; `false` requires `columns`. |

### JSON knobs that change a read

| Parameter | Default | Effect / trap |
|---|---|---|
| `format` | `auto` (docs say `array`) | `array`, `newline_delimited`, `unstructured`, `auto`; `array` on NDJSON errors. |
| `records` | `auto` | `false` returns one `JSON`/`STRUCT` column instead of unpacking keys. |
| `"array"` | unset | Quoted shorthand: `true` = `format='array'`, `false` = NDJSON. |
| `columns` | auto | Explicit struct; unlisted keys are excluded. Cannot use `VARIANT`. |
| `maximum_object_size` | 16777216 | Applies to array/unstructured objects, **not** NDJSON lines. |
| `ignore_errors` | `false` | NDJSON only; malformed line becomes a row of NULLs, not skipped. |
| `union_by_name` | `false` | No observable effect in probes; JSON already unions keys across files. |
| `filename` | virtual | Always present; string renames. |
| `hive_partitioning` | auto | Adds partition columns from the path. |
| `geojson` | `false` | Parse `.geojson` geometry as `GEOMETRY`. |
| `timestampformat`/`dateformat` | `iso` | Applies to inferred/declared temporal columns. |

### Reader signatures (2.0.0 registration)

| Format | Exact call | Dispatch / notes |
|---|---|---|
| CSV, TSV | `read_csv(path VARCHAR)` / `read_csv(paths ANY[])` | Named: `delim`(`sep`), `quote`, `escape`, `header`, `columns`, `types`, `nullstr`(`null`), `dateformat`, `timestampformat`, `sample_size`, `all_varchar`, `normalize_names`, `ignore_errors`, `store_rejects`, `rejects_table`, `rejects_scan`, `rejects_limit`, `rejects_line_size_limit`, `null_padding`, `parallel`, `buffer_size`, `union_by_name`, `filename`, `hive_partitioning`, `auto_detect`, `encoding`, `strict_mode`, `allow_empty`. `read_csv_auto` has the same shape. |
| JSON | `read_json(path VARCHAR)` / `read_json(paths ANY[])` | `read_json_auto` same. Named: `format`, `records`, `"array"`, `columns`, `maximum_object_size`, `ignore_errors`, `union_by_name`, `filename`, `hive_partitioning`, `geojson`, `dateformat`, `timestampformat`, `auto_detect`, `sample_size`, `maximum_sample_files`. |
| NDJSON/JSONL | `read_ndjson(path)` / `read_ndjson_auto(path)` | Aliases for `read_json` with `format='newline_delimited'`. |
| Raw JSON objects | `read_json_objects(path)`, `read_ndjson_objects(path)`, `read_json_objects_auto(path)` | One `json JSON` column per object. |
| Parquet | `read_parquet(path VARCHAR)` / `read_parquet(paths ANY[])` | `parquet_scan` same. Named: `schema`, `binary_as_string`, `filename`, `file_row_number`, `hive_partitioning`, `union_by_name`, `encryption_config`, `int96_as`, `prefetch_strategy`, `utf8_validation`, `bound_schema`, `can_have_nan`, `allow_empty`. `file_row_group_number` is virtual. |
| Avro | `read_avro(path VARCHAR)` / `read_avro(paths ANY[])` | `filename`, `hive_partitioning`, `schema`, `file_row_number`, `allow_empty`; `union_by_name` binds but raises `not implemented for Avro reader yet`. No projection/filter pushdown, no parallelism. |
| Excel | `read_xlsx(file_path VARCHAR, header BOOLEAN, all_varchar BOOLEAN, ignore_errors BOOLEAN, range VARCHAR, sheet VARCHAR, stop_at_empty BOOLEAN, empty_as_varchar BOOLEAN, normalize_names BOOLEAN)` | `.xlsx` bare; `.xls` unsupported. `COPY ... (FORMAT xlsx)` needs `LOAD excel`. |
| SQLite | `sqlite_scan(path VARCHAR, table_name VARCHAR)` | Prefer `ATTACH 'file.sqlite' AS s (TYPE sqlite)`. `.sqlite`/`.sqlite3` do not bare-dispatch; `.db` goes to DuckDB. |
| DuckDB DB | `read_duckdb(path VARCHAR, ..., schema_name VARCHAR, table_name VARCHAR)` | `FROM 'file.duckdb'`/`.db`; tables only, no views. |
| BLOB / text | `read_blob(path VARCHAR, allow_empty BOOLEAN)`, `read_text(path VARCHAR, allow_empty BOOLEAN)` | `filename, content, size, last_modified`; 3.9 GiB cap; `read_text` rejects invalid UTF-8. |
| GeoJSON | `read_json(path, geojson := true)` | `.geojson`/`.geojsonl` bare; output `GEOMETRY`; `st_read` requires `LOAD spatial`. |

### VARIANT signatures (exact)

| Function | Signature | Behavior |
|---|---|---|
| `variant_typeof` | `variant_typeof(v VARIANT) → VARCHAR` | Full nested type. No path overload. |
| `variant_type` | `variant_type(v VARIANT [, path VARCHAR]) → VARCHAR` / `VARCHAR[]` | Category/physical type name. |
| `variant_keys` | `variant_keys(v VARIANT [, path]) → VARCHAR[]` / `VARCHAR[][]` | Object keys; `[]` for arrays/scalars. |
| `variant_extract` | `variant_extract(v VARIANT, field VARCHAR) → VARIANT`; `(v VARIANT, index UINTEGER) → VARIANT` | Object field or 1-based list element. |
| `variant_extract_string` | `(v VARIANT, path VARCHAR) → VARCHAR`; `(v VARIANT, path VARCHAR[]) → VARCHAR[]` | Non-scalar results are stringified as JSON; no integer-index overload. |
| `variant_array_length` | `(v VARIANT [, path]) → UBIGINT` / `UBIGINT[]` | `0` for a non-array. |
| `variant_exists` | `(v VARIANT, path) → BOOLEAN` / `BOOLEAN[]` | Object keys only. |
| `variant_contains` | `(haystack VARIANT, needle VARIANT) → BOOLEAN` | Recursive structural containment; not substring. |
| `variant_comparator` | `(v VARIANT) → BLOB` | Sort key for logical ordering. |
| `variant_normalize` | `(v VARIANT) → VARIANT` | Canonical representation. |
| `variant_group_object` | `(key VARCHAR, value VARIANT) → VARIANT` (aggregate) | Errors on NULL/duplicate key. |
| `variant_group_array` | `(x) → VARIANT` (macro, aggregate/window) | `CAST(list(x) AS VARIANT)`. |

### Secrets (exact shapes)

| Target | Statement |
|---|---|
| S3 | `CREATE SECRET (TYPE s3, PROVIDER config, KEY_ID '...', SECRET '...', REGION 'us-east-1');` |
| MinIO / S3-compatible | `CREATE SECRET (TYPE s3, PROVIDER config, KEY_ID '...', SECRET '...', REGION 'us-east-1', ENDPOINT 'localhost:9000', URL_STYLE 'path', USE_SSL false);` |
| S3 from AWS chain | `CREATE SECRET (TYPE s3, PROVIDER credential_chain [, PROFILE '...', CHAIN '...', REGION '...']);` |
| Public bucket region pin | `CREATE SECRET (TYPE s3, PROVIDER config, REGION 'us-west-2');` |
| R2 | `CREATE SECRET (TYPE r2, PROVIDER config, ACCOUNT_ID '...', KEY_ID '...', SECRET '...');` — URLs are `r2://bucket/key`; no rewrite to `s3://` needed. `credential_chain` reads AWS env vars. |
| GCS | `CREATE SECRET (TYPE gcs, KEY_ID '<HMAC id>', SECRET '<HMAC secret>');` — `gs://` or `gcs://`; HMAC keys, not service-account JSON. |
| Azure (anonymous/public) | `CREATE SECRET (TYPE azure, PROVIDER config, ACCOUNT_NAME '...');` |
| Azure (SPN) | `CREATE SECRET (TYPE azure, PROVIDER service_principal, TENANT_ID '...', CLIENT_ID '...', CLIENT_SECRET '...', ACCOUNT_NAME '...');` |
| HTTP | `CREATE SECRET (TYPE http, BEARER_TOKEN '...');` or `CREATE SECRET (TYPE http, EXTRA_HTTP_HEADERS MAP {'Authorization': 'Bearer ...'});` (not `HEADERS`) |
| Quack | `CREATE SECRET (TYPE quack, TOKEN '...', SCOPE 'quack:host:port');` then `ATTACH 'quack:host:port' (TYPE quack);` |

### JSON vs VARIANT

| Property | `JSON` | `VARIANT` |
|---|---|---|
| Physical storage | `VARCHAR` text | Binary, self-describing per value |
| Whitespace in `=` | Significant (probed `false` for `{ "a": 5 }` vs `{"a":5}`) | Irrelevant (`true`) |
| Object key order in `=` | Significant by text | Irrelevant; keys sorted on display |
| Duplicate keys | Preserved (`{"a":1,"a":2}`) | Collapsed, last wins (`{'a': 2}`) |
| Equality | Text/context-dependent; docs warn | Logical; numeric `1 = 1.0` is `true` |
| List index base | 0 (`'[10,20]'->'$[0]'` = 10) | 1 (`d[1]` = 10; `d[0]` errors) |
| Extraction | `->`, `->>`, `json_extract`, `json_extract_string` | `variant_extract`, `variant_extract_string`, dot path |
| Mutation | `json_set`/`insert`/`replace`/`remove`, `json_transform`, `json_merge_patch` | None; cast `::JSON`, mutate, cast back |
| Text fidelity | Keeps exact bytes (whitespace, duplicate keys) | Not exact; use `::JSON::VARCHAR`, not `::VARCHAR` |
| Parquet | Plain string column | Optional shredded `typed_value` layout |
| `read_json(columns={'x':'VARIANT'})` | n/a | Binds, then errors at execution |
| Best use | Exact text, JSON functions, mutation | Filter/project/sort/group, storage size |

### COPY option matrix (write side)

| Option | CSV | JSON | Parquet | Note |
|---|---|---|---|---|
| `FORMAT` | yes | yes | yes | Also `jsonl`, `blob`, `xlsx` (after `LOAD excel`), `geojson`/`geojsonl`. |
| `HEADER` | yes (default true) | no | no | XLSX format has its own `HEADER` (default false). |
| `DELIMITER`/`DELIM`/`SEP` | yes | no | no | `.tsv` inference writes comma; pass `DELIMITER '\t'` explicitly. |
| `QUOTE`, `ESCAPE`, `NULL`/`NULLSTR`, `FORCE_QUOTE`, `PREFIX`, `SUFFIX`, `NEW_LINE` | yes | no | no | JSON rejects these; Parquet rejects all text options. |
| `DATEFORMAT`, `TIMESTAMPFORMAT` | yes | yes | no | `DATE_FORMAT`/`TIMESTAMP_FORMAT` are CSV COPY aliases. |
| `ARRAY` | no | yes (default false) | no | `true` = one JSON array; `false` = NDJSON. |
| `COMPRESSION` | yes (`none`,`gzip`,`zstd`) | yes | yes (`snappy` default) | Extension mismatch creates a mislabeled file (`.csv` holding gzip). |
| `CODEC` | no | no | yes | Parquet alias for `COMPRESSION`; rejected for CSV. |
| `COMPRESSION_LEVEL` | no | no | yes | zstd only; `1`–`22`. |
| `ROW_GROUP_SIZE`/`CHUNK_SIZE`, `ROW_GROUP_SIZE_BYTES`, `ROW_GROUPS_PER_FILE` | no | no | yes | `ROW_GROUP_SIZE_BYTES` needs `preserve_insertion_order=false`. |
| `PARQUET_VERSION`, `KV_METADATA`, `FIELD_IDS`, `SHREDDING`, `DATA_PAGE_SIZE_LIMIT`, `DICTIONARY_SIZE_LIMIT`, `WRITE_BLOOM_FILTER`, `BLOOM_FILTER_FALSE_POSITIVE_RATIO`, `GEOPARQUET_VERSION`, `TIMESTAMP_IS_ADJUSTED_TO_UTC`, `WRITE_TIMESTAMP_AS_INT96` | no | no | yes | `SHREDDING` is VARIANT-only; `FIELD_IDS` can be `auto`. |
| `PARTITION_BY`, `PARTITION_PATH`, `ORDER_BY`, `OVERWRITE`, `OVERWRITE_OR_IGNORE`, `APPEND`, `FILENAME_PATTERN`, `PER_THREAD_OUTPUT`, `FILE_SIZE_BYTES`, `FILE_EXTENSION`, `WRITE_PARTITION_COLUMNS`, `USE_TMP_FILE`, `PRESERVE_ORDER`, `RETURN_FILES`, `RETURN_STATS` | yes | yes | yes | Multi-file options only bite with `PARTITION_BY`/`PER_THREAD_OUTPUT`/`FILE_SIZE_BYTES`. `PARTITION_PATH` requires `PARTITION_BY`. |
| `COMPRESSION` (BLOB format) | n/a | n/a | n/a | BLOB copy is one `BLOB` column; `FORMAT blob`. |

## Existing skill audit

| Skill | Claim or omission | Verdict | Fix |
|---|---|---|---|
| `duckdb-files` | "GeoJSON, Shapefile, and GeoPackage go to `duckdb-spatial`." | **wrong** for GeoJSON | 2.0 `json` reads/writes `.geojson`/`.geojsonl` natively; keep only Shapefile/GPKG in the spatial handoff. |
| `duckdb-files` | "A `.duckdb` database file goes to `duckdb-session`." | **thin** | 2.0 has `read_duckdb` / `FROM 'file.duckdb'`; files owns single-file reads, session owns attach/manage. |
| `duckdb-files` | Reader row: `.db, .sqlite, .sqlite3` → `ATTACH ... (TYPE sqlite)` | **wrong** for `.db` | `.db`/`.duckdb` are DuckDB files (`FROM` works); `.sqlite`/`.sqlite3` need `ATTACH` (bare paths do not dispatch). |
| `duckdb-files` | `.avro` → `INSTALL avro; LOAD avro;` then `read_avro` | **thin** | `read_avro` autoloads in 2.0; show `INSTALL/LOAD` only as the fallback the Catalog Error names. |
| `duckdb-files` | `.xlsx` → `INSTALL excel; LOAD excel;` then `read_xlsx` | **thin** | `read_xlsx` autoloads; `COPY ... (FORMAT xlsx)` is the exception and needs `LOAD excel`. |
| `duckdb-files` | Reader row groups `.txt`/`.tab` with `.csv`/`.tsv` | **thin** | `.tsv` bare-reads; `.tab`/`.txt` do not dispatch — say "explicit `read_csv`". |
| `duckdb-files` | Reader table uses `read_parquet` for `.pq` and `read_avro` for `.avro` rather than bare paths | **correct** | Bare `.pq`/`.avro` fail; the explicit function is required. Keep this pattern. |
| `duckdb-files` | "anything else → `DESCRIBE FROM 'path'` ..." | **correct** | Keep: the error names `read_csv`/`read_json`/`read_parquet`. |
| `duckdb-files` | "Do not build one macro ... A missing extension then fails the whole statement." | **correct** | Keep the rule, but say autoload makes the failure rare; the exact Catalog Error is the fallback. |
| `duckdb-files` | Preview: `sum(row_group_num_rows)` and `sum(row_group_compressed_bytes)` from `parquet_metadata` | **wrong** | Both repeat per column in a row group; a 3-column 5-row file reports 15 rows. Use `parquet_file_metadata(...).num_rows`, `file_size_bytes`, or `count(*)`. |
| `duckdb-files` | Sandbox: `allowed_paths` → `enable_external_access=false` → `allow_persistent_secrets=false` → `lock_configuration=true` | **correct** | Keep; state that the order is mandatory and extensions must load first. |
| `duckdb-files` | "Skip that sandbox for `s3://` ... `https://`." | **thin** | `enable_external_access=false` blocks remote reads too; the point is not to apply the local allow-list, not that remote is unrestricted. |
| `duckdb-files` | R2: "Rewrite `r2://bucket/key` to `s3://bucket/key` and set the R2 endpoint." | **wrong** | `TYPE r2` is scoped to `r2://` and derives the endpoint from `ACCOUNT_ID`; use `r2://` directly. |
| `duckdb-files` | GCS: `TYPE gcs, KEY_ID, SECRET` and `gs://` | **correct but thin** | Add "HMAC interoperability keys only"; mention `gcs://` alias. |
| `duckdb-files` | Azure: `INSTALL azure; LOAD azure;` then `credential_chain, ACCOUNT_NAME` | **thin** | Azure autoloads; public container only needs `PROVIDER config, ACCOUNT_NAME`. |
| `duckdb-files` | "`credential_chain` for S3 autoloads the `aws` extension." | **correct** | Keep; warn it validates at creation and fails without a profile. |
| `duckdb-files` | "DuckDB 2.0 treats `?s3_access_key_id=...` as part of the object key. The old behavior is `SET s3_enable_deprecated_url_parameters = true` after `LOAD httpfs`." | **correct** | Keep; add that the setting is `NULL` by default and only parses the documented S3 params. |
| `duckdb-files` | "List a prefix without downloading bodies. Select `filename`, `size`, `last_modified` only." | **correct** | Keep; `read_blob` projection pushdown verified on S3. |
| `duckdb-files` | Async scope: Parquet + uncompressed seekable UTF-8 CSV incl. DuckLake; JSON/DB synchronous. | **correct** | Keep; add defaults and "don't tune" guidance. |
| `duckdb-files` | "Leave `async_threads` and `read_ahead_depth` alone unless ... The I/O page has the knobs." | **thin** | Give the three `read_ahead_depth` values and the 4×/256 default; link the I/O page. |
| `duckdb-files` | Convert: `.csv` → `(FORMAT csv, HEADER)` | **correct but redundant** | `HEADER` is already true on write; drop it or mark it explicit. |
| `duckdb-files` | Convert: `.json` → `(FORMAT json, ARRAY true)` | **thin** | `.json` alone writes NDJSON; `ARRAY true` is a deliberate array choice, not inference. |
| `duckdb-files` | Convert: `.tsv` → `(FORMAT csv, HEADER, DELIMITER '\t')` | **correct and necessary** | `.tsv` inference writes comma-separated output; keep the explicit delimiter. |
| `duckdb-files` | "`PARTITION_BY (col)` works for Parquet and CSV directory output." | **thin** | JSON also partitions; add overwrite/append semantics and the non-empty-directory trap. |
| `duckdb-files` | "`CODEC 'zstd'` is the Parquet compression option" | **correct** | `CODEC` and `COMPRESSION` both work for Parquet; `CODEC` fails for CSV. |
| `duckdb-files` | `.xlsx` → `(FORMAT xlsx)` after install/load | **correct** | Default `HEADER` is false for XLSX; add `HEADER true` when headers are wanted. |
| `duckdb-files` | Missing from reader table: `.duckdb`, `.geojson`, `.geojsonl`, BLOB/text, DuckDB DB. | **thin** | Add `read_duckdb`, `read_blob`/`read_text`, GeoJSON; keep SQLite distinct. |
| `duckdb-files` | Preview uses `count(*)` and `LIMIT 20` | **correct** | Keep; note `count(*)` on Parquet is metadata-only locally and remotely. |
| `duckdb-variant` | "`VARIANT` is a binary column ... The `JSON` type is still text." | **correct** | Keep; this is the decision driver. |
| `duckdb-variant` | "Keep `JSON` when the user needs the original text bytes." | **correct but thin** | `VARIANT` loses whitespace, duplicate keys, and textual key order; only `JSON` round-trips them. |
| `duckdb-variant` | Create/load block: `42::VARIANT`, `'hello'::VARIANT`, `[1,2,3]::VARIANT`, struct literal, `'{"user":...}'::JSON::VARIANT` | **correct** | All five insert; note that a quoted `'42'::VARIANT` would be a string, not a number. |
| `duckdb-variant` | "`variant_typeof` returns the full type ... `variant_type` returns only the category." | **correct but thin** | Category vocabulary is physical (`BOOL_TRUE`, `INT8`, `TIMESTAMP_MICROS`), not SQL names. |
| `duckdb-variant` | "Extraction returns `VARIANT` from `variant_extract` and `VARCHAR` from `variant_extract_string`. Dot notation matches `variant_extract`." | **correct** | Add: `variant_extract_string` takes only string paths; non-scalars become JSON text. |
| `duckdb-variant` | Function table entries for `variant_array_length`, `variant_exists`, `variant_contains`, `variant_group_object`, `variant_group_array` | **correct but thin** | Add 0-on-object, keys-only, structural containment, exact error text, macro/window. |
| `duckdb-variant` | "`variant_normalize` and `variant_comparator` are for equality and sort order." | **thin** | `=` is already structural; `normalize` canonicalizes, `comparator` is a sort key. |
| `duckdb-variant` | "The functions page does not say whether `variant_extract` indexes lists from 0 or from 1. Project a sample row..." | **wrong** | 1-based; `d[0]` errors. Remove the uncertainty. |
| `duckdb-variant` | DB shredding threshold default 30000, `-1` off | **correct** | Keep; scope it explicitly to database files. |
| `duckdb-variant` | "Parquet writes can shred too. Auto-shredding follows the structure DuckDB sees." | **thin** | It follows the first row group; `variant_minimum_shredding_size` does not gate it. |
| `duckdb-variant` | `SHREDDING {'payload': 'STRUCT(...)'}` example | **correct** | Keep; add that it is a hint, not a schema contract. |
| `duckdb-variant` | "DuckDB reads shredded `VARIANT` Parquet, including files Snowflake wrote." | **thin** (documented, unprobed) | Label as documented; no interop test in this slice. |
| `duckdb-variant` | "The docs do not say what happens when later rows do not match a `SHREDDING` schema. Check a sample after the copy." | **wrong** | No error: mismatches are preserved (the unshredded `value` remains) and round-trip; non-objects and extra fields also survive. |
| `duckdb-variant` | "Delta tables have a separate shredding switch. See `duckdb-lakehouse`." | **correct** | Keep as a one-line cross-link; do not expand here. |
| `files/references/formats.md` | `read_avro` "Install and load first"; `ST_Read` listed for GeoJSON | **wrong** | Avro autoloads; GeoJSON goes through `json` (`st_read` needed explicit load in probe). |
| `files/references/formats.md` | JSON `format` default `array`; `maximum_object_size` "Reject larger objects" | **wrong / thin** | Effective default is `auto`; the size cap does not apply to NDJSON. |
| `files/references/formats.md` | "`parquet_metadata` gives row counts and compressed sizes ... use it for a remote preview" | **wrong** | Per-column duplication. Use `parquet_file_metadata.num_rows` / `file_size_bytes`. |
| `files/references/formats.md` | "`parquet_file_metadata` ... file-level key/value pairs" | **wrong** | That is `parquet_kv_metadata`; `parquet_file_metadata` is num_rows/version/encryption. |
| `files/references/formats.md` | Secrets: Azure `KEY_ID, SECRET`; HTTP `HEADERS`; R2 `TOKEN` | **wrong** | Azure config: `ACCOUNT_NAME`/`CONNECTION_STRING`; HTTP: `EXTRA_HTTP_HEADERS`; R2: `SESSION_TOKEN`. |
| `files/references/formats.md` | `http_retry_backoff` default 2; `fsync_mode` default `default` | **wrong** | Probed defaults are `4.0` and `STANDARD`. |
| `files/references/formats.md` | `WRITE_PARTITION_COLUMNS true` example | **wrong syntax** | Bare `WRITE_PARTITION_COLUMNS`; `= true` is a parser error. |

## Gaps worth adding

| Rank | Gap | Why an agent needs it | Home: SKILL.md or reference |
|---|---|---|---|
| 1 | Correct cheap Parquet count/size recipe (`parquet_file_metadata.num_rows`, `file_size_bytes`; never raw `sum(row_group_num_rows)`) | The current preview query silently multiplies row counts by column count; an agent will report wrong totals | SKILL.md (one line) + reference (why) |
| 2 | `.db` vs `.duckdb` vs `.sqlite` dispatch, plus `read_duckdb` | The current table sends DuckDB `.db` files to SQLite; `.sqlite` bare paths do not dispatch | SKILL.md reader table |
| 3 | Sandbox order, extension-before-lock, and `-safe` locking | Reversing the order fails; `-safe` cannot be relaxed with `allowed_paths` | SKILL.md (short block) |
| 4 | Autoload truth: most readers work without INSTALL/LOAD; exact Catalog Error and the two exceptions (`FORMAT xlsx`, `st_read`) | Agents add unnecessary installs, or fail offline without the fallback | SKILL.md (rule) + reference (table) |
| 5 | COPY write defaults (CSV header true, JSON NDJSON, XLSX header false, `.tsv` writes comma) | Conversion recipes currently over-specify or mis-describe defaults | SKILL.md convert table |
| 6 | Partitioned-write overwrite semantics: `OVERWRITE` vs `OVERWRITE_OR_IGNORE`, stale partitions, `APPEND`, non-empty dir error | Silent stale partitions are a data-correctness bug | reference (detail) + SKILL.md warning |
| 7 | VARIANT list index base (1-based), `variant_type` physical labels, `variant_extract_string` limits | These are the most likely runtime errors in VARIANT queries | duckdb-variant SKILL.md |
| 8 | VARIANT shredding is a hint: mismatch/extra/non-object fallback, Parquet not gated by the 30k setting | Removes the current "check a sample / docs don't say" uncertainty | duckdb-variant SKILL.md |
| 9 | JSON `ignore_errors` inserts NULL rows; JSON multi-file auto-unions keys while Parquet/CSV error | Agents carrying CSV habits misread results; multi-file behavior differs by format | reference (JSON) + files SKILL one-liner |
| 10 | COPY option applicability matrix (CSV vs JSON vs Parquet) | Agents pass `HEADER` to Parquet or `NULL` to JSON and get binder errors | reference only |
| 11 | Secrets: R2 uses `r2://`; `duckdb_secrets(redact:=false)` needs startup `-unredacted`; `duckdb_secret_type_parameters()` | Current R2 advice is wrong; redaction behavior is surprising | reference (secret matrix) + SKILL one-liner |
| 12 | `?s3_access_key_id=` default and the deprecated-URL switch | Agents paste presigned-style URLs and silently read 0 rows | reference (S3) |

## Traps and contradictions

| Trap | What happens | Correct move | Evidence |
|---|---|---|---|
| Summing `parquet_metadata.row_group_num_rows` | One value per column per row group; 5 rows × 3 columns reports 15 | Use `parquet_file_metadata(...).num_rows`, or `count(*)`, or `DISTINCT file_name,row_group_id,row_group_num_rows` | `P37` |
| Reversing sandbox order | `Cannot change allowed_paths when enable_external_access is disabled` | Set `allowed_paths`/`allowed_directories` before disabling external access | `P59` |
| Assuming `-safe` = the four-line sandbox | `-safe` also sets `lock_configuration=true`; `allowed_paths` cannot be added | Use `-safe` only when zero file access is intended; otherwise use the manual recipe | `P61` |
| `LOAD httpfs` after locking down | `Permission Error: Loading external extensions is disabled through configuration` | Install/load every extension first | `P60` |
| `.db` means SQLite | DuckDB claims `.db`; a DuckDB file reads correctly, a SQLite file must be attached | Use `.duckdb` for DuckDB, `.sqlite` for SQLite, and `ATTACH (TYPE sqlite)` for the latter | `P8` |
| `.pq` or `.avro` bare path | `Binder Error: No extension found ...`; neither suffix is registered for dispatch | `.pq`: use `read_parquet('x.pq')`; `.avro`: use `read_avro('x.avro')` | `P75` |
| `format='array'` on NDJSON | `Expected top-level JSON array ... first character is '{'` | Use `format='newline_delimited'`, `read_ndjson`, or omit `format` | `P26` |
| JSON `ignore_errors=true` | Bad NDJSON line becomes a row of NULLs, not a skipped row | Filter `WHERE key IS NULL` or pre-clean; do not assume CSV semantics | `P29` |
| `maximum_object_size` on NDJSON | Not enforced; a 20 MiB line read fine | Cap applies to array/unstructured objects only | `P28` |
| `read_csv(..., auto_detect=false)` without `columns` | `read_csv requires columns to be specified through the 'columns' option` | Pass `columns`; `columns` alone keeps dialect sniffing | `P14` |
| `null_padding=true` on a ragged file | Sniffer still refuses before padding; adding `strict_mode=false` truncates long rows | `ignore_errors=true` skips rows; `strict_mode=false` truncates; choose deliberately | `P21` |
| `buffer_size` smaller than a line | Misleading `Maximum line size ... exceeded` error | Raise `buffer_size` (≥ 4 lines) or `max_line_size` | `P22` |
| `COMPRESSION gzip` to a `.csv` name | File is gzip but `read_csv` infers `none` from `.csv` and fails with invalid unicode | Write `.csv.gz` or pass `compression='gzip'` on read | `P40` |
| `OVERWRITE_OR_IGNORE` on an existing partition root | Stale partitions from earlier runs survive; query returns old + new rows | Use `OVERWRITE` to clear the root, or delete the directory first | `P45` |
| `PARTITION_PATH` with non-Hive names | A later `hive_partitioning=true` scan fails `Hive partition mismatch` | Keep `key=value` segments, or read with `hive_partitioning=false` / per directory | `P46` |
| Writing all columns as partition columns | `No column to write as all columns are specified as partition columns` | Add `WRITE_PARTITION_COLUMNS` or keep a data column | `P47` |
| `?s3_access_key_id=` in an object URL | Treated as part of the key; known object returns 0 rows | Use a secret; only set `s3_enable_deprecated_url_parameters=true` for legacy URLs | `P55` |
| `duckdb_secrets()` shows redacted values even with `-unredacted` | Default `redact` argument is true | Call `duckdb_secrets(redact := false)` **and** start with `-unredacted`/`allow_unredacted_secrets` | `P52` |
| `variant_extract(v, 0)` | `Extracting index 0 from VARIANT(ARRAY) is invalid, indexes are 1-based` | Use 1-based indexes; JSON and LIST are different (`JSON` is 0-based) | `P63` |
| `variant_type(v) = 'BOOLEAN'` | Never true; booleans report `BOOL_TRUE`/`BOOL_FALSE` | Compare with `variant_typeof` or cast the value | `P64` |
| Forcing `SHREDDING` as validation | Mismatched rows do not error; they are preserved (the unshredded `value` remains) and round-trip | Treat `SHREDDING` as a storage hint; validate with `typeof`/casts if correctness matters | `P71` |
| Assuming `variant_minimum_shredding_size=-1` disables Parquet shredding | Parquet still writes `typed_value` | Scope the setting to database files; Parquet auto-shreds | `P70` |
| `json_set` value `'2'` | Third argument is `JSON`, so `'2'` is the number 2, not the string `"2"` | Pass `'"2"'` for a string; cast VARIANT→JSON→mutate→VARIANT | `P33` |
| `read_json(..., columns={'x':'VARIANT'})` | Binds, then `Not implemented Error: Cannot read a value of type VARIANT from a json file` | Read as `JSON`/typed columns, then cast `::VARIANT` | `P31` |

## What not to add

- A universal `read_any` macro. The current skill's rule is right: one reader per path; a macro makes a missing extension fail the whole statement.
- Full parameter dumps in `SKILL.md`. Keep them in `formats.md`; the top-level skill needs only the parameter that changes a decision (e.g. `format`, `columns`, `ignore_errors`, `schema`).
- `variant_bytes_to_variant` / `variant_to_parquet_variant` / `PARQUET_VARIANT`. Internal encodings; `variant_bytes_to_variant` only accepts the v1 binary scheme and is not a JSON parser.
- Delta/Hive metastore/Iceberg catalog setup. `duckdb-lakehouse` owns it; keep one cross-link for Delta's shredding switch.
- AWS credential-chain internals (SSO, IRSA, assume-role). The `aws` extension page owns them; the files skill needs only "config for keys, credential_chain when a profile exists".
- A JSONPath tutorial. A one-line "JSON uses `->`/`->>` with 0-based indexes" prevents the VARIANT mix-up; the rest is SQL.
- Benchmark numbers for async I/O, encryption, or row-group sizing. They date fast and do not change the command.
- `PREFIX`/`SUFFIX`/`FORCE_QUOTE`/`NEW_LINE` in the skill. Rare CSV-writing knobs; reference only.

## Probe log

```text
$ duckdb -no-agent -csv -c "SELECT version(), current_setting('threads'), current_setting('async_threads'), current_setting('read_ahead_depth'), current_setting('http_retries'), current_setting('http_retry_wait_ms'), current_setting('http_retry_backoff'), current_setting('http_client_pool_capacity'), current_setting('fsync_mode');"
v2.0.0,8,32,-1,3,100,4.0,32,STANDARD
```
`P1` `SELECT function_name, alias_of, parameters ... FROM duckdb_functions()` and `duckdb_extensions()`: all reader names above; `read_csv_auto`/`read_json_auto`/`parquet_scan` `alias_of=NULL`; `json`/`parquet` statically linked.
`P2` `FROM 'people.csv'`, `FROM 'tab.tsv'`, `FROM 't.tab'`, `FROM 'note.txt'`: first two OK; `.tab`/`.txt` → `Binder Error: No extension found that is capable of reading the file`.
`P3` `DESCRIBE FROM read_csv('late2.csv.gz')` → `v BIGINT`; `sample_size=-1` → `v VARCHAR`. `read_json('lines.jsonl')` with no `format` read 3 rows.
`P4` `SET autoinstall_known_extensions=false; SET autoload_known_extensions=false; FROM read_xlsx('missing.xlsx');` → Catalog Error naming `excel`, `INSTALL excel; LOAD excel;` and the two `SET ...=1` hints. Same for `read_avro` naming `avro`.
`P5` `FROM read_xlsx('missing.xlsx')` and `FROM read_avro('missing.avro')` with defaults → resolved the function and failed on the missing file (autoload succeeded). `COPY ... (FORMAT xlsx)` → `Catalog Error: Copy Function with name xlsx does not exist` until `LOAD excel`.
`P6` `SET autoload_known_extensions=false; ATTACH 'shop.sqlite' AS s (TYPE sqlite); SELECT * FROM s.items;` → `1,apple / 2,pear`.
`P7` `FROM 't.tab'` failed; `SELECT * FROM read_csv('note.txt')` → `hello / world`.
`P8` `FROM 'conflict.db'` (a DuckDB database) → `42`. `FROM 'shop.sqlite'` → `Binder Error: No extension found ...`. A SQLite DB copied to `shop2.db`: `FROM 'shop2.db'` → `Not implemented Error: read_duckdb can only be used to read DuckDB files ... is of type "sqlite"`; `ATTACH 'shop2.db' AS s (TYPE sqlite)` → rows `1,apple / 2,pear`.
`P9` `FROM read_duckdb('mydb.duckdb', table_name='t')` → `42`; `FROM 'mydb.duckdb'` → `42`; `table_name='v'` → `Binder Error: ... no tables matching ... Candidates: "t"`.
`P10` `SELECT * FROM 'pts.geojson'` → `POINT (0 1),1`; `read_json('pts.geojson', geojson:=true)` identical; `.geojsonl` identical.
`P11` `SELECT count(*) FROM st_read('pts.geojson')` → `Catalog Error ... exists in the spatial extension`; after `INSTALL spatial; LOAD spatial;` → `2`.
`P12` `SELECT filename,size,last_modified FROM read_blob('s3://noaa-ghcn-pds/ghcnd-stations.txt')` → `11441354, 2026-10-15 ...`; invalid UTF-8 `read_text` → `could not read ... as valid UTF-8 ... use read_blob`.
`P13` `DESCRIBE FROM read_csv('dates.csv')` → `Order ID BIGINT, When DATE, Amount BIGINT`; `normalize_names=true` → `order_id`, `_when`, `amount`.
`P14` `read_csv('people.csv', auto_detect=false)` → `read_csv requires columns to be specified through the 'columns' option`; with `header=true, columns={...}` → 3 rows.
`P15` `nullstr=['NA','']` → first two rows NULL; `force_not_null=['a']` returned zero-length strings.
`P16` `read_csv('dates.csv', dateformat='%d/%m/%Y')` → `2024-12-31, 2025-01-01`.
`P17` gzip 50k rows with `oops` at end: default → `BIGINT`; `sample_size=-1` → `VARCHAR`.
`P18` `all_varchar=true` → `typeof(age)=VARCHAR` for all rows.
`P19` `ignore_errors=true` on `ragged.csv` → only `1,2,3`; `store_rejects=true` → `reject_errors` row `CAST, "Oogie Boogie, three"`; `rejects_limit=1, rejects_line_size_limit=3` → `len=3, Oog`; `count(*)` hid the cast error while `SELECT name, age` exposed it.
`P20` `rejects_table='e4'` temp table existed; defaults `reject_scans`/`reject_errors`.
`P21` `null_padding=true` → sniffer error; `auto_detect=false, null_padding=true` → `4,5,NULL` and error on `6,7,8,9`; `+strict_mode=false` → `6,7,8` (extra field dropped).
`P22` `read_csv('people.csv', buffer_size=10)` → `Maximum line size of 10 bytes exceeded. Actual Size:14 bytes.`; `1000000` → OK.
`P23` `read_csv('multi/*.csv')` → `Schema mismatch ... Column "b" is missing`; `union_by_name=true` → `a,b,c` with NULLs.
`P24` `SELECT file_index, filename, * FROM read_csv([...], union_by_name=true)` → 0/1 and paths; `filename='src'` renamed the column.
`P25` `read_csv('hive/**/*.csv')` → `x,month,year` with `1,1,2024`; `hive_partitioning=false` → `x` only.
`P26` `read_json('arr.json', format='array')` → 2 rows; `read_json('lines.jsonl', format='array')` → `Expected top-level JSON array ... first character is '{'`; `read_json('lines.jsonl', "array"=true)` same error.
`P27` `read_json('arr.json', columns={'id':'BIGINT'})` → only `id`; `auto_detect=false` with columns → OK.
`P28` 20 MiB single object: `read_json('huge.json')` → `"maximum_object_size" of 16777216 bytes exceeded`; same bytes as one NDJSON line read fine.
`P29` `read_json('bad.jsonl')` → `Malformed JSON ...`; `ignore_errors=true` → rows `1, NULL, 3`; `arr.json` accepted the flag silently.
`P30` `read_json('jmulti/*.json', union_by_name=true)` → `a,b,c`; without it the same. Conflicting types both became `JSON`.
`P31` `DESCRIBE FROM read_json(..., columns={'tags':'VARIANT'})` shows `VARIANT`; execution → `Not implemented Error: Cannot read a value of type VARIANT from a json file`.
`P32` `COPY ... TO 'w_lines.json' (FORMAT json)` → `{"i":0}\n{"i":1}`; `ARRAY true` → `[ ... ]`; `COPY ... TO 'auto.jsonl'` → NDJSON; `FORMAT jsonl` → NDJSON.
`P33` `json_set('{"a":1}','$.b','2')` → `{"a":1,"b":2}`; `json_insert`/`json_replace` no-ops when path exists/missing; `json_set('{"a":1}','$.b.c','2')` creates `b.c`; `json_set(d,...)` on `VARIANT` → binder error.
`P34` `json_merge_patch('{"a":{"x":1,"y":2}}','{"a":{"y":null,"z":3}}')` → `{"a":{"x":1,"z":3}}`; `json_deep_merge` keeps `y`; `json_merge_patch_diff` → `{"c":null,"b":99,"d":4}`.
`P35` `read_parquet('nums.parquet', schema=MAP{'i':'VARCHAR'})` → `'schema' expects a STRUCT as the value type of the map`; with `{name:'j', type:'VARCHAR', default_value:NULL}` → `j`; adding an absent `k` with default 7 → column `extra` all 7.
`P36` `file_row_number=true` → 0..4; `file_row_group_number` (no flag) → 0; `binary_as_string=true` turns `BLOB` into `VARCHAR`.
`P37` 5 rows × 3 cols: `sum(row_group_num_rows)=15`, `count(*)=5`, `parquet_file_metadata.num_rows=5`; `sum(row_group_compressed_bytes)=447`, `sum(total_compressed_size)=149`.
`P38` `parquet_metadata` columns include `geo_bbox`, `geo_types`, `encoding_stats`, `stats_nan_count`; `parquet_schema` includes `duckdb_type`, `column_id`; `parquet_bloom_probe('nums.parquet','i',99)` → `false`.
`P39` `PRAGMA add_parquet_key('key256', '...'); COPY ... (ENCRYPTION_CONFIG {footer_key:'key256'})`; read without config → `File 'enc.parquet' is encrypted, but 'encryption_config' was not set`; `parquet_file_metadata` has no config parameter and fails the same way; `column_keys` → `Not implemented Error`.
`P40` `COPY ... TO 'people2.csv'` → header `name,age,city`; `COPY ... TO 'x/out.tsv'` → `a,b / 1,2` (comma); `COPY ... COMPRESSION gzip` to `.csv` → `file` says gzip, `read_csv` fails `Invalid unicode ... not utf-8`.
`P41` `CODEC 'zstd'` Parquet → `compression=ZSTD`; `CODEC` CSV → `Unrecognized option "codec" for csv`; `COMPRESSION_LEVEL 5` without zstd → `Compression level is only supported for the ZSTD compression codec`.
`P42` JSON `HEADER`/`DELIMITER`/`NULL` → `Unknown option ... (FORMAT JSON)`; Parquet `HEADER`/`DELIMITER`/`QUOTE`/`ESCAPE`/`NULL`/`DATEFORMAT`/`TIMESTAMPFORMAT` → `Unrecognized option`; `SHREDDING` CSV/JSON → `Unrecognized/Unknown option`.
`P43` `COPY ... TO 'x/one.blob' (FORMAT blob)` OK; two columns → `"COPY (FORMAT BLOB)" only supports a single BLOB column`.
`P44` `COPY ... PARTITION_BY (year,month)` → `pw/year=2024/month=1/data_0.parquet`; NULL partition → `g=__HIVE_DEFAULT_PARTITION__`; read back NULL.
`P45` second write to `pw2` → `IO Error: Directory "pw2" is not empty! Enable OVERWRITE option...`; `OVERWRITE_OR_IGNORE` kept `year=2024` and added `year=2026`; `OVERWRITE` left only `year=2025`; `APPEND` added `<uuid>.parquet` and kept all.
`P46` `ORDER_BY (v DESC)` → `30,20,10`; `PARTITION_PATH CASE ...` → `pw7/europe`, `pw7/region=us`; `read_parquet('pw7/**/*.parquet', hive_partitioning=true)` → `Hive partition mismatch`.
`P47` `WRITE_PARTITION_COLUMNS true` → file has `year,month`; `= true` → `Parser Error: syntax error at or near "="`; duplicate columns not returned on read.
`P48` `FILE_SIZE_BYTES 100000` on 200k rows → `493316` and `309445` bytes; `PER_THREAD_OUTPUT` → directory `pw4/data_0.parquet`.
`P49` `duckdb_secret_types()` after `LOAD httpfs` → `aws,gcs,http,huggingface,r2,s3`; `duckdb_secret_type_parameters()` S3 config 18 rows, credential_chain 19.
`P50` `CREATE SECRET s3region (TYPE s3, PROVIDER config, REGION 'eu-central-1')` → scope `['s3://','s3n://','s3a://']`; R2 secret → scope `['r2://']`, `endpoint=acct.r2.cloudflarestorage.com`.
`P51` `CREATE SECRET (TYPE s3, PROVIDER credential_chain)` → `Secret Validation Failure: no profile 'default' found ...` + region warning.
`P52` `duckdb_secrets()` → `secret=redacted`, `key_id` visible; `duckdb_secrets(redact:=false)` without flag → `Displaying unredacted secrets is disabled`; with `-unredacted` → `secret=SECRET_TEST`; `SET allow_unredacted_secrets=true` → `Cannot change ... while database is running`.
`P53` `CREATE PERSISTENT SECRET p3` with `SET secret_directory='secrets'` → `secrets/p3.duckdb_secret`, mode 600; `allow_persistent_secrets=false` → `Persistent secrets are disabled...`; temp secret still created; `DROP PERSISTENT SECRET p1` removed it.
`P54` `which_secret('s3://bucket/a/deep/file.parquet','s3')` → `b,TEMPORARY,memory`; unrelated path → 0 rows.
`P55` Plain public key → 1 row; same key + `?s3_access_key_id=x` → 0 rows; `glob` returned the whole URL. With `s3_enable_deprecated_url_parameters=true`, `?region=us-east-1` → `Invalid query parameters ... Supported: 's3_region', 's3_access_key_id', ...`.
`P56` `read_blob('s3://noaa-ghcn-pds/ghcnd-stations.txt')` → 1 row, 11441354 bytes; `read_parquet('https://raw.githubusercontent.com/apache/parquet-testing/master/data/alltypes_plain.parquet')` → 8 rows; `read_duckdb('https://blobs.duckdb.org/data/tpch-sf10.db', table_name='region')` → 5 rows; `hf://datasets/datasets-examples/doc-formats-csv-1/data.csv` → 4 rows.
`P57` defaults as P1; `duckdb_settings()` descriptions; `SET async_threads=1000` accepted; `SET fsync_mode='BOGUS'` → enum error.
`P58` `SET async_threads=10` → pool 16; `SET http_client_pool_capacity=8; SET async_threads=10` → pool stays 8; `RESET` → 16.
`P59` `SET allowed_paths=[people.csv]; SET enable_external_access=false;` → allowed file 3 rows, other file `Permission Error`; reverse order → `Cannot change allowed_paths when enable_external_access is disabled`.
`P60` `SET enable_external_access=false; LOAD httpfs;` → `Permission Error: Loading external extensions is disabled through configuration`; `INSTALL httpfs` → `Cannot access directory .../.duckdb/extensions/...`.
`P61` `duckdb -safe` read → `Permission Error`; `SET allowed_paths` → `Cannot change configuration option "allowed_paths" - the configuration has been locked`; `enable_external_access=false, lock_configuration=true`.
`P62` `duckdb_functions() WHERE function_name ILIKE 'variant%'` → the function set listed in the signatures table; `variant_equal` → `Catalog Error: Scalar Function with name variant_equal does not exist`.
`P63` `variant_extract([10,20,30]::VARIANT, 0)` → `indexes are 1-based`; `d[1]=10, d[3]=30`; `variant_extract_string(d,1)` → no matching function.
`P64` `variant_type`/`variant_typeof` over bool/tinyint/bigint/double/decimal/date/timestamp/blob → `BOOL_TRUE/BOOL_FALSE`, `INT8/INT64`, `DECIMAL(3, 1)`, `TIMESTAMP_MICROS`.
`P65` `{"a":1,"a":2}::JSON` keeps both; `::VARIANT` → `{'a': 2}`; `variant_keys` → `[a]`; whitespace equality false for JSON, true for VARIANT.
`P66` `1::VARIANT = 1.0::VARIANT` → true; `variant_normalize` equality true; `variant_comparator` BLOB; `ORDER BY` mixed → `true, 1.5, 2, a, NULL`.
`P67` `variant_contains` matrix → `true,true,true,false`; `variant_array_length({'a':1})` → 0; `variant_keys([1,2])` → `[]`; `variant_exists([1,2],'1')` → false.
`P68` `variant_group_object` → `{'a':1,'b':2}`; duplicate → `duplicate key "a"`; NULL key → `key cannot be NULL`; `variant_group_array` → `[0,1,2]`, `[1,NULL]`, window `[0] / [0,1] / [0,1,2]`.
`P69` `duckdb_settings()` → `variant_minimum_shredding_size=30000`; `pragma_storage_info` segment count 20 (shredded) vs 25 (`-1`).
`P70` `SET variant_minimum_shredding_size=-1; COPY ... FORMAT parquet` → `parquet_schema` still has `typed_value` struct.
`P71` `SHREDDING {'payload':'STRUCT(name VARCHAR, age INTEGER)'}` with `age='notanint'` → no error, reads back `notanint`; `[1,2]`/`42` → read back as-is; extra field `extra` survived; `NOTATYPE` → `Type with name NOTATYPE does not exist`; unknown column → `VARIANT by name "nope" ... not found`.
`P72` `FORMAT csv, SHREDDING` → `Unrecognized option "shredding" for csv`; JSON → `Unknown option`.
`P73` `{'a':1}::VARIANT::VARCHAR` → `{'a': 1}`; `::JSON` → `{"a":1}`; JSON COPY of VARIANT → `{"v":{"a":1,...}}`; CSV COPY → `{'a': 1}`.
`P74` `GROUP BY d`, `DISTINCT d`, `ORDER BY v` on VARIANT → counts 2/1; order `true,1.5,2,a,NULL`.
`P75` `FROM 'nums.pq'` and `FROM 'u1.avro'` → `Binder Error: No extension found that is capable of reading the file`; `FROM 'lines.ndjson'` → 3 rows; `read_parquet('nums.pq')` and `read_avro('u1.avro')` → OK.

## Open questions

- `read_duckdb` with `schema_name` was not probed (only `table_name` on a single-schema database). A multi-schema DuckDB file would settle whether `schema_name` is required and how it interacts with `table_name`.
- Snowflake-written shredded VARIANT Parquet is documented but not probed here. A sample file would settle `variant_typeof` fidelity and whether Snowflake's `typed_value` layout matches DuckDB's reader.
- `read_json` `union_by_name`: no observable effect in three probes (different keys, conflicting types, nested structs). Source inspection or a file where the sniffer samples only the first file would settle whether the flag is ever consulted.
- Exact `http_client_pool_capacity` formula: observed 32 at `threads=8, async_threads=32` and 16 at `async_threads=10`; docs say "derived automatically", not the formula.
- `variant_minimum_shredding_size` behavior on reads of existing files and on compaction/VACUUM is unprobed; only write-time storage was measured.
