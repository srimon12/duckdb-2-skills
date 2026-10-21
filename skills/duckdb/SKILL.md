---
name: duckdb
description: >
  Start here for any DuckDB 2.0 work. Gate the CLI version, choose the output
  mode for an agent, and route to the task skill. Use when the user mentions
  DuckDB, a .duckdb file, or the duckdb CLI.
---

# DuckDB 2.0

This pack targets DuckDB 2.0.0 LTS and newer 2.0 patch releases. The GitHub release is Cyanoptera. The announcement calls the same release Cinnamon Teal.

## Gate the binary

```bash
duckdb -no-agent --version
```

The version is on stdout and must contain `v2.0`. Stop on 1.x. Without `-no-agent`, a pipe can put the agent banner on stderr, so `2>&1 | head -1` is not the version.

```bash
curl -fsSL https://install.duckdb.org | sh
```

That installs under `~/.duckdb/cli/<version>/`, points `~/.duckdb/cli/latest` at it, and links `~/.local/bin/duckdb` when that directory exists and has no `duckdb` file. Homebrew can lag a release, so check the version after any install. If a 2.0 binary lives elsewhere, call it by full path.

## Choose the output mode

| Consumer | Command | What it gets |
| --- | --- | --- |
| A model reads the table | `duckdb -agent -c "..."` | Compact Markdown, JSON errors on stderr, a row cap, a result hash |
| A script parses the rows | `duckdb -json -c "..."` | One JSON array on stdout; errors as text on stderr |
| A person reads a terminal | `duckdb -box -c "..."` | A box table |

`-csv`, `-json`, and every other output flag disable automatic agent mode. Pass `-agent` explicitly if you want agent framing with a different renderer.

`-agent -json` and `-agent -csv` keep the JSON errors and the banner, but they do not apply the 1,000-row, 10,000-byte, or 500-character caps. Add `LIMIT` or an aggregate when a result could be large.

Read stderr. Agent mode writes its banner, JSON errors, cost estimates, and progress there. A footer that says `first 20 and last 20 of N rows` means the table is a sample. Add `LIMIT` or an aggregate before you treat it as complete. Results of 1 to 9 rows have no hash footer; 0 and 10 or more do.

`-json` on error can leave a partial `[` on stdout. Check the exit code and stderr before parsing. `-json` with multiple statements emits one array per statement, and `NaN`/`Infinity` are not strict JSON. `EXPLAIN ANALYZE` prints a profile, not JSON, even with `-json`.

## Run SQL

Each `duckdb` process starts with a fresh in-memory database, then runs `~/.duckdbrc` unless `-no-init` is set. `ATTACH` dies with the process, so use `duckdb-session` when state must survive.

```bash
duckdb -agent -c "SELECT 42 AS answer;"
duckdb -agent <<'SQL'
SELECT 42 AS answer;
SQL
duckdb -f query.sql
duckdb -init .duckdb/state.sql -agent -c "SHOW TABLES;"
```

`-init` replaces `~/.duckdbrc`. `-no-init` skips both. `-cmd` runs at its argument position. `-f` runs a file and stops at the first error by default; stdin continues. A `-c` string cannot hold a dot command plus SQL; use `-cmd` or a heredoc.

`-readonly` opens without write access, but an explicit `ATTACH ... (READ_WRITE)` can override it. `-safe` blocks external file access, still opens the database named on the command line, and locks configuration before `-init` runs.

`max_execution_time` is milliseconds. `0` means no limit.

```sql
SET max_execution_time = 30000;
```

If stderr prints an `estimate:` line for a scan of more than a million rows, ask before an unbounded run.

## New database files

A file created by 2.0 with default settings uses storage version 69. DuckDB 1.x cannot open it. 2.0 opens files written by 1.x and keeps their old version when it writes to them. Read `duckdb-migrate` before creating a file that older processes must read.

## Route

| Task | Skill |
| --- | --- |
| Write or run SQL, lambdas, triggers, nested schemas | `duckdb-sql` |
| Attach a database and keep it across calls | `duckdb-session` |
| Read or convert a file, or query object storage | `duckdb-files` |
| `VARIANT` or semi-structured columns | `duckdb-variant` |
| Serve a database, `CONNECT`, Postgres or MySQL pushdown | `duckdb-quack` |
| DuckLake, Iceberg, Delta | `duckdb-lakehouse` |
| Install or update extensions | `duckdb-extensions` |
| Search the 2.0 manual | `duckdb-docs` |
| Move a 1.x deployment to 2.0 | `duckdb-migrate` |
| Python client code | `duckdb-python` |
| Geodata, distances, Overture | `duckdb-spatial` |

When an error names a feature, load the owner instead of guessing:

| Symptom | Skill |
| --- | --- |
| `Deprecated lambda arrow`, `Division by zero`, `nested schema`, `BEFORE ... FOR EACH ROW` | `duckdb-sql` |
| `sqlite_master` does not exist, `read_csv` on a Parquet file, a secret validation failure | `duckdb-files` |
| `Trying to read a database file with version number 69` | `duckdb-migrate` |
| `Extension ... not found`, `no update available` | `duckdb-extensions` |
| Output is box drawing under an agent | check `~/.duckdbrc`; rerun with `-no-init` |

## Verify

```bash
duckdb --version
duckdb -agent -c "SELECT 42 AS answer;"
duckdb -json -c "SELECT 42 AS answer;"
```

The first must print `v2.0`. The second must print a Markdown table. The third must print `[{"answer":42}]`.

## References

- [Command line client](https://duckdb.org/docs/2.0/clients/cli/overview.html) owns the CLI surface.
- [Agent mode](https://duckdb.org/docs/2.0/clients/cli/agent_mode.html) owns the output limits and the stderr split.
- [Command line arguments](https://duckdb.org/docs/2.0/clients/cli/arguments.html) owns the flag list.
- [Output formats](https://duckdb.org/docs/2.0/clients/cli/output_formats.html) owns the renderer list.
- [Migration guide](https://duckdb.org/docs/2.0/operations_manual/migration.html) owns the storage break.
- [Install](https://duckdb.org/install/) owns the platform commands.
- The full flag, dot-command, and setting tables are in [references/cli.md](references/cli.md).
- Release checked while writing this pack: DuckDB 2.0.0 `d54cbbe3df`, 2026-10-22. Agent-mode limits and the JSON error split were run locally.
