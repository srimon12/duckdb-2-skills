# DuckDB 2.0.0: Quack, CONNECT, and CLI agent mode

Factual briefing from official DuckDB pages only. Syntax below is copied from those pages. Nothing here was checked by running `duckdb`.

Release context: DuckDB 2.0.0 LTS “Cinnamon Teal” was released 2026-10-21. The `quack` extension page says 2.0.0 shipped a polished Quack protocol that is faster and more stable, and says to expect further improvements in upcoming patch releases.

## Sources actually read

Requested URLs all returned content (none 404’d):

- https://duckdb.org/2026/10/21/announcing-duckdb-200.html
- https://duckdb.org/docs/2.0/core_extensions/quack.html
- https://duckdb.org/docs/2.0/quack/overview.html
- https://duckdb.org/docs/2.0/sql/statements/connect.html
- https://duckdb.org/docs/2.0/quack/setup/reverse_proxy.html
- https://duckdb.org/docs/2.0/clients/cli/arguments.html
- https://duckdb.org/docs/2.0/clients/cli/agent_mode.html
- https://duckdb.org/2026/10/09/agent-mode.html
- https://duckdb.org/2026/08/17/duckdb-20-highlights.html (preview; deltas only)

Extra official pages those docs link to, used only for parameter tables and dot-command spellings the primary pages name but do not fully list:

- https://duckdb.org/docs/2.0/quack/security.html
- https://duckdb.org/docs/2.0/quack/reference.html
- https://duckdb.org/docs/2.0/clients/cli/dot_commands.html

## 1. Starting a Quack server

The `quack` extension turns a DuckDB instance into an HTTP server other DuckDB instances can connect to. It is autoinstalled and autoloaded on first use. Explicit forms:

```sql
INSTALL quack;
LOAD quack;
```

Protocol facts from the overview:

- Messages travel over plain HTTP, or HTTPS via a reverse proxy. There is no custom wire transport.
- The client initiates every interaction. The server does not push.
- Bodies use `application/duckdb` serialization (the same path as the WAL), so nested types, decimals, and intervals stay lossless.
- After the handshake, a query is one request–response pair. Large results stream with follow-up `FETCH` requests.
- Default port is `9494`. URIs use the `quack:` scheme.

### SQL: `CALL quack_serve`

Listen on localhost (default port 9494). The URI argument is optional; omitting it also listens on `quack:localhost`.

```sql
CALL quack_serve('quack:localhost');
-- equivalent:
CALL quack_serve();
```

The release announcement’s form, which only sets the token and therefore uses the default listen URI:

```sql
CALL quack_serve(
    token = 'my_token'
);
```

Overview form that sets both:

```sql
CALL quack_serve('quack:localhost', token = 'my_token');
```

`quack_serve` returns the listen URI, the HTTP URL, and, when the default authentication function is in use, the `auth_token` column clients must present.

Stop:

```sql
CALL quack_stop('quack:localhost');
```

URI examples from the overview (port defaults to 9494):

| URI | Host | Port |
| --- | --- | --- |
| `quack:localhost` | `localhost` | `9494` |
| `quack://localhost` | `localhost` | `9494` |
| `quack:myhost:9000` | `myhost` | `9000` |
| `quack:127.0.0.1` | `127.0.0.1` | `9494` |
| `quack:[::1]:1234` | `::1` | `1234` |

`quack_serve` parameters (reference page):

| Parameter | Type | Default | What the docs say |
| --- | --- | --- | --- |
| `listen_uri` | VARCHAR | `quack:localhost` | Positional. URI to listen on. |
| `allow_other_hostname` | BOOLEAN | `false` | Allow binding to a non-local hostname, e.g. `0.0.0.0`. |
| `token` | VARCHAR | (generated) | Token clients must present. Minimum 4 characters. If omitted, the token of the default `quack` secret is used if one exists; otherwise a random token is generated. |
| `secret` | VARCHAR | (unset) | Name of an existing `quack` secret whose token the server uses. |
| `create_secret_if_not_exists` | BOOLEAN | `false` | If no token is given and no default `quack` secret exists, store the generated token in a persistent default `quack` secret so later servers reuse it. |
| `disable_ssl` | BOOLEAN | `true` for local, else `false` | Serve plain HTTP. Local URIs default to plain HTTP; other URIs to HTTPS. |
| `ssl_cert_file` | VARCHAR | (generated) | Certificate when serving SSL. If omitted, a self-signed certificate is generated. |
| `ssl_key_file` | VARCHAR | (generated) | Private key when serving SSL. |

