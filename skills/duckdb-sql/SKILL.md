---
name: duckdb-sql
description: >
  Write and run DuckDB 2.0 SQL. Covers friendly SQL, lambdas, triggers,
  nested schemas, variables, exact decimals, and the result traps that change
  answers silently. Use when the user asks for a query, a trigger, a lambda,
  GROUP BY ALL, PIVOT, MERGE, or a SQL migration.
---

# DuckDB 2.0 SQL

Run statements with the `duckdb` skill. If a session file from `duckdb-session` exists, pass `-init` with it.

## Before a large query

`DESCRIBE` returns the result columns without running the query. `SUMMARIZE` runs the query and computes statistics. A `LIMIT` without `ORDER BY` is not deterministic.

## Lambdas

The single-arrow form is disabled.

```sql
SELECT list_transform([1, 2, 3], lambda x: x + 1);
SELECT list_transform([10, 20], lambda x, i: i);       -- [1, 2], 1-based index
```

`lambda x, i:` gives the element and its 1-based index. A `NULL` element passes through `list_transform`; `list_filter` drops a row when the predicate is `NULL`. A subquery inside a lambda is a binder error. `SET lambda_syntax = 'enable_single_arrow'` restores the old form for the session, and 2.1 removes it.

The higher-order families are `list_transform`, `list_filter`, and `list_reduce`. `COLUMNS(lambda c: ...)` filters columns by name; its optional second parameter is the 1-based column index.

## Division and decimals

| Expression | Result |
| --- | --- |
| `5 / 2` | `2.5`, `DOUBLE` |
| `5 // 2` | `2`, truncates toward zero |
| `-5 // 2` | `-2`, not floor |
| `fdiv(-5, 2)` | `-3.0`, floor |
| `5 % 2`, `-5 % 2` | `1`, `-1`; sign follows the dividend |
| `5.5 // 2` | `2.75`; if either side is decimal or float, `//` is ordinary division |
| `1 / 0`, `0 / 0` | `inf`, `nan` |
| `1 // 0`, `1 % 0` | error |

```sql
SELECT TRY(1 // 0);  -- NULL for this expression
```

`SET error_on_division_by_zero = false` returns `NULL` for integer division and modulo, but the setting is deprecated and warns. Prefer `TRY`.

`avg(DECIMAL)` and any `/` involving `DECIMAL` return `DOUBLE`. Use `sum(x)` for an exact sum, `decimal_average(x)` for an exact average, and `decimal_division(x, y)` for an exact quotient. Cast both `decimal_division` operands to `DECIMAL`; mixed `DECIMAL` and `INTEGER` arguments gave unstable results on 2.0.0.

## Variables

```sql
SET VARIABLE x = 7;
SELECT $x, getvariable('x');
SET VARIABLE "my var" = 9;
SELECT $"my var";
```

`$undefined` raises `Values were not provided ...`; `getvariable('undefined')` returns `NULL`. `$x` is also a prepared-statement parameter, and a named parameter defaults to a session variable of the same name.

## Nested schemas

```sql
CREATE SCHEMA sales;
CREATE SCHEMA sales.europe;
CREATE TABLE sales.europe.orders (id INTEGER);
SELECT * FROM sales.europe.orders;
```

The parent must exist. `USE sales.europe`, `SET search_path = 'sales.europe'`, and `SET schema = 'sales.europe'` all fail: a nested schema cannot sit on the search path. Two-part names resolve from the top level, so `SELECT * FROM europe.orders` after `USE sales` fails. `SHOW TABLES` under `sales` does not list tables in `sales.europe`.

`duckdb_schemas()` exposes `schema_name`, `parent_schema`, and `parent_schema_oid`. `duckdb_tables()` carries `schema_oid` but no parent name, so join the two when the full path matters.

`DROP SCHEMA sales` fails while the subtree exists. `DROP SCHEMA sales CASCADE` removes it. `CREATE SCHEMA "sales.europe"` is one literal top-level name with a dot, and `USE "sales.europe"` works for that schema.

## Triggers

A trigger body is exactly one data-modifying statement: `INSERT`, `UPDATE`, `DELETE`, or `MERGE`, optionally prefixed by `WITH`. A `SELECT`, DDL, `COPY`, `CALL`, or `PRAGMA` body is a parser error. A body that modifies its own table raises `Recursive trigger chains are not yet supported`.

