# Verified facts

Binary: DuckDB 2.0.0 (Cyanoptera) `d54cbbe3df`, run 2026-10-22 on macOS arm64.

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
| 25 | The docs index has `2.0` and `blog` only | attach the remote index, count by version | `2.0=2695`, `blog=999` |

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