### Default bind host and token

- Default bind is localhost only. The server refuses any other hostname unless `allow_other_hostname` is set.
- Security page: a random authentication token is generated at startup. Clients must supply it on every connection, via a `quack` secret scoped to the server URI or the explicit `TOKEN` option on `ATTACH` / `quack_query`. The default auth callback `quack_check_token` compares the client token to the server token. Default authorization (`quack_nop_authorization`) allows every query.
- Local URIs do not use TLS. The security page says TLS for localhost only adds dependencies for no real benefit. Non-local URIs default to HTTPS with a self-signed certificate unless `ssl_cert_file` and `ssl_key_file` are passed.
- A Quack server exposes the full SQL surface of the session that started it, including writes to every table that session can see.

### What is unsafe vs the recommended proxy

`allow_other_hostname` exposes the server directly. The release announcement says it is only meant for testing. The security page’s best practice: for any deployment beyond local-only, do not expose Quack directly to the internet; put a proven HTTP reverse proxy in front and let the proxy terminate TLS.

Documented testing-only bind (overview):

```sql
CALL quack_serve('quack:0.0.0.0:9494', allow_other_hostname = true);
```

Recommended pattern (announcement, overview, security, reverse-proxy guide): keep the server on localhost and front it with a TLS-terminating reverse proxy. By default the server binds to localhost and speaks plain HTTP.

The client assumes HTTPS for non-local URIs, so a correctly fronted server needs no extra client SSL flags. Local URIs (`localhost`, `127.0.0.1`, `::1`) default to plain HTTP, so a local TLS test must force SSL on with `DISABLE_SSL false`. The default Quack port stays `9494` even when the client uses HTTPS, so a proxy on 443 must be written into the URI.

Local Caddy test from the reverse-proxy page. Caddyfile:

```
localhost:8443 {
    reverse_proxy 127.0.0.1:9494 {
        flush_interval -1
    }

    request_body {
        max_size 256MB
    }
}
```

Server and client:

```sql
CALL quack_serve('quack:localhost');
```

```sql
ATTACH 'quack:localhost:8443' AS quack (
    TOKEN 'authentication_token-from-quack_serve',
    DISABLE_SSL false
);

FROM quack.query('SELECT 42');
```

Production clients (nginx or Caddy + Let’s Encrypt), still with the server on localhost:

```sql
CALL quack_serve('quack:localhost');
```

```sql
ATTACH 'quack:quack.example.com:443' AS quack (
    TOKEN 'authentication_token-from-quack_serve'
);
```

Proxy details the guide calls out, because they are easy to get wrong: raise the body limit (nginx `client_max_body_size 256M`; Caddy `request_body { max_size 256MB }`) because `PREPARE` carries SQL and `APPEND` carries inserted chunks; disable response buffering (`proxy_buffering off` / `flush_interval -1`) so streamed `FETCH` responses are not buffered; keep upstream connections alive (`proxy_http_version 1.1` and `Connection ""`) because Quack keeps server-side `quack_connection_id` state on persistent connections; raise nginx `proxy_read_timeout` and `proxy_send_timeout` (the guide uses `600s`) because long queries can sit between `FETCH`es. The guide’s nginx `proxy_pass` target is `http://127.0.0.1:9494`.

### CLI: `-serve` and `-connect`

Introduced in DuckDB 2.0. Argument spellings from the arguments page:

| Argument | Description in the docs |
| --- | --- |
| `-serve [quack[:SECRET]]` | Serve the opened database with Quack. A named secret can be provided after the type. |
| `-connect [TYPE[:SECRET]]` | Connect to a remote database. The default type is `quack`. A named secret can be provided after the type. |

No database path and no extra configuration: in-memory database on `localhost:9494`.

```
duckdb -serve
```

Persistent file (path before the flag):

```
duckdb analytics.duckdb -serve
```

