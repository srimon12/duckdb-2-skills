---
name: duckdb-search
description: >
  Build and query DuckDB 2.0 search indexes. Covers full-text BM25 and HNSW
  vector search, index freshness, metric matching, persistence, and proof.
  Use when the user asks for keyword search, BM25, semantic search, HNSW, a
  nearest-neighbor index, or ranked search over a table.
---

# Search indexes

Two index families answer different questions. Full-text search ranks documents by terms. HNSW ranks rows by vector distance. Pick the family before writing SQL. `NEAREST` joins in `duckdb-sql` are a separate join feature, not an index.

Load `fts` or `vss` with `duckdb-extensions`. The extension install rules and offline paths live there.

## Pick the index

| Question | Index | First command |
| --- | --- | --- |
| Which rows contain these words, ranked by relevance? | FTS | `PRAGMA create_fts_index(...)` |
| Which vectors are closest to this embedding? | HNSW | `CREATE INDEX ... USING HNSW` |
| One-off scan over a few thousand rows | None | `ILIKE`, `regexp_matches`, or `array_distance` |
| Combine keywords and embeddings | Two indexes | Query both, fuse the ranks in SQL |

Do not build an index for a one-off scan. A small table or a narrow filter is often faster without one.

## Contract

For FTS:

```text
Inputs:      one table, one NOT NULL unique id, one or more text columns
Outputs:     ranked ids and scores
Invariant:   incremental indexes track INSERT and DELETE, not UPDATE
Proof:       an inserted term is found, a deleted term is gone, an updated term is repaired
```

For HNSW:

```text
Inputs:      one table, one fixed-size FLOAT[N] or DOUBLE[N] column
Outputs:     top-k ids by one distance function
Invariant:   the index metric matches the query function
Proof:       EXPLAIN shows HNSW_INDEX_SCAN; the result matches a brute-force scan
```

## Full text

```sql
PRAGMA create_fts_index(
    'docs', 'id', 'body',
    stemmer = 'porter',
    stopwords = 'english',
    overwrite = 1,
    incremental = 1
);
```

The id must be `NOT NULL` and unique. `UNIQUE` alone is not enough because the column can still be `NULL`.

Filter the score in a subquery. The alias has side effects, so a same-select `WHERE score IS NOT NULL` fails.

```sql
SELECT id, body, score
FROM (
    SELECT id, body, fts_main_docs.match_bm25(id, 'database') AS score
    FROM docs
) t
WHERE score IS NOT NULL
ORDER BY score DESC;
```

`incremental = 1` maintains the index for `INSERT` and `DELETE` only. An `UPDATE` leaves the old term searchable and the new term missing. Repair it with `DELETE` plus `INSERT`, or rebuild with `overwrite = 1`. Do not choose an incremental index for an update-heavy table.

Parameters, tokenizers, and rebuild cost are in [references/fts.md](references/fts.md).

## Vector

```sql
LOAD vss;
SET hnsw_enable_experimental_persistence = true;  -- file database, before CREATE
CREATE TABLE items (id INTEGER, emb FLOAT[3]);
CREATE INDEX items_hnsw ON items USING HNSW (emb) WITH (metric = 'cosine');
```

`SET` before `LOAD vss` fails because the setting comes from the extension. The persistence flag gates index creation, not reads. Reopening a file and querying an existing HNSW index works without it.

The query function must match the index metric:

| Index metric | Query function |
| --- | --- |
| `l2sq` | `array_distance` |
| `cosine` | `array_cosine_distance` |
| `ip` | `array_negative_inner_product` |

```sql
SELECT id
FROM items
ORDER BY array_cosine_distance(emb, [1, 0, 0]::FLOAT[3])
LIMIT 3;
```

`array_cosine_similarity` is not accelerated. `DESC` and a missing `LIMIT` fall back to a scan. A `WHERE` filter can ride along. `min_by` is also accelerated.

Do not add `OFFSET` to an HNSW query on 2.0.0. The index scan repeats the first page. Fetch `LIMIT k + offset` and slice in the client, or drop the index for that query. Recheck on 2.0.1.

The HNSW index is not buffer-managed and its size does not count toward `memory_limit`. Budget index RAM separately. Do not raise `memory_limit` to fix an HNSW OOM.

Options, memory behavior, and the brute-force proof are in [references/vss.md](references/vss.md).

## Stop rules

- Do not use `incremental = 1` on a table that receives updates.
- Do not mix an HNSW metric with a different distance function.
- Do not paginate an HNSW query with `OFFSET` on 2.0.0.
- Do not build HNSW in a file database without the persistence flag.
- Do not use `array_cosine_similarity` for an indexed query.
- Do not treat a vector index as authorization or as a document store.

## Verify

```bash
tmp=$(mktemp -d)
duckdb "$tmp/search.duckdb" -c "
LOAD fts;
CREATE TABLE docs (id INTEGER NOT NULL, body VARCHAR);
INSERT INTO docs VALUES (1, 'duck database'), (2, 'other text');
PRAGMA create_fts_index('docs', 'id', 'body', incremental = 1);
SELECT count(*) FROM (
  SELECT id, fts_main_docs.match_bm25(id, 'duck') AS score FROM docs
) WHERE score IS NOT NULL;
LOAD vss;
SET hnsw_enable_experimental_persistence = true;
CREATE TABLE items (id INTEGER, emb FLOAT[3]);
INSERT INTO items VALUES (1, [1, 0, 0]), (2, [0, 1, 0]);
CREATE INDEX items_hnsw ON items USING HNSW (emb) WITH (metric = 'cosine');
EXPLAIN SELECT id FROM items ORDER BY array_cosine_distance(emb, [1, 0, 0]::FLOAT[3]) LIMIT 1;
"
rm -rf "$tmp"
```

The FTS count must be 1. The plan must contain an HNSW index scan (`Hnsw Index Scan` in text, `HNSW_INDEX_SCAN` in JSON). Then compare one HNSW result with the same query on a copy without the index.

## References

- [Full-text search](https://duckdb.org/docs/2.0/core_extensions/full_text_search.html) owns `create_fts_index` and `match_bm25`.
- [Vector similarity search](https://duckdb.org/docs/2.0/core_extensions/vss.html) owns HNSW, metrics, and persistence.
- [Array functions](https://duckdb.org/docs/2.0/sql/functions/array.html) own the distance functions.
- [FTS reference](references/fts.md) has parameters, freshness, and repair.
- [VSS reference](references/vss.md) has metric, memory, and pagination contracts.
- Read `duckdb-extensions` for install, offline, and version pinning.
- Read `duckdb-sql` for `NEAREST` joins and fixed-size array syntax.
