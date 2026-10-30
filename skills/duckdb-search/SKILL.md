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

Four paths answer different questions. Full-text search ranks documents by terms. Layered full-text search adds prefix, substring, and fuzzy matching. HNSW ranks rows by vector distance. Hybrid fusion combines the first and third. Pick the path before writing SQL. `NEAREST` joins in `duckdb-sql` are a separate join feature, not an index.

Load `fts` or `vss` with `duckdb-extensions`. The extension install rules and offline paths live there.

## Pick the path

| Question | Path | First command |
| --- | --- | --- |
| Which rows contain these words, ranked by relevance? | BM25 | `PRAGMA create_fts_index(...)` |
| Which rows contain this prefix, typo, or phrase? | Layered BM25 | `layered_search = 1` |
| Which vectors are closest to this embedding? | HNSW | `CREATE INDEX ... USING HNSW` |
| Combine keywords and embeddings | Two indexes | Fuse the ranks in SQL |

Do not build an index for a one-off scan. A small table or a narrow filter is often faster without one.

## Contract

For FTS:

```text
Inputs:      one base table, one NOT NULL unique id, one or more text columns
Outputs:     ranked ids and scores
Invariant:   a static index is a snapshot; an incremental index covers INSERT and DELETE, not UPDATE
Proof:       an inserted term is found, a deleted term is gone, an updated term is repaired
```

For HNSW:

```text
Inputs:      one table, one FLOAT[N] column, non-null finite vectors
Outputs:     top-k ids by one distance function
Invariant:   the index metric matches the query function, and the query vector is a literal
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

The id must be `NOT NULL` and unique. A static index accepts a nullable id and silently drops the NULL row, or accepts duplicate ids and then fails at query time. An incremental index rejects both at creation. Name the indexed columns explicitly; `'*'` also indexes a `VARCHAR` id and makes it searchable.

Filter the score in a subquery. The alias has side effects, so a same-select `WHERE score IS NOT NULL` fails.

```sql
SELECT id, body, bm25
FROM (
    SELECT id, body, fts_main_docs.match_bm25(id, 'database') AS bm25
    FROM docs
) t
WHERE bm25 IS NOT NULL
ORDER BY bm25 DESC;
```

A query string is a bag of terms. Terms are OR by default. `conjunctive := 1` requires every surviving term. There is no phrase, wildcard, negation, or `AND`/`OR` syntax: quotes, `-`, and `*` are delimiters. Use a layered index for those shapes. `fields := 'title,body'` restricts matching and scoring; on 2.0.0 an unknown field returns zero rows without an error, and later builds raise `fields contains unknown field`.

Scores are unbounded and corpus-dependent. Rank them; do not compare them to a fixed threshold. BM25F combines fields with field weights, then saturates once. `field_weights`, `field_b`, `scoring_model`, and `tie_breaker` are in [references/fts.md](references/fts.md).

Incremental freshness has one hard gate. On a persistent database, `incremental = 1` needs storage version `v2.0.0` or newer:

```text
Invalid Input Error: incremental FTS indexes require trigger support. Persistent DuckDB databases must use storage version v2.0.0 or higher.
```

Incremental triggers cover `INSERT` and `DELETE`. An `UPDATE` leaves the old term searchable and the new term missing. `INSERT ... ON CONFLICT DO UPDATE` and `MERGE INTO` fail on the table. Repair with `DELETE` plus `INSERT`, or rebuild with `overwrite = 1`. `CREATE OR REPLACE TABLE` leaves the old index schema behind and the new table can return stale matches.

Tokenization decides whether a search is usable. The default `ignore` pattern treats digits and `.` as delimiters: `2.0` tokenizes to nothing, and `s3` indexes as the single token `s`, so an exact `s3` match is impossible. The English stopword list contains words such as `name`, `value`, `where`, and `only`. For code, API names, or logs, set `stemmer = 'none'`, `stopwords = 'none'`, and an `ignore` pattern that keeps the characters you need. Stemming is not prefix matching. `duckling` and `duck` are separate terms. Exact tokens need `none`.

The index lives in `fts_<schema>_<table>`. It is a set of tables, not a plan operator, so a plan does not prove it is used. A freshness count does.

## Layered search

Set `layered_search = 1` when users type prefixes, misspellings, or autocomplete fragments. The index adds dictionary sidecar tables and the `search_layered_bm25` / `match_layered_bm25` macros:

```sql
PRAGMA create_fts_index('docs', 'id', 'body', stemmer = 'none', stopwords = 'none', layered_search = 1, incremental = 1);
SELECT docname, score, rank FROM fts_main_docs.search_layered_bm25('quac', top_k := 10);
```

Both macros support prefix, substring, fuzzy, and autocomplete expansion. `query_mode := 'autocomplete'` treats only the final token as a raw prefix. A layered index also enables a JSON boolean tree through `search_layered_bm25_query` after `LOAD json`, with `must`, `should`, `must_not`, and `minimum_should_match`.

Layered maintenance follows the base index: static snapshots need a rebuild, incremental indexes track `INSERT` and `DELETE` only. The sidecar tables add build cost and disk; build layered only when the matching shape needs it. Exact parameters and boolean examples are in [references/fts.md](references/fts.md).

## Vector

```sql
LOAD vss;
SET hnsw_enable_experimental_persistence = true;  -- file database, before CREATE
CREATE TABLE items (id INTEGER, emb FLOAT[3]);
CREATE INDEX items_hnsw ON items USING HNSW (emb) WITH (metric = 'cosine');
```

The key column must be `FLOAT[N]`. `DOUBLE[N]`, `INTEGER[N]`, and variable-length `FLOAT[]` fail:

```text
Binder Error: HNSW index key type must be one of: 'FLOAT[N]'
```

`SET` before `LOAD vss` fails because the setting belongs to the extension. The persistence flag gates creation, not reads. Without `LOAD vss`, an existing index is silently ignored and the query falls back to a scan.

NULL vectors are never indexed. A query with `LIMIT k` can return fewer than `k` rows without an error. Zero vectors are accepted and cosine distance to a zero vector is `nan`. Reject both before insert.

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

The query vector must be a literal `FLOAT[N]`. A `::DOUBLE[N]` cast, a scalar subquery, `DESC`, a missing `LIMIT`, a tie-breaker `ORDER BY dist, id`, and `LIMIT (SELECT k)` silently fall back to a sequential scan. A prepared `$1` and an ordinal `ORDER BY 1` still use HNSW, but as a full index scan without top-k pushdown. Sort by `array_cosine_distance`, or by `1.0 - array_cosine_similarity`, which the planner rewrites to the distance; a bare `array_cosine_similarity` sort is not accelerated.

A `WHERE` filter is applied before the HNSW search by default. Keep `hnsw_prefilter = true`. Setting it to `false` on a selective filter can return zero rows. Prefiltering costs a full scan of the filter columns, so a very selective filter over a large table is not free. Raise `hnsw_ef_search` for recall; the default is 64. Do not add `OFFSET` on 2.0.0; the index scan repeats the first page. Fetch `LIMIT k + offset` and slice in the client, or drop the index for that query. Recheck on 2.0.1.

The index is not buffer-managed and does not count toward `memory_limit`. Budget about 0.6 to 3 KB per vector. It is serialized on every checkpoint and deserialized on first table access. Deletes are marked, not removed. `hnsw_compact_index` did not reclaim memory in 2.0.0; rebuild after a large delete. Options and memory behavior are in [references/vss.md](references/vss.md).

## Hybrid search

Query both indexes, then fuse the ranks. Reciprocal rank fusion (RRF) is robust because it uses ranks, not raw scores. The query vector and term must be literals for HNSW:

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
       coalesce(1.0 / (60 + l.r), 0) + coalesce(1.0 / (60 + v.r), 0) rrf
FROM lex l FULL OUTER JOIN vec v USING (id)
ORDER BY rrf DESC, id;
```