Client with no arguments connects to the Quack server on `localhost:9494` using the default `quack` secret. If that secret does not exist yet, `-serve` creates it as a persistent secret, so `duckdb -serve` and `duckdb -connect` on the same machine need no further setup:

```
duckdb -connect
```

Named secret (only the `quack` type can be served):

```
duckdb analytics.duckdb -serve quack:analytics
duckdb -connect quack:analytics
```

`-connect` cannot be combined with a local database path; the CLI is then a client of the remote database.

By default `-serve` calls `quack_serve` and `-connect` runs a `CONNECT` statement. Those SQL strings can be replaced with the dot commands `.serve_command` and `.connect_command` (for example in `~/.duckdbrc`). The arguments page does not print the default SQL text, only that those are the calls.

The SQL parameter `create_secret_if_not_exists` defaults to `false`. The persistent-secret behavior above is documented for the CLI `-serve` flag, not for a bare `CALL quack_serve()`.

## 2. Client `ATTACH 'quack:...'` and `CONNECT`

Three client styles (overview). `CONNECT` after `ATTACH` is the recommended one.

### Attach, then route the session

```sql
ATTACH 'quack:server.example.com' AS qk (TOKEN 'my_token');

CONNECT qk;
SELECT count(*) FROM events; -- executes on the server, results stream back
DISCONNECT;
```

The announcement’s same-machine example uses `ATTACH 'quack:localhost' AS qk (TOKEN 'my_token');` then `CONNECT qk;`.

Statement syntax (connect page):

```sql
CONNECT { attached_database | 'connection_string' };
DISCONNECT;
```

`CONNECT` takes either an alias already created with `ATTACH`, or a connection string. While it is active, queries that do not explicitly qualify a different database execute on the remote. Results stream back. `DISCONNECT` returns the session to the local database. `DISCONNECT` with no active connection returns an error.

Direct connection string. For databases other than DuckDB, the string must start with the database type, then a connection string for that database. The PostgreSQL example is a libpq connection string:

```sql
CONNECT 'postgres:dbname=mydb host=localhost';
SELECT count(*) FROM orders; -- runs on the PostgreSQL server
DISCONNECT;
```

### Supported databases and remote pushdown

`CONNECT` works with databases that support remote execution, including:

- DuckDB servers over Quack.
- PostgreSQL and MySQL. For these, the remote pushdown optimizer ships SQL directly to the remote server instead of pulling tables over the wire.

The connect page says “including”, not that the list is closed. It does say in-process local databases, such as the default in-memory database or a DuckDB file, do not support `CONNECT`.

No other database types are named on the connect page, the announcement, or the overview.

### Attach as a catalog (no `CONNECT`)

Tables are qualified with the catalog name. DDL, inserts, filters, and transactions are forwarded. `DETACH` drops the attachment.

```sql
ATTACH 'quack:localhost' AS remote_db (
    TOKEN 'MY_QUACK_TOKEN_01234567890ABCDEF'
);

CREATE TABLE remote_db.t AS FROM range(10) r(i);
INSERT INTO remote_db.t VALUES (42);
FROM remote_db.t;
FROM remote_db.t WHERE i = 42;
BEGIN; ...; COMMIT;
DETACH remote_db;
```

Ad-hoc SQL on that attachment:

```sql
FROM remote_db.query('SELECT 42');
```

Plain HTTP on a non-local host (HTTPS is the default there):

```sql
ATTACH 'quack:remote.com' AS remote_db (
    TOKEN 'MY_QUACK_TOKEN_01234567890ABCDEF',
    DISABLE_SSL true
);
```

`ATTACH` binds the remote’s table definitions on the client. One table definition that cannot be bound fails the whole attachment (the overview points at the Quack troubleshooting page for lazy Iceberg catalogs). That failure mode is named, not specified, on the overview page.

### Stateless `quack_query`

```sql
FROM quack_query(
    'quack:localhost',
    'SELECT 42',
    token = 'MY_QUACK_TOKEN_01234567890ABCDEF');
```

```sql
FROM quack_query(
    'quack:remote.com',
    'SELECT 42',
    token = 'MY_QUACK_TOKEN_01234567890ABCDEF',
    disable_ssl = true
);
```

Reference: `quack_query(uri, query, ...)` also accepts `ssl_fingerprint`, `client_id`, and `heartbeat_timeout`, with the same meaning as the `ATTACH` options. `token` overrides any matching `quack` secret.

