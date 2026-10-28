# Verified facts

Binary: DuckDB 2.0.0 (Cyanoptera) `d54cbbe3df`. The first pass ran on 2026-10-22 on macOS arm64. The diagnostics pass ran on 2026-10-26 on Linux x86_64.

`scripts/probe.py` re-runs the automated rows. The rest record a manual probe and the command that produced it. A fact used in a skill must appear here or cite a manual page.

## Automated

Run `python3 scripts/probe.py --network --write research/probe-results.txt`. The table below is the first-pass set. The next-phase probes are recorded separately below.

| # | Fact | Probe | Observed |
| --- | --- | --- | --- |
| 1 | The binary is 2.0 | `SELECT version()` | `v2.0.0` |
| 2 | Lambda syntax is `lambda x: ...` | `list_transform([1,2,3], lambda x: x + 1)` | `[2, 3, 4]` |
| 3 | The arrow form is rejected | `list_transform([1], x -> x + 1)` | `Deprecated lambda arrow (->) detected` |
| 4 | `$x` and `getvariable` agree | `SET VARIABLE x = 7; SELECT $x, getvariable('x')` | `7`, `7` |
| 5 | Integer division by zero raises | `SELECT 1 // 0` | `Invalid Input Error: Division by zero` |
| 6 | `TRY` returns NULL and `/` returns inf | `SELECT TRY(1 // 0), 1 / 0` | `NULL`, `Infinity` |
| 7 | Nested schemas cannot be on the search path | `CREATE SCHEMA s; CREATE SCHEMA s.e; USE s.e` | `nested schemas cannot be used in the search path` |
| 8 | The nested schema is visible through `parent_schema` | `duckdb_schemas()` | row `schema_name='e'`, `parent_schema='s'` |
| 9 | A new file is storage v2.0.0 | `ATTACH 'default.duckdb'` then `tags['storage_version']` | `v2.0.0+` |
| 10 | `-storage-version v1.5.6` writes a 1.5-era file | same, with the flag | `v1.5.0+` |
| 11 | `variant_typeof` returns the physical type | `variant_typeof(42::VARIANT)` | `INT32` |
| 12 | `variant_extract` indexes lists from 1 | `variant_extract([10,20]::VARIANT, 1)` | `10` |
| 13 | Index 0 is rejected | `variant_extract([10,20]::VARIANT, 0)` | `indexes are 1-based` |
| 14 | A row-level INSERT trigger works | `AFTER INSERT ... FOR EACH ROW` | log row present |
| 15 | `BEFORE ... FOR EACH ROW` is not implemented | same with `BEFORE` | `BEFORE FOR EACH ROW triggers are not yet supported` |
| 16 | `sqlite_master(path)` is gone | `SELECT sqlite_master('x')` | `Scalar Function with name sqlite_master does not exist` |
| 17 | `read_duckdb` reads a database file directly | `SELECT * FROM read_duckdb('src.duckdb')` | `42` |
| 18 | `COPY FROM DATABASE` copies a schema | copy `a` to `b`, select | `1` |
| 19 | `NEAREST k BY SIMILARITY` works | fixed-size `DOUBLE[2]` arrays | two nearest rows |
| 20 | `GROUP BY unnest(col)` works | list column with duplicates | counts `a=1, b=3, c=1` |
| 21 | `MERGE INTO` updates a match | `WHEN MATCHED THEN UPDATE` | `20` |
| 22 | `EXPLAIN (SQL)` returns executable SQL | `EXPLAIN (SQL) SELECT 42` | `SELECT CAST(42 AS INTEGER) AS "42"` |
| 23 | Agent mode truncates a large result | `-agent`, `range(2000)` | `first 20 and last 20 of 2000 rows`, hash |
| 24 | `-csv` disables automatic agent mode | `-csv`, `SELECT 42` | plain CSV, no agent banner |
| 25 | The docs index has `2.0` and `blog` only | attach the remote index, count by version | `2.0=2702`, `blog=1006` |

## Diagnostics pass

Numbers below are local to this pass and use the `D` prefix.

