# Slice: search and dbt workflows

Status: complete on 2026-10-28. Scope: turn the first `duckdb-search` and `duckdb-dbt` drafts into workflow skills. Sources: DuckDB 2.0.0 `d54cbbe3df`, fts `223b8cb9e6`, vss `3685131eac`, dbt `2.0.9`, `dbt-duckdb` `1.11.1`, `dbc` `0.3.1`, official docs, extension READMEs, and local probes.

## Verified facts

### Full text

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| S1 | `incremental = 1` on a persistent database requires storage `v2.0.0` or newer. | Probe: old `v1.5.0+` file raised `incremental FTS indexes require trigger support ... STORAGE_VERSION 'v2.0.0'`. | Probed |
| S2 | `match_bm25` terms are OR by default. `conjunctive := 1` requires every term. | Probe: `duck database` returned 3 docs; `conjunctive := 1` returned 1. | Probed |
| S3 | `match_bm25` has no boolean, phrase, wildcard, or negation syntax. Quotes, `-`, and `*` are delimiters. | Probe: `"duck database"`, `duck -database`, and `databas*` matched the same set or zero. | Probed |
| S4 | The default `ignore` pattern strips digits. | Probe: `2.0` and `s3` returned zero; a custom `ignore` kept digits. | Probed |
| S5 | English stopwords include `name`, `value`, `where`, `only`, and other code identifiers. | Source `duckdb-fts` stopword list; probe of code-like text. | Probed |
| S6 | `fields` is a comma-separated string, case-sensitive, and an unknown field returns zero rows without an error. | Probe: `fields := 'title,body'` worked; `'Title'` returned zero. | Probed |
| S7 | A static index accepts NULL and duplicate ids, then silently drops NULL rows or returns duplicate rows. An incremental index rejects both. | Probe: NULL id built and was never returned; duplicate id failed at query with `More than one row returned`. Incremental raised `NOT NULL` and unique errors at creation. | Probed |
| S8 | A table column named `score` collides with the BM25 alias and makes the outer filter read the table column. | Probe: outer `WHERE score IS NOT NULL` kept rows with table score `5.0`. | Probed |
| S9 | `CREATE OR REPLACE TABLE` leaves the old index schema and triggers behind. The new table can return stale matches. | Probe: old term still matched after replace. | Probed |
| S10 | An incremental `UPDATE` leaves the old term searchable and the new term missing. Upsert and `MERGE` are blocked by triggers. | Probe: old=1, new=0; `ON CONFLICT DO UPDATE` and `MERGE INTO` raised Not-implemented errors. | Probed |
| S11 | A layered index adds prefix, substring, fuzzy, autocomplete, and JSON boolean queries. | Probe: `layered_search=1`; `search_layered_bm25('quack')` matched `quacking`; boolean `must dog` returned one row. | Probed |
| S12 | FTS build is effectively serial and retains a file lock. | 100k docs / 65 MB / 10.2M postings: 10.3 s at 1 thread, 9.6 s at 8; index about 22 MB; 50 MB `memory_limit` OOM. | Probed |

### Vector

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| V1 | HNSW keys must be `FLOAT[N]`. `DOUBLE[N]` and `INTEGER[N]` fail. | Probe: `Binder Error: HNSW index key type must be one of: 'FLOAT[N]'`. | Probed |
| V2 | NULL vectors are never indexed. A `LIMIT k` query can return fewer than `k` rows. | Probe: 3 rows with one NULL returned 2; brute force returned 3. | Probed |
| V3 | Zero vectors are indexed and cosine distance is `nan`. | Probe: `array_cosine_distance([0,0,0],[1,0,0])` returned `nan`. | Probed |
| V4 | The query vector must be a literal `FLOAT[N]`. `::DOUBLE[N]`, prepared `$1`, and scalar subqueries silently fall back to a scan. | Probe: plan showed HNSW for the cast literal, no HNSW for `DOUBLE` or subquery. | Probed |
| V5 | A tie-breaker, ordinal `ORDER BY 1`, `DESC`, missing `LIMIT`, and `LIMIT (SELECT k)` remove HNSW acceleration. | Probe: `EXPLAIN` lost `Hnsw Index Scan`. | Probed |
| V6 | `hnsw_prefilter` defaults true. Setting it false on a selective filter returned zero rows. | Probe: 300k rows, 300 matches, `LIMIT 10`; false returned 0. | Probed |
| V7 | `LIMIT ... OFFSET` repeats the first page on 2.0.0. | Probe: indexed page 2 `[1,2]`; brute force `[3,4]`. | Probed |
| V8 | The index is outside `memory_limit`, serialized on checkpoint, and needs a rebuild after a large delete. `hnsw_compact_index` did not reclaim capacity. | Probe: 589 MB index under `memory_limit=100MB`; compact left counts unchanged after 90 percent delete. | Probed |
| V9 | A crash with a dirty HNSW table can leave an index that fails on first open. | Probe: `kill -9`, then `INTERNAL Error: Operation requires a flat or constant vector`; `DROP INDEX` and `CREATE INDEX` repaired it. | Probed |
| V10 | `pragma_hnsw_index_info()` takes no arguments and reports metric, dimensions, count, capacity, and approximate memory. | Probe: returned one row for the index. | Probed |
| V11 | RRF over FTS and HNSW runs on 2.0.0. Row numbers must sit outside the `match_bm25` select and each leg needs a literal `LIMIT`. | Probe: 4-row fixture returned `[1,3,2,4]`; 20k-row fixture stable. | Probed |

