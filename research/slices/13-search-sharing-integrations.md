# Slice: search, sharing, and integrations

Status: complete on 2026-10-28. Scope: the highest-leverage DuckDB ideas found in HN, Reddit, X, ecosystem blogs, official docs, and local 2.0.0 probes after the 2026-10 diagnostics pass. Sources: DuckDB 2.0.0 `d54cbbe3df`, official 2.0 docs, DuckDB blog, GitHub releases, dbt docs, BI driver releases, and community extension docs.

## What changed

The earlier demand slice rejected dbt, VSS, and MCP because the community signal was thin. That premise changed:

- dbt v2 shipped a built-in DuckDB adapter on 2026-09-14.
- The FTS and VSS extensions cover user-facing search and vector indexes.
- `duckdb_mcp` 2.4.0 ships a 2.0.0 build.
- DuckDB published the views-only catalog guide on 2026-10-07.

The pack adds two skills and five references, and polishes the owners of the traps the research exposed.

## Verified facts

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| E1 | FTS `incremental=1` maintains `INSERT` and `DELETE`, not `UPDATE`. An updated row keeps the old term and misses the new one. | Probe: `UPDATE docs SET body='quokka'`; old term still matched, new term returned 0. Delete+insert repaired it. | Probed |
| E2 | Incremental FTS needs a `NOT NULL` id. `UNIQUE` alone is not enough. Duplicate ids fail at creation. | Probe: nullable `UNIQUE` id raised `incremental FTS indexes require the document id column to be NOT NULL`; duplicate ids hit the unique constraint. | Probed |
| E3 | A same-select `match_bm25` alias filter raises a binder error. The subquery form works. | Probe: `Alias "score" referenced - but the expression has side effects`. | Probed |
| E4 | HNSW acceleration requires the index metric to match the query function. `array_cosine_similarity` is not accelerated. | Probe: cosine index plus `array_cosine_distance` produced `Hnsw Index Scan`; `array_cosine_similarity` produced `Seq Scan` + `Top N`. | Probed |
| E5 | `hnsw_enable_experimental_persistence` gates index creation on a file database, not reads. `LOAD vss` must come before `SET`. | Probe: file create failed without the flag; reopen and query worked without it; `SET` before `LOAD` failed. | Probed |
| E6 | In 2.0.0, HNSW ignores `OFFSET` and repeats the first page. | Probe: offsets 1, 5, 10, and 50 returned the top rows. | Probed, version-specific |
| E7 | The HNSW index is not buffer-managed and does not count toward `memory_limit`. | Official VSS limitations page. | Documented |
| E8 | `LIMIT/OFFSET` over Parquet can duplicate and drop rows when `preserve_insertion_order=false` and threads are greater than one. | Probe: 30,000 rows, six row groups, page 10, 3,000 pages; total 30,000 but 20,870 distinct, 9,130 duplicated and 9,130 missing. | Probed |
| E9 | `file_row_number` range pagination is stable for one file. The number resets per file, so a multi-file page needs `(filename, file_row_number)`. | Probe: 3,000 pages, 30,000 distinct rows. Three-file predicate returned 10 rows per file. | Probed |
| E10 | A views-only `.duckdb` catalog is tiny, holds view definitions, and can be attached read-only over HTTP. Consumers still need the data and credentials. | Probe: 268 KB catalog over 100k-row Parquet; attach read-only, query, then move the data and get `No files found`. | Probed |
| E11 | dbt v2 is the `dbt` package with a built-in DuckDB adapter. The bundled driver cannot load extensions; `dbc install duckdb` is required. `dbt-duckdb` remains the v1 adapter. | Official dbt docs updated 2026-10-23; DuckDB blog 2026-09-22; dbt v2.0.0 release. | Documented |
| E12 | Metabase 1.5.6.0 and Grafana 0.4.6 bundle DuckDB 1.5.6; Superset caps `duckdb<2`. They cannot open storage 69. | Release assets and Superset `pyproject.toml`. | Documented |
| E13 | `duckdb_mcp` 2.4.0 ships against DuckDB 2.0.0 and supports MCP client and server modes. `mcp-server-motherduck` 1.1.0 pins DuckDB 1.5.6. | Community extension page and releases. | Documented |
| E14 | Async I/O covers Parquet, uncompressed seekable UTF-8 CSV, and native DuckDB storage. JSON is synchronous. | Official I/O page. | Documented |
| E15 | `CREATE TABLE AS SELECT NULL` creates a `"NULL"` column; a later integer insert fails. `X'…'` is `BLOB`, `B'…'` is `BIT`, and `2 * 3!` is 12. | Probes. | Probed |
| E16 | `duckdb -serve` stores its token in a persistent unencrypted `quack` secret, mode 600; the token grants full read/write access. | Security docs and isolated-HOME probe. | Probed / documented |
| E17 | `allowed_directories` allows a tree, `allowed_paths` allows exact files, and `disabled_filesystems='LocalFileSystem'` blocks local but keeps remote. HTTPS still needs a readable CA bundle. | Probes. | Probed |
| E18 | `VACUUM` does not reclaim space. `CHECKPOINT` frees deleted blocks for reuse but does not guarantee the file shrinks. Older-storage indexed tables need `vacuum_rebuild_indexes`. | Docs and file-size probe. | Probed / documented |
| E19 | A DuckDB-file DuckLake catalog is one writer; all processes must be `READ_ONLY` for multi-process reads. SQLite is local multi-client; PostgreSQL is multi-user; Quack is experimental; MySQL is not recommended. | DuckLake docs and two-process probe. | Probed / documented |
| E20 | A `SELECT *` view blocks VARIANT extraction pushdown even on one homogeneous file. Defining the view with the extracted field restores it. | Probe: 1M rows, direct read 3 ms, `SELECT *` view 149 ms; 2M rows 5 ms vs 300 ms. The 11 ms to 1.4 s blog figure did not reproduce at this scale. | Probed |
| E21 | Remote Parquet caches help repeated scans in one process, not a cold query. `parquet_metadata_cache` and `enable_http_metadata_cache` default false. Compaction was the decisive fix. | Probe: 50 files, cold 101 requests with or without caches; second query 202 vs 102. | Probed |
| E22 | A filter appended to `NEAREST ... BY DISTANCE` becomes part of the ranking key and can return a non-nearest row. Filter the right side in a CTE. | Probe: `AND color='red'` returned a blue row; CTE filter returned the red nearest. | Probed |
| E23 | The trigger-maintained average example covers insert and delete only. An `AFTER UPDATE` statement trigger is needed; row update triggers are unsupported. `MERGE INTO` cannot target a table with triggers. | Probes. | Probed |
| E24 | The ADBC Python DBAPI is not auto-commit; `adbc_ingest` is lost without `commit()`. Ibis 12 and earlier do not support DuckDB 2.0. | Probe and official Ibis guide. | Probed / documented |

