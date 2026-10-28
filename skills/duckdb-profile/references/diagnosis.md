# Diagnosis guide

Read this when the skill's symptom table is not enough: a query is slow, spills, or reads too much, and you need a repeatable way to localize the cause instead of guessing at settings.

## The case file

A diagnosis is six fields. Do not skip a field because the first plan looks familiar.

| Field | Question | Example |
| --- | --- | --- |
| Question | What user-visible symptom are we explaining? | "This dashboard query takes 40 seconds." |
| Baseline | What exact query, data, binary, settings, and cache state produced it? | Query text, `duckdb --version`, `threads`, `memory_limit`, file paths, row counts. |
| Budget | What is acceptable? | "Under 2 seconds and under 500 MB read." |
| Measurement | What did the plan or profile actually show? | `EXPLAIN ANALYZE` operator rows, timings, row groups, bytes. |
| Finding | Which single cause explains most of the gap? | "The join output is 4M rows from 1k-row inputs." |
| Proof | What changed, and what did the same baseline show after it? | "Added the missing key; join output fell to 1k; wall time 40s to 0.8s." |

Without a baseline, "faster" is not measurable. Without a budget, the work has no stop condition. Without a proof, the change is a hypothesis.

### Invariants

- Same query text, same data snapshot, same binary, same settings, same cache state.
- Change one thing at a time. A query rewrite plus a `memory_limit` change cannot tell you which one worked.
- Measure the operator, not only the root. A query that returns 10 rows can scan a billion.
- Keep units on every number: rows, bytes, seconds. A bare "40" is not a diagnosis.
- Prefer a query rewrite over a file rewrite, a file rewrite over a setting, and a setting over hardware.
- Re-run the correctness check after the speed change. A faster wrong answer is not a fix.

## The cost model

DuckDB's work is rows moving through operators. Time is bounded by the slowest of CPU, I/O, memory, and serialization.

| Quantity | Working estimate | What it tells you |
| --- | --- | --- |
| Scan bytes | `rows_after_pruning × columns × bytes_per_value` | Whether the scan is the problem, and whether pruning worked. |
| Selectivity | `output_rows / input_rows` | Whether a filter is selective enough to matter. |
| Join output | `|A| × |B| / max(distinct join keys)` for an equality join | Whether the key is unique enough. Skew makes this worse. |
| Aggregation state | `groups × state_width` | Whether a `GROUP BY` will fit in memory. |
| Sort work | `N log N` comparisons, plus `N × width` bytes if external | Whether an `ORDER BY` or window will spill. |
| Network cost | `bytes / bandwidth + requests × round_trip` | Whether a remote scan is latency-bound or bandwidth-bound. |
| Parallel speedup | bounded by the largest serial operator and the slowest scan | Why adding threads stopped helping. |

These are not the optimizer's cost units. They are sanity checks. When an operator's actual rows or bytes are orders of magnitude above the estimate, the model and the plan disagree. Find out which one is wrong before changing a setting.

### Reading a profile

`EXPLAIN` gives estimates. `EXPLAIN ANALYZE` executes the statement and adds actual rows and timings.

- Operator timings are exclusive. Their sum is close to `query.cpu_time`.
- `query.total_time` includes planning, waiting, and serialization. On a serial query it is larger than the operator sum; on a parallel query the sum and `cpu_time` can exceed it.
- On a parallel query, `query.cpu_time` can exceed wall time because threads overlap. Do not add operator times to predict wall time.
- `system.peak_temp_dir_size > 0` proves a spill. `system.peak_buffer_memory` shows how close the query came to `memory_limit`.
- `io.total_bytes_read` is query-wide FileSystem bytes, including footers and spill reads. It is not the file size and not scan-only bytes. If the query spilled, treat it as an upper bound.
- `operator.rows_scanned` is scan-reported. A base-table scan can report rows examined; a Parquet scan with pushed filters can report rows emitted. Use `intermediate_rows` for emitted rows, and row groups, `Scanning Files`, and `Data Read` for scan work.
- A plan-only `EXPLAIN` has no row-group scan counts, actual rows, timings, spill, or bytes. Do not diagnose pruning from a plan-only tree.
- A metadata-only `count(*)`, `min`, or `max` can produce no operator tree and `{"result":"error"}`. That is not a query failure.

