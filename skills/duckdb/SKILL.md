---
name: duckdb
description: >
  Gate the DuckDB 2.0 CLI binary, select agent output modes, evaluate
  result trust, and route to specialized skills. Use when the user mentions
  DuckDB, a .duckdb file, or the duckdb CLI.
---

# DuckDB 2.0

Target DuckDB 2.0.0 LTS and newer 2.0 patch releases.

## Gate the binary

Before running DuckDB commands, verify the binary version:

```bash
duckdb -no-agent --version
```

If stdout does not contain `v2.0`, stop. DuckDB 1.x is unsupported. When piping version output, pass `-no-agent` because stderr banner pollution invalidates `2>&1 | head -1`.

If DuckDB 2.0 is missing or outdated, install it:

```bash
curl -fsSL https://install.duckdb.org | sh
```

The installer places the binary in `~/.duckdb/cli/<version>/`, points `~/.duckdb/cli/latest` at it, and links `~/.local/bin/duckdb` when that directory exists without an existing `duckdb` binary. If using Homebrew, check the version immediately because Homebrew packages can lag releases. If a 2.0 binary resides outside `PATH`, invoke it by its absolute path.

## Choose the output mode

| Consumer | Command | Output characteristics |
| --- | --- | --- |
| Model reads table | `duckdb -agent -c "..."` | Compact Markdown, JSON errors on stderr, row/byte/cell caps, result hash |
| Script parses rows | `duckdb -json -c "..."` | One JSON array on stdout, text errors on stderr |
| Human reads terminal | `duckdb -box -c "..."` | Unicode box table |
| Human explores visually | `duckdb -ui` | Browser UI served at `localhost:4213` |

When passing any output flag (`-json`, `-csv`, `-box`), DuckDB disables automatic agent mode. To preserve agent framing (stderr JSON errors and banner) with another renderer, pass `-agent` explicitly (for example, `duckdb -agent -json`).

When combining `-agent` with `-json` or `-csv`, DuckDB preserves JSON errors and banners on stderr, but omits the 1,000-row, 10,000-byte, and 500-character cell caps. When results can be large, add `LIMIT` for an intentional sample or use an aggregate for a complete count.

Always read stderr. Agent mode directs its startup banner, JSON errors, cost estimates, and execution progress there. When the footer reads `first X and last Y of N rows`, the terminal display is truncated; the underlying query returned N rows and the result hash covers all N rows.

## Result trust

Before trusting output, check the exit code first, stderr second, and the result footer third.

| Signal | Meaning | Action |
| --- | --- | --- |
| Exit 0, empty stderr, `N rows, hash ...` | Complete query result | Accept output. If the query specifies `LIMIT`, do not treat as dataset total. |
| Exit 0, empty stderr, no footer, 1 to 9 rows | Complete query result (hash omitted) | Accept output. |
| `first X and last Y of N rows` | Display truncated; query returned N rows | Pass `.maxrows -1` to inspect all rows, or use an aggregate for dataset total. |
| `first X of at least N rows` or `query stopped early` | Incomplete lower bound | Stop and bound the query with selective filters. |
| Exit 1 with stderr JSON error | Query execution failed | Read the stderr JSON error. Do not parse stdout. |
| Exit 1 with header-only stdout, no JSON error | Process interrupted (SIGINT or timeout) | Rerun with bounded work or a higher timeout. |

When verifying result determinism, rerun with a different `ORDER BY`; the result hash is order-independent. Never treat a `LIMIT` query result as complete for the underlying dataset.

Before parsing `-json` output, check the exit code and stderr; on failure, `-json` can emit an unclosed `[` on stdout. When executing multiple statements under `-json`, DuckDB emits one JSON array per statement rather than a single document. Note that `NaN` and `Infinity` emit as bare tokens, violating strict JSON. When running `EXPLAIN ANALYZE`, DuckDB prints a formatted profile text block, ignoring `-json`.

When launching `duckdb -ui`, DuckDB auto-installs the `ui` extension on initial run. If installation fails, note that extension builds can lag releases and lack 2.0.0 binaries for `osx_amd64` or `windows_arm64` (see [references/cli.md](references/cli.md)).

## Run SQL

Every `duckdb` process starts with an isolated in-memory database and executes `~/.duckdbrc` unless `-no-init` is passed. When session state must persist across invocations, use `duckdb-session`.

```bash
duckdb -agent -c "SELECT 42 AS answer;"
duckdb -agent <<'SQL'
.maxrows 50
SELECT 42 AS answer;
SQL
duckdb -f query.sql
duckdb -init .duckdb/state.sql -agent -c "SHOW TABLES;"
```

