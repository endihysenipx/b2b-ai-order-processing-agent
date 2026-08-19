import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.handlers.register import RegistrationHandler
from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.settings import ClientRegistrationOptions

from app.api.dependencies import get_current_user
from app.api.routes import auth, clients, documents, emails, extraction, feedback, health, oauth, orders, reports, users
from app.core.config import settings
from app.core.logging import configure_logging
from app.db import base as _models  # noqa: F401
from app.db.session import SessionLocal
from app.mcp.server import http_app as mcp_http_app
from app.mcp.server import lifespan_app as mcp_lifespan_app
from app.oauth.provider import oauth_client_authenticator, oauth_provider
from app.services.aws_document_processing import TextractJobProcessor
from app.services.email.ingestion import GmailIngestionService

configure_logging()

logger = logging.getLogger(__name__)


async def monitor_gmail() -> None:
    service = GmailIngestionService(settings, SessionLocal)
    while True:
        try:
            result = await asyncio.to_thread(service.poll_once)
            if result.fetched:
                logger.info(
                    "Gmail poll completed: fetched=%s imported=%s duplicates=%s failed=%s",
                    result.fetched,
                    result.imported,
                    result.duplicates,
                    result.failed,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Gmail polling failed; the next scheduled poll will retry")
        await asyncio.sleep(settings.gmail_poll_interval_seconds)


async def monitor_textract() -> None:
    processor = TextractJobProcessor(settings, SessionLocal)
    while True:
        try:
            summary = await asyncio.to_thread(processor.poll_once)
            if summary.checked or summary.mapped_items:
                logger.info(
                    "Textract poll completed: checked=%s completed=%s in_progress=%s failed=%s mapped_items=%s",
                    summary.checked,
                    summary.completed,
                    summary.in_progress,
                    summary.failed,
                    summary.mapped_items,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Textract polling failed; the next scheduled poll will retry")
        await asyncio.sleep(settings.textract_poll_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    gmail_task = asyncio.create_task(monitor_gmail()) if settings.gmail_ingestion_enabled else None
    textract_task = asyncio.create_task(monitor_textract()) if settings.textract_auto_processing_enabled else None
    try:
        async with mcp_lifespan_app.router.lifespan_context(mcp_lifespan_app):
            yield
    finally:
        tasks = [task for task in (gmail_task, textract_task) if task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="B2B AI Order Processing Agent", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception):
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Unexpected server error"})


app.include_router(health.router)

api_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(oauth.router, prefix=api_prefix)
protected = [Depends(get_current_user)]
app.include_router(clients.router, prefix=api_prefix, dependencies=protected)
app.include_router(documents.router, prefix=api_prefix, dependencies=protected)
app.include_router(emails.router, prefix=api_prefix, dependencies=protected)
app.include_router(extraction.router, prefix=api_prefix, dependencies=protected)
app.include_router(orders.router, prefix=api_prefix, dependencies=protected)
app.include_router(feedback.router, prefix=api_prefix, dependencies=protected)
app.include_router(reports.router, prefix=api_prefix, dependencies=protected)
app.include_router(users.router, prefix=api_prefix, dependencies=protected)


@app.get("/.well-known/oauth-authorization-server", include_in_schema=False)
def oauth_authorization_server_metadata():
    issuer = settings.oauth_issuer_url
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/authorize",
        "token_endpoint": f"{issuer}/token",
        "registration_endpoint": f"{issuer}/register",
        "scopes_supported": ["orders:read"],
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["private_key_jwt", "none"],
        "token_endpoint_auth_signing_alg_values_supported": ["RS256"],
        "code_challenge_methods_supported": ["S256"],
        "client_id_metadata_document_supported": True,
        "authorization_response_iss_parameter_supported": True,
        "service_documentation": f"{issuer}/docs",
    }


app.add_route("/authorize", AuthorizationHandler(oauth_provider).handle, methods=["GET", "POST"])
app.add_route(
    "/register",
    RegistrationHandler(
        oauth_provider,
        ClientRegistrationOptions(enabled=True, valid_scopes=["orders:read"], default_scopes=["orders:read"]),
    ).handle,
    methods=["POST"],
)
app.add_route(
    "/token",
    TokenHandler(oauth_provider, oauth_client_authenticator).handle,
    methods=["POST"],
)

# Mount last so the MCP transport handles /mcp while the FastAPI routes above
# retain precedence for the REST API, health endpoint, and documentation.
app.mount("", mcp_http_app, name="mcp")
