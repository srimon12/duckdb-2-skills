# Hybrid search reference

Read this when one query must combine keyword relevance and vector similarity, or when a fused ranking needs an evaluation.

The recipe uses reciprocal rank fusion (RRF). It needs one literal query term and one literal query vector. Both indexes must already exist. Read [fts.md](fts.md) and [vss.md](vss.md) for the index contracts.

## Contract

```text
Inputs:      one term, one FLOAT[N] vector, FTS index, HNSW index, candidate limit
Outputs:     fused top-k ids and ranks
Invariants:  literal term and vector; literal LIMIT in each leg; deterministic tie-break by id
Failure:     a missing leg contributes zero; a non-literal vector falls back to a scan
Proof:       fused ranks are stable, and recall@k beats each single leg on a labeled fixture
```

## Fuse the ranks

```sql
WITH lex AS (
  SELECT id, row_number() OVER (ORDER BY bm25 DESC, id) r
  FROM (SELECT id, fts_main_docs.match_bm25(id, 'duck') bm25 FROM docs) t
  WHERE bm25 IS NOT NULL ORDER BY bm25 DESC, id LIMIT 50
),
vec AS (
  SELECT id, row_number() OVER (ORDER BY d, id) r
  FROM (SELECT id, array_cosine_distance(emb, [0.9, 0.3, 0]::FLOAT[3]) d FROM docs ORDER BY d LIMIT 50) t
)
SELECT coalesce(l.id, v.id) id,
       coalesce(1.0 / (60 + l.r), 0) + coalesce(1.0 / (60 + v.r), 0) rrf,
       l.r AS lex_rank, v.r AS vec_rank
FROM lex l FULL OUTER JOIN vec v USING (id)
ORDER BY rrf DESC, id
LIMIT 10;
```

`row_number()` must sit outside the `match_bm25` select. Inside, the window sees a volatile expression and raises `ORDER BY window expressions cannot be volatile`.

Each leg needs a literal `LIMIT`. `LIMIT (SELECT k)` removes HNSW acceleration and turns the vector leg into a full scan.

The vector must be a literal `FLOAT[N]`. A scalar subquery, a prepared parameter, or a `::DOUBLE[N]` cast silently removes the index. Bind a new literal query per request in the client.

RRF uses ranks, so raw BM25 and cosine scores never need a shared scale. The constant 60 is a smoothing floor, not a weight. Weight the two terms when one leg is stronger:

```sql
coalesce(0.7 / (60 + l.r), 0) + coalesce(0.3 / (60 + v.r), 0) AS rrf
```

A missing leg contributes zero, not `1/60`. `FULL OUTER JOIN` keeps ids that only one leg found. `coalesce(l.id, v.id)` deduplicates.

## Choose the candidate limit

Start with `k * 5` per leg, capped at a few hundred. A 20k-row fixture used 50 per leg and returned stable ranks in about 1 ms per leg. A larger candidate set improves recall but costs more HNSW search and more BM25 rows.

Do not fuse the full table. The point of both indexes is to avoid a full scan. A limit below `k` cannot return `k` fused rows.

## Evaluate

Fuse ranks on a labeled fixture and compare recall@k with each leg alone. A small deterministic check:

```sql
-- relevant ids for the query, from a fixture or a human label
CREATE TABLE relevant (id INTEGER);
INSERT INTO relevant VALUES (1), (7), (42);

WITH fused AS (
  SELECT id FROM (/* the RRF query above */) t ORDER BY rrf DESC LIMIT 10
)
SELECT count(*) AS hits
FROM fused JOIN relevant USING (id);
```

Run the same query with the lexical leg only and the vector leg only. A fusion that loses to both legs is a weighting or candidate-limit problem, not a reason to add a reranker.

For recall against an exact baseline, compute the true top-k with `array_cosine_distance` on a copy without the HNSW index, then compare the fused top-k with the union of the two exact rankings. Record the fixture size, dimensions, `hnsw_ef_search`, and candidate limit.

## Rerank

A two-stage query is worth it when the embedding model is weak on the domain or the order must be exact. Fuse to 50 or 100, then rerank that set with a cross-encoder or an exact distance. Do not rerank the full table; the cost defeats the index.

Below roughly 10k rows, a brute-force scan over both scores is simpler and often faster than building two indexes. Build the indexes when the table grows past that or when the query repeats.

## Traps

| Trap | Effect | Correct move |
| --- | --- | --- |
| `row_number()` inside the `match_bm25` select | volatile window error | Put the window outside. |
| `LIMIT (SELECT k)` | HNSW leg scans | Use a literal limit. |
| Scalar-subquery vector | HNSW leg scans | Inline a `FLOAT[N]` literal. |
| `::DOUBLE[N]` vector | HNSW leg scans | Cast to `FLOAT[N]`. |
| `OFFSET` on the fused query | repeated rows | Fuse to `k + offset` and slice. |
| No `id` tie-break | unstable ranks on ties | Add `, id` to both `ORDER BY` clauses. |
| Fusing raw scores | BM25 and cosine are not comparable | Fuse ranks or normalize first. |

## References

- https://duckdb.org/docs/2.0/core_extensions/full_text_search.html
- https://duckdb.org/docs/2.0/core_extensions/vss.html
- https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