When passing `-init FILE`, DuckDB replaces `~/.duckdbrc`. When passing `-no-init`, DuckDB skips all initialization files.

When combining a dot command with SQL statements, use `-cmd` or a heredoc; a single `-c` string cannot mix both. When passing `-cmd COMMAND`, DuckDB executes it at its positional argument index, even following the last `-c` or a completed `-f`.

When running `-f FILE`, execution halts at the first error by default; stdin input continues past errors. When passing `-readonly`, DuckDB denies write access to the opened database, unless overridden by an explicit `ATTACH ... (READ_WRITE)`. When passing `-safe`, DuckDB disables external file access and locks configuration before `-init` runs, while still opening any database file specified on the command line.

To bound query duration, configure `max_execution_time` in milliseconds (`0` disables timeout):

```sql
SET max_execution_time = 30000;
```

If stderr prints an `estimate:` line scanning 1,000,000 or more rows, request user confirmation before running an unbounded query.

## Storage compatibility

When DuckDB 2.0 creates a new database file under default settings, it writes storage version 69. DuckDB 1.x cannot open version 69 files. DuckDB 2.0 reads legacy 1.x files and preserves their existing storage version across writes. Before creating a file destined for older clients, consult `duckdb-migrate`.

## Route

| Task | Skill |
| --- | --- |
| Write or run SQL, lambdas, triggers, nested schemas | `duckdb-sql` |
| Diagnose a slow query, plan, spill, or Parquet layout | `duckdb-profile` |
| Attach a database and keep it across calls | `duckdb-session` |
| Read, convert, or batch-ingest a file, or query object storage | `duckdb-files` |
| `VARIANT` or semi-structured columns | `duckdb-variant` |
| Full-text search, BM25, HNSW, or vector search | `duckdb-search` |
| dbt v2 project, profile, or dbt-duckdb migration | `duckdb-dbt` |
| Serve a database, `CONNECT`, Postgres or MySQL pushdown | `duckdb-quack` |
| DuckLake, Iceberg, Delta | `duckdb-lakehouse` |
| Install or update extensions | `duckdb-extensions` |
| Search the 2.0 manual | `duckdb-docs` |
| Move a 1.x deployment to 2.0 | `duckdb-migrate` |
| Python client code | `duckdb-python` |
| Geodata, distances, Overture | `duckdb-spatial` |

When configuring a Model Context Protocol client or server, consult [references/mcp.md](references/mcp.md). The `duckdb_mcp` community extension targets 2.0; the MotherDuck local server pins 1.5.6.

When an error names a specific feature or symptom, route to the owning skill:

| Symptom | Skill or action |
| --- | --- |
| `Deprecated lambda arrow`, `Division by zero`, `nested schema`, `BEFORE ... FOR EACH ROW` | `duckdb-sql` |
| `sqlite_master` does not exist, `read_csv` on a Parquet file, a secret validation failure | `duckdb-files` |
| `Trying to read a database file with version number 69` | `duckdb-migrate` |
| `Extension ... not found`, `no update available` | `duckdb-extensions` |
| `Out of Memory Error`, actual rows dwarfing estimate, `Row Groups Scanned` near the total | `duckdb-profile` |
| Output is box drawing under an agent | Check `~/.duckdbrc`; rerun with `-no-init` |

## Verify

Run verification commands to confirm CLI version and agent framing:

```bash
duckdb -no-agent --version
duckdb -agent -c "SELECT 42 AS answer;"
duckdb -json -c "SELECT 42 AS answer;"
```

The version check must print `v2.0` on stdout. The agent query must render a compact Markdown table. The JSON query must emit `[{"answer":42}]`.

## References

- [Command line client](https://duckdb.org/docs/2.0/clients/cli/overview.html) owns the CLI surface.
- [Agent mode](https://duckdb.org/docs/2.0/clients/cli/agent_mode.html) owns output limits and stderr splitting.
- [Command line arguments](https://duckdb.org/docs/2.0/clients/cli/arguments.html) owns the flag list.
- [Output formats](https://duckdb.org/docs/2.0/clients/cli/output_formats.html) owns the renderer list.
- [Migration guide](https://duckdb.org/docs/2.0/operations_manual/migration.html) owns the storage break.
- [Install](https://duckdb.org/install/) owns platform install commands.
- The complete flag, dot command, and setting tables are in [references/cli.md](references/cli.md).
- MCP configuration and security controls are in [references/mcp.md](references/mcp.md).
- Release verified against DuckDB 2.0.0 `d54cbbe3df`. Agent limits and JSON error splitting validated locally.
