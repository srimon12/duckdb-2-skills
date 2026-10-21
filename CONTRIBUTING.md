# Contributing

This repo ships agent skills, not a manual. A skill earns its place by changing what an agent does on the next command.

## Layout

```
skills/<name>/SKILL.md          the skill
skills/<name>/references/*.md   long tables loaded only when needed
research/                       evidence, snapshots, and the per-skill audit
scripts/check-skills.py         structure and link checks
scripts/probe.py                executable claims, run against a real binary
evals/triggers.md               routing cases to run after a description change
```

## SKILL.md contract

Frontmatter carries two fields. Nothing client-specific.

```yaml
---
name: duckdb-files
description: >
  Read, preview, and convert data files with DuckDB 2.0. Use when the user
  points at a CSV, Parquet, JSON, Excel, or SQLite file, or asks for a format
  conversion.
---
```

Rules for the description:

- Start with the job, not the product.
- Include the words a user would type, including file extensions and command names.
- End with `Use when ...`.
- Stay under 1024 characters.
- Do not list every feature. The body does that.

Rules for the body:

- One level-1 title, sentence case.
- Short sections with decision-changing content.
- A `## Verify` section with a command that proves the skill's main claim.
- A `## References` section with official URLs and the related skills.
- At most 200 lines. If it grows past that, move a table to `references/`.
- No narration, no history, no restating the manual.
- One owner per deep fact. Other skills may state the minimum needed to recognize the situation, then link the owner.

## References

Add a reference file only when the content is long, tabular, and needed on a minority of runs. A reference that repeats the skill body is dead weight.

- Link it from `SKILL.md` by filename.
- Keep it under 450 lines.
- Open with one sentence that says when to read it.
- Do not link a reference from another skill's reference. Link the owning skill.

Current reference files: CLI flags, friendly SQL, file formats, batch ingest, plan reading, lakehouse catalogs, Overture, migration checklist.

## Fact ownership

| Fact | Owner |
| --- | --- |
| CLI invocation, output modes, agent mode, version gate, install | `duckdb` |
| Plan reading, profiling, pushdown, join and spill diagnosis | `duckdb-profile` |
| `state.sql`, attach/detach, catalog introspection, checkpointing | `duckdb-session` |
| Friendly SQL, lambdas, triggers, parser fallback, SQL traps | `duckdb-sql` |
| Reader and writer dispatch, COPY options, secrets, async I/O | `duckdb-files` |
| Batch ingest contract, quarantine, partitioned load, row-count proof | `duckdb-files` (`references/ingest.md`) |
| `VARIANT` functions, shredding, JSON versus VARIANT | `duckdb-variant` |
| Quack, `CONNECT`, Postgres and MySQL pushdown | `duckdb-quack` |
| DuckLake, Iceberg, Delta, catalog choice | `duckdb-lakehouse` |
| `INSTALL`, `LOAD`, `UPDATE EXTENSIONS`, repositories | `duckdb-extensions` |
| Docs index versions, BM25 query, cache | `duckdb-docs` |
| Storage versions, compatibility, export/import, migration order | `duckdb-migrate` |
| Python API changes, relations, threads, Arrow | `duckdb-python` |
| Spatial setup, distance, bbox, Overture, H3 | `duckdb-spatial` |

## Write for an agent

- Imperative. "Run", "check", "refuse".
- The condition before the instruction.
- Name the exact command, flag, function, or column.
- Say what to do when the first attempt fails.
- Delete a sentence that does not change a decision.
- Use a table when the reader will scan for a case.
- No em dashes, no colon as a connector, no "simply", no "just".

## Verify

```bash
python3 scripts/check-skills.py
python3 scripts/probe.py
python3 scripts/probe.py --network --write research/probe-results.txt
```

`check-skills.py` checks frontmatter, headings, line budgets, relative links, cross-skill names, and stale strings. `probe.py` runs the executable claims against the local DuckDB binary.

When a new fact goes into a skill, add a probe if it is executable. If it is not executable, cite the manual page in `research/09-verified-facts.md` or the slice that covers it.

## Research

1. Snapshot the official markdown at a pinned commit. See `research/sources/MANIFEST.md`.
2. Write one slice per domain in `research/slices/`, using the schema in `research/METHOD.md`.
3. Probe the high-risk claims. Record the command and the output.
4. Merge the slice into `research/08-skill-audit.md` with a per-skill verdict.
5. Only then edit the skill.

A claim without a source does not go in a skill. A source without a probe is labeled `Documented`.

## Adding a skill

A new skill needs a job an agent does repeatedly, a trigger that does not collide with an existing skill, and enough depth to fill a page. `duckdb-profile` cleared that bar in the next-phase pass. A separate ingest skill did not. The workflow is `duckdb-files/references/ingest.md` because `duckdb-files` already owns the convert, partition, and COPY triggers.

Rejected in the 2.0 pass: triggers, JSON beside `VARIANT`, separate Iceberg and Delta, C API and other clients, a `CREATE EXTENSION REPOSITORY` procedure.

Rejected in the next-phase pass: a separate ingest skill, dbt-duckdb, Evidence or Rill, VSS or embedding workflows, Lambda or Cloud Run deployment, MotherDuck hybrid mode, an MCP server, and a Core/Lakehouse/AI repo split.

## Release checklist

- [ ] `check-skills.py` passes with no errors.
- [ ] `probe.py` passes.
- [ ] Every reference file is linked and under budget.
- [ ] `evals/triggers.md` has a pass for each changed description.
- [ ] `evals/ingest` passes its reference run and its grader.
- [ ] `README.md` skill table matches `skills/`.
- [ ] `plugin.json` and `marketplace.json` versions match.
- [ ] `research/08-skill-audit.md` says what changed and why.
