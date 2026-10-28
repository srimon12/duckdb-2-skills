# Next-phase demand

Checked 2026-10-22. Hacker News is the only source with enough volume to rank the work. The points are a snapshot, not a roadmap.

| Story | Points | Comments | What the thread dwells on |
| --- | ---: | ---: | --- |
| [The DuckDB Local UI](https://news.ycombinator.com/item?id=43342712) | 926 | 188 | Looking at data, privacy of a web-loaded UI, comparison with DBeaver and Rill. |
| [A Preview of DuckDB v2.0](https://news.ycombinator.com/item?id=49330781) | 720 | 132 | Joining Excel, MySQL, and Postgres in one process, storage changes, extension availability. |
| [DuckDB is probably the most important geospatial software](https://news.ycombinator.com/item?id=43881468) | 491 | 165 | Leaving Athena and Spark for cost, an LLM query that runs but is still slow, 500 GB CSV that chokes. |
| [DuckDB Doesn't Need Data to Be a Database](https://news.ycombinator.com/item?id=40509987) | 406 | 155 | Querying files directly, S3 range requests, metadata caching, views. |
| [Quack](https://news.ycombinator.com/item?id=48111765) | 387 | 83 | Concurrent writes, client drivers, using DuckDB as a bridge between systems. |
| [DuckDB as the New jq](https://news.ycombinator.com/item?id=39782356) | 364 | 73 | Shell-sized file wrangling. |
| [DuckDB 2.0.0 LTS](https://news.ycombinator.com/item?id=50181136) | 331 | 37 | 7 TB of NDJSON compressed to Parquet, S3 footer range requests, a Quack driver for Metabase. |
| [Why DuckDB is my first choice](https://news.ycombinator.com/item?id=46645176) | 310 | 119 | Large joins versus Polars, `memory_limit`, tools that complement rather than replace. |
| [650 GB Delta on S3](https://news.ycombinator.com/item?id=45920881) | 263 | 107 | The query was a projection, not a full scan. S3 bandwidth and ephemeral workers dominate. |
| [Querying JSON as tables](https://news.ycombinator.com/item?id=35009612) | 294 | 80 | The same file-engine story. |

## What the threads support

1. **Diagnose the query and the files.** The repeated failure is a query that returns the right rows and still hammers S3, spills memory, or hides a cross join. The geospatial thread, the 650 GB thread, the 2.0 footer-request comments, and the `memory_limit` comments all describe cost and latency, not syntax.
2. **One file-to-Parquet workflow.** The 2.0 thread's concrete story is 7 TB of NDJSON to Parquet. The jq thread and the file-engine thread are the same job. The useful skill is the contract from messy input to checked, partitioned Parquet.
3. **A guarded UI handoff.** The Local UI is the largest DuckDB story. The comments ask whether data leaves the machine and how the page is loaded. The UI is worth a handoff, but the 2.0.0 `ui` extension was briefly missing from `core` during the release window and has no `osx_amd64` build. The handoff needs a fallback.

## What the threads do not support

- A dbt-duckdb skill. Algolia has 466 stories mentioning DuckDB and dbt. The ones actually about that stack scored 1 to 3 points.
- Evidence.dev or Rill skills. No DuckDB stories for either product.
- VSS or vector skills. DuckDB-plus-vector stories scored 2 and 3.
- Lambda or Cloud Run skills. Serverless Lambda stories did not show up in the DuckDB results.
- A MotherDuck skill. MotherDuck maintains its own skill catalog and its cloud lags the 2.0 release.
- A new MCP server. Skills are the playbook. A server that cannot explain a bad plan only makes a confident wrong answer faster.
- A Core/Lakehouse/AI repo split. The router already does progressive disclosure. No thread asks for a second catalog.

## Decision

Build `duckdb-profile` as the one new top-level skill. Put the file-to-Parquet contract in `duckdb-files/references/ingest.md` because `duckdb-files` already owns the convert, partition, and COPY triggers. Add one task eval for the ingest contract. Do not add a separate ingest skill, dbt, BI, VSS, Lambda, MotherDuck, MCP, or a repo split.

The UI is a handoff, not a dependency. `duckdb -ui` stays in `duckdb`; the profile skill says when it helps and what to use when the extension cannot install.

Superseded in part by `13-search-sharing-integrations.md` on 2026-10-28. dbt v2, the FTS/VSS extensions, and `duckdb_mcp` changed the premise. The new pass adds `duckdb-search` and `duckdb-dbt`, and keeps BI, MCP, and WASM as references or watches.
