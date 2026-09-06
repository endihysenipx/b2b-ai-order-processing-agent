"""Current attention inbox; read acknowledgements never mutate orders."""

import hashlib
import json
from datetime import UTC

from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased, joinedload, selectinload

from app.api.dependencies import accessible_client_ids
from app.models.attachment import Attachment
from app.models.notification_read import NotificationRead
from app.models.order import Order
from app.services.validation.duplicates import duplicate_orders

TITLES = {"failed": "Processing failed", "duplicate": "Possible duplicate order",
          "waiting": "Customer information needed", "review": "Order needs review"}
MESSAGES = {
    "failed": "Review the processing failure and source documents before retrying.",
    "duplicate": "Compare matching customer PO references before approval or export.",
    "waiting": "Review missing details and prepare a customer clarification draft.",
    "review": "Review validation findings and correct the order before processing.",
}


def current_notifications(db, user, *, include_demo=False, order_id=None):
    other = aliased(Order)
    duplicate = select(other.id).where(
        other.id != Order.id, other.client_id == Order.client_id, other.is_demo == Order.is_demo,
        func.trim(Order.commission_number) != "",
        func.lower(func.trim(other.commission_number)) == func.lower(func.trim(Order.commission_number)),
        or_(other.status != "Rejected", other.generated_xmls.any()),
    ).correlate(Order).exists()
    failed_document = Order.attachments.any(Attachment.processing_status == "failed")
    query = select(Order, duplicate.label("has_duplicate")).where(
        Order.status.not_in(["Rejected", "XMLs Sent"]),
        or_(Order.status.in_(["Failed", "Human in the Loop", "Waiting for Reply"]), duplicate, failed_document),
    ).options(joinedload(Order.client), selectinload(Order.validation_issues), selectinload(Order.attachments))
    allowed = accessible_client_ids(user)
    if allowed is not None:
        query = query.where(Order.client_id.in_(allowed))
    if not include_demo:
        query = query.where(Order.is_demo.is_(False))
    if order_id is not None:
        query = query.where(Order.id == order_id)
    query = query.order_by(Order.updated_at.desc(), Order.id.desc())
    read = {r.order_id: r for r in db.scalars(select(NotificationRead).where(NotificationRead.user_id == user.id))}
    result = []
    for order, has_duplicate in db.execute(query).unique():
        issues = [i for i in order.validation_issues if not i.is_resolved]
        failures = [a.id for a in order.attachments if a.processing_status == "failed"]
        failed = order.status == "Failed" or failures or any(i.issue_type in {"ai_extraction_failed", "technical_exception"} for i in issues)
        kind = "failed" if failed else "duplicate" if has_duplicate else "waiting" if order.status == "Waiting for Reply" else "review"
        matches = duplicate_orders(db, order.client_id, order.commission_number,
                                   order_id=order.id, is_demo=order.is_demo) if has_duplicate else []
        version = [order.status, order.updated_at.isoformat(), sorted(i.id for i in issues), sorted(failures),
                   sorted(m.id for m in matches)]
        fingerprint = hashlib.sha256(json.dumps(version).encode()).hexdigest()
        state = read.get(order.id)
        result.append({"order_id": order.id, "reference": order.commission_number or order.ticket_number or "Unconfirmed reference",
                       "client_name": order.client.client_name, "category": kind, "title": TITLES[kind],
                       "message": MESSAGES[kind], "status": order.status, "is_demo": order.is_demo,
                       "updated_at": order.updated_at.replace(tzinfo=UTC), "fingerprint": fingerprint,
                       "is_read": bool(state and state.fingerprint == fingerprint and state.is_read)})
    return result
