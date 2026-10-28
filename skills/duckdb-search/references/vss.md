# Vector search reference

Read this when the skill needs the HNSW metric matrix, persistence rule, memory model, or pagination contract.

## Load and create

```sql
LOAD vss;
SET hnsw_enable_experimental_persistence = true;  -- file database only
CREATE TABLE items (id INTEGER, emb FLOAT[3]);
CREATE INDEX items_hnsw ON items USING HNSW (emb) WITH (metric = 'cosine');
```

`SET` before `LOAD vss` fails because the setting belongs to the extension. `CREATE INDEX ... USING HNSW` without `LOAD vss` fails with `Unknown index type: HNSW`; the extension does not autoload.

The persistence flag gates creation only. Reopening a file and querying an existing HNSW index works without it. WAL recovery for custom indexes is still incomplete, so treat this as experimental and keep a copy.

## Metrics

| Index metric | Query function |
| --- | --- |
| `l2sq` | `array_distance` |
| `cosine` | `array_cosine_distance` |
| `ip` | `array_negative_inner_product` |

The index must match the query function. A `l2sq` index does not accelerate `array_cosine_distance`. `array_cosine_similarity` is not in the table and is not accelerated.

## What is accelerated

```sql
SELECT id
FROM items
ORDER BY array_cosine_distance(emb, [1, 0, 0]::FLOAT[3])
LIMIT 3;
```

`EXPLAIN` must show `Hnsw Index Scan` in text or `HNSW_INDEX_SCAN` in JSON. The accelerated forms are:

- `ORDER BY <matching distance>(col, constant) LIMIT k`
- `min_by(table, <matching distance>(col, constant), k ORDER BY col)`

A `WHERE` filter can ride along. `DESC`, a missing `LIMIT`, and a non-matching function fall back to a scan.

Do not use `OFFSET` on 2.0.0. The HNSW scan repeats the first page for every offset. Fetch `LIMIT k + offset` and slice in the client, or drop the index for that query. Recheck on 2.0.1.

The fuzzy-join macros `vss_join` and `vss_match` are brute-force helpers. They do not use the HNSW index.

## Build options

| Option | Default | Use |
| --- | --- | --- |
| `metric` | `l2sq` | `l2sq`, `cosine`, or `ip`. |
| `ef_construction` | 128 | Higher builds a more accurate index, slower. |
| `ef_search` | 64 | Higher searches more candidates, slower. |
| `M` | 16 | Neighbors per vertex. |
| `M0` | `2 * M` | Base-layer connectivity. |

`SET hnsw_ef_search = N;` overrides search width per connection. `RESET hnsw_ef_search;` removes the override.

## Memory and maintenance

The index is not buffer-managed and does not count toward `memory_limit`. It must fit in RAM. Build-time temporary memory also matters; a low `memory_limit` can fail the build. Budget index RAM separately.

Deletes are marked, not removed. The index grows stale. Run `PRAGMA hnsw_compact_index('items_hnsw');` after a significant number of deletes or recreate the index.

Only `FLOAT` fixed-size arrays are supported. The column type must be `FLOAT[N]`, not variable-length `FLOAT[]`.

## Proof

Compare the indexed result with the same query on a copy without the index:

```sql
EXPLAIN SELECT id FROM items ORDER BY array_distance(emb, [1, 0, 0]::FLOAT[3]) LIMIT 3;
-- Hnsw Index Scan

CREATE TABLE brute AS SELECT * FROM items;
EXPLAIN SELECT id FROM brute ORDER BY array_distance(emb, [1, 0, 0]::FLOAT[3]) LIMIT 3;
-- Seq Scan + Top N
```

The two results must match for the tested rows. A mismatch means the wrong metric, a stale index, or a different vector width.

## References

- https://duckdb.org/docs/2.0/core_extensions/vss.html
- https://duckdb.org/docs/2.0/sql/functions/array.html
- https://duckdb.org/docs/2.0/sql/indexes.html
