from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_system_user
from app.db.session import get_db
from app.models.feedback_issue import FeedbackIssue
from app.schemas.feedback import FeedbackIssueCreate, FeedbackIssueOut

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("", response_model=list[FeedbackIssueOut])
def list_feedback(db: Session = Depends(get_db)) -> list[FeedbackIssue]:
    return list(db.scalars(select(FeedbackIssue).order_by(FeedbackIssue.created_at.desc())))


@router.post("", response_model=FeedbackIssueOut)
def create_feedback(payload: FeedbackIssueCreate, db: Session = Depends(get_db)) -> FeedbackIssue:
    user = get_system_user(db)
    issue = FeedbackIssue(
        order_id=payload.order_id,
        reported_by_user_id=user.id,
        category=payload.category,
        title=payload.title,
        description=payload.description,
        status="Open",
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue
