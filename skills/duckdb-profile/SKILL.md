---
name: duckdb-profile
description: >
  Diagnose slow DuckDB 2.0 queries and unhealthy Parquet layouts. Covers
  EXPLAIN versus EXPLAIN ANALYZE, estimate and actual row gaps, full scans,
  join blowups, row-group pruning, spill, and schema drift. Use when a query is
  slow, scans too much, returns a huge join, runs out of memory, or a Parquet
  dataset needs a health check.
---

# Query and file diagnostics

Diagnosis is a loop: frame the symptom, capture a plan, localize the dominant cost, classify the cause, change one thing, and prove the change. A plan operator is evidence, not a diagnosis.

Run DuckDB with `duckdb`. Read `duckdb-sql` for query semantics, `duckdb-files` for reader and writer options, and `duckdb-python` when the time is spent outside SQL. This skill owns the diagnosis. For the full protocol and cost model, read [references/diagnosis.md](references/diagnosis.md). For the operator and JSON reference, read [references/plans.md](references/plans.md).

## Start with the symptom

| Symptom | First move | Proof |
| --- | --- | --- |
| Slow, correct result | `EXPLAIN`, then `EXPLAIN ANALYZE` | The dominant operator's rows and time fall |
| Out of memory | Find the blocking operator with the most intermediate rows | `system.peak_temp_dir_size` and peak memory fall |
| A filter reads every row group | Check the filter expression and the sort order | `Row Groups Scanned` is below the total |
| A join returns far more rows than its inputs | Check the join key and both input cardinalities | Join output approaches the expected cardinality |
| A file changed and columns are missing or renamed | Check schema drift in `duckdb-files` first | Every file matches the expected schema |
| A query returns a wrong value with no error | Use `duckdb-sql` result traps first | The value is correct before it is fast |

A wrong answer is not a profiling problem until the plan or the file layout explains the wrong value.

## Frame the case

Record the query text, the binary version, the settings that affect the answer, the data snapshot, the wall time, the rows returned, and the bytes read. Without a baseline, "faster" is not measurable. Without a budget, the work has no stop condition.

Change one thing at a time. Same query, same data, same binary, same settings. If the cache state changed, say so.

## Plan first

`EXPLAIN` shows the physical plan and estimated rows. It does not run the query.

```sql
EXPLAIN
SELECT customer_id, sum(amount)
FROM orders
WHERE ordered_at >= DATE '2024-01-01'
GROUP BY customer_id;
```

`EXPLAIN ANALYZE` runs the query and adds actual rows and timings. It also runs writes. Never add `ANALYZE` to an `INSERT`, `UPDATE`, `DELETE`, or `COPY` unless you intend the side effect.

```sql
EXPLAIN ANALYZE
SELECT ...;
```

The first plan shows `~N rows`. The second shows `N rows`. A gap between the two is a signal. Estimates come from table statistics, Parquet footer statistics, and filters. `ANALYZE` recomputes table statistics after a large load.

`EXPLAIN (FORMAT JSON)` returns an array of plan nodes and no actuals. `EXPLAIN ANALYZE (FORMAT JSON)` executes the statement and returns one object with `operator`, `query`, `io`, and `system` sections. `EXPLAIN ANALYZE` ignores `-json`; the `(FORMAT JSON)` form is the JSON path. The two JSON shapes are different. `legacy_metrics_format` returns a third, flat shape; leave it off.

A metadata-only query can return the right answer with no operator tree. `count(*)`, `min`, and `max` over one table or Parquet file can be answered from metadata: the plan shows `COLUMN_DATA_SCAN` and the profile JSON is `{"result":"error"}`. That is not a query failure. Measure a real scan with a row-level filter or a data-column projection. Text timings are rounded to 0.01 seconds and can print `0µs`; use JSON for any ranking.

`EXPLAIN (FORMAT WEB)` opens an HTML plan. Full statement forms, scan fields, and the operator map are in [references/plans.md](references/plans.md).

## Localize

Find the operator that owns the cost before reading the whole tree.