### dbt

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| D1 | dbt 2.0.9 is a Rust binary with a thin Python shim. `dbt --version` prints one line and no adapter list. | `dbt --version`; wheel has `_core.abi3.so`; `dbt debug` reports `duckdb (remote)`. | Probed |
| D2 | The bundled ADBC driver at 2.0.9 is DuckDB 1.5.4 and cannot read storage 69. | Clean cache: `dbt show --inline "select version()"` returned `v1.5.4`; opening a 2.0 file raised `version number 999 ... between 64 and 68`. 1.5.4 is in the 1.5.5-and-earlier group that prints the raw header field `999`; 1.5.6 prints `69`. | Probed |
| D3 | The bundled driver writes a storage-64 (`v1.0.0+`) file. A system driver writes `v2.0.0+`. | Probe: `tags['storage_version']` and header on each file. | Probed |
| D4 | At dbt 2.0.9 a system driver installed with `dbc` won over the bundled driver. | Probe: `dbc install duckdb`; `dbt show` returned `v2.0.0`; uninstall returned `v1.5.4` and the storage error. Driver order is not guaranteed across dbt releases. | Probed |
| D5 | The bundled driver loaded `httpfs`, `spatial`, `fts`, `vss`, and `ducklake` in a probe, contrary to the setup docs. | `duckdb_extensions()` reported loaded and installed for each. | Probed vs documented |
| D6 | dbt v2 has no profile key for storage version. `settings.storage_compatibility_version` is applied after attach and does not create an old file. | Probe: file header stayed 999; `SET storage_version` is not a DuckDB setting. | Probed |
| D7 | `external` models write one file. The parent directory must exist. A directory `location` errors. | Probe: `out/ext.parquet`; missing parent raised `No such file or directory`; trailing slash raised `Is a directory`. | Probed |
| D8 | Python models and materialized views fail. Seeds, snapshots, tables, views, and incremental models work. | Probe: exact `Python models are not supported` and `get_create_materialized_view_as_sql has not been implemented`. | Probed |
| D9 | `merge` and `delete+insert` without `unique_key` silently append. | Probe: merge emitted `ON (FALSE)`; rerun added rows. | Probed |
| D10 | Duplicate source keys abort a merge. | Probe: `MERGE INTO command cannot affect the same target row more than once`. | Probed |
| D11 | Two dbt processes on one file fail on the lock. Threads inside one process work. | Probe: parallel `dbt run`; exact `Could not set lock on file`. | Probed |
| D12 | Without `schema` in the profile, dbt 2.0.9 renders `this` as `<db>.public.<model>` during hook compilation while the model lands in `main`. | Probe: hook log `"h"."public"."m"`; executed hook SQL and table in `main`; adding `schema: main` made both `main`. | Probed |
| D13 | `dbt docs generate` executes nodes and can replace `run_results.json`; use `--write-catalog` for `catalog.json`. | Probe: 23 nodes executed, empty run results, info schema Parquet written. | Probed |
| D14 | `--compute inline` and `sidecar` fall back to remote for DuckDB and break ad-hoc `duckdb_*` functions. | Probe: warning plus `TableFunctionResolutionFailed`. | Probed |

## Existing skill audit

| Skill | Finding | Verdict |
| --- | --- | --- |
| `duckdb-search` | Missing layered search, query semantics, code tokenization, storage gate, NULL/zero vectors, prefilter, literal-vector rule, compaction reality, hybrid ranking. | Rewrite |
| `duckdb-dbt` | Wrong storage pin advice, no driver proof, extension claim from docs only, no materialization matrix, no silent `merge` failure, no lock error, no hook schema trap. | Rewrite |
| `duckdb-migrate/references/clients.md` | Repeated the false storage pin advice. | Fix and link `duckdb-dbt`. |

## Decisions

- Add layered FTS and hybrid ranking. Both are executable on 2.0.0 and change the first command for prefix, fuzzy, or mixed retrieval. Keep the official page's omissions in the reference, not the skill body.
- Add `references/project.md` to `duckdb-dbt`. The profile, materialization, and error matrices are lookup tables. The skill body keeps the decisions.
- Add `references/hybrid.md` to `duckdb-search`. RRF is a composition with its own proof and evaluation.
- Correct the storage pin advice. dbt v2 cannot create a pre-2.0 file through the profile. Convert with the CLI before dbt opens the file.
- Correct the extension claim. Docs and binary disagree at 2.0.9. State both and make the version query the proof.
- Keep dbt probes manual. `scripts/probe.py` requires only the DuckDB CLI; adding a dbt dependency would break the default verification path.

