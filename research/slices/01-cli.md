# Slice: CLI

Status: complete
Scope: DuckDB CLI contract for agents: flags and precedence, agent mode, output formats, dot commands, safe/read-only/external access, settings defaults, storage, install paths, logging. Audits `skills/duckdb/SKILL.md` and the install/invocation claims in `README.md`.
Sources: `research/sources/duckdb-2.0/` (below, abbreviated `S/`); `https://duckdb.org/install/?environment=cli`; `https://duckdb.org/2026/10/21/announcing-duckdb-200.html`; local `duckdb` 2.0.0 `d54cbbe3df` on macOS arm64.

## Verified facts

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| F1 | `duckdb --version` prints `v2.0.0 (Cyanoptera) d54cbbe3df` to **stdout**, exit 0. Under automatic agent mode it also prints `duckdb agent mode on: ...` to **stderr**, so `2>&1 \| head -1` is not the version. | Probe; `S/clients/cli/overview.md` | Probed |
| F2 | `-init FILE` replaces `~/.duckdbrc` (not additive) and runs before every `-cmd`, `-c`, `-s`, and positional SQL, wherever it appears in argv. | `S/clients/cli/arguments.md`; probe `-init initA.sql` printed only INIT_A, no RC | Probed |
| F3 | `-no-init` skips the init file. It wins over `-init` in either order (`-init A -no-init` and `-no-init -init A` both skip). | Probe | Probed |
| F4 | `-cmd CMD` runs at its argv position, after init and between `-c` commands; multiple are allowed. A trailing `-cmd` after the last `-c` or a successful `-f` also runs; a `-f` error exits before later commands. | Probe `-c one -cmd .print BETWEEN -c two` printed BETWEEN; `-c one -cmd .print B` printed B; `-f file -cmd "SELECT 2"` printed the later result | Probed |
| F5 | `-c CMD` executes CMD and continues to later arguments; two `-c` both run. It is not "exit immediately" when more argv follows. The first error aborts later `-c` args and exits 1. | Probe; `S/clients/cli/arguments.md` | Probed |
| F6 | A dot command plus SQL in one `-c` string fails: `.maxrows 5\nSELECT 1` → `Invalid usage of command '.maxrows'`, exit 1. A lone dot command in `-c` works. Use `-cmd` or stdin/`-f` for scripts. | Probe | Probed |
| F7 | `-s CMD` behaves like `-c CMD` in probes: dot command alone works, multiple statements run, exit 1 on error. | Probe | Probed |
| F8 | `-f FILE` runs the file after init and **bails on the first error by default**. `.bail off` as the first line restores continue-on-error. Stdin defaults to bail **off**. | Probe `errs.sql`: `-f` stopped, `-f` + `.bail off` continued, `< errs.sql` continued | Probed |
| F9 | Positional SQL always runs **after** all `-c` arguments, regardless of its position in argv. | Probe `duckdb :memory: "SELECT 'POS'" -c "SELECT 'C'"` printed C then POS | Probed |
| F10 | `-readonly` requires an existing file; a missing file and `:memory:` both fail (`Cannot launch in-memory database in read-only mode!`). It makes later `ATTACH` default to read-only, but an explicit `(READ_WRITE)` overrides it. | Probe | Probed |
| F11 | `-safe` sets `enable_external_access=false`, disables `.cd .excel .import .log .once .open .output .read .sh .system` and `.web`, disables `getenv`, and locks configuration. It cannot be undone in-session. | `S/clients/cli/safe_mode.md`; probes | Probed |
| F12 | `-storage-version VER` selects the storage version for **new** database files only; opening an existing file ignores it (no upgrade or downgrade). `latest` is accepted. An invalid version prints `duckdb: Error: unknown argument ...` and exits **0**. | `S/internals/storage.md`; probes on `def.db`, `sv15.db` | Probed |
| F13 | `-json` sets output mode `json` (array of objects). It does not add agent limits or the footer, and errors stay text unless agent framing or `errors_as_json` applies. | Probe; `S/clients/cli/arguments.md` | Probed |
| F14 | `-jsonlines` emits NDJSON, one object per row. Multiple statements still produce one stream per statement, which is valid NDJSON but heterogeneous. | Probe | Probed |
| F15 | `-csv` sets output mode CSV and **disables automatic agent mode**. NULL renders as the literal `NULL` by default. | Probe; `S/guides/troubleshooting/command_line.md` | Probed |
| F16 | `-markdown` is a plain output mode: Markdown table, no row/byte caps, no hash footer, no JSON errors. It is not agent mode. | Probe | Probed |
| F17 | `-agent` forces agent **framing** (banner, JSON errors, estimates, progress) and renders Markdown when no output-mode flag is present. With `-json`/`-csv` it keeps that mode's result format but keeps agent framing. | Probes `-agent -json`, `-agent -csv`; `S/clients/cli/agent_mode.md` | Probed |
| F18 | `-no-agent` forces framing off, but a `~/.duckdbrc` `.mode` can still change the rendered format (e.g. Markdown from an rc file with `-no-agent`). | Probe; `S/clients/cli/agent_mode.md` | Probed |
| F19 | `-ui` loads and starts the UI extension, installing it if absent, and opens the browser. Default port 4213; `-ui -readonly` is unsupported. | `S/core_extensions/ui.md`; `S/clients/cli/arguments.md` | Documented; server startup probed |
| F20 | `-format` formats SQL read from stdin to stdout without executing it and without validating it (`SELEC 1` passes through, exit 0). `-format-file FILE` does the same for a file. | Probe; `S/clients/cli/arguments.md` | Probed |
| F21 | `-manual FUNCTION` prints signatures, description, and examples to stdout and exits 0; it needs no database. The manual documents wildcards (`.manual list_%`). | Probe; `S/clients/cli/dot_commands.md` | Probed / Documented |
| F22 | `-unredacted` sets `allow_unredacted_secrets=true` at startup. In 2.0.0 `duckdb_secrets().secret_string` still showed `secret=redacted`; the flag's observable effect was not found. `SET allow_unredacted_secrets` fails at runtime. | Probe; `S/clients/cli/arguments.md`; `S/operations_manual/securing_duckdb/overview.md` | Probed / Uncertain |
| F23 | `-unsigned` sets `allow_unsigned_extensions=true` at startup. `SET allow_unsigned_extensions` fails with `Cannot change ... while database is running`. | Probe; `S/clients/cli/arguments.md` | Probed |
| F24 | `-serve [quack[:SECRET]]` runs the `.serve_command` (default `quack_serve`) for the opened DB; default is in-memory `localhost:9494`. `-connect [TYPE[:SECRET]]` runs `.connect_command` (default `CONNECT`); default type `quack`; it cannot be combined with a local DB path. | `S/clients/cli/arguments.md`; probe `-connect` without server → `Invalid Input Error: Authentication failed` | Documented / Probed |
| F25 | `-bail` stops after an error; `-no-stdin` exits after options instead of reading stdin; `-echo` prints SQL before execution to stdout; `-header`/`-noheader` affect non-duckbox modes only; `-separator`, `-newline`, `-nullvalue` change text separators. | `S/clients/cli/arguments.md`; probes | Probed |
| F26 | An unknown option (`-bogus`, `-tabs`) prints `Unknown Option Error` and exits **1**. `-tabs` does not exist as a flag; `tabs` is only a `.mode`. | Probe; `S/clients/cli/arguments.md` | Probed |
| F27 | Automatic agent mode requires all three: a known agent env var is **present** (even `AI_AGENT=0`), stdout is not a TTY, and no output-mode flag was passed. Known vars include `AI_AGENT`, `AGENT`, `CLAUDECODE`, `CODEX_CI`, `CODEX_SANDBOX`, `CODEX_THREAD_ID`, `COPILOT_AGENT`, `COPILOT_AGENT_SESSION_ID`, `COPILOT_CLI`, `CURSOR_AGENT`, `GEMINI_CLI`. | Probes per var; `strings` on the binary; `S/clients/cli/agent_mode.md` | Probed |
| F28 | `DUCKDB_AGENT_MODE=0/false/no` forces off; `1/true/yes` (and any other non-off value) forces on. CLI flags win: `DUCKDB_AGENT_MODE=0 -agent` is on; `=1 -no-agent` is off. | Probes | Probed |
| F29 | Automatic agent mode is disabled by **any** output-mode flag (`-csv`, `-json`, `-jsonlines`, `-markdown`, `-line`, `-list`, `-box`, `-table`, `-column`, `-ascii`, `-html`, `-quote`), not just `-csv`/`-json`. | Probe matrix, all had empty stderr | Probed |
| F30 | Agent result limits are **1,000 rows**, **10,000 rendered row bytes**, and **500 characters per cell**. Exceeding a limit renders head/tail only. | `S/clients/cli/agent_mode.md`; `.help agent`; probes | Probed |
| F31 | When truncated, at most **20 head + 20 tail** rows are shown, with an ellipsis row (`… N rows omitted …`). `.maxrows N` splits N as ceil(N/2) head / floor(N/2) tail, each capped at 20. `.maxrows 100` on 5,000 rows still shows only 20+20. | Probes N=1..41 | Probed |
| F32 | Footer forms: `100 rows, hash 142834df7ce17104`; `first 20 and last 20 of 2000 rows (.maxrows -1 for all), hash a989b1ca140b5ed3`; `first 20 and last 20 of 100 rows (.maxbytes 0 for all), hash ...`; `0 rows, hash 0000000000000000`. Results of 1–9 rows have **no footer**; 0 and ≥10 rows do. | Probes n=0,1,8,9,10,11 | Probed |
| F33 | The hash is order-independent (`ORDER BY i DESC` gives the same hash) and stable across runs. It is not printed for 1–9 row results. | Probes | Probed |
| F34 | `.maxrows -1` alone does **not** render everything; the 10,000-byte cap still truncates (`first 20 and last 20 ... (.maxbytes 0 for all)`). `.maxrows -1` plus `.maxbytes 0` renders all 2,000 rows with a `2000 rows, hash ...` footer. | Probes | Probed |
| F35 | The estimate line appears when the query reads **≥ 1,000,000** rows: `estimate: ~2000000 rows read (range ~2000000), ~1 rows returned`. It is stderr, agent-only, and the "returned" number is an estimate (a `WHERE i<5` scan estimated `~400000` returned). | Probes n=999999/1000000/1000001; `S/clients/cli/agent_mode.md` | Probed |
| F36 | Progress lines are stderr and start after `progress_bar_time` (default 2000 ms): `progress: 46% (elapsed 2.0s, remaining ~2.3s)`, then `progress: done (elapsed 4.3s)`. Updates roughly every 5 s. | Probe 1.2B-row scan; `S/clients/cli/output_formats.md`, `S/configuration/pragmas.md` | Probed |
| F37 | `max_execution_time` is milliseconds, default 0 (no limit), per-connection with a global fallback. On expiry: exit 1 and `{"exception_type":"INTERRUPT","exception_message":"Query exceeded maximum execution time"}`. | Probe; `S/configuration/pragmas.md` | Probed |
| F38 | Agent errors are one JSON object on **stderr**, exit 1. Shape varies by class: Parser has `exception_type`, `exception_message`, `location`, `position`, `error_subtype`; Catalog adds `type`, `name`, `candidates`; Conversion has no `error_subtype`; INTERRUPT has only type+message. | Probes e1/e2/e6/m3 | Probed |
| F39 | A runtime error can leave a header-only table or earlier rows on **stdout** before the JSON error on stderr; exit 1. DDL (`CREATE TABLE`) succeeds with exit 0 and **zero stdout bytes**. | Probes | Probed |
| F40 | `errors_as_json=true` makes post-parse errors JSON, but **syntax/parser errors stay text** even when set in `~/.duckdbrc`. Only agent mode (or `-agent -json`) made parser errors JSON. | Probes j1/j2, home10 | Probed |
| F41 | `-agent -json` and `-agent -csv` do **not** apply the row/byte/cell limits: 2,000 rows came back whole as JSON/CSV. They keep JSON errors on stderr and the banner. | Probe | Probed |
| F42 | `-json` serializes HUGEINT and DECIMAL as **strings** (`"1"`, `"1.50"`), BLOB as a raw string, DATE/TIMESTAMP as strings, and NaN/Infinity as bare `NaN`/`Infinity` (not valid RFC 8259 JSON; `jq` maps them to null/max-double). | Probe | Probed |
| F43 | `-json` with multiple statements concatenates one JSON array **per statement**, not one array for the batch: `SELECT 1; SELECT 2` → `[{"a":1}]\n[{"b":2}]`. This is not a single valid JSON document. | Probe | Probed |
| F44 | `-json` emits duplicate keys for duplicate column names: `SELECT 1 AS a, 2 AS a` → `[{"a":1,"a":2}]`. | Probe | Probed |
| F45 | `-csv` has no type/null fidelity: NULL is the literal `NULL` unless `-nullvalue` is changed, and `-nullvalue ''` makes NULL indistinguishable from an empty string. Multiple statements produce multiple headers. | Probe; `S/clients/cli/output_formats.md` | Probed |
| F46 | Agent `EXPLAIN` is a compact indented text plan (`UNGROUPED_AGGREGATE (est=1) ...`) instead of the duckbox box plan. `EXPLAIN ANALYZE` adds `rows=`/`time=` per node. | Probe | Probed |
| F47 | In agent mode `.tables` prints one plain line per table (`memory.main.t (table, ~0 rows): x INTEGER`) and `.databases` prints `..databases (table): memory (memory), r2 /path`. This is not Markdown. In non-agent mode both render ANSI-colored duckbox even when piped. | Probes | Probed |
| F48 | `.timer on` prints `Run Time (s): real ... user ... sys ...` to **stdout** after the result, in agent and non-agent mode. `.changes on` prints `changes: N   total_changes: M` to stdout. Neither moves to stderr in agent mode. | Probes | Probed |
| F49 | Dot commands are spelled lowercase in `.help`, need no leading whitespace, and take no trailing semicolon. Exact spellings: `.maxrows`, `.maxbytes`, `.maxcellwidth`, `.startup_text`, `.mode`, `.open`, `.read`, `.output`, `.once`, `.import`, `.schema`, `.tables`, `.databases`, `.timer`, `.changes`, `.log`, `.web`, `.history`, `.serve_command`, `.connect_command`, `.help`. There is **no `.export`**. | `S/clients/cli/dot_commands.md`; `.help`; probe `.export` → `Unknown Command Error` | Probed |
| F50 | `.startup_text none\|version\|all` controls the startup text. As the first line of `~/.duckdbrc`, `.startup_text none` hides the agent-mode banner. Setting it via `-f`/`-c` is too late. | Probe home1; `S/clients/cli/dot_commands.md` | Probed |
| F51 | `.schema` pretty-prints by default in 2.0; `--no-indent` (alias `--no-format`) prints the stored single-line form; `--indent` (alias `--format`) forces pretty printing. | Probe; `S/clients/cli/dot_commands.md` | Probed |
| F52 | `.open` closes the current DB and reopens: options `--new`, `--nofollow`, `--readonly`, `--sql`. `--readonly` requires an existing file. `.open` with no arg opens a fresh in-memory DB. | Probes for `--readonly`/`--new`/`--sql`; `S/clients/cli/dot_commands.md` | Probed / Documented |
| F53 | `.import FILE TABLE` uses `read_csv`/`read_json`/`read_parquet`, infers format from extension, accepts `--csv/--json/--parquet` and reader parameters (`--delimiter`, `--header`), and creates the table if absent. | Probe; `S/clients/cli/dot_commands.md` | Probed |
| F54 | `.history` and `shell_history()` are populated for piped stdin scripts, not only interactive use; `.history` itself appears as an entry. With `-c` the history is empty. | Probes; `S/clients/cli/dot_commands.md` says interactive only | Probed / contradicts docs |
| F55 | In `-safe` mode the exact errors are `.read cannot be used in -safe mode`, `.output/.once/.excel cannot be used in -safe mode`, `.import/.log/.open/.sh` similarly. `.mode` still works. | Probes | Probed |
| F56 | `allowed_paths`/`allowed_directories` must be set **before** `enable_external_access=false`; afterwards `SET allowed_paths` fails with `Cannot change allowed_paths when enable_external_access is disabled`. Paths set first remain readable after `.safe_mode` or disabling external access. | Probes | Probed |
| F57 | `-safe` locks configuration before init runs: `-safe -init allow.sql` fails at `SET allowed_paths`, and the init error is fatal (`Encountered errors while executing init file ... Exiting`). `.safe_mode` at the end of an init script is not equivalent: it permits paths configured before it. | Probes allow.sql/allow2.sql | Probed |
| F58 | `enable_external_access` can be turned off at runtime but **not back on**: `SET enable_external_access=true` → `Cannot enable external access while database is running`. | Probe | Probed |
| F59 | `lock_configuration=true` blocks later `SET`s (`Cannot change configuration option "threads" - the configuration has been locked`); keys listed in `allowed_configs` before locking remain settable. | Probe | Probed |
| F60 | `allow_persistent_secrets` is runtime-settable; `false` blocks new `CREATE PERSISTENT SECRET` but does **not** unload persistent secrets already loaded at startup. In `-safe`, `duckdb_secrets()` failed because the secret directory was inaccessible. | Probes home4 | Probed |
| F61 | Default secret display redacts the value: `...;key_id=AKIA_TEST;region=us-east-1;secret=redacted`; key IDs and regions remain visible. | Probe | Probed |
| F62 | Defaults from `duckdb_settings()` on this 8-core host: `memory_limit`/`max_memory` `12.7 GiB` (80% RAM, accepts `'50%'`), `threads`/`worker_threads` `8` (0 rejected), `temp_directory` `.tmp` in-memory / `<db>.tmp` for a file, `max_temp_directory_size` `90% of available disk space` (does **not** accept `'10%'`), `preserve_insertion_order` `true`, `max_expression_depth` `1000`, `errors_as_json` `false`, `checkpoint_on_detach` `DEFAULT`, `storage_compatibility_version` `latest`, `enable_progress_bar` `true` on a TTY and `false` when piped without agent, `progress_bar_time` `2000`. | Probes; `S/configuration/overview.md`; `S/operations_manual/limits.md` | Probed |
| F63 | New 2.0 files are storage version **69** (v2.0.0). `duckdb_databases().tags` reports `{storage_version=v2.0.0+}`; the on-disk header at offset 12 holds **999**, not 69. A v1.5.0 file stays `v1.5.0+` after 2.0 writes to it. | `S/internals/storage.md`; probes `hexdump`, tags | Probed |
| F64 | `SET storage_compatibility_version='v1.5.0'` before `ATTACH 'new.db'` creates that new DB as v1.5.0+, but setting it after the primary DB is open does **not** downgrade the primary file. Use `-storage-version` before the filename. | Probes `scv.db`, `setmain.db` | Probed |
| F65 | Clean exit checkpoints and removes the `.wal`; a killed process leaves `<db>.wal`, and the next open replays it and checkpoints on clean exit. `checkpoint_on_detach='DISABLED'` leaves a `.wal` after `DETACH`; `ENABLED`/`DEFAULT` do not. | Probes walf.db, det.db | Probed |
| F66 | Official installer installs `~/.duckdb/cli/<version>/duckdb`, points `~/.duckdb/cli/latest` at it, and prints an `export PATH=...` hint. It creates `~/.local/bin/duckdb` only if `~/.local/bin` exists, is writable, and has no `duckdb` file. | `S/operations_manual/installing_duckdb/install_script.md`; fetched `install.sh` lines 349–365; local symlink | Probed |
| F67 | Homebrew `duckdb` is still **1.5.6** on 2026-10-22 (`brew info duckdb`: stable 1.5.6). Official page also lists winget `DuckDB.cli` and Docker `duckdb/duckdb`; version pinning uses `DUCKDB_VERSION=1.2.2` (installer), `--version` (winget), or an image tag. | Live `brew info`; `https://duckdb.org/install/?environment=cli`; `S/operations_manual/installing_duckdb/install_script.md` | Probed / Documented |
| F68 | `osx_amd64` is **partial** support: core extensions ship, community extensions do not as of 2.0.0, and 2.1 drops it. Linux binaries need glibc ≥ 2.28. | `S/operations_manual/installing_duckdb/requirements.md` | Documented |
| F69 | CLI default log storage is `shell_log_storage`; `SELECT * FROM duckdb_logs` fails with `Log storage 'shell_log_storage' does not support this query`. `CALL enable_logging(storage='memory')` makes `duckdb_logs` queryable. `CALL enable_logging()` prints a WARNING and `INFO:QueryLog ...` lines to **stdout**. | `S/operations_manual/logging/overview.md`; probes | Probed |
| F70 | `duckdb_logs` columns: `context_id, scope, connection_id, transaction_id, query_id, thread_id, timestamp, type, log_level, message`. Default level INFO includes QueryLog. | Probe DESCRIBE; `S/operations_manual/logging/overview.md` | Probed |
| F71 | SIGINT during an agent-mode query exits **1** with a header-only stdout (aggregate column header plus separator, no rows) and **no JSON error** on stderr, only the banner and estimate. Exit code is the only signal that it was cancelled. | Probe kill -INT on a 5B-row scan | Probed |