## The loop

### 1. Frame

Convert the symptom into a metric.

| Symptom | Baseline metric | First measurement |
| --- | --- | --- |
| Slow, correct result | Wall time, rows returned, bytes read | `EXPLAIN`, then `EXPLAIN ANALYZE` |
| Out of memory | Peak buffer memory, temp directory size, blocking rows | `EXPLAIN ANALYZE` with the production `memory_limit` |
| Reads too much | `io.total_bytes_read`, `row_groups_scanned / total` | `EXPLAIN ANALYZE` on the scan |
| Wrong rows | Correctness first | `duckdb-sql` result traps |
| Slow only in Python | Client time versus SQL time | `duckdb-python`, then profile the SQL |
| Slow only on S3 | Bytes read, requests, file count | `EXPLAIN ANALYZE` plus metadata |

If the answer is wrong, stop. A wrong answer is not a performance problem until the plan explains the wrong value.

### 2. Capture

Start with `EXPLAIN` when the query is cheap or the statement is a write. Use `EXPLAIN ANALYZE` only when you intend to execute the statement.

```sql
EXPLAIN
SELECT ...;

EXPLAIN ANALYZE
SELECT ...;

EXPLAIN (FORMAT JSON)
SELECT ...;
```

`EXPLAIN ANALYZE` executes `INSERT`, `UPDATE`, `DELETE`, and `COPY` too. Use a read-only copy, a transaction you can roll back, or plain `EXPLAIN` for writes.

For a script, `EXPLAIN ANALYZE (FORMAT JSON)` is the stable path. It returns one object with `io`, `operator`, `query`, and `system` sections. `EXPLAIN (FORMAT JSON)` returns an array of nodes and has no actuals. The two shapes are different; do not feed one parser to both.

### 3. Localize

Find the dominant cost center before reading the whole tree.

| Signal | Evidence | Meaning |
| --- | --- | --- |
| Time hotspot | One operator has most of `query.cpu_time` | Optimize that operator first. Amdahl's law bounds the gain elsewhere. |
| Estimate gap | `actual / estimated >= 100` or `<= 0.01` | Statistics are stale, the predicate is unusual, or the join key is skewed. |
| Scan pruning | `Row Groups Scanned` equals the total after file-list pruning | The filter is not pruning row groups, or the data is unsorted. |
| File pruning | `Scanning Files: N/M` is `N = M` with a partition filter | The partition predicate is not pruning. `File Filters` is not reliable. |
| Join multiplication | Join output `>= 10×` the largest input | Missing key, many-to-many key, or a bad pre-aggregation. |
| Blocking size | A blocking operator holds millions of rows or hundreds of MB | Memory pressure and spill risk. |
| Spill | `system.peak_temp_dir_size > 0` | The query exceeded the memory budget. |
| I/O | `io.total_bytes_read` is large relative to the result | Projection, partition pruning, or file layout. |

### 4. Classify

Match the evidence to one failure class. If two classes fit, pick the one that explains the largest actual row or byte count.

| Class | Fingerprint | First move | Proof |
| --- | --- | --- | --- |
| Non-sargable filter | Scan reads every row group; filter wraps the column in a cast or function | Rewrite as a range on the bare column | Row groups scanned falls |
| Unsorted or unpartitioned data | A selective filter still reads all groups | Sort or partition by the filter column before writing | Same query reads fewer groups |
| Tiny files or tiny row groups | Many files, small `num_rows / num_row_groups`, high metadata overhead | Rewrite with larger files and groups | File count and scan time fall |
| Cardinality explosion | Join output far above both inputs | Add the missing key, deduplicate, or pre-aggregate | Join output falls to the expected cardinality |
| Stale statistics | Estimate far below actual on a base table | `ANALYZE table` | Estimate approaches actual |
| Memory pressure | Large blocking operator, spill, or OOM | Reduce rows before the blocking operator | Peak temp dir and buffer memory fall |
| Remote I/O | Low CPU, high bytes read, many requests | Project fewer columns, prune partitions, increase file size | Bytes read falls |
| Client path | SQL is fast, total time is slow | Fetch less, stream, materialize, or use Arrow | Client time falls |
| Lock or concurrency | Waits, `ResourceInUseException`, one-writer lock | Separate readers and writers, or use Quack/DuckLake | Wait time disappears |

