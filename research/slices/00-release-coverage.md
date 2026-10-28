# Slice: release coverage

Status: complete
Scope: What DuckDB 2.0.0 and DuckLake 1.1 actually shipped, and whether the 2.0-pass pack covers it. Runtime details owned by other slices are cited only when release scope is contested.
Sources: `research/sources/duckdb-2.0/` (pinned manual), `research/sources/ducklake-stable/` (pinned manual), https://duckdb.org/2026/10/21/announcing-duckdb-200.html, https://duckdb.org/2026/08/17/duckdb-20-highlights.html, https://github.com/duckdb/duckdb/releases/tag/v2.0.0, https://duckdb.org/release_calendar.html, https://ducklake.select/2026/10/21/ducklake-11/, https://duckdb.org/quack/faq.html, and the 12 `skills/*/SKILL.md` files plus `skills/duckdb/references/cli.md`. The manual `index.md` is a navigation page and contributes no release claim.

## Verified facts

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| 1 | The local binary is `v2.0.0 (Cyanoptera) d54cbbe3df`; the GitHub tag is `v2.0.0` at `d54cbbe3df`; the announcement calls the release “Cinnamon Teal”. | P1; GH release; announcement | Probed |
| 2 | New database files default to storage version 69. `duckdb_databases()` reports the tag `v2.0.0+`, not `69`. | P1; `sources/duckdb-2.0/internals/storage.md:49-53,97-110` | Probed |
| 3 | `BEFORE ... FOR EACH ROW` and `UPDATE ... FOR EACH ROW` triggers are rejected; `AFTER INSERT` and `AFTER DELETE` row triggers work; `RETURNING` works with statement triggers and fails with row triggers. | P2; `sql/statements/create_trigger.md:126-137` | Probed |
| 4 | Nearest joins are `NEAREST k BY SIMILARITY expr` or `NEAREST k BY DISTANCE expr`; `APPROX` precedes `NEAREST`. Distance functions need fixed-size arrays (`DOUBLE[N]`), not `DOUBLE[]`. | P3; `sql/query_syntax/from.md:529-552` | Probed |
| 5 | `~` and `!~` now partial-match; `~*` and `!~*` are new. `regex_match_operator_semantics='partial'` by default. | P4; `sql/functions/pattern_matching.md:218` | Probed |
| 6 | `avg(DECIMAL)` returns `DOUBLE`; `sum(DECIMAL)` and `decimal_average(DECIMAL)` return `DECIMAL`; `1.00/3` returns `DOUBLE`. | P5; `sql/functions/aggregates.md:330`, `sql/functions/numeric.md:277` | Probed |
| 7 | `decimal_division` is not safe with mixed DECIMAL/INTEGER arguments in 2.0.0: identical processes returned `0.0`, `0.333...`, and an out-of-range error. Both-DECIMAL arguments were stable. | P5 | Probed |
| 8 | `read_parquet(..., schema = MAP {'old': {name: ..., type: ..., default_value: ...}})` renames/adds/casts; `bound_schema` requires explicit `hive_partitioning`; `PARTITION_PATH` and `ORDER_BY` write paths/sort rows. | P6; `data/parquet/overview.md:179-231`, `data/partitioning/partitioned_writes.md:86-142` | Probed |
| 9 | `variant_extract` indexes lists from 1; index 0 is an error and out-of-range returns `NULL`. `variant_comparator(v)` takes one VARIANT and returns a BLOB sort key. | P7; `sql/functions/variant.md` | Probed |
| 10 | The `table_function_identifier_conversion` setting is itself deprecated; `error_on_division_by_zero` is deprecated. Both still work and warn. | P8; `sql/dialect/sql_quirks.md:104`, `configuration/pragmas.md` | Probed |
| 11 | `UPDATE ... FROM` with multiple matching source rows picks one source row, unspecified. `MERGE INTO` with the same shape raises an error. | P9; `sql/statements/update.md:113-129`, `sql/statements/merge_into.md:161-173` | Probed |
| 12 | Quack is beta, not production-ready. C API v2 is shipped but not stable. | `quack/faq.html`; `operations_manual/migration.md:113-117` | Documented |
| 13 | DuckLake 1.1 is opt-in; new catalogs default to 1.1, existing 1.0 catalogs stay 1.0 until `AUTOMATIC_MIGRATION true`. | `ducklake-stable/duckdb/migrations/upgrading_to_ducklake_1_1.md:6-42`; DuckLake 1.1 post | Documented |
| 14 | 2.0.1 is scheduled for 2026-11-18; 2.0.0 LTS support ends 2027-10-22. | release calendar | Documented |

## Existing skill audit

Coverage matrix. `none` means no skill or reference file owns the fact. `Released in` is the first release where the behavior is usable as described. Manual paths are relative to `research/sources/duckdb-2.0/`; DuckLake paths to `research/sources/ducklake-stable/`.

`whats_new_in_the_docs.md` is not a complete release manifest. At least `bound_schema`, `allow_empty`, `TUPLE`, `overlay`, regex `~`, and the CLI `.manual`/`.history` additions are documented as new in 2.0 but absent from that page, so the matrix is built from the manual’s “new in 2.0” markers as well as the announcement.

