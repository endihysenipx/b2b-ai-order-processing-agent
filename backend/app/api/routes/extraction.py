from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.services.extraction import (
    AIExtractionError,
    AIExtractionService,
    ExtractedOrder,
    ExtractionConfigurationError,
    ExtractionRequest,
    build_ai_extraction_service,
)

router = APIRouter(prefix="/extraction", tags=["extraction"])


def get_ai_extraction_service() -> AIExtractionService:
    try:
        return build_ai_extraction_service(settings)
    except ExtractionConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/order", response_model=ExtractedOrder)
def extract_order(
    payload: ExtractionRequest,
    _current_user=Depends(get_current_user),
    service: AIExtractionService = Depends(get_ai_extraction_service),
) -> ExtractedOrder:
    try:
        return service.extract_order(
            payload.client_prompt,
            payload.email_content,
            payload.documents,
        )
    except ExtractionConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AIExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
