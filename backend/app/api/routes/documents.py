from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.services.aws_document_processing import (
    AwsDocumentProcessingError,
    AwsDocumentProcessingService,
    TextractJobResult,
    TextractJobStart,
)

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
