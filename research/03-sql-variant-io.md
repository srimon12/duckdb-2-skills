# DuckDB 2.0.0 SQL briefing: VARIANT, triggers, async I/O, lambdas, PEG parser

Sources are the DuckDB 2.0 docs and the official duckdb.org posts named in the research brief (release announcement 2026-10-21, async I/O 2026-07-31, PEG parser 2026-08-20, and the 2.0 migration guide). Syntax below is copied from those pages. Functions that those pages do not define are not listed.

The preview migration URL (`/docs/preview/operations_manual/migration.html`) redirects to `https://duckdb.org/docs/2.0/operations_manual/migration.html`. The I/O page exists at `https://duckdb.org/docs/2.0/data/io.html` (not a 404). The PEG parser page exists at `https://duckdb.org/docs/2.0/sql/peg_parser.html`.

## VARIANT

`VARIANT` stores typed binary values. Each value carries its own type information, so one column can hold differently shaped rows. That is not the same as the `JSON` type, which is physically stored as text. The type page says the embedded per-value metadata gives `VARIANT` better compression and query performance than `JSON` for semi-structured data. The 2.0 announcement calls it “JSON on steroids” and says it is not a text format. DuckDB 1.5 introduced the type; 2.0 integrates shredding, Parquet read/write, and most `variant_*` functions.

### Casting into VARIANT

Native values cast with `::VARIANT`. JSON text goes through the `JSON` type first, then `VARIANT`. Both forms are in the docs.

```sql
CREATE TABLE events (id INTEGER, data VARIANT);
INSERT INTO events VALUES
    (1, 42::VARIANT),
    (2, 'hello world'::VARIANT),
    (3, [1, 2, 3]::VARIANT),
    (4, {'name': 'Alice', 'age': 30}::VARIANT);
```

```sql
'{"user": {"id": 42, "tags": ["a", "b"]}}'::JSON::VARIANT
```

Object keys are sorted on display: `{'name': 'Alice', 'age': 30}::VARIANT` is returned as `{'age': 30, 'name': Alice}`.

Nested fields can be read with dot notation or `variant_extract`. Both return a `VARIANT`:

```sql
SELECT data.name FROM events WHERE id = 4;
SELECT variant_extract(data, 'name') AS name FROM events WHERE id = 4;
```

### Storage model (shredding)

Shredding of `VARIANT` columns in DuckDB’s own storage was added in 2.0. When a `VARIANT` column is stored in a database file, DuckDB detects the common structure of the values and shreds them: fields that share a type are stored as separate typed columns, so the data compresses and scans like ordinary columns. Shredding applies only to row groups with at least `variant_minimum_shredding_size` rows. The default is 30,000, about one fourth of the default row group size. The configuration reference describes the same option as “Minimum size of a row group to have VARIANT shredding enabled” and says the default is one fourth of the row group size. Setting the option to `-1` turns shredding off:

```sql
SET variant_minimum_shredding_size = -1;
```

The announcement says the execution path is shredded from storage through Parquet read and write.

### What not to do

The docs do **not** say “never store JSON as `VARCHAR`.” They do say the `JSON` type is stored as text, and that `VARIANT` compresses and queries better for semi-structured data. Use a `VARIANT` column (casting JSON with `::JSON::VARIANT`, or casting native values with `::VARIANT`) when the column is semi-structured data. Do not invent a stronger prohibition than that sentence.

### `variant_*` functions the docs actually define

Most of these arrived in 2.0. `variant_extract`, `variant_normalize`, and `variant_typeof` already existed in 1.5. Examples are included only where the function page prints one. `variant_group_object` and `variant_group_array` are aggregates; the second is also a window function because it is a macro for `list(x)::VARIANT`.

