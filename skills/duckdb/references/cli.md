# CLI reference

Read this when the skill needs a flag, dot command, output mode, or setting that is not in `SKILL.md`. The 2.0 manual page is linked at the end.

## Invocation order

The CLI processes arguments left to right. `-c`, `-s`, and `-f` run in the order given. The init file is the exception. It runs once at startup, before every `-cmd`, `-c`, and `-s`, wherever `-init` appears on the command line.

```bash
duckdb -csv -c "SELECT 42 AS hello" -json -c "SELECT 84 AS world"
```

```text
hello
42
[{"world":84}]
```

Each process starts empty unless a database path or an init file is given. `ATTACH` does not survive the process.

## Flags that change agent behavior

| Flag | Effect |
| --- | --- |
| `-agent` | Force agent framing on. Errors become one JSON object on stderr. |
| `-no-agent` | Force agent framing off. |
| `-json` | Render results as a JSON array. Also disables automatic agent mode. |
| `-jsonlines` | Render results as NDJSON. Also disables automatic agent mode. |
| `-csv` | Render results as CSV. Also disables automatic agent mode. |
| `-markdown` | Render a Markdown table. Also disables automatic agent mode. |
| `-box`, `-table`, `-line`, `-list`, `-column`, `-ascii`, `-html`, `-quote` | Pick another renderer. Each disables automatic agent mode. |
| `-c COMMAND` | Run one command. Later `-c` arguments still run; the first error stops the rest. |
| `-s COMMAND` | Same behavior as `-c`. |
| `-f FILE` | Run a SQL file. `~/.duckdbrc` still runs first. Stops at the first error unless `.bail off` is the first line. |
| `-cmd COMMAND` | Run a command at its argument position, after init. |
| `-init FILE` | Use `FILE` instead of `~/.duckdbrc`. |
| `-no-init` | Skip the init file entirely. |
| `-readonly` | Open the database read-only. Later `ATTACH` defaults to read-only, but an explicit `(READ_WRITE)` overrides it. |
| `-safe` | Enable safe mode with no external file access and locked configuration. The database named on the command line still opens. |
| `-storage-version VER` | Storage compatibility version for a new file only. Opening an existing file ignores it. `latest` means the 2.0 format. An invalid value exits 0 without creating a file. |
| `-bail` | Stop after the first error. |
| `-echo` | Print each command before running it. |
| `-header` / `-noheader` | Turn headers on or off. |
| `-separator SEP` | Column separator. |
| `-newline SEP` | Row separator. |
| `-nullvalue TEXT` | Text for `NULL`. Default `NULL`. |
| `-unredacted` | Allow printing secret values. Sets `allow_unredacted_secrets`. |
| `-unsigned` | Allow unsigned extensions. Development only. |
| `-ui` | Load and start the DuckDB UI on port 4213, installing it if absent. Not supported with `-readonly`. |
| `-format`, `-format-file FILE` | Format SQL instead of running it. It does not validate; invalid SQL passes through with exit 0. |
| `-manual FUNCTION` | Print the manual page for a SQL function and exit. |
| `-serve [quack[:SECRET]]` | Serve the opened database with Quack. |
| `-connect [quack[:SECRET]]` | Connect to a remote Quack server. Cannot be combined with a local database path. |
| `-version`, `-h`, `-help` | Version or help. |

`-agent` and an output flag can be combined. The flag picks the renderer; `-agent` still forces the agent contract, so errors stay JSON and the banner still prints. It does not apply the row, byte, or cell caps. `-agent -json` returns the whole JSON array. Without an explicit `-agent`, any output flag turns automatic agent mode off. In batch execution, note that a trailing `-cmd` after the final `-c` does not run.

`-ui` installs the `ui` extension from `core` on first run. The extension ships separately and can lag a release, so a fresh release may return HTTP 404 until it is promoted from `core_nightly`. Retry later. The 2.0.0 `ui` build has no binary for `osx_amd64` or `windows_arm64`. The page assets load from `https://ui.duckdb.org`, while the queries run in the local process. Use `-box` or `EXPLAIN (FORMAT WEB)` when the UI is unavailable.

Automatic activation requires three conditions. A known agent variable is present (even `AI_AGENT=0`), stdout is not a terminal, and no output flag was passed. Known variables include `AI_AGENT`, `AGENT`, `CLAUDECODE`, `CODEX_CI`, `CODEX_SANDBOX`, `CODEX_THREAD_ID`, `COPILOT_AGENT`, `COPILOT_AGENT_SESSION_ID`, `COPILOT_CLI`, `CURSOR_AGENT`, and `GEMINI_CLI`. `DUCKDB_AGENT_MODE=0` or `-no-agent` forces it off; the CLI flags win.

## Output modes

