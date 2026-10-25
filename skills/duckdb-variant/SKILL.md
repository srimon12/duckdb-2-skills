---
name: duckdb-variant
description: >
  Store and query semi-structured values with the DuckDB 2.0 VARIANT type.
  Covers casts from JSON, field and list extraction, aggregate builders, and
  Parquet shredding. Use when the user mentions VARIANT, shredded JSON,
  schema-less columns, or variant_typeof.
---

# VARIANT

`VARIANT` is a binary column. Each value carries its own type, so rows in one column can differ. `JSON` is still text. When the column will be filtered, sorted, or projected, use `VARIANT`. When the user needs the original text bytes or the JSON mutation functions, keep `JSON`.

Run SQL with the `duckdb` skill.

## Create and cast

```sql
CREATE TABLE events (id INTEGER, data VARIANT);
INSERT INTO events VALUES
    (1, 42::VARIANT),
    (2, 'hello'::VARIANT),
    (3, [1, 2, 3]::VARIANT),
    (4, {'name': 'Alice', 'age': 30}::VARIANT),
    (5, '{"user": {"id": 42}}'::JSON::VARIANT);
```

Object keys come back sorted. `{'name': 'Alice', 'age': 30}::VARIANT` prints as `{'age': 30, 'name': Alice}`.

A `VARIANT` can sit in a table, a Parquet file, or a Delta table. In Delta it can be written at the top level only; a nested `VARIANT` can be created but not written.

## Load JSON

`read_json` cannot read into a `VARIANT` column. Read the file as `JSON`, then cast. For a repeatable load:

1. Read as `JSON` and cast to `VARIANT`.
2. Profile keys and types on a sample: `SELECT variant_keys(data), variant_typeof(data) FROM ... LIMIT 1000;`
3. Choose shredding fields that are stable scalars and appear in filters. Leave heterogeneous or high-cardinality fields unshredded.
4. Write with the schema in `## Shredding`, or keep the database default for mixed data.
5. Prove the write: compare the row count and `variant_typeof`/`variant_keys` before and after. A mismatched row falls back to the unshredded `value` and still returns.

## Inspect

```sql
SELECT id, variant_typeof(data) AS full_type, variant_type(data) AS category
FROM events;
```

`variant_typeof` returns the full type, such as `INT32`, `VARCHAR`, `ARRAY(3)`, or `OBJECT(age, name)`. `variant_type` returns the physical category, such as `OBJECT`, `BOOL_TRUE`, `INT8` for a `TINYINT`, `INT32` for an `INTEGER`, `DECIMAL`, or `TIMESTAMP_MICROS`. It does not return SQL type names.

| Function | Use |
| --- | --- |
| `variant_typeof(v)` | Full type, including nested fields |
| `variant_type(v [, path])` | Top-level physical category (e.g. `OBJECT`, `INT32`); optional path |
| `variant_keys(v [, path])` | Object keys; `[]` for an array or scalar; optional path |
| `variant_extract(v, field)` | Field or list element, as `VARIANT` |
| `variant_extract_string(v, path)` | Same, as `VARCHAR`; string paths only, non-scalars become JSON text |
| `variant_array_length(v [, path])` | Array length, as `UBIGINT`; `0` for a non-array; optional path |
| `variant_exists(v, path)` | Key present in an object; `false` for an array index |
| `variant_contains(haystack, needle)` | Structural containment, not substring |
| `variant_normalize(v)` | Canonical form, so equal values share a representation |
| `variant_comparator(v)` | Binary sort key for the logical `VARIANT` order |
| `variant_group_object(key, value)` | Aggregate into one object |
| `variant_group_array(x)` | Aggregate into a `VARIANT` array |

SQL NULL and `VARIANT_NULL` are different. `variant_typeof(v) = 'VARIANT_NULL'` detects a variant null. `variant_type` returns SQL NULL for it, and `IS NULL` is true for both. Use `variant_exists` to separate an absent key from a present null.

## Extract

Dot notation matches `variant_extract`.

```sql
SELECT data.user.id FROM events WHERE id = 5;
SELECT variant_extract_string(data, 'name') FROM events WHERE id = 4;
```

List indexes are 1-based. Index `0` raises `Extracting index 0 from VARIANT(ARRAY) is invalid, indexes are 1-based`. Out-of-bounds list indexes and missing object keys return `NULL`.