| # | Fact | Probe | Observed |
| --- | --- | --- | --- |
| D1 | `EXPLAIN (FORMAT JSON)` returns an array and no actuals | `EXPLAIN (FORMAT JSON) SELECT count(*) ...` | root `UNGROUPED_AGGREGATE`; no `intermediate_rows` |
| D2 | `EXPLAIN ANALYZE (FORMAT JSON)` returns one object with `operator`, `query`, `io`, `system` | same query with `ANALYZE` | object sections present; `TABLE_SCAN` has `rows_scanned` |
| D3 | `EXPLAIN ANALYZE` ignores CLI `-json` | `duckdb -json -c "EXPLAIN ANALYZE SELECT 42"` | text profile with `Total Time:`, not JSON |
| D4 | `legacy_metrics_format` returns a flat object | set the setting, then `EXPLAIN ANALYZE (FORMAT JSON)` | `latency`, `children`, `operator_type`; no `operator` |
| D5 | Operator timings are exclusive and sum to `query.cpu_time` | 4-thread 5M-row aggregate | sum 0.05118432 s; `cpu_time` 0.05118432 s; `total_time` 0.055123027 s |
| D6 | `system.peak_temp_dir_size > 0` proves a spill | 100 MB limit, 2M-row `ORDER BY` | `peak_temp_dir_size=98271232` |
| D7 | `tracked_metrics` restricts `json`, not `query_tree` | `tracked_metrics=['query.total_time']` | JSON has only `query.total_time`; query_tree keeps the tree |
| D8 | A cross product can omit `Estimated Cardinality` | `EXPLAIN (FORMAT JSON) SELECT count(*) FROM a, b` | `CROSS_PRODUCT` with empty `extra_info` |
| D9 | The plan linter finds a cross product, a non-sargable scan, a sargable lookup, and a metadata-only count, and rejects a hidden statement | `plan_lint.py --self-test` | four `PASS` plan lines plus `PASS write guard` |
| D10 | A metadata-only `count(*)` can return `{"result":"error"}` with no operator tree | `EXPLAIN ANALYZE (FORMAT JSON) SELECT count(*) FROM 'sorted.parquet'` | `{"result":"error"}` while the query returns 100000 |
| D11 | `rows_scanned` is scan-reported, not a portable emitted-row count | base-table scan with no matches; Parquet scan with no matches | base table `rows_scanned: 20000000`, `intermediate_rows: 0`; Parquet `rows_scanned: 0` |
| D12 | Row-group denominator is after file-list pruning | Hive filter | `Scanning Files: 1/6`, `Row Groups Scanned: 1/1` |
| D13 | Data Read and Data Written include spill | 100 MB-limit sort | `Data Written: 62.2 MB`, `peak_temp_dir_size: 60817408` |
| D14 | Text timings can print `0µs` for a real multi-millisecond operator | JSON 0.006676964 s | text `0µs` |
| D15 | `explain_output='all'` concatenates three JSON documents | logical, optimized, physical | `json.load` fails |
| D16 | `profiling_output` is last-statement-wins | two SELECTs, one file | file holds the second query |
| D17 | `operator.cpu_time` is advertised but not emitted | `duckdb_available_metrics()` vs operator JSON | no `cpu_time` key |
| D18 | `ROW_GROUP_SIZE` rounds up to a 2,048 multiple | 2,049 -> 4,096; 3,000 -> 4,096 | groups 4,096 |
| D19 | `FILE_SIZE_BYTES` overshoots | 100 KB target | 124,230 and 77,551 bytes |

## Integration pass

Numbers below use the `E` prefix. The full probe log and decisions are in `slices/13-search-sharing-integrations.md`.

