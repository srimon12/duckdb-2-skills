# duckdb-2-skills

Agent skills for [DuckDB 2.0.0 LTS](https://duckdb.org/2026/10/21/announcing-duckdb-200.html), released 2026-10-21. The GitHub release is named Cyanoptera. The announcement calls the same release Cinnamon Teal.

This is an independent pack. It is not a fork of [duckdb/duckdb-skills](https://github.com/duckdb/duckdb-skills) and it is not published by the DuckDB Foundation. Where a workflow is adapted from that MIT-licensed repo, the skill says so, and the copyright notice is in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

The old pack was written for DuckDB 1.x and for Claude Code session logs. DuckDB 2.0 changes the CLI, the storage format, lambdas, the parser, and the lakehouse extensions. These skills were rewritten around that release. Each skill ends with the manual pages it depends on.

## Skills

| Skill | What it owns |
| --- | --- |
| `duckdb` | CLI must be 2.0 or newer. `-agent` for answers, `-json` for rows you will parse. Routes to the other skills. |
| `duckdb-sql` | Friendly SQL, `lambda` syntax, `$x` variables, triggers, nested schemas, integer division. |
| `duckdb-session` | Attach a native DuckDB file and restore it with `duckdb -init` on a `state.sql` file. |
| `duckdb-files` | Read or convert CSV, Parquet, JSON, Avro, Excel, SQLite, HTTP, and object storage. |
| `duckdb-variant` | `VARIANT` columns, `variant_*` functions, shredding, Parquet. |
| `duckdb-quack` | Quack server, `CONNECT`, Postgres and MySQL pushdown. Localhost by default. |
| `duckdb-lakehouse` | DuckLake 1.1, Iceberg REST attach options, Delta `CREATE TABLE` and time travel. |
| `duckdb-extensions` | `INSTALL AND LOAD`, community extensions, `UPDATE EXTENSIONS`, custom repositories. |
| `duckdb-docs` | Full-text search of the 2.0 docs index and the DuckLake docs index. |
| `duckdb-migrate` | 1.4 or 1.5 to 2.0, especially storage version 69. |
| `duckdb-python` | Python client breaks from 1.x to 2.0. |
| `duckdb-spatial` | Spatial extension and Overture Maps, with the release id read from the STAC catalog. |

`read-memories` from the old pack is not here. It searched Claude Code session logs, which is not a DuckDB 2.0 job.

## Install

The CLI has to be DuckDB 2.0 or newer.

```bash
curl -fsSL https://install.duckdb.org | sh
duckdb --version
```

`duckdb --version` must print `v2.0`. On 2026-10-22 the official installer shipped 2.0.0 and Homebrew was still on 1.5.6. Check the version after either install.

Grok, this repository:

```bash
mkdir -p .grok/skills
cp -R skills/. .grok/skills/
```

Grok, every project:

```bash
mkdir -p ~/.grok/skills
cp -R skills/. ~/.grok/skills/
```

Claude Code, from a clone of this repo:

```bash
claude --plugin-dir .
```

Claude Code, from GitHub:

```
/plugin marketplace add srimon12/duckdb-2-skills
/plugin install duckdb-2-skills@duckdb-2-skills
```

The marketplace name is `duckdb-2-skills`, so it does not collide with `duckdb/duckdb-skills`.

## What changed relative to the 1.x skills

The docs search database no longer has a `lts` version. On 2026-10-22 it had `2.0` and `blog`. Filtering `match_bm25(...) AS score` with `WHERE score IS NOT NULL` in the same select fails on 2.0, so `duckdb-docs` wraps the call.

`x -> x + 1` is disabled. The skills write `lambda x: x + 1`.

A new `.duckdb` file is storage version 69. DuckDB 1.x cannot open it. `duckdb-session` says so before it creates a file. `duckdb-migrate` has the pin and the export/import path.

`sqlite_master(path)` is not a function in 2.0. SQLite files are `ATTACH ... (TYPE sqlite)`.

Overture's March 2026 paths in the old spatial notes are expired, and `categories.primary` was removed. `duckdb-spatial` reads `latest` from the STAC catalog and filters `taxonomy.primary`.

Agent mode is on when the CLI sees an agent and stdout is not a terminal, unless you pass `-csv` or `-json`. The old skills always passed `-csv`, which turns that mode off. This pack uses `-agent` when a model will read the table. Errors in that mode are JSON on stderr.

## Checked on 2.0.0

Local binary: DuckDB 2.0.0 `d54cbbe3df`, 2026-10-22.

Ran here: agent-mode JSON errors, lambda syntax, `$x`, `variant_typeof`, a row trigger, nested schemas and the `USE` error, `duckdb_tables()` columns, the docs index version counts, the FTS subquery, a keyless S3 region secret, the Overture STAC `latest` field, and `max_execution_time` as milliseconds.

Not ran here: a Quack server with a second client, a DuckLake migration, or an Iceberg or Delta catalog. Those skills follow the 2.0 manual and the DuckLake 1.1 post, and they say where a signature disagrees between the blog and the core page.

## Design notes

The Quack FAQ still calls the protocol unstable after the 2.0 polish. `duckdb-quack` says that. Notes from the research pass are not in this repository.

## License

[MIT](LICENSE), copyright 2026 duckdb-2-skills contributors.

Adapted workflows from duckdb/duckdb-skills remain under that project's MIT license, copyright 2018-2025 Stichting DuckDB Foundation. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
