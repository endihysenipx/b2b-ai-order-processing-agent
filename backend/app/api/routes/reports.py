from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.reporting.service import get_summary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    return get_summary(db)
