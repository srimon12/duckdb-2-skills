# Plan

Status legend: `[ ]` open, `[~]` in flight, `[x]` done, `[-]` skipped with a reason.

## Definition of done

A reader can install the pack, pick the right skill from the router, and run the documented command on DuckDB 2.0.0 without a correction. Every executable claim in `skills/` is either probed in `scripts/probe.sh` or labeled as documented. A link checker and a structure checker pass. The research folder lets a maintainer re-derive every claim.

## Phases

- [x] **0. Ground.** Read the poteto-mode principles, the repo, all 12 skills, and the existing research. Confirm the local binary is 2.0.0 and the docs snapshot is reachable.
- [x] **1. Snapshot sources.** Download the 2.0 manual (461 pages) and the DuckLake stable manual (76 pages) from the upstream markdown at a pinned commit.
- [x] **2. Fan out research.** Nine slices: release coverage, CLI, SQL, files/VARIANT, lakehouse, server/extensions/Python, spatial, docs/migrate/session, skill spec. All nine are written.
- [x] **3. Probe.** Run the high-risk claims against the local binary. Record commands and outputs in `research/09-verified-facts.md` and `scripts/probe.py`.
- [x] **4. Audit.** Merge slices into a per-skill verdict table in `research/08-skill-audit.md`.
- [x] **5. Design.** Fix the information architecture: router, task skills, reference files, one owner per deep fact.
- [x] **6. Rewrite.** Update all 12 skills. Add reference files only where depth earns it.
- [x] **7. Encode.** Add `scripts/check-skills.py`, `scripts/probe.py`, and `scripts/fetch-docs.py` so the rules can be re-run.
- [~] **8. Verify.** Run both scripts, check every relative link, re-run the probes, and compare the result to the definition of done. Structure and 30 probes pass; the final link and content pass is open.
- [~] **9. Package.** Update `README.md`, `plugin.json`, `marketplace.json`, and `THIRD-PARTY-NOTICES.md`. Written; the install and link pass is open.

## Decisions

| Decision | Reason |
| --- | --- |
| Snapshot the manual instead of fetching pages per claim | 461 pages over the network is slow and non-reproducible. A pinned commit makes every citation stable. |
| Keep 12 skills, add no new top-level skill | The 1.x gap analysis already rejected triggers, JSON, separate Iceberg/Delta, C API, and client skills. The 2.0 surface fits the existing set. |
| Add reference files only for CLI, friendly SQL, formats, catalogs, Overture, migration | These are long tables an agent loads rarely. Everything else stays in `SKILL.md`. |
| Research stays in `research/`, not in the skill text | Skills carry decisions. Evidence belongs where a maintainer can audit it without spending agent context. |
| One owner per deep fact, one-line cross-links elsewhere | An agent that loads one skill must still be able to act. Detail is deduplicated; the minimum needed to recognize the situation is not. |
| Frontmatter stays `name` + `description` | The pack targets multiple clients. Client-specific fields would narrow it. |
