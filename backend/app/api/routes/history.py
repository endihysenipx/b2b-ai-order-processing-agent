from datetime import UTC, date, datetime, time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import false, func, select
from sqlalchemy.orm import Session

from app.api.dependencies import accessible_client_ids, get_current_user
from app.db.session import get_db
from app.models.audit_event import AuditEvent

router = APIRouter(prefix="/history", tags=["change history"])


class HistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    client_id: str
    client_name: str
    actor_id: str
    actor_name: str
    entity_type: str
    entity_id: str
    entity_label: str
    order_id: str | None
    action: str
    batch_id: str | None
    changes: dict
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc_time(cls, value):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class HistoryResponse(BaseModel):
    items: list[HistoryEntry]
    total: int
    page: int
    page_size: int


@router.get("", response_model=HistoryResponse)
def history(
    client_id: str | None = None,
    entity_type: Literal["customer", "product", "order", "order_item"] | None = None,
    entity_id: str | None = None, order_id: str | None = None,
    actor_id: str | None = None, batch_id: str | None = None,
    actor: str | None = Query(None, max_length=200),
    date_from: date | None = None, date_to: date | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Start date must not be after end date.")
    query = select(AuditEvent)
    allowed = accessible_client_ids(user)
    if allowed is not None:
        query = query.where(AuditEvent.client_id.in_(allowed) if allowed else false())
    if actor:
        query = query.where(func.lower(AuditEvent.actor_name).contains(actor.lower(), autoescape=True))
    for column, value in [(AuditEvent.client_id, client_id), (AuditEvent.entity_type, entity_type),
                          (AuditEvent.entity_id, entity_id), (AuditEvent.order_id, order_id),
                          (AuditEvent.actor_id, actor_id), (AuditEvent.batch_id, batch_id)]:
        if value is not None:
            query = query.where(column == value)
    if date_from:
        query = query.where(AuditEvent.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        # datetime.max avoids overflowing on a valid 9999-12-31 date.
        end = datetime.combine(date_to, time.max)
        query = query.where(AuditEvent.created_at <= end)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = list(db.scalars(query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
                           .offset((page - 1) * page_size).limit(page_size)))
    return HistoryResponse(items=items, total=total, page=page, page_size=page_size)
