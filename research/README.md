# Research

Evidence for the DuckDB 2.0 skill pack. Start with [METHOD.md](METHOD.md) for the source order and confidence labels.

| File | What it answers |
| --- | --- |
| [METHOD.md](METHOD.md) | How a claim gets into a skill, and how it is labeled |
| [01-migration.md](01-migration.md) | What breaks between 1.x and 2.0, and the order to fix it |
| [02-quack-agent.md](02-quack-agent.md) | Quack, `CONNECT`, and CLI agent mode |
| [03-sql-variant-io.md](03-sql-variant-io.md) | SQL changes, `VARIANT`, and asynchronous I/O |
| [04-lakehouse-extensions.md](04-lakehouse-extensions.md) | DuckLake 1.1, Iceberg, Delta, and extensions |
| [05-skill-gap.md](05-skill-gap.md) | Upstream skill audit and the curated skill set |
| [06-deep-research.md](06-deep-research.md) | Claim-level research with sources and uncertainty |
| [07-docs-inventory.md](07-docs-inventory.md) | The pages this pack owns, and the local snapshot |
| [08-skill-audit.md](08-skill-audit.md) | Per-skill verdicts and the changes made |
| [09-verified-facts.md](09-verified-facts.md) | Claims re-run against the local binary |
| [slices/](slices/) | Fresh domain research, one file per slice. See the table below. |
| [sources/](sources/) | Offline snapshots of the manuals used above |

Files `01-migration.md` through `06-deep-research.md` are the first research pass. They are kept for provenance. `08-skill-audit.md`, `09-verified-facts.md`, and `slices/` are the final pass; where they disagree, the later files win.

The snapshots are reference copies. The live pages remain the source of truth. Each snapshot records its upstream commit in [sources/MANIFEST.md](sources/MANIFEST.md).

## Slices

| Slice | Domain | Status |
| --- | --- | --- |
| `00-release-coverage.md` | What 2.0 shipped, and which skill covers it | Complete |
| `01-cli.md` | CLI, agent mode, output modes, safety, install | Complete |
| `02-sql.md` | Dialect, lambdas, triggers, nested schemas, traps | Complete |
| `03-files-variant.md` | Readers, COPY, secrets, async I/O, VARIANT | Complete |
| `04-lakehouse.md` | DuckLake 1.1, Iceberg, Delta, Unity Catalog | Complete |
| `05-server-extensions-python.md` | Quack, extensions, Python client | Complete |
| `06-spatial.md` | Spatial, Overture, H3 | Complete |
| `07-docs-migrate-session.md` | Docs index, storage, migration, sessions | Complete |
| `08-skill-spec.md` | Portable skill format, packaging, evals | Complete |
| `09-next-phase-demand.md` | Community demand, scope decisions, rejected product skills | Complete |
| `10-query-diagnostics.md` | Plan reading, pushdown, joins, Parquet layout, UI caveat | Complete |
| `11-file-to-parquet.md` | Batch ingest contract, overwrite behavior, task case | Complete |
| `12-diagnostics-engine.md` | Plan JSON shapes, spill, profiling metrics, plan linter | Complete |
| `13-search-sharing-integrations.md` | FTS, VSS, pagination, views-only sharing, dbt, BI, MCP | Complete |

`METHOD.md` is the contract every slice follows. `08-skill-audit.md` is the merged verdict. `09-verified-facts.md` is the claim registry with probe commands.
