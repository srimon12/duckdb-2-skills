---
name: duckdb-python
description: >
  Write or migrate Python code that uses duckdb 2.0. Covers installation,
  connections, lazy relations, DB-API results, Arrow and pandas output,
  threads, transactions, and the appender. Use when the user edits Python
  that imports duckdb.
---

# Python client on DuckDB 2.0

DuckDB 2.0 requires Python 3.11 or newer. Free-threaded CPython is not supported. On Python 3.10, `pip install duckdb` installs a 1.x release.

```bash
pip install duckdb==2.0.0
python -c "import duckdb; print(duckdb.__version__)"
```

For file storage-format rules, see `duckdb-migrate`. For SQL syntax, see `duckdb-sql`.

## Connect

```python
import duckdb

duckdb.sql("SELECT 42").show()          # global in-memory database, returns a relation
con = duckdb.connect("app.duckdb")      # a file
con = duckdb.connect("app.duckdb", read_only=True)
con = duckdb.connect(config={"threads": 4, "memory_limit": "2GB"})
```

`check_same_thread` is not a 2.0 option; it raises `TypeError`. Give each thread its own `con.cursor()`. A cursor has its own transaction and connection-local settings such as `search_path`; some settings are database-global. Closing a connection closes all its cursors. `read_only=True` rejects writes and will not create a missing file. `config={"extension_directories": ["/path"]}` works. The singular `extension_directory` is deprecated but still effective; prefer the plural list. Because `max_temp_directory_size` in `config` is ignored for enforcement, set it with `SET` after connecting.

`duckdb.sql()` and `duckdb.execute()` use a module-level default connection. `duckdb.connect()` returns an explicit connection. Two read-write connections to one file in one process are legal under MVCC; a read-only connection alongside them fails with a different-configuration error. Use one connection plus cursors unless independent transactions are needed. See `duckdb-session` for the file-lock model. When running Python functions inside SQL queries, use a separate `con.cursor()`.

## Connection and result lifecycle

| Step | Rule |
| --- | --- |
| Scope | `duckdb.sql()` uses the module default. `duckdb.connect()` returns an explicit connection. Pick one and pass it. |
| Read vs write | `read_only=True` rejects writes and does not create a missing file. Do not open a read-only connection in a process that already has the same file read-write. |
| Concurrency | One connection plus `con.cursor()` per thread. Two read-write connections in one process are legal under MVCC. Cross-process is one writer or many readers. |
| Relation vs execute | `con.sql` is lazy for reads and runs once for DDL/DML. `con.execute` runs now and holds a result. `materialize()` if a read relation is reused. |
| Finish a result | Fetch to the end, `complete()`, or `abort()` before `con.sql`, `con.query`, or an appender `flush()`. A new `execute()` replaces an open result silently. |
| Transaction | A failed statement aborts the transaction. `commit()` rolls back; `rollback()` after that commit errors. Start a new transaction before retrying. |
| Appender | `flush()` on success, `clear()` to discard. No `close()`. `key` is for update and delete only; upsert uses the PK or unique constraint. |

To keep a file readable by DuckDB 1.5:

```python
con = duckdb.connect("app.duckdb", config={"storage_compatibility_version": "v1.5.0"})
```

## Relations are lazy

`con.sql()` and `duckdb.sql()` return a relation. A read runs the query again, including a print in a notebook. Do not print a relation you only meant to define.

```python
rel = con.sql("SELECT * FROM events")
rel.show()          # runs the query
rel.show()          # runs it again

rows = con.execute("SELECT * FROM events").fetchall()   # compute once
rel.materialize()   # compute and keep the rows on the relation
```

For DDL and DML, use `con.execute()`. `con.sql("CREATE TABLE ...")` and `con.sql("INSERT ...")` run once at the call and return a relation over the statement result. Printing or fetching that relation does not run the statement again. Only read relations rerun.

## The 2.0 API changes

Apply the row that matches the code you are editing.