### Format choice

| Consumer | Use | Why |
|---|---|---|
| Model reading a table | `-agent` | Markdown, 1,000-row/10 KB/500-char caps, footer hash, JSON errors on stderr |
| Parser needing typed values | `-json`, one statement per invocation | Typed values; watch NaN/Infinity, HUGEINT/DECIMAL strings, duplicate keys |
| Streaming parser | `-jsonlines` | One object per line, no array wrapper; still one stream per statement |
| Simple tabular/CSV pipeline | `-csv` | Header + rows, no caps, agent off; NULL is literal `NULL` |
| Human at a terminal | default `duckbox`, or `-markdown` | Aligned columns; no machine footer or caps |
| JSON results + machine errors | `-agent -json` | JSON results plus agent framing, but **no row/byte/cell caps** |

### Dot commands

| Command | Effect | Agent note |
|---|---|---|
| `.maxrows N` | Whole-result row threshold (default 40 duckbox, 1000 agent); `-1` = all | Over the threshold, display caps at 20 head + 20 tail |
| `.maxbytes N` | Whole-result rendered-byte threshold (default 10000); `0` = all | Still needed after `.maxrows -1` |
| `.maxcellwidth N` | Per-cell character cap (default 500); `0` = all | Truncation marker is `…(+N chars)` |
| `.startup_text none\|version\|all` | Startup banner/version text | First line of `~/.duckdbrc`; `none` hides the agent banner |
| `.mode MODE` | Set output mode; no arg prints current mode | `insert` needs a table argument |
| `.open [--new\|--nofollow\|--readonly\|--sql] FILE` | Close current DB and reopen | `--readonly` requires an existing file |
| `.read FILE` | Execute SQL and dot commands from a file | Disabled in `-safe` |
| `.output FILE` | Redirect all subsequent output; no arg restores stdout | Disabled in `-safe` |
| `.once FILE` | Redirect only the next SQL result | Disabled in `-safe`; `-e`/`-x` open an editor/spreadsheet |
| `.import FILE TABLE` | Import CSV/JSON/Parquet, creating the table | Format inferred or `--csv/--json/--parquet` |
| `.schema [--no-indent\|--indent] [PATTERN]` | Show `CREATE` statements | Pretty-prints by default in 2.0 |
| `.tables [PATTERN]` | List tables with columns/types/rows | Agent mode emits plain lines, not Markdown |
| `.databases` | List attached DB names and paths | Agent mode emits one plain line |
| `.timer on\|off [DIGITS]` | Print real/user/sys time | **stdout**, after the result |
| `.changes on\|off` | Print `changes: N   total_changes: M` | **stdout**, not stderr |
| `.log FILE\|stdout\|stderr\|off` | CLI shell log | Disabled in `-safe`; behavior not observable in piped probes |
| `.web` | Open the last query profile in a browser | Disabled in `-safe` |
| `.history [N]` | Show command history | Populated for piped stdin; empty with `-c` |
| `.serve_command COMMAND` | Command used by `-serve` | Default `quack_serve` |
| `.connect_command COMMAND` | Command used by `-connect` | Default `CONNECT` |
| `.help [-all] [PATTERN]` | Help text; `.help agent` summarizes agent mode | `.help shortcuts` for keys |
| `.export` | **Does not exist** | Use `EXPORT DATABASE 'dir'` SQL |

