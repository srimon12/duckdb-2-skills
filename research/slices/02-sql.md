# Slice: SQL dialect and statements

Status: complete
Scope: the SQL dialect, friendly-SQL clauses, statements, lambdas, triggers, nested schemas, parser fallback, and silent-result traps that an agent writes in `skills/duckdb-sql/SKILL.md`.
Sources: `research/sources/duckdb-2.0/sql/`, `.../guides/sql_features/`, `.../whats_new_in_the_docs.md`; local `duckdb v2.0.0 (Cyanoptera) d54cbbe3df`; `https://duckdb.org/docs/2.0/sql/...` for page paths below.

## Verified facts

Probe IDs refer to the probe log. `P*` = run on the local binary; `Documented` = manual only.

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| F1 | `FROM t WHERE x > 10` is valid, selects all columns, and composes with `GROUP BY` / `ORDER BY`. | P1; `sql/query_syntax/from.md` §FROM-first; `sql/dialect/friendly_sql.md` | Probed |
| F2 | `GROUP BY ALL` infers groups from non-aggregate select expressions; `ORDER BY ALL` orders by every output column. | P1; `sql/query_syntax/groupby.md`, `orderby.md` | Probed |
| F3 | `SELECT * EXCLUDE (a,b)` and `SELECT * REPLACE (expr AS a)` work; `EXCEPT` is an exact synonym for `EXCLUDE` in a star expression as of 2.0. | P1; `sql/expressions/star.md` §EXCLUDE | Probed |
| F4 | `count()` with no argument is `count(*)`; `count() FILTER (WHERE ...)` works. | P1; `sql/functions/aggregates.md` | Probed |
| F5 | `UNION ALL BY NAME` aligns columns by name and fills missing columns with `NULL`; `UNION BY NAME` also exists. | P2; `sql/query_syntax/setops.md` | Probed |
| F6 | `INSERT INTO t BY NAME SELECT ...` matches source columns by name; omitted target columns take their `DEFAULT` (or `NULL`); an unknown source column is a binder error. | P2; P4; `sql/statements/insert.md` | Probed |
| F7 | `CREATE OR REPLACE TABLE` recreates the table: primary keys, constraints, and explicit indexes on the old table are gone. | P2; P10 | Probed |
| F8 | `PIVOT` and `UNPIVOT` work in both simplified and SQL-standard forms. Simplified `UNPIVOT` drops `NULL` values by default; only the standard form accepts `INCLUDE NULLS`. | P2; P10; `sql/statements/pivot.md`, `unpivot.md` | Probed |
| F9 | `DESCRIBE` does not execute the query; `SUMMARIZE` executes it and returns statistics (`approx_unique`, `null_percentage`, etc.). | P1; P10; `guides/meta/describe.md`, `summarize.md` | Probed |
| F10 | List comprehensions (`[x*2 FOR x IN col]`), 1-based slices (`col[1:3]`), negative indexes (`col[-1]`), and struct expansion (`s.*`) work. | P1; `sql/dialect/friendly_sql.md`; `sql/dialect/indexing.md` | Probed |
| F11 | `COLUMNS(*)` applies an expression across columns; `COLUMNS(lambda c: ...)` filters columns by name, and `UNPACK(COLUMNS(...))` expands into a variadic call. | P1; P7; `sql/expressions/star.md` §COLUMNS | Probed/Documented |
| F12 | `ASOF` and `POSITIONAL` joins work. `POSITIONAL JOIN` matches by row number and fills short sides with `NULL`. | P1; `sql/query_syntax/from.md` §ASOF/§POSITIONAL | Probed |
| F13 | `NEAREST k BY DISTANCE expr` / `BY SIMILARITY expr` works for `INNER` and `LEFT` joins; `APPROX` before `NEAREST` enables approximate search; `k` must be a positive integer literal. | P3; `sql/query_syntax/from.md` §NEAREST | Probed |
| F14 | Data-modifying CTEs support `INSERT`, `UPDATE`, `DELETE`, and `COPY ... TO`; `WITH moved AS MATERIALIZED (DELETE ... RETURNING *) INSERT ...` works, and `WITH updated AS (UPDATE ... RETURNING *) SELECT count(*) ...` works. | P4; `sql/query_syntax/with.md` §Data-Modifying CTEs | Probed |
| F15 | `COPY ... FROM` cannot be a CTE body (parser error). `COPY ... TO` in a CTE writes the file, but in 2.0.0 the outer query returns no rows, contradicting the manual's claim that the CTE returns the row count. | P4; `sql/statements/copy.md` §COPY TO | Probed, manual disagrees |
| F16 | Nested schemas: `CREATE SCHEMA a; CREATE SCHEMA a.b; CREATE TABLE a.b.t (...)` works and objects are addressed with the full dot path. The parent must exist; an unqualified `CREATE SCHEMA b` under `USE a` creates a top-level `b`, not `a.b`. | P5; `sql/statements/create_schema.md` §Nested Schemas | Probed |
| F17 | `USE a.b` and `SET search_path = 'a.b'` fail with `Not implemented Error: ... is a nested schema - nested schemas cannot be used in the search path`. `USE a` works; `SET search_path = 'a'` works. | P5; `sql/statements/create_schema.md`; `sql/dialect/keywords_and_identifiers.md` §Identifier Resolution | Probed |
| F18 | A two-part name such as `europe.orders` does not resolve relative to the current schema; it looks for a top-level schema `europe`. Fully qualify nested objects as `a.b.t`. | P5 | Probed |
| F19 | `"a.b"` is one top-level schema whose name contains a dot; `USE "a.b"` works for that literal schema. It is not a nested path. | P5; `sql/dialect/keywords_and_identifiers.md` | Probed |
| F20 | Nested schemas are invisible to `SHOW TABLES` / unqualified lookup in the parent; `SHOW ALL TABLES` shows the leaf schema and `duckdb_schemas()` exposes `parent_schema` / `parent_schema_oid`, columns absent from the manual table. | P5; `sql/meta/duckdb_table_functions.md` §duckdb_schemas | Probed, manual thin |
| F21 | `DROP SCHEMA a` fails if it contains nested schemas or tables; `DROP SCHEMA a CASCADE` removes the subtree. | P5; `sql/statements/create_schema.md` | Probed |
| F22 | `$x` reads a session variable anywhere an expression is allowed; `$"my var"` quotes a non-identifier name. `$undefined` raises `Values were not provided ...`; `getvariable('undefined')` returns `NULL`. `$x` is a prepared-statement parameter, and prepared named parameters fall back to variables of the same name. | P11; `sql/statements/set_variable.md`; `sql/query_syntax/prepared_statements.md` | Probed |
| F23 | `FETCH FIRST n ROWS ONLY`, `FETCH NEXT`, `ROW`/`ROWS`, and `OFFSET ... FETCH` work. `FETCH FIRST ... PERCENT` and `... WITH TIES` are parser errors. | P15; `sql/query_syntax/limit.md` | Probed |
| F24 | `MERGE INTO` errors if one target row matches more than one source row and a `WHEN MATCHED` action applies: `MERGE INTO command cannot affect the same target row more than once`. Deduplicate the source or make `ON` unique. | P9; `sql/statements/merge_into.md` §Multiple Matching Source Rows | Probed |
| F25 | `UPDATE ... FROM` with multiple matching source rows updates the target once using an unspecified source row; no error. Deduplicate for deterministic results. | P9; `sql/statements/update.md` §Multiple Matching Source Rows | Probed |
| F26 | `CREATE SECURE VIEW` hides table statistics and plan internals: `stats()` on a secure view returns only nullness, and `EXPLAIN ANALYZE` shows a `Secure View` node. | P10; `sql/statements/create_view.md` | Probed |
| F27 | `SHOW setting` prints a configuration value; `SHOW table` still describes a table but emits a deprecation warning; `SHOW DATABASES` and `SHOW SCHEMAS` work. `show_behavior` controls bare-name resolution (`auto`, `table`, `setting`). | P10; `sql/statements/show.md` | Probed |
| F28 | `setval('s', 42)` makes the next `nextval` return 43; `setval('s', 42, false)` makes it return 42. | P10; `sql/statements/create_sequence.md` §Setting the Sequence Value | Probed |
| F29 | `regexp_extract(string, pattern, options)` accepts `'i'`; `regexp_extract(string, pattern, name_list)` returns a `STRUCT` of named groups. No match returns an empty string / struct of empty strings, not `NULL`. | P10; `sql/functions/regular_expressions.md` §Using regexp_extract | Probed |
| F30 | `GROUP BY unnest(list_col)` groups by list elements. | P10; `sql/query_syntax/groupby.md` §Grouping by UNNEST | Probed |
| F31 | Backtick-quoted identifiers work like double-quoted identifiers; a backtick is escaped by doubling. Lookup remains case-insensitive and the stored case is preserved. | P10; `sql/dialect/keywords_and_identifiers.md` §Identifiers | Probed |
| F32 | `EXPLAIN (SQL)` renders the optimized plan as executable SQL. It cannot be combined with `ANALYZE` or `FORMAT`. The binary supports `SELECT`, `VALUES`, `WITH`, `INSERT`, `UPDATE`, `DELETE`, `MERGE INTO`; the manual says only `SELECT`/`VALUES`/`WITH`. | P10; P14; `sql/statements/profiling.md` §EXPLAIN (SQL) | Probed, manual disagrees |
| F33 | Empty `STRUCT`: bare `STRUCT`, `NULL::STRUCT`, `struct_pack()`, and `row()` work; `STRUCT()` is an error; `unnest` and `struct_extract` reject an empty struct. | P10; `sql/data_types/struct.md` | Probed |
| F34 | `TIMESTAMPTZ_NS` stores nanosecond precision; `TIMESTAMPTZ` truncates to microseconds. Both display in the session time zone. | P10; `sql/data_types/timestamp.md` §Timestamp Types | Probed |
| F35 | `lttb(x, y, n ORDER BY x)` returns a list of up to `n` `{x,y}` structs for downsampling. | P10; `sql/functions/aggregates.md` §lttb | Probed |
| F36 | `decimal_division(10.00, 4.00)` is exact and returns `DECIMAL(10,6)`; `decimal_average` returns the input width/scale with banker's rounding. Ordinary division involving `DECIMAL` returns a floating-point type. | P8; P10; `sql/functions/numeric.md` §decimal_division; `sql/data_types/numeric.md` §Division | Probed |
| F37 | `GROUPING_ID()` / `GROUPING()` with no arguments default to all `GROUP BY` columns in group order. | P10; `sql/query_syntax/grouping_sets.md` | Probed |
| F38 | `ALTER TABLE v RENAME TO v2` can rename a view as of 2.0; `ALTER VIEW ... RENAME TO` also works. | P10; `sql/statements/alter_table.md` §RENAME TABLE | Probed |
| F39 | `EXPLAIN` estimates without executing; `EXPLAIN ANALYZE` executes and reports actual cardinalities and operator timings. Profiling uses `SET enable_profiling` + `SET profiling_output`; `SET tracked_metrics=['query.*','operator.*']` filters metrics. Min-max zonemaps are automatic; ART indexes serve PK/UNIQUE and point lookups. | P14; `sql/statements/profiling.md`; `sql/indexes.md` | Probed |
| F40 | `query('SELECT ...')` and `query_table('name')` work with literal/constant strings and prepared parameters; column references are rejected (`The function only supports literals as parameters`). | P10; `guides/sql_features/query_and_query_table_functions.md` | Probed |
| F41 | The PEG parser is the default; `enable_peg_parser()` is gone. Errors include `LINE n:` and a caret. `SET enable_legacy_parser = true` autoloads `legacy_parser`; the setting alone is enough. | P12; `sql/peg_parser.md`; `core_extensions/legacy_parser.md` | Probed |
| F42 | The legacy parser is not a strict 1.x dialect: it accepted `$x`, `FETCH FIRST`, data-modifying CTEs, backticks, `SHOW`, `CREATE TRIGGER`, and `SECURE VIEW` in probes, but rejected `NEAREST`. The documented legacy quirks (`~` full match, `B'0101'` as varchar, `ORDER BY true`) did not reproduce. | P12; `core_extensions/legacy_parser.md` | Probed, manual disagrees |
| F43 | `USING SAMPLE` is written after `WHERE`/`GROUP BY` but applied to the `FROM` result before them, so `WHERE` filters the sample rather than sampling the filtered result. | `sql/query_syntax/sample.md`; `sql/dialect/sql_quirks.md` §USING SAMPLE | Documented |
| F44 | Type facts: `VARIANT` is typed binary, keys sorted, with `variant_typeof` and dot extraction; `UNION` is a tagged union with `union_value(tag := expr)` and `union_tag`; `MAP` bracket lookup returns `NULL` for a missing key while `map_extract` returns `[]`; `ARRAY` is fixed-length, `LIST` variable-length, both 1-based; `ENUM` compares in declaration order. | P17; `sql/data_types/variant.md`, `union.md`, `map.md`, `array.md`, `list.md`, `enum.md` | Probed/Documented |
| F45 | `QUALIFY` filters on window-function results in the same `SELECT`, so no extra subquery is needed. | P13; `sql/query_syntax/qualify.md` | Probed |

