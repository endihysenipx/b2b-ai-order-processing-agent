"""Customer-scoped duplicate checks using the per-order commission reference."""

from sqlalchemy import func, or_, select

from app.models.order import Order


def duplicate_orders(db, client_id, reference, *, order_id=None, is_demo=False):
    if not client_id or not reference or not reference.strip():
        return []
    query = select(Order).where(
        Order.client_id == client_id,
        Order.is_demo.is_(is_demo),
        func.lower(func.trim(Order.commission_number)) == func.lower(func.trim(reference)),
        # Rejecting an order cannot erase evidence of a previous export.
        or_(Order.status != "Rejected", Order.generated_xmls.any()),
    )
    if order_id:
        query = query.where(Order.id != order_id)
    return list(db.scalars(query.order_by(Order.created_at, Order.id)))
