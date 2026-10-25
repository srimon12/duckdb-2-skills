# Batch ingest reference

Read this when the user wants a repeatable load, not a one-file preview or a simple format conversion. The driver is `duckdb-files/SKILL.md`.

## Contract

Agree on six things before writing output.

| Item | Example | Why |
| --- | --- | --- |
| Input | `orders.csv`, `events/*.jsonl` | The path and the glob define the row set. |
| Target | `out/`, `s3://bucket/orders/` | A directory for partitioned output, a file for one output. |
| Partition keys | `year`, `month` | Low-cardinality filter columns. |
| Key types | `order_id BIGINT`, `ordered_at DATE`, `amount DECIMAL(18,2)` | Type drift changes results. |
| Nullable columns | `customer` | An empty optional value is `NULL`, not a bad row. |
| Bad-row policy | Quarantine to `quarantine.parquet`; parser rejects to `rejects.parquet` | Never drop or null a bad value silently. |

If the user only wants a preview, use the `Preview` or `Convert` section in `duckdb-files/SKILL.md`. Do not build a pipeline for a one-off `LIMIT 20`.

## 1. Inspect

```sql
FROM sniff_csv('orders.csv');

DESCRIBE FROM read_csv('orders.csv');
FROM read_csv('orders.csv') LIMIT 20;
```

`sniff_csv` returns a `Prompt` with the delimiter, quote, header, and inferred columns. Treat the inferred types as a hint. A mixed date column often becomes `VARCHAR`, and a column with one bad value can become `VARCHAR` or fail. Set the types explicitly.

For JSON, inspect one object and the detected schema.

```sql
FROM read_json('events.jsonl', format = 'newline_delimited') LIMIT 5;
DESCRIBE FROM read_json('events.jsonl', format = 'newline_delimited');
```

For Parquet, use `DESCRIBE` and `parquet_file_metadata`. Do not infer the schema from one file in a glob.

## 2. Read raw

Read CSV as text first. This keeps the original bytes available for quarantine and makes every cast explicit.

```sql
CREATE OR REPLACE TEMP TABLE raw AS
FROM read_csv(
    'orders.csv',
    all_varchar = true,
    header = true
);
```

`all_varchar` is a `read_csv` option. It is not available on `read_json`. For JSONL, use `read_json` with explicit `columns` when the file is clean. When you need one row per raw line for quarantine, use a delimiter that does not occur in the line.

```sql
FROM read_csv(
    'events.jsonl',
    delim = chr(1),
    header = false,
    columns = {'line': 'VARCHAR'}
);
```

Do not use `ignore_errors = true` as a repair. On JSONL it turns a malformed line into a row of `NULL`s. On CSV it skips the row. Both hide the failure.

Choose the reject path before step 3. If the parser structure is clean, read as text with `all_varchar` and cast. If the reader must parse typed columns, use `store_rejects`; parser rejects never enter `typed`. Do not switch paths after `bad` and `good` are built.

## 3. Type explicitly

```sql
CREATE OR REPLACE TEMP TABLE typed AS
SELECT
    TRY_CAST(trim(order_id) AS BIGINT) AS order_id,
    COALESCE(
        TRY_CAST(trim(ordered_at) AS DATE),
        TRY_STRPTIME(trim(ordered_at), '%d/%m/%Y')::DATE
    ) AS ordered_at,
    NULLIF(trim(customer), '') AS customer,
    TRY_CAST(
        replace(replace(replace(trim(amount), '$', ''), '€', ''), ',', '')
        AS DECIMAL(18,2)
    ) AS amount,
    TRY_CAST(trim(payload) AS JSON) AS payload,
    trim(ordered_at) AS raw_ordered_at,
    trim(amount) AS raw_amount,
    trim(payload) AS raw_payload
FROM raw;
```

`TRY_CAST` returns `NULL` for a bad value. Keep the raw value beside the cast so the quarantine can explain what failed.

`TRY_STRPTIME` returns `TIMESTAMP`. Cast it to `DATE` when the target column is a date.