| Feature | Released in | Agent job it changes | Current home | Verdict | Evidence |
| --- | --- | --- | --- | --- | --- |
| Quack server (`quack_serve`, `quack_stop`, `quack_query`) | 1.5.3 preview, 2.0.0 polished | Run DuckDB as a server | `duckdb-quack` | covered | `quack/overview.md`; FAQ |
| `CONNECT` / `DISCONNECT`, remote pushdown to PostgreSQL and MySQL | 2.0.0 | Route a whole session to a remote database | `duckdb-quack` | covered | `sql/statements/connect.md` |
| CLI `-serve` / `-connect` | 2.0.0 | Start or join a server without SQL | `duckdb-quack`, `duckdb/references/cli.md` | covered | `clients/cli/arguments.md:77-104` |
| Triggers: BEFORE/AFTER, row/statement, transition tables, `RETURNING`, `DROP` | 2.0.0 | Audit tables, invariants | `duckdb-sql` | covered | `sql/statements/create_trigger.md`; P2 |
| `CREATE OR REPLACE TRIGGER`, `CREATE TRIGGER IF NOT EXISTS` | 2.0.0 | Re-runnable migration scripts | `duckdb-sql` | thin | `create_trigger.md:88-96` |
| Nested schemas | 2.0.0 | Organize schemas as paths | `duckdb-sql` | covered | `sql/statements/create_schema.md:53-60`; P10 |
| `VARIANT` type, casts, dot access | 1.5.0, first-class in 2.0.0 | Store schema-less columns | `duckdb-variant` | covered | `sql/data_types/variant.md` |
| `VARIANT` shredding in storage and Parquet `SHREDDING` | 2.0.0 | Compress and prune semi-structured data | `duckdb-variant` | covered | `variant.md:89`; P7 |
| `variant_*` functions, `variant_group_object`, `variant_group_array` | 2.0.0 | Build and inspect variant values | `duckdb-variant` | thin | P7; `sql/functions/variant.md:14,134-144` |
| `$var` shorthand and session variables as parameter defaults | 2.0.0 | Parameterize SQL | `duckdb-sql` | covered | `sql/statements/set_variable.md:37`; P10 |
| `NEAREST` / `APPROX NEAREST` joins | 2.0.0 | Top-k vector search in a join | `duckdb-sql` | thin | `from.md:529-552`; P3 |
| Data-modifying CTEs, including `COPY` in a CTE | 2.0.0 | Atomic move/ETL in one statement | `duckdb-sql` | thin | `with.md:110-139`, `copy.md:179`; P10, P11 |
| `SECURE VIEW` | 2.0.0 | Expose a filtered view without leaking internals | `none` | missing | `sql/statements/create_view.md:35-62`; P10 |
| `SHOW` as setting or `DESCRIBE` | 2.0.0 | PostgreSQL-style inspection | `none` | missing | `sql/statements/show.md:12-33`; P10 |
| Regex `~` / `!~` partial matching, `~*` / `!~*` | 2.0.0 | Port 1.x filters without changing results | `none` | missing | `pattern_matching.md:218`; P4 |
| JSON mutation: `json_set`, `json_insert`, `json_replace`, `json_remove` | 2.0.0 | Patch documents without rebuilding them | `none` | missing | `data/json/json_functions.md:514`; P10 |
| `MERGE` / `UPDATE ... FROM` multi-match semantics | 2.0.0 | Deduplicate sources before writing | `none` | missing | `update.md:113-129`, `merge_into.md:161-173`; P9 |
| Other SQL additions: `FETCH FIRST`, `GROUP BY UNNEST`, backticks, `EXCEPT`, no-arg `GROUPING_ID()`, `setval`, `ALTER TABLE` view rename, `regexp_extract` options, `overlay`, `lttb`, `TIMESTAMPTZ_NS`, `TUPLE`, empty `STRUCT`, `EXPLAIN (SQL)` | 2.0.0 | Small syntax upgrades | `duckdb-sql` (some pointers only) | thin | `whats_new_in_the_docs.md:35-50,111-131`; P10 |
| Asynchronous I/O for Parquet and uncompressed CSV | 2.0.0 | Faster object-storage scans | `duckdb-files` | covered | `data/io.md:15-40` |
| Optimizer/engine improvements: recursive CTE rewrite, partial aggregate pushdown, aggregation spill, zonemap pruning, partition-aware planning | 2.0.0 | Query performance tuning | `none` | out of scope | announcement; preview |
| Parquet `schema` / `bound_schema` read options | 2.0.0 | Read renamed, missing, or cast columns | `none` | missing | `data/parquet/overview.md:157-231`; P6 |
| Parquet `PARTITION_PATH` / `ORDER_BY` write options | 2.0.0 | Custom partition directories, sorted files | `duckdb-files` (only `PARTITION_BY`) | thin | `partitioned_writes.md:86-142`; P6 |
| Parquet timestamp write options, `file_row_group_number`, `allow_empty`, CSV `rejects_line_size_limit` | 2.0.0 | Interop and bounded rejects | `none` | missing | `sql/statements/copy.md:380-383`; `parquet/overview.md:233-246`; P6 |
| GeoJSON read (`geojson := true`) and write (`FORMAT GEOJSON`) | 2.0.0 | Native GeoJSON without GDAL | `duckdb-spatial` (GDAL path) | thin | `data/json/loading_json.md:356-367`, `writing_json.md:32` |
| Python migration: relations, results, threads, transactions | 2.0.0 | Port 1.x Python code | `duckdb-python` | covered | `clients/python/migration.md` |
| Python appender, including upsert/update/delete | 2.0.0 | Bulk insert rows produced by Python | `none` | missing | `clients/python/appender.md` |
| Python expression helpers (`fn`, `when`, `sql_expr`, `star`, `coalesce`) | 2.0.0 | Build expressions without old constructors | `duckdb-python` (only `col`/`lit`) | thin | `clients/python/expression.md:30-46` |
| Extension repositories | 2.0.0, WIP | Host and sign private extensions | `duckdb-extensions` | covered | `extensions/extension_repositories.md` |
| C API v2, static linking, C++17 build | 2.0.0 | Write extensions or custom builds | `none` | out of scope | `clients/c/overview.md`, `dev/building/linking_extensions.md` |
| `osx_amd64` phase-out | 2.0.0 community, 2.1 core | Choose a platform | `duckdb-extensions` | covered | `operations_manual/installing_duckdb/requirements.md` |
| DuckLake 1.1: nested schemas, `"NULL"`, epoch transforms, Puffin, stats, row-group counts | 2.0.0 / DuckLake 1.1 | Build and migrate a lake | `duckdb-lakehouse` | covered | DuckLake 1.1 post; `ducklake-stable/duckdb/migrations/upgrading_to_ducklake_1_1.md` |
| DuckLake maintenance: merge/rewrite/add files, table options | DuckLake 1.1 | Compact and tune tables | `duckdb-lakehouse` (defers) | thin | `ducklake-stable/duckdb/maintenance/merge_adjacent_files.md` |
| Iceberg REST `ATTACH` options | 2.0.0 | Attach REST catalogs | `duckdb-lakehouse` | covered | `core_extensions/iceberg/iceberg_options.md` |
| Delta `CREATE TABLE`, time travel, `VARIANT` | 2.0.0 | Create and query Delta | `duckdb-lakehouse` | covered | `core_extensions/delta.md:115-160,278-286` |
| Unity Catalog attach, time travel, `VARIANT`, `CREATE TABLE`, IRC scan plan | 2.0.0 (some 1.5.x) | Query Databricks/UC managed tables | `duckdb-lakehouse` (warning only) | thin | `core_extensions/unity_catalog.md:73-150` |
| CLI agent mode | 2.0.0 | Drive the CLI from an agent | `duckdb` | covered | `clients/cli/agent_mode.md` |
| `.history`, `.manual`, `.schema` formatting, `.web` | 2.0.0 | Interactive inspection | `duckdb/references/cli.md` | covered | `dot_commands.md:235-315` |
| `max_memory` percentage, `max_execution_time`, `checkpoint_on_detach` | 2.0.0 | Bound memory, time, and detach work | `duckdb`, `duckdb/references/cli.md` | covered | `configuration/pragmas.md:160-184,574-580` |
| `http_client_pool_capacity` | 2.0.0 | Tune HTTP concurrency | `none` | missing | `data/io.md:77` |
| `tracked_metrics`, `duckdb_available_metrics()` | 2.0.0 | Replace `custom_profiling_settings` | `duckdb-migrate` (name only) | thin | `configuration/pragmas.md:427`; `sql/meta/duckdb_table_functions.md:50` |
| `table_function_identifier_conversion` | 2.0.0 deprecation | Keep old `read_csv(path)` calls working | `duckdb/references/cli.md` (one line) | thin | `sql/dialect/sql_quirks.md:104`; P8 |
| `error_on_division_by_zero` | 2.0.0 behavior, setting deprecated | Return NULL instead of error | `duckdb-sql`, `duckdb-migrate` | thin | `migration.md:126-135`; P8 |
| Storage version 69 and format conversion | 2.0.0 | Upgrade safely | `duckdb`, `duckdb-migrate`, `duckdb-session` | covered | `internals/storage.md:49-95`; P1 |
| Lambda single-arrow disablement | 2.0.0 | Port 1.x lambdas | `duckdb-sql`, `duckdb-migrate` | covered | `migration.md:77-96`; P10 |
| Native timezone/calendar/collation implementation (no ICU library) | 2.0.0 | Custom builds and collations | `duckdb-migrate` | covered | `migration.md:119-124` |
| S3 URL parameters disabled | 2.0.0 | Rewrite S3 paths as secrets | `duckdb-files`, `duckdb-migrate` | covered | `migration.md:142-145` |
| Removed `custom_profiling_settings`, `enable_http_logging`, `http_logging_output`; CLI log storage | 2.0.0 | Migrate observability config | `duckdb-migrate` | covered | `migration.md:147-156` |
| Metadata additions: `is_generated`, `generation_expression`, `extension_name`, `duckdb_secret_type_parameters()` | 2.0.0 | Introspect generated columns and secrets | `none` | missing | `sql/meta/duckdb_table_functions.md:50,79-80,230,369` |

