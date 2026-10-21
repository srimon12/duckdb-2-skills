---
name: duckdb-profile
description: >
  Diagnose slow DuckDB 2.0 queries and unhealthy Parquet layouts. Use EXPLAIN
  and EXPLAIN ANALYZE to compare estimates with actual rows, spot missing
  pushdown, exploding joins, and spill, and check Parquet row groups and schema
  drift. Use when a query is slow, scans too much, runs out of memory, or a
  Parquet dataset needs a health check.
---

# Query and file diagnostics

Run commands with `duckdb`. If `duckdb-session` created a state file, pass `-init`. Read `duckdb-sql` for query syntax and `duckdb-files` for reader, writer, and metadata options. This skill owns the diagnosis.

## Start with the symptom

| Symptom | First move |
| --- | --- |
| A query is slow and returns the right rows. | `EXPLAIN`, then `EXPLAIN ANALYZE` if the plan is not obvious. |
| `EXPLAIN ANALYZE` shows one operator with far more rows than its estimate. | Check join order and filter placement. |
| Out of Memory Error. | Check `memory_limit`, `temp_directory`, blocking operators, and `preserve_insertion_order`. |
| A Parquet filter scans every row group. | Check the filter expression, row-group statistics, and sort order. |
| A file changed and columns are missing or renamed. | Use `duckdb-files` schema drift first. |
| A query returns a wrong value with no error. | Use `duckdb-sql` result traps first. |

A wrong answer is not a profiling problem until the plan or the file layout explains it.

## Plan first

`EXPLAIN` shows the physical plan and estimated rows. It does not run the query.

```sql
EXPLAIN
SELECT customer_id, sum(amount)
FROM orders
WHERE ordered_at >= DATE '2024-01-01'
GROUP BY customer_id;
```

`EXPLAIN ANALYZE` runs the query and adds actual rows and timings. It also runs writes. Never add `ANALYZE` to `INSERT`, `UPDATE`, `DELETE`, or `COPY` unless you intend the side effect.

```sql
EXPLAIN ANALYZE
SELECT ...;
```

The first plan shows `~N rows`. The second shows `N rows`. A gap between the two is the signal. Estimates come from table statistics, Parquet footer statistics, and filters. `ANALYZE` recomputes table statistics after a large load.

`EXPLAIN (FORMAT JSON)` returns a machine-readable array of plan trees. `EXPLAIN ANALYZE (FORMAT JSON)` returns actuals in a different object shape. `EXPLAIN (FORMAT WEB)` opens an HTML plan. `EXPLAIN ANALYZE` prints text even when `-json` is set; use the JSON formats when a script needs JSON. The full operator table and profiling settings are in [references/plans.md](references/plans.md).

## Three diagnoses

### The scan does too much

Open the scan node. A healthy selective scan names the filter, reads fewer row groups than the file contains, and reads a small byte count.

```text
Table Scan
Filters: ordered_at >= DATE '2024-01-01'
Row Groups Scanned: 1 / 10
```

A scan that reads every row group has one of three causes:

| Cause | Fix |
| --- | --- |
| The filter wraps the column in a function or cast. | Rewrite as a range on the bare column. `CAST(d AS VARCHAR) LIKE '2024-01%'` scans all row groups; `d >= DATE '2024-01-01' AND d < DATE '2024-02-01'` prunes. |
| The file is not sorted or partitioned by the filter column. | Sort before writing, partition by the common filter, or accept a full scan. |
| The files are tiny or the row groups are below the minimum. | Write with 100,000 to 1,000,000 rows per group. The `ROW_GROUP_SIZE` options are in `duckdb-files`. |

`Data Read` in the summary is the bytes DuckDB actually read. It is a better signal than `count(*)` on a remote file. `Total Files Read` shows whether a glob opened more files than expected.

### The join explodes

Read the join node from the build side to the probe side. Equality joins use `Hash Join`. A missing predicate shows `Cross Product`. An inequality can use `Piecewise Merge Join` or `Nested Loop Join`.

| Plan node | Meaning | First move |
| --- | --- | --- |
| `Cross Product` | No join condition. | Add the join key or a deliberate `ON true`. |
| `Hash Join` with a huge actual row count on the probe side | The build side is too large or the key is not selective. | Pre-filter, pre-aggregate, or join on a smaller key. |
| `Nested Loop Join` or `Blockwise NL Join` on a large input | The predicate is not an equality or the join is deliberately non-equi. | Check whether a range or equality rewrite is possible. |
| Actual rows far above the estimate | Statistics are stale or the filter is not selective. | Run `ANALYZE`, then recheck the plan. |

