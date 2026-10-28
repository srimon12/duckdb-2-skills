# Query and file diagnostics

Superseded in part by `12-diagnostics-engine.md`. Slice 12 owns the 2.0.0 JSON shapes, profile metrics, text layout, and plan-linter semantics. This slice keeps the original pushdown, join, metadata, and UI evidence.

Sources: the 2.0 snapshots for [profiling](https://duckdb.org/docs/2.0/dev/profiling.html), [EXPLAIN](https://duckdb.org/docs/2.0/guides/meta/explain.html), [EXPLAIN ANALYZE](https://duckdb.org/docs/2.0/guides/meta/explain_analyze.html), [tuning workloads](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html), [Parquet metadata](https://duckdb.org/docs/2.0/data/parquet/metadata.html), and [UI](https://duckdb.org/docs/2.0/core_extensions/ui.html). Probes ran on DuckDB 2.0.0 `d54cbbe3df` on macOS arm64.

## Plan facts

`EXPLAIN` prints the physical plan with estimated cardinality and does not execute. `EXPLAIN ANALYZE` executes, including writes, and adds actual rows and cumulative operator times.

```text
$ duckdb -no-agent -c "CREATE TABLE t AS SELECT range AS id FROM range(100000); EXPLAIN SELECT count(*) FROM t WHERE id < 10;"
Seq Scan
Filters: id < 10
~20,000 rows
```

The estimate is 20,000. The actual is 10.

```text
$ duckdb -no-agent -c "CREATE TABLE t AS SELECT range AS id FROM range(100000); EXPLAIN ANALYZE SELECT count(*) FROM t WHERE id < 10;"
╭─ Summary ───────────╮
│ Total Time: 0.0027s │
╰─────────────────────╯
╭─ Table Scan ────────╮
│ Filters: id < 10    │
│ 10 rows         0µs │
╰─────────────────────╯
```

The text layout is boxed in 2.0.0; parse JSON for timings because text rounds to `0µs`.

`EXPLAIN ANALYZE` also executes DML.

```text
$ EXPLAIN ANALYZE INSERT INTO t SELECT range FROM range(3);
$ SELECT count(*) FROM t;
3
```

That is why the skill says use plain `EXPLAIN` on a write unless the write is intended. `EXPLAIN ANALYZE` ignores `-json`; `EXPLAIN (FORMAT JSON)` is the JSON path. The JSON tree is `name`, `children`, `extra_info`, not the CLI's row format.

## Pushdown facts

A selective filter on a sorted Parquet file prunes row groups.

```text
COPY (SELECT range AS id FROM range(100000) ORDER BY id)
TO 'sorted.parquet' (FORMAT parquet, ROW_GROUP_SIZE 10000);

EXPLAIN ANALYZE SELECT count(*) FROM 'sorted.parquet' WHERE id = 99999;
Row Groups Scanned: 1 / 10
```

A filter that wraps the column scans all row groups.

```text
WHERE CAST(d AS VARCHAR) LIKE '2024-01%'
Row Groups Scanned: 5 / 5
```

The fix is a range on the bare column. `WHERE d >= DATE '2024-01-01' AND d < DATE '2024-02-01'` prunes. The same rule applies to Hive partitions. A filter on `year = 2024` prunes directories; `year(ordered_at) = 2024` does not.

`EXPLAIN ANALYZE` on a Parquet scan also prints `Total Files Read`, `Filename(s)`, `Row Groups Scanned`, and a `Data Read` byte count. Those four fields are the fastest way to see whether a glob opened too much.

## Join facts

A missing join predicate produces `Cross Product`. An equality join produces `Hash Join`. An inequality can produce `Piecewise Merge Join`.

```text
SELECT * FROM a, b;                 -- Cross Product
SELECT * FROM a JOIN b ON a.i=b.i;  -- Hash Join
SELECT * FROM a JOIN b ON a.i<b.i;  -- Piecewise Merge Join
```

The bad pattern is a join whose output is much larger than either input. A `LIMIT` after the join does not reduce the join work. Pre-aggregate, filter, or change the key.

## Metadata facts

`parquet_file_metadata` has one row per file. `parquet_metadata` has one row per column chunk. A 10-row, 3-column file reports `num_rows=10` at the file level and `sum(row_group_num_rows)=30` at the chunk level.

Schema drift on a glob fails by default.

```text
Invalid Input Error: Failed to read file "b.parquet": schema mismatch in glob
```

`read_parquet(..., union_by_name = true)` fills missing columns with `NULL`. That is a read repair, not a producer fix.

## UI facts

`duckdb -ui` exists in `-help` and installs the `ui` extension from `core` on first run. The extension is built and published separately from DuckDB. On the 2.0.0 release, `core` returned 404 until `00:35:22Z` on 2026-10-22, while `core_nightly` had the same binary from `20:12:50Z`. `duckdb -ui` reads `core`, so it failed during that window. The 2.0.0 `ui` build has no binary for `osx_amd64` or `windows_arm64`.

`EXPLAIN (FORMAT WEB)` still works. It writes a temporary HTML file and opens it. `EXPLAIN ANALYZE (FORMAT WEB)` adds actuals.

The UI page is served by an embedded HTTP server that fetches the page assets from `https://ui.duckdb.org`. Queries run in the local process. The page is remote. That distinction is the privacy caveat.

## Skill boundary

| Fact | Owner |
| --- | --- |
| `EXPLAIN` and `EXPLAIN ANALYZE` as statements | `duckdb-sql` keeps `EXPLAIN (SQL)` in its syntax table. |
| Plan interpretation, pushdown, joins, spill, layout | `duckdb-profile` |
| `EXPLAIN ANALYZE` and `-json` interaction | `duckdb` |
| Metadata function signatures and the row-count trap | `duckdb-files` |
| Reader options and schema drift mechanics | `duckdb-files` |
| UI flag, port, read-only limit, install caveat | `duckdb` |

The profile skill links the owners instead of restating them.