| # | Fact | Probe | Observed |
| --- | --- | --- | --- |
| E1 | FTS `incremental=1` covers `INSERT` and `DELETE`, not `UPDATE` | update a body, query old and new terms | old term 1, new term 0; delete+insert repaired it |
| E2 | Incremental FTS needs a `NOT NULL` id | nullable `UNIQUE` id | `requires the document id column to be NOT NULL` |
| E3 | A same-select `match_bm25` alias filter fails | `WHERE score IS NOT NULL` in the same select | `Alias "score" referenced - but the expression has side effects` |
| E4 | HNSW needs the index metric to match the query function | cosine index, distance vs similarity | distance `Hnsw Index Scan`; similarity `Seq Scan` + `Top N` |
| E5 | HNSW persistence flag gates creation, not reads; `LOAD` before `SET` | file DB create and reopen | create failed without flag; reopen worked without it |
| E6 | HNSW ignores `OFFSET` on 2.0.0 | offsets 1, 5, 10, 50 | first page repeated |
| E7 | HNSW memory is outside `memory_limit` | official limitations page | documented |
| E8 | Bare `LIMIT/OFFSET` over Parquet can duplicate and drop rows | 30k rows, 6 groups, 3k pages, 4 threads, insertion order off | 30k total, 20,870 distinct, 9,130 duplicated and missing |
| E9 | `file_row_number` range pagination is stable per file | 3k pages | 30k distinct; range resets per file |
| E10 | A views-only catalog holds definitions, not data | 268 KB catalog over 100k Parquet | read-only attach and query; moved data breaks it |
| E11 | dbt v2 has a built-in DuckDB adapter; bundled driver cannot load extensions | dbt docs and release | `dbc install duckdb` required; `dbt-duckdb` is v1 |
| E12 | Metabase 1.5.6.0 and Grafana 0.4.6 bundle DuckDB 1.5.6; Superset caps below 2.0 | release assets, `pyproject.toml` | cannot read storage 69 |
| E13 | `duckdb_mcp` 2.4.0 ships for 2.0; MotherDuck local server 1.1.0 pins 1.5.6 | extension page and releases | documented |
| E14 | Async I/O covers Parquet, uncompressed CSV, and native storage; JSON is synchronous | official I/O page | documented |
| E15 | NULL type, `X'…'`/`B'…'`, and factorial changed | probes | `"NULL"`; `BLOB`/`BIT`; `2 * 3!` = 12 |
| E16 | `duckdb -serve` stores an unencrypted token and exposes writes | isolated HOME, remote write | token file mode 600; remote write succeeded |
| E17 | `allowed_directories`, `allowed_paths`, `disabled_filesystems` differ | sandbox probes | tree, exact file, local-only block; HTTPS needs CA |
| E18 | `VACUUM` does not reclaim; `CHECKPOINT` frees blocks | delete, vacuum, checkpoint | 394 to 211 used blocks; file size unchanged |
| E19 | DuckDB-file DuckLake catalog is one writer; readers must all be `READ_ONLY` | two-process attach | lock conflict; two read-only attaches worked |
| E20 | A `SELECT *` view blocks VARIANT extraction pushdown | 1M-row direct vs view | 3 ms direct, 149 ms view; extracted view restores pushdown |
| E21 | Remote Parquet caches help repeated scans, not a cold query | 50-file HTTP range server | cold 101 requests either way; second query 202 vs 102 |
| E22 | A filter inside `NEAREST ... BY DISTANCE` changes the ranking key | filtered nearest join vs CTE | non-nearest row; CTE returns the correct row |
| E23 | Trigger average needs an `AFTER UPDATE` statement trigger | announcement example | insert/delete matches; update stays stale; statement update trigger fixes it |
| E24 | ADBC DBAPI is not auto-commit; Ibis 12 does not support 2.0 | ADBC probe and Ibis guide | write lost without `commit()`; pin `duckdb<2` |

## Manual