## Decisions

### Add `duckdb-search`

FTS and VSS have a distinct job, trigger, contract, and proof. `duckdb-extensions` owns install mechanics, not index freshness or metric matching. `duckdb-docs` consumes BM25 for the hosted manual; it does not own user indexes.

Shape:

- `SKILL.md`: lexical versus vector decision, contracts, freshness, stop rules, proof.
- `references/fts.md`: parameters, `match_bm25`, incremental limits, update repair.
- `references/vss.md`: metric matrix, persistence, acceleration, memory, pagination, compaction.

### Add `duckdb-dbt`

dbt v2 is a separate project, profile, driver, and run workflow. `duckdb-python` owns `import duckdb`; `duckdb-lakehouse` owns catalog semantics. Neither owns the dbt adapter or the driver split.

Shape:

- One skill, no reference. The body carries the adapter split, profile, extension driver, storage gate, catalogs, orchestration, and v1-to-v2 steps.

### Add references

- `duckdb-files/references/pagination.md`: stable page contract and the `LIMIT/OFFSET` corruption proof.
- `duckdb-migrate/references/clients.md`: BI, dbt, Ibis, and MCP compatibility matrix.
- `duckdb/references/mcp.md`: `duckdb_mcp` and MotherDuck server setup and security.
- `duckdb-search/references/fts.md`, `vss.md`: search lookup.

