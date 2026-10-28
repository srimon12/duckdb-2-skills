# Slice: diagnostics engine and plan JSON

Status: complete, with two open questions
Scope: the plan and profile JSON contract that `duckdb-profile` depends on, the spill signal, the profiling formats, and the plan-linter design.
Sources: DuckDB 2.0.0 source at `d54cbbe3df` (`/tmp/opencode/duckdb-src`), the 2.0 manual pages linked from the skill, and probes on DuckDB 2.0.0 `d54cbbe3df` Linux x86_64.

## Verified facts

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| 1 | `EXPLAIN (FORMAT JSON)` returns an array of plan nodes with `name`, `children`, and `extra_info`. | `EXPLAIN (FORMAT JSON) SELECT count(*) FROM t WHERE id < 10` returned `[{"name":"UNGROUPED_AGGREGATE",...}]` | Probed |
| 2 | `EXPLAIN (FORMAT JSON)` has no actual rows, timings, row-group counts, `io`, or `system` sections. | Same output; `intermediate_rows` absent | Probed |
| 3 | `EXPLAIN ANALYZE (FORMAT JSON)` returns one object with `io`, `operator`, `query`, `system`, `optimizer`, `parser`, `physical_planner`, and `planner`. | Probe output; key set printed | Probed |
| 4 | Analyzed operator nodes use `type`, not `name`, and carry `intermediate_rows`, `intermediate_size_bytes`, and `timing`. | `TABLE_SCAN` node in the probe | Probed |
| 5 | Scan nodes add `rows_scanned`, `row_groups_scanned`, and `total_row_groups_to_scan` only in the analyzed shape. | `TABLE_SCAN` node; plan-only scan lacks them | Probed |
| 6 | The analyzed tree is wrapped in `RESULT_COLLECTOR` and `EXPLAIN_ANALYZE`. | Root child is `EXPLAIN_ANALYZE`; its child is the plan root | Probed |
| 7 | `EXPLAIN ANALYZE` ignores `-json` and prints a text profile. | `duckdb -json -c "EXPLAIN ANALYZE SELECT 42"` printed `Total Time:` and did not parse as JSON | Probed |
| 8 | `legacy_metrics_format = true` makes `EXPLAIN ANALYZE (FORMAT JSON)` return a flat object with `latency`, `children`, and `operator_type`, not the grouped shape. | Probe with the setting on; `operator` key absent | Probed |
| 9 | `legacy_metrics_format` is deprecated and emits a warning. | Setting description in `src/include/duckdb/main/settings.hpp`; probe stderr | Probed |
| 10 | Operator timings are exclusive and their sum is close to `query.cpu_time`. | Parallel aggregate probe: sum of timings 0.05118432 s, `query.cpu_time` 0.05118432 s, `query.total_time` 0.055123027 s | Probed |
| 11 | On a parallel query, `query.cpu_time` can exceed wall time. | Same probe; CPU time includes overlapping threads | Probed |
| 12 | `system.peak_temp_dir_size > 0` proves a spill. | `memory_limit=100MB`, `temp_directory`, 2M-row `ORDER BY` returned `peak_temp_dir_size=98271232` | Probed |
| 13 | `system.peak_buffer_memory` tracks the buffer-manager peak, not the total process RSS. | Probe returned 100040704 at a 100 MB limit | Probed |
| 14 | `tracked_metrics` restricts `json` output but `query_tree` keeps a fixed metric set. | `tracked_metrics=['query.total_time']` with `json` produced only `query.total_time`; `query_tree` still showed the operator tree | Probed |
| 15 | The profiler output file extension must match the format, or be `.txt`. | Setting `query_tree` with a `.json` path raised a Parser Error | Probed |
| 16 | A cross product can have no `Estimated Cardinality` in `extra_info`. | `EXPLAIN (FORMAT JSON) SELECT count(*) FROM a, b` returned `CROSS_PRODUCT` with empty `extra_info` | Probed |
| 17 | `EXPLAIN ANALYZE` runs DML. | Existing probe: `EXPLAIN ANALYZE INSERT` inserted 3 rows | Probed |
| 18 | A metadata-only `count(*)`/`min`/`max` can produce `COLUMN_DATA_SCAN` and no profile tree. | `EXPLAIN ANALYZE (FORMAT JSON) SELECT count(*) FROM 'sorted.parquet'` returned `{"result":"error"}` while the query returned 100000 | Probed |
| 19 | `{"result":"error"}` means no profiler root, not query failure. | Same probe; successful DDL and metadata-only aggregates produce it | Probed |
| 20 | `rows_scanned` is scan-reported, not a portable emitted-row count. A Parquet scan with pushed filters can report `0`; a base-table scan can report rows examined. | A 10/10 row-group Parquet scan with no matches reported `rows_scanned: 0`; a base-table scan reported `20000000` while `intermediate_rows` was `0` | Probed |
| 21 | The row-group denominator is after file-list pruning. | Hive filter: `Scanning Files: 1/6`, `Row Groups Scanned: 1/1` | Probed |
| 22 | `Data Read` and `Data Written` are query-wide FileSystem bytes and include spill. | Read-only 100 MB-limit sort: `Data Read: 68.3 MB`, `Data Written: 62.2 MB`, `peak_temp_dir_size: 60817408` | Probed |
| 23 | Text timings can print `0µs` for a real multi-millisecond operator. | JSON `timing: 0.006676964` printed as `0µs` in the text box | Probed |
| 24 | `explain_output='all'` concatenates three JSON documents. | Logical, optimized, physical arrays in one output; `json.load` fails | Probed |
| 25 | `profiling_output` is last-statement-wins; `EXPLAIN ANALYZE` ignores it. | Two SELECTs wrote one file with the second query; `EXPLAIN ANALYZE` created no profile file | Probed |
| 26 | `operator.cpu_time` is advertised but not emitted. | `duckdb_available_metrics()` lists it; tracking only it produces anonymous `{}` nodes | Probed |
| 27 | `ROW_GROUP_SIZE` is rounded up to a multiple of 2,048; `FILE_SIZE_BYTES` overshoots. | 2,049 -> 4,096; 3,000 -> 4,096; 100 KB target produced 124,230 and 77,551 bytes | Probed |

