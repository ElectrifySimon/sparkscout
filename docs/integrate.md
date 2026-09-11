# Integrate your AI assistant with SparkScout

SparkScout speaks the Model Context Protocol (MCP) over HTTP. Any MCP-aware client can connect by pointing at one of the service URLs and sending a bearer token in the `Authorization` header. This document is the copy-pasteable reference: pick the client you use, paste the block, restart the client, and the twelve corpus tools are available.

The transport is **Streamable HTTP** (the MCP 2025-03-26 transport). Legacy HTTP+SSE clients are not supported. Bearer authentication is the only authentication method. OAuth is not in scope.

## TL;DR

Three URLs, one header, one restart per client. Replace the placeholder token with the one the operator gave you, paste the block into the client config file the table in the section below points at, and restart the client.

| Path | URL | When to use it |
|---|---|---|
| Tailnet | `https://<host>.ts.net/sparkscout` | You are on the operator's tailnet. Preferred when reachable. |
| Funnel (public) | `https://<host>.funnel.ts.net/sparkscout` | You are not on the tailnet but the operator has enabled the public Funnel path. Same bearer as the tailnet path. |
| Local-direct | `http://127.0.0.1:7100/mcp` | You are running a client on the same host as the SparkScout container. No bearer required. |

The bearer token is the same across the tailnet and the Funnel paths. The local-direct path is on the host's loopback and does not require authentication.

## Authentication

All HTTP paths accept a single bearer token in the `Authorization` header. The header shape is the standard RFC 6750 form:

```
Authorization: Bearer <token>
```

The token is operator-issued, scoped to the service, and rotatable on request. Treat it like an API key. Do not commit it to a repository, do not paste it in a chat log where it can be scraped, do not include it in screenshots. The recommended pattern is to read the token from an environment variable on the client machine and interpolate it at config-load time.

If the bearer is missing or wrong, the service returns `401 Unauthorized` with a JSON body of `{"error": "invalid_token"}`. The client's tools panel will show zero tools and the tool calls will fail. The fix is to verify the header value matches the operator's last-issued token.

## Client configurations

Pick the client that matches your setup. Each block is a complete, copy-pasteable config fragment. The token placeholder `<SPARKSCOUT_TOKEN>` is replaced by either the literal token (if you trust the file) or an environment variable reference if the client supports it.

### Claude Desktop (Custom Connector, no config file needed)

Claude Desktop since version 0.10 supports remote MCP servers through a Custom Connector, which avoids the stdio-only limitation of the legacy `claude_desktop_config.json` approach. To connect:

1. Open Claude Desktop.
2. Go to **Settings → Connectors → Add custom connector**.
3. For **Name**, type `SparkScout`.
4. For **URL**, paste the tailnet or Funnel URL from the table above.
5. Click **Add**. Claude Desktop opens a browser tab to authenticate.
6. Paste the bearer token when prompted. Claude Desktop stores the token in the system keychain.

This is the recommended path for Claude Desktop because it does not require editing JSON, it works with bearer auth out of the box, and it keeps the token out of plain-text config files. No restart is needed; the connector is live as soon as you click Add.

### Claude Desktop (legacy `claude_desktop_config.json` with `mcp-remote` bridge)

