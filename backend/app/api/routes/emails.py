import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dependencies import get_current_user, require_admin
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.email.gmail import GmailConfigurationError, GmailConnectionError
from app.services.email.ingestion import (
    GmailIngestionService,
    GmailIngestionStatus,
    GmailPollResult,
    OrderIntelligenceResult,
)
from app.services.email.intake import EmailIntakeParseError, EmailIntakePreview, parse_email_intake
from app.services.email.lutz_parser import LutzEmailParseError, ParsedLutzEmail, parse_lutz_email
from app.services.email.profile_detection import ClientProfile

router = APIRouter(prefix="/emails", tags=["emails"])
logger = logging.getLogger(__name__)
MAX_EMAIL_UPLOAD_BYTES = 10 * 1024 * 1024


def get_gmail_ingestion_service() -> GmailIngestionService:
    return GmailIngestionService(settings, SessionLocal)


@router.get("/gmail/status", response_model=GmailIngestionStatus)
def gmail_status(
    _current_user=Depends(require_admin),
    service: GmailIngestionService = Depends(get_gmail_ingestion_service),
) -> GmailIngestionStatus:
    return service.status()


@router.post("/gmail/poll", response_model=GmailPollResult)
async def poll_gmail(
    _current_user=Depends(require_admin),
    service: GmailIngestionService = Depends(get_gmail_ingestion_service),
) -> GmailPollResult:
    try:
        return await asyncio.to_thread(service.poll_once)
    except GmailConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except GmailConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/preview", response_model=EmailIntakePreview)
async def preview_email(
    file: Annotated[UploadFile, File(description="An .eml email to preview with automatic client detection")],
    client_profile: ClientProfile | None = None,
    _current_user=Depends(get_current_user),
) -> EmailIntakePreview:
    if not (file.filename or "").casefold().endswith(".eml"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload an .eml email file.")

    try:
        return parse_email_intake(await file.read(), client_profile)
    except EmailIntakeParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/intelligence/import", response_model=OrderIntelligenceResult)
async def import_email_for_intelligence(
    file: Annotated[UploadFile, File(description="An RFC 822 .eml purchase-order message")],
    current_user=Depends(require_admin),
    service: GmailIngestionService = Depends(get_gmail_ingestion_service),
) -> OrderIntelligenceResult:
    if not (file.filename or "").casefold().endswith(".eml"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload an .eml email file.")
    content = await file.read(MAX_EMAIL_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded email is empty.")
    if len(content) > MAX_EMAIL_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The email exceeds the 10 MB limit.")

    result = await asyncio.to_thread(service.import_uploaded_message, content)
    logger.info(
        "Order Intelligence upload imported: user_id=%s email_id=%s orders=%s duplicate=%s",
        current_user.id,
        result.email_id,
        len(result.orders),
        result.duplicate,
    )
    return result


@router.post("/lutz-preview", response_model=ParsedLutzEmail)
async def preview_lutz_email(
    file: Annotated[UploadFile, File(description="A Lutz .eml purchase-order email")],
    _current_user=Depends(get_current_user),
) -> ParsedLutzEmail:
    if not (file.filename or "").casefold().endswith(".eml"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload an .eml email file.")

    try:
        return parse_lutz_email(await file.read())
    except LutzEmailParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