### Authentication

Preferred: a secret scoped to the server URI. Passing `TOKEN` on `ATTACH` overrides a matching secret.

```sql
CREATE SECRET (
    TYPE quack,
    TOKEN 'MY_QUACK_TOKEN_01234567890ABCDEF',
    SCOPE 'quack:localhost'
);

ATTACH 'quack:localhost' AS remote_db (TYPE quack);
```

`ATTACH` options (reference):

| Option | Type | Default | What the docs say |
| --- | --- | --- | --- |
| `TOKEN` | VARCHAR | (unset) | Overrides any matching `quack` secret. |
| `DISABLE_SSL` | BOOLEAN | `true` for local, else `false` | Force the client transport. Local URIs default to plain HTTP. |
| `TYPE` | VARCHAR | inferred | Pin the secret type used for token resolution (e.g. `quack`). |
| `SSL_FINGERPRINT` | VARCHAR | (unset) | Expected certificate fingerprint. Used to connect to a self-signed server. |
| `CLIENT_ID` | VARCHAR | `quack_default_client_id` | Sent to the server. Minimum 4 characters. |
| `HEARTBEAT_TIMEOUT` | UBIGINT | `quack_default_heartbeat_timeout` | Heartbeat lease timeout in seconds. |

Connection caching is off by default (a new TCP and, with SSL, TLS handshake per request). Turn it on with:

```sql
SET httpfs_connection_caching = true;
```

## 3. CLI flags and agent mode

Agent mode was introduced in DuckDB 2.0. It renders for an AI coding agent instead of a person at a terminal: compact Markdown tables, explicit result limits, machine-readable errors, and progress on `stderr`.

### Flags and the environment variable

| Control | Effect |
| --- | --- |
| `-agent` | Force agent mode on. |
| `-no-agent` | Force agent mode off. |
| `DUCKDB_AGENT_MODE` | `1` forces on, `0` forces off. For when the command line cannot be changed. |
| (none) | Auto-detect, rules below. |

Command-line flags take precedence over `DUCKDB_AGENT_MODE`. Examples from the docs:

```
duckdb -agent -c "SELECT 42 AS answer;"
duckdb -no-agent -c "SELECT 42 AS answer;"
DUCKDB_AGENT_MODE=1 duckdb
```

Hide the startup line by putting this first in `~/.duckdbrc`:

```
.startup_text none
```

The dot-command spelling is `.startup_text none/version/all`.

### How an agent is auto-detected

Agent mode turns on only when all three are true (agent-mode docs and the 2026-10-09 post):

1. A known agent environment variable is set.
2. Standard output is not a terminal (for example it is a pipe).
3. No output-mode flag was passed. The docs’ examples are `-csv` and `-json`. The blog also names `-markdown`.

Environment variables listed on the 2026-10-09 post (the docs page only gives `AI_AGENT` as the example):

| Variable | Set by |
| --- | --- |
| `AI_AGENT`, `AGENT` | Claude Code, Goose, Amp |
| `CLAUDECODE` | Claude Code |
| `CODEX_CI`, `CODEX_SANDBOX`, `CODEX_THREAD_ID` | Codex |
| `CURSOR_AGENT` | Cursor |
| `GEMINI_CLI` | Gemini CLI |
| `COPILOT_AGENT`, `COPILOT_CLI`, `COPILOT_AGENT_SESSION_ID` | GitHub Copilot |

When detection turns the mode on, one line goes to `stderr` before any query:

```
duckdb agent mode on: CLAUDECODE is set and stdout is not a terminal; -no-agent turns it off, .help agent explains the output
```

The variable name in that line is the one that was detected. `.show` reports the agent, for example `agent: claude-code`.

If a run fails while writing to a pipe, no agent was identified, and neither flag was given, one hint goes to `stderr`:

```
hint: -agent renders errors as JSON and results compactly for AI coding agents (duckdb -help lists all options)
```

Explicit settings still win over agent-mode defaults: `.mode`, `.maxrows`, `EXPLAIN (FORMAT ...)`, and anything in `.duckdbrc` (blog).

### Output format

Human default is a padded box with a type row under the names. Agent mode prints unpadded Markdown. The column type is in the header cell:

