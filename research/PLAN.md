# Plan

Status legend: `[ ]` open, `[~]` in flight, `[x]` done, `[-]` skipped with a reason.

## Definition of done

A reader can install the pack, pick the right skill from the router, and run the documented command on DuckDB 2.0.0 without a correction. Every executable claim in `skills/` is either probed in `scripts/probe.py` or labeled as documented. A link checker and a structure checker pass. The research folder lets a maintainer re-derive every claim.

## Phases

- [x] **0. Ground.** Read the poteto-mode principles, the repo, all 12 skills, and the existing research. Confirm the local binary is 2.0.0 and the docs snapshot is reachable.
- [x] **1. Snapshot sources.** Download the 2.0 manual (461 pages) and the DuckLake stable manual (76 pages) from the upstream markdown at a pinned commit.
- [x] **2. Fan out research.** Nine slices: release coverage, CLI, SQL, files/VARIANT, lakehouse, server/extensions/Python, spatial, docs/migrate/session, skill spec. All nine are written.
- [x] **3. Probe.** Run the high-risk claims against the local binary. Record commands and outputs in `research/09-verified-facts.md` and `scripts/probe.py`.
- [x] **4. Audit.** Merge slices into a per-skill verdict table in `research/08-skill-audit.md`.
- [x] **5. Design.** Fix the information architecture: router, task skills, reference files, one owner per deep fact.
- [x] **6. Rewrite.** Update all 12 skills. Add reference files only where depth earns it.
- [x] **7. Encode.** Add `scripts/check-skills.py`, `scripts/probe.py`, and `scripts/fetch-docs.py` so the rules can be re-run.
- [x] **8. Verify.** Run both scripts, check every relative link, re-run the probes, and compare the result to the definition of done. Structure and 75 probes pass.
- [x] **9. Package.** Update `README.md`, `plugin.json`, `marketplace.json`, and `THIRD-PARTY-NOTICES.md`.
- [x] **10. Diagnose and ingest.** Add `duckdb-profile`; move plan reading out of `duckdb-sql`; add the batch-ingest reference to `duckdb-files`; add the task case.
- [x] **11. Domain audit.** Probe the core and data skills against the 2.0.0 source. Fix silent wrong answers, add `references/triggers.md` and `references/diagnosis.md`, add `scripts/plan_lint.py`, and add the workflow authoring guide at `docs/skill-design.md`.
- [x] **12. Integration pass.** Recheck HN, Reddit, X, blogs, and official docs. Add `duckdb-search` and `duckdb-dbt`; add pagination, client, MCP, FTS, and VSS references; fix the async, security, migration, and sharing traps.
- [x] **13. Search and dbt workflow pass.** Re-probe dbt 2.0.9 and the FTS/VSS extensions. Add layered FTS, hybrid RRF, HNSW acceleration and memory rules, dbt driver and storage proof, materializations, hooks, concurrency, and a dbt project reference. Re-run 83 probes.

## Decisions

| Decision | Reason |
| --- | --- |
| Snapshot the manual instead of fetching pages per claim | 461 pages over the network is slow and non-reproducible. A pinned commit makes every citation stable. |
| Keep 13 skills in the diagnostics pass, then add `duckdb-search` and `duckdb-dbt` when the shipped extensions and adapter cleared the bar | A separate ingest skill would still collide with `duckdb-files`; that workflow stays a reference. Search and dbt have distinct triggers, contracts, and proofs. |
| Add reference files only for CLI, friendly SQL, triggers, formats, ingest, pagination, plans, diagnosis, catalogs, Overture, migration, clients, MCP, FTS, VSS | These are long tables or workflows an agent loads rarely. Everything else stays in `SKILL.md`. |
| Research stays in `research/`, not in the skill text | Skills carry decisions. Evidence belongs where a maintainer can audit it without spending agent context. |
| One owner per deep fact, one-line cross-links elsewhere | An agent that loads one skill must still be able to act. Detail is deduplicated; the minimum needed to recognize the situation is not. |
| Frontmatter stays `name` + `description` | The pack targets multiple clients. Client-specific fields would narrow it. |
