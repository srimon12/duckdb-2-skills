# Full-text search reference

Read this when the skill needs the exact FTS parameters, freshness contract, or an update repair.

## Create an index

```sql
PRAGMA create_fts_index(
    'main.docs', 'id', 'body', 'title',
    stemmer = 'porter',
    stopwords = 'english',
    ignore = '(\\.|[^a-z])+',
    strip_accents = 1,
    lower = 1,
    overwrite = 0,
    incremental = 0
);
```

| Parameter | Default | Use |
| --- | --- | --- |
| `input_table` | required | Qualified table name. |
| `input_id` | required | Document id column. |
| `input_values` | required | One or more `VARCHAR` columns, or `'*'` for all text columns. |
| `stemmer` | `porter` | Language stemmer, or `none`. |
| `stopwords` | `english` | `english`, `none`, or a one-column table of words. |
| `ignore` | `(\\.|[^a-z])+` | Regex of characters to discard. |
| `strip_accents` | `1` | Fold accents before indexing. |
| `lower` | `1` | Lowercase before indexing. |
| `overwrite` | `0` | Replace an existing index. |
| `incremental` | `0` | Add triggers for `INSERT` and `DELETE`. |

The index lives in a schema named `fts_main_<table>`. Drop it with `PRAGMA drop_fts_index('main.docs');`.

## Query

```sql
SELECT id, title, score
FROM (
    SELECT id, title, fts_main_docs.match_bm25(id, 'duck database') AS score
    FROM docs
) t
WHERE score IS NOT NULL
ORDER BY score DESC;
```

`match_bm25(input_id, query_string, fields := NULL, k := 1.2, b := 0.75, conjunctive := 0)` returns a score. `fields` limits the search to named indexed columns. `conjunctive = 1` requires every term.

The alias has side effects. Filtering or qualifying it in the same `SELECT` that computes it raises:

```text
Binder Error: Alias "score" referenced - but the expression has side effects
```

Use the subquery above.

## Freshness

Without `incremental = 1`, the index does not change when the table changes. Rebuild with `overwrite = 1` or drop and recreate.

With `incremental = 1`, triggers maintain the index for `INSERT` and `DELETE`. They do not cover `UPDATE`. An updated row keeps the old terms searchable and the new terms missing.

Repair an update with a delete and insert:

```sql
DELETE FROM docs WHERE id = 2;
INSERT INTO docs VALUES (2, 'new body');
```

`INSERT ... ON CONFLICT DO UPDATE` and `INSERT OR REPLACE` fail on an incremental FTS table with the trigger conflict error. Rebuild on a schedule when updates dominate.

The id must be declared `NOT NULL` or `PRIMARY KEY`. `UNIQUE` alone is not enough because the column can still be `NULL`. Duplicate ids fail at creation with a unique-constraint error.

## Cost and proof

The first build reads the indexed columns and writes a new schema. `overwrite = 1` rebuilds from scratch. A rebuild is proportional to the table size; an incremental trigger is proportional to the changed rows.

Prove freshness after a write:

```sql
SELECT count(*) FROM (
    SELECT id, fts_main_docs.match_bm25(id, 'newterm') AS score FROM docs
) WHERE score IS NOT NULL;
```

A new insert must return at least one row. A deleted term must return zero. An updated term must be repaired before it passes.

## References

- https://duckdb.org/docs/2.0/core_extensions/full_text_search.html
- https://duckdb.org/docs/2.0/guides/sql_features/full_text_search.html
- https://duckdb.org/docs/2.0/sql/statements/create_trigger.html