## Existing skill audit

| Skill | Claim or omission | Verdict | Fix |
|---|---|---|---|
| `SKILL.md` L12 | "This pack targets DuckDB 2.0.0 LTS and newer patch releases on the 2.0 line. Codename on the GitHub release is Cyanoptera. The announcement calls the same release Cinnamon Teal." | Correct | Keep. Verified against the binary and the announcement page. |
| `SKILL.md` L22 | "Continue only when the first line contains `v2.0`." | Thin | Say "parse stdout, or run `duckdb -no-agent --version`; stderr may carry the agent banner". |
| `SKILL.md` L25 | "`curl -fsSL https://install.duckdb.org \| sh`" | Correct | Keep; add the `DUCKDB_VERSION=` pin one-liner. |
| `SKILL.md` L28 | "That installs `~/.duckdb/cli/latest/duckdb` and links `~/.local/bin/duckdb`." | Correct but conditional | Add "only if `~/.local/bin` exists and has no `duckdb`"; the installer prints a PATH hint. |
| `SKILL.md` L28 | "Homebrew lagged the 2.0.0 release and was still on 1.5.6 the day after it shipped." | Correct | Keep; `brew info` still says 1.5.6 on 2026-10-22. |
| `SKILL.md` L34 | "Each `duckdb` process starts empty unless you pass `-init` or a database file." | Thin / misleading | It starts with a fresh in-memory DB but still executes `~/.duckdbrc` unless `-no-init`. Say exactly that. |
| `SKILL.md` L36 | "Agent mode writes the banner, JSON errors, row estimates, and progress to stderr." | Correct | Keep; qualify that `.startup_text none` hides the banner and `.timer`/`.changes` still write stdout. |
| `SKILL.md` L41 | "`duckdb -agent -c "SELECT 42 AS answer;"`" | Correct | Keep. |
| `SKILL.md` L47 | "`duckdb -json -c "SELECT 42 AS answer;"`" | Correct | Keep; add "one statement per invocation" and the NaN/HUGEINT caveats in the reference. |
| `SKILL.md` L53 | "`duckdb -agent <<'SQL'`" | Correct | Keep. |
| `SKILL.md` L58 | "`-json` without `-agent` prints errors as text. `-agent` prints errors as one JSON object on stderr." | Correct but thin | Add: exit 1; shape varies; partial results can remain on stdout; `errors_as_json` does not cover parser errors. |
| `SKILL.md` L58 | "A footer that says rows were omitted, or that the query stopped early, is a sample." | Wrong / unverified | No "stopped early" footer appeared for timeout, mid-stream error, or SIGINT. Timeout/mid-stream give JSON errors + exit 1; SIGINT gives exit 1 with no JSON error. Keep only the omitted-rows rule. |
| `SKILL.md` L60 | "`max_execution_time` is milliseconds. `0` means no limit." | Correct | Keep; note per-connection with global fallback. |
| `SKILL.md` L66 | "If stderr prints an `estimate:` line for a scan of more than about a million rows, ask before an unbounded run." | Correct but imprecise | Threshold is **≥ 1,000,000**; returned-row estimates can be wrong by orders of magnitude. |
| `SKILL.md` L68 | "A `~/.duckdbrc` can turn agent mode off. If the table comes back as a box drawing, rerun with `-no-init`." | Wrong mechanism | An rc `.mode` changes the **format**, not agent framing (errors stay JSON). `-no-init` fixes the format; an explicit `-csv`/`-json` also wins over rc. |
| `SKILL.md` L72 | "A database file created by 2.0 with default settings uses storage version 69. DuckDB 1.x cannot open it. DuckDB 2.0 can still open files written by 1.x, and writing to those files does not upgrade them." | Correct | Keep; add `tags` shows `v2.0.0+` and the header shows 999, so don't infer 69 from `hexdump`. |
| `SKILL.md` L72 | "Follow `duckdb-migrate` before creating or checkpointing a file that older processes must keep reading." | Correct | Keep; `-storage-version` is the creation lever; existing files need `COPY FROM DATABASE`/export-import. |
| `SKILL.md` L30 | "Stop if the only binary is 1.x. The SQL in this pack uses 2.0 syntax." | Correct | Keep; 2.0 features used elsewhere (lambdas, `VARIANT`, storage 69) make the gate real. |
| `SKILL.md` L58 | "Add `LIMIT` or an aggregate and run again before you treat the table as complete." | Correct | Keep; this is the right reaction to the truncation footer. |
| `SKILL.md` L90 | "Missing extension: `INSTALL AND LOAD <name>;` then retry." | Thin / out of scope | Verify the combined `INSTALL AND LOAD` signature in the extensions slice; keep only the cross-link here. |
| `SKILL.md` L94-98 | References: announce post, `clients/cli/agent_mode.html`, migration, install. | Correct | Announce/install fetched live; agent_mode and migration exist in the snapshot. Keep. |
| `SKILL.md` route table | No CLI entries for `-readonly`, `-safe`, `.maxrows`, `-cmd`/`-f`, or dot commands. | Missing | Add a compact CLI reference link; keep SKILL.md to decisions. |
| `README.md` L2 | "Agent skills for DuckDB 2.0.0 LTS, released 2026-10-21." | Correct | Keep. |
| `README.md` L3 | "The GitHub release is named Cyanoptera. The announcement calls the same release Cinnamon Teal." | Correct | Keep. |
| `README.md` L13 | "`duckdb` \| CLI must be 2.0 or newer. `-agent` for answers, `-json` for rows you will parse." | Correct but thin | Add "or `-jsonlines`"; note `-agent` caps vanish with `-json`. |
| `README.md` L33-35 | "`curl -fsSL https://install.duckdb.org \| sh` / `duckdb --version`" | Correct | Keep; same banner caveat. |
| `README.md` L37 | "On 2026-10-22 the official installer shipped 2.0.0 and Homebrew was still on 1.5.6." | Correct | Verified live; keep. |
| `README.md` L80 | "Agent mode is on when the CLI sees an agent and stdout is not a terminal, unless you pass `-csv` or `-json`." | Thin | Say "any output-mode flag", "env var presence, even `AI_AGENT=0`", "`DUCKDB_AGENT_MODE=0` or `-no-agent` to force off", and "`AGENT` alone triggers". |
| `README.md` L80 | "The old skills always passed `-csv`, which turns that mode off." | Correct | Keep; `-csv` also removes the caps, which is the point for parsers. |