### 5. Intervene

Change one thing. Prefer the change with the largest expected effect and the smallest blast radius.

| Change | Use when | Avoid when |
| --- | --- | --- |
| Rewrite the predicate | Filter is not sargable | The rewrite changes NULL or type semantics; check `duckdb-sql` |
| Pre-aggregate or deduplicate | Join is many-to-many | The output must keep every input row |
| Move the filter earlier | A blocking operator sees too many rows | The filter depends on the join result |
| Sort or partition the files | The same selective filter runs repeatedly | It is a one-off query |
| `ANALYZE` | Estimates are stale after a bulk load | The table is small or the query is ad hoc |
| Raise `memory_limit` | The shape is sound and the machine has headroom | The plan is a cross product or a bad join |
| Set `temp_directory` | Spill is unavoidable | The temp directory is a network mount |
| `preserve_insertion_order = false` | Order is not required by the consumer | The consumer depends on row order |

### 6. Prove

Run the same baseline, then compare:

- Wall time, with the same warm or cold cache state.
- `io.total_bytes_read`.
- `system.peak_temp_dir_size`.
- The dominant operator's actual rows and time.
- The correctness check.

Stop when the result meets the budget, or when the next change is larger than the remaining gap. A 5% change inside run-to-run noise is not a win.

## Workflows

### Slow query, ten minutes

1. Run `EXPLAIN` and confirm the plan shape. No `EXPLAIN ANALYZE` on a write.
2. Run `EXPLAIN ANALYZE` on a safe query or copy.
3. List operators by time. Find the top one.
4. Check the top operator's actual rows against its estimate and its children.
5. If it is a scan, check row groups and filters.
6. If it is a join, check output versus inputs.
7. Change one thing. Re-run the same profile.
8. Record the before and after numbers.

```bash
python3 scripts/plan_lint.py --db app.duckdb --query-file slow.sql --analyze
```

The linter does steps 1 to 4 and emits ranked findings with evidence. It does not replace step 7.

### Out of memory, ten minutes

1. Find the blocking operator with the largest `intermediate_rows` or `intermediate_size_bytes`.
2. Reduce rows before that operator: filter, pre-aggregate, or eliminate a `SELECT *`.
3. Check for a cross product or a many-to-many join. A bigger `memory_limit` will not fix a bad join.
4. Set `temp_directory` to local SSD and a hard `max_temp_directory_size`.
5. Only then raise `memory_limit`, and only if the machine has headroom.
6. If the consumer does not need order, set `preserve_insertion_order = false`.
7. If the result is large, stream it or write it instead of fetching it.

```sql
SET memory_limit = '4GB';
SET temp_directory = '/fast/disk/duckdb.tmp';
SET max_temp_directory_size = '50GB';
SET preserve_insertion_order = false;
```

`memory_limit` is a ceiling, not a target. Lowering it can force a spill that was not there. Raising it can hide a plan that should be rewritten.

### Remote lake query

1. Read metadata before `count(*)`: `parquet_file_metadata` gives `num_rows`, `num_row_groups`, and `file_size_bytes`.
2. Check `Scanning Files`, `Total Files Read`, `Row Groups Scanned`, and `Data Read` in the profile. `Total Files Read` is files opened, not glob matches. `Data Read` includes footers and spill.
3. Confirm the partition filter targets the partition column. `year = 2024` prunes; `year(ordered_at) = 2024` does not. A foldable expression on the partition value, such as `year % 2 = 0`, can still prune files.
4. Project only the columns the result needs.
5. Check that the path glob did not open more files than intended.
6. A tight filter over many files can spend its time on tiny footer range requests. `parquet_metadata_cache` and `enable_http_metadata_cache` default false; they help repeated scans in one process, not a cold query. Compact or partition before tuning `threads`.
7. Tune `async_threads`, `read_ahead_depth`, and `http_retries` only after bytes and file count are under control.

