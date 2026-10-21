# duckdb-2-skills

Agent skills for [DuckDB 2.0.0 LTS](https://duckdb.org/2026/10/21/announcing-duckdb-200.html), released 2026-10-21. The GitHub release is named Cyanoptera. The announcement calls the same release Cinnamon Teal.

This is an independent pack. It is not a fork of [duckdb/duckdb-skills](https://github.com/duckdb/duckdb-skills) and is not published by the DuckDB Foundation. Where a workflow is adapted from that MIT-licensed repo, the skill says so, and the copyright notice is in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

## What this is

Twelve skills. One router, eleven task skills, and six lookup references. The router checks the binary, picks the output mode, and points at the skill that owns the job. Each task skill is short enough to load whole and specific enough to change the next command.

The pack was rewritten for 2.0. It is not a 1.x pack with a version string changed. DuckDB 2.0 changes the storage format, the lambda syntax, the parser, the CLI output contract, the lakehouse extensions, and the Python client. Each of those has a migration action.

## Install

The CLI has to be DuckDB 2.0 or newer.

```bash
curl -fsSL https://install.duckdb.org | sh
duckdb -no-agent --version
```

`duckdb -no-agent --version` must print `v2.0`. On 2026-10-22 the official installer shipped 2.0.0 and Homebrew was still on 1.5.6. Check the version after either install.

### Claude Code

From a clone of this repo:

```bash
claude --plugin-dir .
```

From GitHub:

```
/plugin marketplace add srimon12/duckdb-2-skills
/plugin install duckdb-2-skills@duckdb-2-skills
```

Plugin skills are namespaced. Invoke `/duckdb-2-skills:duckdb`, not `/duckdb`.

### Codex

```bash
mkdir -p .agents/skills
cp -R skills/. .agents/skills/
```

For every project, copy to `~/.agents/skills/` instead. Invoke `$duckdb` or use `/skills`.

### Cursor

```bash
mkdir -p .cursor/skills
cp -R skills/. .cursor/skills/
```

Cursor also reads `.agents/skills`, `.claude/skills`, and `.codex/skills`. Invoke `/duckdb`.

### Grok

```bash
mkdir -p .grok/skills
cp -R skills/. .grok/skills/
```

For every project, copy to `~/.grok/skills/`. A project may need to be trusted before its `.grok/skills` directory is read. Invoke `/duckdb`.

### Any Agent Skills client

Copy `skills/<name>/` into the client's skills root. The folder is the unit; there is no build step.

## Skills

| Skill | Job | Load when |
| --- | --- | --- |
| [`duckdb`](skills/duckdb/SKILL.md) | Gate the binary, pick the output mode, route | The user mentions DuckDB or the CLI, or you do not know which skill to load |
| [`duckdb-sql`](skills/duckdb-sql/SKILL.md) | Write and run SQL | A query, lambda, trigger, nested schema, `MERGE`, or SQL migration |
| [`duckdb-session`](skills/duckdb-session/SKILL.md) | Attach a database and keep it across calls | Attach, open, switch, or persist a native `.duckdb` file |
| [`duckdb-files`](skills/duckdb-files/SKILL.md) | Read, preview, and convert files | A CSV, Parquet, JSON, Avro, Excel, SQLite, HTTP, or object-storage path |
| [`duckdb-variant`](skills/duckdb-variant/SKILL.md) | Store and query semi-structured values | `VARIANT`, shredded JSON, schema-less columns |
| [`duckdb-quack`](skills/duckdb-quack/SKILL.md) | Serve a database or route a session | Quack, `-serve`, `-connect`, `CONNECT`, Postgres or MySQL pushdown |
| [`duckdb-lakehouse`](skills/duckdb-lakehouse/SKILL.md) | Use DuckLake, Iceberg, Delta, Unity Catalog | A lakehouse catalog or an open table format decision |
| [`duckdb-extensions`](skills/duckdb-extensions/SKILL.md) | Install, load, and update extensions | A missing extension, a community extension, or a custom repository |
| [`duckdb-docs`](skills/duckdb-docs/SKILL.md) | Search the official docs index | A signature or behavior needs the current manual |
| [`duckdb-migrate`](skills/duckdb-migrate/SKILL.md) | Move a 1.4 or 1.5 deployment to 2.0 | Upgrade, storage version, export/import, or a 1.x reader |
| [`duckdb-python`](skills/duckdb-python/SKILL.md) | Write or migrate Python client code | Code that imports `duckdb` |
| [`duckdb-spatial`](skills/duckdb-spatial/SKILL.md) | Answer location questions | Maps, lat/lng, GeoJSON, Overture, H3 |

## How the pack is organized

```
skills/
  duckdb/                  router and CLI contract
  duckdb-sql/              task skill
    references/            long lookup tables, loaded only when needed
  ...
research/                  evidence, snapshots, and the per-skill audit
scripts/                   structure checks and executable probes
evals/                     trigger cases
CONTRIBUTING.md            the skill contract
```

Load `duckdb` first when the task is not specific. It routes. The other eleven skills are written to stand alone for their job, but each deep fact has one owner. When a skill needs a fact another skill owns, it gives the one line needed to recognize the situation and links the owner.

`references/` is lookup material, not required reading. A skill links a reference at the point where the choice is made.

## What changed in 2.0

- New files use storage version 69. DuckDB 1.x cannot open them.
- `x -> x + 1` is disabled. Write `lambda x: x + 1`.
- The PEG parser is the default. `legacy_parser` is a grammar fallback, not a semantic one.
- `1 // 0` and `1 % 0` raise. `1 / 0` is still `inf`.
- `~` and `!~` are partial matches, like PostgreSQL.
- Agent mode is on when an agent environment variable is present and stdout is not a terminal, unless an output flag is passed.
- `VARIANT` is a first-class type, with shredding in database storage and Parquet.
- Triggers exist, with limits: no `BEFORE ... FOR EACH ROW`, no `UPDATE ... FOR EACH ROW`.
- Quack serves a database, and `CONNECT` routes a session to Quack, PostgreSQL, or MySQL.
- DuckLake 1.1, Iceberg REST attach options, and Delta `CREATE TABLE`, time travel, and `VARIANT`.
- Python relations are lazy, `execute()` results must be consumed, and one connection serves one call at a time.

The evidence for each claim is in [research/](research/), with the per-skill verdict in [research/08-skill-audit.md](research/08-skill-audit.md).

## Verify

```bash
python3 scripts/check-skills.py
python3 scripts/probe.py
python3 scripts/probe.py --network --write research/probe-results.txt
```

`check-skills.py` checks frontmatter, name and directory agreement, descriptions, required sections, line budgets, relative links, cross-skill names, and stale strings. `probe.py` runs the executable claims against the local binary.

Checked here on 2026-10-22 with DuckDB 2.0.0 `d54cbbe3df` on macOS arm64:

- Version gate, agent-mode truncation and footer, `-csv` behavior, JSON error split.
- Lambda syntax, `$x`, integer division, nested schemas, triggers, `MERGE`, `NEAREST`, `GROUP BY unnest`.
- Storage versions, `COPY FROM DATABASE`, `read_duckdb`.
- `VARIANT` functions, 1-based indexing, comparator, shredding syntax.
- Parquet `schema`, R-tree index scan, `SECURE VIEW`, regex `~`.
- The docs index versions and the BM25 subquery.
- A local Quack server on a non-default port and a Python 2.0.0 venv.

Not run here: a live Iceberg REST catalog, a Delta or Unity Catalog endpoint, the Claude Code plugin validator (the CLI is not installed), and a second-machine install. Those claims are labeled documented or announced in the research, not probed.

## Research

[research/README.md](research/README.md) is the index. [research/METHOD.md](research/METHOD.md) explains the confidence labels and the source order. The manual snapshots under `research/sources/` are local and reproducible with:

```bash
python3 scripts/fetch-docs.py
```

The snapshots are pinned to a commit. The live pages remain the source of truth.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before editing a skill. Run [evals/triggers.md](evals/triggers.md) after changing a description.

## License

[MIT](LICENSE), copyright 2026 duckdb-2-skills contributors.

Adapted workflows from duckdb/duckdb-skills remain under that project's MIT license, copyright 2018-2025 Stichting DuckDB Foundation. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). The documentation snapshots under `research/sources/` come from the MIT-licensed `duckdb/duckdb-web` and `duckdb/ducklake-web` repositories. DuckDB is a trademark of the DuckDB Foundation.