| Function | Purpose | Example from the docs | Documented result |
| --- | --- | --- | --- |
| `variant_typeof(v)` | Full type of a `VARIANT`, including nested structure. | `variant_typeof('{"a": 1}'::JSON::VARIANT)` | `OBJECT(a)` |
| `variant_type(v)` | Top-level type category only. | `variant_type('{"a": 1}'::JSON::VARIANT)` | `OBJECT` |
| `variant_keys(v)` | Keys of a `VARIANT` object, as a list. | `variant_keys('{"a": 1, "b": 2}'::JSON::VARIANT)` | `[a, b]` |
| `variant_extract(v, field)` | Nested value by object field name or list index. Returns `VARIANT`. | `variant_extract('{"name": "Fry"}'::JSON::VARIANT, 'name')` | `Fry` |
| `variant_extract_string(v, field)` | Same extraction, returned as `VARCHAR`. | `variant_extract_string('{"name": "Fry"}'::JSON::VARIANT, 'name')` | `Fry` |
| `variant_array_length(v)` | Number of elements in a `VARIANT` array. | `variant_array_length('[1, 2, 3]'::JSON::VARIANT)` | `3` |
| `variant_exists(v, key)` | Whether `key` exists in a `VARIANT` object. | `variant_exists('{"a": 1}'::JSON::VARIANT, 'a')` | `true` |
| `variant_contains(haystack, needle)` | Whether the needle `VARIANT` is contained in the haystack `VARIANT`. | `variant_contains('{"user": {"id": 42}}'::JSON::VARIANT, '{"user": {"id": 42}}'::JSON::VARIANT)` | `true` |
| `variant_comparator(v)` | `BLOB` sort key that orders a `VARIANT` by logical `VARIANT` order (type bucket, then value), not by internal bytes. Used so `VARIANT` compares like the corresponding native types. | `variant_comparator({'a': 1, 'b': 2}::VARIANT)` | A `BLOB` sort key (no literal bytes printed) |
| `variant_normalize(v)` | Canonical form. Two `VARIANT`s that represent the same data normalize to the same result, regardless of construction or physical storage. | `variant_normalize({'b': [1, 2, 3], 'a': 42}::VARIANT)` | A normalized `VARIANT` (no literal printed) |
| `variant_group_object(key, value)` | Aggregate. Builds a `VARIANT` object from `VARCHAR` keys and `VARIANT` values in the group. A `NULL` key or a duplicate key raises an error. | `variant_group_object('duck', 'goose'::VARIANT)` | `{'duck': goose}` |
| `variant_group_array(x)` | Aggregate and window. Collects `x` into a `VARIANT` array, preserving order. Equivalent to `list(x)::VARIANT`. `NULL`s are kept as `VARIANT` nulls. | `variant_group_array(i)` | `[0, 1, 2, 3]` |

The comparator page also shows ordering of native integers cast to `VARIANT`:

```sql
SELECT i
FROM range(-2, 2) t(i)
ORDER BY i::VARIANT;
```

That returns `-2`, `-1`, `0`, `1`.

A filtering example from the same page:

```sql
SELECT *
FROM events
WHERE variant_contains(payload, {'user': {'id': 42}}::VARIANT);
```

`variant_typeof` on the mixed `events` table in the type page returns `INT32`, `VARCHAR`, `ARRAY(3)`, and `OBJECT(age, name)`. `variant_type` on an object returns the category `OBJECT`, not the field list.

### Parquet read and write

The type page links Parquet support to the general Parquet overview. That overview page does not itself document `VARIANT`. The read/write rules are on the type page, and the copy option is on the `COPY` statement page.

DuckDB reads and writes `VARIANT` in Parquet, including shredding (nested data stored as flat typed values). On write, DuckDB can auto-shred from the structure of the first row group. The type page says that enables predicate pushdown and column access. To force a schema, pass `SHREDDING`:

```sql
COPY events TO 'events.parquet' (
    FORMAT parquet,
    SHREDDING {'data': 'STRUCT(name VARCHAR, age INTEGER)'}
);
```

The `COPY` reference describes `SHREDDING` as a `STRUCT` mapping `VARIANT` column names to the type they should be shredded into, default empty. Its example is `{variant_col: 'STRUCT(name VARCHAR, age INTEGER)'}`.

Reading: DuckDB reads shredded `VARIANT` Parquet written by Snowflake and reconstructs the variant values from the shredded columns. The type is the Parquet variant encoding added in 2025 (`VariantEncoding.md`).

## Triggers

`CREATE TRIGGER` is new in 2.0. A trigger is one SQL statement that runs on `INSERT`, `UPDATE`, or `DELETE` against a base table. The statement page says that statement is typically a data-modification statement such as `INSERT`, `UPDATE`, or `DELETE`. The 2.0 announcement also uses `MERGE INTO` as the triggered statement (incremental aggregate maintenance). There is no `WHEN` clause, no `INSTEAD OF`, no trigger on a view, and no multi-statement body in the documented syntax.

