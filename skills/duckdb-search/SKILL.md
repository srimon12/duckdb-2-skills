---
name: duckdb-search
description: >
  Build and query DuckDB 2.0 search indexes. Covers BM25 full-text search,
  layered prefix and fuzzy search, HNSW vector search, freshness, metric
  matching, hybrid ranking, and proof. Use when the user asks for keyword
  search, BM25, semantic search, HNSW, a nearest-neighbor index, or ranked
  search over a table.
---

# Search indexes

Before writing SQL, choose among four search paths. Full-text ranks by keywords, layered full-text adds prefix and typo matching, HNSW ranks by vector distance, and hybrid fusion combines keywords and vectors. For spatial or as-of proximity, use `NEAREST` joins in `duckdb-sql` instead of an index. To install or load `fts` or `vss` offline, follow `duckdb-extensions`.

## Pick the path

| Question | Path | First command |
| --- | --- | --- |
| Which rows contain these words, ranked by relevance? | BM25 | `PRAGMA create_fts_index(...)` |
| Which rows contain this prefix, typo, or phrase? | Layered BM25 | `layered_search = 1` |
| Which vectors are closest to this embedding? | HNSW | `CREATE INDEX ... USING HNSW` |
| Combine keywords and embeddings | Two indexes | Fuse the ranks in SQL |

For one-off queries, small tables, or narrow pre-filters, a sequential scan is usually faster than an index.

## Contract

For FTS:

```text
Inputs:      one base table, one NOT NULL unique id, one or more text columns
Outputs:     ranked ids and scores
Invariant:   static index is a snapshot; incremental covers INSERT and DELETE, not UPDATE
Proof:       inserted term is found, deleted term is gone, updated term is repaired
```

For HNSW:

```text
Inputs:      one table, one FLOAT[N] column, non-null finite vectors
Outputs:     top-k ids by one distance function
Invariant:   index metric matches query function; query vector is a literal FLOAT[N]
Proof:       EXPLAIN shows HNSW_INDEX_SCAN; result matches brute-force scan
```

## Full text

```sql
PRAGMA create_fts_index('docs', 'id', 'body', stemmer = 'porter', stopwords = 'english', overwrite = 1, incremental = 1);
```

Before building an index, declare the id column `NOT NULL UNIQUE`. A static index accepts nullable ids and silently drops NULL rows, or accepts duplicate ids and fails at query time with `More than one row returned`. An incremental index rejects both at creation. Name indexed columns explicitly; `'*'` indexes every `VARCHAR` column, including a `VARCHAR` id, making it searchable.

To filter by score, wrap `match_bm25` in a subquery. Because the alias expression has side effects, a same-select `WHERE score IS NOT NULL` fails:

```sql
SELECT id, body, bm25
FROM (SELECT id, body, fts_main_docs.match_bm25(id, 'database') AS bm25 FROM docs) t
WHERE bm25 IS NOT NULL
ORDER BY bm25 DESC;
```

When querying, treat the string as a bag of terms combined with `OR`. To require all surviving terms, pass `conjunctive := 1`. Because quotes, `-`, and `*` act as delimiters rather than phrase, negation, or wildcard operators, use a layered index for those patterns. To restrict matching, pass `fields := 'title,body'`; DuckDB 2.0.0 returns zero rows on unknown fields, whereas development builds raise `fields contains unknown field`.

Because BM25 scores are unbounded and corpus-dependent, rank results rather than comparing scores to a fixed threshold. Multi-field indexes use BM25F to weight fields via `field_weights` and `field_b` before saturating once; see [references/fts.md](references/fts.md).

On persistent databases, `incremental = 1` requires storage version `v2.0.0` or newer; older versions fail:

```text
Invalid Input Error: incremental FTS indexes require trigger support. Persistent DuckDB databases must use storage version v2.0.0 or higher.
```

Because incremental triggers cover only `INSERT` and `DELETE`, an `UPDATE` leaves old terms searchable and new terms missing. On incrementally indexed tables, `INSERT ... ON CONFLICT DO UPDATE` and `MERGE INTO` fail. To refresh updated rows, run `DELETE` followed by `INSERT`, or rebuild with `overwrite = 1`. When replacing a table via `CREATE OR REPLACE TABLE`, rebuild the index because the operation leaves the old index schema behind.