Do not add `LIMIT` to a slow join until the plan shows the join is not the problem. `LIMIT` after a blocking join does not reduce the join work.

### The query spills or runs out of memory

Blocking operators are `GROUP BY`, joins, `ORDER BY`, and window functions. They buffer before they emit.

If the plan shows a huge intermediate row count before a blocking operator, fix the query shape first. Then check `memory_limit`, `temp_directory`, and `preserve_insertion_order`. The settings and tradeoffs are in [references/plans.md](references/plans.md).

## Parquet layout

Use file metadata before `count(*)` on a remote dataset.

```sql
SELECT file_name, num_rows, num_row_groups, file_size_bytes,
       round(num_rows::DOUBLE / nullif(num_row_groups, 0)) AS rows_per_group
FROM parquet_file_metadata('s3://bucket/prefix/**/*.parquet')
ORDER BY rows_per_group;
```

Healthy files are roughly 100 MB to 10 GB. Healthy row groups are 100,000 to 1,000,000 rows. Row groups below 5,000 rows are often 5 to 10 times slower. A single giant row group limits parallelism to one thread.

Check schema drift across files.

```sql
SELECT file_name, name, type, logical_type
FROM parquet_schema('data/**/*.parquet')
ORDER BY file_name, name;
```

A `schema mismatch in glob` error is the signal. `read_parquet(..., union_by_name = true)` fills missing columns with `NULL`. Do not use it to hide a broken producer; quarantine or backfill first. Use `parquet_file_metadata` for the total; the metadata rules live in `duckdb-files`.

## Profile and hand off

For repeatable profiles, use settings.

```sql
SET enable_profiling = 'json';
SET profiling_output = '/tmp/query.json';
SET tracked_metrics = ['query.*', 'operator.*'];
```

`tracked_metrics` affects `json` and `no_output`, not `query_tree`. `profiling_mode` is deprecated and has no effect. `CALL enable_profiling(...)` and `CALL disable_profiling()` are the table-function form. `duckdb_available_metrics()` lists metric names. Read [references/plans.md](references/plans.md) before building a metrics pipeline.

`duckdb -ui` is the local browser UI. `duckdb` owns the flag and the 2.0.0 extension caveat. `EXPLAIN (FORMAT WEB)` is the built-in plan fallback. The UI fetches its assets from `https://ui.duckdb.org`; queries run locally, but the page is remote. Do not use it for offline or restricted-network data.

## Verify

```bash
tmp=$(mktemp -d)
duckdb -no-agent -c "
COPY (SELECT range AS id FROM range(100000) ORDER BY id)
TO '$tmp/sorted.parquet' (FORMAT parquet, ROW_GROUP_SIZE 10000);
EXPLAIN ANALYZE SELECT count(*) FROM '$tmp/sorted.parquet' WHERE id = 99999;
" | grep -E 'Row Groups Scanned: 1 / 10'
rm -rf "$tmp"
```

The plan must show one row group scanned out of ten. Run `EXPLAIN` on the same query and confirm it shows `~N rows` and no actual timings.

```bash
duckdb -no-agent -c "CREATE TABLE t AS SELECT range AS id FROM range(100000); EXPLAIN SELECT count(*) FROM t WHERE id < 10;" | grep -E '~[0-9,]+ rows'
```

## References

- [Profiling](https://duckdb.org/docs/2.0/dev/profiling.html) owns profiling settings and formats.
- [EXPLAIN](https://duckdb.org/docs/2.0/guides/meta/explain.html) owns estimates.
- [Profiling statements](https://duckdb.org/docs/2.0/sql/statements/profiling.html) owns `EXPLAIN (SQL)`.
- [EXPLAIN ANALYZE](https://duckdb.org/docs/2.0/guides/meta/explain_analyze.html) owns actual rows and timings.
- [Tuning workloads](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html) owns spill, memory, and remote I/O.
- [Parquet metadata](https://duckdb.org/docs/2.0/data/parquet/metadata.html) owns the metadata functions.
- [Local UI](https://duckdb.org/docs/2.0/core_extensions/ui.html) owns the UI contract.
- Read `duckdb-sql` for `EXPLAIN (SQL)` and SQL result traps.
- Read `duckdb-files` for reader options, `COPY`, and the `parquet_metadata` row-count trap.
- Read `duckdb` for the settings table and the `-ui` flag.
