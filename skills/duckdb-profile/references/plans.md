# Plan reading reference

Read this when `EXPLAIN` or `EXPLAIN ANALYZE` is already in hand, or when the skill needs a profiling format or a metric name.

## Statement forms

| Statement | Runs the query | Output | Use |
| --- | --- | --- | --- |
| `EXPLAIN` | No | Physical plan with `~N` estimates | First look. Supported on queries and supported DDL/DML; `EXPLAIN ATTACH` is a parser error. |
| `EXPLAIN ANALYZE` | Yes | Plan with actual rows and timings | Measure the operators after the plan looks plausible. |
| `EXPLAIN (FORMAT JSON)` | No | Array of plan trees with `name`, `children`, `extra_info` | Scripts and diffs. |
| `EXPLAIN ANALYZE (FORMAT JSON)` | Yes | Object with `io`, `operator`, and `optimizer` | Scripted profiles with actuals. |
| `EXPLAIN (FORMAT GRAPHVIZ)` | No | DOT graph | Graph tooling. |
| `EXPLAIN (FORMAT HTML)` | No | HTML tree | A browser without the UI extension. |
| `EXPLAIN (FORMAT MERMAID)` | No | Mermaid flowchart | Docs and reviews. |
| `EXPLAIN (FORMAT WEB)` | No | Opens an HTML plan in the browser | A local visual plan when `-ui` is unavailable. |
| `EXPLAIN (SQL)` | No | Optimized SQL | See `duckdb-sql`; not a plan. |

`EXPLAIN ANALYZE` executes the statement. That includes `INSERT`, `UPDATE`, `DELETE`, and `COPY`. Use plain `EXPLAIN` for write statements unless the write is intended.

`EXPLAIN ANALYZE` ignores `-json` and prints text. `EXPLAIN (FORMAT JSON)` is the JSON path. The JSON tree is not the same as the CLI output format.

## Estimate and actual

`EXPLAIN` prints estimated cardinality with a tilde.

```text
Seq Scan
Table: memory.main.orders
Filters: ordered_at >= DATE '2024-01-01'
~20,000 rows
```

`EXPLAIN ANALYZE` prints actual rows and elapsed time.

```text
Table Scan
Filters: ordered_at >= DATE '2024-01-01'
Row Groups Scanned: 1 / 10
1,000 rows
```

Compare the two per operator, not just at the root. A scan estimate of 20,000 and an actual of 1,000 is a statistics gap. A join estimate of 1,000 and an actual of 4,000,000 is a cardinality explosion. The second is the expensive one.

## Operator map

| Node | What it does | Red flag | First move |
| --- | --- | --- | --- |
| `Seq Scan` / `Table Scan` | Reads a base table. | `Filters` empty when the query has a `WHERE`, or `Row Groups Scanned` equals the total. | Check pushdown and file order. |
| `Parquet Scan` / `PARQUET_SCAN` | Reads Parquet files. | `Total Files Read` is larger than the partition count, or `Row Groups Scanned` is all. | Check the path, partition filter, and row-group statistics. |
| `Projection` | Selects and computes columns. | Huge row count before a filter. | Move the filter closer to the scan. |
| `Filter` | Applies a predicate after a scan. | The same predicate also appears in the scan. | Push the predicate into the scan or rewrite it. |
| `Hash Join` | Equality join. | Probe side has far more rows than the build side. | Shrink the build side or fix the join key. |
| `Cross Product` | No join condition. | Always a red flag on large inputs. | Add the missing predicate. |
| `Piecewise Merge Join` | Range or inequality join. | Large inputs with a wide range. | Add an equality key or pre-aggregate. |
| `Nested Loop Join` / `Blockwise NL Join` | Nested-loop join. | Large outer input. | Look for an equality rewrite. |
| `Hash Group By` / `Perfect Hash Group By` | Aggregation. | Intermediate rows far above output rows. | Pre-filter or reduce the grouping key. |
| `Order By` | Sort. | Large intermediate row count. | Filter before sorting, or use a `TOP N` shape. |
| `Window` | Window function. | Large partition buffers. | Reduce the partition width or pre-aggregate. |
| `UNNEST` | Expands a list. | Output rows far above input rows. | Check list cardinality before the unnest. |
| `Delim Join` | Delimiter join for `DISTINCT` or `GROUP BY` pushdown. | Not a problem by itself. | Read its child, not the join name. |
| `Top N` | Sort with a limit. | Large input. | Filter before the sort. |
| `Streaming Limit` | Limit that stops downstream work. | Not a problem by itself. | Verify the input is not a blocking join. |

