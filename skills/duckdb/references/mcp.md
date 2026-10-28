# MCP reference

Read this when an agent or desktop client must connect to DuckDB over the Model Context Protocol, or when DuckDB must expose tables as MCP resources.

## Two paths

| Path | Use | 2.0 file |
| --- | --- | --- |
| `duckdb_mcp` community extension | Local DuckDB 2.0 server or client | Yes |
| `mcp-server-motherduck` 1.1.0 | MotherDuck cloud or a 1.5.6 local file | No, pins 1.5.6 |

Prefer the extension for a local 2.0 file. The MotherDuck local server cannot open storage 69.

## DuckDB MCP extension

```sql
INSTALL duckdb_mcp FROM community;
LOAD duckdb_mcp;
SELECT mcp_server_start('stdio');
```

Publish a table or a query:

```sql
SELECT mcp_publish_table('products', 'data://tables/products', 'json');
SELECT mcp_publish_query('top_users', 'SELECT * FROM users LIMIT 10', 'Top 10 users', 300);
```

The extension also works as a client:

```sql
ATTACH 'python3' AS data_server (
    TYPE mcp,
    TRANSPORT 'stdio',
    ARGS '["path/to/server.py"]'
);
SELECT * FROM read_csv('mcp://data_server/file:///data.csv');
SELECT mcp_list_resources('data_server');
SELECT mcp_call_tool('data_server', 'process_data', '{"table": "sales"}');
```

The server starts over `stdio` by default. For HTTP, add TLS and authentication in front. Do not expose `0.0.0.0` without them.

## Security

`duckdb_mcp` defaults to deny-all for commands and URLs. Keep `mcp_allow_all_commands = false`. Set `allowed_mcp_commands` to exact executable paths and `allowed_mcp_urls` to URL prefixes when a client needs them.

HTTP origin validation is on by default in 2.4.0. An unlisted browser `Origin` gets 403 before authentication. Use `cors_origins` only for trusted browser clients.

The token is not tenant isolation. A Quack token or MCP client can see every table its DuckDB session can see. Use a separate process and a read-only database for an untrusted client.

## MotherDuck local server

```json
{
  "mcpServers": {
    "DuckDB (read-only)": {
      "command": "uvx",
      "args": [
        "mcp-server-motherduck",
        "--db-path", "/absolute/path/app.duckdb",
        "--read-only",
        "--init-sql", "SET enable_external_access=false; SET lock_configuration=true;"
      ]
    }
  }
}
```

The server is version 1.1.0 and requires `duckdb==1.5.6`. Its read-only mode is not a filesystem sandbox; add the init SQL above, or use the extension on a 2.0 binary.

## Verify

```bash
duckdb -no-agent -c "
INSTALL duckdb_mcp FROM community;
LOAD duckdb_mcp;
SELECT extension_name, extension_version FROM duckdb_extensions()
WHERE extension_name = 'duckdb_mcp';
SELECT mcp_server_status();
"
```

The version must be 2.4.0 or newer on a 2.0 binary. `mcp_server_status()` must return a row. Start a server only in a process that stays alive.

## References

- https://duckdb.org/community_extensions/extensions/duckdb_mcp
- https://github.com/teaguesterling/duckdb_mcp/releases/tag/v2.4.0
- https://github.com/motherduckdb/mcp-server-motherduck
- https://pypi.org/project/mcp-server-motherduck/1.1.0/
- https://duckdb.org/docs/2.0/operations_manual/securing_duckdb/overview.html
- https://duckdb.org/quack/security.html