`NULLIF(trim(customer), '')` turns an optional blank into `NULL`. Do not quarantine an optional blank unless the contract says the column is required.

`replace(..., ',', '')` removes thousands separators. It also removes a comma from a decimal locale that uses a comma as the decimal point. Decide the locale before the load.

Common recipes:

| Target | Expression |
| --- | --- |
| Integer | `TRY_CAST(trim(raw) AS BIGINT)` |
| Decimal money | `TRY_CAST(replace(replace(replace(trim(raw), '$', ''), '€', ''), ',', '') AS DECIMAL(18,2))` |
| ISO date | `TRY_CAST(trim(raw) AS DATE)` |
| Day-first date | `TRY_STRPTIME(trim(raw), '%d/%m/%Y')::DATE` |
| Timestamp | `TRY_CAST(trim(raw) AS TIMESTAMP)` or `TRY_STRPTIME(trim(raw), '%Y-%m-%d %H:%M:%S')` |
| Boolean | `CASE lower(trim(raw)) WHEN 'true' THEN true WHEN 'false' THEN false END` |
| JSON | `TRY_CAST(trim(raw) AS JSON)` |

## 4. Gate bad rows

Build one reason per bad row, then split valid and bad.

```sql
CREATE OR REPLACE TEMP TABLE flagged AS
SELECT *,
    nullif(concat_ws('; ',
        CASE WHEN order_id IS NULL THEN 'invalid_order_id' END,
        CASE WHEN ordered_at IS NULL THEN 'invalid_date' END,
        CASE WHEN amount IS NULL THEN 'invalid_amount' END,
        CASE WHEN payload IS NULL THEN 'invalid_payload' END
    ), '') AS reason
FROM typed;

CREATE OR REPLACE TEMP TABLE bad AS
FROM flagged
WHERE reason IS NOT NULL;

CREATE OR REPLACE TEMP TABLE good AS
FROM flagged
WHERE reason IS NULL;
```

A row with two bad columns gets one quarantine row with both reasons. That is the contract. Do not count it twice. A blank optional column is not a bad row; it is `NULL` in the typed row.

### Parser rejects

Parser rejects never enter `typed`. If the reader uses `store_rejects`, they are not in `bad`. Decide the path before step 3. Do not replace `typed` after `bad` and `good` exist; rebuild `flagged`, `bad`, and `good` after the final typed read.

```sql
CREATE OR REPLACE TEMP TABLE typed AS
FROM read_csv(
    'orders.csv',
    columns = {'order_id': 'BIGINT', 'amount': 'DECIMAL(18,2)'},
    store_rejects = true,
    rejects_table = 'rejects'
);

-- Rebuild flagged, bad, and good from this typed table.
SELECT count(*) AS errors,
       count(DISTINCT file_id || ':' || line) AS bad_lines
FROM rejects;
```

One bad line can produce several reject rows. Count distinct `(file_id, line)` for the row count. The rejects table details are in [formats.md](formats.md).

Persist both quarantine tables before the process exits. A temp table disappears with the connection.

```sql
COPY (FROM rejects) TO 'rejects.parquet' (FORMAT parquet);
COPY (FROM bad) TO 'quarantine.parquet' (FORMAT parquet);
```

## 5. Write partitioned Parquet

`PARTITION_BY` takes columns, not expressions. Add the partition columns in the `SELECT`.

```sql
COPY (
    SELECT *,
           year(ordered_at) AS year,
           month(ordered_at) AS month
    FROM good
)
TO 'out'
(
    FORMAT parquet,
    PARTITION_BY (year, month),
    OVERWRITE,
    FILENAME_PATTERN 'part_{i}',
    ROW_GROUP_SIZE 122880,
    COMPRESSION zstd,
    RETURN_FILES
);
```

The CLI result for `RETURN_FILES` is `Count` and `Files` on 2.0.0, in both box and `-json` output. The manual's lowercase `files VARCHAR[]` describes the logical column, not the CLI keys.

