# Skill audit

Date: 2026-10-22, diagnostics pass 2026-10-26. Binary: DuckDB 2.0.0 `d54cbbe3df`. Evidence: `research/slices/`. The diagnostics probes ran on Linux x86_64; the first-pass probes ran on macOS arm64.

## Verdicts

| Skill | Before | Main issue | Change |
| --- | --- | --- | --- |
| `duckdb` | Covered | The CLI contract was terse and missed agent activation precedence, `-agent -json` losing the caps, JSON caveats, and the `~/.duckdbrc` behavior. | Rewritten around the version gate, output mode, invocation, routing, and first response. Added `references/cli.md` with flags, dot commands, settings, safety, and install. |
| `duckdb-sql` | Thin | Triggers had one overbroad `RETURNING` claim; division, nested schemas, and silent-result traps were shallow; `NEAREST`, `SECURE VIEW`, and multi-match DML were missing. | Rewritten with a trigger support matrix, exact division and decimal rules, nested-schema rules, 2.0 syntax, and a result-traps table. Added `references/friendly-sql.md`. Moved plan diagnosis to `duckdb-profile`; kept `EXPLAIN (SQL)` as syntax. |
| `duckdb-profile` | Missing | No skill owned `EXPLAIN` interpretation, pushdown failures, join blowups, spill, or Parquet layout diagnosis. `duckdb-sql` had two lines and no room. The first version was an operator guide, not a repeatable diagnostic. | Added with the plan-first workflow, three diagnoses, Parquet health checks, profiling settings, and a guarded UI handoff. The diagnostics pass added a case-file contract, a cost model, a failure-class catalog, six workflows, `references/diagnosis.md`, and `scripts/plan_lint.py` with a self-test. |
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

## Domain audit pass

A second audit ran on 2026-10-26 against the same binary and the v2.0.0 source. It found silent wrong answers that the first pass missed because the probes did not cover those interactions.

| Skill | Main issue found | Change |
| --- | --- | --- |
| `duckdb` | No result-trust proof; trailing `-cmd` claim was stale. | Added the footer and exit-code matrix; `-cmd` runs in argv order. |
| `duckdb-sql` | Trigger composition, DML proof, and three broken friendly-SQL examples. | Added trigger invariants and a reference; added the DML proof; fixed the examples; added `~` to result traps. |
| `duckdb-session` | The state file had no reconciliation step. | Added the alias/path reconciliation procedure and a fresh-process check. |
| `duckdb-files` | Parser rejects broke the ingest proof; multi-table `.duckdb` and the `schema` placeholder were wrong. | Added the reject branch and invariant; fixed the reader row and the schema form; removed duplicated CLI safety. |
| `duckdb-migrate` | The target had to be empty, and only 1.5 pinning was shown. | Added the 1.4/1.5/2.0 reader-to-pin matrix; unrelated target objects are allowed. |
| `duckdb-python` | The one-process connection model was wrong; the result lifecycle was scattered; `key` on upsert was wrong. | Corrected the connection model; added the lifecycle table; fixed appender and extension-directory claims. |
| `duckdb-profile` | Plan semantics were read too literally: `rows_scanned`, `Data Read`, row-group denominators, metadata-only plans, and text timings. | Added the diagnostic contract, `references/diagnosis.md`, and `scripts/plan_lint.py`; corrected the metrics and added no-profile handling. |
| `duckdb-spatial` | Min-corner bbox filtering silently dropped lines and polygons; measurement and join contracts were missing. | Added the full-overlap bbox rule, the distance/radius decision table, and the spatial-join contract. |
| `duckdb-variant` | SQL NULL and `VARIANT_NULL` were conflated; no JSON-to-VARIANT storage contract. | Added the null invariant and the five-step load and proof. |
| `duckdb-quack` | Authorization return type was incomplete; token reuse was false. | Added the `BOOLEAN` or `VARCHAR` authorization contract and the default-secret token rule. |
| `duckdb-lakehouse` | No classifier for an existing path; Unity needed a storage secret and time travel. | Added the path classifier, maintenance thresholds, and the Unity storage step. |
| `duckdb-extensions` | `install_mode` and gzip were wrong; the pin example was a 404. | Listed all five modes; gzip is accepted; the pin example is now a verified-value placeholder. |
| `duckdb-docs` | The trigger claimed all DuckDB and DuckLake questions; index counts were stale. | Narrowed the trigger to manual lookup; counts are now a range, not a target. |