### Per-skill verdict

| Skill | Verdict | Main issue | Fix |
| --- | --- | --- | --- |
| `duckdb` | covered | Router and CLI contract are sound. Storage version 69 is stated without the `v2.0.0+` tag form. | Add one line: `tags['storage_version']` reports `v2.0.0+`, not `69`. |
| `duckdb-sql` | thin | Strong on triggers, lambdas, nested schemas. Missing regex change, decimal exactness, `SECURE VIEW`, `SHOW`, JSON mutation, multi-match DML, and only points at `NEAREST`/DML CTE syntax. | Add six compact blocks or table rows; do not expand the friendly-SQL list. |
| `duckdb-migrate` | thin | Covers storage, lambdas, division, S3, settings. Omits the `~` semantic change, `TUPLE`, implicit identifier conversion, and the deprecated division flag. | Add three bullets to “SQL text”; keep shadow-copy guidance. |
| `duckdb-files` | thin | Async I/O and reader dispatch are correct. Parquet 2.0 read/write options are absent. | Add `references/parquet.md`; link it from the reader table. |
| `duckdb-variant` | thin | Type, shredding, and function table are correct. Leaves list indexing unresolved and omits the comparator signature. | Two sentences: 1-based indexing and `variant_comparator(v) -> BLOB`. |
| `duckdb-lakehouse` | thin | DuckLake 1.1, Iceberg, Delta are well covered. Unity Catalog is a warning with no attach syntax; maintenance is deferred. | Add 3-line UC attach; add `references/ducklake-maintenance.md`. |
| `duckdb-quack` | covered | Correctly marks Quack beta and rejects `postgres://` from the preview. | None. |
| `duckdb-python` | thin | Migration table is accurate. Missing the appender and most expression helpers. | Add a 6-line appender block; add `fn`/`when`/`sql_expr` to the helper list. |
| `duckdb-spatial` | thin | Spatial and Overture guidance is strong. Native GeoJSON path is absent. | One line: `read_json(..., geojson := true)` and `FORMAT GEOJSON`. |
| `duckdb-extensions` | covered | Repositories, community, update, and platform rules match the manual. | None. |
| `duckdb-session` | covered | `ATTACH` persistence and storage tags are correct. | None. |
| `duckdb-docs` | covered | Not a release-coverage skill; index-version counts will age. | Recheck counts at release time; no content fix. |

