# Full-text search reference

Read this when the skill needs the exact FTS parameters, query semantics, layered search, freshness contract, or an update repair.

Behavior below was probed on DuckDB 2.0.0 with fts `223b8cb9e6`. The official 2.0 page is older than the extension and omits `tokenizer`, `cluster_terms`, `layered_search`, `field_weights`, `field_b`, `scoring_model`, and `tie_breaker`.

## Create an index

```sql
PRAGMA create_fts_index(
    'main.docs', 'id', 'body', 'title',
    stemmer = 'porter',
    tokenizer = 'regex',
    stopwords = 'english',
    strip_accents = 1,
    lower = 1,
    overwrite = 0,
    incremental = 0,
    cluster_terms = 0,
    layered_search = 0
);
```

| Parameter | Default | Use |
| --- | --- | --- |
| `input_table` | required | Qualified base table. `'t'`, `'schema.t'`, or `'catalog.schema.t'`. |
| `input_id` | required | Id column. The value, not the column name, is passed to `match_bm25`. |
| `input_values` | required | One or more text columns. `'*'` means every `VARCHAR` column, including a `VARCHAR` id. |
| `stemmer` | `porter` | Snowball stemmer name, or `none`. |
| `tokenizer` | `regex` | `regex` or `opensearch_standard`. |
| `stopwords` | `english` | `english`, `none`, or a one-column table of words. |
| `ignore` | punctuation and digits | Delimiter regex. Characters that match are separators, not removed text. |
| `strip_accents` | `1` | Fold accents before lowercasing. Not supported with `opensearch_standard`. |
| `lower` | `1` | `0` makes the index and the query case-sensitive. |
| `overwrite` | `0` | Drop the old index schema and triggers, then rebuild. |
| `incremental` | `0` | Add triggers for `INSERT` and `DELETE`. |
| `cluster_terms` | `0` | Physically order the terms table. Implied by `layered_search`. |
| `layered_search` | `0` | Add dictionary sidecar tables and the layered search macros. |

The index is a schema named `fts_<schema>_<table>`. `main.docs` becomes `fts_main_docs`; `sales.docs` becomes `fts_sales_docs`. Two table names can collide after flattening, for example `a.b_c` and `a_b.c`. The base index has `dict`, `docs`, `fields`, `stats`, `stopwords`, and `terms`. Layered search adds `raw_dict`, `term_stats`, `term_stats_by_len`, `term_grams`, and `term_prefixes`.

A static index stores `docid` as the base-table row id at build time. It is a snapshot. An `UPDATE` does not move the row, and the index never re-reads the row. Indexes on views are rejected with `Catalog Error: <view> is not an table`. Indexes on temp tables and non-main schemas work.

## Id contract

The id must be `NOT NULL` and unique.

- A static index accepts a nullable id. The NULL row is stored but never returned because the join compares `NULL`.
- A static index accepts duplicate ids. A later `match_bm25` can fail with `More than one row returned by a subquery used as an expression`.
- An incremental index rejects a nullable id: `Invalid Input Error: incremental FTS indexes require the document id column to be NOT NULL`.
- An incremental index rejects duplicate ids at commit: `TransactionContext Error: Failed to commit: PRIMARY KEY or UNIQUE constraint violation: duplicate key "1"`.

Declare the id `NOT NULL UNIQUE` or `PRIMARY KEY` before building any index.

## Query

```sql
SELECT id, bm25
FROM (
    SELECT id, fts_main_docs.match_bm25(id, 'duck database') AS bm25
    FROM docs
) t
WHERE bm25 IS NOT NULL
ORDER BY bm25 DESC;
```

`match_bm25(input_id, query_string, fields := NULL, k := 1.2, b := 0.75, conjunctive := false, field_weights := NULL, field_b := NULL, scoring_model := 'bm25f', tie_breaker := 0.0)`.

Terms are OR by default. `conjunctive := 1` requires every term that survives tokenization, stopword removal, and stemming. There is no boolean, phrase, wildcard, or negation parser in `match_bm25`:

| Query | Result |
| --- | --- |
| `duck database` | Documents with `duck`, `database`, or both. |
| `duck AND database` | Same as `duck database`; `and` is a stopword. |
| `"duck database"` | Same as `duck database`; quotes are delimiters. |
| `duck -database` | Same as `duck database`; `-` is a delimiter. |
| `databas*` | No prefix match; `*` is stripped. |
| `duckling` | A separate term from `duck`. |