For code, logs, and identifiers, override the default tokenizer. The default `ignore` pattern treats digits and `.` as delimiters, so `2.0` tokenizes to empty and `s3` indexes only as `s`, making exact matches impossible. The default English stopword list also strips valid identifiers like `name`, `value`, `where`, and `only`. Set `stemmer = 'none'`, `stopwords = 'none'`, and specify a custom `ignore` pattern that preserves required characters. Because stemming is not prefix matching, `duckling` and `duck` remain separate terms unless stemmed to `none` or queried with a layered index.

The index resides in tables under schema `fts_<schema>_<table>`. Because FTS uses table lookups rather than a physical plan operator, `EXPLAIN` does not show index usage; verify index health with a term count query.

## Layered search

When users search by prefix, typo, or autocomplete fragment, set `layered_search = 1`. This builds dictionary sidecar tables and exposes the `search_layered_bm25` and `match_layered_bm25` macros:

```sql
PRAGMA create_fts_index('docs', 'id', 'body', stemmer = 'none', stopwords = 'none', layered_search = 1, incremental = 1);
SELECT docname, score, rank FROM fts_main_docs.search_layered_bm25('quac', top_k := 10);
```

Both macros support prefix, substring, fuzzy, and autocomplete matching. To treat only the final token as a raw prefix, set `query_mode := 'autocomplete'`. To execute boolean trees with `must`, `should`, `must_not`, and `minimum_should_match`, run `LOAD json;` and query `search_layered_bm25_query`.

Because sidecars increase build time and disk footprint, enable layered search only when prefix or fuzzy matching is required. Maintenance matches base FTS: static indexes require rebuilding with `overwrite = 1`, while incremental indexes capture `INSERT` and `DELETE` but ignore `UPDATE`. See [references/fts.md](references/fts.md).

## Vector

```sql
LOAD vss;
SET hnsw_enable_experimental_persistence = true;  -- file database, before CREATE
CREATE TABLE items (id INTEGER, emb FLOAT[3]);
CREATE INDEX items_hnsw ON items USING HNSW (emb) WITH (metric = 'cosine');
```

In file databases, run `LOAD vss;` before setting `SET hnsw_enable_experimental_persistence = true;` because settings belong to the extension. The persistence flag gates index creation, not reads. Without `LOAD vss`, DuckDB silently ignores existing indexes and scans sequentially.

When defining the index, restrict the key column to `FLOAT[N]`. Types like `DOUBLE[N]`, `INTEGER[N]`, or `FLOAT[]` fail:

```text
Binder Error: HNSW index key type must be one of: 'FLOAT[N]'
```

Before inserting, reject NULL and zero vectors. NULL vectors are never indexed, causing `LIMIT k` queries to return fewer rows without warning, while zero vectors produce `nan` cosine distances.

To accelerate vector queries, match the query function to the index metric:

| Index metric | Query function |
| --- | --- |
| `l2sq` | `array_distance` |
| `cosine` | `array_cosine_distance` |
| `ip` | `array_negative_inner_product` |

```sql
SELECT id FROM items ORDER BY array_cosine_distance(emb, [1, 0, 0]::FLOAT[3]) LIMIT 3;
```

When querying, pass the query vector as a literal `FLOAT[N]`. Any `::DOUBLE[N]` cast, scalar subquery, `DESC` sort, missing `LIMIT`, tie-breaker like `ORDER BY dist, id`, or dynamic `LIMIT (SELECT k)` silently triggers a full sequential scan. Prepared `$1` vectors and ordinal `ORDER BY 1` use HNSW but execute a full index scan without top-k pushdown. Sort by `array_cosine_distance` or `1.0 - array_cosine_similarity`; bare `array_cosine_similarity` is never accelerated.

When filtering, retain the default `hnsw_prefilter = true`. Setting it to `false` on a selective filter can return zero rows. Prefiltering costs a full scan of the filter columns, so a very selective filter over a large table is not free. To improve recall, raise `hnsw_ef_search` (default 64). On DuckDB 2.0.0, never use `OFFSET`; the index scan repeats the first page. Query `LIMIT (k + offset)` and slice results in the client.

Because HNSW allocations occur outside the buffer manager, index memory does not count toward `memory_limit`. Budget 0.6 to 3 KB per vector. Checkpoints serialize the entire index, and the first table access deserializes it. Because deletes only mark entries and `hnsw_compact_index` does not reclaim capacity in 2.0.0, rebuild the index after large deletes. See [references/vss.md](references/vss.md).

## Hybrid search

To combine keyword relevance and semantic distance, query both indexes and merge candidates using reciprocal rank fusion (RRF). RRF compares relative ranks rather than incompatible raw scores. Use literal terms and literal vectors to keep both legs accelerated:

```sql
WITH lex AS (
  SELECT id, row_number() OVER (ORDER BY bm25 DESC, id) AS r
  FROM (SELECT id, fts_main_docs.match_bm25(id, 'duck') AS bm25 FROM docs) t
  WHERE bm25 IS NOT NULL ORDER BY bm25 DESC, id LIMIT 50
),
vec AS (
  SELECT id, row_number() OVER (ORDER BY d, id) AS r
  FROM (SELECT id, array_cosine_distance(emb, [0.9, 0.3, 0]::FLOAT[3]) AS d FROM docs ORDER BY d LIMIT 50) t
)
SELECT coalesce(l.id, v.id) AS id,
       coalesce(1.0 / (60 + l.r), 0) + coalesce(1.0 / (60 + v.r), 0) AS rrf
FROM lex l FULL OUTER JOIN vec v USING (id)
ORDER BY rrf DESC, id;
```

In the lexical leg, place `row_number()` outside the `match_bm25` subquery to prevent volatile expression errors. In both legs, supply a literal `LIMIT`; dynamic limits force vector sequential scans. Missing legs contribute zero rather than `1/60`. To tune precision, raise candidate limits before adjusting leg weights, and measure recall against a brute-force baseline. See [references/hybrid.md](references/hybrid.md).

## Stop rules

- On update-heavy tables or persistent databases with storage version below `v2.0.0`, do not set `incremental = 1`; rebuild with `overwrite = 1`.
- When indexing code, logs, or identifiers, do not use default stopwords or ignore patterns; set `stemmer = 'none'`, `stopwords = 'none'`, and preserve digits.
- When querying HNSW, do not mix metrics with mismatched distance functions, and do not sort by bare `array_cosine_similarity`; use `array_cosine_distance` or `1.0 - array_cosine_similarity`.
- When accelerating vector searches, do not use non-literal vectors, `DESC`, tie-breaker sorts, or dynamic `LIMIT (SELECT ...)`; on 2.0.0, do not paginate with `OFFSET`.
- In persistent file databases, do not create HNSW indexes without setting `hnsw_enable_experimental_persistence = true` after loading `vss`.
- When filtering indexed vectors with selective predicates, do not set `hnsw_prefilter = false`.

## Verify

```bash
tmp=$(mktemp -d)
duckdb "$tmp/search.duckdb" -c "
LOAD fts;
CREATE TABLE docs (id INTEGER NOT NULL, body VARCHAR);
INSERT INTO docs VALUES (1, 'duck database'), (2, 'other text');
PRAGMA create_fts_index('docs', 'id', 'body', incremental = 1);
SELECT count(*) FROM (SELECT id, fts_main_docs.match_bm25(id, 'duck') AS score FROM docs) WHERE score IS NOT NULL;
LOAD vss;
SET hnsw_enable_experimental_persistence = true;
CREATE TABLE items (id INTEGER, emb FLOAT[3]);
INSERT INTO items VALUES (1, [1, 0, 0]), (2, [0, 1, 0]);
CREATE INDEX items_hnsw ON items USING HNSW (emb) WITH (metric = 'cosine');
EXPLAIN SELECT id FROM items ORDER BY array_cosine_distance(emb, [1, 0, 0]::FLOAT[3]) LIMIT 1;
SELECT * FROM pragma_hnsw_index_info();
"
rm -rf "$tmp"
```

To verify correctness, confirm the FTS query returns count `1`, the `EXPLAIN` plan includes `Hnsw Index Scan` (or `HNSW_INDEX_SCAN`), and `pragma_hnsw_index_info()` reports the `cosine` metric with 3 dimensions. Validate vector recall by comparing top-k outputs against an unindexed table scan.

## References

- [Full-text search](https://duckdb.org/docs/2.0/core_extensions/full_text_search.html) documents `create_fts_index` and `match_bm25`.
- [Vector similarity search](https://duckdb.org/docs/2.0/core_extensions/vss.html) documents HNSW indexes, metrics, and persistence settings.
- [Array functions](https://duckdb.org/docs/2.0/sql/functions/array.html) documents vector distance functions.
- [FTS reference](references/fts.md) details parameters, layered search, boolean JSON trees, BM25F scoring, and update repairs.
- [VSS reference](references/vss.md) details metric matching, plan acceleration rules, memory overhead, and pagination.
- [Hybrid reference](references/hybrid.md) details reciprocal rank fusion, weighting, and recall evaluation.
- Consult `duckdb-extensions` for installing, loading, and pinning `fts` and `vss` offline.
- Consult `duckdb-sql` for `NEAREST` joins and fixed-size array syntax.
