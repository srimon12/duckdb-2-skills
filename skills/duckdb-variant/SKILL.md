---
name: duckdb-variant
description: >
  Store and query semi-structured values with the DuckDB 2.0 VARIANT type:
  casts from JSON, field extraction, shredding, and Parquet. Use when the user
  mentions VARIANT, shredded JSON, schema-less columns, or variant_typeof.
  Use /duckdb-variant.
---

# VARIANT

`VARIANT` is a binary column. Each value carries its own type, so rows in one column can differ. The `JSON` type is still text. Prefer `VARIANT` when the column will be filtered or projected. Keep `JSON` when the user needs the original text bytes.

Run SQL with the `duckdb` skill.

## Create and load

```sql
CREATE TABLE events (id INTEGER, payload VARIANT);
INSERT INTO events VALUES
    (1, 42::VARIANT),
    (2, 'hello'::VARIANT),
    (3, [1, 2, 3]::VARIANT),
    (4, {'name': 'Alice', 'age': 30}::VARIANT),
    (5, '{"user": {"id": 42}}'::JSON::VARIANT);
```

Object keys come back sorted. `{'name': 'Alice', 'age': 30}::VARIANT` prints as `{'age': 30, 'name': Alice}`.

## Inspect

`variant_typeof` returns the full type, such as `OBJECT(age, name)` or `ARRAY(3)`. `variant_type` returns only the category, such as `OBJECT`.

```sql
SELECT variant_typeof(payload), variant_type(payload), variant_keys(payload)
FROM events;
```

Extraction returns `VARIANT` from `variant_extract` and `VARCHAR` from `variant_extract_string`. Dot notation matches `variant_extract`.

```sql
SELECT payload.user.id FROM events WHERE id = 5;
SELECT variant_extract_string(payload, 'name') FROM events WHERE id = 4;
```

| Function | Use |
| --- | --- |
| `variant_typeof(v)` | Full type, including nested fields |
| `variant_type(v)` | Top-level category only |
| `variant_keys(v)` | Object keys |
| `variant_extract(v, field)` | Field or list element, as `VARIANT` |
| `variant_extract_string(v, field)` | Same, as `VARCHAR` |
| `variant_array_length(v)` | Array length |
| `variant_exists(v, key)` | Key present |
| `variant_contains(haystack, needle)` | Needle `VARIANT` occurs in the haystack |
| `variant_group_object(key, value)` | Aggregate into one object. `NULL` or duplicate keys error |
| `variant_group_array(x)` | Aggregate into a `VARIANT` array. Same as `list(x)::VARIANT` |

`variant_normalize` and `variant_comparator` are for equality and sort order. Look them up on the functions page before using them in a predicate you have not tested.

The functions page does not say whether `variant_extract` indexes lists from 0 or from 1. Project a sample row before relying on an index.

## Shredding

In a DuckDB database file, 2.0 shreds a `VARIANT` column inside row groups of at least `variant_minimum_shredding_size` rows. The default is 30000. Shredded fields are stored as typed columns.

```sql
SET variant_minimum_shredding_size = -1;  -- off
```

Parquet writes can shred too. Auto-shredding follows the structure DuckDB sees. To force a schema:

```sql
COPY events TO 'events.parquet' (
    FORMAT parquet,
    SHREDDING {'payload': 'STRUCT(name VARCHAR, age INTEGER)'}
);
```

DuckDB reads shredded `VARIANT` Parquet, including files Snowflake wrote. The docs do not say what happens when later rows do not match a `SHREDDING` schema. Check a sample after the copy.

Delta tables have a separate shredding switch. See `duckdb-lakehouse`.

## References

- https://duckdb.org/docs/2.0/sql/data_types/variant.html
- https://duckdb.org/docs/2.0/sql/functions/variant.html
- https://duckdb.org/2026/10/21/announcing-duckdb-200.html
- `variant_typeof`, `variant_type`, `variant_keys`, and `variant_extract` were present in DuckDB 2.0.0 `duckdb_functions()`. The examples above are from the 2.0 type and function pages.
