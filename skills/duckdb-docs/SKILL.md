---
name: duckdb-docs
description: >
  Answer DuckDB and DuckLake questions from the official full-text search
  indexes. Covers index versions, the BM25 query, caching, and URL handling.
  Use when a 2.0 function signature, setting, or behavior needs the current
  manual instead of a guess.
---

# Docs search

Use the hosted index before guessing a signature. Answer from the returned chunks, and cite the page.

## Index versions

| Index | URL | Versions |
| --- | --- | --- |
| DuckDB | `https://duckdb.org/data/docs-search.duckdb` | `2.0`, `blog` |
| DuckLake | `https://ducklake.select/data/docs-search.duckdb` | `stable` |

The DuckDB index has no `lts`, `current`, or `stable` slice. Default to `2.0`. Add `blog` only when the user wants a post or the motivation. The DuckLake `stable` slice is the 1.1 manual.

The table has `chunk_id`, `page_title`, `section`, `breadcrumb`, `url`, `version`, and `text`. `url` is a path, not an absolute URL.

## Cache

Store the file at `$HOME/.duckdb/docs/duckdb-docs.duckdb` or `ducklake-docs.duckdb`. Refresh when the file is missing or older than two days.

```bash
mkdir -p "$HOME/.duckdb/docs"
```

```sql
INSTALL httpfs; LOAD httpfs;
INSTALL fts; LOAD fts;
ATTACH 'https://duckdb.org/data/docs-search.duckdb' AS remote (READ_ONLY);
ATTACH '/absolute/cache.tmp' AS tmp;
COPY FROM DATABASE remote TO tmp;
```

Rename the temp file over the cache. Open the cache with `-readonly` and as the main database, not as an attached catalog, so `fts_main_docs_chunks.match_bm25` resolves. A read-write open locks out other agents.

## Query

`match_bm25` has side effects. DuckDB 2.0 rejects `WHERE score IS NOT NULL` or `QUALIFY score IS NOT NULL` when `score` is the alias in the same select list. Wrap those in a subquery or CTE. `ORDER BY score DESC` in the same select works.

```sql
LOAD fts;
SELECT page_title, section, url, version, text, score
FROM (
    SELECT page_title, section, url, version, text,
           fts_main_docs_chunks.match_bm25(chunk_id, 'variant extract') AS score
    FROM docs_chunks
    WHERE version = '2.0'
)
WHERE score IS NOT NULL
ORDER BY score DESC
LIMIT 8;
```

The 2.0 macro has ten parameters: `match_bm25(docname, query_string, fields := NULL, k := 1.2, b := 0.75, conjunctive := false, field_weights := NULL, field_b := NULL, scoring_model := 'bm25f', tie_breaker := 0.0)`. The manual page lists only six; the binary and `duckdb_functions()` are authoritative. The indexed fields are `page_title`, `section`, and `text`.

Set `conjunctive := 1` when every term must appear. `field_weights := {'text': 2.0}` boosts a field. `stemmer`, `stopwords`, and `ignore` are `PRAGMA create_fts_index` options, not `match_bm25` arguments. `bm25_k1` and `bm25_b` do not exist; use `k` and `b`.

Turn the question into two or three technical terms. Drop "how" and "do". Keep a function name as written. If a search returns nothing, drop a term. If you had set `conjunctive := 1`, retry with `0`; the default is already `0`.

Prefix a relative `url` with `https://duckdb.org` or `https://ducklake.select`.

## Answer

Lead with the answer in one or two sentences. Then give the page title and absolute URL for each chunk you used. Quote only the lines that carry the signature or the rule.

If the cache is missing and the network works, query the hosted index directly: `ATTACH ... AS remote; USE remote;` and run the same query. It took about five seconds in probing. If the network is down, use a stale cache read-only with a warning. If neither exists, say so and link `https://duckdb.org/docs/2.0/` or `https://ducklake.select/docs/stable/`. Do not invent an answer from memory.

## Verify

```bash
duckdb -readonly "$HOME/.duckdb/docs/duckdb-docs.duckdb" -c \
  "LOAD fts; SELECT version, count(*) FROM docs_chunks GROUP BY version;"
```

Expect `2.0` and `blog`, with no `lts` or `current` row. A missing or empty result means the cache is stale or the copy failed. On 2026-10-22 the counts were `2.0=2695`, `blog=999`, and DuckLake `stable=198`. A count change is a refresh signal; a missing `2.0` or `stable` row is decisive.

## References

- [DuckDB search index](https://duckdb.org/data/docs-search.duckdb) is the 2.0 manual and blog.
- [DuckLake search index](https://ducklake.select/data/docs-search.duckdb) is the stable DuckLake manual.
- [Full-text search extension](https://duckdb.org/docs/2.0/core_extensions/full_text_search.html) owns the `match_bm25` signature.
- [What's new in the 2.0 docs](https://duckdb.org/docs/2.0/whats_new_in_the_docs.html) is a useful fallback when a term is new.
- Index counts and the BM25 subquery were checked on 2026-10-22 against DuckDB 2.0.0. The current counts live in `research/09-verified-facts.md`.
