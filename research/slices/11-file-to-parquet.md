# File to checked Parquet

Sources: the 2.0 snapshots for [CSV](https://duckdb.org/docs/2.0/data/csv/overview.html), [JSON](https://duckdb.org/docs/2.0/data/json/loading_json.html), [COPY](https://duckdb.org/docs/2.0/sql/statements/copy.html), [partitioned writes](https://duckdb.org/docs/2.0/data/partitioning/partitioned_writes.html), [Parquet metadata](https://duckdb.org/docs/2.0/data/parquet/metadata.html), and [file format performance](https://duckdb.org/docs/2.0/guides/performance/file_formats.html). Probes ran on DuckDB 2.0.0 `d54cbbe3df`.

## Why this is a reference, not a new skill

`duckdb-files` already owns reader dispatch, `COPY` options, partition writes, rejected rows, and Parquet metadata. The eval table already assigns "Convert CSV to zstd parquet" and "Write parquet partitioned by month" to `duckdb-files`. A separate ingest skill would take those triggers and force a rewrite of the owner.

The new value is a contract and a proof. That belongs in `duckdb-files/references/ingest.md` and in a task case. It does not need a second folder.

## The state machine

```text
raw text
  -> typed rows with TRY_CAST
  -> flagged rows with one reason list
  -> good rows + bad rows
  -> partitioned Parquet + quarantine.parquet
  -> input = kept + distinct rejected lines
  -> footer rows = kept
```

The split is the important part. A validation step that drops rows or turns bad values into `NULL` cannot satisfy the proof.

## Probe facts

### Rejects are one row per error

A CSV line with two bad columns produces two rows in the rejects table.

```text
$ read_csv('bad.csv', columns={'id':'BIGINT','amount':'DECIMAL(18,2)','name':'VARCHAR'},
           store_rejects=true, rejects_table='rejects')
$ SELECT count(*), count(DISTINCT file_id || ':' || line) FROM rejects;
2, 1
```

The row count must use distinct `(file_id, line)`. Counting `rejects` directly double-counts the line.

The rejects table is temporary. Persist it with `COPY` before the process exits.

### JSON `ignore_errors` is not a repair

A three-line JSONL file with one bad line returns three rows under `ignore_errors=true`. The bad line becomes a row with `NULL` fields. It does not disappear and it does not raise.

Use `TRY_CAST(raw AS JSON)` on a raw text line and quarantine the `NULL`. Do not use `ignore_errors` as the only gate.

### Partition writes and overwrite

A partitioned write returns `Count` and `Files` in the CLI on 2.0.0.

```text
COPY (...) TO 'out' (FORMAT parquet, PARTITION_BY (year, month), RETURN_FILES);
Count=6, Files=[...]
```

A second write without an overwrite option fails.

```text
IO Error: Directory "out" is not empty
```

`OVERWRITE` removes the target tree and writes the new partition set. `OVERWRITE_OR_IGNORE` does not remove stale partitions. A two-month dataset rerun with only one month still reads two months. Use `OVERWRITE` for a full rebuild, or remove the root first.

The partitioned-writes page says both options remove existing directories. The COPY statement table says `OVERWRITE` removes files and `OVERWRITE_OR_IGNORE` only permits overwriting. The probe agrees with the COPY table, so the skill follows the probe.

`APPEND` keeps old files and generates a non-clashing name. It can duplicate rows if the same input is loaded twice.

### Row groups

`ROW_GROUP_SIZE` defaults to 122,880. A request is rounded up to a multiple of 2,048, with a minimum of 2,048. The final group can be smaller. A 10,000-row file written with `ROW_GROUP_SIZE 1000` has four groups of 2,048 and one group of 1,808. A request for 10,000 becomes 10,240, so a 100,000-row file has nine full groups and a final smaller group.

Healthy Parquet row groups are 100,000 to 1,000,000 rows. Healthy files are roughly 100 MB to 10 GB. Tiny groups and tiny files cost more in metadata and scheduling than they save.

### Proof

`parquet_file_metadata` reads the footer and returns one row per file. Sum `num_rows` for the written total. Do not sum `parquet_metadata.row_group_num_rows`; it repeats once per column.

## The task case

`evals/ingest` generates 60,000 orders with mixed ISO and day-first dates, currency symbols, empty customers, and nested JSON. The deterministic fixture has 55,913 valid rows and 4,087 quarantined rows.

The prompt asks for `out/` partitioned by year and month and `quarantine.parquet` with a reason. The grader checks 25 conditions.

- Kept row count and distinct order ids.
- Required values not null.
- Amount total.
- `order_id`, `ordered_at`, `amount`, and `payload` types.
- Month partition counts.
- Parquet footer row count.
- Quarantine count, distinct ids, reasons, and no bad rows in the output.
- Input accounting.

The reference run is `bash evals/ingest/run_reference.sh`. It passes 25 of 25.

A first candidate smoke run quarantined the 579 blank optional customers. The count was internally consistent, but it treated an optional blank as a bad value. The contract now has a `Nullable columns` row, and the prompt says an empty customer is allowed. The failure was a real ambiguity in the first draft, not a grader bug.

A final maintainer smoke run on the expanded fixture passed 25 of 25, with 55,913 kept, 4,087 quarantined, and 579 `NULL` customers. No candidate transcript is committed; the reference run is the reproducible artifact.

## Decision

The workflow is a `duckdb-files` reference with a deterministic task case. It is not a new top-level skill. The agent still gets a repeatable contract, and the pack does not duplicate the `duckdb-files` trigger.
