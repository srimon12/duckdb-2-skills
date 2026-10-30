# Vector search reference

Read this when the skill needs the HNSW metric matrix, acceleration rules, persistence behavior, memory model, or pagination contract.

Behavior below was probed on DuckDB 2.0.0 with vss `3685131eac`.

## Create

```sql
LOAD vss;
SET hnsw_enable_experimental_persistence = true;  -- file database, before CREATE
CREATE TABLE items (id INTEGER, emb FLOAT[3]);
CREATE INDEX items_hnsw ON items USING HNSW (emb) WITH (metric = 'cosine');
```

`SET` before `LOAD vss` fails because the setting belongs to the extension:

```text
Catalog Error: Setting with name "hnsw_enable_experimental_persistence" is not in the catalog, but it exists in the vss extension.
```

The flag gates creation only. Reopening a file and querying an existing index works without it. Without `LOAD vss` at all, the index is silently ignored and the query falls back to a scan.

The key must be exactly one `FLOAT[N]` column or expression:

```text
Binder Error: HNSW index key type must be one of: 'FLOAT[N]'
```

`DOUBLE[N]`, `INTEGER[N]`, and variable-length `FLOAT[]` fail. An expression index works when the query repeats the cast:

```sql
CREATE INDEX items_hnsw ON items USING HNSW ((emb::FLOAT[3])) WITH (metric = 'cosine');
```

An empty table can be indexed before the first insert. Inserts, updates, and deletes update the index. Multiple HNSW indexes can exist on one table; the planner picks the index whose metric matches the query function.

## Metric

| Index metric | Query function | Notes |
| --- | --- | --- |
| `l2sq` | `array_distance` | Default. Ordering is L2 squared; the returned value is the square root. |
| `cosine` | `array_cosine_distance` | Normalizes internally. Range `0` to `2`. |
| `ip` | `array_negative_inner_product` | Negative dot product. |

A mismatch is silent. An `l2sq` index with `array_cosine_distance` produces a sequential scan, not an error. Sort by `1.0 - array_cosine_similarity` to get the rewrite to `array_cosine_distance`; a bare `array_cosine_similarity` sort is not accelerated. Check the plan, or `pragma_hnsw_index_info().metric`.

## Query shape

```sql
SELECT id
FROM items
ORDER BY array_cosine_distance(emb, [1, 0, 0]::FLOAT[3])
LIMIT 3;
```

`EXPLAIN` must show `Hnsw Index Scan` in text or `HNSW_INDEX_SCAN` in JSON. The accelerated forms are narrow:

| Shape | Index? |
| --- | --- |
| `ORDER BY <matching distance>(col, literal) LIMIT k` | Yes |
| `ORDER BY alias LIMIT k`, alias is that distance | Yes |
| CTE or subquery that keeps the ORDER BY and LIMIT inside | Yes |
| `WHERE other_col = constant` | Yes, prefiltered |
| `WHERE id IN (1, 2, 3)` | Yes, mark join |
| `ORDER BY dist, id` tie-breaker | No |
| `ORDER BY 1` ordinal | Yes, full scan without top-k pushdown |
| Prepared `$1` vector | Yes, full scan without top-k pushdown |
| `DESC` | No |
| Missing `LIMIT` | No |
| `LIMIT (SELECT k)` | No |
| `WHERE id IN (SELECT ...)` | No |
| `JOIN`, `QUALIFY`, window function | No |
| `min_by(t, <matching distance>(col, literal), k ORDER BY col)` | Yes |

The query vector must be a literal `FLOAT[N]`. A `::DOUBLE[N]` cast or a scalar subquery such as `(SELECT emb FROM items WHERE id = 1)` silently falls back to a sequential scan. A prepared `$1` still uses HNSW, but as a full index scan without top-k pushdown. The same applies to a non-flat vector expression that the planner cannot fold.

`array_distance` on a `FLOAT[3]` column and a bare `[1, 2, 3]` literal binds as `INTEGER[]` and fails. Always cast the literal.

## Filtered search

`hnsw_prefilter` defaults to `true`. A static filter that DuckDB can push into the scan is applied before the graph search, so the index returns up to `k` qualifying rows instead of post-filtering the global top `k`.

```sql
SELECT id
FROM items
WHERE category = 'electronics'
ORDER BY array_distance(emb, [0.5, 0.5, 0.5]::FLOAT[3])
LIMIT 10;
```

The prefilter builds a row-id bitmap with an O(n) scan over the filter columns for each query. A selective filter over a large table is correct but not free.

Do not set `hnsw_prefilter = false` on a selective filter. In a 300k-row probe with 300 matching rows, it returned zero rows for `LIMIT 10`. Keep the default.

Computed predicates and some joins stay as separate operators and are not pushed into the HNSW search. Filter the base table in a CTE or materialize the candidate set when the filter must run first.

## Nulls and zero vectors

NULL vectors are never indexed. A query with `LIMIT k` returns fewer than `k` rows and no error. This breaks a page-size assumption:

```sql
SELECT id FROM items
ORDER BY array_cosine_distance(emb, [1, 0, 0]::FLOAT[3])
LIMIT 10;
```