## Reading a plan

1. Start at the root and read down to the scans.
2. Find the operator with the largest gap between estimated and actual rows.
3. Check the scan filters and row groups before touching `memory_limit`.
4. Check join sides when the row count grows at a join.
5. Check the row count before a blocking operator when memory is the problem.
6. Change one thing, then rerun `EXPLAIN ANALYZE`.

The root row count is the result size, not the work. A query that returns 10 rows can scan a billion.

## Pushdown

DuckDB pushes filters into scans when the predicate references a bare column and the file format has statistics.

```sql
-- Prunes row groups on a sorted Parquet file.
WHERE ordered_at >= DATE '2024-01-01'
  AND ordered_at < DATE '2024-02-01'

-- Reads every row group because the column is wrapped.
WHERE CAST(ordered_at AS VARCHAR) LIKE '2024-01%'
```

The same rule applies to partition columns. A filter on `year = 2024` prunes directories when `year` is a Hive partition. A filter on `year(ordered_at) = 2024` does not.

Projection pushdown is separate. `SELECT *` reads every column. Select only the columns the result needs, especially on remote Parquet.

## Joins

Hash joins build on the right operand and probe from the left. The build side should be the smaller, more selective side. If the plan builds a billion-row side, the join key or the filter order is wrong.

A join that multiplies rows is not fixed by a `LIMIT`. The limit is applied after the join. Pre-aggregate the fact table, filter before the join, or join on a key with a known cardinality.

A `Cross Product` is sometimes deliberate. If it is, say so in the query with `ON true` or a comment, and keep the inputs tiny. A missing join key is the common case.

## Memory and spill

Blocking operators buffer their input. The main ones are `GROUP BY`, joins, `ORDER BY`, and window functions. `LIMIT` after a blocking operator does not reduce the buffer.

```sql
SET memory_limit = '4GB';
SET temp_directory = '/fast/disk/duckdb.tmp';
SET max_temp_directory_size = '50GB';
SET preserve_insertion_order = false;
SET threads = 4;
```

`memory_limit` is a ceiling. The default is 80% of system RAM. Lowering it can help when another process shares the machine, but it can also force spills. `temp_directory` should be local SSD, not a network mount. `max_temp_directory_size` is a hard cap, not a target.

`preserve_insertion_order = false` lets DuckDB reorder rows without an `ORDER BY`. It can reduce memory for large loads and exports. Do not use it when the consumer depends on row order.

## Profiling settings

```sql
SET enable_profiling = 'query_tree';
SET profiling_output = '/tmp/query.txt';
SET profiling_coverage = 'SELECT';
```

`enable_profiling` is mandatory. Formats are `query_tree`, `json`, `query_tree_optimizer`, and `no_output`. The file extension must match the format, or be `.txt`.

`profiling_coverage = 'SELECT'` profiles only `SELECT`. Use `'ALL'` for `INSERT`, `ATTACH`, and other statements. This can produce a lot of output.

```sql
SET enable_profiling = 'json';
SET profiling_output = '/tmp/query.json';
SET tracked_metrics = ['query.*', 'operator.*'];
```