### Trigger support matrix (2.0.0)

Every row was probed; “Transition” means `REFERENCING OLD TABLE` / `NEW TABLE`.

| Timing | Event | FOR EACH | REFERENCING | Result | Exact behavior / error |
|---|---|---|---|---|---|
| BEFORE | INSERT | STATEMENT | none | works | body executes before the insert |
| BEFORE | UPDATE | STATEMENT | none | works | body executes before the update |
| BEFORE | DELETE | STATEMENT | none | works | body executes before the delete |
| BEFORE | INSERT/UPDATE/DELETE | ROW | any | fails | `Not implemented Error: BEFORE FOR EACH ROW triggers are not yet supported` |
| BEFORE | INSERT/UPDATE/DELETE | STATEMENT | transition | fails | `Binder Error: Transition tables can only be specified for AFTER triggers` |
| AFTER | INSERT | STATEMENT | `NEW TABLE` only | works | `OLD TABLE` is invalid for INSERT |
| AFTER | UPDATE | STATEMENT | `OLD TABLE`, `NEW TABLE`, or both | works | both tables can be joined |
| AFTER | DELETE | STATEMENT | `OLD TABLE` only | works | `NEW TABLE` is invalid for DELETE |
| AFTER | INSERT | ROW | none, body uses `NEW.col` | works | `OLD` is not available |
| AFTER | DELETE | ROW | none, body uses `OLD.col` | works | `NEW` is not available |
| AFTER | UPDATE | ROW | any | fails | `Not implemented Error: UPDATE FOR EACH ROW triggers are not yet supported` |
| AFTER | INSERT/DELETE | ROW | transition | fails | `Binder Error: REFERENCING is not valid for FOR EACH ROW triggers` |
| BEFORE/AFTER | UPDATE | STATEMENT | `UPDATE OF col` | works | `columns` in `duckdb_triggers()` lists the columns |
| BEFORE/AFTER | UPDATE | STATEMENT | `UPDATE OF` + transition | fails | `Binder Error: UPDATE OF is not valid with transition tables` |
| any | any | any | `WHEN (...)` | fails | `Parser Error: syntax error at or near "WHEN"` |
| AFTER | INSERT | STATEMENT | none, DML has `RETURNING` | works | returns rows; trigger fires |
| AFTER | INSERT | ROW | none, `INSERT ... RETURNING` | fails | `RETURNING is not yet supported on tables with FOR EACH ROW triggers` |
| AFTER | DELETE | ROW | none, `DELETE ... RETURNING` | fails | same error; matching-event rule |
| AFTER | INSERT | ROW | none, `UPDATE ... RETURNING` | works | row trigger is for a different event |
| any | any | any | `INSTEAD OF` | fails | `Not implemented Error: INSTEAD OF triggers are not yet supported` |
| any | view | any | any | fails | `CREATE TRIGGER requires a base table, not a view or subquery` |
| any | any | any | `CREATE TEMP TRIGGER` | fails | `Parser Error: Temporary triggers are not supported` |
| any | temp table | any | body uses temp objects | works | trigger is `temporary = true` in `duckdb_triggers()` |
| any | any | any | duplicate name on same table | fails | `Catalog Error: Trigger with name "trg" already exists!` |
| any | any | any | `CREATE OR REPLACE` / `IF NOT EXISTS` | works | the two clauses cannot be combined |