## Gaps worth adding

Ranked by what an agent gets wrong without them.

| Rank | Gap | Why an agent needs it | Home: SKILL.md or reference | Exact fix |
| --- | --- | --- | --- | --- |
| 1 | `~` / `!~` changed from full to partial match | A 1.x filter such as `WHERE msg ~ 'ERROR'` now matches substrings, silently returning extra rows. | `duckdb-migrate` SKILL.md and `duckdb-sql` SKILL.md | Add to the SQL-text checklist: “`col ~ 'pat'` and `col !~ 'pat'` are partial (PostgreSQL) in 2.0. For 1.x full-match use `regexp_full_match(col, 'pat')` or `SET regex_match_operator_semantics='full'` (deprecated). `~*`/`!~*` are new.” |
| 2 | Exact decimal arithmetic | `avg(DECIMAL)` and `/` return DOUBLE, so finance results lose exactness; `decimal_average` and `decimal_division` are the 2.0 tools. | `duckdb-sql` SKILL.md | Add an “Exact decimals” block: `sum(x)` stays DECIMAL; `decimal_average(x)` returns DECIMAL; `1.00/3` returns DOUBLE; `decimal_division(10.00, 3.00, 6)` is exact. Warn: in 2.0.0 mixed DECIMAL/INTEGER arguments gave `0.0`, `0.333...`, or an error across runs; cast both operands to DECIMAL. |
| 3 | Parquet 2.0 read/write options | Agents re-create tables to rename columns or use the default Hive layout when the user asked for a custom path or sorted files. | `duckdb-files` reference file (`references/parquet.md`), linked from SKILL.md | Document `schema = MAP {'old': {name: 'new', type: 'BIGINT', default_value: NULL}}`; `bound_schema` requires explicit `hive_partitioning`; `PARTITION_PATH`; `ORDER_BY`; `file_row_group_number`; `allow_empty`; `TIMESTAMP_IS_ADJUSTED_TO_UTC`; `WRITE_TIMESTAMP_AS_INT96`. |
| 4 | `SECURE VIEW` | An agent asked to expose a filtered view uses `CREATE VIEW`, which can leak hidden columns through `stats()` and `EXPLAIN ANALYZE`. | `duckdb-sql` SKILL.md | Add: “A plain view is not a security boundary. Use `CREATE SECURE VIEW name AS SELECT ...` when the view is exposed to another user or team; secure views show a `Secure View` node and return NULL for internals.” |
| 5 | Python appender | Agents write per-row `execute()` or `executemany()` for Python-produced rows; the appender is faster and supports upsert/update/delete. | `duckdb-python` SKILL.md | Add a 6-line block: `with con.appender("people") as a: a.append_rows([...])`; note `action="upsert"`, `"update"`, or `"delete"` with `key=[...]`, and `query_appender()` for custom SQL. For DataFrames, `INSERT INTO t SELECT * FROM df` is still faster. |
| 6 | `NEAREST` join syntax and array type | The syntax is not guessable: `APPROX NEAREST k BY DISTANCE expr`. `array_distance` rejects variable-length `DOUBLE[]`; embeddings must be `DOUBLE[N]` or `FLOAT[N]`. | `duckdb-sql` SKILL.md | Add the exact example: `JOIN products t NEAREST 2 BY SIMILARITY array_cosine_similarity(q.embedding, t.embedding)`; `BY DISTANCE` for lower-is-closer; `APPROX` before `NEAREST`; cast embedding columns to `DOUBLE[768]` (or the model dimension). |
| 7 | `VARIANT` indexing and comparator | The skill admits it does not know whether lists are 0- or 1-based; an agent will try index 0 and get a binder error. `variant_comparator` is one-argument, not a two-argument compare. | `duckdb-variant` SKILL.md | Replace the uncertainty with: “List indexes in `variant_extract` are 1-based; 0 raises, out-of-range returns NULL. `variant_comparator(v)` returns a BLOB sort key for one VARIANT; use it in `ORDER BY`, not as a two-argument predicate.” |
| 8 | Data-modifying CTEs | Agents use separate statements and lose atomicity, or write a CTE without `MATERIALIZED` and get re-execution. `COPY` in a CTE has a documented return value that 2.0.0 does not produce. | `duckdb-sql` SKILL.md | Add: `WITH moved AS MATERIALIZED (DELETE FROM staging RETURNING *) INSERT INTO archive SELECT * FROM moved;` (verified). Note `COPY` in a CTE executes the write, but `SELECT rows_written FROM copied` returned no rows in 2.0.0 despite the manual; do not rely on the count. `COPY ... FROM` cannot be a CTE body. |
| 9 | Multi-match `UPDATE ... FROM` / `MERGE` | `UPDATE ... FROM` picks one matching source row, unspecified; `MERGE` raises on the same shape. Both silently differ from many agents’ assumptions. | `duckdb-sql` SKILL.md | Add: “Deduplicate the source or make the join key unique before `UPDATE ... FROM`; otherwise the chosen row is unspecified. `MERGE INTO` raises `MERGE INTO command cannot affect the same target row more than once`.” |
| 10 | DuckLake compaction and maintenance signatures | The skill says “read the page” but gives no call shape; agents will not know `schema`, size, time-window, or `max_compacted_files` arguments. | `duckdb-lakehouse` reference file (`references/ducklake-maintenance.md`), linked from SKILL.md | Document `CALL ducklake_merge_adjacent_files('lake')`, `('lake','orders', schema => 'sales', max_compacted_files => 10, min_file_size => 10485760, newer_than => now() - INTERVAL '7 days')`, and `ducklake_rewrite_data_files(..., max_compacted_files => 5)`. Note `auto_compact` only selects tables; files with deletes need `rewrite_data_files`. |

