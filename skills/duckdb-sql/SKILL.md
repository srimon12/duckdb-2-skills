---
name: duckdb-sql
description: >
  Write and run DuckDB 2.0 SQL. Covers friendly SQL, lambdas, triggers,
  nested schemas, variables, exact decimals, and the result traps that change
  answers silently. Use when the user asks for a query, a trigger, a lambda,
  GROUP BY ALL, PIVOT, MERGE, or a SQL migration.
---

# DuckDB 2.0 SQL

Execute statements with `duckdb`. If a session file from `duckdb-session` exists, supply it via `-init`.

## Before a large query

To inspect result columns and types without executing a query, run `DESCRIBE SELECT ...`. To compute full column statistics across all rows, run `SUMMARIZE <table>`. When restricting query output, never run `LIMIT` without an explicit `ORDER BY`; unordered limits return nondeterministic rows.

## Lambdas

DuckDB disables single-arrow syntax; write `lambda x: expr`. Higher-order list functions comprise `list_transform`, `list_filter`, and `list_reduce`:

```sql
SELECT list_transform([1, 2, 3], lambda x: x + 1);
SELECT list_transform([10, 20], lambda x, i: i);       -- [1, 2], 1-based index
```

When tracking positions, use `lambda x, i:` for the element and its 1-based index.
When encountering `NULL`, `list_transform` preserves `NULL` elements; `list_filter` drops elements whose predicate evaluates to `NULL`.
Never write subqueries inside lambdas; subqueries raise a binder error.
If legacy syntax is required to unblock queries, run `SET lambda_syntax = 'enable_single_arrow';` (removed in 2.1).
To filter projection columns by name, write `COLUMNS(lambda c: ...)`; supply an optional second argument `lambda c, i:` for the 1-based column index.

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
SELECT TRY(1 // 0);  -- returns NULL
```

To catch division by zero on integer division or modulo without failing, wrap expressions in `TRY(...)`. Avoid `SET error_on_division_by_zero = false`; this setting is deprecated and emits warnings.

Because `avg(DECIMAL)` and standard `/` operations cast operands to `DOUBLE`, run dedicated decimal functions for exact arithmetic:
- To sum without precision loss, use `sum(x)`.
- To compute an exact mean, use `decimal_average(x)`.
- To divide exact values, use `decimal_division(x, y)`. Cast both operands explicitly to `DECIMAL`; mixing `DECIMAL` and `INTEGER` arguments yielded unstable types on 2.0.0.

## Variables

```sql
SET VARIABLE x = 7;
SELECT $x, getvariable('x');
SET VARIABLE "my var" = 9;
SELECT $"my var";
```

To define a session variable, run `SET VARIABLE name = value;`. Query variables using `$name` or `getvariable('name')`.
For identifiers containing spaces or special characters, quote with double quotes: `SET VARIABLE "my var" = 9; SELECT $"my var";`.
When querying an unassigned variable, `$undefined` raises `Values were not provided ...`, whereas `getvariable('undefined')` returns `NULL`.
In prepared statements, parameter placeholders (`$x`) fall back to session variables of the same name when omitted from execution arguments.

## Nested schemas

```sql
CREATE SCHEMA sales;
CREATE SCHEMA sales.europe;
CREATE TABLE sales.europe.orders (id INTEGER);
SELECT * FROM sales.europe.orders;
```

When creating a nested schema, create the parent schema first (`CREATE SCHEMA sales; CREATE SCHEMA sales.europe;`).
Nested schemas cannot sit on the search path: `USE sales.europe`, `SET search_path = 'sales.europe'`, and `SET schema = 'sales.europe'` all fail.
Two-part references resolve from the catalog root, not relative to the current schema; running `SELECT * FROM europe.orders` after `USE sales` fails.
Running `SHOW TABLES` inside `sales` lists only immediate tables, omitting `sales.europe.*`.
To inspect full schema paths, join `duckdb_tables()` with `duckdb_schemas()` on `schema_oid = oid`, exposing `schema_name`, `parent_schema`, and `parent_schema_oid`.
To drop a schema tree, specify `CASCADE`: `DROP SCHEMA sales CASCADE`. A bare `DROP SCHEMA sales` fails while child schemas exist.
If a top-level schema name requires an embedded dot, quote the identifier: `CREATE SCHEMA "sales.europe"` creates a single top-level schema where `USE "sales.europe"` succeeds.

## Triggers

A trigger body must consist of exactly one data-modifying statement: `INSERT`, `UPDATE`, `DELETE`, or `MERGE`, optionally prefixed by `WITH`. Any `SELECT`, DDL, `COPY`, `CALL`, or `PRAGMA` body causes a parser error. A body modifying its own target table raises `Recursive trigger chains are not yet supported`.

On any single table, never mix `FOR EACH STATEMENT` and `FOR EACH ROW` triggers.
When attaching triggers to temporary tables, reference only temporary objects; modifying main-catalog tables raises a catalog binder error.
DuckDB does not support `BEFORE ... FOR EACH ROW`, `AFTER UPDATE ... FOR EACH ROW`, row triggers with `REFERENCING`, `WHEN`, `INSTEAD OF`, or `CREATE TEMP TRIGGER`.

For the trigger support matrix, `RETURNING` rules, execution order, and metadata queries, read [references/triggers.md](references/triggers.md).

## DML proof

When executing `UPDATE`, `DELETE`, or `MERGE`, follow this verification sequence:

1. `BEGIN` transaction.
2. Count matching predicate rows. Before executing `MERGE` or `UPDATE ... FROM`, deduplicate the source table: a target row matching multiple source rows causes a runtime error in `MERGE` and updates from an arbitrary source row in `UPDATE ... FROM`.
3. Run the DML statement. If a matching row trigger exists on the table, DuckDB blocks `RETURNING` (see event rules in [references/triggers.md](references/triggers.md)). When `RETURNING` is blocked, verify modifications via before-and-after row counts or CLI `.changes`.
4. `COMMIT`, then re-count. Treat zero rows affected as an operation result, not proof of success. Never use `RETURNING` as the sole proof when row triggers exist.

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

`COPY ... FROM` cannot serve as a CTE body. A `COPY ... TO` inside a CTE executes the write, but on 2.0.0 the outer query returns zero rows. Treat CTE `COPY ... TO` purely as a side effect and do not expect a row count.

## Result traps

| Trap | Behavior | Move |
| --- | --- | --- |
| `NULL` ordering | `ORDER BY x` puts `NULL`s last for both `ASC` and `DESC` | Write `NULLS FIRST` or `NULLS LAST` explicitly |
| Integer versus string | `1 = '1.1'` evaluates to true; string is cast to integer and rounded | Cast explicitly and compare matching data types |
| Decimal division | Any `/` involving `DECIMAL` returns `DOUBLE` | Use `decimal_division(x, y)` |
| Window frame | `sum(x) OVER (ORDER BY x)` defaults to `RANGE ...` and ties share cumulative totals | Specify `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` for row-by-row accumulation |
| `approx_count_distinct` | Error is data-dependent and can swing several percent | Use exact `count(DISTINCT x)` for user-facing metrics |
| Empty-group aggregate | `sum`, `list`, and `string_agg` return `NULL`; `count` returns `0` | Wrap with `coalesce(sum(x), 0)` |
| `sum` overflow | `sum(DECIMAL(38,0))` and `sum(HUGEINT)` can silently overflow | Cast explicitly to `DECIMAL(38,s)` |
| Timestamps | Casting `DATE` to `TIMESTAMPTZ` evaluates in session time zone | Store instants as `TIMESTAMPTZ`; set time zone explicitly |
| `CREATE OR REPLACE TABLE` | Drops existing constraints, primary keys, and indexes without warning | Use `CREATE TABLE IF NOT EXISTS` plus `INSERT` or `MERGE` |
| `PIVOT ... FILTER` | Accepted by parser and silently ignored | Compute filtered aggregates in a CTE prior to pivoting |
| Simplified `UNPIVOT` | Silently drops rows with `NULL` values | Use standard `UNPIVOT (... INCLUDE NULLS)` |
| `DISTINCT ON` without `ORDER BY` | Selects an arbitrary row for each group | Add `ORDER BY` starting with the `DISTINCT ON` key columns |
| `USING SAMPLE` | Written after `WHERE` but evaluated before the filter | Place filter in a subquery prior to sampling |
| `NEAREST ... AND <filter>` | Filter joins the distance ranking key, returning non-nearest rows | Filter candidate rows in a CTE before joining |
| `1 IN (0, NULL)` | Scalar returns `NULL`; list `1 IN [0, NULL]` returns false | Use `IS NOT DISTINCT FROM` or `coalesce` |
| `~`, `!~` | 2.0 matches substrings; 1.x matched full string | Use `regexp_full_match` for 1.x semantics; see `duckdb-migrate` |

For friendly-SQL patterns and edge-case examples behind these traps, read [references/friendly-sql.md](references/friendly-sql.md).

## Parser

The PEG parser is active by default; syntax errors report `LINE n:` with an exact position caret. If a query that parsed in 1.5 fails under 2.0, run `SET enable_legacy_parser = true;` to autoload the extension and switch parsers for the session. Note that the legacy parser rejects simplified `FROM ... NEAREST` syntax; explicit `INNER JOIN ... NEAREST` still parses. Treat the legacy parser strictly as a temporary syntax fallback to unblock migrations, not a semantic time machine. File an upstream issue, unblock immediately, and remove the setting from production SQL.

## Before optimizing

When reading execution plans, comparing `EXPLAIN` against `EXPLAIN ANALYZE`, profiling operator bottlenecks, or diagnosing memory spills, hand off to `duckdb-profile`. `EXPLAIN (SQL)` belongs here because it decompiles optimized query representations back into executable SQL rather than reporting runtime profile metrics.

## Verify

```sql
SELECT list_transform([1, 2, 3], lambda x: x + 1) AS lambda,
       TRY(1 // 0) AS safe_divide,
       decimal_division(10.00, 4.00) AS exact;
```

Expect `[2, 3, 4]`, `NULL`, and `2.500000`.

## References

- [Friendly SQL](https://duckdb.org/docs/2.0/sql/dialect/friendly_sql.html) owns clause syntax. Detailed examples are in [references/friendly-sql.md](references/friendly-sql.md).
- [Lambda functions](https://duckdb.org/docs/2.0/sql/functions/lambda.html) owns lambda syntax and function families.
- [CREATE TRIGGER](https://duckdb.org/docs/2.0/sql/statements/create_trigger.html) owns trigger specifications. Support matrices and `RETURNING` rules are in [references/triggers.md](references/triggers.md).
- [Nested schemas](https://duckdb.org/docs/2.0/sql/statements/create_schema.html) owns schema path resolution.
- [FROM and JOIN](https://duckdb.org/docs/2.0/sql/query_syntax/from.html) owns `NEAREST`, `ASOF`, and `POSITIONAL`.
- [WITH](https://duckdb.org/docs/2.0/sql/query_syntax/with.html) owns data-modifying CTE specifications.
- [MERGE INTO](https://duckdb.org/docs/2.0/sql/statements/merge_into.html) and [UPDATE](https://duckdb.org/docs/2.0/sql/statements/update.html) own multi-match rules.
- [PEG parser](https://duckdb.org/docs/2.0/sql/peg_parser.html) and [legacy parser](https://duckdb.org/docs/2.0/core_extensions/legacy_parser.html) own parser fallback settings.
- Friendly-SQL origins trace to the `query` skill in https://github.com/duckdb/duckdb-skills (MIT). Lambda, trigger, schema, division, and multi-match behaviors were verified on DuckDB 2.0.0.