## Cross-cutting

- Descriptions no longer contain slash commands. Plugin installs namespace the skill, Codex uses `$`, and a slash clause is not portable.
- Every skill has `## Verify` and ends with `## References`.
- Ten reference files: CLI, friendly SQL, trigger support, file formats, batch ingest, plan reading, diagnosis protocol, lakehouse catalogs, Overture, migration checklist.
- The router owns the version gate and output mode. Storage, secrets, Overture, extension rules, and plan diagnosis have one owner each.
- The frontmatter stays `name` and `description`. Client-specific fields are omitted so the pack loads in Claude Code, Codex, Cursor, Grok, and other Agent Skills clients.
- `scripts/check-skills.py` encodes the structure and runs with zero errors and zero warnings across all 13 skills in strict mode.
- `scripts/probe.py` encodes executable claims across 71 automated probes, including plan estimates and actuals, plan-only versus analyzed JSON shapes, metadata-only plans, spill metrics, the legacy metrics shape, DML execution under `EXPLAIN ANALYZE`, trigger composition, the friendly-SQL examples, migration targets, multi-table `read_duckdb`, Parquet row-group pruning, metadata duplication, schema drift, partitioned writes, overwrite behavior, CSV rejects, the ingest reject invariant, and JSON `ignore_errors`.
- `duckdb-profile/scripts/plan_lint.py` turns a plan into ranked findings. Its self-test covers a cross product, a non-sargable Parquet filter, a sargable point lookup, a metadata-only count, and a write-guard check.
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
- `slices/12-diagnostics-engine.md`: plan JSON shapes, spill, profiling metrics, linter design.

## Open verification

- A live Iceberg REST catalog and a Unity Catalog endpoint were not available.
- The 2.0.0 `ui` extension was promoted to `core` after the release. The UI handoff documents the install lag and the missing `osx_amd64` build, and the probe starts the server.
- The Claude Code plugin validator was not run because the CLI is not installed.
- A Grok project-skill trust test was inconclusive.
- `decimal_division` with mixed `DECIMAL` and `INTEGER` arguments was unstable on 2.0.0; the skill tells the reader to cast both.
- The `COPY` CTE row-count contradiction is recorded in the SQL slice; the skill treats the write as a side effect.
- A bbox-filtered Overture places scan followed by `ORDER BY confidence` or a computed distance hit an internal `Vector::Reference` error on 2.0.0. The workaround is a `MATERIALIZED` CTE; the root cause is open.
- A Snowflake-written shredded `VARIANT` Parquet file was not available, so that read path is documented, not probed.
- The `decimal_division` mixed-type instability and the `COPY` CTE result should be retested on 2.0.1.
- `profiling_output` is last-statement-wins in the repeated probe. The linter still avoids the file and uses `EXPLAIN ANALYZE (FORMAT JSON)`, because `EXPLAIN ANALYZE` never writes the file.
- A metadata-only `count(*)` returned `{"result":"error"}`; a `tracked_metrics` variation may change whether an empty `operator` list appears. The linter treats both as no profile.
- `ROW_GROUPS_PER_FILE` was exact in an unpartitioned write. Its interaction with `PARTITION_BY` was not tested.
- A 1.5.x binary was not available, so the 1.4/1.5 reader pins come from the source and the existing 1.5 probes, not from a second binary.
- The Unity storage secret is shown for S3. Azure and GCS paths need their own secret type and were not probed.