Additional trigger facts: a trigger body is exactly one data-modifying statement (`INSERT`, `UPDATE`, `DELETE`, `MERGE`, optionally prefixed by `WITH`); `SELECT`, `CREATE`, `PRAGMA`, `COPY`, `CALL`, and `BEGIN` are parser errors, and two statements without a semicolon are a parser error. A body may modify another table, but a body that modifies its own table raises `Recursive trigger chains are not yet supported`. Multiple triggers on the same event fire in creation order; all `BEFORE` triggers fire before all `AFTER` triggers. Trigger names are unique per table, not per schema. `duckdb_triggers()` columns: `database_name`, `database_oid`, `schema_name`, `schema_oid`, `trigger_name`, `trigger_oid`, `table_name`, `action_timing`, `event_manipulation`, `columns` (`VARCHAR[]`), `for_each`, `comment`, `tags` (`MAP(VARCHAR,VARCHAR)`), `temporary`, `sql`. `DROP TRIGGER IF EXISTS ... ON missing_table` still errors because the table must exist.

### Lambda support (2.0.0)

| Form | Works | Notes |
|---|---|---|
| `lambda x: x + 1` | yes | canonical Python-style form |
| `lambda x, i: x + i` | yes | extra last parameter is the 1-based element index |
| `x -> x + 1` | no by default | `Binder Error: Deprecated lambda arrow (->) detected`; `SET lambda_syntax='enable_single_arrow'` re-enables it |
| `SET lambda_syntax='disable_single_arrow'` | yes | Python form still works; setting only controls the arrow form |
| nested `lambda` | yes | inner parameters shadow outer; then columns, then macro parameters |
| capture a column | yes | `lambda y: y + tbl.x`; column names are in scope |
| `NULL` element | passes through | `list_transform([1,NULL,3], lambda x: x+1)` → `[2, NULL, 4]`; `list_filter` drops a `NULL` predicate result |
| subquery in body | no | `Binder Error: subqueries in lambda expressions are not supported` |
| scalar macro in body | yes | macro must not contain a subquery |
| return a lambda from a macro | no | lambdas must be defined inline |
| `COLUMNS(lambda c: ...)` | yes | first parameter is column name; optional second parameter is the 1-based column index |
| higher-order functions | 3 families | `list_transform` (aliases `apply`, `array_apply`, `array_transform`, `list_apply`), `list_filter` (aliases `array_filter`, `filter`), `list_reduce` (aliases `array_reduce`, `reduce`); `list_reduce` takes an optional initial value and an optional third index parameter |

### Division and modulo (2.0.0)

| Expression | Result | Note |
|---|---|---|
| `5 / 2` | `2.5` (DOUBLE) | `/` is floating-point division even for integers |
| `5 // 2` | `2` | `//` truncates toward zero |
| `-5 // 2` | `-2` | truncation, not floor |
| `fdiv(-5, 2)` | `-3.0` | `fdiv` is floored division and returns DOUBLE |
| `5 % 2`, `-5 % 2`, `5 % -2` | `1`, `-1`, `1` | remainder sign follows the dividend |
| `5.5 // 2` | `2.75` | if either operand is `DECIMAL`/floating, `//` is ordinary division |
| `5::DECIMAL(10,2) / 2` | `2.5` (DOUBLE) | decimal division returns floating point; use `decimal_division` |
| `1 / 0`, `-1 / 0`, `0 / 0` | `inf`, `-inf`, `nan` | no error |
| `1 // 0`, `1 % 0` | error | `Invalid Input Error: Division by zero ... Use TRY(...) or SET error_on_division_by_zero=false` |
| `TRY(1 // 0)`, `TRY(1 % 0)` | `NULL` | per-expression recovery |
| `SET error_on_division_by_zero=false` | `NULL` | setting is deprecated and warns; it does not change `/` (`inf`/`nan`) |

### Nested schema behavior (2.0.0)

| Operation | Result |
|---|---|
| `CREATE SCHEMA a` | top-level schema `a` |
| `CREATE SCHEMA a.b` | nested schema; `a` must already exist (`Catalog Error: "a" is not a catalog or schema` otherwise) |
| `CREATE SCHEMA b` after `USE a` | creates top-level `b`, not `a.b` |
| `CREATE TABLE a.b.t (...)` | works; use the full path everywhere |
| `CREATE TABLE b.t` after `USE a` | fails: `Schema with name b does not exist!` |
| `SELECT * FROM b.t` after `USE a` | fails; two-part names are resolved from the top level |
| `USE a.b` | fails: nested schema cannot be in the search path |
| `SET search_path='a.b'` / `SET schema='a.b'` | same failure |
| `SHOW TABLES` while `USE a` | does not list tables in `a.b` |
| `SHOW ALL TABLES` | lists `schema = b` (leaf name only) |
| `duckdb_schemas()` | `schema_name = b`, `parent_schema = a`; `parent_schema` is undocumented in the manual table |
| `DROP SCHEMA a` | fails while `a.b` or its tables exist; `DROP SCHEMA a CASCADE` removes the subtree |
| `CREATE SCHEMA "a.b"`; `USE "a.b"` | works; this is a literal top-level schema name containing a dot |

## Existing skill audit

