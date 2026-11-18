# Slice: retrieval audit

Status: complete on 2026-11-17. Scope: recheck the search, VARIANT, file reader, Quack, and profiling claims that a retrieval benchmark depends on. Sources: DuckDB 2.0.0 `d54cbbe3df`, vss `3685131eac`, fts `2266e67d01`, the `duckdb-vss` and `duckdb-fts` repositories, the 2.0 manual, the Query.Farm 2.0 issue-activity report, and local probes on macOS arm64.

## Verified facts

### Vector

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| R1 | `<=>` returns `array_cosine_distance` and `<->` returns `array_distance`, but neither uses HNSW. | Probe: both values matched; `EXPLAIN` showed `Seq Scan` plus `Top N` for both operators with a cosine index present. | Probed |
| R2 | Without `LOAD vss`, reads scan but writes to an indexed table fail. | Probe: reopen without load, `SELECT` returned rows; `INSERT` raised `Missing Extension Error: Cannot bind index "items", unknown index type 'HNSW'`. | Probed |
| R3 | `hnsw_ef_search` cannot be read before the first `SET`, and `RESET` returns NULL. | Probe: `current_setting` raised `Catalog Error`; after `SET 128` it returned 128; `ROLLBACK` left 100; `RESET` returned NULL. | Probed |
| R4 | `hnsw_compact_index` prunes links but does not reclaim capacity or memory on 2.0.0. | Probe: 100 rows, delete 90, compact; `count` fell to 10, `capacity` stayed 100, `approx_memory_usage` stayed 16779488. | Probed |
| R5 | The OFFSET bug is still open upstream and has no fix on main. | `duckdb-vss#110` open since 2026-11-08; `hnsw_optimize_scan.cpp` still passes `top_n.limit` without `top_n.offset`; main at `430d5f8`. | Probed |
| R6 | The extension README and the 2.0.0 probe describe different compaction outcomes. | README says compaction prunes deleted items; probe shows capacity and memory unchanged. The README claim is about links, not allocation. | Probed vs documented |

### Full text

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| R7 | The released 2.0.0 FTS build is older than the `v2.0-cyanoptera` branch HEAD. | Installed extension `2266e67d01` is a 2026-07-30 commit; branch HEAD `623ee80e` is 2026-10-05. | Probed |
| R8 | The unknown-field error depends on the extension build. | Probe: `fields := 'nope'` returned 0 rows on `2266e67d01`; branch source at `623ee80e` raises `fields contains unknown field: <name>`. | Probed |
| R9 | `b` outside 0 to 1 has an exact error. | Probe: `b := 2.0` raised `Invalid Input Error: b must be finite and between 0 and 1`. | Probed |
| R10 | `search_layered_bm25` returns the document id as `docname`, not a row number. | Source and probe: result columns `docname`, `score`, `rank`. | Probed |

### VARIANT, files, Quack, and Python

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| R11 | JSON numbers cast to VARIANT keep a parsed numeric type. | Probe: `{'k': 1.2}` is `DECIMAL(2, 1)`; `{'n': 64}` is `INT32`; Parquet round-trip preserved `DECIMAL(2, 1)`. | Probed |
| R12 | `read_json` cannot write a VARIANT target. | Probe: `COPY t FROM 'v.json'` raised `Not implemented Error: Cannot read a value of type VARIANT from a json file`. | Probed |
| R13 | Python returns two columns for `EXPLAIN ANALYZE (FORMAT JSON)`. | Probe: `duckdb` 2.0.0 returned `('analyzed_plan', '<json>')`; the JSON parsed from `row[1]`. | Probed |
| R14 | `duckdb ... -serve` exits when stdin closes in a non-interactive shell. | Probe: with `< /dev/null`, the process printed the token and exited 0; holding stdin with `tail -f /dev/null` kept it alive. | Probed |
| R15 | Serving a Parquet file exposes a view named after the stem. | Probe: `q.parquet` served `file` and `q`; `SELECT * FROM q` worked. | Probed |
| R16 | `read_csv_auto`, `read_json_auto`, and `parquet_scan` are registered overloads, not aliases. | Manual: `formats.md` reader table; probe: both names read the same file. | Documented and probed |
| R17 | Async I/O is on for local reads too, but the documented payoff is remote latency. | Manual: 2.0 I/O page; the design-post ratios are not 2.0.0 local-disk guarantees. | Documented |
| R18 | Per-query nDCG, recall, and MRR can be computed in one DuckDB query. | Probe: fixture returned nDCG 0.6590018, recall 1.0, MRR 0.5 for query 1. | Probed |
| R19 | DuckDB 2.0.1 is planned, not released. | Query.Farm report marks 2026-11-18 as the planned patch date; GitHub has no `v2.0.1` tag on 2026-11-17. | Announced |

## Existing skill audit

