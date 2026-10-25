# Slice: Quack, extensions, Python client

Status: complete
Scope: Quack server and client, `CONNECT`, PostgreSQL/MySQL attach and pushdown, extension install/update/repositories, and the Python client on DuckDB 2.0.0. Manual paths are relative to `research/sources/duckdb-2.0/`. Probe IDs map to the log below.
Sources: `quack/{overview,reference,security,troubleshooting}.md`, `quack/setup/{overview,deployment,reverse_proxy,quack_wasm}.md`; `sql/statements/connect.md`; `core_extensions/{quack,postgres/*,mysql}.md`; `clients/cli/{arguments,dot_commands}.md`; `extensions/*.md`; `operations_manual/securing_duckdb/securing_extensions.md`; `clients/python/*.md`; `guides/python/*.md`; local `duckdb v2.0.0 (Cyanoptera) d54cbbe3df`; Python `duckdb 2.0.0`; https://duckdb.org/quack/faq.html; https://duckdb.org/2026/08/17/duckdb-20-highlights; `tools/shell/include/shell_state.hpp` at `v2.0.0`.
## Verified facts
### 1. Quack server

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| Q1 | `quack_serve` has two overloads: `quack_serve(listen_uri VARCHAR, disable_ssl BOOLEAN, ssl_cert_file VARCHAR, ssl_key_file VARCHAR, allow_other_hostname BOOLEAN, token VARCHAR, secret VARCHAR, create_secret_if_not_exists BOOLEAN)` and the same without `listen_uri`. Only `listen_uri` is positional in the documented form. | P1 `duckdb_functions()`; `quack/reference.md` | Probed |
| Q2 | Defaults: `listen_uri='quack:localhost'`, `allow_other_hostname=false`, generated `token`, no `secret`, `create_secret_if_not_exists=false`, `disable_ssl=true` for local and `false` for non-local, generated self-signed cert/key. | `quack/reference.md`; P1/P7 | Documented + Probed |
| Q3 | Default port is `9494`; URI forms `quack:localhost`, `quack://localhost`, `quack:host:9000`, `quack:127.0.0.1`, `quack:[::1]:1234`. `quack_uri_parser(uri, ssl)` is a scalar returning `STRUCT(host, port, ipv6, ssl, url)`. | P7; `quack/overview.md` | Probed |
| Q4 | A token must be at least 4 characters. If `token` is omitted, the default `quack` secret's token is reused when one exists; otherwise a random token is generated and returned in `auth_token`. A supplied token is returned as given. Clients send it on every request. | P1/P7; `quack/reference.md`; `quack/security.md` | Probed + Documented |
| Q5 | `-serve` (CLI) stores a **persistent** default secret named `__default_quack`, type `quack`, scope `['quack:']`, when none exists. A bare `CALL quack_serve()` does **not** create it. | P1/P2; `clients/cli/arguments.md`; source default `create_secret_if_not_exists=true` | Probed |
| Q6 | `quack_stop(listen_uri)` stops a server **in the current process only**. From another process it returns `No server found listening on ...`; the server keeps serving. | P1 | Probed |
| Q7 | `quack_stop` needs the exact listen URI, including a non-default port. It returns a `status` row, not an error, when no local server matches. | P1 | Probed |
| Q8 | `quack_identify(name, provider, hostname, region, meta)` exists and returns `ok`; it sets the fields behind the `whoami()` table macro. `quack_server_list()` and `quack_active_connections()` exist. | P1; `quack/reference.md` | Probed |
| Q9 | `quack_generate_keys(directory=...)` writes `server.pem` and `private_key.pem` and returns `cert_file`, `key_file`, `fingerprint`, `status`. Existing key files are not overwritten. | P5; `quack/reference.md` | Probed |
| Q10 | `quack_query(uri, query, disable_ssl, ssl_fingerprint, token, client_id, heartbeat_timeout)` runs one stateless query. `quack_query_by_name(catalog, query)` runs against an attached catalog; `quack_cancel`, `quack_connection_id`, `quack_clear_cache` exist. | P1; `quack/reference.md` | Probed |
| Q11 | `-serve [quack[:SECRET]]` and `-connect [TYPE[:SECRET]]` exist. Only `quack` can be served. `-connect` cannot be combined with a local database path. | P2/P3; `clients/cli/arguments.md` | Probed |
| Q12 | `-serve quack:analytics` uses the named secret and prints its token as `auth_token`; `-connect quack:analytics` connects with `(SECRET 'analytics')`; an unknown secret errors `Secret with name "nope" not found`. | P3 | Probed |
| Q13 | Default `.serve_command` is `CALL quack_serve(create_secret_if_not_exists=true{serve_secret\|})`. Default `.connect_command` is `CONNECT '{type\|quack}:'{connect_secret\|}`. Placeholders are `{parameter\|default}`; `-serve quack:analytics` injects `, secret='analytics'`, `-connect` injects ` (SECRET 'analytics')`. | P3; `tools/shell/include/shell_state.hpp`; `shell_command_line_option.cpp` | Probed |
### 2. Quack client

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| C1 | Three client paths: `ATTACH 'quack:host' AS name` + `CONNECT name` (recommended); `ATTACH ... AS name` and qualify `name.table` / `name.query('SQL')`; `quack_query(uri, sql)`. | P1/P4; `quack/overview.md` | Probed |
| C2 | `CONNECT 'quack:host:port'` also works directly, and accepts `(TOKEN '...')`; `CONNECT 'quack:host:port'` without a token/secret fails `Authentication failed`. The connect page does not show this form. | P4 | Probed |
| C3 | `DISCONNECT` with no active `CONNECT` errors: `Invalid Input Error: DISCONNECT: no active CONNECT (already on LOCAL)`. | P4; `sql/statements/connect.md` | Probed |
| C4 | A second `CONNECT` while one is active errors: `Already connected to "q1"; DISCONNECT first before issuing another CONNECT`. | P4 | Probed |
| C5 | Local in-memory databases and local DuckDB files reject `CONNECT`: `the attached database does not support CONNECT`. | P4 | Probed |
| C6 | `ATTACH` options are `TOKEN`, `DISABLE_SSL` (default true local, false non-local), `TYPE`, `SSL_FINGERPRINT`, `CLIENT_ID` (min 4, default `quack_default_client_id`), `HEARTBEAT_TIMEOUT` (default 60s). | `quack/reference.md`; P5 | Documented + Probed |
| C7 | A local URI defaults to plain HTTP. `DISABLE_SSL false` on a plain-HTTP local server fails with an SSL connect error; a non-local URI defaults to HTTPS. | P5; `quack/overview.md` | Probed |
| C8 | A self-signed TLS server needs `SSL_FINGERPRINT` on the client. Without it: `SSL peer certificate or SSH remote key was not OK`; with the fingerprint from `quack_generate_keys`, the query succeeds. | P5 | Probed |
| C9 | A quack secret's `SCOPE` must match the URI used. `SCOPE 'quack:localhost:9499'` works for that URI; `SCOPE 'quack:'` does **not** cover an explicit host/port. The default `-connect` works because its URI is exactly `quack:`. | P4 | Probed |
| C10 | The attached catalog exposes `name.query('SELECT ...')`, e.g. `FROM qk.query('SELECT 42')`; this is valid. The preview's bare `remote.query($$...$$)` is not the 2.0 form. | P1; `quack/overview.md` | Probed |
| C11 | `ATTACH` binds all remote table definitions up front. One un-bindable table (e.g. an Iceberg lazy table reported as `UNKNOWN`) fails the whole attachment; use `quack_query()` or attach Iceberg with `TABLE_RESOLUTION 'eager'` on the server. | `quack/troubleshooting.md` | Documented |
| C12 | Reverse proxy requirements: nginx `client_max_body_size 256M`, `proxy_read_timeout/proxy_send_timeout 600s`, HTTP/1.1 keep-alive, `proxy_buffering off`; Caddy `flush_interval -1`, `request_body max_size 256MB`. Clients must name port 443 explicitly because Quack's default remains 9494. | `quack/setup/reverse_proxy.md`; P20 | Documented |
### 3. PostgreSQL and MySQL

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| PG1 | Current `CONNECT` form for PostgreSQL is `CONNECT 'postgres:dbname=mydb host=localhost'` — the type prefix plus a libpq key/value string. `CONNECT 'postgres:postgresql://localhost/mydb'` also works. | P8; `sql/statements/connect.md` | Probed |
| PG2 | `CONNECT 'postgres://localhost/mydb'` does **not** work in 2.0.0: it is treated as a local file and fails `Cannot open file "postgres://localhost/mydb"`. The same string **does** work in `ATTACH ... (TYPE postgres)`. | P8; `core_extensions/postgres/overview.md` | Probed |
| PG3 | `CONNECT 'mysql:host=localhost database=mydb'` works. `CONNECT 'mysql://localhost/mydb'` fails as a local file. The MySQL page has no `CONNECT` example. | P8; `core_extensions/mysql.md` | Probed |
| PG4 | `ATTACH '' AS db (TYPE postgres)` uses a `postgres` secret or libpq environment; `ATTACH 'dbname=...' AS db (TYPE postgres, READ_ONLY, SCHEMA 'public', ISOLATION_LEVEL 'READ COMMITTED')`. Default isolation is `REPEATABLE READ`. | `core_extensions/postgres/overview.md`; `postgres/secrets.md` | Documented |
| PG5 | `ATTACH ... (TYPE postgres)` exposes tables; ordinary `SELECT` pulls rows and uses filter pushdown (`pg_enable_filter_pushdown=true`). `CONNECT` routes the session and the remote pushdown optimizer ships SQL to PostgreSQL/MySQL. | `core_extensions/postgres/overview.md`; `core_extensions/mysql.md`; `sql/statements/connect.md` | Documented |
| PG6 | `postgres_query(attached_db, sql)` runs a read query and returns rows; `postgres_execute(attached_db, sql, use_transaction=true)` runs arbitrary SQL and returns an empty result. Both accept `params` (`postgres_query`, text protocol only) and `use_transaction`. | P9; `core_extensions/postgres/functions.md` | Probed |
| PG7 | `postgres_scan` and `postgres_scan_pushdown` are listed as deprecated in the manual but are **absent** from the 2.0.0 binary (`Catalog Error: Table Function ... does not exist`). `mysql_scan` is absent from both the manual and the binary. | P9; `postgres/functions.md` | Probed |
| PG8 | MySQL equivalents are `mysql_query(attached_db, sql)` and `mysql_execute(attached_db, sql)`; the binary also exposes `mysql_configure_pool`, `mysql_pin_connection`, `mysql_clear_cache`. | P9; `core_extensions/mysql.md` | Probed |
| PG9 | PostgreSQL pooling: `pg_pool_max_connections` default is `4 <= cpu_count * 1.5 <= 32` (12 on the 8-core probe host), `pg_pool_acquire_mode='force'`, `pg_pool_idle_timeout_millis=60000`, reaper on. `postgres_configure_pool()` lists or changes a pool; `pg_connection_cache` and `pg_connection_limit` are deprecated. | P9; `postgres/connection_pool.md`; `postgres/functions.md` | Probed |
| PG10 | MySQL pooling uses `mysql_pool_size` (12 on the probe host), `mysql_pool_acquire_mode`, idle/lifetime timeouts and reaper settings. | P9; `core_extensions/mysql.md` | Probed |
| PG11 | Secrets: `CREATE SECRET (TYPE postgres, HOST ..., PORT ..., DATABASE ..., USER ..., PASSWORD ...)`; then `ATTACH '' AS db (TYPE postgres)` or `(TYPE postgres, SECRET name)`. MySQL uses the same shape with `TYPE mysql`. Persistent secrets need `CREATE PERSISTENT SECRET`. Passwords in a connection string can leak in errors. | `postgres/secrets.md`; `core_extensions/mysql.md` | Documented |
### 4. Quack security and stability

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| S1 | The FAQ says Quack is **not production-ready**: beta, usable for prototyping, breaking changes expected in the protocol, function names and default settings; 2.0 is "polished" but the protocol is not stable. | P20; `quack/faq.html` | Documented |
| S2 | A Quack server exposes the full SQL surface of its DuckDB session: read/write to every table it sees, DDL, transactions, `COPY`, and file reads/writes. The default authorization callback allows every query. | `quack/security.md`; P6 | Probed |
| S3 | On a default server (`enable_external_access=true`), a token holder can read server files (`FROM read_text('/etc/hosts')`) and write them (`COPY ... TO 'scratch/05/remote_write.csv'`). This is not mentioned on the security page. | P6 | Probed |
| S4 | Mitigation: start the server, then `SET enable_external_access=false; SET lock_configuration=true`. Remote file reads/writes then fail with `file system operations are disabled by configuration`, and a remote `SET enable_external_access=true` fails because the configuration is locked. | P6 | Probed |
| S5 | Locking **before** `quack_serve` is not equivalent: `quack_serve` tries to read `~/.duckdb/stored_secrets` and fails `Cannot access directory ... stored_secrets`. Start the server first, then lock. | P6 | Probed |
| S6 | Defaults are conservative: random token, localhost-only bind, no TLS on localhost, HTTPS with a self-signed cert for non-local URIs. Direct internet exposure is explicitly discouraged; use a TLS-terminating reverse proxy. | `quack/security.md`; `quack/setup/reverse_proxy.md` | Documented |
| S7 | Authentication is `quack_check_token(sid, client_token, server_token) -> BOOLEAN`; authorization is `quack_nop_authorization(sid, query) -> BOOLEAN` or `-> VARCHAR`, where VARCHAR is the SQL to execute. The VARCHAR form is the supported row-filter hook. Both are global settings and run on a fresh server-side connection. SQL macros and extension-registered scalar functions work; Python UDFs from `create_function` do not. | `quack/security.md`; `quack/reference.md` | Documented |
| S8 | The manual's read-only authorization example is a prefix regex and is explicitly **not** a robust filter: `WITH x AS (SELECT 1) INSERT ...` starts with `WITH`. Use a read-only attached database or inspect the parsed statement type. | `quack/security.md` | Documented |
| S9 | A server process runs SQL as the OS user that started DuckDB, including writes and extension installation. An agent must not treat a token as tenant isolation. | `quack/security.md`; P6 | Probed |
| S10 | An agent must refuse: binding `0.0.0.0` or a public interface without an explicit request and a TLS proxy; `developer_mode_auth` or permissive authorization on a shared server; running untrusted SQL against a default server; loading community/unsigned extensions on a shared server; calling Quack production-ready. | `quack/security.md`; `extensions/community_extensions.md`; P6 | Documented + Probed |
### 5. Extensions

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| E1 | Syntax: `INSTALL name`, `INSTALL name FROM {core, community, core_nightly, 'url'}`, `INSTALL name VERSION 'vX.Y.Z'`, `FORCE INSTALL ...`, `INSTALL AND LOAD ...`, `FORCE INSTALL AND LOAD ...`. `FORCE` goes before `INSTALL`. | P10; `sql/statements/load_and_install.md`; `extensions/versioning_of_extensions.md` | Probed |
| E2 | `INSTALL` without `FORCE` is a no-op when the extension is already installed, so a changed `VERSION` or `FROM` is ignored. Use `FORCE INSTALL` to switch version or repository. | P10 | Probed |
| E3 | `UPDATE EXTENSIONS` updates from each extension's source repository. Columns are `extension_name`, `repository`, `update_result`, `previous_version`, `current_version`. `UPDATE EXTENSIONS (httpfs, azure)` limits the set. Only `REPOSITORY` installs are updated. The statement force-installs the repository's current build, so it replaces a pinned version; `CUSTOM_PATH` installs return `NOT_A_REPOSITORY`. Re-pin with `FORCE INSTALL ... VERSION` after an update. | P10; `sql/statements/update_extensions.md`; source `extension_helper.cpp` | Probed + Source |
| E4 | `UPDATE EXTENSIONS` does not reload anything. Extensions cannot be unloaded or reloaded; restart the process to use a new binary. | `sql/statements/update_extensions.md`; `extensions/installing_extensions.md` | Documented |
| E5 | Statically linked extensions are not updated by `UPDATE EXTENSIONS`. In the local CLI: `autocomplete`, `core_functions`, `icu`, `json`, `parquet`, `shell`, all `v2.0.0`. | P10; `sql/statements/update_extensions.md` | Probed |
| E6 | `duckdb_extensions()` columns: `extension_name`, `loaded`, `installed`, `install_path`, `description`, `aliases`, `extension_version`, `install_mode`, `installed_from`, `signature_key_fingerprint`. `install_mode` is `STATICALLY_LINKED`, `REPOSITORY`, `CUSTOM_PATH`, `NOT_INSTALLED`, or `UNKNOWN`. `installed_from` is a repository name for `REPOSITORY` and a source path for `CUSTOM_PATH`. | P10; `extensions/overview.md`; source `extension_install_info.hpp` | Probed + Source |
| E7 | Installation and loading are separate. Install once into `~/.duckdb/extensions/<version>/<platform>/`; load every process. The setting is `extension_directories` (a list): install into the first, load from all. `extension_directory` (singular) is deprecated and warns. | P10; `extensions/installing_extensions.md` | Probed |
| E8 | In Python, `duckdb.connect(config={"extension_directory": ...})` is accepted and sets the deprecated singular setting; `extension_directories` stays `[]`, so it looks ignored. Use `config={"extension_directories": ["..."]}`. | P18 | Probed |
| E9 | Autoload/autoinstall defaults are true: `autoinstall_known_extensions=true`, `autoload_known_extensions=true`. `LOAD` autoinstalls a known extension. Autoload applies only to core extensions; disable both and `lock_configuration` for untrusted SQL. | P10; `extensions/overview.md`; `operations_manual/securing_duckdb/securing_extensions.md` | Probed |
| E10 | A plain name comes from `core`; `FROM community` is the third-party repository; `core_nightly` exists. Community extensions are built and signed by DuckDB CI but not audited, and run with DuckDB's privileges. | `extensions/community_extensions.md`; `extensions/installing_extensions.md` | Documented |
| E11 | Platforms: core supports `linux_amd64`, `linux_arm64`, `osx_amd64`, `osx_arm64`, `windows_amd64`, `windows_arm64`. Community supports all except `osx_amd64` in 2.0; 2.1 drops `osx_amd64` entirely. HTTP probe: community `h3` for `osx_amd64` = 404, core `spatial` for `osx_amd64` = 200. | P12; `extensions/overview.md`; `extensions/extension_distribution.md` | Probed |
| E12 | Core and community extensions are signed; `signature_key_fingerprint` exposes the SHA-256 key. Unsigned extensions require `allow_unsigned_extensions=true` at startup (`duckdb -unsigned`), cannot be enabled while running, and are a code-execution risk. `strip` corrupts the metadata footer and makes an extension unloadable. | P10; `extensions/extension_distribution.md`; `operations_manual/securing_duckdb/securing_extensions.md` | Probed |
| E13 | Offline install: `INSTALL '/abs/path/name.duckdb_extension'`. A `.duckdb_extension.gz` file is accepted and decompressed by `INSTALL`; decompress it manually only if the installer rejects it. `LOAD '/abs/path/name.duckdb_extension'` skips the installed copy. The file basename determines the extension name (`quack_copy.duckdb_extension` installs as `quack_copy`, not `quack`). | P10 (gzip probe); P13; `extensions/advanced_installation_methods.md`; source `extension_install_dynamic.cpp` | Probed + Source |
| E14 | Troubleshooting: HTTP 404 lists candidate extensions; HTTP 451 is a regional legal block; dev builds may have no repository build. `core`/`community` fall back to `extensions.duckdb-backup.org`; `custom_extension_repository` and explicit `FROM 'url'` do not. `latest_stable_version.txt` returned `2.0.0`. | P10; `extensions/troubleshooting.md`; `extensions/installing_extensions.md` | Probed |
| E15 | `FORCE INSTALL spatial FROM core VERSION 'v1.1.8'` is syntactically valid but returned HTTP 404 for `v2.0.0/osx_arm64`. `FORCE INSTALL httpfs VERSION '77392a7207'` also returned HTTP 404 for `v2.0.0/linux_amd64`. The syntax is not evidence that the version exists for the build; test a pin in a scratch `extension_directories` path before shipping it. | P10; probe 2026-10-26 | Probed |

### 6. Extension repositories (WIP)

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| R1 | The manual marks custom repositories **work-in-progress; syntax may change**. Do not present the statements as frozen. | `extensions/extension_repositories.md` | Documented |
| R2 | `allow_extension_repositories` is `undecided` (default), `allowed`, or `forbidden`. `undecided` blocks adds but trusts existing repositories; `forbidden` blocks adds and distrusts existing custom repositories. | P11; `extensions/extension_repositories.md` | Probed |
| R3 | While running, only `undecided -> {allowed, forbidden}` and `allowed -> forbidden` are legal; `allowed -> undecided` errors. | P11 | Probed |
| R4 | `CREATE EXTENSION REPOSITORY name WITH PREFIX '...'` fetches and pins repository keys, printing SHA-256 fingerprints. `USING PUBLIC KEY 'PEM'` pins a key without trusting the network; keys are 2048-bit RSA, PEM or base64 body. Prefix can be a local path, `https`, `s3`, etc. | P11; `extensions/extension_repositories.md` | Probed |
| R5 | `duckdb_extension_repositories()` columns are `repository_name`, `prefix`, `type`, `key_fingerprints`, `public_keys`; built-ins appear as `CORE`/`COMMUNITY`, custom as `USER_PROVIDED`. | P11 | Probed |
| R6 | Pinned repositories are stored **globally** under `~/.duckdb/extension_repositories/<name>.duckdb_extension.repo.json`, not in the database file: a new empty database sees the same repository. They survive restarts. | P11 | Probed |
| R7 | `extension_repository_directory` is the trust anchor. While signature checking is enabled it can only be set at startup; `SET` at runtime errors. | P11; `operations_manual/securing_duckdb/securing_extensions.md` | Probed |
| R8 | `DROP EXTENSION REPOSITORY name` removes the global trust entry; after the drop `duckdb_extension_repositories()` has no `USER_PROVIDED` row. | P11 | Probed |

### 7. Python install

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| Y1 | DuckDB 2.0 requires Python 3.11+; free-threaded CPython is unsupported. On Python 3.10.21, plain `pip install duckdb` installed `1.5.6`, not 2.0. | P14; `clients/python/overview.md`; `guides/python/install.md` | Probed |
| Y2 | `pip install duckdb` installs 2.0.0 on 3.12/3.14; `uv pip install duckdb==2.0.0` also works; `duckdb.__version__` is `2.0.0`. | P14 | Probed |
| Y3 | `duckdb.sql()` uses a module-global in-memory database; `duckdb.connect()` without arguments creates a separate in-memory database. | P19; `clients/python/overview.md` | Probed |

### 8. Python API changes

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| A1 | `con.sql(q)` returns a lazy relation for a read query; the query runs on every read and `sql_query()` returns the text. `con.execute(q)` runs now and returns the connection with an open result. | P15; `relational_api.md` §Lazy Evaluation | Probed |
| A2 | A relation reruns on each read: `SELECT count(*)` went 1, 2, 3 after inserts. `materialize()` freezes the rows once and returns a relation over them. | P15/P19 | Probed |
| A3 | `con.sql("CREATE TABLE ...")` and `con.sql("INSERT ...")` run **once at the call** and return a relation over the statement's result (e.g. `Count 1`). Printing/fetching that relation does **not** rerun the DDL/DML. | P15 | Probed |
| A4 | Relations no longer have `fetchone()`, `fetchmany()`, `fetch_df_chunk()`, `execute()` or `arrow()`; they raise `AttributeError` with a migration message. Use `iter_rows()`, `to_arrow_reader()`, or `con.execute()`. | P15 | Probed |
| A5 | `con.execute()` results retain `fetchone()`, `fetchmany()`, `fetchall()`, `fetch_df_chunk()`, `df()`, `fetchnumpy()`, `fetch_df()`. They no longer have `fetch_arrow_table()`, `fetch_record_batch()`, `arrow()` or `pl()`. | P15; `dbapi.md` | Probed |
| A6 | `execute()` results have `to_arrow_table()` and `to_arrow_reader()`, but they copy all rows and emit a `UserWarning`; the reader does not stream. Use `con.sql(q)` for streaming Arrow/Polars. | P15/P17; `dbapi.md` | Probed |
| A7 | `rel.fetch_record_batch()`, `rel.arrow()`, `rel.fetch_arrow_table()` remain as deprecated aliases on relations; `fetch_record_batch()` warns `DeprecationWarning`. | P15; `relational_api.md` | Probed |
| A8 | `ResourceInUseException` is raised when `con.sql()` or `con.query()` runs while a **streaming** `execute()` result or Arrow reader is open. A new `con.execute()` does not raise; it replaces the open result silently. Small results may be buffered, so the exception is not a reliable guard. `con.complete()` drains the result; `con.abort()` cancels it. | P15; P18; `dbapi.md` | Probed |
| A9 | Inside `con.begin()`, a failed `execute()` aborts the transaction. Further statements raise `TransactionException` until `rollback()`; `commit()` rolls the aborted transaction back without raising. After `commit()` the transaction is closed, so a following `rollback()` errors `cannot rollback - no transaction is active`. | P19; `dbapi.md` | Probed |
| A10 | One connection serves one call at a time. A concurrent call raises `ResourceInUseException`; each thread needs `con.cursor()`. A cursor has its own transaction and connection-local settings such as `search_path`; some settings are database-global. Two read-write connections to one file in one process are legal under MVCC; a read-only connection alongside a writer fails with a different-configuration error. | P19; P18; `overview.md` | Probed |
| A11 | `ColumnExpression("t.x")` is the single column name `t.x`; `col("t", "x")` is qualified. A bare string in an expression is a value; `col("s") == "x"` compares to text and warns when `x` is also a column. | P16; `expression.md` | Probed |
| A12 | `rel.update(set={"a": "x"})` raises `TypeError`; use `col("x")` or `lit("x")`. `fn("upper", col("s"))` builds a function call. | P16 | Probed |
| A13 | `con.values({1: "a"})` becomes `MAP(INTEGER, VARCHAR)`; string keys become `STRUCT`. | P16; `conversion.md` | Probed |
| A14 | Relations gained `offset`, `sample`, `head`, `rename`, `pivot`, `drop`, `unnest`, `unpivot`, `preview`, `group_by`, `with_columns`. A column named like one is reached with `rel["offset"]`. `preview()` returns `str`; `group_by()` returns `GroupedRelation` with `.agg()`. | P16; `relational_api.md` | Probed |
| A15 | `write_csv(..., overwrite=False)` and `write_parquet(..., overwrite=False)` raise `IOException` when the file exists; omitting `overwrite` replaces it. With `partition_by`, only `overwrite=True` writes into a non-empty directory. | P17; `relational_api.md` | Probed |
| A16 | `Decimal("1E+2")` converts to `DECIMAL(3,0)` holding 100; `Decimal("1E-7")` is `DECIMAL(8,7)`; more than 38 digits becomes `DOUBLE`; NaN/inf become `FLOAT`. | P17; `conversion.md` | Probed |
| A17 | Default Arrow batch size is 131072 rows for `to_arrow_table`/`to_arrow_reader`/`pl`; `batch_size` overrides it. | P17; `migration.md` | Probed |
| A18 | New 2.0 files use storage version 69; DuckDB 1.5 reads versions 64–68. A `v1.5.0` compatibility file opened in 1.5.6; the default 2.0 file failed with `version number 69 ... can only read versions between 64 and 68`. | P18; `operations_manual/migration.md` | Probed |

### 9. Python connection config

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| N1 | `duckdb.connect(database, read_only, config)`; `config` takes settings such as `threads`, `memory_limit`, `temp_directory`, `storage_compatibility_version`. A read-only connection does not create a missing file and rejects writes. | P18; `dbapi.md`; `overview.md` | Probed |
| N2 | `config={"extension_directories": ["..."]}` works. `config={"extension_directory": "..."}` is deprecated but still effective for the load path; `current_setting('extension_directories')` stays `[]`, so it looks ignored. Prefer the plural list. | P18 | Probed |
| N3 | `check_same_thread` is not a 2.0 Python option: `duckdb.connect(check_same_thread=False)` raises `TypeError`; `config={"check_same_thread": False}` raises `InvalidInputException: options were not recognized`. | P18 | Probed |
| N4 | `:memory:` is a fresh database; `:memory:name` shares a named in-memory database; `:default:` and `duckdb.default_connection()` return the module default; `set_default_connection(con)` replaces it. | P19; `dbapi.md` | Probed |
| N5 | `from_df`, `from_arrow`, `from_query`/`query`/`sql`, `read_csv`, `read_parquet`, `read_json`, `table`, `values`, `view` create relations. `duckdb.from_df` is the module form of `con.from_df`. | P19; `relational_api.md` | Probed |
| N6 | Use the appender for Python-produced rows, not `executemany`. `with con.appender("t") as app:` flushes on success; `action` one of `insert`, `upsert`, `update`, `delete`; `update` and `delete` take a list `key`, while `upsert` uses the PK/unique constraint and rejects `key`. `columns` is a list; `query_appender(statement, columns, source=...)` takes a dict and reads `appender_data` (the source reads `appender_buffer`). `flush()`/`clear()`, no `close()`. | P19; `appender.md` | Probed |
| N7 | `max_temp_directory_size` passed in `config` is ignored for enforcement; `current_setting()` shows it but writes exceed it. Set it with `SET` after connecting. | `known_issues.md`; P18 | Documented / Probed |
| N8 | In one process, two read-write connections to one file work under MVCC. A read-only connection opened after a read-write connection to the same file fails: `ConnectionException: Can't open a connection to same database file with a different configuration than existing connections`. | P18 | Probed |

## Existing skill audit

| Skill | Claim or omission | Verdict | Fix |
|---|---|---|---|
| quack | “DuckDB 2.0 ships a faster Quack, and the protocol is still not stable… beta… not production-ready.” | Correct | Keep; cite FAQ and never call it production-ready. |
| quack | “If you omit it, the server generates one and returns it.” | Thin | With no explicit token, `quack_serve` reuses the default `quack` secret's token when one exists; only otherwise does it generate a random token. |
| quack | “`-serve` stores a persistent default `quack` secret when none exists… A bare `CALL quack_serve()` does not. Its `create_secret_if_not_exists` default is false.” | Correct, thin | Add exact name `__default_quack`, scope `['quack:']`, and that `-connect` without it errors `Could not find a Quack authentication token`. |
| quack | “`CALL quack_stop('quack:localhost')`.” | Correct, thin | State that `quack_stop` stops only a server in the current process and needs the exact listen URI. |
| quack | “`DISCONNECT` with nothing connected raises.” | Correct | Keep; exact error is `DISCONNECT: no active CONNECT (already on LOCAL)`. |
| quack | “Local in-memory databases and local DuckDB files do not accept `CONNECT`.” | Correct | Keep. |
| quack | “`allow_other_hostname = true` with `quack:0.0.0.0:9494` exposes the server directly. Use it only when the user asked for a local test bind.” | Partly wrong | `0.0.0.0` is not local. Say: refuse to bind a non-local address unless the user explicitly asks and a TLS proxy is in front; the default error is `Only localhost is allowed...`. |
| quack | “The server runs SQL as the user who started it, including writes.” | Correct, thin | Add filesystem read/write and extension installation; probe shows `/etc/hosts` read and `COPY` write from a client. |
| quack | “Do not emit `postgres://...` or `remote.query(...)`. Those appear in the August 2026 preview and are not the 2.0 connect page.” | Partly right | `CONNECT 'postgres://...'` fails in 2.0.0, but `ATTACH 'postgres://...' (TYPE postgres)` works. `remote_db.query()` is valid for Quack; the preview's bare `remote.query()` is not. Split these claims. |
| quack | “The connect page names MySQL and does not show a MySQL connection-string example. Open the MySQL extension page before writing one.” | Thin | The MySQL page also has no `CONNECT` example. Probed form: `CONNECT 'mysql:host=localhost database=mydb'`; `mysql://...` fails. |
| quack | Omission: direct `CONNECT 'quack:host:port'` with `(TOKEN ...)` or a secret. | Thin | Add the direct form and the exact-scope secret rule; the skill currently teaches only `ATTACH` + `CONNECT`. |
| quack | Omission: full `quack_serve` signature, `secret`, `create_secret_if_not_exists`, `disable_ssl`, cert/key, `SSL_FINGERPRINT`, `quack_identify`, `whoami`, `quack_server_list`. | Thin | Add a compact option table; put auth callbacks and logging in a reference. |
| quack | Omission: reverse proxy numbers (256M body, 600s timeouts, no buffering, HTTP/1.1 keep-alive, port 443). | Thin | Add the required proxy settings, not just “do not buffer”. |
| extensions | “An extension installed by 1.5 is the wrong build for 2.0.” | Correct | Keep. |
| extensions | “`INSTALL AND LOAD` is `INSTALL`, then `LOAD`. It accepts `FORCE`, `FROM`, and `VERSION`.” | Correct | Keep; exact order is `FORCE INSTALL AND LOAD`. |
| extensions | “`FORCE INSTALL spatial FROM core VERSION 'v1.1.8';`” | Correct syntax, bad example | On 2.0.0/osx_arm64 this exact command returns HTTP 404. The skill now uses a placeholder and says to test a pin in a scratch `extension_directories` path. |
| extensions | “From 2.0 community extensions are not built for `osx_amd64`. Core still are. 2.1 drops `osx_amd64`.” | Correct | Keep; HTTP probe confirms 404 community / 200 core. |
| extensions | “The statement does not reload… Statically linked extensions including `json`, `parquet`, `icu` are not updated this way. Result columns…” | Correct | Keep; add `autocomplete`, `core_functions`, `shell` to the local static list if enumerating. |
| extensions | “`allow_extension_repositories` is `undecided` by default… `allowed` permits adds… `forbidden` blocks adds and distrusts…” | Correct | Keep; add that the value can only move toward `allowed`/`forbidden`, never back. |
| extensions | “At `CREATE`, DuckDB fetches the repository public keys, pins them, and prints each SHA-256 fingerprint. You can pin a key yourself with `USING PUBLIC KEY`.” | Correct, thin | Add that `USING PUBLIC KEY` skips the fetch, and that the trust store is global under `~/.duckdb/extension_repositories`. |
| extensions | `SELECT repository_name, prefix, key_fingerprints FROM duckdb_extension_repositories();` | Correct, thin | Table also has `type` and `public_keys`; built-ins appear as `CORE`/`COMMUNITY`. |
| extensions | “Pinned repositories survive restarts.” | Correct, thin | They are global, not per database; `extension_repository_directory` is startup-only while signatures are enforced. |
| extensions | Omission: `extension_directories` vs deprecated `extension_directory`, offline `INSTALL 'path'`, unsigned loading, autoinstall/autoload, `duckdb_extensions()` columns, HTTP 404/451. | Thin | Add a short install/troubleshooting table; keep full repo syntax in a reference. |
| python | “DuckDB 2.0 requires Python 3.11 or newer… On Python 3.10, `pip install duckdb` installs a 1.x release.” | Correct | Probe: 3.10.21 installs 1.5.6. Add `free-threaded unsupported` and pip/uv. |
| python | `execute()` Arrow/Polars table; relation `fetchone`/`fetchmany`/`fetch_df_chunk` removal; `materialize`; expressions; dict keys; relation methods. | Correct | Keep; note `con.execute()` still has `fetchone`/`fetchmany`/`fetch_df_chunk`. |
| python | “`con.sql("CREATE TABLE ...")`: Returns a relation, and printing it runs the query again. Use `con.execute()` for DDL and DML.” | Wrong | DDL/DML runs once at the `sql()` call; printing/fetching the returned relation does not rerun it. Only read relations rerun. Rewrite. |
| python | “A failed `execute()` inside `con.begin()` aborts… `commit()` rolls back. Call `rollback()` before more SQL.” | Correct, thin | After `commit()` the transaction is already closed; calling `rollback()` then errors. Say “call `rollback()` (or `commit()`, which rolls back) once.” |
| python | “`rel.write_csv(path, overwrite=False)` … raise if the file exists. Omit `overwrite` to replace.” | Correct | Keep; add partition-directory nuance. |
| python | “`Decimal("1E+2")` … 100 as DECIMAL(3,0)” and “Arrow batch 131072.” | Correct | Keep; add >38 digits -> DOUBLE. |
| python | “2.0 can open a 1.5 file; a 2.0 default file cannot be opened by 1.5. Pin with `storage_compatibility_version: v1.5.0`.” | Correct | Probe confirms version 69 vs 64–68 and that the pinned file opens in 1.5.6. |
| python | Omission: connection config, `extension_directory` singular deprecated but effective, `check_same_thread` rejected, default connection, `from_df`/`from_arrow`/`from_query`, appender. | Thin | Add a short “connection and ingestion” section; full appender/UDF details stay a reference. |

## Gaps worth adding

| Rank | Gap | Why an agent needs it | Home: SKILL.md or reference |
|---|---|---|---|
| 1 | Quack exposes the server's filesystem and extension installation; lock with `enable_external_access=false` + `lock_configuration=true` **after** `quack_serve`. | A token otherwise means read/write of server files and code execution as the server user. | SKILL.md, security section |
| 2 | Direct `CONNECT 'quack:host:port'` with `(TOKEN ...)`, and exact secret `SCOPE` matching. | The skill teaches only `ATTACH` + `CONNECT`; agents will use a broader `SCOPE 'quack:'` and fail auth. | SKILL.md |
| 3 | Python `extension_directory` (singular) is deprecated but still effective for the load path; `extension_directories` stays `[]`. Prefer `extension_directories`. | The plural list is the supported configuration; the singular alias can disappear in a later release. | SKILL.md |
| 4 | DDL/DML through `con.sql()` runs once; printing the relation does not rerun it. | The current skill overstates the rerun and may push agents away from `con.sql()` unnecessarily. | SKILL.md, migration table |
| 5 | No unverified pin example. `FORCE INSTALL ... VERSION 'v1.1.8'` is not a working 2.0.0/osx_arm64 example, and the `httpfs` hash also 404s. | Copying an unverified example yields HTTP 404. The skill now uses a placeholder and a scratch-directory test. | SKILL.md |
| 6 | Extension repository trust is global and the trust directory is startup-only; `USING PUBLIC KEY` pins without network. | An agent may expect per-database trust or try to change the directory at runtime. | reference (repository page is WIP and long) |
| 7 | `quack_stop` is local-only; `-serve` creates `__default_quack`, bare `CALL` does not. | Agents will try to stop a remote server or expect a SQL call to create the CLI secret. | SKILL.md |
| 8 | `postgres_scan`/`postgres_scan_pushdown` are absent in 2.0.0; `mysql_scan` never existed; use `postgres_query`/`postgres_execute`/`mysql_query`/`mysql_execute`. | Agents hallucinate scan functions from older docs. | SKILL.md |
| 9 | Quack TLS needs `SSL_FINGERPRINT` for a self-signed cert; proxy needs 256M body, 600s timeouts, no buffering, port 443. | A local HTTPS test or a proxy deploy fails without these. | reference (proxy recipes) |
| 10 | Python `check_same_thread` is rejected; `con.cursor()` is the 2.0 answer. | Common 1.x-style connection code fails at connect time. | SKILL.md |
| 11 | Extension metadata (`duckdb_extensions()` columns), offline install, unsigned loading, autoinstall/autoload settings. | Install/update debugging and air-gapped deployments need them. | SKILL.md (compact), reference (troubleshooting) |
| 12 | Quack auth callbacks and the Python-UDF limitation. | An agent may try `con.create_function` as a Quack auth hook; it is not visible on the fresh server connection. | reference |

## Traps and contradictions

| Trap | What happens | Correct move | Evidence |
|---|---|---|---|
| `CONNECT 'postgres://host/db'` | Treated as a local file: `Cannot open file "postgres://..."`. | Use `CONNECT 'postgres:dbname=... host=...'` or `CONNECT 'postgres:postgresql://...'`. | P8 |
| `ATTACH 'postgres://host/db' (TYPE postgres)` | Works; the same string in `CONNECT` does not. | Do not generalize the `CONNECT` warning to `ATTACH`. | P8 |
| `CONNECT 'mysql://host/db'` | Treated as a local file. | Use `CONNECT 'mysql:host=... database=...'`. | P8 |
| Secret `SCOPE 'quack:'` for `quack:localhost:9499` | Authentication failed; the secret does not match the host-specific URI. | Scope to the exact URI, or use the default `quack:` URI. | P4 |
| `CALL quack_stop(...)` from a client process | Returns `No server found listening...`; the remote server stays up. | Stop it in the serving process, or terminate that process. | P1 |
| Locking configuration before `quack_serve` | `quack_serve` cannot read `~/.duckdb/stored_secrets`; server fails to start. | Start server first, then `SET enable_external_access=false; SET lock_configuration=true`. | P6 |
| Default Quack server + token holder | Can read `/etc/hosts` and write files as the server user; can install extensions. | Treat the token as OS-user access; lock external access or run in a sandbox. | P6 |
| `FORCE INSTALL spatial FROM core VERSION 'v1.1.8'` | HTTP 404 for `v2.0.0/osx_arm64`. | Verify the version exists for the build; do not copy an unverified pin. The skill now ships no pin example. | P10 |
| `SET extension_directory='...'` | Warning: deprecated; singular is removed in a future release. | `SET extension_directories=['...']`. | P10 |
| Python `config={"extension_directory": "..."}` | Accepted; deprecated singular sets the load path while `extension_directories` stays `[]`. | Use `extension_directories`. | P18 |
| `UPDATE EXTENSIONS` then use the extension | Old binary remains loaded until restart; extensions cannot reload. | Restart the process. | P10 |
| Python `con.sql("INSERT ...")` then print relation | Prints `Count 1`; does not insert twice. | Use `con.execute()` for DDL/DML; `con.sql()` for read relations. | P15 |
| Python transaction commit after failed statement | `commit()` rolls back and closes the transaction; a following `rollback()` errors. | Call `rollback()` before more SQL, or accept `commit()` as the rollback. | P19 |
| Python `duckdb.connect(check_same_thread=False)` | `TypeError: connect(): incompatible function arguments`; config also rejected. | Remove it; use `con.cursor()` per thread. | P18 |
| 2.0 default database file opened by 1.5 | `version number 69 ... can only read versions between 64 and 68`. | Create with `storage_compatibility_version='v1.5.0'` if 1.5 must read it. | P18 |
| `.help serve_command` text | Says placeholders use `-host/-port/-token`, but those CLI flags do not exist. | Use the actual placeholders `{serve_secret\|}`, `{type\|quack}`, `{connect_secret\|}`. | P3; `shell_state.hpp` |

## What not to add

- C API, Java, Rust, Node.js, Go, or R client skills. The pack already routes those to their docs; this slice only owns Python.
- A full Quack wire-protocol or log-schema description. It is beta and the reference already owns it; link, do not copy.
- Quack production deployment recipes beyond the reverse-proxy pattern. The FAQ says not production-ready; an agent should not present HA, multi-tenant, or public-internet recipes as supported.
- Full PostgreSQL/MySQL settings tables, RDS IAM, hstore, and `COPY` formats. These are vendor-extension depth, not a 2.0 migration decision.
- Python UDF, Spark API, Ibis, JupySQL, and Polars lazy-plan internals. Link to the pages; keep only the 2.0 migration rows and the connection/threading rules.

## Probe log