### Polish

- `duckdb-files`: native async I/O correction, pagination trap, directory sandbox, `bound_schema` conflicts.
- `duckdb-session`: checkpoint versus vacuum, views-only sharing.
- `duckdb-quack`: unencrypted default token, per-thread connections, parameter binding.
- `duckdb-migrate`: NULL type, `X'…'`/`B'…'`, factorial, client matrix.
- `duckdb-sql`: `NEAREST` filter placement, incremental average update trigger.
- `duckdb-python`: ADBC commit, Ibis pin, Quack cursor exception.
- `duckdb-variant`: `SELECT *` view blocks extraction pushdown.
- `duckdb-lakehouse`: catalog choice and read-only processes.
- `duckdb-profile`: remote footer requests and cache scope.
- `duckdb`: routes to search, dbt, and MCP.

### Reject or watch

- **DuckDB-Wasm OPFS:** official 2026-09-18 feature, but the pack is CLI/SQL. Reject until browser-app requests repeat.
- **A separate BI skill:** the client matrix is version-sensitive and belongs with migration.
- **A separate MCP skill:** setup and security are a lookup, not a full workflow.
- **A dbt orchestration skill:** the orchestrated unit is dbt; one section is enough.
- **Log archive and warm serving references:** useful, but adjacent to ingest and profile. Watch for repeated demand.
- **`pg_duckdb`:** embeds DuckDB 1.4.3, not 2.0. Reject.
- **Jev, MotherDuck hybrid, Lance, Vortex, DuckPGQ:** demo or niche for this pack. Watch.

## Open questions

- Does 2.0.1 fix HNSW `OFFSET`? The stop rule is version-scoped; retest after the patch.
- dbt v2 and BI driver versions change within days. Recheck the exact pinned DuckDB build before a release.
- The MotherDuck MCP server may add a 2.0 driver. Recheck before repeating the 1.5.6 pin.
- The views-only catalog over HTTP was probed with Python's `http.server`, which lacks range requests. A range-capable server is the production path.
- The dbt, Metabase, Grafana, Superset, and Ibis claims are documented, not executed.

## Evidence

- HN Quack: https://news.ycombinator.com/item?id=48111765
- HN full-text search: https://news.ycombinator.com/item?id=47966254
- HN Parquet paging: https://news.ycombinator.com/item?id=49111006
- HN 2.0 release: https://news.ycombinator.com/item?id=50181136
- Reddit DuckLake production: https://www.reddit.com/r/DuckDB/comments/1oq7n13/
- Plotly DuckDB 2.0: https://plotly.com/blog/duckdb-2-0/
- FTS: https://duckdb.org/docs/2.0/core_extensions/full_text_search.html
- VSS: https://duckdb.org/docs/2.0/core_extensions/vss.html
- Views-only: https://duckdb.org/docs/2.0/guides/network_cloud_storage/duckdb_views_only.html
- Parquet: https://duckdb.org/docs/2.0/data/parquet/overview.html
- dbt: https://duckdb.org/2026/09/22/dbt-fusion.html
- MCP: https://duckdb.org/community_extensions/extensions/duckdb_mcp
- I/O: https://duckdb.org/docs/2.0/data/io.html
- Security: https://duckdb.org/docs/2.0/operations_manual/securing_duckdb/overview.html
- DuckLake catalogs: https://ducklake.select/docs/stable/duckdb/usage/choosing_a_catalog_database.html
