from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, clients, feedback, health, orders, reports
from app.core.config import settings
from app.core.logging import configure_logging
from app.db import base as _models  # noqa: F401

configure_logging()

app = FastAPI(title="B2B AI Order Processing Agent", version="0.3.0")

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
app.include_router(orders.router, prefix=api_prefix)
app.include_router(feedback.router, prefix=api_prefix)
app.include_router(reports.router, prefix=api_prefix)