| Skill | Claim or omission | Verdict | Fix |
| --- | --- | --- | --- |
| `duckdb-search` | Did not mention `<=>` or `<->`; said reads scan without `LOAD vss` but omitted the write failure; omitted the `current_setting` trap; compaction wording could imply reclamation. | Fix | Added operator and write-gate traps, the settings probe, and the capacity distinction. |
| `duckdb-search/references/hybrid.md` | Evaluation stopped at recall and a hand fixture. | Thin | Linked a new evaluation reference with nDCG, recall, MRR, and latency. |
| `duckdb-variant` | Omitted JSON numeric types and the exact `read_json` error. | Thin | Added `DECIMAL`/`INT32` typing, the `::DOUBLE` rule, and the error. |
| `duckdb-files` | Called reader overloads "legacy aliases"; implied async speedups without a local/remote distinction. | Fix | Called them overloads; scoped the speedup claim to remote storage. |
| `duckdb-quack` | Told the agent to background `-serve` without the stdin lifetime caveat; omitted the file-view name. | Fix | Added the stdin rule and the stem-named view. |
| `duckdb-profile` | Omitted the Python two-column result shape. | Thin | Added `fetchone()[1]` to the skill and `references/plans.md`. |

## Gaps worth adding

| Rank | Gap | Why an agent needs it | Home |
| --- | --- | --- | --- |
| 1 | nDCG@k, recall@k, and MRR SQL with per-query averaging | A hybrid or reranker claim without a labeled metric is a demo, not a result. | `duckdb-search/references/evaluation.md` |
| 2 | `<=>` and `<->` are not index-accelerated | A user can copy a pgvector habit and silently lose the index. | `references/vss.md` and the skill body |
| 3 | Write sessions must load `vss` | A benchmark that reconnects for ingest fails after the index exists. | `references/vss.md` and the stop rules |
| 4 | `hnsw_ef_search` is not readable before `SET` | A tuning script that reads the default gets a catalog error. | `references/vss.md` |
| 5 | JSON numbers are DECIMAL or INT32 | Metric math and `VARIANT` run configs silently change type. | `duckdb-variant` |
| 6 | `-serve` exits when stdin closes | A background server in a script dies after printing a token. | `duckdb-quack` |
| 7 | Python `EXPLAIN ANALYZE` has two columns | A parser that expects one column reads the label, not the JSON. | `duckdb-profile` |

## Traps and contradictions

| Trap | What happens | Correct move | Evidence |
| --- | --- | --- | --- |
| Using `<=>` or `<->` for a measured HNSW query | Seq Scan plus Top N | Use `array_cosine_distance` or `array_distance` | R1 |
| Reconnecting without `LOAD vss` to ingest | Insert fails on the bound index | Load `vss` in every write session | R2 |
| Reading `current_setting('hnsw_ef_search')` for a default | Catalog Error before the first SET | Track the effective value in the script | R3 |
| Expecting compaction to shrink the index | Capacity and memory unchanged | Rebuild after a large delete | R4 |
| Treating the released FTS extension as branch HEAD | Unknown fields return zero rows, not an error | Pin the extension build, check the error, or validate fields first | R7, R8 |
| Doing metric math on `cfg.k` without a cast | DECIMAL arithmetic changes precision or aggregation | `cfg.k::DOUBLE` | R11 |
| Backgrounding `-serve` with stdin closed | Process exits after printing the token | Hold stdin or use a terminal | R14 |
| Parsing the first column of a Python `EXPLAIN ANALYZE` result | Gets `analyzed_plan`, not JSON | Parse `fetchone()[1]` | R13 |

## What not to add

- A separate retrieval-evaluation skill. The job belongs to `duckdb-search`, and the SQL is a lookup table.
- A Qdrant or pgvector arm in this pack. The DuckDB skills own the DuckDB side.
- A claim that 2.0.1 fixes OFFSET or compaction. No tag exists; keep the stop rule and retest.
- A local-disk async speedup ratio. The documented numbers are remote and workload-specific.

## Probe log

```text
$ duckdb -no-agent -no-init -c ".read /tmp/audit-search.sql"
vss 3685131eac at 'cosine'; array_cosine_distance -> Hnsw Index Scan
emb <=> vector -> Seq Scan + Top N
emb <-> vector -> Seq Scan + Top N
LIMIT 2 OFFSET 2 -> 1, 2
LIMIT 2 OFFSET 4 -> 1, 2

$ duckdb -no-agent -no-init /tmp/audit-persist.duckdb -c "INSERT ..."
Missing Extension Error: Cannot bind index "items", unknown index type 'HNSW'

$ duckdb -no-agent -no-init -c "LOAD vss; SET hnsw_ef_search=128; ..."
after_set 128; after_rollback 100; after_reset NULL

$ duckdb -no-agent -no-init -c ".read /tmp/audit-compact.sql"
before count=100 capacity=100 memory=16779488
after  count=10  capacity=100 memory=16779488

$ duckdb -no-agent -no-init -c ".read /tmp/audit-fts.sql"
known=1 unknown=0 empty=0; update old=1 new=0

$ duckdb -no-agent -no-init -c "SELECT variant_typeof(...)"
DECIMAL(2, 1), INT32

$ /tmp/ddbvenv/bin/python -c "duckdb.execute('EXPLAIN ANALYZE (FORMAT JSON) ...')"
('analyzed_plan', '<json>')

$ duckdb /tmp/q.parquet -serve < /dev/null
exit 0 after printing the token

$ duckdb -no-agent -no-init -c ".read /tmp/eval-test.sql"
0.6590018048024133 | 1.0 | 0.5
```

## Open questions

- Does 2.0.1 fix `duckdb-vss#110` or change compaction capacity? Retest when the tag exists.
- Does the 2.0.1 FTS extension build include the unknown-field validation from `623ee80e`? Check `duckdb_extensions()` and the error text.
- Does the 2.0.1 Python wheel keep the two-column `EXPLAIN ANALYZE` shape? The probe is pinned to 2.0.0.
