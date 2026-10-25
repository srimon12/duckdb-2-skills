# Trigger evals

Run these by hand after a description change. Give the agent only the prompt, in a fresh session with the pack installed. It passes when it loads the expected skill first and does not load a competing one.

A description that needs this table explained is too weak. The prompt should be something a real user would type.

## Router

| # | Prompt | Expected first skill | Should not load |
| --- | --- | --- | --- |
| 1 | `duckdb --version` prints 1.5.6, what do I do? | `duckdb` | `duckdb-migrate` before the version is confirmed |
| 2 | Read this parquet file and tell me the columns. | `duckdb-files` | `duckdb-sql`, `duckdb-lakehouse` |
| 3 | Attach sales.duckdb and keep it for the next command. | `duckdb-session` | `duckdb-files` |
| 4 | Query the Iceberg table in our REST catalog. | `duckdb-lakehouse` | `duckdb-files` |
| 5 | Why does `x -> x + 1` fail? | `duckdb-sql` | `duckdb-docs` |
| 6 | Serve this database to another DuckDB on my laptop. | `duckdb-quack` | `duckdb-session` |
| 7 | Install the spatial extension and update it. | `duckdb-extensions` | `duckdb-spatial` |
| 8 | What does the 2.0 manual say about `variant_extract`? | `duckdb-docs` | `duckdb-variant` |
| 9 | Our 1.5 database will not open in 2.0. | `duckdb-migrate` | `duckdb-session` |
| 10 | This pandas cell prints the query twice. | `duckdb-python` | `duckdb-sql` |
| 11 | Find coffee shops within 2 km of Times Square. | `duckdb-spatial` | `duckdb-files` |
| 12 | Store this JSON blob without flattening it. | `duckdb-variant` | `duckdb-files` |
| 13 | Save all my attached databases and settings for tomorrow. | `duckdb-session` | `duckdb` |
| 14 | Read CSV from an S3 bucket with secret credentials. | `duckdb-files` | `duckdb-quack`, `duckdb-sql` |
| 15 | Write new partitions into our Apache Iceberg table. | `duckdb-lakehouse` | `duckdb-files` |
| 16 | Convert PyCapsule Arrow stream to DuckDB relation zero-copy. | `duckdb-python` | `duckdb-files` |
| 17 | Allow a frontend app to query Quack server directly with public token. | `duckdb-quack` | `duckdb-session` |
| 18 | This query takes 40 seconds and I do not know why. | `duckdb-profile` | `duckdb-sql`, `duckdb-files` |
| 19 | EXPLAIN ANALYZE says 10 rows but the join returns 4 million. | `duckdb-profile` | `duckdb-sql` |
| 20 | Ingest this CSV into partitioned Parquet and keep the bad rows. | `duckdb-files` | `duckdb-sql`, `duckdb-session` |
| 21 | Open this parquet in a local UI. | `duckdb` | `duckdb-files`, `duckdb-profile` |
| 22 | How do I migrate our DuckLake 1.0 catalog to 1.1? | `duckdb-lakehouse` | `duckdb-docs` |
| 23 | Distance in meters between two lon/lat points. | `duckdb-spatial` | `duckdb-docs` |

## Skill-specific

### `duckdb`

| Prompt | Expected action |
| --- | --- |
| Run `SELECT 42` so I can read the result. | `duckdb -agent -c`, not `-csv` |
| Parse this result in a script. | `-json`, not `-agent` |
| The output is a box drawing under my agent. | check `~/.duckdbrc`; rerun with `-no-init` |
| The footer says `first 20 and last 20 of 1001 rows`. Is that the full answer? | no; it is a sample. Run `count(*)` or an aggregate |
| Safe mode blocked the file I named. | explain that `-safe` blocks external access; use the SQL sandbox for one named file |
| Open this in a local UI. | `duckdb -ui`; use `-box` if the extension cannot install |

### `duckdb-sql`