### Parquet health check

```sql
SELECT file_name, num_rows, num_row_groups, file_size_bytes,
       round(num_rows::DOUBLE / nullif(num_row_groups, 0)) AS rows_per_group,
       round(file_size_bytes::DOUBLE / nullif(num_rows, 0), 2) AS bytes_per_row
FROM parquet_file_metadata('s3://bucket/prefix/**/*.parquet')
ORDER BY rows_per_group;
```

Aim for groups large enough that metadata and scheduling are small, and numerous enough for parallel scans. The default `ROW_GROUP_SIZE` is 122,880 rows, rounded up to a multiple of 2,048. For narrow rows, 100,000 to 1,000,000 rows per group is a useful range. For wide rows, 10 to 50 MB per group is a better target. Files from roughly 100 MB to 10 GB are a useful range, not a rule. `FILE_SIZE_BYTES` can overshoot; read the footer after the write.

Check schema drift separately:

```sql
SELECT file_name, name, type, logical_type
FROM parquet_schema('data/**/*.parquet')
ORDER BY file_name, name;
```

A `schema mismatch in glob` error is the signal. `union_by_name = true` fills missing columns with `NULL`. It is a read repair, not a producer fix. Quarantine or backfill the files first.

### Regression hunt

1. Capture `EXPLAIN (FORMAT JSON)` for the old and new query or data snapshot.
2. Compare the operator trees by path, not by line order.
3. Compare estimated rows, `row_groups_scanned`, and join output.
4. Capture `EXPLAIN ANALYZE` on both if the plan difference is not decisive.
5. Change one input, not both. A query change and a data change at once is not a regression test.

The JSON node names are stable enough for a diagnostic, not a public API. `extra_info` keys vary by operator and version.

### Safe profile in production

- Prefer read-only replicas, clones, or a bounded `LIMIT` subquery.
- Use `-readonly` when the database is opened only for diagnosis.
- Set `max_execution_time` before an unbounded query.
- Do not run `EXPLAIN ANALYZE` on a write unless the write is intended and authorized.
- Do not paste secrets or tokens into a query file or a saved profile.
- Keep the profile file local; it can contain the query text and table names.

```bash
duckdb -readonly app.duckdb -c "SET max_execution_time = 30000; EXPLAIN ANALYZE SELECT ...;"
```

## Plan diff

A useful diff compares the same operator path across two profiles.

| Field | Why it changed the answer |
| --- | --- |
| `estimated_rows` | Shows whether statistics or a predicate changed. |
| `actual_rows` | Shows whether the data or the filter changed. |
| `row_groups_scanned / total` | Shows whether pruning improved or regressed. |
| `intermediate_size_bytes` | Shows whether memory pressure changed. |
| `time` | Shows whether the change moved the cost. |

Ignore absolute timings below about 10 ms on a warm local database; they are noise. Prefer a ratio or a repeated run.

## Stop rules

- Stop when the query meets the budget.
- Stop when the next change is bigger than the remaining gap.
- Stop when the bottleneck is outside the plan: client fetch, serialization, lock waits, or network.
- Do not add `LIMIT` to a blocking operator and call it a fix. The work happens before the limit.
- Do not raise `memory_limit` before reducing the rows entering a blocking operator.
- Do not rewrite the file layout for a one-off query.
- Do not use `union_by_name` to hide schema drift in a production pipeline.
- Do not optimize a query whose answer is wrong.
- Do not benchmark a scan with `count(*)`, `min`, or `max` when DuckDB can answer from metadata.

## Handoffs

| Observation | Owner |
| --- | --- |
| Wrong value, type, or NULL behavior | `duckdb-sql` |
| Reader, COPY, secret, or remote path | `duckdb-files` |
| Storage version, migration, rollback | `duckdb-migrate` |
| Missing or stale extension | `duckdb-extensions` |
| DuckLake, Iceberg, Delta, Unity | `duckdb-lakehouse` |
| Python relation, fetch, Arrow, thread | `duckdb-python` |
| Quack, Postgres, MySQL route | `duckdb-quack` |
| Spatial predicate or index | `duckdb-spatial` |