If the Custom Connector path is unavailable on your Claude Desktop version, fall back to the stdio-bridge path. The bridge runs `mcp-remote` as a local subprocess that translates between stdio (what Claude Desktop's `claude_desktop_config.json` accepts) and the remote HTTP server.

On macOS, the config file is at `~/Library/Application Support/Claude/claude_desktop_config.json`. On Windows, `%APPDATA%\Claude\claude_desktop_config.json`. On Linux, `~/.config/Claude/claude_desktop_config.json`. Create the file if it does not exist.

```json
{
  "mcpServers": {
    "sparkscout": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://<host>.ts.net/sparkscout/mcp",
        "--header",
        "Authorization: Bearer ${SPARKSCOUT_TOKEN}"
      ]
    }
  }
}
```

Set the environment variable `SPARKSCOUT_TOKEN` in the shell that launches Claude Desktop, or substitute the literal token. Restart Claude Desktop. The twelve corpus tools appear in the tools panel.

### Claude Code (terminal)

Claude Code uses `.mcp.json` at the project root, or `~/.claude/mcp.json` for the user scope, with the same shape as the legacy `claude_desktop_config.json` but with a flatter key:

```json
{
  "mcpServers": {
    "sparkscout": {
      "type": "http",
      "url": "https://<host>.ts.net/sparkscout/mcp",
      "headers": {
        "Authorization": "Bearer ${SPARKSCOUT_TOKEN}"
      }
    }
  }
}
```

Or use the CLI equivalent: `claude mcp add --transport http sparkscout https://<host>.ts.net/sparkscout/mcp --header "Authorization: Bearer $SPARKSCOUT_TOKEN"`. The CLI form is preferred because it sets the scope and persists the config without a restart.

### Cursor (`.cursor/mcp.json`)

Cursor supports remote HTTP servers natively with the `url` and `headers` keys. Per-project config goes at `<project>/.cursor/mcp.json`; per-user config at `~/.cursor/mcp.json`. The per-project form is preferred for reproducible team setups.

```json
{
  "mcpServers": {
    "sparkscout": {
      "url": "https://<host>.ts.net/sparkscout/mcp",
      "headers": {
        "Authorization": "Bearer ${env:SPARKSCOUT_TOKEN}"
      }
    }
  }
}
```

Cursor's `${env:NAME}` interpolation resolves at config-load time, so the literal token is never written to disk. Restart Cursor after editing the file. The MCP server appears under **Settings → Models → MCP Servers**.

If you prefer the per-user form, replace `.cursor/mcp.json` with `~/.cursor/mcp.json` in the path above. The JSON body is identical.

### Cline (`cline_mcp_settings.json` or `.vscode/mcp.json`)

Cline uses the same shape as Cursor. The legacy path is `cline_mcp_settings.json`; the modern path (recommended, Cline 3.10+) is `.vscode/mcp.json` in your project root. Pick one and stick with it; Cline will read both, but the modern path is the one that survives VS Code workspace moves.

```json
{
  "mcpServers": {
    "sparkscout": {
      "url": "https://<host>.ts.net/sparkscout/mcp",
      "headers": {
        "Authorization": "Bearer ${env:SPARKSCOUT_TOKEN}"
      },
      "disabled": false
    }
  }
}
```

In VS Code, open the Cline panel, click the **MCP Servers** icon, and the new server appears in the list. Cline reads the file on every panel open, so a restart of VS Code is not required, just a panel refresh.

### Continue (`~/.continue/config.yaml`)

Continue uses YAML, not JSON, and exposes the same `mcpServers` key. Place the file at `~/.continue/config.yaml`. Continue reads it on every IDE open; restart the IDE to pick up changes.

```yaml
mcpServers:
  - name: sparkscout
    type: streamable-http
    url: https://<host>.ts.net/sparkscout/mcp
    headers:
      Authorization: Bearer ${env:SPARKSCOUT_TOKEN}
```

Continue supports `${env:NAME}` interpolation as of 1.0. For older versions, substitute the literal token or use a wrapper script.

### Other MCP-aware clients (Zed, Windsurf, custom)

The pattern is the same across all compliant clients: a `url` field pointing at the Streamable HTTP endpoint, a `headers` object with `Authorization: Bearer ***, and a transport type of `streamable-http` or `http`. If the client does not support the Streamable HTTP transport, fall back to the `mcp-remote` stdio bridge as in the Claude Desktop legacy section.

## Direct API access (curl, scripts, your own client)

For ad-hoc testing or for a custom client you are writing, the protocol is standard MCP-over-HTTP. A minimal `tools/list` call from a shell:

```bash
curl -sS -X POST https://<host>.ts.net/sparkscout/mcp \
  -H "Authorization: Bearer $SPARKSCOUT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

The response is a JSON-RPC envelope containing the twelve tools. To call a tool, send `{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"irena_query_dataset","arguments":{"dataset_id":"country_capacity","filters":{"countries":["BRA"],"technologies":["Solar PV"],"years":[2024]},"limit":10}}}`. The `name` field is the Python function name as registered by the FastMCP server (the `irena_*` prefix); the public URL path (`/sparkscout/mcp`) is the same as before, only the tool names changed when the server moved to FastMCP 4.0.

The same two headers (`Authorization` and `Content-Type: application/json`) plus the MCP-required `Accept: application/json, text/event-stream` header are sufficient for every operation. No additional headers are required. No cookies. No CSRF token. No state.

## Verification

The single command that proves the integration is live:

```bash
curl -fsS -X POST https://<host>.ts.net/sparkscout/mcp \
  -H "Authorization: Bearer $SPARKSCOUT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python3 -c 'import sys, json; d=json.load(sys.stdin); print(len(d["result"]["tools"]), "tools:", [t["name"] for t in d["result"]["tools"]])'
```

Expected output: `12 tools: ['irena_answer_question', 'irena_cite', 'irena_embed_health', 'irena_get_dataset_meta', 'irena_get_dataset_value', 'irena_get_report', 'irena_list_datasets', 'irena_list_reports', 'irena_query_dataset', 'irena_query_dataset_aggregations', 'irena_sample_dataset', 'irena_search_reports']` (the list of names will grow as new data sources are added). A count of 0 or a 401 means the bearer is wrong; a count that does not include the names above means the server is up but returning a cached or stale schema, which means a restart is in progress on the operator side.

## Common failures

- **401 Unauthorized, `{"error": "invalid_token"}`**: the bearer is wrong, missing, or rotated. Get the current token from the operator and retry.
- **Connection refused**: you are pointing at the wrong URL. If the operator is on a tailnet, you need to be on the tailnet to reach `<host>.ts.net`. If you are not on the tailnet, use the Funnel URL.
- **The MCP server appears in the client but all tool calls fail with `tool not found`**: the client is caching a stale schema from a previous connection. Restart the client (not the server) to force a fresh `tools/list`.
- **The client silently strips the `url` field on save**: you are on a client that does not support the Streamable HTTP transport yet. Use the `mcp-remote` stdio-bridge fallback described in the Claude Desktop legacy section.
- **`mcp-remote` exits immediately with a parse error**: the `Authorization: Bearer ***` value contains a shell-special character (most often `$`). Wrap the value in single quotes when exporting it as an environment variable, or write the literal token directly into the args array.
- **Tools work in `tools/list` but `tools/call` returns a 500**: the client is missing the `Accept: application/json, text/event-stream` header. Most MCP clients set this automatically; some custom curl-based clients do not. Add the header and retry.

## Token rotation

The bearer token rotates on operator request. The old token is invalidated, the new one is delivered through the operator's preferred channel, and the integration's `Authorization` header is updated to the new value. No client restart is required for a token rotation, only a config-file edit. Clients that read the token from an environment variable need only the env var updated and a client restart to clear the in-memory cache.

If the rotation is urgent (token leak), the operator can invalidate the old token without warning, and the service returns 401 to all integrations using the old value until they update. Plan for this when deciding where to store the token: a file that requires a code change to update is slower to recover than an environment variable that requires only a shell restart.

## What this document does not cover

OAuth 2.1 flows. The service does not implement OAuth; the bearer is the only authentication method, period. If your client requires OAuth and cannot consume a static bearer, you cannot use SparkScout as-is. The service does not implement API key rotation hooks (the operator rotates the bearer; the service does not call back to a key-management system). The service does not implement per-tool authorization (every authenticated client has the same twelve tools, no scoping). The service does not implement rate limiting at the bearer level (rate limits, if any, are global). If any of those become requirements, the answer is a new release of the service, not a workaround in the client.
