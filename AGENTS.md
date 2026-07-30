# Repository Guidance

## Production and deployment context

- The application is hosted on Amazon Lightsail.
- Production runs with `docker-compose.prod.yml`.
- GitHub Actions is the deployment path; `.github/workflows/ci.yml` deploys successful pushes to `main` after the backend and frontend jobs pass.
- The production workflow connects to Lightsail over SSH, fast-forwards the server checkout, rebuilds the Compose services, verifies the HTTPS `/health` endpoint, and rolls back when deployment or health verification fails.
- Treat changes to `.github/workflows/ci.yml`, `docker-compose.prod.yml`, frontend Nginx configuration, health checks, certificates, ports, volumes, and production environment variables as production-sensitive.
- Never commit credentials, private keys, `.env` contents, access tokens, or customer/order data. Keep production secrets in GitHub Actions secrets and the server's protected environment configuration.
- Do not bypass the GitHub Actions deployment path or make direct production/Lightsail changes unless the user explicitly requests it.
- Before changing deployment behavior, preserve the existing CI gates, deployment concurrency lock, strict SSH host verification, health verification, and rollback behavior.

## Development and verification

- Keep local and production configuration compatible with the existing FastAPI, React, PostgreSQL, and Docker Compose architecture.
- Run relevant backend checks from `backend`: `ruff check .` and `pytest`.
- Run relevant frontend checks from `frontend`: `npm run lint`, `npm test -- --run`, and `npm run build`.
- When a change affects deployment or service wiring, also validate the rendered production Compose configuration with `docker compose -f docker-compose.prod.yml config`.

## MCP and agent integrations

- If MCP support is added, implement it as a thin server-side adapter over the existing FastAPI service/repository layer; do not replace the REST API or give agents direct database access.
- Keep the production MCP endpoint behind HTTPS and the existing reverse proxy/deployment architecture.
- Start with narrowly scoped, read-only order tools. Enforce authentication, authorization, tenant/client boundaries, input validation, rate limits, and audit logging in server code.
- Require explicit user confirmation for consequential actions such as order approval, email sending, XML/ERP transmission, deletion, or reprocessing that incurs external cost.
- Never expose secrets, raw credentials, or unnecessary customer data in MCP tool metadata or results.
