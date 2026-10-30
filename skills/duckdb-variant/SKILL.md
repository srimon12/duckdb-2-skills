---
name: duckdb-variant
description: >
  Store and query semi-structured values with the DuckDB 2.0 VARIANT type.
  Covers casts from JSON, field and list extraction, aggregate builders, and
  Parquet shredding. Use when storing or querying semi-structured data,
  shredded JSON, schema-less columns, or using variant_typeof.
---

# VARIANT

`VARIANT` is a binary columnar format where each value preserves its individual type, allowing rows within the same column to store distinct data types. `JSON` remains unparsed UTF-8 text. When filtering, projecting, or sorting semi-structured data, use `VARIANT`. When requiring byte-exact raw text preservation or JSON-specific mutation functions, retain `JSON`.

Run SQL queries with `duckdb`.

## Create and cast

To create and populate a `VARIANT` column, cast SQL literals, lists, structs, or parsed JSON text:

```sql
CREATE TABLE events (id INTEGER, data VARIANT);
INSERT INTO events VALUES
    (1, 42::VARIANT),
    (2, 'hello'::VARIANT),
    (3, [1, 2, 3]::VARIANT),
    (4, {'name': 'Alice', 'age': 30}::VARIANT),
    (5, '{"user": {"id": 42}}'::JSON::VARIANT);
```

When displaying VARIANT objects, DuckDB formats keys in sorted alphabetical order: `{'name': 'Alice', 'age': 30}::VARIANT` prints as `{'age': 30, 'name': Alice}`.

VARIANT storage is supported in DuckDB native tables, Parquet files, and Delta tables. In Delta tables, write VARIANT at the top level only; nested VARIANT columns can be defined in schemas but cannot be written.

## Load JSON

Because `read_json` cannot read directly into a `VARIANT` target (binding succeeds but execution fails), ingest documents as `JSON` text first, then cast with `::VARIANT`. For a reliable ingest workflow:

1. Ingest as `JSON` and cast to `VARIANT`: `SELECT json_data::VARIANT FROM read_json('events.json', columns={'json_data': 'JSON'});`.
2. Profile key structures and types on a sample: `SELECT variant_keys(data), variant_typeof(data) FROM events LIMIT 1000;`.
3. Select stable scalar fields accessed in query filters for shredding; keep heterogeneous, deeply nested, or high-cardinality fields unshredded.
4. Apply explicit schema hints during Parquet writes (see `## Shredding`), or rely on DuckDB's automatic database file shredding for mixed workloads.
5. Verify load fidelity: compare row counts and check sample keys before and after ingest. Rows diverging from shredding schemas automatically fall back to the unshredded `value` column without data loss.

## Inspect

To inspect stored VARIANT types and categories:

```sql
SELECT id, variant_typeof(data) AS full_type, variant_type(data) AS category
FROM events;
```

`variant_typeof` returns the full logical type, such as `INT32`, `VARCHAR`, `ARRAY(3)`, or `OBJECT(age, name)`. `variant_type` returns the top-level physical storage category, such as `OBJECT`, `BOOL_TRUE`, `INT8` (for `TINYINT`), `INT32` (for `INTEGER`), `DECIMAL`, or `TIMESTAMP_MICROS`. It does not return SQL type names.

