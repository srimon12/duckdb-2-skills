---
name: duckdb-python
description: >
  Write, optimize, or migrate Python applications using DuckDB 2.0.
  Covers installation, connections, transactions, cursor threading, lazy
  relations, DB-API streaming results, Arrow and Polars zero-copy
  interchange, batch appenders, and 2.0 API migration traps. Use when
  writing or migrating Python code that imports duckdb.
---

# Python client on DuckDB 2.0

DuckDB 2.0 requires Python 3.11 or newer and does not support free-threaded CPython (PEP 703). On Python 3.10 or earlier, `pip install duckdb` installs legacy 1.x releases.

```bash
pip install duckdb==2.0.0
python -c "import duckdb; print(duckdb.__version__)"
```

For database file storage migration, consult `duckdb-migrate`. For SQL syntax and dialect behaviors, see `duckdb-sql`.

## Connect and concurrency

```python
import duckdb

duckdb.sql("SELECT 42").show()          # Module default in-memory database; returns lazy relation
con = duckdb.connect("app.duckdb")      # Persistent database file
con = duckdb.connect("app.duckdb", read_only=True)
con = duckdb.connect(config={"threads": 4, "memory_limit": "2GB"})
```

When issuing queries without an explicit connection handle, `duckdb.sql()` and `duckdb.execute()` operate on a shared module-level in-memory database. For isolated transactions, persistent files, or specific engine configurations, obtain an explicit connection with `duckdb.connect()`.

When dispatching work across threads, never share a single connection handle. The option `check_same_thread` was removed in 2.0 and raises `TypeError`. Allocate an independent cursor to each thread via `con.cursor()`. Each cursor isolates its own transaction state and connection-local settings (such as `search_path`), while sharing database-global configurations. Closing a parent connection terminates all its descendant cursors.

When executing Python user-defined functions inside SQL queries, assign a separate `con.cursor()` to avoid concurrency conflicts.

When connecting to remote Quack sessions, note the cursor exception: cursors share the remote Quack session handle, causing concurrent queries to fail with `superseded by a new query`. For threaded Quack queries, open an independent attached connection per thread (see `duckdb-quack`).

When opening databases read-only, pass `read_only=True` to reject writes; read-only mode never creates a missing file. Within a single process, opening multiple read-write connections to the same file is permitted under MVCC. However, opening a read-only connection alongside existing read-write connections to the same file in one process fails with a configuration error. For cross-process file locking (single writer or multiple readers), see `duckdb-session`.

When configuring extension search paths, pass the plural list `config={"extension_directories": ["/path"]}`; the singular `extension_directory` is deprecated. Because DuckDB ignores `max_temp_directory_size` inside `config` dictionaries, set disk spill limits in SQL after connecting: `SET max_temp_directory_size = '10GB';`.

When creating database files intended for DuckDB 1.5 readers, pin the storage format at connect time:

```python
con = duckdb.connect("app.duckdb", config={"storage_compatibility_version": "v1.5.0"})
```

## Lazy relations vs execution

`con.sql()` and `duckdb.sql()` return lazy relation objects (`DuckDBPyRelation`). Read relations defer execution until an action consumes them; inspecting, printing, or iterating a read relation (including in a notebook) re-executes the query from scratch. Do not print a read relation you only intend to define.

```python
rel = con.sql("SELECT * FROM events")
rel.show()          # Executes query and prints results
rel.show()          # Re-executes the query from scratch

rows = con.execute("SELECT * FROM events").fetchall()   # Computes once and buffers DB-API result
rel.materialize()   # Computes query once and caches rows on the relation
```

When executing DDL or DML statements (`CREATE`, `INSERT`, `UPDATE`, `DELETE`), use `con.execute()`. While `con.sql()` executes DDL/DML immediately upon invocation, it wraps the statement result in a relation; subsequent prints or fetches on that returned relation do not rerun the mutation. Only read relations re-execute.

## Streaming results and transactions

When consuming `con.execute()` results incrementally via `fetchone()` or `fetchmany()`, DuckDB maintains an active streaming result on the connection:

- While an unconsumed streaming result remains open, calling `con.sql()`, `con.query()`, or `appender.flush()` raises `ResourceInUseException`.
- Issuing a new `con.execute()` on the same connection silently cancels and replaces the previous open result.
- Because DuckDB may buffer small result sets entirely in memory, never rely on `ResourceInUseException` as an execution guard.
- To clear an open result before running other queries, consume all remaining rows, call `con.complete()`, call `con.abort()`, or execute concurrent queries in an independent `con.cursor()`.

When any statement fails inside a transaction block (`con.begin()`), DuckDB marks the transaction aborted. Calling `con.commit()` performs an implicit rollback and terminates the block; invoking `con.rollback()` after that aborted `commit()` raises an error. Always initiate a fresh transaction before retrying queries.

## 2.0 API migration reference

Apply the replacement matching the 1.x pattern:

| 1.x pattern | 2.0 replacement and rule |
| --- | --- |
| `con.execute(q).fetch_arrow_table()`, `.arrow()`, `.pl()`, `.fetch_record_batch()` | Removed from DB-API execute results. Use `con.sql(q).to_arrow_table()`, `.to_arrow_reader()`, or `.pl()`. Calling `con.to_arrow_table()` after `execute()` copies rows and issues a deprecation warning. |
| `rel.fetchone()`, `rel.fetchmany(n)`, `rel.fetch_df_chunk()` | Removed from relations. Use `con.execute(q)` for streaming DB-API results, `for row in rel.iter_rows()` for row iteration, or `rel.to_arrow_reader()` for batched records. |
| `rel.execute()` | Removed. Call `rel.materialize()` to evaluate the query and cache resulting rows directly on the relation. |
| `ColumnExpression("s") == "x"` or `rel.update(set={"a": "x"})` | Bare strings evaluate as string literals, not column identifiers. Use `col("x")` for columns and `lit("x")` for values. `rel.update()` rejects bare strings. |
| `ColumnExpression("t.x")` | Use `col("t", "x")`. Column expressions do not parse dots as table qualifiers. |
| `con.values({1: "a"})` | Dictionaries with non-string keys parse as `MAP`. For `STRUCT` types, use string keys. |
| `rel.offset`, `rel.sample`, `rel.drop`, etc., matching column name | Access via dictionary syntax `rel["offset"]`. Relations introduced methods named `offset`, `sample`, `head`, `rename`, `pivot`, `drop`, `unnest`, `unpivot`, `preview`, and `group_by`. |
| `rel.write_csv(..., overwrite=False)` or `write_parquet(..., overwrite=False)` | Raises `IOException` if target destination already exists. Omit `overwrite` to replace existing files. When specifying `partition_by`, only `overwrite=True` permits writing into non-empty directories. |
| `Decimal("1E+2")` | Parsed as `DECIMAL(3,0)` with value `100`, rather than `DECIMAL(3,2)` with value `1.00`. |
| Default Arrow reader batch size | Defaults to 131072 rows. Pass `batch_size` to `to_arrow_reader()` to adjust record batch size. |
| Legacy DuckDB 1.5 file interoperability | DuckDB 2.0 reads 1.x databases, but default 2.0 writes use storage version 69. Set `config={"storage_compatibility_version": "v1.5.0"}` at connect time to maintain 1.5 readability. |

## Arrow, pandas, and Polars

```python
rel.to_arrow_table()                 # Eager PyArrow Table
rel.to_arrow_reader(batch_size=65536) # Streaming Arrow RecordBatchReader
rel.df()                             # Pandas DataFrame
rel.pl()                             # Polars DataFrame
rel.pl(lazy=True)                    # Polars LazyFrame
polars.DataFrame(rel)                # Zero-copy via Arrow PyCapsule interface (no pyarrow required)
```

When converting results to Arrow or Polars, prefer relation methods over `con.to_arrow_table()`, which warns and copies data from DB-API execute buffers.