| Prompt | Expected action |
| --- | --- |
| Write a lambda that doubles each element. | `lambda x: x * 2` |
| Group by every non-aggregate column. | `GROUP BY ALL` |
| Insert a row by column name. | `INSERT ... BY NAME` |
| Create an audit trigger for updates. | statement-level `AFTER UPDATE ... REFERENCING OLD/NEW TABLE` |
| Create a `BEFORE UPDATE FOR EACH ROW` trigger. | refuse; not implemented in 2.0 |
| Why did `1 // 0` start failing? | integer division by zero now errors; `TRY` or the setting |
| Update every row from a source table that has duplicate keys. | deduplicate the source, count matches, run, then verify; `UPDATE ... FROM` picks one unspecified row |

### `duckdb-profile`

| Prompt | Expected action |
| --- | --- |
| This query takes 40 seconds. | `EXPLAIN`, then `EXPLAIN ANALYZE`; find the operator with the estimate/actual gap |
| EXPLAIN ANALYZE says 10 rows but the join returns 4 million. | inspect join sides; do not add `LIMIT` first |
| My Parquet filter reads every row group. | check for a function or cast around the filter column; rewrite as a range |
| The query runs out of memory. | check the blocking operator before `memory_limit`; then check `temp_directory` and `preserve_insertion_order` |
| Explain this plan without running the query. | `EXPLAIN`, not `EXPLAIN ANALYZE` |
| Give me a ranked diagnosis of this plan, with evidence. | capture `EXPLAIN ANALYZE (FORMAT JSON)` and run the plan linter; report findings, not an operator lecture |
| Should I raise memory_limit? | only after the blocking operator's rows are reduced; show `system.peak_temp_dir_size` first |
| Open this plan in a browser. | `EXPLAIN (FORMAT WEB)`; `duckdb -ui` for the notebook UI |

### `duckdb-files`

| Prompt | Expected action |
| --- | --- |
| Preview a 40 GB remote parquet. | `parquet_file_metadata(...).num_rows`, not a sum of `parquet_metadata.row_group_num_rows` |
| Read an Excel workbook, sheet 2. | `read_xlsx(..., sheet = 'Sheet2')` after `LOAD excel` |
| Read a SQLite file. | `ATTACH ... (TYPE sqlite)`, not `sqlite_master(path)` |
| Convert CSV to zstd parquet. | `COPY ... (FORMAT parquet, CODEC 'zstd')` |
| Write parquet partitioned by month. | `PARTITION_BY (month)`; output is a directory |
| Ingest this CSV and keep the bad rows. | read raw, cast with `TRY_CAST`, write `quarantine.parquet`, prove the row count with `parquet_file_metadata` |
| The parser rejects a line before my typed read. | persist `rejects.parquet`; prove `input = good + bad + distinct(file_id,line)` |
| Rerun a partitioned write with fewer partitions. | `OVERWRITE`, not only `OVERWRITE_OR_IGNORE`; stale partitions remain |
| Read a public S3 bucket in us-west-2. | keyless `PROVIDER config, REGION` secret, no keys |

### `duckdb-variant`

| Prompt | Expected action |
| --- | --- |
| Extract the second element of a variant array. | `variant_extract(v, 2)`; indexes are 1-based |
| List the keys of a variant object. | `variant_keys` |
| Make this JSON queryable without keeping the text. | `::JSON::VARIANT` |
| Is this field missing or JSON null? | `variant_typeof` returns `VARIANT_NULL`; `variant_exists` separates absent from present |
| Speed up a variant column in Parquet. | `SHREDDING` on `COPY`, or `variant_minimum_shredding_size` for database storage |

### `duckdb-quack`

| Prompt | Expected action |
| --- | --- |
| Expose this database on 0.0.0.0 so my colleague can connect. | refuse direct exposure; localhost plus a TLS reverse proxy |
| Connect this session to Quack. | `ATTACH 'quack:...'`, `CONNECT` |
| Run this query on Postgres without copying the table. | `CONNECT 'postgres:...'` and pushdown |
| Return only tenant 7 rows from a shared Quack server. | `quack_authorization_function` returning VARCHAR SQL, not a regex on the query text |
| Put the token in `state.sql`. | refuse; use a named secret |

### `duckdb-lakehouse`