`tracked_metrics` accepts glob patterns. It affects `json` and `no_output`. `query_tree` and `query_tree_optimizer` use a fixed metric set. `profiling_mode` is deprecated and has no effect in 2.0.

The table-function form is easier to keep in one statement.

```sql
CALL enable_profiling(
    format := 'json',
    save_location := '/tmp/query.json',
    coverage := 'select',
    metrics := ['query.total_time', 'operator.timing']
);
CALL disable_profiling();
```

## Metrics

```sql
SELECT metric_name, metric_type, unit
FROM duckdb_available_metrics()
ORDER BY metric_name;
```

Useful metrics:

| Metric | Unit | Use |
| --- | --- | --- |
| `query.total_time` | seconds | End-to-end query time. |
| `query.total_intermediate_size_bytes` | bytes | Total intermediate data produced. |
| `operator.timing` | seconds | Time in one operator. |
| `operator.intermediate_rows` | rows | Row count between operators. |
| `operator.intermediate_size_bytes` | bytes | Bytes between operators. |
| `operator.rows_scanned` | rows | Rows read by a scan. |
| `operator.row_groups_scanned` | row groups | Row groups read by a scan. |
| `operator.total_row_groups_to_scan` | row groups | Row groups available to the scan. |
| `operator.extra_info` | map | Operator-specific details. |

Per-operator times are cumulative and overlap across threads. Their sum can exceed the query time. Do not add them to estimate wall time.

## JSON plan

`EXPLAIN (FORMAT JSON)` returns a top-level array. Each element is a root plan node.

```sql
EXPLAIN (FORMAT JSON)
SELECT ...;
```

```json
[
  {
    "name": "PROJECTION",
    "children": [
      {
        "name": "PARQUET_SCAN",
        "children": [],
        "extra_info": {
          "Filters": "id = 99999",
          "Estimated Cardinality": "1"
        }
      }
    ],
    "extra_info": {
      "Projections": "id",
      "Estimated Cardinality": "1"
    }
  }
]
```

`EXPLAIN ANALYZE (FORMAT JSON)` returns one object, not an array. The object has `io`, an `operator` tree, and optimizer timings. Operator nodes use `type`, not `name`, and carry the actual fields at the top level.

```json
{
  "io": {"total_bytes_read": 47700, "total_bytes_written": 0},
  "operator": [
    {
      "type": "TABLE_SCAN",
      "children": [],
      "extra_info": {"Filters": "id = 99999"},
      "intermediate_rows": 1,
      "row_groups_scanned": 1,
      "total_row_groups_to_scan": 10,
      "timing": 0.0003
    }
  ]
}
```

The estimate format and the actual format are different. Do not feed one parser to both. Node names are stable enough for a diagnostic, not a public API. `extra_info` keys vary by operator and version.

## Web and UI

`EXPLAIN (FORMAT WEB)` writes a temporary HTML file and opens it. It works without the `ui` extension. `EXPLAIN ANALYZE (FORMAT WEB)` includes actual rows and timings.

`duckdb -ui` starts the local UI. `duckdb` owns the flag and the 2.0.0 extension caveat. Use `EXPLAIN (FORMAT WEB)` for plans when the UI is unavailable or the network is restricted.

## Before changing a setting

Ask which operator is expensive and why. A setting can hide a bad plan. A rewrite usually beats a knob.

| Observation | Usually means | Change |
| --- | --- | --- |
| Scan reads all row groups | Filter is not sargable or data is unsorted | Rewrite the predicate or rewrite the file layout |
| `Cross Product` on large inputs | Missing join key | Add the predicate |
| Join output is much larger than both inputs | Many-to-many join | Pre-aggregate or deduplicate |
| Huge intermediate rows before `ORDER BY` | Sorting too much | Filter or aggregate first |
| Spill with a small result | Blocking operator on a large input | Rewrite the shape before raising `memory_limit` |
| Estimate is far below actual | Stale table statistics | `ANALYZE` |
