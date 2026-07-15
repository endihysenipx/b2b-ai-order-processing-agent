from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.services.aws_document_processing import (
    AwsDocumentProcessingError,
    AwsDocumentProcessingService,
    LesninaEmailMapping,
    LesninaOrderMapping,
    LesninaTableMapper,
    TextractJobResult,
    TextractJobStart,
)
from app.services.email.intake import EmailIntakeParseError, EmailMessageType, parse_email_intake
from app.services.email.profile_detection import ClientProfile

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_DOCUMENT_BYTES = 50 * 1024 * 1024


def get_aws_document_processing_service() -> AwsDocumentProcessingService:
    return AwsDocumentProcessingService(settings)


@router.post("/textract/jobs", response_model=TextractJobStart, status_code=status.HTTP_202_ACCEPTED)
async def start_textract_job(
    file: Annotated[UploadFile, File(description="A PDF or multipage TIFF document")],
    _current_user=Depends(get_current_user),
    service: AwsDocumentProcessingService = Depends(get_aws_document_processing_service),
) -> TextractJobStart:
    content = await file.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Document exceeds the 50 MB pilot limit.")
    try:
        return service.start_table_analysis(file.filename or "document", content)
    except AwsDocumentProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/textract/jobs/{job_id}", response_model=TextractJobResult)
def get_textract_job(
    job_id: str,
    _current_user=Depends(get_current_user),
    service: AwsDocumentProcessingService = Depends(get_aws_document_processing_service),
) -> TextractJobResult:
    try:
        return service.get_table_analysis(job_id)
    except AwsDocumentProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/textract/jobs/{job_id}/lesnina-order", response_model=LesninaOrderMapping)
async def map_lesnina_order(
    job_id: str,
    email_file: Annotated[UploadFile, File(description="The original Lesnina .eml email")],
    _current_user=Depends(get_current_user),
    service: AwsDocumentProcessingService = Depends(get_aws_document_processing_service),
) -> LesninaOrderMapping:
    if not (email_file.filename or "").casefold().endswith(".eml"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload the original .eml email file.")
    try:
        preview = parse_email_intake(await email_file.read())
        result = service.get_table_analysis(job_id)
    except (EmailIntakeParseError, AwsDocumentProcessingError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if preview.client_profile is not ClientProfile.LESNINA or preview.message_type is not EmailMessageType.ORDER:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The email is not a detected Lesnina order.")
    if len(preview.orders) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Automatic merge currently requires exactly one commission block in the email.",
        )
    if result.status != "SUCCEEDED" or result.lesnina_mapping is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Textract job is not ready; current status is {result.status}.")
    return LesninaTableMapper.merge_order(preview.orders[0], result.lesnina_mapping)


@router.post("/textract/jobs/{job_id}/lesnina-orders", response_model=LesninaEmailMapping)
async def map_lesnina_orders(
    job_id: str,
    email_file: Annotated[UploadFile, File(description="The original Lesnina .eml email")],
    _current_user=Depends(get_current_user),
    service: AwsDocumentProcessingService = Depends(get_aws_document_processing_service),
) -> LesninaEmailMapping:
    if not (email_file.filename or "").casefold().endswith(".eml"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload the original .eml email file.")
    try:
        preview = parse_email_intake(await email_file.read())
        result = service.get_table_analysis(job_id)
    except (EmailIntakeParseError, AwsDocumentProcessingError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if preview.client_profile is not ClientProfile.LESNINA or preview.message_type is not EmailMessageType.ORDER:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The email is not a detected Lesnina order.")
    if result.status != "SUCCEEDED" or result.lesnina_mapping is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Textract job is not ready; current status is {result.status}.")
    return LesninaTableMapper.merge_email_orders(preview.orders, result.lesnina_mapping)