## Gaps worth adding

| Rank | Gap | Why an agent needs it | Home: SKILL.md or reference |
|---|---|---|---|
| 1 | Agent activation + precedence (`AGENT`/`AI_AGENT=0`, `DUCKDB_AGENT_MODE`, any mode flag, rc `.mode`) | Wrong assumption silently changes output format and error channel | SKILL.md one-liner + `references/cli.md` table |
| 2 | `-agent -json`/`-agent -csv` keep framing but drop the 1,000-row/10 KB/500-char caps | A model can pull a 2,000-row result into context believing agent mode protected it | SKILL.md warning |
| 3 | `.maxrows -1` needs `.maxbytes 0`; `.maxrows 100` still shows 20+20 | Agents ask for "all rows" and get 40 | `references/cli.md` |
| 4 | `-json` is not strict JSON for NaN/Infinity, HUGEINT/DECIMAL are strings, duplicate keys, multi-statement concatenation | Parser crashes or silent corruption | `references/cli.md`; SKILL.md "one statement" |
| 5 | `-c` cannot hold dot command + SQL; `-cmd` ordering; `-f` bails while stdin continues | Setup silently doesn't run, or later statements silently skip | `references/cli.md` |
| 6 | `-readonly` only defaults attachments to read-only; `-safe` is the hard boundary; `allowed_paths` ordering | Security decisions that look enforced but aren't | `references/cli.md`; SKILL.md one line |
| 7 | `-storage-version` only affects new files; `SET storage_compatibility_version` doesn't touch the primary DB; invalid value exits 0 | Agent thinks it downgraded a file when it didn't | `references/cli.md` |
| 8 | `duckdb_settings()` defaults: memory `%`, temp size has no `%`, threads, preserve order, progress bar | Resource tuning without OOM or surprise ordering | `references/cli.md` |
| 9 | Install matrix: Homebrew 1.5.6, winget, Docker, `osx_amd64`, `DUCKDB_VERSION` pin | Version check is the first failure point | `references/cli.md` install table |
| 10 | Logging default `shell_log_storage` cannot be queried and writes to stdout | `duckdb_logs` errors; log lines corrupt JSON/CSV | `references/cli.md` |
| 11 | `.tables`/`.databases` agent format is plain text, not Markdown; `.timer`/`.changes` go to stdout | Parsers expecting Markdown/JSON break | `references/cli.md` |
| 12 | `.export` does not exist; use `EXPORT DATABASE` | Dead command in generated scripts | `references/cli.md` one line |

