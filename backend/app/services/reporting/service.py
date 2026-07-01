from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.order import Order


def get_summary(db: Session) -> dict:
    total = db.scalar(select(func.count(Order.id))) or 0
    by_status = dict(db.execute(select(Order.status, func.count(Order.id)).group_by(Order.status)).all())
    by_client_rows = db.execute(
        select(Client.client_name, func.count(Order.id))
        .join(Order, Order.client_id == Client.id)
        .group_by(Client.client_name)
    ).all()
    recent_since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)
    recent_order_count = db.scalar(select(func.count(Order.id)).where(Order.created_at >= recent_since)) or 0
    return {
        "total_orders": total,
        "count_by_status": by_status,
        "count_by_client": dict(by_client_rows),
        "recent_order_count": recent_order_count,
    }
