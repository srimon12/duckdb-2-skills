---
name: duckdb-docs
description: >
  Look up exact DuckDB 2.0 and DuckLake manual text in the official full-text
  indexes. Covers index versions, the BM25 query, caching, and URL handling.
  Use when a signature, setting, or page needs the current manual and no task
  skill owns the procedure.
---

# Docs search

Before guessing a signature, setting, or syntax rule, query the hosted documentation index. Use this skill only when no dedicated task skill owns the procedure. Answer strictly from retrieved chunks and cite the exact page. To build an FTS index on user tables, read `duckdb-search`.

## Index versions

| Index | URL | Versions |
| --- | --- | --- |
| DuckDB | `https://duckdb.org/data/docs-search.duckdb` | `2.0`, `blog` |
| DuckLake | `https://ducklake.select/data/docs-search.duckdb` | `stable` |

The DuckDB index provides only `2.0` and `blog` slices; it contains no `lts`, `current`, or `stable` slice. Filter by `version = '2.0'` by default. Include `blog` only when searching for release notes or design motivation. For DuckLake queries, filter by `version = 'stable'` (covers the 1.1 manual).

The `docs_chunks` table has seven columns: `chunk_id`, `page_title`, `section`, `breadcrumb`, `url`, `version`, and `text`. The `url` column stores a relative path (e.g. `/docs/2.0/...`), not an absolute URL.

## Cache

Store the database at `$HOME/.duckdb/docs/duckdb-docs.duckdb` or `ducklake-docs.duckdb`. When the cache file is missing or older than two days, refresh it:

```bash
mkdir -p "$HOME/.duckdb/docs"
```

```sql
INSTALL httpfs; LOAD httpfs;
INSTALL fts; LOAD fts;
ATTACH 'https://duckdb.org/data/docs-search.duckdb' AS remote (READ_ONLY);
ATTACH '/tmp/docs-refresh.tmp' AS tmp;
COPY FROM DATABASE remote TO tmp;
```

Move the temp file over the cache path (`mv /tmp/docs-refresh.tmp "$HOME/.duckdb/docs/duckdb-docs.duckdb"`).

Always open the cache with `-readonly` and as the main database. Opening as an attached catalog prevents `fts_main_docs_chunks.match_bm25` from resolving unqualified internal schema references. Opening in read-write mode locks out concurrent sessions.

## Query

DuckDB 2.0 rejects filtering on the score alias (`WHERE score IS NOT NULL` or `QUALIFY score IS NOT NULL`) within the same `SELECT` level because `match_bm25` has side effects. Wrap the scoring expression in a subquery or CTE. Direct `ORDER BY score DESC` within the same `SELECT` works.

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

The 2.0 macro accepts ten parameters: `match_bm25(docname, query_string, fields := NULL, k := 1.2, b := 0.75, conjunctive := false, field_weights := NULL, field_b := NULL, scoring_model := 'bm25f', tie_breaker := 0.0)`. The manual page lists only six; the binary and `duckdb_functions()` are authoritative. The indexed fields are `page_title`, `section`, and `text`.

When every term must appear, set `conjunctive := 1`. To boost specific fields, pass `field_weights := {'text': 2.0}`. Options `stemmer`, `stopwords`, and `ignore` belong to `PRAGMA create_fts_index`, not `match_bm25`. Parameter names `bm25_k1` and `bm25_b` do not exist; use `k` and `b`.

### Search term optimization

1. Formulate searches using two or three technical keywords. Strip conversational words ("how", "do").
2. Preserve exact function, setting, and error names as written.
3. If zero rows return, drop the least specific term. If `conjunctive := 1` was set, retry with `0` (the default).

Prefix relative paths in `url` with `https://duckdb.org` or `https://ducklake.select`.

## Answer

Follow this response protocol:
1. Lead with the direct technical answer in one or two sentences.
2. Quote only the exact lines carrying the signature, setting, or operational constraint.
3. Provide the page title and absolute URL citation for each chunk used.

### Fallback protocol

When normal cache query execution is obstructed:
- If the local cache is missing and network connectivity is active, query the hosted index directly with `ATTACH 'https://duckdb.org/data/docs-search.duckdb' AS remote (READ_ONLY); USE remote;`.
- If the network is unreachable, read a stale local cache in `-readonly` mode and issue a staleness warning.
- If neither cache nor network is available, report the failure and direct the user to `https://duckdb.org/docs/2.0/` or `https://ducklake.select/docs/stable/`. Refuse to invent signatures from memory.

## Verify

```bash
duckdb -readonly "$HOME/.duckdb/docs/duckdb-docs.duckdb" -c \
  "LOAD fts; SELECT version, count(*) FROM docs_chunks GROUP BY version;"
```

Expect `2.0` and `blog` rows, with no `lts` or `current` rows. Expect roughly 2,700 `2.0` chunks, 1,000 `blog` chunks, and about 198 DuckLake `stable` chunks. A missing `2.0` or `stable` row is a failure; a count drift indicates an upstream documentation release.

## References

Consult these references when reviewing official search index assets and FTS macro mechanics:

- [DuckDB search index](https://duckdb.org/data/docs-search.duckdb) provides the hosted 2.0 manual and blog index.
- [DuckLake search index](https://ducklake.select/data/docs-search.duckdb) provides the hosted stable DuckLake manual index.
- [Full-text search extension](https://duckdb.org/docs/2.0/core_extensions/full_text_search.html) owns the complete `match_bm25` signature and scoring models.
- [What's new in the 2.0 docs](https://duckdb.org/docs/2.0/whats_new_in_the_docs.html) details documentation structure changes.
