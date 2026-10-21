# Skill audit

Date: 2026-10-22. Binary: DuckDB 2.0.0 `d54cbbe3df`. Evidence: `research/slices/`.

## Verdicts

| Skill | Before | Main issue | Change |
| --- | --- | --- | --- |
| `duckdb` | Covered | The CLI contract was terse and missed agent activation precedence, `-agent -json` losing the caps, JSON caveats, and the `~/.duckdbrc` behavior. | Rewritten around the version gate, output mode, invocation, routing, and first response. Added `references/cli.md` with flags, dot commands, settings, safety, and install. |
| `duckdb-sql` | Thin | Triggers had one overbroad `RETURNING` claim; division, nested schemas, and silent-result traps were shallow; `NEAREST`, `SECURE VIEW`, and multi-match DML were missing. | Rewritten with a trigger support matrix, exact division and decimal rules, nested-schema rules, 2.0 syntax, and a result-traps table. Added `references/friendly-sql.md`. Moved plan diagnosis to `duckdb-profile`; kept `EXPLAIN (SQL)` as syntax. |
| `duckdb-profile` | Missing | No skill owned `EXPLAIN` interpretation, pushdown failures, join blowups, spill, or Parquet layout diagnosis. `duckdb-sql` had two lines and no room. | Added with the plan-first workflow, three diagnoses, Parquet health checks, profiling settings, and a guarded UI handoff. Added `references/plans.md`. |
| `duckdb-session` | Covered | Good attach and state-file advice. Needed the nested-schema catalog join, `checkpoint_on_detach` enum, detach rules, and the one-writer model. | Rewritten with those rules and a restart check. |
| `duckdb-files` | Thin | Reader dispatch was right. Parquet 2.0 read/write options, COPY options, temporary versus persistent secrets, and metadata functions were missing. The convert section also told a rerun to use `OVERWRITE_OR_IGNORE`, which leaves stale partitions. | Rewritten with a reader table, preview, convert, remote secrets, async I/O, and a local sandbox. Added `references/formats.md` and `references/ingest.md` for the batch contract. Corrected the overwrite rule. |
| `duckdb-variant` | Thin | Left list indexing unresolved and treated the comparator vaguely. | Rewritten with 1-based indexing, out-of-range NULL, comparator signature, aggregate constraints, shredding, and JSON mutation. |
| `duckdb-quack` | Covered | Marked Quack beta and rejected `postgres://` for `CONNECT`. Needed the filesystem risk, `quack_stop` scope, exact secret scope, direct `CONNECT`, and the missing `postgres_scan`/`mysql_scan`. | Rewritten with serve, connect, secrets, security, and pushdown, plus proxy numbers. |
| `duckdb-lakehouse` | Thin | DuckLake 1.1 and attach basics were right. Snapshots, time travel, maintenance, Iceberg writes, Unity Catalog, and the format decision were missing. | Rewritten with a decision table, DuckLake operations and safety, Iceberg writes, Delta exact-name rules, and Unity. Added `references/catalogs.md`. |
| `duckdb-extensions` | Covered | Install and update were right. `install_mode`, the no-op `INSTALL`, `extension_directories`, global repository trust, and offline paths were wrong or thin. | Rewritten with install/load, update, inspect, repositories, platform, and troubleshooting. |
| `duckdb-docs` | Covered | The index filter and BM25 subquery were right. Needed the signature parameters, a cache verification, and a clearer fallback. | Rewritten with versions, cache, query, answer rules, and verify. |
| `duckdb-migrate` | Thin | Storage, lambdas, division, S3, and settings were right. The regex break, deprecated settings, order of work, and rollback were missing. | Rewritten with order, storage, SQL text, CLI/deployment, Python/extensions, and rollback. Added `references/checklist.md`. |
| `duckdb-python` | Thin | The migration table was accurate. Connection config, the appender, `check_same_thread`, extension directories, and the DDL/DML rerun rule were missing or wrong. | Rewritten with connect, lazy relations, API changes, results and threads, Arrow, bulk load, and verify. |
| `duckdb-spatial` | Thin | Distance and Overture bbox-first were right. `geometry_always_xy` was treated as optional, the spheroid area and length signatures were wrong, `bbox` was called a partition column, `ST_Write` does not exist, and the current Overture schema and H3 argument order were missing. | Rewritten with the mandatory setting, exact spheroid argument types, bbox semantics for points versus polygons, R-tree `ST_DWithin`, native GeoJSON, current Overture themes, and H3 latitude-first. Added `references/overture.md`. |

