---
name: duckdb-python
description: >
  Change Python code that used DuckDB 1.x so it runs on duckdb 2.0. Relations,
  Arrow and Polars fetches, expressions, threads, and transactions. Use when
  the user edits Python that imports duckdb, or runs /duckdb-python.
---

# Python client on DuckDB 2.0

DuckDB 2.0 requires Python 3.11 or newer. Free-threaded CPython is not supported. On Python 3.10, `pip install duckdb` installs a 1.x release. Storage-format rules for the file on disk are in `duckdb-migrate`.

Apply the rows that match the code you are editing. Each line is the 2.0 behavior from the Python migration page.

| 1.x code | 2.0 code |
| --- | --- |
| `con.execute(q).fetch_arrow_table()`, `.arrow()`, `.pl()`, `.fetch_record_batch()` | `con.sql(q).to_arrow_table()`, `.to_arrow_reader()`, or `.pl()`. `to_arrow_table()` on an `execute()` result copies and warns. |
| `rel.fetchone()`, `rel.fetchmany(n)`, `rel.fetch_df_chunk()` | Gone. A relation reruns on every read. Use `con.execute(q)` to hold a result, or `for row in rel.iter_rows()`. Stream with `rel.to_arrow_reader()`. |
| `rel.execute()` | `rel.materialize()` when the rows must be computed and kept. |
| `ColumnExpression("s") == "x"` and `rel.update(set={"a": "x"})` | A bare string is a value. Use `col("x")` for a column and `lit("x")` for text. `update()` rejects a bare string. |
| `ColumnExpression("t.x")` | `col("t", "x")`. A dot is not a separator. |
| `con.values({1: "a"})` | A dict with non-string keys becomes a `MAP`. Use string keys for a `STRUCT`. |
| `rel.offset` when `offset` is a column | `rel["offset"]`. Relations gained methods named `offset`, `sample`, `head`, `rename`, `pivot`, `drop`, `unnest`, `unpivot`, `preview`, and `group_by`. |
| `con.sql("CREATE TABLE ...")` | Returns a relation, and printing it runs the query again. Use `con.execute()` for DDL and DML. |
| Another query while `execute()` rows are unread | `ResourceInUseException` until the result is consumed or you call `con.complete()` or `con.abort()`. The next `execute()` replaces the open result. |
| Several threads calling one connection | `ResourceInUseException`. Give each thread `con.cursor()`. |
| A failed `execute()` inside `con.begin()` | Aborts the transaction. `commit()` rolls back. Call `rollback()` before more SQL. |
| `rel.write_csv(path, overwrite=False)` and `write_parquet(..., overwrite=False)` | Raise if the file exists. Omit `overwrite` to replace the file. |
| `Decimal("1E+2")` | `100` as `DECIMAL(3,0)`, not `1.00` as `DECIMAL(3,2)`. |
| Arrow batches of 1,000,000 rows | Default batch size is 131072. Pass `batch_size`. |
| A file written for DuckDB 1.5 | 2.0 can open it. A file 2.0 writes in the default format cannot be opened by 1.5. Pin it with `duckdb.connect(path, config={"storage_compatibility_version": "v1.5.0"})`. |

A relation runs its query on every read, including a print in a notebook. Do not print a relation you only meant to define.

## References

- https://duckdb.org/docs/2.0/clients/python/migration.html
- https://duckdb.org/docs/2.0/clients/python/overview.html
- https://duckdb.org/docs/2.0/clients/python/expression.html
- https://duckdb.org/docs/2.0/clients/python/relational_api.html
- https://duckdb.org/docs/2.0/clients/python/dbapi.html
- https://duckdb.org/docs/2.0/operations_manual/migration.html