### Split

| File | Owns |
|---|---|
| `skills/duckdb/SKILL.md` | Version gate; `-agent` vs `-json` decision; the `~/.duckdbrc`/`-no-init` escape; one line each for `-readonly`/`-safe`; the storage-version warning; route table. No flag catalog, no dot-command catalog. |
| `skills/duckdb/references/cli.md` | Full flag table and argument order; agent caps/footer/hash/error shapes; dot-command table; format and JSON-quirk matrix; read-only/safe/external-access matrix; settings defaults; install matrix; logging defaults. |

## Traps and contradictions

| Trap | What happens | Correct move | Evidence |
|---|---|---|---|
| `AI_AGENT=0` to disable | Still activates agent mode; any presence counts | `-no-agent` or `DUCKDB_AGENT_MODE=0` | Probe |
| `AGENT=1` from CI/tooling | Silently switches piped output to Markdown | Pin `DUCKDB_AGENT_MODE=0` or pass an output mode | Probe |
| Checking `duckdb --version 2>&1 \| head -1` | First line is the agent banner, not the version | Parse stdout or add `-no-agent` | Probe F1 |
| `~/.duckdbrc` `.mode duckbox` + `-agent` | Box-drawing table, but JSON errors/estimate/framing stay on | `-no-init` or explicit `-csv`/`-json`; `-no-agent` alone is not enough for format | Probe |
| `-agent -json` for safety | All 2,000 rows returned; no caps | Use Markdown agent for sampling, or add `LIMIT`/aggregate | Probe F41 |
| `.maxrows -1` for all rows | Byte cap still truncates | Add `.maxbytes 0` (and expect a large result) | Probe F34 |
| `.maxrows 100` on 5,000 rows | Shows only 20+20, not 50+50 | Use `LIMIT`/aggregate; `.maxrows` sets the whole-result threshold, and over it the display is capped at 20+20 | Probe F31 |
| Footer absent on 1–9 rows | Agent assumes no hash means no result | Hash only appears for 0 or ≥10 rows | Probe F32 |
| `-c ".mode csv\nSELECT ..."` | `Invalid usage of command '.mode'`, exit 1 | `-cmd ".mode csv" -c "SELECT ..."` or stdin/`-f` | Probe F6 |
| `-f script.sql` after an error | Stops at first error; later statements never run | Put `.bail off` first if continuing is intended | Probe F8 |
| Positional SQL + `-c` | Positional SQL runs last, not where it appears | Use `-c` only for deterministic order | Probe F9 |
| `-storage-version` on an existing 69 file | Ignored; file stays 69 | Create a new file, or `COPY FROM DATABASE` into a v1.x-version file | Probe F12/F64 |
| `-storage-version v9.9.9` | Prints error but exits 0 and creates no DB | Check the file exists, not just `$?` | Probe F12 |
| `-help` says storage default `v0.10.0` | Actual new-file default is v2.0.0/69 | Trust the manual/tags, not the help line | Probe `-help` vs `db.tags` |
| `hexdump` shows 999 | Agent concludes "storage version 999" | 999 is the header marker; `tags` says `v2.0.0+`; table says 69 | `S/internals/storage.md`; probe |
| `SET storage_compatibility_version` on the primary DB | No effect; file already created | Use `-storage-version` before the filename | Probe F64 |
| `-json` + multiple statements | Concatenated arrays, invalid as one document | One statement per invocation, or `-jsonlines` | Probe F43 |
| `-json` NaN/Infinity | Bare `NaN`/`Infinity`; strict parsers reject | Use `-csv`, or cast/guard non-finite values | Probe F42 |
| `-json` duplicate columns | Duplicate keys; parser keeps last | Alias columns uniquely | Probe F44 |
| `-csv` NULL | Literal `NULL` looks like data | `-nullvalue ''` plus a separate null flag, or JSON | Probe F45 |
| `errors_as_json=true` for syntax errors | Parser errors stay text | Use `-agent`/`-agent -json` for uniform JSON errors | Probe F40 |
| `-safe` + `allowed_paths` in `-init` | Config already locked; init fails and exits | Prefer `.safe_mode` after setting paths, or accept a hard lockdown | Probe F57 |
| `allowed_paths` after disabling external access | `Cannot change allowed_paths ...` | Set paths first, then disable | Probe F56 |
| Re-enabling external access | `Cannot enable external access while database is running` | Decide before disabling; restart to change | Probe F58 |
| `-unredacted` expected to show keys | `secret_string` still says `secret=redacted` | Treat redaction as on; verify per provider before relying on it | Probe F22 |
| `SET allow_unsigned_extensions` | Fails at runtime | Pass `-unsigned` at startup | Probe F23 |
| `.export` | `Unknown Command Error` | `EXPORT DATABASE 'dir'` SQL | Probe F49 |
| `.tables` in agent mode | Plain text line, not a Markdown table | Parse `db.schema.table (...)` or use `SHOW TABLES` | Probe F47 |
| `.timer on` with `-json` | "Run Time" text after JSON on stdout | Leave timer off for parseable runs | Probe F48 |
| `CALL enable_logging()` | WARNING and INFO lines on stdout; `duckdb_logs` still unqueryable | `CALL enable_logging(storage='memory')` before querying logs | Probe F69 |
| `-readonly` as a write sandbox | `ATTACH ... (READ_WRITE)` still writes | Use `-safe`/`enable_external_access=false` for a hard boundary | Probe F10 |
| `allow_persistent_secrets=false` as a secret sandbox | Already-loaded persistent secrets remain in `duckdb_secrets()` | Set it at startup, not via `SET`; `-safe` blocks the directory | Probe F60 |
| Ctrl-C / SIGINT during a query | Exit 1, header-only stdout, no JSON error; looks like an empty successful result if only stdout is read | Always check the exit code; don't treat an empty table as a valid empty result | Probe F71 |

