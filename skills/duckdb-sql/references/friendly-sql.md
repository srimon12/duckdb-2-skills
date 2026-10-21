# Friendly SQL reference

Read this when the skill needs an example or an edge case for a friendly-SQL clause. The driver is `duckdb-sql/SKILL.md`.

## FROM first

```sql
FROM events
WHERE kind = 'click'
SELECT user_id, count(*) AS clicks
GROUP BY ALL
ORDER BY clicks DESC;
```

The `SELECT` list is optional when every column is wanted.

## GROUP BY ALL and ORDER BY ALL

```sql
SELECT region, product, sum(amount)
FROM sales
GROUP BY ALL;
```

`GROUP BY ALL` groups by every non-aggregate select expression. `ORDER BY ALL` orders by every output column, left to right. Both are convenient in exploration and fragile in saved SQL, because a new column changes the grouping or sort. Write the columns explicitly when the query is part of a pipeline.

## Star expressions

```sql
SELECT * EXCLUDE (internal_id, created_at) FROM events;
SELECT * EXCEPT (internal_id) FROM events;       -- same as EXCLUDE in a star
SELECT * REPLACE (amount / 100 AS amount) FROM sales;
SELECT COLUMNS('^metric_') FROM readings;
```

`EXCEPT` is a set operator outside a star expression. Do not confuse the two.

## count and FILTER

```sql
SELECT count() AS rows,
       count() FILTER (WHERE kind = 'click') AS clicks,
       count(DISTINCT user_id) AS users
FROM events;
```

`count()` is `count(*)`. `FILTER` works on any aggregate.

## Set operations by name

```sql
SELECT 1 AS a, 2 AS b
UNION ALL BY NAME
SELECT 3 AS b, 4 AS c;
```

Result: `a, b, c` with `1, 2, NULL` and `NULL, 3, 4`. Missing columns become `NULL`, and types are combined. `UNION BY NAME` is the distinct form.

## INSERT BY NAME

```sql
INSERT INTO target BY NAME SELECT 7 AS b, 8 AS a;
```

Source columns are matched by name. Omitted target columns take their default, or `NULL`. An unknown source column is a binder error.

## CREATE OR REPLACE TABLE

`CREATE OR REPLACE TABLE` recreates the table. Primary keys, constraints, and explicit indexes on the old table are gone without a warning. Use `CREATE TABLE IF NOT EXISTS` plus `INSERT` or `MERGE` when the table has invariants.

## PIVOT and UNPIVOT

```sql
PIVOT sales ON quarter USING sum(amount) GROUP BY year;
UNPIVOT sales ON q1, q2 INTO NAME quarter VALUE amount;
```

`PIVOT ... FILTER` is accepted and silently ignored. Compute the filtered aggregate in a CTE first. The simplified `UNPIVOT` drops rows whose value is `NULL`; only the SQL-standard `FROM ... UNPIVOT (... INCLUDE NULLS)` form keeps them.

## DESCRIBE and SUMMARIZE

`DESCRIBE SELECT ...` returns the result schema and does not run the query. `SUMMARIZE table` runs the query and returns `column_name`, `column_type`, `min`, `max`, `approx_unique`, `avg`, `std`, `q25`, `q50`, `q75`, `count`, and `null_percentage`.

## Lists and structs

```sql
SELECT [x * 2 FOR x IN [1, 2, 3]] AS doubled;   -- [2, 4, 6]
SELECT [10, 20, 30, 40][2:3] AS slice;          -- [20, 30], 1-based
SELECT [10, 20, 30][-1] AS last;                -- 30
SELECT {'x': 1, 'y': 2}.*;                      -- two columns
SELECT [1, 2] || [3] AS appended;
```

Indexes are 1-based, including slices. JSON arrays are the 0-based exception. `list_transform`, `list_filter`, and `list_reduce` accept `lambda x: ...`, and the optional last parameter is the 1-based index.

## COLUMNS

```sql
SELECT COLUMNS(*) + 1 FROM (SELECT 1 AS a, 2 AS b);
SELECT COLUMNS('^metric_') FROM readings;
SELECT COLUMNS(lambda c: c NOT IN ('id', 'created_at')) FROM events;
SELECT UNPACK(COLUMNS('^flag_')) FROM flags;
```

`COLUMNS(...)` applies an expression across columns. `UNPACK` expands the list into a variadic call. `COLUMNS(lambda c, i: ...)` receives the column name and its 1-based position.

## Joins

ASOF needs equality keys plus one inequality on the ordering column:

```sql
SELECT t.*, p.price
FROM trades t
ASOF JOIN prices p
  ON t.symbol = p.symbol AND t.when >= p.when;
```

POSITIONAL matches by row number and fills the short side with `NULL`:

```sql
SELECT * FROM a POSITIONAL JOIN b;
```

NEAREST matches the top-k right rows by a distance or similarity:

```sql
SELECT q.id, p.id
FROM queries q
INNER JOIN products p
  NEAREST 2 BY SIMILARITY array_cosine_similarity(q.embedding, p.embedding);

SELECT q.id, p.id
FROM queries q
LEFT JOIN products p
  NEAREST 1 BY DISTANCE array_distance(q.embedding, p.embedding);
```

`k` must be a positive integer literal. `APPROX` goes before `NEAREST`. The distance functions accept fixed-size arrays such as `DOUBLE[768]` or `FLOAT[768]`, not variable-length `DOUBLE[]`. Cast the embedding columns to the model dimension.

## Variables and prepared statements

```sql
SET VARIABLE region = 'eu';
SELECT * FROM sales WHERE region = $region;

SET VARIABLE "my var" = 9;
SELECT $"my var";

PREPARE p AS SELECT $region;
EXECUTE p(region := 'us');
```

`$undefined` raises. `getvariable('undefined')` returns `NULL`. A named prepared parameter falls back to a session variable of the same name.

## FETCH FIRST and LIMIT

```sql
SELECT * FROM range(10) FETCH FIRST 3 ROWS ONLY;
SELECT * FROM range(10) OFFSET 2 ROWS FETCH NEXT 3 ROWS ONLY;
SELECT * FROM range(1000) LIMIT 10%;
```

`FETCH FIRST ... PERCENT` and `FETCH FIRST ... WITH TIES` are parser errors. `LIMIT 10%` floors: 9 rows give 0, 10 give 1, 1000 give 100.

## query and query_table

```sql
SELECT * FROM query('SELECT 42 AS answer');
SELECT * FROM query_table('events');
```

The argument must be a literal or a prepared string. A column reference is rejected.

## Sequences and regex

```sql
CREATE SEQUENCE s START 1;
SELECT setval('s', 42);        -- next nextval is 43
SELECT setval('s', 42, false); -- next nextval is 42

SELECT regexp_extract('2023-04-15', '(\d{4})-(\d{2})-(\d{2})', ['y', 'm', 'd']);
SELECT regexp_extract('ABC', 'abc', 'i');
```

`regexp_extract` with a name list returns a `STRUCT` of named groups. No match returns empty strings, not `NULL`. The `'i'` option is case-insensitive.

## Window functions and QUALIFY

```sql
SELECT * FROM events QUALIFY row_number() OVER (PARTITION BY user_id ORDER BY ts DESC) = 1;
```

`QUALIFY` filters after window evaluation. The default frame for `sum(x) OVER (ORDER BY x)` is `RANGE UNBOUNDED PRECEDING TO CURRENT ROW`, so tied `x` values share a cumulative value. Use `ROWS BETWEEN ...` for a row-by-row running total.

## DISTINCT ON

```sql
SELECT DISTINCT ON (user_id) user_id, ts, event
FROM events
ORDER BY user_id, ts DESC;
```

Without an `ORDER BY` that starts with the `DISTINCT ON` keys, the chosen row is arbitrary.

## Types worth knowing

| Type | Fact |
| --- | --- |
| `VARIANT` | Typed binary, keys sorted; see `duckdb-variant` |
| `UNION` | Tagged union; `union_value(tag := expr)`, `union_tag` |
| `MAP` | `m['missing']` returns `NULL`; `map_extract(m, 'missing')` returns `[]` |
| `ARRAY` | Fixed length, 1-based |
| `LIST` | Variable length, 1-based |
| `ENUM` | Compares in declaration order |
| `DECIMAL` | Bare literal is `DECIMAL(18,3)`; division returns `DOUBLE` |
| `TUPLE` | `(1, 'a')` is a tuple, not a named struct |
| `STRUCT` | Bare `STRUCT` is an empty struct; `STRUCT()` is an error |

## References

- https://duckdb.org/docs/2.0/sql/dialect/friendly_sql.html
- https://duckdb.org/docs/2.0/sql/query_syntax/from.html
- https://duckdb.org/docs/2.0/sql/query_syntax/groupby.html
- https://duckdb.org/docs/2.0/sql/query_syntax/orderby.html
- https://duckdb.org/docs/2.0/sql/expressions/star.html
- https://duckdb.org/docs/2.0/sql/statements/pivot.html
- https://duckdb.org/docs/2.0/sql/statements/unpivot.html
- https://duckdb.org/docs/2.0/sql/query_syntax/with.html
- https://duckdb.org/docs/2.0/sql/query_syntax/limit.html
- https://duckdb.org/docs/2.0/sql/statements/create_sequence.html
- https://duckdb.org/docs/2.0/sql/functions/regular_expressions.html