| Shape | Status |
| --- | --- |
| `BEFORE INSERT/UPDATE/DELETE ... FOR EACH STATEMENT` | Works |
| `AFTER INSERT ... FOR EACH STATEMENT REFERENCING NEW TABLE` | Works |
| `AFTER UPDATE ... FOR EACH STATEMENT REFERENCING OLD TABLE, NEW TABLE` | Works |
| `AFTER DELETE ... FOR EACH STATEMENT REFERENCING OLD TABLE` | Works |
| `AFTER INSERT ... FOR EACH ROW` with `NEW.col` | Works |
| `AFTER DELETE ... FOR EACH ROW` with `OLD.col` | Works |
| `BEFORE ... FOR EACH ROW` | Not implemented |
| `AFTER UPDATE ... FOR EACH ROW` | Not implemented |
| Row trigger with `REFERENCING` | Binder error |
| Transition tables on a `BEFORE` trigger | Binder error |
| `UPDATE OF col` on a statement trigger | Works |
| `UPDATE OF` with transition tables | Binder error |
| `WHEN (...)` | Parser error |
| `INSTEAD OF`, triggers on views | Not supported |
| `CREATE TEMP TRIGGER` | Not supported |
| Trigger on a temporary table | Works; `temporary = true` |

Statement-level audit:

```sql
CREATE TRIGGER trg_audit
    AFTER UPDATE ON target
    REFERENCING OLD TABLE AS o NEW TABLE AS n
    FOR EACH STATEMENT
        INSERT INTO audit
        SELECT n.id, o.val, n.val
        FROM o
        JOIN n ON o.id = n.id;
```

`RETURNING` is blocked per matching event: an `INSERT ... RETURNING` fails when the table has an `INSERT` row trigger, and a `DELETE ... RETURNING` fails with a `DELETE` row trigger. `UPDATE ... RETURNING` works with an `INSERT` row trigger. A table whose triggers are all statement-level allows `RETURNING`.

All `BEFORE` triggers fire before all `AFTER` triggers; triggers on the same event fire in creation order. Names are unique per table. `CREATE OR REPLACE TRIGGER` and `IF NOT EXISTS` work, but not together. Inspect with `duckdb_triggers()`.

## 2.0 syntax worth using

| Feature | Form |
| --- | --- |
| `NEAREST` join | `INNER JOIN p NEAREST 2 BY SIMILARITY array_cosine_similarity(q.e, p.e)`; `APPROX NEAREST` for approximate; `BY DISTANCE` when lower is closer; embeddings must be fixed-size arrays such as `DOUBLE[768]` |
| Data-modifying CTE | `WITH moved AS MATERIALIZED (DELETE FROM staging RETURNING *) INSERT INTO archive SELECT * FROM moved` |
| `FETCH FIRST` | `FETCH FIRST 3 ROWS ONLY`; `PERCENT` and `WITH TIES` are parser errors |
| `MERGE INTO` | Errors if one target row matches more than one source row |
| `UPDATE ... FROM` | Multiple matches update once from an unspecified source row; deduplicate |
| `SECURE VIEW` | `CREATE SECURE VIEW v AS SELECT ...`; hides statistics and plan internals |
| `SHOW` | `SHOW threads`, `SHOW DATABASES`, `SHOW SCHEMAS`; `SHOW table` is deprecated in favor of `DESCRIBE` |
| `GROUP BY unnest(col)` | Groups by list elements |
| Backtick identifiers | `` `select` `` is the same as `"select"` |
| `EXPLAIN (SQL)` | Renders the optimized plan as executable SQL; cannot combine with `ANALYZE` or `FORMAT` |
| `query()` / `query_table()` | `FROM query('SELECT 42')`; literal or prepared string only |
| Empty `STRUCT` | `NULL::STRUCT`, `struct_pack()`, `row()`; `STRUCT()` is an error |
| `TUPLE` | `(1, 'a')` is a tuple, not a named struct |
| `TIMESTAMPTZ_NS` | Nanosecond precision; `TIMESTAMPTZ` truncates to microseconds |
| `lttb(x, y, n ORDER BY x)` | Downsample a series |
| `decimal_division`, `decimal_average` | Exact decimal arithmetic |
| `GROUPING_ID()` / `GROUPING()` | No arguments default to all `GROUP BY` columns |
| `ALTER TABLE v RENAME TO v2` | Also renames a view |

`COPY ... FROM` cannot be a CTE body. A `COPY ... TO` inside a CTE writes the file, but on 2.0.0 the outer query returns no rows. Treat it as a side effect and do not read a row count.

## Result traps