| Skill | Claim or omission | Verdict | Fix |
|---|---|---|---|
| duckdb-sql | “Run statements with the `duckdb` skill ... `duckdb -agent` ... `duckdb -json` ... `-init` session file.” | correct | CLI/session details are owned by the `duckdb`/`duckdb-session` skills; keep only the cross-link here. |
| duckdb-sql | “Friendly SQL, Python-style lambdas, triggers, nested schemas, integer division by zero, and result size.” | thin | Keep the scope, but “integer division by zero” is a trap, not a feature; “result size” belongs to the CLI skill. |
| duckdb-sql | “Look at columns with `DESCRIBE`, which does not run the query. Profile a table with `SUMMARIZE`.” | thin | `DESCRIBE` is correct; `SUMMARIZE` executes the query and computes statistics, it does not profile. Say so. |
| duckdb-sql | “If the source can return a huge row set ... add `LIMIT 100` for a first look and say that you did.” | correct | Keep; add that `LIMIT` without `ORDER BY` is not deterministic. |
| duckdb-sql | “The single-arrow form is disabled.” | correct | Keep. Add the exact error and that the setting is removed in 2.1. |
| duckdb-sql | “`SET lambda_syntax = 'enable_single_arrow'` turns the old `x -> x + 1` form back on for the session.” | correct | Keep; write the `lambda` form in saved SQL. |
| duckdb-sql | “`1 // 0` and `1 % 0` raise. `1 / 0` still returns `inf`.” | correct | Keep; add `0/0 = nan`, `//` truncates, `fdiv` floors, and decimal operands change `//` to floating division. |
| duckdb-sql | “`SET error_on_division_by_zero = false` makes every integer division by zero return `NULL`.” | thin | Correct, but the setting is deprecated in 2.0 and warns. Prefer `TRY(...)`; do not put the setting in generated scripts. |
| duckdb-sql | “`CREATE SCHEMA sales.europe` ... `SELECT * FROM sales.europe.orders`” | correct | Keep; add that the parent must exist and that relative two-part names fail. |
| duckdb-sql | “`USE sales.europe` fails. Nested schemas cannot sit on the search path. Qualify the name.” | correct | Keep; add `SET search_path`/`SET schema` fail with the same error, and `SHOW TABLES` hides nested tables. |
| duckdb-sql | “A quoted identifier `"sales.europe"` is one schema whose name contains a dot, not a nested path.” | correct | Keep; add that `USE "a.b"` works for that literal schema. |
| duckdb-sql | “A trigger body is one SQL statement.” | correct | Keep; specify that the statement must be `INSERT`/`UPDATE`/`DELETE`/`MERGE` (optionally `WITH`), not `SELECT`/DDL/utility statements. |
| duckdb-sql | “Several triggers on the same event run in creation order.” | correct | Keep; add that all `BEFORE` triggers fire before all `AFTER` triggers and names are per-table. |
| duckdb-sql | Statement-level audit example with `REFERENCING OLD TABLE AS o NEW TABLE AS n` | correct | Keep. Add that transition tables are only valid on `AFTER` triggers and cannot be combined with `UPDATE OF`. |
| duckdb-sql | Row-level insert example with `NEW.id` | correct | Keep; note `OLD` is unavailable for INSERT and `NEW` for DELETE. |
| duckdb-sql | “`UPDATE OF price` limits an update trigger to those columns.” | thin | Correct only for `FOR EACH STATEMENT`; row-level UPDATE is unsupported, and `UPDATE OF` cannot see transition tables. |
| duckdb-sql | “`NEW` exists for `INSERT`. `OLD` exists for `DELETE`. `NEW TABLE` exists for `INSERT` and `UPDATE`. `OLD TABLE` exists for `UPDATE` and `DELETE`.” | thin | Correct for row vs statement respectively; statement-level `NEW.id`/`OLD.id` do not exist, and transition tables are `AFTER` only. |
| duckdb-sql | “Unsupported in 2.0: `BEFORE ... FOR EACH ROW`, `UPDATE ... FOR EACH ROW`.” | correct | Keep. |
| duckdb-sql | “`RETURNING` on a table that has a `FOR EACH ROW` trigger” is unsupported. | wrong | Overbroad. The binary blocks `INSERT ... RETURNING` with an INSERT row trigger and `DELETE ... RETURNING` with a DELETE row trigger; `UPDATE ... RETURNING` still works with an INSERT row trigger. Say “the matching event”. |
| duckdb-sql | “`INSTEAD OF`, triggers on views, temporary triggers.” | thin | INSTEAD OF and views are correct. “Temporary triggers” is ambiguous: `CREATE TEMP TRIGGER` is unsupported, but a trigger on a temporary table is allowed and reports `temporary = true`. |
| duckdb-sql | “`RETURNING` is allowed on a table whose triggers are `FOR EACH STATEMENT`.” | correct | Keep. |
| duckdb-sql | “`FROM t WHERE x > 10` selects every column.” | correct | Keep. |
| duckdb-sql | “`GROUP BY ALL`, `ORDER BY ALL`.” | correct | Keep; one line of examples is enough. |
| duckdb-sql | “`SELECT * EXCLUDE (a, b)` and `SELECT * REPLACE (expr AS a)`. `EXCEPT` is a synonym of `EXCLUDE`.” | correct | Keep; warn that `EXCEPT` is also a set operator outside a star expression. |
| duckdb-sql | “`count()` with an empty argument list. `count() FILTER (WHERE x > 10)`.” | correct | Keep. |
| duckdb-sql | “`UNION ALL BY NAME`.” | thin | Add: missing columns become `NULL`, types are combined, and `UNION BY NAME` (distinct) exists. |
| duckdb-sql | “`INSERT INTO t BY NAME SELECT ...`.” | thin | Add: omitted columns take defaults, unknown source columns error. |
| duckdb-sql | “`CREATE OR REPLACE TABLE`.” | thin | Correct but destructive: it drops the old table's constraints and indexes. Do not use it to “update” a table that has a primary key. |
| duckdb-sql | “`PIVOT` and `UNPIVOT`.” | thin | Add: `PIVOT ... USING` silently ignores `FILTER`; simplified `UNPIVOT` drops `NULL`s; only standard `UNPIVOT INCLUDE NULLS` keeps them. |
| duckdb-sql | “`DESCRIBE` and `SUMMARIZE`.” | correct | Keep. |
| duckdb-sql | “List comprehensions `[x * 2 FOR x IN col]`, list slices `col[1:3]`, struct expansion `s.*`.” | correct | Keep; add 1-based indexing and `[-1]`; JSON is the 0-based exception. |
| duckdb-sql | “`COLUMNS(*)` to apply an expression across columns.” | thin | Add `COLUMNS(lambda c: ...)`, regex column selection, and `UNPACK` for OR/variadic calls. |
| duckdb-sql | “`ASOF` and `POSITIONAL` joins.” | thin | Add one line each: ASOF needs equality keys plus one inequality; POSITIONAL matches by row number and fills NULLs. |
| duckdb-sql | “`SET VARIABLE x = 7; SELECT $x;` ... `getvariable('x')` still works. Write `$x` in new SQL.” | thin | Add: `$undefined` raises, `getvariable` returns `NULL`; `$x` is a prepared parameter and can be a default for a named parameter. |
| duckdb-sql | “2.0 syntax to look up before inventing a statement: `NEAREST` joins, data-modifying CTEs, `FETCH FIRST`, backtick-quoted identifiers, and `EXPLAIN (SQL)`.” | thin | The list is incomplete and the promised pages are not in the reference list. Add `MERGE`, `SHOW`, `SECURE VIEW`, `setval`, `regexp_extract` options, `GROUP BY UNNEST`, empty `STRUCT`, `TIMESTAMPTZ_NS`, `lttb`, `decimal_division`, no-arg `GROUPING_ID`, view rename, `query()`/`query_table()`. |
| duckdb-sql | “The PEG parser is the default. A query that parsed on 1.x should still parse, and errors include a source location.” | thin | Default and locations are correct; “should still parse” is an intent, not a guarantee. Say “if it parsed on 1.5 and fails, file an issue before falling back”. |
| duckdb-sql | “`INSTALL AND LOAD legacy_parser; SET enable_legacy_parser = true;`” | thin | Works, but `SET enable_legacy_parser=true` autoloads the extension; `INSTALL AND LOAD` is redundant. The legacy parser rejects `NEAREST` and did not reproduce the manual's listed quirks. |
| duckdb-sql | “File the query if you need the fallback.” | wrong | Typo/incorrect instruction: file an issue against DuckDB; do not preserve a silent-semantics fallback. |
| duckdb-sql | “Do not leave `legacy_parser` in a script you generate for someone else unless they asked.” | correct | Keep. |
| duckdb-sql | Reference list of 7 links. | thin | Missing the pages for `NEAREST`, data-modifying CTEs, `FETCH FIRST`, backticks, `EXPLAIN (SQL)`, `SHOW`, `MERGE`, triggers beyond the one page, and nested-schema introspection. Add a compact “See also” block or move the friendly-SQL links into the new reference. |
| duckdb-sql | Footer: “The lambda rule, trigger limits, nested-schema `USE` error, and `//` error were checked on DuckDB 2.0.0.” | wrong | The trigger limits were not checked accurately: the `RETURNING` claim is overbroad and “temporary triggers” is ambiguous. Re-probe before repeating. |