Use a layered index for prefix, substring, fuzzy, autocomplete, or boolean queries.

Filter the score in a subquery. A same-select filter or `QUALIFY` raises:

```text
Binder Error: Alias "score" referenced - but the expression has side effects
```

`ORDER BY score` in the same select works, but the outer `WHERE` does not. If the table already has a `score` column, alias the function as `bm25`. Two `score` columns make the outer filter read the table column and return the wrong rows.

A query with no score filter returns every row, with NULL for non-matches. `ORDER BY score DESC` keeps NULLs. Always filter.

Scores are unbounded and corpus-dependent. A rare term can score 4.82 and a common term 0.0000065. Rank, never threshold.

`fields := 'title,body'` is a comma-separated string, trimmed and matched case-sensitively. An unknown field returns zero rows without an error. `fields := 'Title'` is not the same as `fields := 'title'`. `fields := ''` returns zero rows.

## Scoring

BM25F is the default for single-field and multi-field indexes. It normalizes term frequency per field, combines fields with weights, and applies BM25 saturation once. A single-field index reduces to ordinary BM25.

| Parameter | Effect |
| --- | --- |
| `k` | Saturation. `0` makes every hit score equally. |
| `b` | Length normalization from `0` to `1`. Outside the range is an error. |
| `field_weights` | `MAP(VARCHAR, DOUBLE)`. Omitted fields weigh `1.0`. Unknown fields error. |
| `field_b` | Per-field `b`, from `0` to `1`. Omitted fields inherit `b`. |
| `scoring_model` | `bm25f` or `best_fields`. |
| `tie_breaker` | Only with `best_fields`, from `0` to `1`. |

`best_fields` uses `max(field_score) + tie_breaker * (sum(field_score) - max(field_score))`.

```sql
SELECT docname, score
FROM fts_main_docs.search_layered_bm25(
    'mark',
    field_weights := MAP {'author': 4.0, 'body': 1.0},
    field_b := MAP {'author': 0.3, 'body': 0.8},
    scoring_model := 'best_fields',
    tie_breaker := 0.1,
    top_k := 10
);
```

## Freshness

Without `incremental = 1`, the index does not change when the table changes. Rebuild with `overwrite = 1`, or drop and recreate.

With `incremental = 1`, triggers maintain the index for `INSERT` and `DELETE`. They do not cover `UPDATE`. An updated row keeps the old terms searchable and the new terms missing. An updated id leaves the index keyed to the old id.

Incremental indexes have two extra gates:

- The document id must be `NOT NULL` and unique.
- A persistent database must use storage version `v2.0.0` or newer.

The storage error is exact:

```text
Invalid Input Error: incremental FTS indexes require trigger support. Persistent DuckDB databases must use storage version v2.0.0 or higher; reattach/create the database with STORAGE_VERSION 'v2.0.0', or omit incremental=true to create a rebuild-only FTS index.
```

Repair an update with delete and insert:

```sql
DELETE FROM docs WHERE id = 2;
INSERT INTO docs VALUES (2, 'new body');
```

`INSERT ... ON CONFLICT DO UPDATE` and `INSERT OR REPLACE` fail on an incremental table:

```text
Not implemented Error: ON CONFLICT DO UPDATE is not yet supported with REFERENCING NEW TABLE AS triggers
```

`MERGE INTO` fails too:

```text
Not implemented Error: MERGE INTO is not supported on tables with triggers
```

`ON CONFLICT DO NOTHING` and `COPY FROM` work. Rebuild on a schedule when updates dominate.

`CREATE OR REPLACE TABLE` leaves the old index schema and its triggers behind. The new table can return matches from the old text. Rebuild with `overwrite = 1` after replacing a table.

Dropping the base table leaves the index schema orphaned. `PRAGMA drop_fts_index('old_table')` still removes it. Renaming an incrementally indexed table fails with `Dependency Error: Cannot alter entry ... because there are entries that depend on it`.

## Tokenization

The defaults are tuned for prose, not code.

| Shape | What happens | Correct move |
| --- | --- | --- |
| `2.0`, `s3`, `2024` | Digits are delimiters. The terms disappear. | Set `ignore` to keep digits. |
| `name`, `value`, `where`, `only` | In the 571-word English stopword list. A document of only stopwords indexes nothing. | `stopwords = 'none'`. |
| `user_id`, `fts_main_docs` | Punctuation and underscore split identifiers. | Index a normalized copy, or use `stemmer = 'none'` and a custom `ignore`. |
| `databases` | Porter stems to `databas`. | Keep `porter` for prose. |
| `duckling` | Separate from `duck`. Stemming is not prefix matching. | Use layered search for prefixes. |
| `DuckDB2` | Lowercased and split on the digit by default. | Custom `ignore` when versions matter. |