## Design evidence

### Why a script

The skill already had the operator map and the three diagnoses. It did not have a deterministic way to answer four questions on a new plan:

1. Which operator owns the time?
2. Which operator has the largest estimate gap?
3. Did the scan prune row groups?
4. Did the query spill?

A script is the right home because the step is repeated, fragile (two JSON shapes), and the output should be ranked rather than read raw. It returns a nonzero exit code for a high or critical finding, so a maintainer can gate a change.

### What the linter computes

| Signal | Rule | Why |
| --- | --- | --- |
| Cross product | `CROSS_PRODUCT` with at least 10,000 estimated or child rows | Missing join key is the common expensive defect |
| Nested loop | `NESTED_LOOP_JOIN` or `BLOCKWISE_NL_JOIN` with at least 100,000 rows | Large non-equi joins are usually rewritable |
| Full scan | Row groups scanned equal the total and the total is at least 2 | A selective filter should prune |
| Metadata only | `COLUMN_DATA_SCAN` or `{"result":"error"}` and no operator tree | The query was answered from metadata, not a scan |
| Estimate gap | Actual and estimate differ by at least 100×, actual at least 1,000 | Statistics, skew, or an unusual predicate |
| Join multiplication | Join output at least 10× the largest input and at least 10,000 rows | Many-to-many or missing key |
| Blocking operator | A blocking node holds at least 1,000,000 rows | Memory pressure |
| Spill | `system.peak_temp_dir_size > 0` | The query exceeded the memory budget |
| Time hotspot | One operator holds at least 50% of measured time and at least 1,000,000 rows | Amdahl bound |
| I/O heavy | `io.total_bytes_read >= 1 GB` | Projection or pruning problem |

The thresholds are heuristics. They are labeled as such in the output. The linter reports evidence and a proof command, not a verdict about correctness.

### Self-test

The self-test builds a deterministic database and four plan cases, plus a write-guard check:

| Case | Query | Expected |
| --- | --- | --- |
| Cross join | `SELECT count(*) FROM a, b` | `cross_product` |
| Non-sargable Parquet filter | `WHERE CAST(id AS VARCHAR) LIKE '1%'` | `full_scan` |
| Sargable point lookup | `WHERE id = 99999` | no `full_scan` |
| Metadata-only count | `SELECT count(*)` without a filter | `no_profile`, not a failure |

The reference run passes all four plan cases and the guard check. The self-test is also wired into `scripts/probe.py`.

