# duckdb-2-skills

Agent skills for DuckDB 2.0. Write SQL, ingest files, diagnose slow plans, search tables, run dbt, work with lakes, and ship Python code without re-learning the 2.0 traps each time.

Fifteen skills, fifteen lookup references, one router, and a plan linter. Verified against DuckDB 2.0.0 LTS `d54cbbe3df` on Linux x86_64.

## Why this pack

- The router checks the binary, picks the output mode, and loads the skill that owns the job.
- Every workflow carries a contract, a proof, and stop rules. The agent can tell a correct result from a plausible wrong one.
- Deep facts have one owner. Other skills link to it instead of repeating it.

## Install

DuckDB 2.0 or newer is required.

```bash
curl -fsSL https://install.duckdb.org | sh
duckdb -no-agent --version
```

The version must print `v2.0`. Homebrew can lag the release.

### Claude Code

From GitHub:

```text
/plugin marketplace add srimon12/duckdb-2-skills
/plugin install duckdb-2-skills@duckdb-2-skills
```

From a clone:

```bash
claude --plugin-dir .
```

Plugin skills are namespaced. Invoke `/duckdb-2-skills:duckdb`.

### Codex

```bash
mkdir -p .agents/skills
cp -R skills/. .agents/skills/
```

Use `~/.agents/skills/` for every project. Invoke `$duckdb`.

### Cursor

```bash
mkdir -p .cursor/skills
cp -R skills/. .cursor/skills/
```

Cursor also reads `.agents/skills`, `.claude/skills`, and `.codex/skills`.

### Grok

```bash
mkdir -p .grok/skills
cp -R skills/. .grok/skills/
```

Use `~/.grok/skills/` for every project. A project may need to be trusted first.

### Other Agent Skills clients

Copy `skills/<name>/` into the client's skills directory. The folder is the unit. There is no build step.

## Quick start

Load the router when the task is not specific:

```text
/duckdb-2-skills:duckdb
```

Then ask in normal language:

- "This query takes 40 seconds. Diagnose the plan."
- "Ingest this CSV into partitioned Parquet and keep the bad rows."
- "Search these support emails by keyword and rank the matches."
- "The Metabase driver cannot open our 2.0 database file."

## Skills

| Skill | Job | Load when |
| --- | --- | --- |
| [`duckdb`](skills/duckdb/SKILL.md) | Gate the binary, pick the output mode, route | DuckDB, the CLI, or an unknown task |
| [`duckdb-sql`](skills/duckdb-sql/SKILL.md) | Write and run SQL | Query, lambda, trigger, nested schema, `MERGE`, SQL migration |
| [`duckdb-profile`](skills/duckdb-profile/SKILL.md) | Diagnose plans and Parquet layouts | Slow query, `EXPLAIN ANALYZE`, OOM, full scan, spill, schema drift |
| [`duckdb-files`](skills/duckdb-files/SKILL.md) | Read, convert, and batch-ingest files | CSV, Parquet, JSON, Avro, Excel, SQLite, HTTP, object storage |
| [`duckdb-session`](skills/duckdb-session/SKILL.md) | Attach and restore a database | Attach, open, switch, persist a `.duckdb` file |
| [`duckdb-variant`](skills/duckdb-variant/SKILL.md) | Store and query semi-structured values | `VARIANT`, shredded JSON, schema-less columns |
| [`duckdb-search`](skills/duckdb-search/SKILL.md) | Build full-text and vector indexes | BM25, keyword search, HNSW, embeddings |
| [`duckdb-python`](skills/duckdb-python/SKILL.md) | Write or migrate Python client code | Code that imports `duckdb` |
| [`duckdb-dbt`](skills/duckdb-dbt/SKILL.md) | Run dbt v2 on DuckDB | dbt project, profile, `dbt-duckdb`, dbt migration |
| [`duckdb-quack`](skills/duckdb-quack/SKILL.md) | Serve a database or route a session | Quack, `-serve`, `-connect`, Postgres or MySQL pushdown |
| [`duckdb-lakehouse`](skills/duckdb-lakehouse/SKILL.md) | Use DuckLake, Iceberg, Delta, Unity | Lakehouse catalog or open table format decision |
| [`duckdb-spatial`](skills/duckdb-spatial/SKILL.md) | Answer location questions | Maps, lat/lng, GeoJSON, Overture, H3 |
| [`duckdb-extensions`](skills/duckdb-extensions/SKILL.md) | Install, load, and update extensions | Missing extension, community extension, custom repository |
| [`duckdb-docs`](skills/duckdb-docs/SKILL.md) | Search the official docs index | Exact signature or page, and no task skill owns it |
| [`duckdb-migrate`](skills/duckdb-migrate/SKILL.md) | Move 1.4 or 1.5 to 2.0 | Upgrade, storage pin, export/import, 1.x reader |

## How it works

Start with `duckdb` when the task is not specific. It gates the version, chooses the output mode, and routes.

Each task skill stands alone. It links the owner when it needs a deep fact from another skill. References load only when the task needs them, and scripts handle deterministic steps.

```text
skills/       one folder per skill, with references and scripts
research/     evidence, audits, probe logs, and manual snapshots
scripts/      structure checks and the probe runner
evals/        routing cases and the ingest task
docs/         skill authoring guide
```

## Verify

```bash
python3 scripts/check-skills.py --strict
python3 scripts/probe.py --network
bash evals/ingest/run_reference.sh
python3 skills/duckdb-profile/scripts/plan_lint.py --self-test
```

Current result: 15 skills with 0 errors, 75/75 probes, 25/25 ingest checks, and 5/5 linter checks.

The probe suite needs DuckDB 2.0. The network probes cover the docs index and the UI extension. dbt, Metabase, Grafana, Superset, Ibis, live Iceberg, and Unity Catalog are documented, not executed. See [research/08-skill-audit.md](research/08-skill-audit.md) for the exact coverage.

## Research and contributing

[research/README.md](research/README.md) indexes the evidence. [research/09-verified-facts.md](research/09-verified-facts.md) records every probed claim. [docs/skill-design.md](docs/skill-design.md) explains the workflow contract and the ownership rules.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing a skill. Run [evals/triggers.md](evals/triggers.md) after changing a description.

## License

MIT. This is an independent pack, not a DuckDB Foundation project. Adapted workflows and documentation snapshots keep their original MIT notices. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). DuckDB is a trademark of the DuckDB Foundation.