The docs do not print one grammar diagram. The clauses they do define combine as follows. Do not add clauses that are not in this list.

```sql
CREATE [OR REPLACE] TRIGGER name
    | CREATE TRIGGER IF NOT EXISTS name
    { BEFORE | AFTER } { INSERT | DELETE | UPDATE [ OF column_name ] } ON table_name
    [ REFERENCING
        [ OLD TABLE AS alias ]
        [ NEW TABLE AS alias ] ]
    FOR EACH { ROW | STATEMENT }
        single_sql_statement;
```

`OR REPLACE` and `IF NOT EXISTS` cannot be combined. Without either, a duplicate name on that table is an error. `CREATE OR REPLACE TRIGGER` replaces the trigger of the same name. `CREATE TRIGGER IF NOT EXISTS` does nothing if that name already exists on the table.

### BEFORE / AFTER

- `BEFORE` runs before the triggering statement is applied.
- `AFTER` runs after it is applied.

### FOR EACH ROW vs FOR EACH STATEMENT

- `FOR EACH ROW` runs once per affected row. The triggered statement sees that row as `NEW` (for `INSERT`) and `OLD` (for `DELETE`).
- `FOR EACH STATEMENT` runs once per statement, however many rows changed. Affected rows are not `NEW`/`OLD` row aliases; they are transition tables (next section).

Row-level example from the statement page:

```sql
CREATE TRIGGER trg_log
    AFTER INSERT ON t
    FOR EACH ROW
        INSERT INTO log VALUES (NEW.id);
```

`UPDATE OF` limits an update trigger to named columns:

```sql
CREATE TRIGGER trg_price
    AFTER UPDATE OF price ON products
    FOR EACH STATEMENT
        INSERT INTO price_changes DEFAULT VALUES;
```

### REFERENCING

Only statement-level triggers expose transition tables:

- `NEW TABLE` is the inserted or post-update rows. Available for `INSERT` and `UPDATE`.
- `OLD TABLE` is the deleted or pre-update rows. Available for `UPDATE` and `DELETE`.

```sql
CREATE TRIGGER trg_audit
    AFTER UPDATE ON target
    REFERENCING
        OLD TABLE AS o
        NEW TABLE AS n
    FOR EACH STATEMENT
        INSERT INTO audit
        SELECT n.id, o.val, n.val
        FROM o
        JOIN n ON o.id = n.id;
```

### Multiple triggers

A table may have several triggers for the same event. They fire in creation order.

### RETURNING

A modifying statement on a table that has `FOR EACH STATEMENT` triggers may still use `RETURNING`. The trigger runs as part of the statement. `RETURNING` reports rows affected by the statement itself, not rows written by the trigger:

```sql
INSERT INTO t VALUES (1), (2) RETURNING id;
```

(The statement page pairs that `INSERT` with an `AFTER INSERT ... FOR EACH STATEMENT` trigger that does `INSERT INTO log SELECT count(*) FROM t`.)

### DROP TRIGGER

The table must be named. It may be schema-qualified (`ON my_schema.target`). The table must exist even with `IF EXISTS`.

```sql
DROP TRIGGER trg_audit ON target;
DROP TRIGGER IF EXISTS trg_audit ON target;
```

Dropping a missing trigger without `IF EXISTS` is an error. Dropping a table drops its triggers.

Inspect with `duckdb_triggers()`. The documented projection is:

```sql
SELECT trigger_name, table_name, action_timing, event_manipulation, for_each
FROM duckdb_triggers();
```

### Documented limitations (2.0)

These combinations are unsupported. Do not generate them.

- `BEFORE ... FOR EACH ROW` is not supported.
- `UPDATE ... FOR EACH ROW` is not supported. So there is no documented row-level `NEW`/`OLD` pair for `UPDATE`.
- `RETURNING` is not supported on a table that has any `FOR EACH ROW` trigger.
- `INSTEAD OF` triggers are not supported. Triggers on views are not supported. The target must be a base table.
- Temporary triggers are not supported.

The announcement names the same two gaps (`BEFORE ... FOR EACH ROW` and `UPDATE ... FOR EACH ROW`) and points at that limitations section. The statement page defines `BEFORE` as a timing and only calls out `BEFORE ... FOR EACH ROW` as unsupported, but it never shows a `BEFORE ... FOR EACH STATEMENT` example.