| # | Fact | Command | Observed |
| --- | --- | --- | --- |
| 26 | Agent mode writes its banner and JSON errors to stderr | `duckdb -agent -c "SELECT 1//0"` | stdout has the table header, stderr has the banner and `{"exception_type":"Invalid Input",...}` |
| 27 | `-json` writes a partial `[` to stdout on error | `duckdb -json -c "SELECT 1//0"` | stdout `[`, stderr text error |
| 28 | `EXPLAIN ANALYZE` ignores `-json` | `duckdb -json -c "EXPLAIN ANALYZE SELECT 42"` | box-drawing profile, not JSON |
| 29 | `-safe` allows the database path but blocks other file access | `duckdb -safe s.duckdb -c "SELECT * FROM t"` then `FROM 's.duckdb'` | first succeeds, second is `Permission Error` |
| 30 | `max_execution_time` interrupts a query | `SET max_execution_time=50; SELECT count(*) FROM range(1000000000)` | `INTERRUPT Error: Query exceeded maximum execution time` |
| 31 | A pinned file keeps its storage version after a write | create with `-storage-version v1.5.6`, reopen, insert, checkpoint | `v1.5.0+` |
| 32 | A clean exit checkpoints and removes the WAL | create a 100k-row table, exit, list files | no `.wal` |
| 33 | `checkpoint_on_detach` is an enum, not a boolean | `SET checkpoint_on_detach=true` | `unrecognized value "true" for enum "CheckpointOnDetach"` |
| 34 | `.maxrows` controls the agent truncation | `printf '.maxrows 3\nSELECT range FROM range(10);\n' \| duckdb -agent` | three rows plus `… 7 rows omitted …` |
| 35 | `duckdb_schemas()` has `parent_schema`, not `schema_oid` | `DESCRIBE SELECT * FROM duckdb_schemas()` | columns include `parent_schema`, `parent_schema_oid` |
| 36 | `duckdb_tables()` has `schema_oid` but no parent name | `DESCRIBE SELECT * FROM duckdb_tables()` | columns end at `sql`; no `parent_schema` |
| 37 | `variant_type` returns `OBJECT` for an object | `variant_type({'a':1}::VARIANT)` | `OBJECT` |
| 38 | Empty structs use `STRUCT`, not `STRUCT()` | `SELECT row() AS s, NULL::STRUCT AS n` | `[]`, `NULL` |
| 39 | `array_cosine_similarity` needs a fixed-size array | `::DOUBLE[]` versus `::DOUBLE[2]` | the variable-length cast fails to bind |
| 40 | `-readonly` opens a database without write access | `duckdb -readonly r.duckdb -c "INSERT ..."` | write rejected |
| 41 | `variant_extract` out of range returns NULL | `variant_extract([10,20]::VARIANT, 4)` | `NULL` |
| 42 | `variant_comparator` returns a BLOB sort key | `typeof(variant_comparator({'a':1}::VARIANT))` | `BLOB` |
| 43 | `~` is a partial match in 2.0 | `SELECT 'abc' ~ 'b'` | `true`; `regex_match_operator_semantics` is `partial` |
| 44 | `decimal_division` is exact with two DECIMAL operands | `decimal_division(10.00, 4.00)` | `2.500000` |
| 45 | `SECURE VIEW` creates a usable view | create, insert, select | `1` |
| 46 | An R-tree index produces an index scan | `CREATE INDEX ... USING RTREE`, `EXPLAIN` | `Rtree Index Scan` |
| 47 | `read_parquet` can rename and cast with `schema` | `schema = MAP {'a': {...}}` | `renamed = 1` |
| 48 | `checkpoint_on_detach` accepts `ENABLED` | `SET checkpoint_on_detach = 'ENABLED'` | setting reads `ENABLED` |
| 49 | A default 1.5.6 file is storage 64 | create with the 1.5.6 binary, read the header | `0x40` (64), tag `v1.0.0+` |
| 50 | Version 68 is opt-in on 1.5.6 | create with `-storage-version v1.5.6` | `0x44` (68), tag `v1.5.0+` |
| 51 | `ATTACH ... (STORAGE_VERSION 'latest')` plus a write upgrades an old file | attach a 68 file with `latest`, create a table | tag `v2.0.0+`; 1.5.6 refuses it |
| 52 | A lower `STORAGE_VERSION` on an existing file errors | attach a 69 file with `v1.5.6` | `cannot initialize database with storage version 68` |
| 53 | `EXPORT DATABASE` defaults to CSV | export a table | `schema.sql`, `load.sql`, `t.csv` |
| 54 | `COPY FROM DATABASE` permits an unrelated target table | copy `s.t` into a target that already has `other` | succeeds; a target with `t` fails with `Table with name "t" already exists!` |
| 55 | A native file allows one writer or many readers, not both | writer plus read-only process | lock conflict; two read-only processes coexist |
| 56 | `ATTACH IF NOT EXISTS` is keyed on the alias | same alias, different path | silent no-op |
| 57 | A missing path in `ATTACH` is created as a 69 file | `ATTACH IF NOT EXISTS 'missing.db'` | file created, header 999 |
| 58 | `match_bm25` has ten parameters in 2.0 | bind a wrong named argument | candidate list includes `field_weights`, `field_b`, `scoring_model`, `tie_breaker` |
| 59 | Filtering the BM25 alias needs a subquery | same-SELECT `WHERE score IS NOT NULL` | `Alias "score" referenced - but the expression has side effects` |
| 60 | `ORDER BY score` works without a subquery | same-SELECT order | correct top rows |