```
| name:VARCHAR | n:BIGINT | total:HUGEINT | avg_amount:DECIMAL(10,2) |
|---|---|---|---|
| customer_0 | 3 | 777 | 259.00 |
| customer_1 | 3 | 888 | 296.00 |
```

The blog says this is still valid Markdown and is typically 25 to 65% smaller than the box output.

### Truncation, hash, early stop

Docs page: a result of up to 1,000 rows and 10,000 bytes is rendered whole. Anything larger is the first and last rows plus the total row count. Cells are truncated at 500 characters.

Blog, more specific about the sample and the footer text. A larger result is the first and last 20 rows around an explicit marker, then a footer:

```
| 19 | customer_19 | 13.3 |
| … 4960 rows omitted … |
| 4980 | customer_30 | 86.0 |
...
first 20 and last 20 of 5000 rows (.maxbytes 0 for all), hash 7389c2f5ff3cefb6
```

Long cells are cut at 500 characters with a marker such as `…(+4500 chars)`.

The footer includes an order-independent hash of the entire result, including rows past the cap. The hash distinguishes `NULL` from the string `'NULL'`. The blog says the footer is printed for empty results, for results of 10 rows or more, and whenever output was capped. It is omitted when the query was stopped early, because the hash would not cover the whole result. The docs page says the footer has the row count and, when the whole result was read, the hash.

Early stop (blog): because the Markdown table does not need column widths, rows can stream. Once the cap is reached, remaining rows are only counted and hashed. After 100,000 more rows the query is stopped and the count is a lower bound. `FROM range(1_000_000_000);` is described as returning in 30 milliseconds with:

```
first 20 of at least 102400 rows (query stopped early; .maxrows -1 for all)
```

Limits, from the agent-mode docs:

| Dot command | Description |
| --- | --- |
| `.maxrows count` | Maximum number of rows to render whole (`-1` for all) |
| `.maxbytes count` | Maximum number of bytes of rows to render whole (`0` for all) |
| `.maxcellwidth count` | Maximum number of characters per cell (`0` for all) |

The dot-commands page adds: `.maxbytes` and `.maxcellwidth` apply only to agent mode (the longer help text says “markdown mode in `-agent` mode”). `.maxrows` applies to duckbox and to agent mode, and that page’s help text says its default is 40 with `-1` meaning all. See Uncertainties: that default does not match the 1,000-row agent-mode render default.

The blog says `.maxrows N` and `.maxbytes N` treat `-1` or `0` as no limit. The docs table is narrower: `-1` for `.maxrows`, `0` for `.maxbytes` and `.maxcellwidth`.

### JSON errors

Errors go to `stderr` as JSON, using the existing `errors_as_json` setting. Shell errors (unknown dot command, and similar) use the same structure. Example from the blog:

```json
{"exception_type":"Binder","exception_message":"Referenced column \"foo\" not found in FROM clause!\nCandidate bindings: \"bar\"","error_subtype":"COLUMN_NOT_FOUND","location":"[7,3]","position":"7","name":"foo"}
```

The shell drops the `candidates` field because the message already lists candidates. The blog says that without that drop, one “no matching function” error weighs 2.7 kB.

### Compact plans, cost estimate, progress

`EXPLAIN` defaults to a `compact` format, one operator per line, indented by depth. Estimates, actual row counts, and timings go in parentheses, then the operator’s properties. `EXPLAIN ANALYZE` starts with a summary such as `QUERY (time=0.0012s, read=1.2 MB)`. `EXPLAIN (FORMAT compact)` also works outside agent mode.

When the planner expects a statement to read a million rows or more, the estimate is printed on `stderr` before execution. Smaller queries print nothing. Example from the blog:

```
estimate: ~7501215 rows read (lineitem ~6001215, orders ~1500000), ~4 rows returned
```

The docs page states the same threshold as “more than 1,000,000 rows” and says an estimate line and progress go to `stderr`.

While a long query runs, the terminal progress bar is replaced by a plain `stderr` line every 5 seconds:

```
progress: 42% (elapsed 12.0s, remaining ~16.5s)
progress: done (elapsed 28.7s)
```

### `.tables` and other agent-facing commands

In agent mode, `.tables` is one line per table, with an approximate row count and the columns:

```
memory.main.t1 (table, ~15 rows): a INTEGER PK, b VARCHAR
```

`.help agent` prints the output rules. Both the docs and the blog point agents at:

- `SET max_execution_time = milliseconds` (the blog writes `SET max_execution_time = ms`) to bound runtime
- `DESCRIBE query` for result columns without running the query
- `SUMMARIZE` for a quick profile of a table or query
- `.tables` for the schema
- `duckdb_functions()` for function descriptions and examples

The announcement’s summary, which matches the pages above: the 2.0 CLI detects an agent and prints compact Markdown instead of padded boxes, says when a result was truncated, stops runaway queries early, reports errors as JSON, and reports expected cost before long queries. On TPC-H it says agent mode cut the DuckDB output the model read by 59%. The 2026-10-09 post gives the underlying counts: 22 TPC-H questions, scale factor 100, plain English, three runs with agent mode and three with `-no-agent`, all 132 answers correct, DuckDB output from 123.6k tokens to 50.8k tokens. That post also says the savings were about 0.5% of total input because the system prompt dominates, and that agent-mode runs took slightly more turns (237 vs 224).

## 4. What a skill must do differently when it shells out to `duckdb` in 2.0

This is behavior of the 2.0 CLI, not a skill file.

- If the process already has one of the agent variables above, and the skill captures stdout through a pipe, agent mode turns on by itself. Do not pass `-agent` just to get Markdown. Do not pass `-markdown`, `-csv`, or `-json` “so the output is parseable.”
- Passing an output-mode flag is what blocks automatic agent mode. The docs name `-csv` and `-json`. The blog names `-csv`, `-json`, and `-markdown`, and says a format flag is a deliberate choice that switches agent mode off. Agent mode already prints compact Markdown, so `-markdown` is not required and, on the blog’s later wording, turns the mode off.
- Do not keep a box-table parser. There is no `┌─┐` frame and no separate type row. Types are `name:VARCHAR` inside the header cells. Columns are not space-padded.
- Treat truncation as incomplete data. Look for the marker row `… N rows omitted …`, the footer `first 20 and last 20 of N rows`, and `query stopped early`. A footer that only shows the first and last 20 rows is not the full result. The early-stop footer is a lower bound (`at least 102400 rows`), and that case has no hash.
- Read `stderr` as well as stdout. The startup line, the failure hint, JSON errors, the `estimate:` line, and `progress:` lines are all on `stderr`. Errors are JSON objects, not a free-text `Error:` line. Do not assume a missing `candidates` field means there were no suggestions; they are in `exception_message`.
- A cost line appears only when the planner expects more than 1,000,000 rows read, and it appears before the query runs. The announcement says the agent can decide whether to wait. The pages do not document a CLI flag that accepts or rejects that estimate; they only print it.
- To ask for the full result, the documented knobs are `.maxrows` and `.maxbytes`. The agent-mode page says `-1` renders all rows and `0` renders all bytes. The early-stop footer itself says `.maxrows -1 for all`. The blog’s “`-1` or `0` means no limit” for both settings is broader than the docs table.
- `.mode`, `.maxrows`, and `~/.duckdbrc` override agent-mode defaults. A skill that inherits a user’s init file can lose Markdown, the row cap, or JSON errors. `-init` / the default `~/.duckdbrc` runs at startup before `-cmd`, `-c`, and `-s`. `-no-init` skips that file.
- `-no-agent` or `DUCKDB_AGENT_MODE=0` is how to force the old human renderer. The announcement says to tell the agent to turn the mode off with `-no-agent` when that is what you want. Flags beat the environment variable.
- Other output-mode flags that exist, and that would count as “an output mode was given” if the detection rule is general: `-ascii`, `-box`, `-column`, `-csv`, `-html`, `-json`, `-jsonlines`, `-line`, `-list`, `-markdown`, `-quote`, `-table`. Only `-csv`, `-json`, and `-markdown` are named in the agent-mode detection text. Do not assume the others were tested in the docs.

## 5. Preview deltas only (2026-08-17)

The preview page now says DuckDB 2.0.0 was released on 2026-10-21 and that some details changed; it points at the release announcement and the migration guide. Its own closing section said details might still shift before the fall release. Use it only to see what moved.

