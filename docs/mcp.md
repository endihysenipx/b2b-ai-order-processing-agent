# MCP server

The backend exposes a read-only Model Context Protocol server at `/mcp`. It is a thin adapter over the existing SQLAlchemy repositories and validation service; it does not replace the REST API or provide direct database access.

## Available tools

- `get_daily_briefing`: answer "What orders came in today?" with a timezone-correct workload and value summary.
- `get_attention_queue`: rank blocked, failed, and human-review orders with explicit reasons.
- `get_operations_report`: produce management KPIs by date range, status, client, currency, and exception workload.
- `search_orders`: filter orders by status, client, text, or creation date.
- `get_order_details`: retrieve structured order fields, line items, validation issues, and attachment metadata.
- `get_order_evidence`: retrieve bounded excerpts from the source email and extracted attachment text.
- `get_validation_issues`: compare persisted issues with a fresh, non-mutating validation result.
- `get_processing_summary`: summarize orders, attachment processing, and unresolved validation issues.

## Role-aware experience

- Operators see only orders and metrics for their assigned clients.
- Managers see organization-wide operations and reports, but cannot administer users or trigger ERP actions.
- Administrators retain organization-wide visibility and administrative capabilities in the REST application.

The briefing and reporting tools return `viewer_role` and `access_scope` so the model can explain the scope of its answer instead of implying it saw unauthorized data.

## Amazon presentation demo

Connect an MCP client and try this sequence:

1. "Give me today's order briefing."
2. "What should the operations team work on first, and why?"
3. "Create a management report for the last seven days."
4. "Investigate the highest-priority order and show me the source evidence behind the problem."
5. "Can you approve it and send it to ERP?" The assistant should explain that the MCP is read-only and that a human must confirm consequential actions in the application.

This demonstrates natural-language operations, prioritized exception handling, evidence-backed AI, role boundaries, and human control in one short flow.

Every tool is marked read-only, non-destructive, idempotent, and closed-world. Tool results omit attachment storage paths, S3 object keys, access tokens, and user credentials. Evidence text is truncated to a caller-selected maximum of 200–10,000 characters per source.

## Authentication

The MCP transport accepts both the short-lived, MFA-verified JWT bearer tokens used by Codex and OAuth 2.1 access tokens issued through the browser-based ChatGPT connection. Password authentication alone never produces an access token. The token must belong to an active application user and MCP tools enforce the user's role and client grants.

The hosted flow provides OAuth authorization-server discovery, MCP protected-resource discovery, authorization code with S256 PKCE, ChatGPT Client ID Metadata Document validation, `private_key_jwt` client authentication, one-use authorization codes and client assertions, rotating refresh tokens, and RFC 9207 issuer identification. OAuth access tokens are audience-bound to `/mcp` and are rejected by the REST API.

## Connect ChatGPT Web

The ChatGPT production MCP URL is `https://kolton-unestopped-untransiently.ngrok-free.dev/mcp`. The persistent ngrok service forwards that stable HTTPS origin to the Lightsail reverse proxy; the direct Lightsail IP remains the deployment health-check endpoint. In ChatGPT Developer mode, create an MCP app/connection with the ngrok URL and OAuth authentication. ChatGPT discovers the authorization endpoints automatically. When redirected to FlowForge:

1. Sign in with the normal production account and authenticator or recovery code.
2. Review the read-only permission screen.
3. Select **Allow read-only access**.
4. Return to ChatGPT and test: “Give me today's production order briefing.”

The connection exposes only the eight tools listed above. It does not expose order mutation, approval, email, XML/ERP transmission, deletion, or reprocessing. A ChatGPT connection can be used from the signed-in ChatGPT account after it is created; organization-wide availability requires the workspace administrator's plugin/app publication or approval flow.

## Connect Codex locally

The committed `.codex/config.toml` registers the local MCP URL without containing a credential. Complete authenticator enrollment in the web UI first. Then obtain a login challenge and verify it:

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

$verificationBody = @{
    challenge_token = $login.challenge_token
    code = Read-Host "Authenticator code"
} | ConvertTo-Json

$verified = Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:8000/api/v1/auth/2fa/verify" `
    -ContentType "application/json" `
    -Body $verificationBody

$env:B2B_MCP_TOKEN = $verified.access_token
```

Restart Codex from a terminal that inherits `B2B_MCP_TOKEN`. The project-scoped MCP configuration is loaded only when the repository is trusted. Use `/mcp` or the MCP server settings to confirm that `b2b_order_processing` and its eight tools are available.

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
- Set `FRONTEND_URL` to the stable ngrok HTTPS origin through the protected `.env.ngrok` deployment file. Production Compose also uses it as `PUBLIC_BASE_URL`, which defines the exact OAuth issuer and MCP resource audience.
- Keep `NGROK_AUTHTOKEN` only in the GitHub Actions production secret and the protected server `.env.ngrok` file. Never commit it.
- Keep application JWT signing material and the independent `TOTP_ENCRYPTION_KEY` only in protected server configuration.
- Retain tool invocation logs without logging tokens or raw evidence.
- Review and tune the Nginx MCP rate limit as real usage becomes known.
- Preserve the OAuth discovery, PKCE, ChatGPT signed-client validation, consent, refresh rotation, and MCP-only audience checks when changing authentication.

## Deliberately excluded from version 1

The MCP server cannot update, approve, reject, reprocess, generate XML, email customers, or transmit orders to ERP. Those operations require finer-grained authorization, durable audit records, idempotency controls, and explicit human confirmation before they should be exposed as agent tools.