For code, API names, and logs:

```sql
PRAGMA create_fts_index(
    'docs', 'id', 'body',
    stemmer = 'none',
    stopwords = 'none',
    ignore = '[^a-z0-9_.-]+',
    overwrite = 1
);
```

`'*'` indexes every `VARCHAR` column, including a `VARCHAR` id. Name columns explicitly. An explicit non-`VARCHAR` column is cast and indexed; `'*'` skips it.

## Layered search

`layered_search = 1` builds dictionary sidecar tables and installs four macros:

```sql
PRAGMA create_fts_index(
    'docs', 'id', 'body',
    stemmer = 'none',
    stopwords = 'none',
    layered_search = 1,
    incremental = 1
);

SELECT docname, score, rank
FROM fts_main_docs.search_layered_bm25('quac', top_k := 10);
```

`search_layered_bm25(query_string, fields := NULL, top_k := 50, ...)` returns `docname`, `score`, and `rank`. `match_layered_bm25(input_id, query_string, ...)` is the scalar form.

Expansion controls are `term_limit` (default 32), `max_df_ratio` (0.15), `max_df` (50000), `enable_prefix`, `enable_substring`, `enable_fuzzy`, `enable_short_fuzzy`, and `expand_exact_terms` (false). `query_mode := 'autocomplete'` keeps preceding tokens exact and matches the final token by raw prefix. The final token needs at least two characters.

Exact dictionary terms are always included. Prefix, substring, and fuzzy alternatives get lower expansion weights before BM25 scoring. Numeric query terms are exact and excluded from trigram expansion. A query of only stopwords returns nothing.

For boolean queries, load `json` before creating the index. Then use `search_layered_bm25_query` with a JSON tree:

```sql
LOAD json;

SELECT docname, score, rank
FROM fts_main_docs.search_layered_bm25_query(
    '{
        "must": [{"query": "quack", "fields": ["body"]}],
        "should": [{"query": "han", "fields": ["author"], "query_mode": "autocomplete", "boost": 2.0}],
        "must_not": [{"query": "archive"}],
        "minimum_should_match": 0
    }'::JSON,
    top_k := 10
);
```

A group with at least one `must` clause defaults `minimum_should_match` to zero. A should-only group defaults to one. Setting it to zero on a should-only group matches every indexed document with score `0`. Empty groups, pure-negative groups, unknown keys, and out-of-range boosts are rejected. Defaults are 1024 leaves and depth 64.

For an existing layered index created before `json` was loaded, install the macros with `PRAGMA create_fts_boolean_query_macros('docs')`. They reuse the existing index; no rebuild.

Layered indexes are still snapshots unless `incremental = 1`. Incremental triggers maintain the sidecars for `INSERT` and `DELETE`, not `UPDATE`.

## Cost and proof

Build cost scales with text and postings, not row count alone. A 100k-document, 65 MB text fixture with 10.2M postings built in 10.3 s at one thread and 9.6 s at eight, effectively serial. The index was about 22 MB, roughly 0.34 times the raw text. A query over 100k rows with 500 hits took 0.08 s.

The build respects `memory_limit`. A 50 MB limit failed with `Out of Memory Error` on that fixture; 100 MB passed. Budget at least twice the indexed text.

A rebuild takes an exclusive file lock. A reader blocks the rebuild and the rebuild blocks the reader:

```text
IO Error: Could not set lock on file "...": Conflicting lock is held in ...
```

`overwrite = 1` inside a transaction works. `ROLLBACK` restores the previous index; `COMMIT` publishes the rebuild.

The official `EXPLAIN` does not show an FTS operator. The index is ordinary tables read by a macro. Prove use with results, not a plan:

```sql
SELECT count(*) FROM (
    SELECT id, fts_main_docs.match_bm25(id, 'newterm') AS bm25 FROM docs
) WHERE bm25 IS NOT NULL;
```

A new insert must return at least one row. A deleted term must return zero. An updated term must be repaired before it passes.

## References

- https://duckdb.org/docs/2.0/core_extensions/full_text_search.html
- https://github.com/duckdb/duckdb-fts
- https://duckdb.org/docs/2.0/sql/statements/create_trigger.html
- https://duckdb.org/docs/2.0/sql/functions/array.html
