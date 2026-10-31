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

Diagnosis follows a six-stage loop: frame the symptom, capture a plan, localize the dominant cost, classify the cause, change one thing, and prove the change. Treat plan operators as evidence, not diagnoses.

Execute DuckDB with `duckdb`. For query semantics, consult `duckdb-sql`; for reader and writer parameters, consult `duckdb-files`; when time is spent outside SQL in host code, consult `duckdb-python`. For the diagnosis protocol and cost model, read [references/diagnosis.md](references/diagnosis.md). For operator specifications and JSON structures, read [references/plans.md](references/plans.md).

## Start with the symptom

| Symptom | First move | Proof |
| --- | --- | --- |
| Slow, correct result | Run `EXPLAIN`, then `EXPLAIN ANALYZE` | Dominant operator rows and elapsed timings fall |
| Out of memory | Locate blocking operator holding peak intermediate rows | `system.peak_temp_dir_size` and memory drop |
| Filter reads every row group | Inspect filter expression and physical column ordering | `Row Groups Scanned` drops below total groups |
| Join multiplies input rows | Check join key uniqueness and input cardinalities | Join output matches expected cardinality |
| Schema changed or columns missing | Check schema drift across files in `duckdb-files` | Every file matches expected schema |
| Wrong value returned without error | Inspect SQL semantics in `duckdb-sql` result traps | Result is proven correct before optimizing |

A wrong answer is never a profiling problem until plan execution or physical layout explains the incorrect value.

## Frame the case

Before modifying queries or settings, establish the baseline: record query text, binary version, active configuration, data snapshot, wall time, returned rows, and bytes read. Without a baseline, performance gains cannot be measured; without a latency and resource budget, tuning lacks a stop condition.

Change exactly one variable at a time under identical queries, data snapshots, binaries, and settings. When the OS file cache state changes between runs, record the difference.

## Plan first

To inspect estimated cardinality (`~N rows`) and the physical plan without executing queries, run `EXPLAIN`:

```sql
EXPLAIN SELECT customer_id, sum(amount) FROM orders WHERE ordered_at >= DATE '2024-01-01' GROUP BY customer_id;
EXPLAIN ANALYZE SELECT customer_id, sum(amount) FROM orders WHERE ordered_at >= DATE '2024-01-01' GROUP BY customer_id;
```

`EXPLAIN ANALYZE` executes the statement, reporting actual row counts (`N rows`) and timings. Never append `ANALYZE` to `INSERT`, `UPDATE`, `DELETE`, or `COPY` unless write side effects are intended. Divergence between `~N rows` and `N rows` flags stale statistics, skewed keys, or opaque predicates; after bulk loads, run `ANALYZE <table>` to recompute statistics.

To parse plans programmatically, specify JSON formats. `EXPLAIN (FORMAT JSON)` returns an array of plan nodes without execution actuals. `EXPLAIN ANALYZE (FORMAT JSON)` executes queries and returns one object containing `operator`, `query`, `io`, and `system` sections. `EXPLAIN ANALYZE` ignores the CLI `-json` flag; use explicit `(FORMAT JSON)`. Leave `legacy_metrics_format` disabled to avoid deprecated flat JSON.

When queries evaluate `count(*)`, `min`, or `max` over single tables or Parquet files, DuckDB resolves answers directly from storage metadata: plans display `COLUMN_DATA_SCAN` and analyzed profiles return `{"result":"error"}`. This indicates an absent profiler root rather than query failure; benchmark physical scans by adding row-level filters or projecting data columns. Text timings print at low precision (often `0µs`); use JSON metrics for operator ranking. To inspect visual plans locally in a browser, run `EXPLAIN (FORMAT WEB)`. For statement options and scan fields, see [references/plans.md](references/plans.md).

## Localize

Before reading full operator trees, isolate the dominant cost center:

| Signal | Evidence | Diagnostic meaning |
| --- | --- | --- |
| Time hotspot | One operator consumes most of `query.cpu_time` | Optimize this operator first; Amdahl's law bounds gains elsewhere |
| Estimate gap | `actual / estimated >= 100` or `<= 0.01` | Stale statistics, non-sargable predicate, or data skew |
| Scan pruning | `Row Groups Scanned` equals total after file-list pruning | Filter fails to prune row groups, or no pushed filter exists |
| File pruning | `Scanning Files: N/M` shows `N = M` with partition filter | Partition predicate is not pruning; do not use `File Filters` as signal |
| Join multiplication | Join output exceeds 10x the largest input | Missing join key, many-to-many relationship, or bad pre-aggregation |
| Blocking size | Operator accumulates millions of rows or hundreds of MB | High memory pressure and external spill risk |
| Spill | `system.peak_temp_dir_size > 0` | Memory budget exceeded; operator spilled to disk |
| Remote I/O | `io.total_bytes_read` is disproportionate to output rows | Inefficient projection, unpruned partitions, or fragmented layout |

Operator timings are exclusive; their sum approximates `query.cpu_time`, not `query.total_time`. Because worker threads overlap during parallel execution, the operator sum can exceed elapsed wall time. Compare relative percentage shares rather than absolute sums.

## Explain the cause

Match diagnostic signals to a failure classification. If multiple classes match, prioritize the class explaining the greatest row count or byte volume:

| Class | Fingerprint | First move |
| --- | --- | --- |
| Non-sargable filter | Scans every row group; filter wraps column in cast or function | Rewrite as a range comparison on the bare column |
| Unsorted or unpartitioned | Selective filter reads all groups despite bare column | Sort or partition by filter column prior to writing |
| Tiny files or row groups | High file count, few rows per group, excessive metadata overhead | Compact dataset into larger files and row groups |
| Cardinality explosion | Join output dwarfs both input cardinalities | Add missing join key, deduplicate keys, or pre-aggregate |
| Stale statistics | Base-table estimate is far below actual row count | Run `ANALYZE <table>` |
| Memory pressure | Large blocking operator, disk spill, or out-of-memory error | Push filters ahead of blocking operator to reduce input rows |
| Remote I/O | Low CPU utilization, high bytes read, many remote HTTP requests | Project fewer columns, prune partitions, and enlarge files |
| Client path | SQL execution is fast, but total client latency is high | Fetch smaller batches, stream results, or transfer via Arrow |
| Lock or concurrency | Thread waits, `ResourceInUseException`, single-writer lock | Separate readers and writers; adopt Quack or DuckLake |

## Change one thing and prove it

When optimizing, prioritize interventions in order: query rewrite > file rewrite > configuration setting > hardware scaling.

| Condition | Intervention |
| --- | --- |
| Filter wraps column in function or cast | Rewrite predicate as bare-column range |
| Join produces many-to-many multiplication | Pre-aggregate inputs or deduplicate join keys |
| Blocking operator sees excessive rows | Push selective filter ahead of operator |
| Selective filter runs repeatedly on dataset | Sort or partition files on filter column |
| Cardinality estimates diverge after bulk load | Run `ANALYZE <table>` |
| Plan shape is sound, spill occurs, memory available | Raise `memory_limit` |
| Spill is unavoidable on local disk | Set `temp_directory` |

After applying an intervention, rerun the identical baseline. Compare elapsed wall time, `io.total_bytes_read`, `system.peak_temp_dir_size`, dominant operator rows and timings, and result correctness. A 5% timing change within run-to-run variance is not a performance win. Stop tuning once the query meets the resource budget or when the cost of further changes exceeds the remaining performance gap. Never append `LIMIT` to a blocking operator (`ORDER BY`, `GROUP BY`) and treat it as a fix; blocking work completes before rows are truncated. Never raise `memory_limit` before reducing intermediate row counts entering blocking operators.

## Parquet layout

When inspecting remote Parquet datasets, query file metadata before issuing `count(*)` to avoid downloading full data pages:

```sql
SELECT file_name, num_rows, num_row_groups, file_size_bytes,
       round(num_rows::DOUBLE / nullif(num_row_groups, 0)) AS rows_per_group,
       round(file_size_bytes::DOUBLE / nullif(num_rows, 0), 2) AS bytes_per_row
FROM parquet_file_metadata('s3://bucket/prefix/**/*.parquet')
ORDER BY rows_per_group;
```

In scan profiles, `Row Groups Scanned: 1 / 1` can indicate a single pruned file rather than healthy dataset pruning, because denominators compute after file-list pruning. Correlate with `Scanning Files: N/M`, `Total Files Read`, and `parquet_file_metadata.num_row_groups`. `Data Read` measures cumulative FileSystem bytes including footers and temp spills; when `system.peak_temp_dir_size > 0`, treat `Data Read` as an upper bound.