## Traps and contradictions

| Trap | What happens | Correct move | Evidence |
| --- | --- | --- | --- |
| Regex `~` changed meaning | 1.x full match becomes 2.0 substring match; more rows pass. | Use `regexp_full_match` or the deprecated `regex_match_operator_semantics='full'` for old behavior; write `~` only when partial is intended. | `pattern_matching.md:218`; P4 |
| `UPDATE ... FROM` multi-match | Target row updated once from an unspecified source row; results can change across plans. | Deduplicate the source or make the `ON` key unique. `MERGE` errors instead. | `update.md:113-129`; P9 |
| `COPY` in a CTE returns no count | The write happens, but `SELECT rows_written FROM copied` returns an empty result in 2.0.0, while the manual says the CTE returns rows written. | Use `COPY` in a CTE only for its side effect; do not branch on its row count. | `copy.md:179-193`; P11 |
| `decimal_division` with an INTEGER operand | Results were not stable across identical 2.0.0 processes: `0.0`, `0.333...`, or out-of-range. | Cast both operands to DECIMAL and pass a scale; or use `CAST(a AS DECIMAL(38,s)) / b`. Retest on 2.0.1. | P5 |
| `error_on_division_by_zero` | Still works, but the binary warns the setting is deprecated and will be removed. | Prefer `TRY(expr)` per expression; mention the setting only as a session-wide bridge. | P8; `migration.md:126-135` |
| `table_function_identifier_conversion` | The setting that controls the old behavior is itself deprecated. `DISABLE_IMPLICIT_STRING` raises a binder error. | Quote table-function arguments: `read_csv('file.csv')`; do not generate bare identifiers. | P8; `sql_quirks.md:104` |
| Triggers are not “in full” | `BEFORE ... FOR EACH ROW`, `UPDATE ... FOR EACH ROW`, `RETURNING` with row triggers, `INSTEAD OF`, and view/temporary triggers are rejected. | Use `AFTER INSERT/DELETE` row triggers or statement triggers with transition tables. | P2; `create_trigger.md:126-137` |
| `variant_extract` zero index | `variant_extract([10,20,30], 0)` raises “indexes are 1-based”. | Start at 1; out-of-range returns NULL. | P7 |
| Variant object key order | Objects print sorted; insertion order is not preserved. | Compare/sort with `variant_normalize`/`variant_comparator`, not key position. | P7; `variant.md` |
| `(a, b)` is a `TUPLE` | `typeof((1, 'a'))` is `TUPLE(INTEGER, VARCHAR)`, not an unnamed `STRUCT`; `.v1` access does not apply. | Use `struct_pack(a := ..., b := ...)` for named fields; use tuple positions for tuples. | P10; `sql/data_types/struct.md:185` |
| Storage version reported as text | `tags['storage_version']` is `v2.0.0+`, not `69`. | Compare the tag string; use the manual’s table for the numeric mapping. | P1; `storage.md:97-110` |
| `bound_schema` without partitioning | Binder error: “‘bound_schema’ requires explicit hive_partitioning=true or false”. | Pass `hive_partitioning = true` or `false`; it cannot be combined with `schema` or `union_by_name`. | P6 |
| `PARTITION_PATH` path rules | Leading `/`, empty paths, and `..` segments are rejected; it requires `PARTITION_BY` and cannot combine with `HIVE_FILE_PATTERN`. | Return a relative, non-empty path with no `..`. | `partitioned_writes.md:88-101` |
| Quack is beta | Protocol, function names, and defaults may break. | Prototype only; do not present it as production-ready. | FAQ |
| C API v2 is not stable | Interface may change in upcoming releases. | Do not promise ABI stability to extension authors. | `migration.md:113-117` |