There is no `variant_concat` function in DuckDB. Applying `||` casts operands to `VARCHAR`. To merge objects, cast to `JSON` and use `json_merge_patch(a::JSON, b::JSON)::VARIANT`.

```sql
SELECT variant_extract([10, 20, 30]::VARIANT, 2);  -- 20
```

`variant_extract` returns `VARIANT` even when the value is a string. `variant_extract_string` only accepts string paths, not list indexes. When the next step needs text, cast with `::VARCHAR` or use `variant_extract_string`.

`VARIANT::VARCHAR` produces DuckDB's literal form, such as `{'a': 1}`. When the next step needs JSON text, use `::JSON::VARCHAR`.

An object with duplicate keys keeps one value. JSON preserves both keys.

## Aggregate

```sql
SELECT variant_group_object(k, v::VARIANT) AS obj
FROM (VALUES ('a', 1), ('b', 2)) AS t(k, v);

SELECT variant_group_array(x) AS arr FROM (VALUES (1), (2)) AS t(x);
```

The value argument to `variant_group_object` must be `VARIANT`. A `NULL` key errors, and a duplicate key errors. `variant_group_array` is equivalent to `list(x)::VARIANT`; it keeps order and `NULL`s, and works as a window function.

## Sorting and equality

Comparisons (`=`, `!=`, `<`, `<=`, `>`, `>=`), `GROUP BY`, and `DISTINCT` work directly on `VARIANT`. Ordering follows a strict type hierarchy: `BOOL` < numeric (`1 = 1.0` is true) < `VARCHAR` < `ARRAY` < `OBJECT` < `VARIANT_NULL`.

```sql
SELECT i FROM range(-2, 2) t(i) ORDER BY i::VARIANT;
```

`=` already compares logical values, so whitespace and key order do not matter. `variant_normalize` produces a canonical representation. When you need the binary sort key itself, use `variant_comparator`.

## Shredding

In a DuckDB database file, 2.0 shreds a `VARIANT` column inside row groups of at least `variant_minimum_shredding_size` rows. The default is 30000. Shredded fields are stored as typed columns.

```sql
SET variant_minimum_shredding_size = -1;  -- off
```

Parquet writes can shred too. The database setting does not gate Parquet shredding; a one-row file still writes the typed structure. Auto-shredding follows the first row group. To force a schema:

```sql
COPY events TO 'events.parquet' (
    FORMAT parquet,
    SHREDDING {'data': 'STRUCT(name VARCHAR, age INTEGER)'}
);
```

DuckDB reads shredded `VARIANT` Parquet, including files Snowflake wrote. `SHREDDING` is a storage hint, not a validation contract. A row that does not match the schema falls back to the unshredded `value` and still round-trips. Extra fields survive. Invalid type names error at bind.

`read_json` cannot read directly into a `VARIANT` column. It binds, then fails at execution. Read as `JSON`, then cast `::VARIANT`.

Delta tables have a separate switch. See `duckdb-lakehouse`.

## JSON mutation

Mutation functions stay on the JSON type. Use them before the cast when the user needs to edit a document.

```sql
SELECT json_set('{"a": 1}'::JSON, '$.a', '2'::JSON) AS updated;
```

`json_set`, `json_insert`, `json_replace`, and `json_remove` take a JSON value, not a bare SQL value. Once the value is `VARIANT`, use `variant_extract` and rebuild with `variant_group_object` or a cast.

## Verify

```sql
SELECT variant_typeof({'a': 1}::VARIANT) AS type,
       variant_extract([10, 20]::VARIANT, 2) AS second,
       variant_keys({'b': 2, 'a': 1}::VARIANT) AS keys;
```

Expect `OBJECT(a)`, `20`, and `[a, b]`.

## References

- [Variant type](https://duckdb.org/docs/2.0/sql/data_types/variant.html) owns storage, shredding, and Parquet.
- [Variant functions](https://duckdb.org/docs/2.0/sql/functions/variant.html) owns the signatures.
- [JSON functions](https://duckdb.org/docs/2.0/data/json/json_functions.html) owns mutation on JSON text.
- [Delta extension](https://duckdb.org/docs/2.0/core_extensions/delta.html) owns the Delta variant rules.
- `variant_typeof`, `variant_type`, `variant_keys`, `variant_extract`, and 1-based list indexing were run on DuckDB 2.0.0. Duplicate and NULL keys in `variant_group_object` were also checked there.