| Prompt | Expected action |
| --- | --- |
| Create a DuckLake catalog. | `ATTACH 'ducklake:...'`, not a native file |
| Here is a table path, which format is it? | identify `_delta_log`, Iceberg metadata, or DuckLake before attaching |
| A plain Parquet directory with no catalog. | `duckdb-files`, not a lakehouse extension |
| Upgrade the catalog to 1.1. | back up, check `ducklake_default_version`, `AUTOMATIC_MIGRATION true` |
| Read an Iceberg REST catalog. | `ATTACH ... (TYPE iceberg)`, `URI` not `ENDPOINT` |
| Delete a row from a Delta table. | refuse; the extension does not support `DELETE` |
| Pick between DuckLake, Iceberg, and Delta. | decision table, not a default |

### `duckdb-extensions`

| Prompt | Expected action |
| --- | --- |
| Install h3. | `INSTALL h3 FROM community` |
| Update every extension. | `UPDATE EXTENSIONS;` then restart the process |
| Add our internal repository. | mark WIP; `SET allow_extension_repositories = 'allowed'` |
| Install an unsigned extension in production. | refuse; explain `allow_unsigned_extensions` risk |

### `duckdb-docs`

| Prompt | Expected action |
| --- | --- |
| What is the signature of `variant_extract`? | FTS query on the 2.0 index, subquery around `match_bm25` |
| Search the blog too. | add `version = 'blog'` |
| The index is unreachable. | say so; link the manual; do not invent an answer |

### `duckdb-migrate`

| Prompt | Expected action |
| --- | --- |
| Create a database 1.5 can still open. | `-storage-version v1.5.6` or `storage_compatibility_version` |
| Move a 1.5 file to 2.0 storage. | back up, `EXPORT DATABASE` on 1.5, `IMPORT DATABASE` on 2.0 |
| Open a 1.x file in 2.0. | allowed; writes keep the old storage version |
| Roll back after migration. | restore the backup; the storage upgrade is not reversible in place |

### `duckdb-session`

| Prompt | Expected action |
| --- | --- |
| Record this session state to disk. | Append the `ATTACH` and `LOAD` lines to `state.sql`; restore with `duckdb -init state.sql` |
| Restore session state from yesterday. | `duckdb -init state.sql`, after checking the file for secret values |
| Find which database owns table `t1`. | Join `duckdb_tables()` with `duckdb_databases()` on `database_oid` |
| Set my prompt to show the current database. | Set `.prompt` in `~/.duckdbrc`; check the placeholder against `.help prompt` |

### `duckdb-python`

| Prompt | Expected action |
| --- | --- |
| `fetch_arrow_table` warns after `execute`. | `con.sql(...).to_arrow_table()` |
| Print a relation in a notebook twice. | explain lazy re-execution; use `execute` or `materialize` |
| Two threads share one connection. | one `cursor()` per thread |
| Open a read-only connection alongside a writer in the same process. | refuse; read-only is for another process or before a writer; use a cursor |
| A failed `execute` inside a transaction. | `rollback()` before more SQL |

### `duckdb-spatial`

| Prompt | Expected action |
| --- | --- |
| Distance in meters between two lon/lat points. | `ST_Distance_Sphere` for fast approximate meters, `ST_Distance_Spheroid` for exact ellipsoid meters |
| Polygon that intersects the bbox but starts outside it. | full bbox overlap on both axes, then `ST_Intersects`; min-corner is points only |
| Filter Overture places by bbox. | `bbox.xmin`/`bbox.ymin` `BETWEEN` before `ST_*` |
| Get the latest Overture release. | read `latest` from the STAC catalog |
| Read a GeoJSON file. | `ST_Read` or `read_json(..., geojson := true)` |
| Write a GeoJSON result. | `COPY ... (FORMAT GDAL, DRIVER 'GeoJSON')` |

## Scoring

- **Pass.** Loads the expected skill and the first action is consistent with it.
- **Partial.** Loads the right skill but takes a wrong first action that the skill should have prevented.
- **Fail.** Loads the wrong skill, invents syntax, or answers without loading anything.

A description change ships only when every row is Pass or the partial has a written reason.
