from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.notification_read import NotificationRead
from app.models.user import User
from app.services.notifications import current_notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])


class ReadUpdate(BaseModel):
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    is_read: bool = True


@router.get("")
def list_notifications(category: Literal["failed", "duplicate", "waiting", "review"] | None = None,
                       unread_only: bool = False, include_demo: bool = False,
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    items = current_notifications(db, user, include_demo=include_demo)
    unread_count = sum(not item["is_read"] for item in items)
    items = [item for item in items if (not category or item["category"] == category)
             and (not unread_only or not item["is_read"])]
    start = (page - 1) * page_size
    return {"items": items[start:start + page_size], "total": len(items), "unread_count": unread_count,
            "page": page, "page_size": page_size}


@router.put("/{order_id}/read")
def mark_read(order_id: str, payload: ReadUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Serialize two browser tabs acknowledging the same user's inbox.
    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    items = current_notifications(db, user, include_demo=True, order_id=order_id)
    if not items:
        raise HTTPException(404, "Notification not found")
    if items[0]["fingerprint"] != payload.fingerprint:
        raise HTTPException(409, "The order changed. Refresh notifications before marking it read.")
    state = db.get(NotificationRead, (user.id, order_id))
    if state is None:
        state = NotificationRead(user_id=user.id, order_id=order_id)
        db.add(state)
    state.fingerprint, state.is_read = payload.fingerprint, payload.is_read
    state.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return {"is_read": state.is_read}