| 1.x code | 2.0 code |
| --- | --- |
| `con.execute(q).fetch_arrow_table()`, `.arrow()`, `.pl()`, `.fetch_record_batch()` | These methods are gone from the execute result. Use `con.sql(q).to_arrow_table()`, `.to_arrow_reader()`, or `.pl()`. `con.to_arrow_table()` after `execute()` copies and warns. Relations keep `fetch_arrow_table`, `arrow`, and `fetch_record_batch` as deprecated aliases. |
| `rel.fetchone()`, `rel.fetchmany(n)`, `rel.fetch_df_chunk()` | Gone on a relation. `con.execute()` results still have them. Use `con.execute(q)` for a held result, `for row in rel.iter_rows()`, or `rel.to_arrow_reader()`. |
| `rel.execute()` | When the rows must be computed and kept, use `rel.materialize()`. |
| `ColumnExpression("s") == "x"` and `rel.update(set={"a": "x"})` | A bare string is a value. Use `col("x")` for a column and `lit("x")` for text. `update()` rejects a bare string. |
| `ColumnExpression("t.x")` | `col("t", "x")`. A dot is not a separator. |
| `con.values({1: "a"})` | A dict with non-string keys becomes a `MAP`. For a `STRUCT`, use string keys. |
| `rel.offset` when `offset` is a column | `rel["offset"]`. Relations gained methods named `offset`, `sample`, `head`, `rename`, `pivot`, `drop`, `unnest`, `unpivot`, `preview`, and `group_by`. |
| `con.sql("CREATE TABLE ...")` | Runs once at the call. Printing the returned relation does not run the DDL or DML again. When you do not want a relation, use `con.execute()`. Only a read relation reruns. |
| Another query while a streaming `execute()` result is unread | `sql` and `query` raise `ResourceInUseException` until the result is consumed or ended with `con.complete()` or `con.abort()`. A new `execute()` replaces the open result silently. Small results may be buffered. |
| Several threads calling one connection | `ResourceInUseException`. Give each thread `con.cursor()`. |
| A failed `execute()` inside `con.begin()` | Aborts the transaction. `commit()` rolls back and closes it. Call `rollback()` before more SQL, or accept `commit()` as the rollback; a `rollback()` after that `commit()` errors. |
| `rel.write_csv(path, overwrite=False)` and `write_parquet(..., overwrite=False)` | Raise `IOException` if the file exists. Omit `overwrite` to replace the file. With `partition_by`, only `overwrite=True` writes into a non-empty directory. |
| `Decimal("1E+2")` | `100` as `DECIMAL(3,0)`, not `1.00` as `DECIMAL(3,2)`. |
| Arrow batches of 1,000,000 rows | Default batch size is 131072. Pass `batch_size`. |
| A file written for DuckDB 1.5 | 2.0 can open it. A file 2.0 writes in the default format cannot be opened by 1.5. Pin it with `storage_compatibility_version`. |

When rows remain unread after `con.execute().fetchone()`, a streaming result makes `con.sql()`, `con.query()`, or an appender `flush()` raise `ResourceInUseException`. A new `con.execute()` replaces the open result silently. Small results may be buffered, so do not rely on the exception as a guard. To clear an open result, consume all rows, call `con.complete()`, call `con.abort()`, or use a separate cursor.

## Arrow, pandas, and Polars

```python
rel.to_arrow_table()                 # eager Arrow table
rel.to_arrow_reader(batch_size=65536)
rel.df()                             # pandas DataFrame
rel.pl()                             # Polars DataFrame
rel.pl(lazy=True)                    # Polars LazyFrame
polars.DataFrame(rel)                # zero-copy Arrow PyCapsule, no pyarrow needed
```

`con.to_arrow_table()` after `execute()` warns because it copies rows. Prefer a relation. Querying Arrow tables and Polars frames is zero-copy through Arrow C Data and PyCapsule interfaces. To query a DataFrame or Arrow table, name it in SQL or use the helpers:

```python
con.sql("SELECT * FROM my_df")
con.from_df(my_df)
con.from_arrow(my_arrow)
con.from_query("SELECT 42 AS x")
```

## Bulk load

For a DataFrame, `INSERT INTO t SELECT * FROM df` is the fastest path. For pandas, `con.append("t", df)` is also fast.

```python
con.execute("CREATE TABLE people (id INTEGER PRIMARY KEY, name VARCHAR)")

with con.appender("people") as appender:
    appender.append_row(1, "Ada")
    appender.append_rows([(2, "Grace"), (3, "Edsger")])
```

The appender supports `action="insert"`, `"upsert"`, `"update"`, and `"delete"`. `update` and `delete` take `key`, a list of key columns. `upsert` uses the table's primary key or unique constraint and rejects `key`. `columns` is a list, and `con.query_appender(statement, columns, source=...)` takes a dict of column names to types. The statement reads `appender_data`; the optional source query reads `appender_buffer`. The appender has no `close()` method; call `clear()` to discard buffered rows. Do not share an appender across threads. Finish open `execute()` results before calling `flush()`. A `with` block flushes on success and discards buffered rows on an exception. Outside a `with` block, call `flush()`.

## Verify

```python
import duckdb
assert duckdb.__version__.startswith("2.")
con = duckdb.connect()
con.execute("CREATE TABLE t AS SELECT 42 AS a")
assert con.execute("SELECT a FROM t").fetchall() == [(42,)]
assert con.sql("SELECT a FROM t").to_arrow_table().num_rows == 1
print("ok")
```

Run it in a venv with `duckdb==2.0.0` and `pyarrow` for the Arrow line.

## References

- https://duckdb.org/docs/2.0/clients/python/migration.html
- https://duckdb.org/docs/2.0/clients/python/overview.html
- https://duckdb.org/docs/2.0/clients/python/dbapi.html
- https://duckdb.org/docs/2.0/clients/python/relational_api.html
- https://duckdb.org/docs/2.0/clients/python/expression.html
- https://duckdb.org/docs/2.0/clients/python/appender.html
- https://duckdb.org/docs/2.0/operations_manual/migration.html
- The API changes and the open-result behavior were run against `duckdb==2.0.0` on Python 3.14.3.
