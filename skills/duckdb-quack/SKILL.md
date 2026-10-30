---
name: duckdb-quack
description: >
  Serve DuckDB 2.0 over HTTP with the Quack protocol, or route a session to
  Quack, PostgreSQL, or MySQL with CONNECT. Covers tokens, TLS reverse
  proxies, pushdown, and connection management. Use when the user says quack,
  duckdb -serve, duckdb -connect, CONNECT, or remote pushdown.
---

# Quack and CONNECT

Quack turns a DuckDB process into an HTTP server, defaulting to `quack:localhost` on port `9494` over plain HTTP. DuckDB automatically installs and loads the extension on first use. Result payloads use native DuckDB binary serialization, keeping decimals, intervals, and nested structures strongly typed.

The protocol is in beta and suited for prototyping, not production. Upgrades may introduce breaking changes across the wire protocol, function names, and default settings. An active server exposes the entire SQL surface, including writes, under the host OS identity of the user who started it.

Because a server process is long-running, start it in the background and do not block the active session. For CLI execution guidelines, consult `duckdb`.

## Serve

To serve a database over HTTP from the CLI, run:

```bash
duckdb analytics.duckdb -serve
```

When omitting the database path, `-serve` serves an in-memory database. When no default Quack secret exists, `-serve` generates a token and persists an unencrypted secret named `__default_quack` (scope `quack:`, mode 600) so `duckdb -connect` works immediately. Because possession of the token grants full read and write access to every session table, delete `__default_quack` when stopping the server, or load a named secret from a vault.

To manage the server lifecycle in SQL, invoke `quack_serve` or `quack_stop`:

```sql
CALL quack_serve('quack:localhost', token = 'my_token');
CALL quack_stop('quack:localhost');
```

Tokens require at least 4 characters. When a default `quack` secret exists, `quack_serve` reuses its token; otherwise it generates a token and returns it in `auth_token`. A bare `CALL quack_serve()` does not persist the token unless `create_secret_if_not_exists => true`.

To halt the server, run `quack_stop()` within the originating process. When invoked from a different process, `quack_stop` fails with `No server found listening on ...` while the server keeps running. Always pass the exact listen URI, including any custom port.

| Parameter | Default | Use |
| --- | --- | --- |
| `listen_uri` | `quack:localhost` | Host and port to bind. |
| `token` | reused or generated | Shared authentication token (at least 4 characters). |
| `secret` | unset | Name of an existing `quack` secret to load. |
| `create_secret_if_not_exists` | `false` | Persist generated token as default `quack` secret. |
| `allow_other_hostname` | `false` | Permit non-local bind such as `0.0.0.0` (testing only). |
| `disable_ssl` | `true` local, `false` remote | Plain HTTP versus HTTPS. |
| `ssl_cert_file`, `ssl_key_file` | generated | Certificate and private key paths. |

To inspect running servers or generate self-signed TLS certificates, run:

```sql
SELECT * FROM quack_server_list();
SELECT * FROM quack_active_connections();
CALL quack_generate_keys('/path/to/keys');
```

`quack_generate_keys` writes `server.pem` and `private_key.pem` to the target path and returns the SHA-256 fingerprint. Pass that fingerprint to the client's `SSL_FINGERPRINT` option.

## Connect

To route an interactive session to an attached Quack instance, run:

```sql
ATTACH 'quack:localhost' AS qk (TOKEN 'my_token');
CONNECT qk;
SELECT count(*) FROM events;
DISCONNECT;
```

While `CONNECT` is active, unqualified table names resolve and execute on the remote database. When no remote session is active, running `DISCONNECT` raises an error. Local in-memory databases and local DuckDB files reject `CONNECT`.

To route directly without prior attachment, pass the URI and token to `CONNECT`:

```sql
CONNECT 'quack:localhost:9494' (TOKEN 'my_token');
SELECT 42;
DISCONNECT;
```

To query remote tables while keeping the local session active, qualify names against the attached catalog:

```sql
ATTACH 'quack:localhost' AS remote_db (TOKEN 'my_token');
FROM remote_db.t;
FROM remote_db.query('SELECT 42');
```

To execute a single ad-hoc query without attaching a catalog, use `quack_query`:

```sql
FROM quack_query('quack:localhost', 'SELECT 42', token = 'my_token');
```

When querying Quack concurrently, enforce one Quack connection per thread. Calling `con.cursor()` in Python shares the underlying remote session; concurrent queries across shared cursors fail with `superseded by a new query`.

When binding parameters against Quack tables, client-side parameter binding fails with `Values were not provided`. To supply parameterized values, stage them in a DataFrame or local temporary table, or route the session with `CONNECT` and run SQL `PREPARE` and `EXECUTE`. Python DB-API binding continues to fail even after `CONNECT`.

| Option | Use |
| --- | --- |
| `TOKEN` | Explicit token overriding matching Quack secrets. |
| `TYPE quack` | Secret type qualifier. |
| `DISABLE_SSL` | Force plain HTTP over local connections. |
| `SSL_FINGERPRINT` | Trust a specific self-signed certificate fingerprint. |
| `CLIENT_ID` | Client identifier string (at least 4 characters). |
| `HEARTBEAT_TIMEOUT` | Connection lease timeout in seconds. |

To keep tokens out of query statements, store credentials in a scoped secret:

```sql
CREATE SECRET (
    TYPE quack,
    TOKEN 'my_token',
    SCOPE 'quack:localhost:9494'
);
ATTACH 'quack:localhost:9494' AS remote_db (TYPE quack);
```

The `SCOPE` pattern must match the target URI exactly. `SCOPE 'quack:'` covers only the default `quack:` URI, not explicit host and port strings.

For attached catalog administration, use `quack_query_by_name(catalog, query)`, `quack_connection_id(catalog)`, `quack_cancel(catalog, connection_id)`, and `quack_clear_cache()`.

## Security

By default, Quack binds to `localhost` over plain HTTP without TLS. On a single machine, this is correct.

When exposing DuckDB across machines, keep `quack_serve` on `localhost` and terminate TLS with a reverse proxy in front. Configure the proxy with a 256 MB request body limit, 600-second read and send timeouts, HTTP/1.1 keep-alive enabled, response buffering disabled, and listen on port 443. Because Quack defaults to port 9494, connecting clients must explicitly specify port 443. Non-local client URIs assume HTTPS.

Refuse `allow_other_hostname = true` on shared networks (`0.0.0.0` is not local). Reject direct external exposure unless the user explicitly mandates it behind a verified TLS proxy. Never record tokens in shell history, version control, or `state.sql`; use named secrets.

A Quack token provides host OS-user access, not tenant isolation. Authenticated clients can read or write host files and install extensions permitted to the server user. To restrict capabilities, start the server first, then lock configuration:

```sql
CALL quack_serve('quack:localhost', token = 'my_token');
SET enable_external_access = false;
SET lock_configuration = true;
```

Locking configuration before `quack_serve` fails because the server reads `~/.duckdb/stored_secrets` at startup.

The server validates the token on connection and triggers an authorization callback before each query. Default callbacks permit all authenticated queries; override them when sharing an instance. `quack_authentication_function` accepts `(sid, client_token, server_token)` and returns `BOOLEAN`. `quack_authorization_function` accepts `(sid, query)` and returns `BOOLEAN` to allow or deny, or `VARCHAR` SQL to replace the incoming query.

To enforce row filters or tenant boundaries, return rewritten SQL via the `VARCHAR` signature. Never inspect or authorize queries with regular expressions on query text. SQL comments can disguise leading keywords, and data-modifying CTEs begin with `WITH`, allowing write queries to bypass `SELECT`-prefix filters. Before configuring `quack_authorization_function`, consult the security documentation.

Both callbacks run inside a fresh server-side connection and cannot depend on session state.

## Postgres and MySQL

To route an interactive session directly to PostgreSQL or MySQL with SQL pushdown optimization, run `CONNECT`:

```sql
CONNECT 'postgres:dbname=mydb host=localhost';
SELECT count(*) FROM orders;
DISCONNECT;
```

When routing PostgreSQL sessions, prefix the string with `postgres:`, followed by either a libpq key-value string or a standard URI:

```sql
CONNECT 'postgres:dbname=mydb host=localhost';
CONNECT 'postgres:postgresql://localhost/mydb';
```

When omitting the `postgres:` prefix (such as `CONNECT 'postgresql://localhost/mydb'`), DuckDB interprets the URI as a local database file path and fails. Conversely, catalog attachment accepts the unadorned URI: `ATTACH 'postgresql://localhost/mydb' (TYPE postgres);`.

When routing MySQL sessions, run `CONNECT 'mysql:host=localhost database=mydb';`. Omitting `mysql:` or using a bare URI fails identically.

To execute queries directly without routing session state, call `postgres_query`, `postgres_execute`, `mysql_query`, or `mysql_execute`. Note that `postgres_scan`, `postgres_scan_pushdown`, and `mysql_scan` are absent in the DuckDB 2.0.0 binary.

## Verify

To verify Quack server and client operation, run across two terminals:

```bash
# Terminal 1: start server and keep process active
duckdb -serve

# Terminal 2: connect using the persistent __default_quack secret
duckdb -connect -c "SELECT 42 AS a;"
```

Confirm the second command returns `42`. Because passing `-c` exits immediately after executing `quack_serve`, never attempt to start a persistent server via `duckdb -c 'CALL quack_serve();'`.

## References

Consult these references when configuring advanced network topologies, proxy rules, authentication hooks, or external pushdown:

- [Quack overview](https://duckdb.org/docs/2.0/quack/overview.html) details the protocol and URI scheme.
- [Quack reference](https://duckdb.org/docs/2.0/quack/reference.html) covers functions, options, and configuration settings.
- [Quack security](https://duckdb.org/docs/2.0/quack/security.html) covers exposure risks, authentication, and authorization hooks.
- [Reverse proxy](https://duckdb.org/docs/2.0/quack/setup/reverse_proxy.html) provides nginx and Caddy deployment recipes.
- [CONNECT and DISCONNECT](https://duckdb.org/docs/2.0/sql/statements/connect.html) explains session routing and connection strings.
- [PostgreSQL extension](https://duckdb.org/docs/2.0/core_extensions/postgres/overview.html) and [MySQL extension](https://duckdb.org/docs/2.0/core_extensions/mysql.html) document direct execution functions.
- [Quack FAQ](https://duckdb.org/quack/faq.html) notes beta status and architectural limits.
