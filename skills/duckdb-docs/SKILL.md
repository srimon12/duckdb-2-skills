---
name: duckdb-docs
description: >
  Look up exact DuckDB 2.0 and DuckLake manual text in the official full-text
  indexes. Covers index versions, the BM25 query, caching, and URL handling.
  Use when a signature, setting, or page needs the current manual and no task
  skill owns the procedure.
---

# Docs search

Before guessing a signature, query the hosted index. Use this skill only when no task skill owns the procedure. Answer from the returned chunks, and cite the page.

This skill queries the hosted docs index. To build an FTS index on a user table, read `duckdb-search`.

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

The 2.0 macro accepts ten parameters in `match_bm25(docname, query_string, fields := NULL, k := 1.2, b := 0.75, conjunctive := false, field_weights := NULL, field_b := NULL, scoring_model := 'bm25f', tie_breaker := 0.0)`. The manual page lists only six; the binary and `duckdb_functions()` are authoritative. The indexed fields are `page_title`, `section`, and `text`.

When every term must appear, set `conjunctive := 1`. Use `field_weights := {'text': 2.0}` to boost a field. The options `stemmer`, `stopwords`, and `ignore` belong to `PRAGMA create_fts_index`, not `match_bm25`. The names `bm25_k1` and `bm25_b` do not exist; use `k` and `b`.

Turn the question into two or three technical terms. Drop "how" and "do". Keep a function name as written. If a search returns nothing, drop a term. If you had set `conjunctive := 1`, retry with `0`; the default is already `0`.

Prefix a relative `url` with `https://duckdb.org` or `https://ducklake.select`.

## Answer

Lead with the answer in one or two sentences. Then give the page title and absolute URL for each chunk you used. Quote only the lines that carry the signature or the rule.

If the cache is missing and the network works, query the hosted index directly with `ATTACH ... AS remote; USE remote;` and run the same query. The query took about five seconds in probing. If the network is down, use a stale cache read-only with a warning. If neither exists, report the issue and link `https://duckdb.org/docs/2.0/` or `https://ducklake.select/docs/stable/`. Do not invent an answer from memory.

## Verify

```bash
duckdb -readonly "$HOME/.duckdb/docs/duckdb-docs.duckdb" -c \
  "LOAD fts; SELECT version, count(*) FROM docs_chunks GROUP BY version;"
```

Expect `2.0` and `blog`, with no `lts` or `current` row. Expect roughly 2,700 `2.0` chunks, 1,000 `blog` chunks, and about 198 DuckLake `stable` chunks. A missing `2.0` or `stable` row is decisive; a count change is a refresh signal.

## References

- [DuckDB search index](https://duckdb.org/data/docs-search.duckdb) is the 2.0 manual and blog.
- [DuckLake search index](https://ducklake.select/data/docs-search.duckdb) is the stable DuckLake manual.
- [Full-text search extension](https://duckdb.org/docs/2.0/core_extensions/full_text_search.html) owns the `match_bm25` signature.
- [What's new in the 2.0 docs](https://duckdb.org/docs/2.0/whats_new_in_the_docs.html) is a useful fallback when a term is new.
- The index schema and the BM25 subquery were checked against DuckDB 2.0.0.