`row_number` must sit outside the `match_bm25` select. Both legs need a literal `LIMIT`. A missing leg contributes zero, not `1/60`. Raise the two candidate limits before adding weights, and evaluate recall against a brute-force scan. The full recipe, weighting, and evaluation are in [references/hybrid.md](references/hybrid.md).

## Stop rules

- Do not use `incremental = 1` on an update-heavy table or a pre-2.0 storage file.
- Do not index code or identifiers with the default stopwords and digit-stripping pattern.
- Do not mix an HNSW metric with a different distance function, or sort by a bare `array_cosine_similarity`.
- Do not use a non-literal HNSW query vector, `DESC`, a tie-breaker, or `LIMIT (SELECT ...)`; do not paginate with `OFFSET` on 2.0.0.
- Do not build HNSW in a file database without the persistence flag.
- Do not disable `hnsw_prefilter` on a selective filter.

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
SELECT * FROM pragma_hnsw_index_info();
"
rm -rf "$tmp"
```

The FTS count must be 1. The plan must contain `Hnsw Index Scan` in text or `HNSW_INDEX_SCAN` in JSON. The index info must report the `cosine` metric and three dimensions. Then compare one HNSW result with the same query on a copy without the index.

## References

- [Full-text search](https://duckdb.org/docs/2.0/core_extensions/full_text_search.html) owns `create_fts_index` and `match_bm25`.
- [Vector similarity search](https://duckdb.org/docs/2.0/core_extensions/vss.html) owns HNSW, metrics, and persistence.
- [Array functions](https://duckdb.org/docs/2.0/sql/functions/array.html) own the distance functions.
- [FTS reference](references/fts.md) has parameters, layered search, query semantics, scoring, and repair.
- [VSS reference](references/vss.md) has metric, acceleration, memory, and pagination contracts.
- [Hybrid reference](references/hybrid.md) has rank fusion, weights, and evaluation.
- Read `duckdb-extensions` for install, offline, and version pinning.
- Read `duckdb-sql` for `NEAREST` joins and fixed-size array syntax.