| Signal | Evidence | What it means |
| --- | --- | --- |
| Time hotspot | One operator has most of `query.cpu_time` | Optimize it first. Other changes cannot beat Amdahl's law. |
| Estimate gap | `actual / estimated >= 100` or `<= 0.01` | Stale statistics, an unusual predicate, or skew. |
| Scan pruning | `Row Groups Scanned` equals the total after file-list pruning | The filter does not prune row groups, or there is no filter. |
| File pruning | `Scanning Files: N/M` is `N = M` with a partition filter | The partition predicate is not pruning. Do not use `File Filters` as the signal. |
| Join multiplication | Join output is at least 10 times the largest input | Missing key, many-to-many key, or a bad pre-aggregation. |
| Blocking size | A blocking operator holds millions of rows or hundreds of MB | Memory pressure and spill risk. |
| Spill | `system.peak_temp_dir_size > 0` | The query exceeded the memory budget. |
| I/O | `io.total_bytes_read` is large relative to the result | Projection, partition pruning, or file layout. |

Operator timings are exclusive. Their sum is close to `query.cpu_time`, not `query.total_time`. On a parallel query the sum can exceed wall time because threads overlap. Compare shares, not sums.

## Explain the cause

Match the evidence to one failure class. If two fit, pick the one that explains the largest row or byte count.

| Class | Fingerprint | First move |
| --- | --- | --- |
| Non-sargable filter | Every row group is scanned; the filter wraps the column in a cast or function | Rewrite as a range on the bare column |
| Unsorted or unpartitioned data | A selective filter still reads all groups | Sort or partition by the filter column before writing |
| Tiny files or row groups | Many files, few rows per group, high metadata overhead | Rewrite with larger files and groups |
| Cardinality explosion | Join output dwarfs both inputs | Add the missing key, deduplicate, or pre-aggregate |
| Stale statistics | Estimate far below actual on a base table | `ANALYZE table` |
| Memory pressure | Large blocking operator, spill, or OOM | Reduce rows before the blocking operator |
| Remote I/O | Low CPU, high bytes read, many requests | Project fewer columns, prune partitions, enlarge files |
| Client path | SQL is fast but total time is slow | Fetch less, stream, or use Arrow |
| Lock or concurrency | Waits, `ResourceInUseException`, one-writer lock | Separate readers and writers, or use Quack or DuckLake |

## Change one thing and prove it

Prefer a query rewrite over a file rewrite, a file rewrite over a setting, and a setting over hardware.

| Change | Use when |
| --- | --- |
| Rewrite the predicate | The filter is not sargable |
| Pre-aggregate or deduplicate | The join is many-to-many |
| Move the filter before a blocking operator | The blocking operator sees too many rows |
| Sort or partition the files | The same selective filter runs repeatedly |
| `ANALYZE` | Estimates are stale after a bulk load |
| Raise `memory_limit` | The shape is sound and the machine has headroom |
| Set `temp_directory` | Spill is unavoidable and the temp path is local |

Re-run the same baseline. Compare wall time, `io.total_bytes_read`, `system.peak_temp_dir_size`, the dominant operator's rows and time, and the correctness check. Stop when the query meets the budget, or when the next change is larger than the remaining gap. A 5 percent change inside run-to-run noise is not a win.

Do not add `LIMIT` to a blocking operator and call it a fix. The work happens before the limit. Do not raise `memory_limit` before reducing the rows entering the blocking operator.

## Parquet layout

Use file metadata before `count(*)` on a remote dataset.

```sql
SELECT file_name, num_rows, num_row_groups, file_size_bytes,
       round(num_rows::DOUBLE / nullif(num_row_groups, 0)) AS rows_per_group,
       round(file_size_bytes::DOUBLE / nullif(num_rows, 0), 2) AS bytes_per_row
FROM parquet_file_metadata('s3://bucket/prefix/**/*.parquet')
ORDER BY rows_per_group;
```

A `Row Groups Scanned: 1 / 1` can mean one selected file, not a healthy dataset. The denominator is after file-list pruning. Pair it with `Scanning Files: N/M`, `Total Files Read`, and `parquet_file_metadata.num_row_groups`. `Data Read` is query-wide and includes Parquet footers and spill; if `system.peak_temp_dir_size > 0`, treat it as an upper bound.

The default `ROW_GROUP_SIZE` is 122,880 rows. A request is rounded up to a multiple of 2,048, with a minimum of 2,048, so `ROW_GROUP_SIZE 10000` produces 10,240-row groups except the final group. `ROW_GROUP_SIZE_BYTES` is approximate; rows are written in batches. `FILE_SIZE_BYTES` can overshoot or undershoot. Use `ROW_GROUPS_PER_FILE` when the exact group count matters.

For narrow rows, 100,000 to 1,000,000 rows per group is a useful range. For wide rows, 10 to 50 MB per group is a better target. Files from roughly 100 MB to 10 GB are a useful range, not a rule. A single giant row group limits parallelism to one thread. Row groups below 5,000 rows often cost more in metadata and scheduling than they save. These are heuristics; confirm with `parquet_metadata` after the write.

