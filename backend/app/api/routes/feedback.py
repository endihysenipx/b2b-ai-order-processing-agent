from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import accessible_client_ids, get_current_user
from app.db.session import get_db
from app.models.feedback_issue import FeedbackIssue
from app.models.order import Order
from app.repositories.orders import get_order
from app.schemas.feedback import FeedbackIssueCreate, FeedbackIssueOut

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("", response_model=list[FeedbackIssueOut])
def list_feedback(db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> list[FeedbackIssue]:
    query = select(FeedbackIssue).outerjoin(Order, FeedbackIssue.order_id == Order.id)
    allowed = accessible_client_ids(current_user)
    if allowed is not None:
        order_access = Order.client_id.in_(allowed) if allowed else false()
        query = query.where(or_(FeedbackIssue.reported_by_user_id == current_user.id, order_access))
    return list(db.scalars(query.order_by(FeedbackIssue.created_at.desc())))


@router.post("", response_model=FeedbackIssueOut)
def create_feedback(
    payload: FeedbackIssueCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> FeedbackIssue:
    if payload.order_id and get_order(db, payload.order_id, accessible_client_ids(current_user)) is None:
        raise HTTPException(status_code=404, detail="Order not found")
    issue = FeedbackIssue(
        order_id=payload.order_id,
        reported_by_user_id=current_user.id,
        category=payload.category,
        title=payload.title,
        description=payload.description,
        status="Open",
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue
