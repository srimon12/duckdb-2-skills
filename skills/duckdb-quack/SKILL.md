---
name: duckdb-quack
description: >
  Run DuckDB 2.0 as a server with the Quack protocol, or CONNECT the session
  to Quack, PostgreSQL, or MySQL. Use when the user says quack, duckdb -serve,
  duckdb -connect, CONNECT, remote pushdown, or /duckdb-quack.
---

# Quack and CONNECT

`quack` turns the current DuckDB process into an HTTP server. The extension installs and loads on first use. The default listen address is `quack:localhost` on port `9494`. Messages are HTTP. Result bodies use DuckDB's own serialization, so decimals, intervals, and nested types stay typed.

DuckDB 2.0 ships a faster Quack, and the protocol is still not stable. The Quack FAQ says it is beta, fine for prototyping, and not production-ready. Breaking changes may include the protocol, function names, and default settings. Do not treat the statements below as a frozen API.

Run the CLI with the `duckdb` skill. A Quack server is a long-running process. Start it in the background and do not block the session on it.

## Same machine

```bash
duckdb analytics.duckdb -serve
```

In another process:

```bash
duckdb -connect
```

`-serve` with no database path serves memory. `-connect` cannot be combined with a local database path. On one machine, `-serve` stores a persistent default `quack` secret when none exists, so `-connect` can find the token. A bare `CALL quack_serve()` does not do that. Its `create_secret_if_not_exists` default is false.

```sql
CALL quack_serve('quack:localhost', token = 'my_token');
CALL quack_stop('quack:localhost');
```

The token is at least 4 characters. If you omit it, the server generates one and returns it. Clients send it on every request.

## Client SQL

Attach, then route the whole session:

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

A secret scoped to the URI avoids putting the token in every statement:

```sql
CREATE SECRET (
    TYPE quack,
    TOKEN 'my_token',
    SCOPE 'quack:localhost'
);
ATTACH 'quack:localhost' AS remote_db (TYPE quack);
```

`TOKEN` on `ATTACH` overrides the secret. One ad-hoc query:

```sql
FROM quack_query('quack:localhost', 'SELECT 42', token = 'my_token');
```

## Who may connect

The default bind is localhost, plain HTTP, no TLS. That is the right setup on one machine.

`allow_other_hostname = true` with `quack:0.0.0.0:9494` exposes the server directly. Use it only when the user asked for a local test bind. For any other host, keep `quack_serve` on localhost and put a TLS reverse proxy in front. The proxy must not buffer streamed responses, must allow large bodies, and must keep the upstream connection alive. The proxy guide has nginx and Caddy examples. Non-local client URIs assume HTTPS. A local TLS test sets `DISABLE_SSL false` on `ATTACH`.

The server runs SQL as the user who started it, including writes.

## Postgres and MySQL

`CONNECT` also routes the session at PostgreSQL and MySQL. The pushdown optimizer sends the SQL to that server.

```sql
CONNECT 'postgres:dbname=mydb host=localhost';
SELECT count(*) FROM orders;
DISCONNECT;
```

The string starts with `postgres:` and then a libpq connection string. Do not emit `postgres://...` or `remote.query(...)`. Those appear in the August 2026 preview and are not the 2.0 connect page. The connect page names MySQL and does not show a MySQL connection-string example. Open the MySQL extension page before writing one.

## References

- https://duckdb.org/docs/2.0/quack/overview.html
- https://duckdb.org/docs/2.0/quack/security.html
- https://duckdb.org/docs/2.0/quack/setup/reverse_proxy.html
- https://duckdb.org/docs/2.0/sql/statements/connect.html
- https://duckdb.org/docs/2.0/clients/cli/arguments.html
- https://duckdb.org/docs/2.0/core_extensions/quack.html
- https://duckdb.org/quack/faq.html
- https://duckdb.org/2026/10/21/announcing-duckdb-200.html
