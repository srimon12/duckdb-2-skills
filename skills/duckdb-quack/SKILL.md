---
name: duckdb-quack
description: >
  Serve a DuckDB 2.0 database with the Quack protocol, or route a session to
  Quack, PostgreSQL, or MySQL with CONNECT. Covers tokens, TLS, reverse
  proxies, pushdown, and connection management. Use when the user says quack,
  duckdb -serve, duckdb -connect, CONNECT, or remote pushdown.
---

# Quack and CONNECT

Quack turns a DuckDB process into an HTTP server. The extension installs and loads on first use. Defaults are `quack:localhost` on port `9494` over plain HTTP. Result bodies use DuckDB's serialization, so decimals, intervals, and nested types stay typed.

The protocol is still beta. The Quack FAQ says it is fine for prototyping and not production-ready. Breaking changes may touch the protocol, function names, and default settings. A server exposes the full SQL surface, including writes, as the user who started it.

Run the CLI with the `duckdb` skill. A server is long-running. Start it in the background and do not block the session on it.

## Serve

```bash
duckdb analytics.duckdb -serve
```

`-serve` with no database path serves an in-memory database. On a machine with no default `quack` secret, `-serve` creates a persistent secret named `__default_quack` with scope `quack:`, so `duckdb -connect` works without extra setup. A bare `CALL quack_serve()` does not create it unless `create_secret_if_not_exists => true`.

```sql
CALL quack_serve('quack:localhost', token = 'my_token');
CALL quack_stop('quack:localhost');
```

`quack_stop` stops a server in the current process only. From another process it returns `No server found listening on ...` and the server keeps running. Pass the exact listen URI, including a non-default port.

The token is at least 4 characters. Omit it and the server generates one and returns it.

| Parameter | Default | Use |
| --- | --- | --- |
| `listen_uri` | `quack:localhost` | Host and port. |
| `token` | generated | Shared secret. |
| `secret` | unset | Name of an existing `quack` secret to use. |
| `create_secret_if_not_exists` | `false` | Persist the generated token as the default `quack` secret. |
| `allow_other_hostname` | `false` | Permit a non-local bind such as `0.0.0.0`. Testing only. |
| `disable_ssl` | `true` for local, else `false` | Plain HTTP versus HTTPS. |
| `ssl_cert_file`, `ssl_key_file` | generated | Certificate and key. |

```sql
SELECT * FROM quack_server_list();
SELECT * FROM quack_active_connections();
CALL quack_generate_keys('/path/to/keys');
```

`quack_generate_keys` writes a self-signed `server.pem` and `private_key.pem` and returns the fingerprint. Put that fingerprint in the client's `SSL_FINGERPRINT`.

## Connect

```sql
ATTACH 'quack:localhost' AS qk (TOKEN 'my_token');
CONNECT qk;
SELECT count(*) FROM events;
DISCONNECT;
```

`DISCONNECT` with nothing connected raises. While `CONNECT` is active, unqualified names run on the remote. Local in-memory databases and local DuckDB files do not accept `CONNECT`.

Qualify names when you want the attachment as a catalog and the local session stays put:

```sql
ATTACH 'quack:localhost' AS remote_db (TOKEN 'my_token');
FROM remote_db.t;
FROM remote_db.query('SELECT 42');
```

One ad-hoc query:

```sql
FROM quack_query('quack:localhost', 'SELECT 42', token = 'my_token');
```

`ATTACH` options:

| Option | Use |
| --- | --- |
| `TOKEN` | Override any matching Quack secret. |
| `TYPE quack` | Pin the secret type. |
| `DISABLE_SSL` | Force plain HTTP. |
| `SSL_FINGERPRINT` | Trust a specific self-signed certificate. |
| `CLIENT_ID` | Client identifier, at least 4 characters. |
| `HEARTBEAT_TIMEOUT` | Lease timeout in seconds. |

A secret scoped to the URI keeps the token out of every statement:

```sql
CREATE SECRET (
    TYPE quack,
    TOKEN 'my_token',
    SCOPE 'quack:localhost:9494'
);
ATTACH 'quack:localhost:9494' AS remote_db (TYPE quack);
```

The scope must match the URI exactly. `SCOPE 'quack:'` covers the default `quack:` URI, not an explicit host and port.

A direct session route works too:

```sql
CONNECT 'quack:localhost:9494' (TOKEN 'my_token');
SELECT 42;
DISCONNECT;
```