Querying in-memory PyArrow tables and Polars DataFrames achieves zero-copy execution through Arrow C Data and PyCapsule protocols. Reference Python DataFrame and Table variables directly by name in SQL, or wrap them using connection helpers:

```python
con.sql("SELECT * FROM my_df")
con.from_df(my_df)
con.from_arrow(my_arrow)
con.from_query("SELECT 42 AS x")
```

## Bulk load and appender

To ingest in-memory DataFrames, `INSERT INTO t SELECT * FROM df` provides the highest throughput. For pandas DataFrames, `con.append("t", df)` offers comparable performance.

For high-volume row-by-row or batch ingestion, use `con.appender()`:

```python
con.execute("CREATE TABLE people (id INTEGER PRIMARY KEY, name VARCHAR)")

with con.appender("people") as appender:
    appender.append_row(1, "Ada")
    appender.append_rows([(2, "Grace"), (3, "Edsger")])
```

The appender supports operations via `action="insert"`, `"upsert"`, `"update"`, and `"delete"`:
- When specifying `action="update"` or `"delete"`, pass `key=["col1", ...]`, a list of key column names identifying target rows.
- When specifying `action="upsert"`, DuckDB matches against the target table's primary key or unique constraint. The table must define exactly one conflict target; passing `key` with upsert is rejected.
- To load transformed stream batches, use `con.query_appender(statement, columns, source=...)`. Here `columns` is a list and `source` takes the dict of column names to data types; `statement` reads from the virtual table `appender_data`, and optional `source` queries read from `appender_buffer`.
- Manage appender lifecycles with context managers (`with con.appender(...)`). A `with` block automatically calls `flush()` upon clean exit and calls `clear()` to discard uncommitted rows if an exception occurs. Outside a context manager, explicitly call `appender.flush()` to commit rows, or `appender.clear()` to discard buffered rows. The appender has no `close()` method.
- Never share an appender instance across threads. Ensure open streaming `con.execute()` results are finished before calling `flush()`.

## Other Python entry points

When using the ADBC Python driver (`adbc_driver_duckdb`), the DBAPI connection does not auto-commit transactions. Writes issued through `cur.adbc_ingest()` are discarded on connection close unless explicitly committed:

```python
import pyarrow as pa
from adbc_driver_duckdb import dbapi

con = dbapi.connect("app.duckdb")
with con.cursor() as cur:
    cur.adbc_ingest("events", pa.table({"id": [1, 2]}))
con.commit()
```

When integrating with Ibis, note that Ibis versions 12.0.0 and earlier pin `duckdb<2`. Pin `duckdb<2` in dependencies until upstream Ibis releases DuckDB 2.0 compatibility.

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

Run the verification script in a Python environment containing `duckdb==2.0.0` and `pyarrow`.

## References

- [Python client migration](https://duckdb.org/docs/2.0/clients/python/migration.html) documents 2.0 breaking changes and API removals.
- [Python client overview](https://duckdb.org/docs/2.0/clients/python/overview.html) details installation, connection types, and configuration.
- [Python DB-API](https://duckdb.org/docs/2.0/clients/python/dbapi.html) specifies cursor semantics, result sets, and thread safety.
- [Relational API](https://duckdb.org/docs/2.0/clients/python/relational_api.html) defines lazy relation lifecycle, evaluation, and dataframe methods.
- [Python expressions](https://duckdb.org/docs/2.0/clients/python/expression.html) covers column expressions, literals, and relational filters.
- [Python appender](https://duckdb.org/docs/2.0/clients/python/appender.html) details batch loading, actions, conflict handling, and query appenders.
- [ADBC driver](https://duckdb.org/docs/2.0/clients/adbc.html) documents the DuckDB ADBC interface and transaction commit rules.
- [Ibis integration](https://duckdb.org/docs/2.0/guides/python/ibis.html) tracks framework compatibility and driver versions.
- [Migration guide](https://duckdb.org/docs/2.0/operations_manual/migration.html) details storage version compatibility across releases.
- API changes, streaming locks, and cursor concurrency were validated against `duckdb==2.0.0` on Python 3.14.3.