## Existing skill audit

| Claim or omission | Verdict | Fix |
| --- | --- | --- |
| The skill described plan operators but not how to rank them. | Thin | Added the case file, cost model, and failure-class catalog in `references/diagnosis.md`. |
| The JSON section did not distinguish plan-only and analyzed shapes. | Wrong by omission | Added the shape table and field list in `references/plans.md`. |
| The metrics section called operator timings cumulative. | Wrong | Timings are exclusive and sum to `query.cpu_time`; `query.total_time` includes planning. |
| The skill had no spill signal. | Thin | Added `system.peak_temp_dir_size` and a spill workflow. |
| The skill had no automated evidence collector. | Gap | Added `scripts/plan_lint.py` with a self-test. |
| The skill did not say `EXPLAIN ANALYZE (FORMAT JSON)` returns one object. | Thin | Added the shape and wrapper notes. |
| The skill did not name `legacy_metrics_format`. | Thin | Added the deprecated flat shape and a warning not to mix parsers. |

## Gaps worth adding

| Rank | Gap | Why an agent needs it | Home |
| --- | --- | --- | --- |
| 1 | Ranked findings with evidence | A raw plan has too many nodes; the agent needs one cause | `scripts/plan_lint.py` |
| 2 | Metadata-only plans and no profile | `count(*)`, `min`, and `max` can look like a failed or empty profile | `references/plans.md`; `scripts/plan_lint.py` |
| 3 | Cost model with units | The agent can compare a join rewrite with a file rewrite | `references/diagnosis.md` |
| 4 | Spill signal | OOM advice was setting-first, not shape-first | `references/plans.md`; `SKILL.md` |
| 5 | Plan-only versus analyzed shape | A parser written for one shape fails on the other | `references/plans.md` |
| 6 | Stop rules and handoffs | The agent over-optimizes or restates another skill | `references/diagnosis.md` |
| 7 | Plan regression workflow | A changed plan is not a changed query | `references/diagnosis.md` |

## Traps and contradictions

| Trap | What happens | Correct move | Evidence |
| --- | --- | --- | --- |
| Treating the analyzed JSON as an array | `json.loads` returns an object; indexing by `[0]` fails | Branch on `operator` in the parsed object | Probed |
| Treating the plan-only JSON as an object | It is an array of roots | Branch on `list` | Probed |
| Reading `Estimated Cardinality` as an int | It is a string, and can be absent on a cross product | Parse with a number helper and handle `None` | Probed |
| Summing operator times to predict wall time | Operator times are CPU-side and parallel threads overlap | Compare shares; use `query.total_time` for wall time | Probed |
| Using `-json` with `EXPLAIN ANALYZE` | The CLI prints a text profile, not JSON | Use `EXPLAIN ANALYZE (FORMAT JSON)` | Probed |
| Leaving `legacy_metrics_format` on | The JSON shape changes completely | Set it off; fail the parser with a clear message | Probed |
| Diagnosing pruning from `EXPLAIN` | Plan-only has no row-group scan counts | Use `EXPLAIN ANALYZE` on a safe query | Probed |
| Running `EXPLAIN ANALYZE` on a write | The write happens | Use plain `EXPLAIN` unless the write is intended | Existing probe |
| Reading `{"result":"error"}` as query failure | The query may have succeeded; only the profiler root is missing | Check the result separately; measure a real scan | Probed |
| Using `count(*)` as a scan benchmark | The plan can be metadata-only and instant | Add a row filter or select a data column | Probed |
| Reading `rows_scanned` as a portable emitted-row count | Base-table and Parquet scans disagree; a Parquet scan can report 0 while a base table reports rows examined | Use `intermediate_rows` for emitted rows; use row groups and Data Read for scan work | Probed |
| Reading `Row Groups Scanned: 1/1` as healthy | The denominator is after file pruning | Pair it with `Scanning Files` and file metadata | Probed |
| Treating Data Read as scan bytes | It includes footers and spill | If temp > 0, treat it as an upper bound | Probed |
| Ranking from text timings | A real multi-millisecond operator can print `0µs` | Use `(FORMAT JSON)` | Probed |
| Parsing `explain_output='all'` as one JSON document | Three documents concatenate | Force `physical_only` or parse stream values | Probed |
| Raising `memory_limit` first | A bad join still explodes, with a larger bill | Reduce rows before the blocking operator | Design rule |
| Using `union_by_name` to hide drift | The read succeeds with NULLs; the producer is still broken | Quarantine or backfill first | `duckdb-files` |