| Trap | Behavior | Move |
| --- | --- | --- |
| `NULL` ordering | `ORDER BY x` puts `NULL`s last for both `ASC` and `DESC` | Write `NULLS FIRST` or `NULLS LAST` |
| Integer versus string | `1 = '1.1'` is true; the string is cast and rounded | Cast explicitly and compare like types |
| Decimal division | Any `/` involving `DECIMAL` returns `DOUBLE` | Use `decimal_division` |
| Window frame | `sum(x) OVER (ORDER BY x)` shares a value across ties | Use `ROWS BETWEEN ...` for row-by-row |
| `approx_count_distinct` | Roughly 0.5% low on 1M values | Use `count(DISTINCT x)` for user-visible numbers |
| Empty-group aggregate | `sum`, `list`, and `string_agg` return `NULL`; `count` returns `0` | `coalesce(sum(x), 0)` |
| `sum` overflow | `sum(DECIMAL(38,0))` and `sum(HUGEINT)` can overflow | Cast deliberately to `DECIMAL(38,s)` |
| Timestamps | `DATE -> TIMESTAMPTZ` uses the session zone | Store instants as `TIMESTAMPTZ`; set the zone explicitly |
| `CREATE OR REPLACE TABLE` | Drops constraints and indexes | Use `CREATE TABLE IF NOT EXISTS` plus `INSERT`/`MERGE` |
| `PIVOT ... FILTER` | Accepted and silently ignored | Filter in a subquery before the pivot |
| Simplified `UNPIVOT` | Drops `NULL` values | Use the standard form with `INCLUDE NULLS` |
| `DISTINCT ON` without `ORDER BY` | Returns an arbitrary row | Add an `ORDER BY` starting with the `DISTINCT ON` keys |
| `USING SAMPLE` | Written after `WHERE` but applied before it | Put the filter in a subquery before sampling |
| `1 IN (0, NULL)` | Returns `NULL`; list `IN [0, NULL]` returns false | Use `IS NOT DISTINCT FROM` or `coalesce` |

Friendly-SQL examples and the edge cases behind these rows are in [references/friendly-sql.md](references/friendly-sql.md).

## Parser

The PEG parser is the default and errors carry `LINE n:` and a caret. If a query that worked on 1.5 fails to parse, `SET enable_legacy_parser = true;` autoloads the extension and switches for the session. The legacy parser rejects `NEAREST` and is not a semantic time machine. File the query, use the fallback only to unblock, and remove it from saved SQL.

## Before optimizing

`EXPLAIN` shows the plan with estimated cardinality and does not run the query. `EXPLAIN ANALYZE` runs it and reports actual rows and timings. Use `SET enable_profiling = 'query_tree'` or `tracked_metrics`; `PRAGMA enable_profiling` is deprecated.

## Verify

```sql
SELECT list_transform([1, 2, 3], lambda x: x + 1) AS lambda,
       TRY(1 // 0) AS safe_divide,
       decimal_division(10.00, 4.00) AS exact;
```

Expect `[2, 3, 4]`, `NULL`, and `2.500000`.

## References

- [Friendly SQL](https://duckdb.org/docs/2.0/sql/dialect/friendly_sql.html) owns the clause list.
- [Lambda functions](https://duckdb.org/docs/2.0/sql/functions/lambda.html) owns the syntax and function families.
- [CREATE TRIGGER](https://duckdb.org/docs/2.0/sql/statements/create_trigger.html) owns the trigger contract.
- [Nested schemas](https://duckdb.org/docs/2.0/sql/statements/create_schema.html) owns the path rules.
- [FROM and JOIN](https://duckdb.org/docs/2.0/sql/query_syntax/from.html) owns `NEAREST`, `ASOF`, and `POSITIONAL`.
- [WITH](https://duckdb.org/docs/2.0/sql/query_syntax/with.html) owns data-modifying CTEs.
- [MERGE INTO](https://duckdb.org/docs/2.0/sql/statements/merge_into.html) and [UPDATE](https://duckdb.org/docs/2.0/sql/statements/update.html) own the multi-match rules.
- [PEG parser](https://duckdb.org/docs/2.0/sql/peg_parser.html) and [legacy parser](https://duckdb.org/docs/2.0/core_extensions/legacy_parser.html) own the fallback.
- The friendly-SQL list started from the `query` skill in https://github.com/duckdb/duckdb-skills (MIT). The lambda, trigger, nested-schema, division, and multi-match rules were probed on DuckDB 2.0.0.