Check schema drift across files.

```sql
SELECT file_name, name, type, logical_type
FROM parquet_schema('data/**/*.parquet')
ORDER BY file_name, name;
```

A `schema mismatch in glob` error is the signal. `read_parquet(..., union_by_name = true)` fills missing columns with `NULL`. It is a read repair, not a producer fix. Quarantine or backfill the files first. Use `parquet_file_metadata` for the total; the metadata rules live in `duckdb-files`.

## Automate

`scripts/plan_lint.py` runs the capture and localization steps, then prints ranked findings with evidence and a proof command. It is plan-only by default and never executes the query unless `--analyze` is passed.

```bash
python3 scripts/plan_lint.py --db app.duckdb --query-file slow.sql
python3 scripts/plan_lint.py --db app.duckdb --query-file slow.sql --analyze
python3 scripts/plan_lint.py --query "SELECT ..." --json
python3 scripts/plan_lint.py --self-test
```

`--analyze` executes the statement and refuses a statement that looks like a write unless `--allow-write` is also passed. The exit code is 1 for a high or critical finding and 0 otherwise, so a script can gate on it. Pass `--set memory_limit=4GB` to reproduce production settings. The linter recognizes a metadata-only plan and reports that no profile tree exists. It does not replace the before-and-after proof.

## Profile and hand off

For repeatable profiles, use settings.

```sql
SET enable_profiling = 'json';
SET profiling_output = '/tmp/query.json';
SET tracked_metrics = ['query.*', 'operator.*', 'io.*', 'system.*'];
```

`tracked_metrics` affects `json` and `no_output`; `query_tree` uses a fixed metric set. The example above includes `io.*` and `system.*`; without them, bytes and spill disappear. `profiling_output` is overwritten by each statement, so the file holds the last statement, and `EXPLAIN ANALYZE` ignores the file entirely. Session `enable_profiling` also changes a bare `EXPLAIN ANALYZE` output format; use explicit `(FORMAT TEXT)` or `(FORMAT JSON)`. `profiling_mode` is deprecated and has no effect. `legacy_metrics_format` is deprecated and changes the JSON shape. `operator.cpu_time` is advertised but not emitted; use `operator.timing`. `CALL enable_profiling(...)` and `CALL disable_profiling()` are the table-function form. `duckdb_available_metrics()` lists metric names. Read [references/plans.md](references/plans.md) before building a metrics pipeline.

`duckdb -ui` is the local browser UI. `duckdb` owns the flag and the install caveat. `EXPLAIN (FORMAT WEB)` is the built-in plan fallback. The UI page is served locally but fetches its assets from `https://ui.duckdb.org`; queries run locally, but the page is remote. Do not use it for offline or restricted-network data.

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

The plan must show one row group scanned out of ten. The row-level filter forces a real scan; a bare `count(*)` can be metadata-only. Run `EXPLAIN` on the same query and confirm it shows `~N rows` and no actual timings.

```bash
python3 scripts/plan_lint.py --self-test
```

The self-test builds a cross join, a non-sargable Parquet filter, and a sargable point lookup. It must find the cross product and the full scan, and must not flag the point lookup.

## References

- [Profiling](https://duckdb.org/docs/2.0/dev/profiling.html) owns profiling settings and formats.
- [EXPLAIN](https://duckdb.org/docs/2.0/guides/meta/explain.html) owns estimates.
- [Profiling statements](https://duckdb.org/docs/2.0/sql/statements/profiling.html) owns `EXPLAIN (SQL)`.
- [EXPLAIN ANALYZE](https://duckdb.org/docs/2.0/guides/meta/explain_analyze.html) owns actual rows and timings.
- [Tuning workloads](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html) owns spill, memory, and remote I/O.
- [Parquet metadata](https://duckdb.org/docs/2.0/data/parquet/metadata.html) owns the metadata functions.
- [Local UI](https://duckdb.org/docs/2.0/core_extensions/ui.html) owns the UI contract.
- Read [references/diagnosis.md](references/diagnosis.md) for the protocol, cost model, and workflows.
- Read [references/plans.md](references/plans.md) for the statement matrix, JSON fields, metrics, and operator map.
- Read `duckdb-sql` for `EXPLAIN (SQL)` and SQL result traps.
- Read `duckdb-files` for reader options, `COPY`, and the `parquet_metadata` row-count trap.
- Read `duckdb` for the settings table and the `-ui` flag.