`WRITE_PARTITION_COLUMNS` defaults to `false`. The partition columns are stored in the directory names and reconstructed when the reader uses Hive partitioning.

Use 100,000 to 1,000,000 rows per group for a dataset that is read often. The `ROW_GROUP_SIZE` defaults and minimum are in [formats.md](formats.md).

## 6. Rerun and append

| Option | Effect | Use |
| --- | --- | --- |
| No option | Fails when the target directory is not empty. | Safe first write. |
| `OVERWRITE` | Removes the target directory tree on a local filesystem. | Full rebuild. |
| `OVERWRITE_OR_IGNORE` | Overwrites matching paths and leaves partitions from earlier runs that the new run does not write. | Idempotent rerun of the same partition set. |
| `APPEND` | Keeps old files and generates a non-clashing name. | Incremental load. |

`OVERWRITE_OR_IGNORE` is not a full rebuild. On 2.0.0, rerunning a two-month dataset with only one month left the old month in place. Use `OVERWRITE` or remove the root when the partition set can shrink.

Remote filesystems do not support overwrite. Write to a new prefix and swap the reader path, or delete the old prefix with the object-store tool.

`APPEND` can duplicate rows when the same input is loaded twice. Add a load id or a unique key and deduplicate in the query.

## 7. Prove the load

Run the row counts before the process exits. For a fresh read-only check, persist `good`, `bad`, and `rejects` first, then count the written files.

```sql
SELECT count(*) AS kept FROM good;
SELECT count(*) AS rejected FROM bad;
SELECT count(DISTINCT file_id || ':' || line) AS rejected_lines FROM rejects;
SELECT sum(num_rows) AS written
FROM parquet_file_metadata('out/**/*.parquet');
```

The invariant is:

```text
input data rows = good + bad + rejected_lines
written rows = good
```

Count input data rows from the source, not from `read_csv` output. A header and a multiline field are not rows. If `store_rejects` is not used, `rejected_lines` is 0 and the rejects query is omitted.

Then check the schema and the required columns.

```sql
DESCRIBE FROM read_parquet('out/**/*.parquet', hive_partitioning = true);

SELECT count(*) AS bad_dates
FROM read_parquet('out/**/*.parquet', hive_partitioning = true)
WHERE ordered_at IS NULL;
```

`ordered_at IS NULL` can be legitimate only when the source allows a missing date. If the source has a non-null contract, the count must be zero. Do the same for every required key.

For a remote dataset, `parquet_file_metadata` reads footers and avoids a full scan. It is the cheap row-count proof. Use it for the total; `duckdb-files` owns the `parquet_metadata` row-count trap.

## 8. Schema drift

A glob with different schemas fails.

```text
Invalid Input Error: schema mismatch in glob
```

Options:

| Option | Effect | Use |
| --- | --- | --- |
| `union_by_name = true` | Fills missing columns with `NULL`. | Read a dataset with additive schema changes. |
| `schema = MAP {'col': {name: 'col', type: 'VARCHAR', default_value: NULL}}` | Renames, casts, and supplies defaults. The value type must be a STRUCT with `name`, `type`, and `default_value`. | A known contract with a small drift. |
| `bound_schema = {'col': 'VARCHAR'}` with `hive_partitioning = false` | Exact ordered output schema; source columns not listed are dropped. | A known contract with no defaults. |
| Separate reads and `UNION ALL BY NAME` | Keeps each producer visible. | A quarantine or a per-source audit. |

Do not use `union_by_name` to hide a missing required column. Count the `NULL`s first. A simple `MAP {'col': 'VARCHAR'}` is not a valid `schema` value because the map value must be a STRUCT.

## 9. Hand off

For a person, write a small query that reads the partition root and open it with `duckdb -ui`. `duckdb` owns the install caveat. Use `-box` or a notebook when the UI is unavailable. For a plan, use `EXPLAIN (FORMAT WEB)`.

The full reader and writer option matrix is in [formats.md](formats.md). Query-plan diagnosis is in `duckdb-profile`. JSON versus `VARIANT` is in `duckdb-variant`.
