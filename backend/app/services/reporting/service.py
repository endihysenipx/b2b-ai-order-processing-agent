from datetime import UTC, datetime, timedelta

from sqlalchemy import false, func, select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.order import Order


def get_summary(db: Session, accessible_client_ids: set[str] | None = None) -> dict:
    access_filter = None
    if accessible_client_ids is not None:
        access_filter = Order.client_id.in_(accessible_client_ids) if accessible_client_ids else false()
    total_query = select(func.count(Order.id))
    status_query = select(Order.status, func.count(Order.id)).group_by(Order.status)
    client_query = (
        select(Client.client_name, func.count(Order.id))
        .join(Order, Order.client_id == Client.id)
        .group_by(Client.client_name)
    )
    recent_since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)
    recent_query = select(func.count(Order.id)).where(Order.created_at >= recent_since)
    if access_filter is not None:
        total_query = total_query.where(access_filter)
        status_query = status_query.where(access_filter)
        client_query = client_query.where(access_filter)
        recent_query = recent_query.where(access_filter)
    total = db.scalar(total_query) or 0
    by_status = dict(db.execute(status_query).all())
    by_client_rows = db.execute(client_query).all()
    recent_order_count = db.scalar(recent_query) or 0
    return {
        "total_orders": total,
        "count_by_status": by_status,
        "count_by_client": dict(by_client_rows),
        "recent_order_count": recent_order_count,
    }
