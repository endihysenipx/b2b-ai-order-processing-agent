import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, clients, documents, emails, extraction, feedback, health, orders, reports
from app.core.config import settings
from app.core.logging import configure_logging
from app.db import base as _models  # noqa: F401
from app.db.session import SessionLocal
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    gmail_task = asyncio.create_task(monitor_gmail()) if settings.gmail_ingestion_enabled else None
    try:
        yield
    finally:
        if gmail_task is not None:
            gmail_task.cancel()
            try:
                await gmail_task
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
    return JSONResponse(status_code=500, content={"detail": "Unexpected server error", "error": str(exc)})


app.include_router(health.router)

api_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(clients.router, prefix=api_prefix)
app.include_router(documents.router, prefix=api_prefix)
app.include_router(emails.router, prefix=api_prefix)
app.include_router(extraction.router, prefix=api_prefix)
app.include_router(orders.router, prefix=api_prefix)
app.include_router(feedback.router, prefix=api_prefix)
app.include_router(reports.router, prefix=api_prefix)