Other client functions: `quack_query_by_name(catalog, query)` for an attached catalog, `quack_cancel(catalog, connection_id)`, `quack_connection_id(catalog)`, and `quack_clear_cache()`.

## Security

The default bind is localhost, plain HTTP, no TLS. That is correct on one machine. For any other host, keep `quack_serve` on localhost and put a TLS reverse proxy in front. The proxy guide recommends a 256 MB body limit, 600-second read and send timeouts, HTTP/1.1 keep-alive, and buffering off. Clients must name port 443 explicitly because Quack's default remains 9494. Non-local client URIs assume HTTPS.

Do not set `allow_other_hostname = true` for a shared network. `0.0.0.0` is not local. Refuse it unless the user explicitly asks and a TLS proxy is in front. Do not paste a token into a shell history, a committed file, or `state.sql`. Use a named secret.

A token is OS-user access, not tenant isolation. The server can read and write files as its user and install extensions. To reduce that surface, start the server first, then lock it:

```sql
CALL quack_serve('quack:localhost', token = 'my_token');
SET enable_external_access = false;
SET lock_configuration = true;
```

Locking before `quack_serve` fails because the server reads `~/.duckdb/stored_secrets` at startup. The default authorization callback allows every query. Replace it when the server is shared.

The server checks a token on connect and runs an authorization callback before each query. The defaults allow every authenticated query.

Do not replace that callback with a regular expression on the query text. A data-modifying CTE starts with `WITH`, and a comment can hide the first keyword, so a prefix check that allows `WITH` still runs writes. Read the security page before setting `quack_authorization_function`.

`quack_authentication_function` takes `(sid, client_token, server_token)` and returns `BOOLEAN`. `quack_authorization_function` takes `(connection_id, query)`. Both run on a fresh server-side connection, so they cannot rely on session state.

## Postgres and MySQL

`CONNECT` also routes the session at PostgreSQL and MySQL. The pushdown optimizer sends the SQL to that server.

```sql
CONNECT 'postgres:dbname=mydb host=localhost';
SELECT count(*) FROM orders;
DISCONNECT;
```

The string starts with `postgres:` and then a libpq connection string. Do not emit `postgres://...`. The 2.0 connect page names MySQL and does not show a MySQL connection-string example, so open the MySQL extension page before writing one.

The current PostgreSQL forms are `CONNECT 'postgres:dbname=mydb host=localhost'` and `CONNECT 'postgres:postgresql://localhost/mydb'`. `CONNECT 'postgres://localhost/mydb'` is treated as a local file and fails. `ATTACH 'postgres://localhost/mydb' (TYPE postgres)` does work. For MySQL, use `CONNECT 'mysql:host=localhost database=mydb'`; `mysql://...` fails the same way.

For direct reads and writes without routing the session, use `postgres_query`, `postgres_execute`, `mysql_query`, and `mysql_execute`. `postgres_scan`, `postgres_scan_pushdown`, and `mysql_scan` are absent from the 2.0.0 binary. Secrets and pooling live on the extension pages.

## Verify

```bash
# terminal 1: keep the process alive
duckdb -serve

# terminal 2: use the default secret that -serve created
duckdb -connect -c "SELECT 42 AS a;"
```

The second command must return `42`. A `-c` process exits immediately after `quack_serve`, so do not start a server that way.

## References

- [Quack overview](https://duckdb.org/docs/2.0/quack/overview.html) owns the protocol and URI scheme.
- [Quack reference](https://duckdb.org/docs/2.0/quack/reference.html) owns the functions, options, and settings.
- [Quack security](https://duckdb.org/docs/2.0/quack/security.html) owns exposure, auth, and authorization.
- [Reverse proxy](https://duckdb.org/docs/2.0/quack/setup/reverse_proxy.html) owns the nginx and Caddy recipes.
- [CONNECT and DISCONNECT](https://duckdb.org/docs/2.0/sql/statements/connect.html) owns session routing and the connection strings.
- [PostgreSQL extension](https://duckdb.org/docs/2.0/core_extensions/postgres/overview.html) and [MySQL extension](https://duckdb.org/docs/2.0/core_extensions/mysql.html) own the direct functions.
- [Quack FAQ](https://duckdb.org/quack/faq.html) states the beta status.
- A local server on port 9497 answered `quack_query` on DuckDB 2.0.0. The default port and the token behavior come from the 2.0 pages.