## Probe log

```text
$ duckdb -no-agent -json -c "CREATE TABLE t AS SELECT range AS id FROM range(1000); EXPLAIN (FORMAT JSON) SELECT count(*) FROM t WHERE id < 10;"
[{"name":"UNGROUPED_AGGREGATE",...,"extra_info":{"Aggregates":"count_star()","Estimated Cardinality":"1"}}]
# array, no intermediate_rows

$ duckdb -no-agent -json -c "CREATE TABLE t AS SELECT range AS id FROM range(1000); EXPLAIN ANALYZE (FORMAT JSON) SELECT count(*) FROM t WHERE id < 10;"
{"io":{...},"operator":[{"type":"RESULT_COLLECTOR",...}],"query":{...},"system":{...},...}
# object, TABLE_SCAN has rows_scanned and intermediate_rows=10

$ duckdb -no-agent -json -c "EXPLAIN ANALYZE SELECT 42;"
# box-drawing profile with "Total Time:", not JSON

$ duckdb -no-agent -c "SET legacy_metrics_format=true; EXPLAIN ANALYZE (FORMAT JSON) SELECT 42;"
WARNING: The 'legacy_metrics_format' setting is deprecated ...
{"latency":...,"children":[...],"operator_type":"RESULT_COLLECTOR"}
# flat legacy shape

$ duckdb -no-agent -json -c "SET memory_limit='100MB'; SET temp_directory='spill'; SET threads=2; EXPLAIN ANALYZE (FORMAT JSON) SELECT range i, repeat('x',100) s FROM range(2000000) ORDER BY i DESC;"
{"system":{"peak_temp_dir_size":98271232,...},"operator":[{"type":"ORDER_BY",...}],...}

$ duckdb -no-agent -json -c "SET threads=4; EXPLAIN ANALYZE (FORMAT JSON) SELECT k, count(*) FROM (SELECT range i, range%100 k FROM range(5000000)) GROUP BY k ORDER BY k;"
query.cpu_time=0.05118432000000002
sum(operator.timing)=0.051184320000000026
query.total_time=0.055123027

$ duckdb -no-agent -json -c "EXPLAIN ANALYZE (FORMAT JSON) SELECT count(*) FROM 'sorted.parquet';"
{"result":"error"}
# query itself returned 100000; no profiler root

$ duckdb -no-agent -c "EXPLAIN ANALYZE SELECT count(*) FROM 'sorted.parquet' WHERE id = 99999;"
# boxed Summary; Table Scan Row Groups Scanned: 1 / 10; rows_scanned is 1

$ duckdb -no-agent -c "SET explain_output='all'; EXPLAIN (FORMAT JSON) SELECT ...;"
# three JSON documents concatenated; json.load fails

$ python3 skills/duckdb-profile/scripts/plan_lint.py --self-test
PASS write guard: one statement, no second statement from --set
PASS cross join: ['cross_product']
PASS non-sargable filter: ['full_scan']
PASS sargable filter: []
PASS metadata-only count: ['no_profile']
```

## What not to add

- A separate profiling skill. `duckdb-profile` owns the diagnosis and has room in its references.
- A general plan visualizer. `EXPLAIN (FORMAT WEB)`, `FORMAT HTML`, and `FORMAT MERMAID` already exist.
- A metrics database or dashboard. The one-shot linter and the profile file cover the repeated case.
- A hard threshold for "good" row-group size. Row width and scan pattern change the answer; keep the range and the formula.
- A parser for the legacy metrics shape. It is deprecated; fail with a clear message instead.

## Open questions

- Does `EXPLAIN ANALYZE (FORMAT JSON)` include the same `system.peak_temp_dir_size` on all platforms? It is the buffer-manager metric, not process RSS. A spill test on macOS and Windows would settle the field values.
- Does a metadata-only `count(*)` always return `{"result":"error"}`, or only when no operator is in the profiling whitelist? The source suggests the latter; a fixture with `tracked_metrics` variations would settle it.
- Does `ROW_GROUPS_PER_FILE` remain exact when combined with `PARTITION_BY`? The probe checked an unpartitioned write. A partitioned test would settle the interaction.