## Gaps worth adding

| Rank | Gap | Why an agent needs it | Home: SKILL.md or reference |
|---:|---|---|---|
| 1 | Trigger support matrix, including `AFTER`-only transition tables, no `WHEN`, no row UPDATE, no `UPDATE OF` + transition, DML-only body, temp-table nuance, and the event-specific `RETURNING` rule. | The current text has two wrong/ambiguous claims and omits the constraints that make a trigger fail at create time. This is the highest-risk section because triggers are new in 2.0. | `SKILL.md` (compact matrix; no new skill) |
| 2 | Division semantics: `/` vs `//` vs `fdiv`, truncation vs floor, decimal operands turning `//` into floating division, `%` sign, zero behavior, `TRY`, deprecated setting. | Silent numeric wrongness is worse than a binder error; an agent will otherwise write `//` on a DECIMAL and get a fractional result. | `SKILL.md` |
| 3 | Nested schema rules: full qualification, no `USE`/search path, relative two-part names fail, `SHOW TABLES` hides nested objects, `duckdb_schemas().parent_schema`, `DROP ... CASCADE`, literal dot-schema. | The current example works, but an agent that follows it and then writes `SELECT * FROM b.t` gets a catalog error; introspection also misleads. | `SKILL.md` |
| 4 | Silent result traps: NULL ordering, int-to-string comparison rounding, decimal division to DOUBLE, default window frame, `APPROX_COUNT_DISTINCT`, empty-group `sum`, timestamp session time zone. | These change answers without an error, which is the hardest class of bug to notice. | `SKILL.md` (short table) |
| 5 | `$x` vs `getvariable`: undefined behavior differs; `$x` is a prepared parameter and named-parameter default; `$"my var"`. | The current “write `$x`” advice is right but incomplete; the failure mode is an error only for `$x`, `NULL` for `getvariable`. | `SKILL.md` |
| 6 | Statement semantics for `MERGE` / `UPDATE ... FROM` multiple matches, `COPY` in CTE, `FETCH FIRST` limits, `SHOW` table deprecation. | These are 2.0 features an agent will reach for; two have surprising failure/silence modes. | `SKILL.md` (one-liners) + `references/friendly-sql.md` (examples) |
| 7 | Lambda edge cases: index base, captures/shadowing, NULL propagation, no subqueries, exact function families and aliases. | The syntax is current, but the current section gives no way to choose a function or predict NULL/index behavior. | `SKILL.md` (syntax + rules); no function catalog |
| 8 | Friendly-SQL edge cases: `CREATE OR REPLACE TABLE` destroys constraints/indexes, `PIVOT` ignores `FILTER`, simplified `UNPIVOT` drops NULLs, `BY NAME` default/extra-column behavior, `LIMIT 10%` floors on small tables. | These are exactly the “friendly” shortcuts an agent will use without reading the long pages. | `references/friendly-sql.md` |
| 9 | Pre-optimization statements: `EXPLAIN`, `EXPLAIN ANALYZE`, `SET enable_profiling`/`tracked_metrics`, `EXPLAIN (SQL)`, zonemaps vs ART. | Keeps an agent from guessing at performance work; `PRAGMA enable_profiling` is deprecated. | `SKILL.md` (4–6 lines) |

Reference split: `SKILL.md` keeps decisions and traps (triggers, division, nested schemas, lambdas, parser, perf); `references/friendly-sql.md` holds exact friendly-clause syntax and edge cases (F1–F13, PIVOT/UNPIVOT, `BY NAME`, `$x`, joins).

## Traps and contradictions

