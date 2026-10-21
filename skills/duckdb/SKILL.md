---
name: duckdb
description: >
  Start here for any DuckDB 2.0 work: CLI version check, how to run SQL from
  an agent, agent mode versus JSON output, and which other duckdb-* skill to
  load. Use when the user mentions DuckDB, a .duckdb file, the duckdb CLI, or
  runs /duckdb.
---

# DuckDB 2.0 CLI contract

This pack targets DuckDB 2.0.0 LTS and newer patch releases on the 2.0 line. Codename on the GitHub release is Cyanoptera. The announcement calls the same release Cinnamon Teal.

Load another skill from the route table when the task is more specific than "run this". Do not restate this file inside those skills.

## 1. Require a 2.0 binary

```bash
duckdb --version
```

Continue only when the first line contains `v2.0`. The official installer is:

```bash
curl -fsSL https://install.duckdb.org | sh
```

That installs `~/.duckdb/cli/latest/duckdb` and links `~/.local/bin/duckdb`. If `duckdb --version` is older, call the 2.0 binary by its full path. Homebrew lagged the 2.0.0 release and was still on 1.5.6 the day after it shipped, so a `brew install duckdb` success is not a version check.

Stop if the only binary is 1.x. The SQL in this pack uses 2.0 syntax.

## 2. Run a statement

Each `duckdb` process starts empty unless you pass `-init` or a database file.

Read stdout and stderr. Agent mode writes the banner, JSON errors, row estimates, and progress to stderr.

Answers a person or a model will read:

```bash
duckdb -agent -c "SELECT 42 AS answer;"
```

Rows you will parse:

```bash
duckdb -json -c "SELECT 42 AS answer;"
```

Multi-line SQL uses a quoted heredoc:

```bash
duckdb -agent <<'SQL'
SELECT 42 AS answer;
SQL
```

`-json` without `-agent` prints errors as text. `-agent` prints errors as one JSON object on stderr. A footer that says rows were omitted, or that the query stopped early, is a sample. Add `LIMIT` or an aggregate and run again before you treat the table as complete.

`max_execution_time` is milliseconds. `0` means no limit.

```sql
SET max_execution_time = 30000;
```

If stderr prints an `estimate:` line for a scan of more than about a million rows, ask before an unbounded run.

A `~/.duckdbrc` can turn agent mode off. If the table comes back as a box drawing, rerun with `-no-init`.

## 3. New database files

A database file created by 2.0 with default settings uses storage version 69. DuckDB 1.x cannot open it. DuckDB 2.0 can still open files written by 1.x, and writing to those files does not upgrade them. Follow `duckdb-migrate` before creating or checkpointing a file that older processes must keep reading.

## 4. Route

| Task | Skill |
| --- | --- |
| Write or run SQL, triggers, lambdas | `duckdb-sql` |
| Attach a database and keep it across calls | `duckdb-session` |
| Read or convert a file, or query object storage | `duckdb-files` |
| `VARIANT` / semi-structured columns | `duckdb-variant` |
| DuckDB as a server, `CONNECT`, Postgres or MySQL pushdown | `duckdb-quack` |
| DuckLake, Iceberg, Delta | `duckdb-lakehouse` |
| Install or update extensions, custom repositories | `duckdb-extensions` |
| Search the docs index | `duckdb-docs` |
| Move a 1.x deployment to 2.0 | `duckdb-migrate` |
| Python client code | `duckdb-python` |
| Geodata, distances, Overture | `duckdb-spatial` |

Missing extension: `INSTALL AND LOAD <name>;` then retry. The rest of the install rules are in `duckdb-extensions`.

## References

- https://duckdb.org/2026/10/21/announcing-duckdb-200.html
- https://duckdb.org/docs/2.0/clients/cli/agent_mode.html
- https://duckdb.org/docs/2.0/operations_manual/migration.html
- https://duckdb.org/install/
- Release checked while writing this pack: DuckDB 2.0.0 `d54cbbe3df`, 2026-10-22. Agent-mode JSON errors, `-json` text errors, and `max_execution_time` in milliseconds were run locally.
