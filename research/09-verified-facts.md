# Verified facts

Binary: DuckDB 2.0.0 (Cyanoptera) `d54cbbe3df`, run 2026-10-22 on macOS arm64.

`scripts/probe.py` re-runs the automated rows. The rest record a manual probe and the command that produced it. A fact used in a skill must appear here or cite a manual page.

## Automated

Run `python3 scripts/probe.py --network --write research/probe-results.txt`.

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
| 54 | `COPY FROM DATABASE` needs an empty target | copy into a database that already has the table | `Table with name "t" already exists!` |
| 55 | A native file allows one writer or many readers, not both | writer plus read-only process | lock conflict; two read-only processes coexist |
| 56 | `ATTACH IF NOT EXISTS` is keyed on the alias | same alias, different path | silent no-op |
| 57 | A missing path in `ATTACH` is created as a 69 file | `ATTACH IF NOT EXISTS 'missing.db'` | file created, header 999 |
| 58 | `match_bm25` has ten parameters in 2.0 | bind a wrong named argument | candidate list includes `field_weights`, `field_b`, `scoring_model`, `tie_breaker` |
| 59 | Filtering the BM25 alias needs a subquery | same-SELECT `WHERE score IS NOT NULL` | `Alias "score" referenced - but the expression has side effects` |
| 60 | `ORDER BY score` works without a subquery | same-SELECT order | correct top rows |