## Asynchronous I/O

Introduced in 2.0 and **on by default** for the formats that support it. DuckDB issues reads in the background and keeps multiple requests in flight while worker threads process data that has already arrived. The documented payoff is remote bandwidth that synchronous reads do not fill, for example `s3://`. It is also used automatically when those formats are read through a lake format such as DuckLake. The July 2026 design post says the same, and adds that any DuckDB-supported data lake already benefits when the underlying files are Parquet (or CSV).

### Formats

Supported, and therefore asynchronous by default:

- Parquet files.
- Uncompressed, seekable CSV encoded as UTF-8.

Not asynchronous. The 2.0 I/O page says these stay synchronous:

- JSON files.
- DuckDB’s native database format.

The July post said JSON and native-file async reads were still planned, and that out-of-tree extension formats were not on the roadmap. The 2.0 docs are the current statement: JSON is synchronous; native DuckDB storage is async.

### Thread pools and SET commands

Two pools:

- Regular workers do decoding, joins, and aggregations. Size is `threads` (alias `worker_threads`), default one per CPU core. They prefer query work and can do I/O when idle.
- The async pool is for blocking I/O. Default is `4 ×` system threads, capped at 256, because those threads mostly wait. Size is `async_threads`.

```sql
SET async_threads = 48;
```

The I/O page warns that the async pool raises the thread count per DuckDB instance. If many instances share a process, set `threads` and `async_threads` explicitly.

Read-ahead schedules upcoming scan jobs (Parquet row groups, or CSV byte ranges) before workers need them. `read_ahead_depth`:

- `-1` (default): unlimited depth, bounded by memory. The budget is negotiated with the same memory manager as joins, sorts, and windows. Under memory pressure the queue shrinks to one job and the scan behaves like a synchronous scan, then fills again when memory frees. Cap total memory with `memory_limit`, not with an invented I/O knob.
- `N > 0`: at most `N` jobs ahead, and **no** memory budget.
- `0`: read-ahead off. Each scan task schedules I/O only for its own job.

```sql
SET read_ahead_depth = 5;
```

The configuration reference matches those defaults: `async_threads` default `4 × # CPU cores (max. 256)`, `read_ahead_depth` default `-1` with the description “-1 = automatic, with the backlog being bound by a memory budget, 0 = disabled.”

Defaults are what the I/O page says to use in most cases. The only tuning block it prints, for a 64-core EC2 instance that saturated a 25 Gbit/s link reading Parquet from S3, is:

```sql
SET read_ahead_depth = 64;
SET async_threads = 48;
SET http_retries = 8;
SET http_retry_wait_ms = 50;
SET http_retry_backoff = 2;
```

Do not treat those numbers as universal defaults. They are one documented high-bandwidth example.

Also new in 2.0, on the same tuning section: `http_client_pool_capacity`. By default the HTTP client pool is derived from CPU threads and async threads, bounded by the OS file-descriptor limit, and capped at 256. Changing `async_threads` resizes that automatic pool so it tracks the async pool. A positive integer pins the pool. `RESET` returns it to automatic:

```sql
SET http_client_pool_capacity = 8;
RESET http_client_pool_capacity;
```

Practical advice that is actually written down:

- A Parquet row group is the unit of scan parallelism. Async I/O works best when the file has at least as many row groups as threads. A file with a few very large row groups cannot keep enough requests in flight to fill the network.
- `prefetch_all_parquet_files` is deprecated and has no effect; the configuration reference says Parquet files are now always prefetched.
- The same I/O page documents `fsync_mode` (`STANDARD` default, `FULL`, `NONE`) for **local database write** durability. That is not the async read path. `NONE` can lose data or corrupt the database on OS crash or power loss.

The July post’s benchmarks (TPC-H Q6, SF100, S3) are design evidence, not settings: Parquet about 8.230 s (v1.5.5) to 2.844 s (v2.0.0-dev); the tuned run above was 2.227 s; cold local Parquet about 1.5×; CSV about 878 s to 45 s. Do not quote those as 2.0.0 guarantees.

## Lambdas

DuckDB 2.0 disables the single-arrow lambda by default. DuckDB 2.1 will remove both the syntax and the setting. This is a breaking change called out in the migration guide and the release announcement.

Disabled (default):