### Previewed or announced, not shipped in 2.0.0

| Claim | What actually shipped | Evidence |
| --- | --- | --- |
| ART indexes become buffer-managed “later this year”. | Manual still warns ART indexes must fit in memory during creation; no buffer-managed PR in the 2.0.0 changelog. | Preview; `sql/indexes.md:25`; GH changelog grep |
| Async I/O reaches DuckDB’s native file format. | The 2.0 manual lists Parquet, uncompressed seekable UTF-8 CSV, and native DuckDB storage. JSON stays synchronous. | Probed / documented; `data/io.md` |
| New `MMAP` and `DIRECT_IO` modes. | Neither name appears in the 2.0 manual or the 2.0.0 changelog. | Preview; manual grep; GH changelog grep |
| A large part of C API v2 will be stable and frozen. | C API v2 ships, but is explicitly not stable. | Preview; `migration.md:113-117` |
| Triggers ship “in full”. | Row-level `BEFORE` and `UPDATE` are unsupported; `RETURNING` is blocked on row-trigger tables. | Preview; `create_trigger.md:126-137`; P2 |
| JSON will be backed by `VARIANT`. | Not in 2.0.0; the preview calls it “longer term, likely soon after v2.0”. | Preview; no manual page |
| `osx_amd64` is removed. | Core builds still support it; community extensions stopped; 2.1 removes it. | Announcement; requirements page |

### Contradictions between sources

