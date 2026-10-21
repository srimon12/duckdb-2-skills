---
name: duckdb-docs
description: >
  Full-text search of the DuckDB 2.0 docs and blog, and the DuckLake docs,
  through the official search databases. Use when a DuckDB or DuckLake
  question needs the current manual, or when /duckdb-docs is run.
---

# Search the docs

Prefer this over guessing a function signature. Answer from the chunks, and include the URL.

The DuckDB index at `https://duckdb.org/data/docs-search.duckdb` currently has `version` values `2.0` and `blog`. There is no `lts` or `current` row. Default to `2.0`. Add `blog` when the user wants a post or the motivation. The DuckLake index at `https://ducklake.select/data/docs-search.duckdb` uses `version = 'stable'`.

Checked 2026-10-22: DuckDB index had 2695 chunks at `2.0` and 999 at `blog`. DuckLake had 198 chunks at `stable`.

## Cache

Store the file at `$HOME/.duckdb/docs/duckdb-docs.duckdb` or `ducklake-docs.duckdb`. Refresh when the file is missing or older than two days.

```bash
mkdir -p "$HOME/.duckdb/docs"
```

```sql
INSTALL httpfs; LOAD httpfs; INSTALL fts; LOAD fts;
ATTACH 'https://duckdb.org/data/docs-search.duckdb' AS remote (READ_ONLY);
ATTACH '/absolute/cache.tmp' AS tmp;
COPY FROM DATABASE remote TO tmp;
```

Then rename the temp file over the cache. Open the cache as the main database. `match_bm25` does not resolve correctly through an attached catalog.

## Query

`match_bm25` has side effects. DuckDB 2.0 rejects `WHERE score IS NOT NULL` when `score` is that alias. Wrap it.

```sql
LOAD fts;
SELECT page_title, section, breadcrumb, url, version, text, score
FROM (
    SELECT page_title, section, breadcrumb, url, version, text,
           fts_main_docs_chunks.match_bm25(chunk_id, 'variant shredding') AS score
    FROM docs_chunks
    WHERE version = '2.0'
)
WHERE score IS NOT NULL
ORDER BY score DESC
LIMIT 8;
```

Turn a question into a few technical terms. Drop "how" and "do". Use a function name as-is.

Prefix a relative `url` with `https://duckdb.org` or `https://ducklake.select`.

Columns: `chunk_id`, `page_title`, `section`, `breadcrumb`, `url`, `version`, `text`.

If the index is unreachable, say so and send the user to https://duckdb.org/docs/2.0/ or https://ducklake.select/docs/stable/. If the score filter returns nothing, drop a term and run once more.

Lead with the answer, then the page title and URL for each chunk you used.

## References

- https://duckdb.org/data/docs-search.duckdb
- https://ducklake.select/data/docs-search.duckdb
- https://duckdb.org/docs/2.0/whats_new_in_the_docs.html
- The cache path and `fts_main_docs_chunks.match_bm25` pattern come from the `duckdb-docs` skill in https://github.com/duckdb/duckdb-skills (MIT). The version filter and the subquery are the 2.0 behavior. `WHERE score IS NOT NULL` on the same select list failed on DuckDB 2.0.0 with "Alias score referenced - but the expression has side effects."