## Traps

| Trap | What happens | Correct move | Evidence |
| --- | --- | --- | --- |
| Incremental FTS on an old file | Build fails after index creation starts | Reattach with `STORAGE_VERSION 'v2.0.0'`, or omit `incremental` | S1 |
| Search syntax in `match_bm25` | Quotes, `-`, `*`, and `AND` are treated as text or delimiters | Use `conjunctive` or a layered index | S2, S3 |
| Default tokenization on code | Digits and identifiers disappear | `stemmer='none'`, `stopwords='none'`, custom `ignore` | S4, S5 |
| Static index with duplicate ids | Query errors or duplicate rows | Add `NOT NULL UNIQUE` before indexing | S7 |
| `score` column | Outer filter reads the wrong column | Alias as `bm25` | S8 |
| `CREATE OR REPLACE TABLE` | Old index matches new data | Rebuild with `overwrite=1` | S9 |
| `UPDATE` on incremental FTS | Old term remains, new term missing | Delete and insert, or rebuild | S10 |
| `DOUBLE[N]` index | Binder error | Cast the column to `FLOAT[N]` | V1 |
| NULL vectors | Fewer rows than `LIMIT` | Reject NULL before insert | V2 |
| Zero vectors | NaN distance | Reject zero and non-finite vectors | V3 |
| Prepared or subquery vector | Silent sequential scan | Inline a literal | V4 |
| `hnsw_prefilter=false` | Zero rows on a selective filter | Keep the default true | V6 |
| `OFFSET` on HNSW | Repeated page | Fetch `k + offset` and slice | V7 |
| `merge` without `unique_key` | Silent append | Set the key and assert the row count | D9 |
| Hook uses `this` without `schema` | Hook targets `public`, model is in `main` | Set `schema` in the profile | D12 |
| Two dbt processes | Lock error | One writer per file | D11 |

## Probe log

```text
$ dbt --version
dbt 2.0.9

$ dbt debug
Debugging adapter type: duckdb (remote)
Debugged All checks passed!

$ dbt show --inline "select version()"
v1.5.4

$ dbc install duckdb
Installed duckdb 2.0.0

$ dbt show --inline "select version()"
v2.0.0

$ dbt show --inline "select * from t"   # file created by 2.0 CLI
[error] IO Error: Trying to read a database file with version number 999, but we can only read versions between 64 and 68.

$ dbt run  (second process at the same time)
[error] IO Error: Could not set lock on file "...": Conflicting lock is held ...

$ duckdb -c "LOAD fts; PRAGMA create_fts_index('d','id','body', incremental=1);"
Invalid Input Error: incremental FTS indexes require trigger support. Persistent DuckDB databases must use storage version v2.0.0 or higher.

$ duckdb -c "LOAD vss; CREATE TABLE d (emb DOUBLE[3]); CREATE INDEX i ON d USING HNSW(emb);"
Binder Error: HNSW index key type must be one of: 'FLOAT[N]'

$ duckdb -c "LOAD vss; EXPLAIN SELECT ... LIMIT 2 OFFSET 2"
Hnsw Index Scan; page 2 = [1, 2]; brute force = [3, 4]
```

## What not to add

- A full FTS internals table. The six-table schema is only useful for the orphan and collision traps.
- A 30-language stemmer list. The manual owns it.
- `vss_join` and `vss_match` recipes. They are brute force and do not use the index.
- A dbt orchestration skill. The orchestrated unit is dbt; one section is enough.
- A dbt probe script. It needs dbt, `dbc`, and a network install; keep it in research.
- Version-specific timings or memory numbers beyond order of magnitude.

## Open questions

- Does 2.0.1 fix HNSW `OFFSET` and the filtered-subquery crash? Retest after the patch.
- Is `hnsw_ef_search` per connection or per database? Source says session; `duckdb_settings().scope` says global.
- Does `dbt docs generate` always execute nodes, or only with static analysis enabled? Recheck on 2.0.10.
- Does the bundled dbt driver keep extension loading in the next dbt release? Recheck the docs against the binary.
- Is layered FTS maintained in MotherDuck and DuckLake? Untested.

## References

- https://duckdb.org/docs/2.0/core_extensions/full_text_search.html
- https://github.com/duckdb/duckdb-fts
- https://duckdb.org/docs/2.0/core_extensions/vss.html
- https://github.com/duckdb/duckdb-vss
- https://docs.getdbt.com/docs/local/connect-data-platform/duckdb-setup
- https://docs.getdbt.com/reference/resource-configs/duckdb-configs
- https://docs.getdbt.com/docs/dbt-versions/dbt-upgrade/upgrading-to-v2
- https://github.com/duckdb/dbt-duckdb