| Trap | What happens | Correct move | Evidence |
|---|---|---|---|
| NULL ordering | `ORDER BY x` puts `NULL`s last for both `ASC` and `DESC`; this differs from PostgreSQL's `DESC` default. | Write `NULLS FIRST`/`NULLS LAST` when the position matters; do not port a PG query unchanged. | P13; `sql/query_syntax/orderby.md` |
| Integer/string comparison | `1 = '1.1'` is `true` because the string is cast to INTEGER and rounded; `2 = '1.5'` is also `true`. | Cast explicitly (`TRY_CAST`/`CAST`) and compare like types; never compare an id to a decimal-looking string. | P13; `sql/dialect/sql_quirks.md` §Results That May Surprise You |
| Decimal division | Any division involving `DECIMAL` returns a floating-point type; `5::DECIMAL(10,2)/2` is `2.5` DOUBLE, and `5.5 // 2` is `2.75`. | Use `decimal_division(x,y)` or `decimal_average` for exact money/ratio arithmetic; `//` is only integer division when both operands are integers. | P8; `sql/data_types/numeric.md` §Division; `sql/functions/numeric.md` |
| `//` negative values | `-5 // 2` is `-2` (truncation), while `fdiv(-5,2)` is `-3.0` (floor). | Choose `//` for truncation and `fdiv` for floor; document which one the business rule means. | P8 |
| Window default frame | `sum(x) OVER (ORDER BY x)` uses `RANGE UNBOUNDED PRECEDING TO CURRENT ROW`, so tied `x` values all receive the same cumulative sum. | Use `ROWS BETWEEN ...` for a row-by-row running total; use `RANGE` only when peers should share the value. | P13 |
| `APPROX_COUNT_DISTINCT` | On 1M values it returned `99467` vs exact `100000` (≈0.5% low). | Use `count(DISTINCT x)` when the number is user-visible or feeds a decision; use approximate only for exploration. | P13 |
| Empty-group aggregates | `sum`, `list`, and `string_agg` return `NULL` on an empty group, not `0`/`[]`/`''`; `count` returns `0`. | `coalesce(sum(x), 0)` when a numeric zero is required; do not assume `sum` is zero on no rows. | P13; `sql/dialect/sql_quirks.md` §Aggregating Empty Groups |
| `sum()` overflow | `sum(INT)`/`sum(BIGINT)` widen to `HUGEINT`, but `sum(DECIMAL(38,0))`/`sum(HUGEINT)` can overflow; `sum(DOUBLE)` is floating-point. | Cast to `DECIMAL(38,s)` deliberately or use `decimal_average`; don't assume “sum of integers cannot overflow” at the HUGEINT boundary. | P13 |
| Timestamp time zones | `DATE -> TIMESTAMPTZ` uses the session time zone (epoch differs by zone); `TIMESTAMPTZ -> TIMESTAMP` returns local wall time; display follows the session zone. | Store instants as `TIMESTAMPTZ`, do date arithmetic in a chosen zone (`timezone('UTC', ts)`), and set the session zone explicitly in reproducible scripts. | P13; `guides/sql_features/timestamps.md` |
| `CREATE OR REPLACE TABLE` | Recreates the table; PK, constraints, and indexes disappear without a warning. | Use `CREATE TABLE IF NOT EXISTS` + `INSERT`/`MERGE`, or explicitly recreate constraints/indexes. | P2; P10 |
| `PIVOT ... FILTER` | DuckDB accepts `FILTER` in `USING` but silently ignores it. | Compute the filtered aggregate in a subquery/CTE before `PIVOT`, or use `CASE` inside the aggregate. | P2; `sql/statements/pivot.md` |
| Simplified `UNPIVOT` | Drops rows whose value is `NULL`; `INCLUDE NULLS` is only in the SQL-standard `FROM ... UNPIVOT (...)` form. | Use the standard form with `INCLUDE NULLS` when NULL rows matter. | P10; `sql/statements/unpivot.md` |
| `COPY` in a CTE | The file is written, but the outer query returns zero rows; the manual says the CTE returns the number of rows written. | Treat the `COPY` CTE as a side effect only; do not `SELECT rows_written` in 2.0.0. | P4; `sql/statements/copy.md` §COPY TO |
| Trigger `RETURNING` | The restriction is per matching event: INSERT RETURNING fails with an INSERT row trigger, DELETE RETURNING fails with a DELETE row trigger, but UPDATE RETURNING works with an INSERT row trigger. | Check the trigger's event, not just “the table has a row trigger”. | P6 |
| Legacy parser | `SET enable_legacy_parser=true` is a grammar fallback, not a semantic time machine: it rejected `NEAREST`; the manual's listed quirks did not reproduce. | Use it only to test a 1.5 query that fails on PEG, file an issue, and remove it from saved scripts. | P12 |
| Identifier-to-string | `glob(no_such_file.csv)` still works but logs a deprecation warning; `DISABLE_IMPLICIT_STRING` makes it a binder error. | Always quote file/table-function string arguments; the setting itself is deprecated. | P16; `sql/dialect/sql_quirks.md` §Implicit Conversion |
| `USING SAMPLE` placement | Written after `WHERE`/`GROUP BY`, applied before them, so `WHERE` filters after sampling and can leave fewer rows than the percentage suggests. | Put the filter in a subquery/CTE before sampling, or use `TABLESAMPLE` on the table expression. | Documented; `sql/query_syntax/sample.md` |
| `DISTINCT ON` without `ORDER BY` | DuckDB executes it as `first()` per group; the chosen row is arbitrary. | Always add `ORDER BY` that starts with the `DISTINCT ON` expressions. | P13; `sql/query_syntax/select.md` §DISTINCT ON |
| `read_csv(..., union_by_name=true)` | Files with different columns are unioned by name; absent values become `NULL`; `false` raises `Schema mismatch`. | Enable it deliberately and inspect the NULL columns; do not confuse a missing column with a real NULL. | P13; `data/csv/overview.md` |
| `1 IN (0, NULL)` vs `1 IN [0, NULL]` | SQL `IN` returns `NULL`; list `IN` returns `false`. | Use `IS NOT DISTINCT FROM`/`coalesce` when NULL semantics matter; don't mix the two forms. | `sql/dialect/sql_quirks.md` §Results That May Surprise You; P16 |

## What not to add

- A function catalog. The skill needs decisions and failure modes, not an index of every scalar/aggregate function; the manual already is the catalog.
- A separate triggers skill. The pack deliberately folds triggers into `duckdb-sql`; keep the support matrix there.
- A separate lambda skill. Lambda syntax is one small subsection; its edge cases fit in the same section.
- Exhaustive friendly-SQL examples. The reference should cover the clauses an agent will otherwise misuse; it should not reproduce the 197-line manual page.
- PEG grammar internals, parser benchmarks, or the `check_peg_parser` testing utility. The actionable facts are “PEG is default”, “errors have locations”, and “legacy is a last resort”.
- A full type-system chapter. Keep only the type facts that change SQL results (`VARIANT`/`UNION` access, `MAP` missing key, `ARRAY` vs `LIST`, `ENUM` order, `DECIMAL` division).
- Profiling formats (`web`, `html`, `mermaid`), metric names, or `PRAGMA`-style settings. Use `SET` and `EXPLAIN`; `PRAGMA enable_profiling` is deprecated.
- A general “PostgreSQL compatibility” section; the traps table covers the differences an agent will actually hit.

## Probe log