## Cross-cutting

- Descriptions no longer contain slash commands. Plugin installs namespace the skill, Codex uses `$`, and a slash clause is not portable.
- Every skill has `## Verify` and ends with `## References`.
- Eight reference files: CLI, friendly SQL, file formats, batch ingest, plan reading, lakehouse catalogs, Overture, migration checklist.
- The router owns the version gate and output mode. Storage, secrets, Overture, and extension rules have one owner each.
- The frontmatter stays `name` and `description`. Client-specific fields are omitted so the pack loads in Claude Code, Codex, Cursor, Grok, and other Agent Skills clients.
- `scripts/check-skills.py` encodes the structure and runs with zero errors and zero warnings across all 13 skills in strict mode.
- `scripts/probe.py` encodes executable claims across 52 automated probes, including plan estimates and actuals, DML execution under `EXPLAIN ANALYZE`, Parquet row-group pruning, metadata duplication, schema drift, partitioned writes, overwrite behavior, CSV rejects, and JSON `ignore_errors`.
- `evals/triggers.md` covers routing, skill-specific prompts, and negative disambiguation triggers across all skills including `duckdb-profile` and `duckdb-files`.
- `evals/ingest` is a task case for the file-to-Parquet workflow, with a deterministic 60,000-row fixture and 25 grader checks. The first candidate smoke run found a nullable-column ambiguity; the contract now names it.

## What was rejected

- A triggers skill. The support matrix fits in `duckdb-sql`.
- A JSON skill beside `VARIANT`. JSON readers stay in `duckdb-files`; mutation stays in `duckdb-variant` as a short section.
- Separate Iceberg and Delta skills. The decision table is the product.
- A `CREATE EXTENSION REPOSITORY` procedure. The syntax is WIP; the skill names it and stops.
- C API, Java, Rust, Node, Go, or R skills. Out of scope for this pack.
- A function catalog or a full dot-command catalog. Both are lookup material and go stale.
- A separate ingest skill. The workflow is `duckdb-files/references/ingest.md` because `duckdb-files` already owns the convert, partition, and COPY triggers.
- A dbt, BI, VSS, Lambda, MotherDuck, or MCP skill. The community signal is query and file pain, not a new product surface.

## Evidence

- `slices/00-release-coverage.md`: feature coverage and release contradictions.
- `slices/01-cli.md`: flags, agent mode, output modes, dot commands, safety, install.
- `slices/02-sql.md`: dialect, lambdas, triggers, nested schemas, traps.
- `slices/04-lakehouse.md`: DuckLake, Iceberg, Delta, Unity.
- `slices/05-server-extensions-python.md`: Quack, extensions, Python.
- `slices/08-skill-spec.md`: portable frontmatter, layout, descriptions, evals, packaging.
- `slices/03-files-variant.md`: readers, COPY, secrets, VARIANT.
- `slices/07-docs-migrate-session.md`: docs index, storage, migration, sessions.
- `slices/06-spatial.md`: spatial, Overture, H3.
- `slices/09-next-phase-demand.md`: community demand and rejected product skills.
- `slices/10-query-diagnostics.md`: plans, pushdown, joins, Parquet layout, UI caveat.
- `slices/11-file-to-parquet.md`: ingest contract, overwrite behavior, task case.

## Open verification

- A live Iceberg REST catalog and a Unity Catalog endpoint were not available.
- The 2.0.0 `ui` extension returned HTTP 404 on five platform URLs on 2026-10-22. The UI handoff is documented with a fallback, not assumed to work.
- The Claude Code plugin validator was not run because the CLI is not installed.
- A Grok project-skill trust test was inconclusive.
- `decimal_division` with mixed `DECIMAL` and `INTEGER` arguments was unstable on 2.0.0; the skill tells the reader to cast both.
- The `COPY` CTE row-count contradiction is recorded in the SQL slice; the skill treats the write as a side effect.
- A bbox-filtered Overture places scan followed by `ORDER BY confidence` or a computed distance hit an internal `Vector::Reference` error on 2.0.0. The workaround is a `MATERIALIZED` CTE; the root cause is open.
- A Snowflake-written shredded `VARIANT` Parquet file was not available, so that read path is documented, not probed.
- The `decimal_division` mixed-type instability and the `COPY` CTE result should be retested on 2.0.1.