## What not to add

- The full dot-command catalog. It is lookup material; only the 10–15 commands that change an agent's output or safety belong in a reference, and none in `SKILL.md`.
- Interactive editor, history, pager, prompt, highlight, and keybinding details. They do not change a batch agent decision.
- `-ui`, `-serve`, and `-connect` protocol detail. The Quack/UI skills own those; keep one sentence and a cross-link.
- `-format`/`-format-file` as a validation step. They pass invalid SQL through with exit 0.
- A blanket "always pass `-agent`" rule. It is wrong for parsers and removes the caps when combined with `-json`/`-csv`.
- `-tabs` or `.export`. Neither exists in 2.0.0; documenting them creates dead commands.
- `.timer`/`.changes` as recommended defaults. They write to stdout and corrupt JSON/CSV.

## Probe log

```text
$ duckdb --version >out 2>err
out: v2.0.0 (Cyanoptera) d54cbbe3df
err: duckdb agent mode on: AI_AGENT is set and stdout is not a terminal; ...

$ duckdb -agent -c "SELECT 42 AS answer;"
stdout: | answer:INTEGER | / |---| / | 42 |
stderr: duckdb agent mode on (-agent); .help agent explains the output

$ duckdb -agent -c "SELECT i FROM range(2000) t(i);"
stdout (44 lines): first 20 values, "| … 1960 rows omitted … |", last 20
footer: first 20 and last 20 of 2000 rows (.maxrows -1 for all), hash a989b1ca140b5ed3

$ duckdb -agent -c "SELECT i FROM range(1000) t(i);"
footer: 1000 rows, hash a8879abae4959f72

$ duckdb -agent -c "SELECT repeat('x',600) AS s;"
cell: 500 x's + "…(+100 chars)"

$ duckdb -agent -c "SELECT i, repeat('x',200) AS s FROM range(100) t(i);"
footer: first 20 and last 20 of 100 rows (.maxbytes 0 for all), hash ...

$ printf '.maxrows -1\nSELECT i FROM range(2000) t(i);\n' | duckdb -agent
footer: first 20 and last 20 of 2000 rows (.maxbytes 0 for all), hash a989b1ca140b5ed3
$ printf '.maxrows -1\n.maxbytes 0\nSELECT i FROM range(2000) t(i);\n' | duckdb -agent
footer: 2000 rows, hash a989b1ca140b5ed3

$ printf '.maxrows 100\nSELECT i FROM range(5000) t(i);\n' | duckdb -agent
footer: first 20 and last 20 of 5000 rows (.maxrows -1 for all), hash ...

$ duckdb -agent -c "SELECT count(*) FROM range(2000000);"
stderr: estimate: ~2000000 rows read (range ~2000000), ~1 rows returned

$ duckdb -agent -c "SELECT sum(sin(i::DOUBLE)*cos(i::DOUBLE)) FROM range(1200000000) t(i);"
stderr: estimate: ~1200000000 rows read (range ~1200000000), ~1 rows returned
progress: 12% (elapsed 2.0s, remaining ~13.6s)
progress: 45% (elapsed 7.0s, remaining ~8.5s)
progress: 77% (elapsed 12.0s, remaining ~3.6s)
progress: done (elapsed 15.7s)

$ duckdb -agent -c "SELEC 1;"
stderr: {"exception_type":"Parser","exception_message":"syntax error at or near \"1\"","location":"[6,1]","position":"6","error_subtype":"SYNTAX_ERROR"}
exit 1

$ duckdb -agent -c "SELECT * FROM no_such_table;"
stderr: {"exception_type":"Catalog","exception_message":"Table with name no_such_table does not exist! ...","error_subtype":"MISSING_ENTRY","type":"Table","position":"14","location":"[14,13]","name":"no_such_table"}

$ duckdb -agent -c "SET max_execution_time=200; SELECT count(*) FROM range(1000000000) t(i) WHERE i%7=0;"
stderr: {"exception_type":"INTERRUPT","exception_message":"Query exceeded maximum execution time"}
exit 1

$ kill -INT <pid of: duckdb -agent -c "SELECT sum(sin(i::DOUBLE)) FROM range(5000000000) t(i);">
exit 1; stdout: header + separator only; stderr: banner + estimate, no JSON error

$ duckdb -agent -json -c "SELECT i FROM range(2000) t(i);" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"
2000

$ duckdb -json -c "SELECT 1 AS a; SELECT 2 AS b;"
[{"a":1}]
[{"b":2}]

$ duckdb -json -c "SELECT 'NaN'::DOUBLE AS n, 1::HUGEINT AS h, 1.5::DECIMAL(10,2) AS d;"
[{"n":NaN,"h":"1","d":"1.50"}]

$ duckdb -json -c "SELECT 1 AS a, 2 AS a;"
[{"a":1,"a":2}]

$ HOME=home8 duckdb -agent -c "SELECT 42 AS x;"   # home8/.duckdbrc = .mode duckbox
duckbox table, not Markdown; -no-init restores Markdown

$ duckdb -agent -c $'.maxrows 5\nSELECT 1;'
Invalid Command Error: Invalid usage of command '.maxrows' ...  exit 1

$ duckdb -agent -cmd ".maxrows 5" -c "SELECT i FROM range(100) t(i);"
footer: first 3 and last 2 of 100 rows (.maxrows -1 for all), hash ...

$ duckdb -no-agent -f errs.sql      # first line: SELECT CAST('x' AS INT); second: SELECT 42
error only; second statement not run
$ duckdb -no-agent -cmd ".bail off" -f errs.sql
error + 42

$ duckdb -no-agent -safe -c "SELECT * FROM read_csv('data.csv');"
Permission Error: Cannot access file "data.csv" ... exit 1

$ duckdb -no-agent -safe -c ".read one.sql"
.read cannot be used in -safe mode  exit 1

$ duckdb -no-agent -c "SET allowed_paths=['.../data.csv']; SET enable_external_access=false; SELECT * FROM read_csv('.../data.csv');"
reads the file
$ duckdb -no-agent -c "SET enable_external_access=false; SET allowed_paths=['.../data.csv'];"
Invalid Input Error: Cannot change allowed_paths when enable_external_access is disabled

$ duckdb -no-agent -c "SET lock_configuration=true; SET threads=2;"
Invalid Input Error: Cannot change configuration option ""threads"" - the configuration has been locked

$ duckdb -no-agent -readonly rw.duckdb -c "ATTACH 'other.duckdb'; INSERT INTO other.o VALUES (2);"
Invalid Input Error: ... attached in read-only mode!
$ duckdb -no-agent -readonly rw.duckdb -c "ATTACH 'other.duckdb' (READ_WRITE); INSERT INTO other.o VALUES (3);"
succeeds

$ duckdb -no-agent -storage-version v1.5.0 sv15.db -c "CREATE TABLE t AS SELECT 1; SELECT tags FROM duckdb_databases();"
{storage_version=v1.5.0+}
$ duckdb -no-agent -storage-version v9.9.9 bad.db -c "SELECT 1;"
duckdb: Error: unknown argument (v9.9.9) ... exit 0; no bad.db

$ hexdump -n 20 -C def.db
00000000  ... 44 55 43 4b e7 03 00 00 00 00 00 00   |DUCK............|
# e7 03 = 999; tags for the same file: {storage_version=v2.0.0+}

$ ls walf.db*   # after kill -9 during a write
walf.db  walf.db.wal
$ duckdb walf.db -c "SELECT count(*) FROM base;"   # reopen replays
1100
$ ls walf.db*   # after clean exit
walf.db

$ brew info duckdb | head -1
duckdb: stable 1.5.6 (bottled)
$ ls -l ~/.local/bin/duckdb
... -> /Users/.../.duckdb/cli/latest/duckdb

$ duckdb -no-agent -c "CALL enable_logging(storage='memory'); SELECT 42; SELECT type,message FROM duckdb_logs WHERE type='QueryLog';"
QueryLog  SELECT 42;
$ duckdb -no-agent -c "SELECT count(*) FROM duckdb_logs;"   # default storage
Invalid Configuration Error: Log storage 'shell_log_storage' does not support this query...
```

## Open questions

- What does `-unredacted` actually unredact? It sets `allow_unredacted_secrets=true`, but `duckdb_secrets().secret_string` stayed `secret=redacted` for a provider=config S3 secret. Source inspection or a provider that echoes credentials in an error would settle it.
- Is the exit-0 on invalid `-storage-version` intentional? Source or a release note would settle it; until then, check for the file.
- Does `.log FILE` do anything observable in a normal terminal session? Piped and pty probes were inconclusive (the pty run hung and was killed). A controlled pty test with `.log` plus a later `.exit` would settle it.
- Is the `.help`/`agent_mode.md` "10,000 bytes" the rendered-row budget or the raw cell budget? The 100×90/100×92 boundary points to rendered rows, but source would settle the exact accounting.
- Does any code path emit a "query stopped early" footer? Timeout and mid-stream errors produced only JSON errors; source grep would settle whether the skill's phrase has any basis.
- `-ui` installs the extension and starts the server in `scripts/probe.py`; the browser interaction is not probed.
