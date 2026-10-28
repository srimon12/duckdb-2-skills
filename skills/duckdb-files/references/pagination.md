# Stable pagination reference

Read this when an API, export, or UI pages through Parquet or a large result and every page must contain each row exactly once.

## Contract

```text
Inputs:      one file or one query, page size, page index
Outputs:     disjoint pages, in a stable order
Invariant:   sum(page rows) = source rows; no duplicate ids; no missing ids
Proof:       page count plus a distinct-key count on the union of pages
```

A row count is not a pagination proof. A broken page sequence can return the right total and still duplicate and drop rows.

## The trap

`LIMIT` and `OFFSET` preserve order by default, but `preserve_insertion_order = false` lets DuckDB reorder rows before the sink. With more than one thread, pages from `LIMIT/OFFSET` can overlap and skip.

A 30,000-row Parquet file with six 5,000-row groups, page size 10, `threads = 4`, and `preserve_insertion_order = false` produced 3,000 pages with a total of 30,000 rows but only 20,870 distinct ids. 9,130 ids were duplicated and 9,130 were missing.

## Stable page by file row number

For a single Parquet file, page on `file_row_number`:

```sql
SELECT id
FROM read_parquet('data.parquet', file_row_number => true)
WHERE file_row_number >= 40 AND file_row_number < 50;
```

`file_row_number` is the row index within the file, starting at zero. Use the same range in every page. Get the file row count from `parquet_file_metadata('data.parquet')`.

The index resets for each file. A predicate `file_row_number < 10` over three 10,000-row files returns 30 rows, not 10. Add a filename:

```sql
WHERE filename = 'data.parquet'
  AND file_row_number >= 40 AND file_row_number < 50;
```

For a dataset, page by `(filename, file_row_number)` and sort the file list deterministically.

## Stable page by key

If the result has a unique, immutable key, page on it:

```sql
SELECT id, payload
FROM events
WHERE id > :last_id
ORDER BY id
LIMIT :page_size;
```

Keep the last key, not the offset. A key page survives inserts and deletes better than an offset page. It still needs a unique key and a deterministic tie-breaker.

For a one-shot export, stream the query once instead of paging. For a concurrent table, page inside one transaction or snapshot.

## Proof

Materialize the union of the page rows, then count:

```sql
CREATE TEMP TABLE pages AS
SELECT * FROM page_1
UNION ALL SELECT * FROM page_2;  -- all pages

SELECT count(*) AS rows, count(DISTINCT id) AS distinct_ids
FROM pages;
```

`rows` must equal the source count and `distinct_ids` must equal `rows`. Compare a hash of the ordered ids as a second check. Do not accept a page run that only checks `count(*)` per page.

## References

- https://duckdb.org/docs/2.0/data/parquet/overview.html
- https://duckdb.org/docs/2.0/data/parquet/metadata.html
- https://duckdb.org/docs/2.0/sql/dialect/order_preservation.html
- https://duckdb.org/docs/2.0/sql/query_syntax/limit.html