| Function | Description |
| --- | --- |
| `variant_typeof(v)` | Full logical type including nested fields (e.g. `INT32`, `VARCHAR`, `ARRAY`, `OBJECT`) |
| `variant_type(v [, path])` | Physical storage category (e.g. `OBJECT`, `BOOL_TRUE`, `INT8`, `INT32`); optional path |
| `variant_keys(v [, path])` | Object keys as `VARCHAR[]`; returns `[]` for arrays or scalars; optional path |
| `variant_extract(v, field)` | Field or list element as `VARIANT` |
| `variant_extract_string(v, path)` | Field as `VARCHAR` (string paths only; non-scalars render as JSON text) |
| `variant_array_length(v [, path])` | Array length as `UBIGINT`; returns `0` for non-arrays; optional path |
| `variant_exists(v, path)` | Key presence check in an object; returns `false` for array indexes |
| `variant_contains(haystack, needle)` | Structural variant containment (not substring matching) |
| `variant_normalize(v)` | Canonical representation sharing identical binary encoding for equal values |
| `variant_comparator(v)` | Binary sort key reflecting logical VARIANT order |
| `variant_group_object(key, value)` | Aggregate key-value pairs into a single VARIANT object |
| `variant_group_array(x)` | Aggregate expressions into an ordered VARIANT array |

When casting SQL `NULL` to `VARIANT` or parsing JSON `null`, DuckDB yields `VARIANT_NULL`. Both evaluate `IS NULL` to `true` and return SQL `NULL` from `variant_type`; no column-level predicate separates them. To distinguish an absent key from an explicit null inside an object, call `variant_exists(v, path)`.

## Extract

Dot notation provides shorthand for `variant_extract`:

```sql
SELECT data.user.id FROM events WHERE id = 5;
SELECT variant_extract_string(data, 'name') FROM events WHERE id = 4;
SELECT variant_extract([10, 20, 30]::VARIANT, 2);  -- 20
```

When indexing lists within VARIANT, use 1-based indexing. Querying index `0` raises `Extracting index 0 from VARIANT(ARRAY) is invalid, indexes are 1-based`. When list indexes exceed bounds or object keys are absent, DuckDB returns `NULL`.

When extracting text, call `variant_extract_string(v, path)` or cast `variant_extract(...)` with `::VARCHAR`. Note that `variant_extract_string` accepts string paths only, rejecting numeric array indexes.

When serializing to string, distinguish DuckDB literal formatting from JSON text: `v::VARCHAR` produces DuckDB's internal literal syntax (such as `{'a': 1}`), whereas `v::JSON::VARCHAR` produces valid JSON text.

Because DuckDB provides no `variant_concat` function (`||` casts operands to `VARCHAR`), merge objects via JSON: `json_merge_patch(a::JSON, b::JSON)::VARIANT`.

When constructing or casting objects with duplicate keys, `VARIANT` retains only a single value for each key, whereas `JSON` preserves duplicate key tokens.

## Aggregate

To aggregate rows into variant objects or arrays:

```sql
SELECT variant_group_object(k, v::VARIANT) AS obj
FROM (VALUES ('a', 1), ('b', 2)) AS t(k, v);

SELECT variant_group_array(x) AS arr FROM (VALUES (1), (2)) AS t(x);
```

When aggregating key-value pairs with `variant_group_object(key, value)`, cast the value explicitly to `VARIANT`. Supplying a `NULL` key or duplicate keys raises an execution error.

When aggregating values into an array, use `variant_group_array(x)` (equivalent to `list(x)::VARIANT`). It preserves input ordering, retains `NULL` elements, and operates as a window function (`OVER (...)`).

## Sorting and equality

Equality comparisons (`=`, `!=`), ordering (`<`, `<=`, `>`, `>=`), `GROUP BY`, and `DISTINCT` operate directly on `VARIANT` values without manual casting:

```sql
SELECT i FROM range(-2, 2) t(i) ORDER BY i::VARIANT;
```

Logical comparison ignores formatting whitespace and key ordering across equivalent objects. When comparing or sorting across mixed data types, DuckDB enforces a strict type hierarchy:

`BOOL` < numeric (`1 = 1.0` evaluates to true) < `VARCHAR` < `ARRAY` < `OBJECT` < `VARIANT_NULL`.

When requiring an identical binary representation for logically equal values, call `variant_normalize(v)`. When generating an explicit binary sort key for custom ordering routines, call `variant_comparator(v)`.

## Shredding

