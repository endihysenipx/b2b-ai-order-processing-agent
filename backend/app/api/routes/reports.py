from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import accessible_client_ids, get_current_user
from app.db.session import get_db
from app.services.reporting.service import get_summary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> dict:
    return get_summary(db, accessible_client_ids(current_user))