| Source A | Source B | Resolution |
| --- | --- | --- |
| Announcement: “Cinnamon Teal”. | GitHub release and binary: “Cyanoptera”. | Same species, different common name; the binary string is authoritative for version checks. |
| Preview: “over 10,000 commits since 1.5”. | Announcement: “close to 20,000 commits since 1.5”. | Different publication dates (August vs October); do not quote a commit count as a 2.0 fact. |
| Preview: triggers “in full”. | Announcement and manual: explicit limitations. | Manual and binary win; document the limitations. |
| Preview: async I/O includes DuckDB’s native format. | The shipped 2.0 manual also lists native storage as async. JSON is the synchronous case. | Treat the manual as the shipped contract. |
| Preview: `CONNECT 'postgres://localhost/mydb'`. | Manual and `duckdb-quack`: `CONNECT 'postgres:dbname=mydb host=localhost'`. | Use the manual form; `postgres://` is a preview artifact. |
| Manual: `decimal_division` “using exact decimal arithmetic”. | Binary: mixed DECIMAL/INTEGER arguments can return wrong or unstable results. | Binary wins; require both-DECIMAL casts and a scale, and flag the 2.0.0 bug. |
| Manual: a `COPY` CTE “returns the number of rows written”. | Binary: the write happens but `SELECT rows_written FROM copied` returns no rows. | Do not rely on the count; use the write for its side effect only. |
| Manual and skills: `SET error_on_division_by_zero=false` is a supported bridge. | Binary: setting warns “deprecated and will be removed”. | Behavior still works; prefer `TRY`, mention the setting as temporary. |
| Manual: `table_function_identifier_conversion` controls conversion. | Binary: the setting itself is deprecated. | Quote arguments; treat the setting as a migration aid only. |
| Manual: storage version 69. | `duckdb_databases()`: `v2.0.0+`. | Same fact, different representation; do not compare the tag to `69`. |
| Preview: a large part of C API v2 will be stable. | Announcement and manual: not yet stable. | Promise nothing about ABI stability. |
| Announcement and migration guide omit a regex breaking change. | Manual documents `~`/`!~` partial matching; changelog has “Make regex operators match PostgreSQL behaviour” (#23432). | Treat regex semantics as a breaking change even though the announcement’s breaking-changes list does not. |
| Announcement and migration guide omit the identifier-conversion deprecation. | Manual documents it; changelog has “Deprecate Implicit Table-Function Identifier String Conversion” (#23350). | Quote table-function arguments in generated SQL. |

## What not to add

- **C API v2, static linking, C++17 build requirements.** Separate audience; no skill in the pack owns C/C++ extension authoring.
- **Optimizer internals and benchmark numbers.** Partial aggregates, recursive CTE speedups, row-group pruning, and partition-aware planning belong in release notes, not task guidance.
- **Non-Python client libraries (Go, R, Java, Node, WASM, ODBC).** The pack routes Python only; adding one-line stubs would imply coverage it does not have.
- **Quack wire protocol and custom client implementation.** Operational `quack_serve`/`CONNECT` guidance is enough; the FAQ owns beta status and protocol caveats.
- **DuckLake specification internals.** Puffin container layout, exact-string-stat encoding, and catalog table columns are maintainer material; the task skill needs the user-facing options only.
- **Full Unity Catalog coverage.** Writes, IRC scan planning, and catalog-managed commits are a separate product surface; keep only a 3-line `ATTACH ... (TYPE unity_catalog)` pointer in `duckdb-lakehouse`.
- **Trivia functions with no decision:** `lttb`, `overlay`, `setval`, no-arg `GROUPING_ID()`, `ALTER TABLE` view rename, backticks, `FETCH FIRST`, empty `STRUCT`. A one-line docs pointer is enough; a skill section would be accretion.
- **`TUPLE` as a type-system chapter.** One trap row is enough; agents rarely need tuple semantics beyond knowing `(a,b)` is not a named struct.
- **`.history`, `.manual`, `.schema` formatting.** Already in `duckdb/references/cli.md`; no SKILL.md space.
- **Web profiling UI.** `.web` is in the CLI reference; profiling format details belong in the profiling page.
- **`VARIANT` binary/shredding layout.** The user-facing rules (shredding threshold, `SHREDDING`, 1-based extraction) are enough.
- **Async I/O tuning beyond defaults.** `async_threads` and `read_ahead_depth` are already in the CLI reference; do not turn them into a tuning guide. Add `http_client_pool_capacity` only as one row in that table.

## Probe log

```text
$ duckdb --version
v2.0.0 (Cyanoptera) d54cbbe3df

P1  $ duckdb -no-agent -json -c "SELECT version() AS v, current_setting('storage_compatibility_version') AS storage;"
[{"v":"v2.0.0","storage":"latest"}]
$ rm -f new.db && duckdb -no-agent -json new.db -c "CREATE TABLE t(x INT); SELECT database_name, tags['storage_version'] AS sv FROM duckdb_databases();"
[{"database_name":"new","sv":"v2.0.0+"}, ...]

P2  $ duckdb -no-agent -json < trig_row.sql
Not implemented Error: BEFORE FOR EACH ROW triggers are not yet supported
$ duckdb -no-agent -json < trig_after_insert.sql
[{"id":1},{"id":2}]
$ duckdb -no-agent -json < trig_after_update.sql
Not implemented Error: UPDATE FOR EACH ROW triggers are not yet supported
$ duckdb -no-agent -json < trig_returning.sql
Not implemented Error: RETURNING is not yet supported on tables with FOR EACH ROW triggers
$ duckdb -no-agent -json < trig_stmt_returning.sql
[{"id":1},{"id":2}]

P3  $ duckdb -no-agent -json < nearest.sql
[{"user_id":1,"product_id":10}]
[{"user_id":1,"product_id":10}]
# with DOUBLE[] instead of DOUBLE[2]:
Binder Error: No function matches the given name and argument types 'array_distance(DOUBLE[], DOUBLE[])'

P4  $ duckdb -no-agent -json -c "SELECT 'abc' ~ 'b' AS tilde_partial, 'abc' ~ '^abc$' AS tilde_anchored;"
[{"tilde_partial":true,"tilde_anchored":true}]
$ duckdb -no-agent -json -c "SELECT current_setting('regex_match_operator_semantics') AS sem;"
[{"sem":"partial"}]

P5  $ duckdb -no-agent -json -c "SELECT typeof(avg(x)) AS avg_type, avg(x) AS avg_val, typeof(sum(x)) AS sum_type FROM (VALUES (1.00),(2.00)) t(x);"
[{"avg_type":"DOUBLE","avg_val":1.5,"sum_type":"DECIMAL(38,2)"}]
$ duckdb -no-agent -json -c "SELECT typeof(decimal_average(x)) AS t, decimal_average(x) AS v FROM (VALUES (1.00),(2.00)) t(x);"
[{"t":"DECIMAL(3,2)","v":"1.50"}]
$ for i in 1 2 3; do duckdb -no-agent -json -c "SELECT decimal_division(10.00, 3) AS v;"; done
[{"v":"0.0000000000000"}]
[{"v":"0.3333333333333"}]
Out of Range Error: decimal_division: result out of range for result type
$ duckdb -no-agent -json -c "SELECT decimal_division(10.00, 3.00) AS v;"
[{"v":"3.333333"}]

P6  $ duckdb -no-agent -json -c "SELECT * FROM read_parquet('t.parquet', schema = MAP {'a': {name: 'renamed_a', type: 'BIGINT', default_value: NULL}, 'c': {name: 'c', type: 'VARCHAR', default_value: 'x'}}) LIMIT 2;"
[{"renamed_a":0,"c":"x"},{"renamed_a":1,"c":"x"}]
$ duckdb -no-agent -json -c "SELECT * FROM read_parquet('t.parquet', bound_schema = {'a':'BIGINT','b':'BIGINT'}) LIMIT 1;"
Binder Error: 'bound_schema' requires explicit hive_partitioning=true or false
$ duckdb -no-agent -json -c "SELECT file_row_group_number, count(*) AS n FROM read_parquet('t.parquet') GROUP BY 1;"
[{"file_row_group_number":"0","n":10}]
$ duckdb -no-agent -json < partition.sql   # COPY ... (PARTITION_BY (region), PARTITION_PATH CASE ... END, ORDER_BY (amount DESC))
parts/europe/data_0.parquet
parts/region=us/data_0.parquet

P7  $ duckdb -no-agent -json < variant.sql
[{"typeof":"INT32","type":"INT32","keys":[]},{"typeof":"OBJECT(age, name)","type":"OBJECT","keys":["age","name"]},{"typeof":"OBJECT(user)","type":"OBJECT","keys":["user"]}]
[{"obj":{"a":1,"b":2}}]
[{"arr":[1,2]}]
[{"len":"3","contains":true}]
$ duckdb -no-agent -json -c "SELECT variant_extract([10,20,30]::VARIANT, 0);"
Binder Error: Extracting index 0 from VARIANT(ARRAY) is invalid, indexes are 1-based
$ duckdb -no-agent -json -c "SELECT variant_extract([10,20,30]::VARIANT, 1) AS i1, variant_extract([10,20,30]::VARIANT, 4) AS i4;"
[{"i1":10,"i4":null}]
$ duckdb -no-agent -json -c "SELECT typeof(variant_comparator({'a':1}::VARIANT)) AS t;"
[{"t":"BLOB"}]

P8  $ duckdb -no-agent -json < ident.sql   # SET table_function_identifier_conversion='DISABLE_IMPLICIT_STRING'
WARNING: The 'table_function_identifier_conversion' setting is deprecated and will be removed in a future release.
Binder Error: Deprecated implicit conversion of unbound identifiers to strings in table function arguments detected. Please use a string literal instead, e.g. 'no_such_file.csv'.
$ duckdb -no-agent -json -c "SET error_on_division_by_zero=false; SELECT 1//0 AS d, 1%0 AS m;"
WARNING: The 'error_on_division_by_zero' setting is deprecated and will be removed in a future release.
[{"d":null,"m":null}]

P9  $ for i in 1 2 3 4 5; do duckdb -no-agent -json < multimatch.sql; done
[{"id":1,"v":10}]   (x5; manual says the source row is unspecified)
$ duckdb -no-agent -json < mergemulti.sql
Invalid Input Error: MERGE INTO command cannot affect the same target row more than once.

P10 $ duckdb -no-agent -json < sql_misc2.sql
[{"a":1}]                          # SECURE VIEW
[{"threads":8}]                    # SHOW threads
[{"x":1}]                          # EXCEPT
[{"x":1}]                          # FETCH FIRST
[{"select":42}]                    # backticks
SELECT CAST(1 AS INTEGER) AS "1"   # EXPLAIN (SQL)
[{"s":{"a":1,"b":2},"r":{"b":2}}]  # json_set / json_remove
[{"t":"TUPLE(INTEGER, VARCHAR)"}]  # typeof((1, 'a'))

P11 $ duckdb -no-agent -json < copy_cte3.sql
# writes x2.csv, but SELECT rows_written FROM copied returns no rows
# manual: "The CTE returns the number of rows written."
```

## Open questions

- Does the `decimal_division` mixed-type instability reproduce on 2.0.1 and on Linux? Settle with the same probe on 2.0.1; until then, the skill warns.
- Is async I/O for the native DuckDB format shipped but undocumented, or was PR #24654 only partial? Settle by reading the PR and testing a remote read against a native file.
- Are `MMAP` / `DIRECT_IO` exposed under different setting names? Settle by grepping `duckdb_settings()` and the storage source.
- Does `variant_comparator` ordering match native DuckDB ordering for all types? Settle with a mixed-type sort probe.
- Is the `COPY` CTE row-count result a 2.0.0 regression fixed in 2.0.1, or an intentional statement-only CTE? Settle by testing 2.0.1 and reading the parser/planner code.
- Is `CREATE EXTENSION REPOSITORY` syntax frozen for 2.0.1? The manual says work-in-progress; recheck the page at release time.
- Does `read_blob` projection pushdown avoid downloading `content`? Not release-specific, but the `duckdb-files` claim “list without downloading bodies” needs a network probe.