In native DuckDB database files, 2.0 shreds a `VARIANT` column into typed storage columns within row groups containing at least `variant_minimum_shredding_size` rows (default 30000). To disable native shredding:

```sql
SET variant_minimum_shredding_size = -1;  -- off
```

When writing to Parquet, DuckDB shreds variant columns independently of `variant_minimum_shredding_size`; even a single-row file writes typed sub-columns. Automatic shredding derives types from the first row group. To enforce an explicit schema, specify the `SHREDDING` copy option:

```sql
COPY events TO 'events.parquet' (
    FORMAT parquet,
    SHREDDING {'data': 'STRUCT(name VARCHAR, age INTEGER)'}
);
```

DuckDB reads shredded `VARIANT` Parquet files, including those written by Snowflake. Note that `SHREDDING` serves as a storage layout hint rather than a validation contract: unmatched rows fall back to the unshredded `value` column and round-trip successfully, extra fields survive without truncation, and invalid type names fail at bind time.

For Delta table variant shredding configurations, consult `duckdb-lakehouse`.

## Parquet layout and views

Projection pushdown into a Parquet scan requires explicitly naming the target nested field. A `SELECT *` view encapsulates the query and loses pushdown, causing full-column reads:

```sql
CREATE VIEW v AS SELECT * FROM 'events.parquet';
SELECT sum(length(data.payload.action::VARCHAR)) FROM v;                 -- slow (reads entire variant)
SELECT sum(length(data.payload.action::VARCHAR)) FROM 'events.parquet'; -- fast (pushes down projection)
```

To preserve pushdown performance, define views with explicit extracted fields:

```sql
CREATE VIEW v AS
SELECT id, data.payload.action AS action FROM read_parquet('events/*.parquet');
```

Partitioning files by homogeneous shape families accelerates direct reads when fields are uniformly shreddable. When a file omits the field or stores an incompatible type, DuckDB falls back to the unshredded `value` column. Verify pushdown optimizations by checking the `EXPLAIN` projection plan rather than relying solely on timing benchmarks.

## JSON mutation

Because mutation functions operate exclusively on JSON text, apply edits before casting to `VARIANT`:

```sql
SELECT json_set('{"a": 1}'::JSON, '$.a', '2'::JSON) AS updated;
```

The functions `json_set`, `json_insert`, `json_replace`, and `json_remove` require JSON-typed arguments rather than bare SQL values. Once data is stored as `VARIANT`, mutate values by extracting fields with `variant_extract` and rebuilding via `variant_group_object`, or cast back to `JSON` for patching.

## Verify

Execute an inline query to validate type reflection, 1-based extraction, and key ordering:

```sql
SELECT variant_typeof({'a': 1}::VARIANT) AS type,
       variant_extract([10, 20]::VARIANT, 2) AS second,
       variant_keys({'b': 2, 'a': 1}::VARIANT) AS keys;
```

Confirm expected outputs: `type` returns `OBJECT(a)`, `second` returns `20`, and `keys` returns `[a, b]`.

## References

- [Variant type](https://duckdb.org/docs/2.0/sql/data_types/variant.html) details internal storage formats, shredding thresholds, and Parquet mechanics.
- [Parquet overview](https://duckdb.org/docs/2.0/data/parquet/overview.html) documents projection pushdown and nested variant scanning.
- [Variant functions](https://duckdb.org/docs/2.0/sql/functions/variant.html) specifies full function signatures and extraction behaviors.
- [JSON functions](https://duckdb.org/docs/2.0/data/json/json_functions.html) covers text-based JSON mutation and JSON path functions.
- [Delta extension](https://duckdb.org/docs/2.0/core_extensions/delta.html) defines Delta table variant column constraints.
- Introspection functions (`variant_typeof`, `variant_type`, `variant_keys`, `variant_extract`), 1-based indexing, and `variant_group_object` NULL/duplicate key validation verified on DuckDB 2.0.0.
