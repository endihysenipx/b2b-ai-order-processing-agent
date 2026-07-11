from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dependencies import get_current_user
from app.services.email.intake import EmailIntakeParseError, EmailIntakePreview, parse_email_intake
from app.services.email.lutz_parser import LutzEmailParseError, ParsedLutzEmail, parse_lutz_email
from app.services.email.profile_detection import ClientProfile

router = APIRouter(prefix="/emails", tags=["emails"])


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