```text
P1  quack server lifecycle (port 9495, token probe_token)
$ python scratch/05/quack_server.py
version 2.0.0
serve: [('quack:localhost:9495', 'http://localhost:9495', 'probe_token')]
servers: [('quack:localhost:9495', 'http://localhost:9495', 'localhost', 9495, 0, {'ipv6': 'false', 'ssl': 'false'})]
secrets-after: []
$ duckdb -c "FROM quack_query('quack:localhost:9495','SELECT 42 AS x',token='probe_token');"
42
$ duckdb -c "CALL quack_stop('quack:localhost:9495');"
No server found listening on quack:localhost:9495        # from a second process
server log: [('Stopped listening on quack:localhost:9495',)]   # in the serving process
P2  CLI -serve creates the default secret; -connect uses it
$ duckdb -c "SELECT name,type,scope FROM duckdb_secrets();"   # before: 0 rows
$ (tail -f /dev/null | duckdb scratch/05/serve_test.db -serve)
auth_token 24B86ECE2EB24FA4A628D75AE6E7EF51
$ duckdb -c "SELECT name,type,scope FROM duckdb_secrets();"
__default_quack | quack | ['quack:']
$ duckdb -connect -c "SELECT current_database();"
serve_test
$ duckdb scratch/05/serve_test.db -connect
Invalid Input Error: cannot open a database (...) together with -connect
P3  TYPE:SECRET and command templates
$ duckdb -c "CREATE PERSISTENT SECRET analytics (TYPE quack, TOKEN 'secret_tok', SCOPE 'quack:localhost');"
$ (tail -f /dev/null | duckdb scratch/05/serve_secret.db -serve quack:analytics)
auth_token secret_tok
$ duckdb -connect quack:analytics -c "SELECT 11;"
11
$ duckdb -connect quack:nope
Invalid Input Error: Secret with name "nope" not found
$ duckdb -c ".help serve_command"
Set the command executed by -serve
Placeholders of the form {parameter|default} are replaced by the -host/-port/-token arguments
source: serve_command = "CALL quack_serve(create_secret_if_not_exists=true{serve_secret\|})"
source: connect_command = "CONNECT '{type\|quack}:'{connect_secret\|}"
P4  direct CONNECT, secret scope, DISCONNECT
$ duckdb -c "CONNECT 'quack:localhost:9499' (TOKEN 'direct_tok'); SELECT * FROM direct_t;"
7
$ duckdb -c "CREATE SECRET (TYPE quack, TOKEN 'direct_tok', SCOPE 'quack:localhost:9499');
             CONNECT 'quack:localhost:9499'; SELECT * FROM direct_t;"
Success true; 7
$ duckdb -c "CREATE SECRET (TYPE quack, TOKEN 'direct_tok', SCOPE 'quack:');
             CONNECT 'quack:localhost:9499';"
Invalid Input Error: Authentication failed
$ duckdb -c "DISCONNECT;"
Invalid Input Error: DISCONNECT: no active CONNECT (already on LOCAL)
$ duckdb -c "ATTACH 'scratch/05/l3.db' AS l; CREATE TABLE l.t AS SELECT 1; CONNECT l;"
Invalid Input Error: Database ""l"" does not support CONNECT
$ duckdb -c "... ATTACH q1; ATTACH q2; CONNECT q1; CONNECT q2;"
Invalid Input Error: Already connected to "q1"; DISCONNECT first before issuing another CONNECT
P5  TLS and key generation
$ duckdb -c "SELECT * FROM quack_generate_keys(directory='scratch/05/keys');"
cert_file=scratch/05/keys/server.pem | key_file=.../private_key.pem | fingerprint=72:A8:...:4C:0E
$ duckdb -c "ATTACH 'quack:localhost:9498' AS q (TOKEN 'tls_token', DISABLE_SSL false);"
IO Error: SSL peer certificate or SSH remote key was not OK
$ duckdb -c "ATTACH ... (TOKEN 'tls_token', DISABLE_SSL false, SSL_FINGERPRINT '72:A8:...:4C:0E'); FROM q.query('SELECT 5');"
5
$ duckdb -c "SELECT quack_uri_parser('quack:remote.com', true);"
{host: remote.com, port: 9494, ipv6: false, ssl: true, url: https://remote.com:9494}
P6  remote filesystem access and lock
$ duckdb -c "FROM quack_query('quack:localhost:9497','SELECT count(*) FROM read_text(''/etc/hosts'')',token='sec_probe_token');"
1
$ duckdb -c "FROM quack_query(...,'COPY (SELECT 42) TO ''scratch/05/remote_write.csv''',...);"
Count 1; -rw-r--r-- scratch/05/remote_write.csv
# after serve: SET enable_external_access=false; SET lock_configuration=true
$ ... read_text('/etc/hosts')
Permission Error: Cannot access file "/etc/hosts" - file system operations are disabled by configuration
$ ... SET enable_external_access=true
Invalid Input Error: Cannot change configuration option ... configuration has been locked
# locking before quack_serve
Cannot access directory "/Users/.../.duckdb/stored_secrets" - file system operations are disabled
P7  bind/token errors
$ CALL quack_serve('quack:0.0.0.0:9499');
Invalid Input Error: Only localhost is allowed as a Quack RPC hostname by default, set allow_other_hostname=true...
$ CALL quack_serve('quack:localhost:9499', token='abc');
Invalid Input Error: Quack server token must be at least 4 characters long
P8  PostgreSQL/MySQL connection strings
$ CONNECT 'postgres:dbname=mydb host=localhost connect_timeout=2';
IO Error: Unable to connect to Postgres at "dbname=mydb host=localhost..." (connection refused)
$ CONNECT 'postgres://localhost/mydb';
IO Error: Cannot open file "postgres://localhost/mydb": No such file or directory
$ ATTACH 'postgres://localhost/mydb' AS pg (TYPE postgres);
IO Error: Unable to connect to Postgres at "postgres://localhost/mydb" (connection refused)
$ CONNECT 'postgres:postgresql://localhost/mydb';
IO Error: Unable to connect to Postgres at "postgresql://localhost/mydb" (connection refused)
$ CONNECT 'mysql:host=localhost port=1 database=mydb';
IO Error: Failed to connect to MySQL ... Can't connect to server
$ CONNECT 'mysql://localhost/mydb';
IO Error: Cannot open file "mysql://localhost/mydb": No such file or directory
P9  extension functions and pools
$ duckdb_functions() after LOAD postgres:
postgres_query[database,sql,use_transaction,params,suppress_dml_output,prepare,query_mode,connection]
postgres_execute[database,sql,use_transaction,params,prepare,query_mode,connection]
(no postgres_scan, no postgres_scan_pushdown)
$ FROM postgres_scan('dbname=x','public','t');
Catalog Error: Table Function with name postgres_scan does not exist!
$ LOAD mysql; mysql_query, mysql_execute, mysql_configure_pool available; mysql_scan absent.
$ SELECT name,value FROM duckdb_settings() WHERE name LIKE 'pg_pool%';
pg_pool_max_connections=12; acquire_mode=force; idle_timeout_millis=60000
$ SELECT name,value FROM duckdb_settings() WHERE name LIKE 'mysql_pool%';
mysql_pool_size=12; acquire_mode=force
P10  extensions
$ INSTALL spatial VERSION 'v1.1.8';       # skipped: already installed
$ FORCE INSTALL spatial FROM core VERSION 'v1.1.8';
HTTP Error ... /spatial/v1.1.8/v2.0.0/osx_arm64/spatial.duckdb_extension.gz (HTTP 404)
$ UPDATE EXTENSIONS;
extension_name | repository | update_result | previous_version | current_version
httpfs | core | NO_UPDATE_AVAILABLE | 77392a7207 | 77392a7207
json | core | NO_UPDATE_AVAILABLE | v2.0.0 | v2.0.0
$ UPDATE EXTENSIONS (httpfs);  -> one row
$ DESCRIBE SELECT * FROM duckdb_extensions();
extension_name, loaded, installed, install_path, description, aliases,
extension_version, install_mode, installed_from, signature_key_fingerprint
install_mode=STATICALLY_LINKED: autocomplete, core_functions, icu, json, parquet, shell
$ SET extension_directory='scratch/05/one';
WARNING: The 'extension_directory' setting is deprecated...
$ SET extension_directories=['scratch/05/a','scratch/05/b'];
[scratch/05/a, scratch/05/b]
$ INSTALL h3 FROM community;  h3 | v1.5.6 | community | REPOSITORY | sha256:b9aa...
$ FORCE INSTALL 'scratch/05/spatial.duckdb_extension.gz'; LOAD spatial; SELECT ST_Point(1,2) IS NOT NULL;
true
$ duckdb_extensions(): spatial | a3dbcd1781 | CUSTOM_PATH | scratch/05/spatial.duckdb_extension.gz
$ FORCE INSTALL httpfs VERSION '77392a7207';
HTTP Error ... /httpfs/77392a7207/v2.0.0/linux_amd64/httpfs.duckdb_extension.gz (HTTP 404)
$ duckdb_settings(): autoinstall_known_extensions=true, autoload_known_extensions=true,
  allow_community_extensions=true, allow_unsigned_extensions=false
P11  extension repository
$ SET allow_extension_repositories='allowed';
$ CREATE EXTENSION REPOSITORY my_repo WITH PREFIX 'scratch/05/repo'
  USING PUBLIC KEY '-----BEGIN PUBLIC KEY-----...';
$ SELECT repository_name,prefix,type,key_fingerprints FROM duckdb_extension_repositories();
my_repo | scratch/05/repo | USER_PROVIDED | ['sha256:8616...']
core | http://extensions.duckdb.org | CORE | NULL
community | http://community-extensions.duckdb.org | COMMUNITY | NULL
$ # reopen another database file: my_repo is still present (global trust store)
$ DROP EXTENSION REPOSITORY my_repo;  -> 0 USER_PROVIDED rows
$ CREATE ... without SET allowed
Permission Error: Adding extension repositories is not enabled...
$ SET allowed; SET undecided;
Invalid Input Error: allow_extension_repositories can only be changed from ...
$ SET extension_repository_directory='scratch/05/repos';
Invalid Input Error: ... can only be set at startup while signature checking is enabled
$ ls ~/.duckdb/extension_repositories
my_repo.duckdb_extension.repo.json
P12  platform HTTP checks
community h3 osx_arm64  200
community h3 osx_amd64  404
core spatial osx_amd64  200
P13  offline install
$ SET extension_directories=['/abs/scratch/05/offline_ext5'];
$ INSTALL '/abs/scratch/05/offline_src/quack.duckdb_extension';
$ LOAD quack; SELECT count(*) FROM quack_server_list();  -> 0
# relative extension dir made dlopen fail on macOS; absolute path worked.
P14  Python install
$ uv venv --python 3.10 scratch/05/py310 && uv pip install duckdb
3.10.21 1.5.6
$ uv venv --python 3.12 scratch/05/uvenv && uv pip install duckdb==2.0.0
2.0.0
$ python -c "import duckdb; print(duckdb.__version__)"  -> 2.0.0
P15  Python relations, fetch removal, DDL
$ con.sql("FROM range(3) t(i)").fetchall() -> [(0,), (1,), (2,)]; repeat same
$ rel.fetchone() -> AttributeError: Relations no longer have fetchone()...
$ rel.fetchmany(1) -> AttributeError ... fetchmany ...
$ rel.execute() -> AttributeError ... execute ...
$ rel.fetch_df_chunk() -> AttributeError ... fetch_df_chunk ...
$ con.execute("SELECT 42").pl/fetch_arrow_table/fetch_record_batch -> absent
$ con.execute(...).to_arrow_table() -> UserWarning: Arrow output on a DB-API result makes an extra copy...
$ con.execute("SELECT * FROM range(5)"); con.sql("SELECT 42").fetchall()
ResourceInUseException: connection has an unfinished result from execute()...
$ con.complete(); con.sql("SELECT 1") -> [(1,)]
$ r = con.sql("INSERT INTO t VALUES (1)"); repr(r) -> Count 1; count stays 1 after print/fetch
P16  Python expressions and relation methods
$ str(col("t.x")) -> "t.x"; str(col("t","x")) -> "t"."x"
$ str(col("s") == "x") -> ("s" = 'x')
$ rel.update(set={"a":"x"}) -> TypeError: update() takes an expression or a Python value ... not the string 'x'
$ con.values({1:"a"}).types -> [MAP(INTEGER, VARCHAR)]
$ con.values({"a":1}).types -> [STRUCT(a INTEGER)]
$ methods: offset/sample/head/rename/pivot/drop/unnest/unpivot/preview/group_by/with_columns -> True
$ pivot -> [(1,2)]; unpivot -> [('a','v',1),('b','v',2)]; unnest -> [(1,),(2,)]; sample(1) -> one row
$ group_by type -> GroupedRelation; preview type -> str
P17  Python Arrow, writes, Decimal
$ to_arrow_table(batch_size=4) -> [4,4,2]; to_arrow_reader(batch_size=2) -> [2,2,1]
$ default 200000 rows -> [131072, 68928]
$ rel.write_csv(p, overwrite=False) -> IOException: ... it exists! Pass overwrite=True
$ rel.write_parquet(p, overwrite=False) -> IOException: ... it exists!
$ con.sql("SELECT ?", params=[Decimal("1E+2")]).types -> DECIMAL(3,0); value 100
$ Decimal("1E-7") -> DECIMAL(8,7)
P18  Python config, read_only, storage, check_same_thread
$ duckdb.connect(config={"threads":2}).sql("SELECT current_setting('threads')") -> 2
$ config memory_limit='1GB' -> 953.6 MiB; temp_directory -> scratch/05/tmp2
$ config={"extension_directories":["scratch/05/ext"]} -> set
$ config={"extension_directory":"scratch/05/ext2"} -> accepted; current_setting('extension_directory') -> scratch/05/ext2; current_setting('extension_directories') -> []
$ c1=RW, c2=RW same file -> INSERT succeeds; c2=read_only=True -> ConnectionException: different configuration
$ duckdb.connect(check_same_thread=False) -> TypeError: connect(): incompatible function arguments
$ config={"check_same_thread":False} -> InvalidInputException: options were not recognized
$ read_only=True: SELECT works; CREATE -> InvalidInputException
$ 2.0 default file opened by 1.5.6:
IOException: version number 69, but we can only read versions between 64 and 68
$ config={"storage_compatibility_version":"v1.5.0"} file opened by 1.5.6 -> [(42,)]
P19  Python tx, threads, default, appender, materialize
$ con.begin(); INSERT; SELECT * FROM missing_table -> CatalogException
$ con.execute("SELECT count(*) FROM t") -> TransactionException: Current transaction is aborted...
$ con.commit() -> ok (rolls back); subsequent rollback -> TransactionException: no transaction is active
$ 4 threads on one connection -> ResourceInUseException
$ duckdb.sql(...) and duckdb.connect(":default:") share table; default_connection() is same
$ con.from_df(df) -> [(1,),(2,)]; from_query("SELECT 7") -> [(7,)]; from_arrow -> [(1,)]
$ with con.appender("ap") as app: append_row / append_rows -> rows written
$ r = con.sql("SELECT count(*) FROM t"); m = r.materialize(); insert -> r=4, m=3
P20  docs and web
https://duckdb.org/quack/faq.html: "Not yet... beta... breaking changes... protocol not yet stable"
https://duckdb.org/2026/08/17/duckdb-20-highlights: preview used CONNECT 'postgres://localhost/mydb'
quack/setup/reverse_proxy.md: nginx 256M, 600s, proxy_buffering off; Caddy flush_interval -1, 256MB
```

## Open questions

- Is direct `CONNECT 'quack:host:port' (TOKEN ...)` a supported public form? It works in 2.0.0 but `sql/statements/connect.md` shows only `CONNECT {attached_database | 'connection_string'}` with no options. The syntax page or release notes would settle whether the option clause is frozen.
- Python `config={"extension_directory": ...}` is deprecated but still effective for the load path; the plural list is the supported form. No further probe needed unless 2.1 removes the alias.
- Why does the 2.0.0 binary lack `postgres_scan`/`postgres_scan_pushdown` while the manual still documents them as deprecated? The extension release notes would settle removal versus documentation lag.
- Does `CREATE EXTENSION REPOSITORY` without `USING PUBLIC KEY` fetch a repository key file at a fixed path? The extension-template repository format is the source of truth; not probed.
- What is the exact boundary of Quack's file access when `enable_external_access=false` but `autoinstall_known_extensions=true`? The locked probe blocked both file access and extension installation; a separate `autoinstall_known_extensions=false` probe would separate the two.