Do not wrap that `SELECT` in `count(*)` to count the page. The planner can replace the aggregate and return the table count. Count the returned rows in the client.

Zero vectors are accepted. Cosine distance to a zero vector is `nan`, which sorts last but is still returned. Reject NULL, zero, and non-finite vectors before insert.

## Recall and tuning

| Option | Default | Set at | Effect |
| --- | --- | --- | --- |
| `metric` | `l2sq` | `CREATE INDEX` | Must match the distance function. |
| `ef_construction` | 128 | `CREATE INDEX` | Higher builds a better graph, slower. |
| `ef_search` | 64 | `CREATE INDEX` | Stored search width. |
| `hnsw_ef_search` | `NULL` | Session `SET` | Overrides the stored width. |
| `M` | 16 | `CREATE INDEX` | Neighbors per vertex. Also sets `M0 = 2 * M`. |
| `M0` | `2 * M` | `CREATE INDEX` | Base-layer connectivity. |
| `hnsw_prefilter` | `true` | Session `SET` | Filter before the graph search. |

At 50k vectors and 32 dimensions, recall@10 was 0.865 at `ef_search` 8, 0.915 at the default 64, and 0.988 at 128. Raising `ef_search` is the first lever. Change `M` or `ef_construction` only after that.

`hnsw_ef_search` is session-scoped in the source. `BEGIN; SET hnsw_ef_search = 100; ROLLBACK` leaves the value changed; `SET LOCAL` is not implemented.

## Memory and persistence

The index is not buffer-managed and does not count toward `memory_limit`. A 589 MB index built under `memory_limit = '100MB'` without an OOM. Budget roughly 0.6 to 3 KB per vector, plus build headroom.

The index is serialized into the database on every checkpoint and deserialized on first table access after a restart. A large index slows startup and makes checkpoints write the whole index again. Keep the index on a fast local file, not a network mount.

Persistence is still experimental. A crash after committed inserts into an indexed table can leave an index that fails on first open:

```text
INTERNAL Error: Operation requires a flat or constant vector but a non-flat/non-constant vector was encountered
```

`DROP INDEX` and `CREATE INDEX` repair it. Keep a backup before relying on a persistent HNSW index.

Deletes are marked, not removed. `PRAGMA hnsw_compact_index('items_hnsw')` ran clean in 2.0.0 but left capacity, memory, and level statistics unchanged after deleting 90 percent of the rows. Rebuild the index after a large delete; do not rely on compaction.

`EXPORT DATABASE` writes the index with its options. `IMPORT DATABASE` into a file database needs the persistence flag first, or it fails with the create-index error. `COPY FROM DATABASE` copies the index.

A read-only database loads and accelerates the index. Writes fail with the normal read-only error.

## Index lifecycle

| Operation | Effect |
| --- | --- |
| `ALTER TABLE ADD COLUMN` | Index survives. |
| `ALTER COLUMN TYPE` | `Catalog Error: Cannot change the type of this column: an index depends on it!` |
| `DROP TABLE` | Index is dropped. |
| `CREATE OR REPLACE TABLE` | Index is dropped silently. Recreate it. |
| `DROP INDEX` | Index is removed. |
| Checkpoint | Whole index is serialized. |

Inspect an index with:

```sql
SELECT * FROM pragma_hnsw_index_info();
```

The pragma takes no arguments. Filter by `table_name` or `index_name` in SQL. It reports `metric`, `dimensions`, `count`, `capacity`, `approx_memory_usage`, and level statistics.

`vss_join` and `vss_match` are brute-force helpers. They do not use the HNSW index.

## Pagination

Do not use `OFFSET` on 2.0.0. The HNSW scan repeats the first page for every offset:

```sql
-- page 2 of an indexed query: wrong
SELECT id FROM items
ORDER BY array_cosine_distance(emb, [1, 0, 0]::FLOAT[3])
LIMIT 10 OFFSET 10;

-- correct: fetch k + offset and slice in the client
SELECT id FROM items
ORDER BY array_cosine_distance(emb, [1, 0, 0]::FLOAT[3])
LIMIT 20;
```

A brute-force scan without the index returns the correct offset rows. Recheck the bug on 2.0.1 before keeping the stop rule.

## Proof

Compare an indexed result with the same query on a copy without the index:

```sql
EXPLAIN SELECT id FROM items ORDER BY array_distance(emb, [1, 0, 0]::FLOAT[3]) LIMIT 3;
-- Hnsw Index Scan

CREATE TABLE brute AS SELECT * FROM items;
EXPLAIN SELECT id FROM brute ORDER BY array_distance(emb, [1, 0, 0]::FLOAT[3]) LIMIT 3;
-- Seq Scan + Top N
```

The two result sets must match for the tested rows. A mismatch means the wrong metric, a stale or dropped index, a non-literal vector, or a different vector width. HNSW is approximate, so compare recall, not exact order, on a large fixture.

## References

- https://duckdb.org/docs/2.0/core_extensions/vss.html
- https://github.com/duckdb/duckdb-vss
- https://duckdb.org/docs/2.0/sql/functions/array.html
- https://duckdb.org/docs/2.0/sql/indexes.html