```text
P1  $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/friendly.sql
    FROM t WHERE a > 1 -> a,b,c / 2,20,y / 3,30,z
    SELECT a%2, count(), count() FILTER (...) GROUP BY ALL ORDER BY ALL -> 0,1,1 / 1,2,1
    * EXCLUDE (b) -> a,c; * EXCEPT (b) -> a,c; * REPLACE (b*2 AS b) -> 1,20,x
    [x*2 FOR x IN [1,2,3]] -> [2,4,6]; [10,20,30,40][2:3] -> [20,30]; [-1] -> 40
    struct s.* -> x,y; COLUMNS(*) + 1 -> 2,3
    ASOF LEFT JOIN prices USING (sym, ts) -> A,2024-01-02,10.0
    POSITIONAL JOIN -> 1,a,10 / 2,b,20

P2  $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/friendly2.sql
    UNION ALL BY NAME -> a,b,c / 1,x,NULL / 2,y,9
    UNION BY NAME -> 1,x
    INSERT BY NAME SELECT 7 AS b, 8 AS a -> a,b / 8,7
    CREATE OR REPLACE TABLE dst (z INTEGER) -> table replaced
    PIVOT sales ON q USING sum(amt) GROUP BY yr -> 2024,Q1=10,Q2=20; 2025,Q1=30,Q2=NULL
    UNPIVOT (...) ON x,y INTO NAME k VALUE v -> 1,x,10 / 1,y,20
    DESCRIBE sales -> column_name,column_type,null,key,default,extra
    SUMMARIZE sales -> column_name,...,approx_unique,avg,std,q25,q50,q75,count,null_percentage
    SELECT q,yr FROM sales ORDER BY ALL -> Q1,2024 / Q1,2025 / Q2,2024
    count(), count(*) -> 3,3

P3  $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/nearest.sql
    INNER JOIN p NEAREST 2 BY DISTANCE array_distance(...) -> 1/10,1/11,2/11,2/12
    INNER JOIN p NEAREST 1 BY SIMILARITY array_cosine_similarity(...) -> 1/10,2/12
    APPROX NEAREST 1 ... -> 1/10,2/12
    LEFT JOIN p NEAREST 1 ... -> 1/10,2/12
    NEAREST 0 -> Parser Error: NEAREST expects a positive integer literal, got "0"
    NEAREST 2.5 -> same; no BY -> syntax error

P4  $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/dmcte.sql
    WITH moved AS MATERIALIZED (DELETE FROM staging RETURNING *) INSERT INTO archive SELECT * FROM moved
      -> archive 1,a / 2,b; staging empty
    WITH updated AS (UPDATE orders ... RETURNING *) SELECT count(*) -> 2
    WITH ins AS (INSERT ... RETURNING id) SELECT * FROM ins -> 3
    WITH copied(rows_written) AS (COPY ... TO ...) SELECT * FROM copied -> zero rows, file written
    COPY FROM as CTE body -> Parser Error: COPY FROM cannot be used as a CTE body
    DESCRIBE WITH c(n) AS (COPY ...) SELECT * FROM c
      -> Binder Error: WITH clause containing a COPY statement must be at the top level

P5  $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/schemas.sql
    CREATE SCHEMA sales; CREATE SCHEMA sales.europe; CREATE TABLE sales.europe.orders...
    USE sales.europe -> Not implemented Error: SET schema: "sales.europe" is a nested schema -
      nested schemas cannot be used in the search path
    SET search_path='sales.europe' -> same error; SET search_path='s' -> current_schema()=s, SELECT * FROM t works
    CREATE SCHEMA "a.b"; CREATE TABLE "a.b".t; USE "a.b" -> current_schema() = a.b; SELECT * FROM t works
    DESCRIBE duckdb_schemas() -> ... schema_name, ..., parent_schema, parent_schema_oid
    SHOW SCHEMAS -> database_name,schema_name,current / memory,europe,false / memory,sales,true
    DROP SCHEMA sales.europe -> Dependency Error: ... table "orders" depends on schema "europe"
    $ duckdb ... < schemas2.sql
    CREATE SCHEMA nope.child -> Catalog Error: "nope" is not a catalog or schema
    USE sales; CREATE SCHEMA europe2 -> parent_schema NULL (top-level)
    CREATE TABLE europe.orders2 -> Catalog Error: Schema with name europe does not exist!
    DROP SCHEMA sales CASCADE -> removes sales/europe; europe2 remains
    $ duckdb ... < schemas4.sql
    USE sales; SELECT * FROM europe.orders -> Catalog Error: schema "europe" does not exist
    SELECT * FROM orders -> Catalog Error; SHOW TABLES -> only header; SHOW ALL TABLES -> memory,europe,orders,...

P6  $ bash research/scratch/02-sql/trig_probe.sh; trig_rows.sh; trig_refs.sh; trig_more.sh; trig_more2.sh; trig_body.sh; trig_body2.sh; trig_return.sh; trig_order.sh
    BEFORE INSERT/UPDATE/DELETE STATEMENT -> PASS
    BEFORE ... ROW -> Not implemented Error: BEFORE FOR EACH ROW triggers are not yet supported
    AFTER INSERT ROW NEW.id -> PASS; AFTER DELETE ROW OLD.id -> PASS
    AFTER UPDATE ROW -> Not implemented Error: UPDATE FOR EACH ROW triggers are not yet supported
    AFTER INSERT ROW without NEW/OLD -> Binder Error: ... must reference at least one NEW or OLD column
    STMT INSERT NEW TABLE -> PASS; OLD TABLE -> Binder Error: REFERENCING OLD TABLE AS is not valid
    STMT DELETE OLD TABLE -> PASS; NEW TABLE -> Binder Error: ... not valid for AFTER DELETE
    STMT UPDATE both tables -> PASS; one table -> PASS
    ROW + REFERENCING -> Binder Error: REFERENCING is not valid for FOR EACH ROW triggers
    STMT NEW.id / OLD.id -> Binder Error: Referenced table "NEW"/"OLD" not found
    UPDATE OF statement -> PASS; UPDATE OF row -> UPDATE ... ROW not implemented
    UPDATE OF + transition -> Binder Error: UPDATE OF is not valid with transition tables
    WHEN (...) -> Parser Error: syntax error at or near "WHEN"
    INSERT ... RETURNING with INSERT ROW trigger -> Not implemented: RETURNING ...
    DELETE ... RETURNING with DELETE ROW trigger -> same
    UPDATE ... RETURNING with INSERT ROW trigger -> PASS, returns id
    INSTEAD OF -> Not implemented; view -> Binder Error: CREATE TRIGGER requires a base table
    CREATE TEMP TRIGGER -> Parser Error: Temporary triggers are not supported
    trigger on TEMP table (body uses temp log) -> PASS; duckdb_triggers().temporary = true
    duplicate name same table -> Catalog Error: Trigger with name "trg" already exists!
    OR REPLACE -> PASS; IF NOT EXISTS -> PASS; both -> Parser Error: Cannot specify both ...
    body SELECT/CREATE/PRAGMA/COPY/CALL/BEGIN -> Parser Error
    body two statements without semicolon -> Parser Error
    body WITH ... INSERT -> PASS; body MERGE -> PASS; body INSERT ... RETURNING -> PASS
    body modifies own table -> Not implemented Error: Recursive trigger chains are not yet supported
    multiple triggers b1,b2,a1,a2 -> log 1,before1 / 2,before2 / 3,after1 / 4,after2
    duckdb_triggers() columns -> database_name,...,columns VARCHAR[],for_each,...,temporary,sql
    DROP TRIGGER IF EXISTS b1 ON nosuch -> Catalog Error: Table with name nosuch does not exist!

P7  $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/lambda_edge.sql
    lambda x: x+1 -> [2,3,4]; x -> x+1 -> Binder Error: Deprecated lambda arrow (->)
    SET lambda_syntax='enable_single_arrow'; x -> x+1 -> works
    list_transform([10,20,30], lambda x,i: i) -> [1,2,3]
    list_filter([1,3,1,5], lambda x,i: x>i) -> [3,5]
    list_reduce(['a','b','c','d'], lambda x,y,i: ...) -> a2b3c4d
    list_reduce(..., 'I') -> I1a2b
    list_transform([1,NULL,3], lambda x: x+1) -> [2,NULL,4]
    list_filter([5,-6,NULL,7], lambda x: x>0) -> [5,7]
    nested lambdas -> [0,4,16]; capture column -> [11,12]; shadowing -> [15,16]
    subquery in lambda -> Binder Error: subqueries in lambda expressions are not supported
    COLUMNS(lambda c: c != 'col1') -> col0,col2; COLUMNS(lambda c,i: i=1) -> col0 (1-based)

P8  $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/div.sql
    5//2, -5//2, 5//-2, -5//-2, 5/2 -> 2,-2,-2,2,2.5
    5%2, -5%2, 5%-2, -5%-2 (parenthesized) -> 1,-1,1,-1
    1/0, -1/0, 0/0 -> inf,-inf,nan
    1//0 -> Invalid Input Error: Division by zero in expression (1 // 0). Use TRY(...) ...
    1%0 -> same; TRY(1//0), TRY(1%0) -> NULL,NULL
    SET error_on_division_by_zero=false -> WARNING: deprecated; 1//0,1%0 -> NULL,NULL; 1/0,0/0 -> inf,nan
    5.5//2, -5.5//2, 5.5%2 -> 2.75,-2.75,1.5
    divide(5,2), fdiv(5,2), fdiv(-5,2), decimal_division(10.00,4.00) -> 2,2.0,-3.0,2.500000
    decimal_average over DECIMAL(10,2) -> 1.7; decimal_division type DECIMAL(10,6)

P9  $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/merge_update.sql
    MERGE with two source rows for one target -> Invalid Input Error: MERGE INTO command cannot affect the same target row more than once ...
    UPDATE target SET v=source.v FROM source WHERE target.id=source.id -> id,v / 1,10 (one arbitrary source row; no error), repeat -> 1,10

P10 $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/misc2.sql
    CREATE SECURE VIEW sv AS SELECT ...; EXPLAIN ANALYZE SELECT * FROM sv -> Secure View node
    SET threads=2; SHOW threads -> 2; SHOW t -> deprecation warning + DESCRIBE output
    CREATE SEQUENCE s START 1; nextval=1; setval(s,42)=42; nextval=43; setval(s,100,false)=100; nextval=100
    regexp_extract('2023-04-15','(...)',['y','m','d']) -> {'y':2023,'m':04,'d':15}
    regexp_extract('ABC','abc','i') -> ABC
    GROUP BY unnest(tags) -> a,1 / b,3 / c,1
    CREATE TABLE `weird name` (`select` INTEGER); SELECT `select` ... -> 1
    EXPLAIN (SQL) SELECT 1+2 -> SELECT CAST(3 AS INTEGER) AS answer
    SELECT NULL::STRUCT, struct_pack(), row() -> NULL,{},()
    TIMESTAMPTZ_NS '...123456789' -> ...123456789+05:30
    lttb(x,y,3 ORDER BY x) -> [{'x':1.0,'y':1.0},{'x':3.0,'y':9.0},{'x':5.0,'y':25.0}]
    decimal_division(10.00,4.00), decimal_average -> 2.500000,1.7
    GROUPING_ID() with ROLLUP(y,q) -> 0,0,1,3
    ALTER TABLE v1 RENAME TO v2 on a view -> works
    query('SELECT 42 AS a') -> 42; query_table('t') -> rows

P11 $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/vars.sql
    SET VARIABLE x=7; SELECT $x, getvariable('x') -> 7,7
    SET VARIABLE "my var"=9; SELECT $"my var" -> 9
    SELECT $nope -> Invalid Input Error: Values were not provided for the following parameters: nope
    SELECT getvariable('nope') -> NULL
    SET VARIABLE m=10; SET VARIABLE x=42; PREPARE p AS SELECT $m*$x; EXECUTE p -> 420; EXECUTE p(m:=3) -> 126

P12 $ duckdb -no-agent -csv :memory: -c "..." (parser probes)
    SELECT 1 +; -> Parser Error: syntax error at or near ";" / LINE 1: SELECT 1 +; / caret
    PRAGMA enable_peg_parser / SELECT enable_peg_parser() -> Catalog Error: no such function
    SET enable_legacy_parser=true; SELECT 42 -> 42 (setting autoloads legacy_parser)
    legacy + NEAREST -> Parser Error: syntax error at or near "1"
    legacy + 'abc' ~ '^b' / 'b' -> false,true (same as PEG); B'0101'::VARCHAR -> BIT
    legacy + ORDER BY true -> Binder Error: ORDER BY non-integer literal has no effect
    legacy + INSTALL AND LOAD json -> exit 0 (manual says newer syntax rejected)
    legacy + $x, FETCH FIRST, data-mod CTE, backticks, SHOW, CREATE TRIGGER, SECURE VIEW -> PASS

P13 $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/traps.sql; window.sql; tz.sql; io_traps.sql
    SELECT x ... ORDER BY x -> 1,2,NULL; ORDER BY x DESC -> 2,1,NULL (NULL last both ways)
    GROUP BY x over 1,NULL,2,NULL -> 1,1 / 2,1 / NULL,2
    1='1', 1=' 1', 1='01', 1='1.1', 1=true -> true,true,true,true,true
    5/2,5//2,5.0/2,5::DECIMAL(10,2)/2 -> 2.5,2,2.5,2.5; typeof -> DOUBLE, DOUBLE
    sum(INT)/sum(BIGINT) -> HUGEINT; sum(DECIMAL(10,2)) -> DECIMAL(38,2)
    approx_count_distinct over 1M values 0..99999 -> 99467 vs count(DISTINCT)=100000
    DISTINCT ON (g) ... ORDER BY g,v DESC -> a,2 / b,3; without ORDER BY -> arbitrary first
    QUALIFY rn=1 -> a,2 / b,3
    default sum(x) OVER (ORDER BY x) -> 1:2, 1:2, 2:4, 3:7; ROWS -> 1:1, 1:2, 2:4, 3:7
    DATE '2024-01-01'::TIMESTAMPTZ epoch 1704047400000 vs UTC epoch 1704067200000
    TIMESTAMPTZ '2024-01-01 00:00:00+00'::TIMESTAMP -> 2024-01-01 05:30:00
    glob(no_such_file.csv) -> WARNING: Deprecated implicit conversion ...; DISABLE -> Binder Error
    read_csv([f1,f2], union_by_name=true) -> a,b,c / 1,2,NULL / NULL,3,4; false -> Schema mismatch error

P14 $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/perf.sql
    EXPLAIN SELECT sum(x) FROM t -> plan with estimated cardinality, no execution
    EXPLAIN ANALYZE (FORMAT JSON) ... -> JSON with actual rows/timings
    EXPLAIN (SQL) INSERT ... -> INSERT ... SELECT ... (manual says SELECT/VALUES/WITH only)
    EXPLAIN (SQL, ANALYZE) -> Invalid Input Error: EXPLAIN (SQL) cannot be combined with ANALYZE or FORMAT
    EXPLAIN (SQL) CREATE/COPY -> Not implemented Error: ... supports SELECT, VALUES, WITH, INSERT, UPDATE, DELETE and MERGE INTO statements only
    SET enable_profiling='query_tree'; SELECT 42 -> profile tree on stdout
    SET enable_profiling='json'; SET profiling_output='/tmp/prof3.json'; SELECT 42 (pipe, not `-c`) -> file written; `-c` exits before flush
    SET tracked_metrics=['query.total_time','operator.timing']; duckdb_available_metrics() -> 17 matches
    PRAGMA enable_profiling / profiling_output -> WARNING: deprecated, use SET

P15 $ duckdb -no-agent -csv :memory: < research/scratch/02-sql/fetch.sql
    FETCH FIRST 3 ROWS ONLY -> 0,1,2
    OFFSET 2 ROWS FETCH NEXT 3 ROWS ONLY -> 2,3,4
    FETCH FIRST ROW ONLY -> 0
    FETCH FIRST 10 PERCENT ROWS ONLY -> Parser Error at "PERCENT"
    FETCH FIRST 3 ROWS WITH TIES -> Parser Error at "WITH"
    SELECT count(*) FROM (SELECT * FROM range(9) LIMIT 10%) -> 0; 10 rows -> 1; 1000 -> 100

P16 $ duckdb -no-agent -csv :memory: -c "..."
    1 IN (0,NULL) -> NULL; 1 IN [0,NULL] -> false; concat('abc',NULL) -> abc; 'abc'||NULL -> NULL

P17 $ duckdb -no-agent -csv :memory: -c "..."
    VARIANT keys sorted; variant_typeof -> INT32/VARCHAR/ARRAY(3)/OBJECT(age,name)
    UNION(num INTEGER, str VARCHAR) values + union_tag -> num/str/str
    MAP {'key1':5}['key3'] -> NULL; map_extract(...)['key3'] -> []
    ARRAY INTEGER[3] fixed length; list/array indexing 1-based
    ENUM ('sad','ok','happy') ORDER BY -> sad,ok,happy; 'happy' > 'ok' -> true
    bare DECIMAL is DECIMAL(18,3); DECIMAL(38,0) sum overflow -> Out of Range Error

"`duckdb_triggers()` column list" was also confirmed with `DESCRIBE SELECT * FROM duckdb_triggers()`.
```

## Open questions

- Does the `COPY`-in-CTE zero-row result reproduce through the Python/ODBC/API path, or is it a CLI/result-collector bug? A Python `duckdb.connect().execute(...).fetchall()` on the same statement would settle it.
- Is the `RETURNING`-with-row-trigger restriction intentionally per event, or a binder limitation that will broaden? The binary behavior is clear; the manual's blanket sentence is not.
- The `legacy_parser` manual lists quirks (`~` full match, `B'0101'` as varchar, `ORDER BY true`) that did not reproduce in 2.0.0; the extension build/commit would settle whether the docs are ahead of or behind the binary.
- `EXPLAIN (SQL)` supports `INSERT`/`UPDATE`/`DELETE`/`MERGE` in the binary while the manual says only `SELECT`/`VALUES`/`WITH`; confirm the intended contract before documenting it.

