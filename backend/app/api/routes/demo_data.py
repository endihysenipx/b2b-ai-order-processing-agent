import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.db.session import get_db
from app.models.user import User
from app.services.demo_data import DemoDataStatus, delete_demo_data, generate_demo_data, get_demo_data_status

router = APIRouter(prefix="/demo-data", tags=["demo data"])
logger = logging.getLogger(__name__)


class DeleteDemoDataRequest(BaseModel):
    confirmation: Literal["DELETE DEMO DATA"]


@router.get("", response_model=DemoDataStatus)
def status(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> DemoDataStatus:
    return get_demo_data_status(db)


@router.post("", response_model=DemoDataStatus)
def generate(db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> DemoDataStatus:
    result = generate_demo_data(db, admin)
    logger.info("Demo data generation requested by user_id=%s; order_count=%s", admin.id, result.order_count)
    return result


@router.delete("", response_model=DemoDataStatus)
def remove(
    payload: DeleteDemoDataRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> DemoDataStatus:
    if payload.confirmation != "DELETE DEMO DATA":
        raise HTTPException(status_code=400, detail="Exact confirmation is required")
    result = delete_demo_data(db)
    logger.info("Demo data deletion requested by user_id=%s", admin.id)
    return result