```sql
SELECT list_transform([1, 2, 3], x -> x + 1);
```

Replacement. The lambda page’s syntax line is `lambda parameters : expression`. The migration guide writes spaces around the colon. Several examples on the lambda page omit the space before the colon (`lambda x: x + 1`). Both spellings appear in the docs; the syntax line is the one with spaces:

```sql
SELECT list_transform([1, 2, 3], lambda x : x + 1);
```

The announcement’s spelling is `lambda x: x + 1` (no spaces).

Parameters are a comma-separated list of names. List functions always pass the current element (usually the first parameter) and may pass a 1-based index as the last parameter. The expression must be scalar: no subquery, no table function. Scalar macros are allowed inside the expression only if they do not use a subquery. A lambda cannot be returned from a macro; it has to be written inline. `COLUMNS` lambdas are a separate use: the first parameter is the column name, and an optional second parameter is the 1-based column index. The lambda keeps the column when it returns true.

Documented list functions that take a lambda: `list_transform` / `list_apply` / `apply` / `array_apply` / `array_transform`; `list_filter` / `filter` / `array_filter`; `list_reduce` / `reduce` / `array_reduce` (optional `initial_value`). Examples that match the page:

```sql
list_filter([3, 4, 5], lambda x : x > 4)          -- [5]
list_reduce([1, 2, 3], lambda x, y : x + y)       -- 6
list_transform([1, 2, 3], lambda x : x + 1)       -- [2, 3, 4]
list_filter([1, 3, 1, 5], lambda x, i: x > i)     -- [3, 5]
```

### Re-enable the arrow

`lambda_syntax` is a deprecated `VARCHAR`, scope `GLOBAL`, default `DEFAULT`. The lambda page lists three values:

```sql
SET lambda_syntax = 'default';              -- 2.0: Python-style only
SET lambda_syntax = 'enable_single_arrow';  -- temporary: arrow works again
SET lambda_syntax = 'disable_single_arrow';
```

From 1.3 through 1.5, `default` allowed both syntaxes. 1.5 was the last release that accepted `x -> x + 1` without an explicit setting. In 2.0, `default` is Python-style only. The migration guide and the announcement both tell you to re-enable with:

```sql
SET lambda_syntax = 'enable_single_arrow';
```

The flag and the single-arrow syntax are removed in v2.1. Do not generate `->` lambdas for 2.0 unless that setting is in force, and do not present the setting as permanent.

## PEG parser

From 2.0 the PEG parser is the default. It replaces the PostgreSQL-derived front end. In 1.5 it was experimental and opt-in via `enable_peg_parser()`. That function is no longer required and is no longer available. The grammar first appeared in 1.2 for CLI autocomplete.

What an agent needs to know:

- **Compatibility claim.** Switching parsers does not change the SQL dialect. The parser and grammar were replaced; the binder and the rest of the pipeline still consume the same internal syntax tree. Queries that parsed before should still parse. If one fails on 2.0.0, the docs say to file an issue. The migration guide repeats that claim.
- **Errors.** Error messages include precise source locations. The August post shows a syntax error with `LINE` and a caret under the offending token, and a separate catalog/binder error once the statement has parsed (`Table with name missing_table does not exist!`). Parse success is not bind success.
- **Extensions can extend the grammar.** The 2.0 docs say an extension can extend the tokenizer, add grammar rules, and register custom matchers, and can reuse the rest of DuckDB’s grammar, so syntax from more than one extension can be combined. The August post’s C++ registration sample was explicitly a preview that might change before 2.0. The shipped docs do not publish that API. Do not generate PEG rules or that registration code.
- **Fallback.** For exceptional cases, `SET enable_legacy_parser = true` switches to the old parser. The PEG page says that setting autoloads the `legacy_parser` extension. The extension page and the migration guide also show an explicit install:

```sql
INSTALL AND LOAD legacy_parser;
SET enable_legacy_parser = true;
```

Switch back with `SET enable_legacy_parser = false`. The legacy parser is a bridge, not the default. It rejects newer syntax such as `INSTALL AND LOAD`. It keeps several 1.5 quirks, which means the **default PEG parser does the opposite**:

- `~` and `!~` are partial regular-expression matches on PEG (2.0 default). On the legacy parser they are full matches. The pattern-matching page says the same change in its own words: as of 2.0, `~` / `!~` are partial by default and map to `regexp_matches`; `~*` / `!~*` are the case-insensitive forms. `regex_match_operator_semantics = 'full'` restores full-match `~` / `!~` (maps to `regexp_full_match`) but is deprecated and will be removed.
- `B'0101'` is a bit-string literal on PEG. On the legacy parser it is the `VARCHAR` `'b0101'`.
- PEG rejects `ORDER BY true` (non-integer literal). The legacy parser accepts it.
- Rendered SQL on the legacy parser qualifies built-in functions (`main.struct_pack(x := 1)` in view definitions). That is described as a legacy quirk, not as PEG behavior.
- Column constraints on `ALTER TABLE ... ADD COLUMN`, such as `UNIQUE`, are rejected by the legacy transformer.
- `preserve_identifier_case = 'uppercase'` is a 2.0 feature. The legacy grammar treats that setting as `'preserve_case'`.

`check_peg_parser` (from the `autocomplete` extension) is a testing utility. In 2.0.0 it returns an empty result even for invalid SQL such as `SELEC 42`, so it does not reliably report parse failure. To test parse without binding or executing, use `json_serialize_sql` from the `json` extension. A failed parse has `"error": true`:

```sql
SELECT json_serialize_sql('SELEC 42')::JSON->>'error' AS parse_error;
```

Packrat parsing memoizes intermediate matches. The docs say the extra memory and the overhead are milliseconds and negligible for analytical queries. That is not a user setting.

## Other 2.0 SQL behavior changes

These are the behavior changes linked from “What’s New in the Docs for 2.0” and the migration guide. They are not a catalog of new functions. An agent that emits 1.x SQL will get these wrong.

**Integer division by zero.** `//` and `%` by zero (`1 // 0`, `1 % 0`) throw instead of returning `NULL`. The pragmas page adds `INTERVAL '1' DAY / 0` to that list. The error text tells you to use `TRY(1 // 0)` for one expression, or `SET error_on_division_by_zero = false` for all of them. That setting is deprecated, prints a warning, and will be removed. Ordinary `/` still follows IEEE: `1 / 0` is `inf`, unless `ieee_floating_point_ops` is set to false.

**`UPDATE ... FROM` vs `MERGE INTO` when several source rows match.** `MERGE INTO` must not touch the same target row twice. If a `WHEN MATCHED` action would apply to a target row that matches more than one source row, it errors: “MERGE INTO command cannot affect the same target row more than once.” Deduplicate the source or make `ON` unique. `UPDATE ... FROM` does the opposite: the target row is updated once, using one of the matching source rows, and which one is not specified. The scalar-subquery form of `UPDATE` errors if the subquery returns more than one row, unless `scalar_subquery_error_on_multiple_rows` is false (that setting is deprecated; the configuration reference says throwing will become the default and is already the default).

**`$name` is not `getvariable` when unset.** For a variable that is set, `$my_var` and `getvariable('my_var')` are the same, and `$name` is allowed anywhere an expression is allowed. Names that are not identifiers are quoted: `$"my var"`. If the variable was never set, `getvariable` returns `NULL` and `$undefined_var` raises `Invalid Input Error: Values were not provided for the following parameters: undefined_var`.

**Bare identifiers passed to table functions.** `glob(no_such_file.csv)` used to mean `glob('no_such_file.csv')`. In 2.0 that conversion is deprecated. `table_function_identifier_conversion` defaults to `DEFAULT` (convert and warn). `ENABLE_IMPLICIT_STRING` converts silently. `DISABLE_IMPLICIT_STRING` raises a binder error. Emit a string literal.

**`preserve_identifier_case` is a string.** Values are `'preserve_case'` (default), `'lowercase'`, and `'uppercase'`. Old booleans still work: `true` maps to `'preserve_case'`, `false` to `'lowercase'`.

**`FETCH FIRST`.** Alternative to `LIMIT`, new in 2.0. `FIRST` and `NEXT` are interchangeable, and so are `ROW` and `ROWS`. Omitting the count fetches one row.

```sql
SELECT *
FROM addresses
ORDER BY city
OFFSET 5 ROWS
FETCH NEXT 10 ROWS ONLY;
```

**`GROUP BY unnest(...)`.** New in 2.0. `UNNEST` may appear in `GROUP BY` so aggregates run per list element:

```sql
SELECT unnest(tags) AS tag, count(*) AS n
FROM (VALUES (['a', 'b']), (['b', 'c']), (['b'])) t(tags)
GROUP BY unnest(tags)
ORDER BY tag;
```

**S3 URL query parameters.** `s3://bucket/file.csv?s3_access_key_id=...` no longer sets S3 options. The `?` and the rest are part of the object key. Use secrets, or opt back in with `SET s3_enable_deprecated_url_parameters = true` after loading `httpfs`.

Removed or ignored settings an old script might still emit: `custom_profiling_settings` (use `tracked_metrics`), `enable_http_logging` and `http_logging_output` (use `CALL enable_logging('HTTP')`), and `profiling_mode` (deprecated, value ignored; use `PRAGMA enable_profiling`).

Dialect additions that are new syntax rather than changed semantics, and that this briefing does not expand: `NEAREST` joins, data-modifying CTEs (`INSERT` / `UPDATE` / `DELETE` / `COPY` inside `WITH`), nested schemas (`CREATE SCHEMA finance.reports`), JSON mutation functions `json_set`, `json_insert`, `json_replace`, `json_remove`, and `CONNECT` / `DISCONNECT`. Storage-format compatibility (new files are storage version 69; DuckDB before 2.0 cannot read them; 2.0 can still read and write older files) is in the migration guide, not a SQL-syntax change.

## Uncertainties

- The `CREATE TRIGGER` page never prints a single formal grammar. The sketch above is only the clauses that page defines. It does not show whether `BEFORE ... FOR EACH STATEMENT` actually runs. That form is not in the unsupported list (only `BEFORE ... FOR EACH ROW` is), and it is also not in any example.
- The announcement’s audit trigger is valid against the statement page. Its `MERGE INTO` trigger bodies are only in the announcement, not on the statement page. The statement page says the body is a single SQL statement, “typically” `INSERT`, `UPDATE`, or `DELETE`. It does not say other statements are rejected.
- Row-level `UPDATE` is unsupported, so there is no documented way to mention both `NEW` and `OLD` as row aliases. Transition tables are the documented way to see pre- and post-update rows, and only at statement granularity.
- No separate Parquet “read VARIANT” or “write VARIANT” page is linked. The type page points at the general Parquet overview, which does not mention `VARIANT` or `SHREDDING`. Write details are the type page plus the `COPY` option. The two `SHREDDING` literals differ in quoting (`{'data': 'STRUCT(...)'}` versus `{variant_col: 'STRUCT(...)'}`). Both are printed in the docs. Nothing here says what happens when the declared shredding schema does not match later rows, or whether auto-shredding uses only the first row group’s keys.
- The docs never say “do not store JSON as `VARCHAR`.” They compare `VARIANT` with the `JSON` type, which is stored as text.
- `variant_group_array(i)` is shown with result `[0, 1, 2, 3]` without the query that produced `i`. `variant_comparator` and `variant_normalize` results are described, not printed as literals.
- `variant_extract`’s description says the second argument may be a list index. The only example uses an object field name. Index base (0 versus 1) is not stated on that page.
- The July 2026 async-I/O post describes implementation detail (job = one Parquet row group, CSV scan boundaries, memory governor) and says JSON and native async reads were still to come. The 2.0 I/O page is the behavior to follow: JSON is synchronous; async is the default for Parquet, uncompressed seekable UTF-8 CSV, and native DuckDB storage. Benchmark timings in that post are v2.0.0-dev, not the 2.0.0 release.
- `SET enable_legacy_parser = true` is said to autoload `legacy_parser` on the PEG page. The migration guide and the extension page still show `INSTALL AND LOAD legacy_parser` first. This briefing does not resolve which is required in every client.
- The August PEG post’s extension-registration API was a pre-release preview. The 2.0 parser page confirms that extension grammars exist and does not document how to write one.
- `check_peg_parser` returning no rows does not mean the query parsed. The docs say that explicitly for 2.0.0.
- Lambda spacing (`lambda x : x + 1` versus `lambda x: x + 1`) is inconsistent across the migration guide, the announcement, and the lambda page. The syntax line uses spaces around `:`.
- The Delta extension’s `VARIANT` column support is linked from What’s New. This briefing does not copy that extension’s syntax.
- None of this was executed against a DuckDB 2.0.0 binary.