## Next phase

Rows 61-77 are automated in `scripts/probe.py`. Row 78 and the URL checks in row 79 run under `--network`. Rows 80-82 are manual because they depend on the browser or the JSON profile shape.

| # | Fact | Command | Observed |
| --- | --- | --- | --- |
| 61 | `EXPLAIN` shows estimated rows and does not execute | `EXPLAIN SELECT count(*) FROM t WHERE id < 10` | `~N rows`; no `Total Time` |
| 62 | `EXPLAIN ANALYZE` shows actual rows and timing | same query with `ANALYZE` | `10 rows`, `Total Time` |
| 63 | `EXPLAIN ANALYZE` executes DML | `CREATE TABLE t; EXPLAIN ANALYZE INSERT INTO t SELECT range FROM range(3); SELECT count(*)` | count is `3` |
| 64 | `EXPLAIN (FORMAT JSON)` returns a plan tree | `EXPLAIN (FORMAT JSON) SELECT 42` | node `PROJECTION` with `extra_info` |
| 65 | A Parquet filter prunes row groups | sorted 100k-row file, `ROW_GROUP_SIZE 10000`, `WHERE id = 99999` | `Row Groups Scanned: 1 / 10` |
| 66 | A non-sargable filter scans every row group | `CAST(d AS VARCHAR) LIKE '2024-01%'` on a sorted date file | `Row Groups Scanned: 5 / 5` |
| 67 | `parquet_file_metadata` has one row per file | 10 rows, 3 columns | `sum(num_rows)=10` |
| 68 | `parquet_metadata` repeats row-group rows per column | same file | `sum(row_group_num_rows)=30` |
| 69 | Schema drift errors on a glob by default | two files with different columns | `schema mismatch in glob` |
| 70 | `union_by_name` fills missing columns with NULL | same two files | two rows; missing fields are `NULL` |
| 71 | Partitioned COPY round-trips rows | `PARTITION_BY (y,m)`, `RETURN_FILES` | `Count=9`, `Files=[...]`; footer rows `9` |
| 72 | Partitioned COPY refuses a non-empty target by default | rerun without overwrite | `Directory "..." is not empty` |
| 73 | `OVERWRITE_OR_IGNORE` leaves stale partitions | write two months, rerun one month | old month remains; `count=2` |
| 74 | `OVERWRITE` removes stale partitions | same case with `OVERWRITE` | only the new month remains; `count=1` |
| 75 | CSV rejects one row per error | one line with two bad columns | `rows=2`, `distinct_lines=1` |
| 76 | `ROW_GROUP_SIZE` below 2048 is raised | `ROW_GROUP_SIZE 1000` on 10k rows | full groups have `2048` rows; final group `1808` |
| 77 | JSON `ignore_errors` nulls a malformed line | three-line JSONL with one bad line | three rows; middle row has `NULL` fields |
| 78 | `duckdb -ui` installs the separately published `ui` extension from `core` | `INSTALL ui` during and after the 2.0.0 release window | 404 before the promotion; 200 after `00:35:22Z` on 2026-10-22 |
| 79 | The 2.0.0 `ui` extension is promoted from `core_nightly` to `core` and is not built for every platform | compare `Last-Modified` and SHA; HEAD each platform URL | nightly `20:12:50Z`, core `00:35:22Z`, same `b4f0b9bb12`; 404 on `osx_amd64` and `windows_arm64` |
| 80 | `EXPLAIN (FORMAT WEB)` works without the UI extension | `EXPLAIN (FORMAT WEB) SELECT 42` | writes a temporary HTML file and opens it |
| 81 | `duckdb -ui -readonly` is unsupported | read the UI page | the UI writes notebook state; use a separate UI catalog |
| 82 | `EXPLAIN ANALYZE (FORMAT JSON)` is an object, not an array | `EXPLAIN ANALYZE (FORMAT JSON) SELECT ...` | `io`, `operator` tree, `type=TABLE_SCAN`, `row_groups_scanned` |