| Mode | Use |
| --- | --- |
| `duckbox` | Default interactive box table. |
| `box` | Simpler Unicode box table. |
| `markdown` | Agent mode's renderer. |
| `json` | One JSON array. Best for a parser. |
| `jsonlines` | One JSON object per line. |
| `csv` | Comma-separated. |
| `tabs` | Tab-separated. |
| `line` | One value per line. Good for wide rows. |
| `list` | Pipe-delimited values. |
| `column` | Column-aligned text. |
| `table` | ASCII-art table. |
| `latex` | LaTeX tabular. |
| `html` | HTML table. |
| `insert TABLE` | SQL `INSERT` statements. |
| `quote` | SQL-quoted values. |
| `ascii` | Unit-separator delimited. |
| `trash` | Discard output. |

## Agent mode limits

- Up to 1,000 rows and 10,000 rendered row bytes render whole.
- A larger result renders the first 20 and last 20 rows, a `… N rows omitted …` line, and a footer with the total and an order-independent hash.
- A cell truncates at 500 characters and prints `…(+N chars)`.
- Results of 1 to 9 rows have no footer. 0 rows and 10 or more do.
- `.maxrows -1` alone does not render everything; the byte cap still applies. Add `.maxbytes 0`.
- `.maxrows N` shows at most 20 head and 20 tail rows, even when `N` is larger.
- The banner, JSON errors, cost estimate, and progress go to stderr. `.timer` and `.changes` still write stdout.
- `SET max_execution_time = <milliseconds>` bounds the query. On expiry the exit code is 1 and stderr carries an `INTERRUPT` JSON object.

## Dot commands

Dot commands start at column 1, take one line, and need no semicolon.

| Command | Effect |
| --- | --- |
| `.help [PATTERN]` | Help. `.help agent` summarizes agent mode. |
| `.maxrows N` | Rows rendered whole. `-1` for all. Agent and duckbox modes. |
| `.maxbytes N` | Bytes rendered whole. `0` for all. Agent mode. |
| `.maxcellwidth N` | Characters per cell. `0` for all. Agent mode. |
| `.startup_text none` | Hide the startup line. Put it first in `~/.duckdbrc`. An rc `.mode` changes the renderer, not the agent framing. `-no-init` or an explicit output flag fixes the format. |
| `.mode MODE` | Set the output mode. `.mode` alone prints the current one. |
| `.open [--readonly] FILE` | Close the current database and open `FILE`. |
| `.read FILE` | Run a SQL file. |
| `.output FILE` | Send output to a file, or back to stdout with no argument. |
| `.once [OPTIONS] FILE` | Send only the next result to a file. |
| `.import [--csv\|--json\|--parquet] FILE TABLE` | Import a file into a table. |
| `.dump [TABLE]` | Dump database content as SQL. |
| `.schema [PATTERN]` | Show `CREATE` statements. `--no-indent` for one line each. |
| `.tables [PATTERN]` | Tables with columns, types, and row counts. In agent mode this is plain text, not Markdown. |
| `.databases` | Attached databases. In agent mode this is plain text. |
| `.indexes [TABLE]` | Indexes. |
| `.timer on\|off [DIGITS]` | Query timer. |
| `.changes on\|off` | Rows changed by the last statement. |
| `.log FILE\|stderr\|stdout\|off` | CLI logging. |
| `.web` | Render the last query graph and open it. Disabled in safe mode. |
| `.history [N]` | Command history. |
| `.serve_command COMMAND` | Change what `-serve` runs. |
| `.connect_command COMMAND` | Change what `-connect` runs. |
| `.ui_command COMMAND` | Change what `-ui` runs. |
| `.safe_mode` | Turn safe mode on. |
| `.bail on\|off` | Stop after an error. |
| `.echo on\|off` | Echo commands. |
| `.headers on\|off` | Headers. |
| `.nullvalue STRING` | Text for `NULL`. |
| `.separator COL [ROW]` | Separators. |
| `.width N...` | Minimum column widths. |
| `.exit [CODE]`, `.quit` | Exit. |
| `.export` | Does not exist. Use `EXPORT DATABASE`. |

## Settings an agent is likely to touch