Still matches the 2.0 docs:

```sql
CALL quack_serve(
    token = 'my_token'
);
```

```sql
ATTACH 'quack:server.example.com'
    AS qk (TOKEN 'my_token');

CONNECT qk;
SELECT count(*) FROM events;
DISCONNECT;
```

Changed or not carried forward:

- Preview PostgreSQL example: `CONNECT 'postgres://localhost/mydb';`. The 2.0 connect page and the announcement do not show that URL form. The shipped example is `CONNECT 'postgres:dbname=mydb host=localhost';`, and the page says a non-DuckDB string must start with the type (`postgres:`) followed by that database’s connection string (libpq for PostgreSQL).
- The preview called `CONNECT` the successor to `remote.query($$...$$)`. The 2.0 Quack and `CONNECT` pages do not mention `remote.query`. They document `quack_query`, `catalog.query(...)`, and `CONNECT`. Do not emit `remote.query`.
- The preview did not document `allow_other_hostname`, the reverse proxy, `-serve`, `-connect`, tokens as secrets, or agent mode. Those are 2.0 docs, not preview syntax.
- Agent mode is absent from the August preview. It is described in the 2026-10-09 post and the 2.0.0 announcement.

## WIP and “may change”

- Quack extension page: “Expect further improvements in upcoming patch releases.” That is a stability/performance note, not a syntax warning.
- Agent-mode blog, conclusion: “The current behavior is a first attempt, and the conventions around agents are a work in progress.” It asks for issues if an agent is not detected or the output confuses it.
- The announcement’s sentence “This feature is still a work in progress and its syntax may change in future releases” is about extension repositories (`CREATE EXTENSION REPOSITORY`), not about Quack, `CONNECT`, or agent mode.
- The August preview’s “some details may still shift” is historical. The page itself says 2.0.0 has since shipped and some details did change (see section 5).

## Uncertainties

- `-agent` combined with a format flag. One sentence in the 2026-10-09 post says `duckdb -agent -csv` keeps agent behavior and only changes how rows are printed. A later section of the same post says a format flag switches agent mode off. The 2.0 agent-mode doc page says automatic activation requires that no output-mode flag was passed, and it does not say what `-agent -csv` does. Do not rely on JSON errors, early stop, or the cost line surviving `-csv` / `-json` / `-markdown`.
- `.maxrows` default. The agent-mode page and the blog say up to 1,000 rows and 10,000 bytes are rendered whole. The dot-commands page says `.maxrows` defaults to 40 (`-1` = all) for duckbox and agent mode. Which value is in force at startup in agent mode is not reconciled on these pages.
- No-limit sentinels. Docs: `.maxrows -1`, `.maxbytes 0`, `.maxcellwidth 0`. Blog: `-1` or `0` means no limit for `.maxrows` and `.maxbytes`. The early-stop example only mentions `.maxrows -1`.
- The env-var table is from the blog, not from `agent_mode.html`, which only says “such as `AI_AGENT`”. Agents not on that list are not detected; the blog says they can find the mode from the `stderr` hint the first time a piped run fails.
- The arguments page says `-serve` creates a persistent default `quack` secret if none exists. It does not show the SQL, so it is not documented whether that is `create_secret_if_not_exists => true` or another call. A bare `CALL quack_serve()` uses the reference default `create_secret_if_not_exists = false`.
- `CONNECT` “including” PostgreSQL and MySQL does not name SQLite, MotherDuck, or any other extension. No other type prefix besides `postgres:` is shown. MySQL’s connection-string spelling is not on the connect page.
- The preview URL form `postgres://...` is not repeated in the 2.0 connect docs. Whether the parser still accepts it is not stated.
- `remote.query($$...$$)` is preview wording only. These 2.0 pages do not say it was removed; they simply do not document it.
- Proxy body size 256MB, nginx timeouts of 600s, and Caddy `flush_interval -1` are the guide’s examples, not Quack server settings. The reference’s own batch and buffer settings (`quack_target_batch_bytes` 32 MiB, `quack_server_stream_buffer_bytes` 256 MiB, and others) were not part of the requested pages’ narrative and are not repeated here as skill requirements.
- No CLI session was run, so flag spelling was not cross-checked against `duckdb -help`.
