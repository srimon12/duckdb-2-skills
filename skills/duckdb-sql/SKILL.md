---
name: duckdb-sql
description: >
  Write and run DuckDB 2.0 SQL. Friendly SQL, Python-style lambdas, triggers,
  nested schemas, integer division by zero, and result size. Use when the user
  asks for a query, a trigger, a lambda, GROUP BY ALL, PIVOT, MERGE, or
  /duckdb-sql.
---

# Write DuckDB 2.0 SQL

Run statements with the `duckdb` skill. If it is not loaded, require `duckdb --version` to contain `v2.0`, use `duckdb -agent` for tables a model will read, and `duckdb -json` for rows you will parse.

If a session file from `duckdb-session` exists, pass `-init` with that file. Otherwise query files directly or use `:memory:`.

## Before a large query

Look at columns with `DESCRIBE`, which does not run the query. Profile a table with `SUMMARIZE`. If the source can return a huge row set and the statement has no `LIMIT` and no aggregate, add `LIMIT 100` for a first look and say that you did.

## Lambdas

The single-arrow form is disabled.

```sql
SELECT list_transform([1, 2, 3], lambda x: x + 1);
```

`SET lambda_syntax = 'enable_single_arrow'` turns the old `x -> x + 1` form back on for the session. DuckDB 2.1 removes that setting. Write the `lambda` form in anything you save.

## Integer division

`1 // 0` and `1 % 0` raise. `1 / 0` still returns `inf`.

```sql
SELECT TRY(1 // 0);  -- NULL for this expression
```

`SET error_on_division_by_zero = false` makes every integer division by zero return `NULL`.

## Nested schemas

```sql
CREATE SCHEMA sales;
CREATE SCHEMA sales.europe;
CREATE TABLE sales.europe.orders (id INTEGER);
SELECT * FROM sales.europe.orders;
```

`USE sales.europe` fails. Nested schemas cannot sit on the search path. Qualify the name. A quoted identifier `"sales.europe"` is one schema whose name contains a dot, not a nested path.

## Triggers

A trigger body is one SQL statement. Several triggers on the same event run in creation order.

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

Row-level insert:

```sql
CREATE TRIGGER trg_log
    AFTER INSERT ON t
    FOR EACH ROW
        INSERT INTO log VALUES (NEW.id);
```

`UPDATE OF price` limits an update trigger to those columns. `NEW` exists for `INSERT`. `OLD` exists for `DELETE`. `NEW TABLE` exists for `INSERT` and `UPDATE`. `OLD TABLE` exists for `UPDATE` and `DELETE`.

```sql
DROP TRIGGER IF EXISTS trg_audit ON target;
SELECT trigger_name, table_name, action_timing, event_manipulation, for_each
FROM duckdb_triggers();
```

Unsupported in 2.0: `BEFORE ... FOR EACH ROW`, `UPDATE ... FOR EACH ROW`, `RETURNING` on a table that has a `FOR EACH ROW` trigger, `INSTEAD OF`, triggers on views, temporary triggers. `RETURNING` is allowed on a table whose triggers are `FOR EACH STATEMENT`.

## Friendly SQL worth using

These are normal DuckDB, still valid on 2.0:

- `FROM t WHERE x > 10` selects every column.
- `GROUP BY ALL`, `ORDER BY ALL`.
- `SELECT * EXCLUDE (a, b)` and `SELECT * REPLACE (expr AS a)`. `EXCEPT` is a synonym of `EXCLUDE`.
- `count()` with an empty argument list. `count() FILTER (WHERE x > 10)`.
- `UNION ALL BY NAME`.
- `INSERT INTO t BY NAME SELECT ...`.
- `CREATE OR REPLACE TABLE`.
- `PIVOT` and `UNPIVOT`.
- `DESCRIBE` and `SUMMARIZE`.
- List comprehensions `[x * 2 FOR x IN col]`, list slices `col[1:3]`, struct expansion `s.*`.
- `COLUMNS(*)` to apply an expression across columns.
- `ASOF` and `POSITIONAL` joins.

Session variables:

```sql
SET VARIABLE x = 7;
SELECT $x;
```

`getvariable('x')` still works. Write `$x` in new SQL.

2.0 syntax to look up before inventing a statement: `NEAREST` joins, data-modifying CTEs, `FETCH FIRST`, backtick-quoted identifiers, and `EXPLAIN (SQL)`. Pages are listed below. Nested schemas and triggers are specified in this skill.

## Parser

The PEG parser is the default. A query that parsed on 1.x should still parse, and errors include a source location. If a known-good query fails to parse:

```sql
INSTALL AND LOAD legacy_parser;
SET enable_legacy_parser = true;
```

File the query if you need the fallback. Do not leave `legacy_parser` in a script you generate for someone else unless they asked.

## References

- https://duckdb.org/docs/2.0/sql/statements/set_variable.html
- https://duckdb.org/docs/2.0/sql/functions/lambda.html
- https://duckdb.org/docs/2.0/sql/statements/create_trigger.html
- https://duckdb.org/docs/2.0/sql/statements/create_schema.html
- https://duckdb.org/docs/2.0/sql/peg_parser.html
- https://duckdb.org/docs/2.0/operations_manual/migration.html
- https://duckdb.org/docs/2.0/whats_new_in_the_docs.html
- Friendly-SQL examples in the older `query` skill of https://github.com/duckdb/duckdb-skills (MIT) were the starting list. The lambda rule, trigger limits, nested-schema `USE` error, and `//` error were checked on DuckDB 2.0.0.