| Setting | Why |
| --- | --- |
| `max_execution_time` | Wall-clock cap in milliseconds. `0` is no limit. |
| `threads` | Worker threads. Default is the system thread count. |
| `max_memory` | Memory limit. Accepts a size or a percentage of system memory; the default is 80%. |
| `temp_directory` | Spill directory. Default `.tmp` for in-memory, `<db>.tmp` for a file. |
| `max_temp_directory_size` | Cap on spill. Default 90% of available disk; it does not accept a percentage string. |
| `preserve_insertion_order` | `false` can speed bulk loads and lower memory; it gives up row order. |
| `enable_progress_bar` | Turn off for clean stderr in automation. |
| `checkpoint_on_detach` | Enum (`ENABLED`, `DISABLED`, `DEFAULT`), not a boolean. Default `DEFAULT`. |
| `storage_compatibility_version` | `latest` or a version such as `v1.5.6`. |
| `allow_persistent_secrets` | Set `false` before locking configuration. |
| `enable_external_access` | Set `false` to block file and network access. |
| `allowed_paths` | Allowlist for the file sandbox. Set before locking configuration. |
| `lock_configuration` | Freeze settings for the session. |
| `allow_unsigned_extensions` | Development only. |
| `async_threads` | Async I/O pool. Default four times `threads`, capped at 256. |
| `read_ahead_depth` | `-1` is memory-bounded. `0` disables read-ahead. |
| `variant_minimum_shredding_size` | Row-group threshold for `VARIANT` shredding. Default 30000. |
| `table_function_identifier_conversion` | Controls the deprecated implicit identifier-to-string conversion. |

Query the live list and defaults:

```sql
SELECT name, value, description FROM duckdb_settings() ORDER BY name;
```

## Safety

| Control | Blocks |
| --- | --- |
| `-safe` / `.safe_mode` | External file access, `.cd`, `.excel`, `.web`, `.read`, `.output`, `.once`, `.import`, `.log`, `.open`, `.sh`, `.system`, and `getenv`. It locks configuration before `-init` runs. The named database still opens. |
| `-readonly` | Writes to the opened database, unless an `ATTACH` says `(READ_WRITE)`. |
| `SET enable_external_access = false` | All file and network access, including the database path in some cases. |
| `SET allowed_paths = [...]` | Everything outside the listed paths. Set it before locking. |
| `SET allow_persistent_secrets = false` | New persistent secrets. |
| `SET lock_configuration = true` | Further `SET` and `RESET`. |
| `-unsigned` | Nothing; it allows unsigned extensions. Do not use outside development. |

Set the sandbox in this order. `allowed_paths` must come before `enable_external_access = false`; afterward the setting is rejected.

```sql
SET allowed_paths = ['/absolute/file.csv'];
SET enable_external_access = false;
SET allow_persistent_secrets = false;
SET lock_configuration = true;
```

External access cannot be turned back on in the same process. `-safe -init allow.sql` fails because `-safe` locks configuration before init runs; when paths must be configured first, use `.safe_mode` at the end of an init script.

## Install

| Platform | Command |
| --- | --- |
| macOS, Linux | `curl -fsSL https://install.duckdb.org | sh` |
| Homebrew | `brew install duckdb`, then check the version |
| Windows | `winget install DuckDB.cli` |
| Docker | `docker run --rm -it duckdb/duckdb` |

The install script puts the binary under `~/.duckdb/cli/<version>/`, points `latest` at it, and links `~/.local/bin/duckdb` only when that directory exists and has no `duckdb` file. Pin a version with `DUCKDB_VERSION=2.0.0` on the install command. Homebrew was still on 1.5.6 on 2026-10-22. `osx_amd64` has partial support and is dropped in 2.1; Linux requires glibc >= 2.28. Version check:

```bash
duckdb -no-agent --version
curl -fsSL https://duckdb.org/data/latest_stable_version.txt
```

## Logging

```sql
CALL enable_logging(storage = 'memory');
SELECT * FROM duckdb_logs();
```

Since 1.5 the CLI defaults to `shell_log_storage`, which `duckdb_logs` cannot query. Enable memory storage first. A bare `CALL enable_logging()` prints a warning and `INFO:QueryLog` lines to stdout, which corrupts JSON or CSV output. `enable_http_logging` and `http_logging_output` were removed in 2.0. Use `CALL enable_logging('HTTP');`.

## JSON caveats

- `-json` with multiple statements emits one JSON array per statement. That is not one valid JSON document.
- `HUGEINT` and `DECIMAL` values are strings. `NaN` and `Infinity` are bare tokens, not strict JSON.
- Duplicate column names produce duplicate keys; a parser usually keeps the last one.
- `errors_as_json = true` covers post-parse errors only. Parser errors stay text unless agent framing is on.
- `EXPLAIN ANALYZE` ignores `-json` and prints a profile.
- Interruption via SIGINT exits 1 with a table header on stdout and no JSON error on stderr. Always check the exit code.

## References

- https://duckdb.org/docs/2.0/clients/cli/arguments.html
- https://duckdb.org/docs/2.0/clients/cli/dot_commands.html
- https://duckdb.org/docs/2.0/clients/cli/output_formats.html
- https://duckdb.org/docs/2.0/clients/cli/agent_mode.html
- https://duckdb.org/docs/2.0/clients/cli/safe_mode.html
- https://duckdb.org/docs/2.0/configuration/pragmas.html
- https://duckdb.org/docs/2.0/operations_manual/logging/overview.html
