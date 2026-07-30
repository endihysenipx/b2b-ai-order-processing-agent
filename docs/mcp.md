# MCP server

The backend exposes a read-only Model Context Protocol server at `/mcp`. It is a thin adapter over the existing SQLAlchemy repositories and validation service; it does not replace the REST API or provide direct database access.

## Available tools

- `search_orders`: filter orders by status, client, text, or creation date.
- `get_order_details`: retrieve structured order fields, line items, validation issues, and attachment metadata.
- `get_order_evidence`: retrieve bounded excerpts from the source email and extracted attachment text.
- `get_validation_issues`: compare persisted issues with a fresh, non-mutating validation result.
- `get_processing_summary`: summarize orders, attachment processing, and unresolved validation issues.

Every tool is marked read-only, non-destructive, idempotent, and closed-world. Tool results omit attachment storage paths, S3 object keys, access tokens, and user credentials. Evidence text is truncated to a caller-selected maximum of 200–10,000 characters per source.

## Authentication

The MCP transport accepts the same short-lived JWT bearer tokens issued by `POST /api/v1/auth/login`. The token must belong to an active application user. This initial authentication model works well for local development and private clients such as Codex.

The server does not yet advertise an OAuth authorization flow. Add OAuth 2.1 and MCP protected-resource discovery before publishing this endpoint as a broadly available ChatGPT or third-party integration. Do not replace bearer authentication with an unauthenticated public endpoint.

## Connect Codex locally

The committed `.codex/config.toml` registers the local MCP URL without containing a credential. Start the application and obtain a login token:

```powershell
$loginBody = @{
    email = "admin@example.com"
    password = "your-local-password"
} | ConvertTo-Json

$login = Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:8000/api/v1/auth/login" `
    -ContentType "application/json" `
    -Body $loginBody

$env:B2B_MCP_TOKEN = $login.access_token
```

Restart Codex from a terminal that inherits `B2B_MCP_TOKEN`. The project-scoped MCP configuration is loaded only when the repository is trusted. Use `/mcp` or the MCP server settings to confirm that `b2b_order_processing` and its five tools are available.

JWTs expire according to `ACCESS_TOKEN_EXPIRE_MINUTES`. Repeat the login step and restart or refresh the MCP connection when the token expires. Never write the token into `.codex/config.toml`, `.env.example`, source code, or documentation.

To connect a different MCP-compatible client, configure:

- Transport: Streamable HTTP
- URL: `http://localhost:8000/mcp` locally or `https://<production-host>/mcp` in production
- Authorization: `Bearer <application-JWT>`

## Inspect and test

Run the backend tests:

```bash
cd backend
ruff check .
pytest
```

For interactive protocol inspection:

```bash
npx -y @modelcontextprotocol/inspector
```

Connect the Inspector to `http://localhost:8000/mcp` and supply an active bearer token. Verify initialization, tool schemas, representative calls, invalid inputs, and authorization failure before deployment.

## Production deployment

Both frontend Nginx configurations proxy the exact `/mcp` path to the backend, preserve the `Authorization` header, disable response buffering, use extended MCP timeouts, and enforce a per-IP request limit. The existing GitHub Actions workflow builds and deploys these changes to Lightsail after backend and frontend CI pass.

Production requirements:

- Keep `/mcp` behind HTTPS.
- Set `FRONTEND_URL` to the public HTTPS origin; the MCP transport derives its Host and Origin allowlist from this setting.
- Keep application JWT signing material only in protected server configuration.
- Retain tool invocation logs without logging tokens or raw evidence.
- Review and tune the Nginx MCP rate limit as real usage becomes known.
- Add OAuth 2.1 before connecting hosted ChatGPT plugins or external customer workspaces.

## Deliberately excluded from version 1

The MCP server cannot update, approve, reject, reprocess, generate XML, email customers, or transmit orders to ERP. Those operations require finer-grained authorization, durable audit records, idempotency controls, and explicit human confirmation before they should be exposed as agent tools.