Sizing parameters and layout heuristics: default `ROW_GROUP_SIZE` is 122,880 rows. DuckDB rounds requests up to multiples of 2,048 (minimum 2,048); `ROW_GROUP_SIZE 10000` writes 10,240-row groups. `ROW_GROUP_SIZE_BYTES` writes approximate batches, and `FILE_SIZE_BYTES` may overshoot or undershoot; specify `ROW_GROUPS_PER_FILE` when exact group counts are mandatory. For narrow tables, target 100,000 to 1,000,000 rows per group; for wide tables, target 10 to 50 MB per group; target files between 100 MB and 10 GB. Avoid single monolithic row groups that restrict concurrency to one thread, and avoid row groups under 5,000 rows where metadata scheduling dominates scan time. Validate layouts using `parquet_metadata` following writes.

If multi-file reads fail with `schema mismatch in glob`, query column definitions across files:

```sql
SELECT file_name, name, type, logical_type
FROM parquet_schema('data/**/*.parquet')
ORDER BY file_name, name;
```

While `read_parquet(..., union_by_name = true)` handles missing columns by populating `NULL`, treat it as an emergency read repair rather than an upstream producer solution; quarantine or rewrite drifted files. For total file metadata and reader options, consult `duckdb-files`.

## Automate

To automate capture and localization, run `scripts/plan_lint.py` to produce ranked findings with supporting evidence and proof commands. By default, the linter operates plan-only without executing queries:

```bash
python3 scripts/plan_lint.py --db app.duckdb --query-file slow.sql
python3 scripts/plan_lint.py --db app.duckdb --query-file slow.sql --analyze
python3 scripts/plan_lint.py --query "SELECT ..." --json
python3 scripts/plan_lint.py --self-test
```

To execute queries during linting, pass `--analyze`. To prevent accidental mutations, `--analyze` refuses write statements unless `--allow-write` is explicitly provided. When inspecting persistent databases, pass `--db <file>` and `--readonly` to open connections with `-readonly`. To mirror production constraints, supply settings via `--set memory_limit=4GB`. The linter detects metadata-only plans and reports the absent profile tree without failing. Script CI pipelines using exit codes (1 for high or critical findings, 0 otherwise). Automated linting supplements but never replaces before-and-after baseline proofs.

## Profile and hand off

For repeatable session profiling, configure settings:

```sql
SET enable_profiling = 'json';
SET profiling_output = '/tmp/query.json';
SET tracked_metrics = ['query.*', 'operator.*', 'io.*', 'system.*'];
```

`tracked_metrics` governs `json` and `no_output`; `query_tree` uses fixed metrics. Always include `io.*` and `system.*`; omitting them drops I/O byte counts and spill indicators. Each statement overwrites `profiling_output`, retaining only the final statement; `EXPLAIN ANALYZE` bypasses this file completely. Session `enable_profiling` alters bare `EXPLAIN ANALYZE` outputs; specify explicit `(FORMAT TEXT)` or `(FORMAT JSON)`. `profiling_mode` is deprecated (no-op). `legacy_metrics_format` is deprecated (alters JSON schema). `operator.cpu_time` is documented but unpopulated; read `operator.timing`. Table functions provide programmatic control via `CALL enable_profiling(...)` and `CALL disable_profiling()`; query available metrics with `SELECT * FROM duckdb_available_metrics();`. For metrics pipeline schemas, read [references/plans.md](references/plans.md).

For visual query trees, `duckdb -ui` launches the local browser interface (`duckdb` owns the flag and install requirements). Alternatively, run `EXPLAIN (FORMAT WEB)` for built-in HTML plan visualization. Note that while queries execute locally, `-ui` fetches web assets from `https://ui.duckdb.org`; never launch it in air-gapped, offline, or restricted-network environments.

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

The plan must report one row group scanned out of ten. The row-level filter forces physical scanning, whereas an unconstrained `count(*)` may evaluate as metadata-only. Run `EXPLAIN` on the identical query to verify it outputs `~N rows` without execution timings.

```bash
python3 scripts/plan_lint.py --self-test
```

The self-test constructs a cross join, a non-sargable Parquet filter, a sargable point lookup, and a metadata-only aggregate. Verification requires flagging the cross product, full scan, and absent profile, while passing the point lookup without warnings. It also confirms rejection of hidden secondary statements and malformed `--set` options.

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
