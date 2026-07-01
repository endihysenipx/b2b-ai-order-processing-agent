from datetime import date

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.order import Order


def order_detail_options():
    return (
        joinedload(Order.client),
        joinedload(Order.email),
        selectinload(Order.items),
        selectinload(Order.attachments),
        selectinload(Order.validation_issues),
        selectinload(Order.generated_xmls),
    )


def get_order(db: Session, order_id: str) -> Order | None:
    return db.scalar(select(Order).options(*order_detail_options()).where(Order.id == order_id))


def build_order_query(
    status: str | None = None,
    client_id: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Select[tuple[Order]]:
    query = select(Order).options(joinedload(Order.client)).order_by(Order.created_at.desc())
    if status and status != "All":
        query = query.where(Order.status == status)
    if client_id:
        query = query.where(Order.client_id == client_id)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Order.ticket_number.ilike(pattern),
                Order.commission_number.ilike(pattern),
                Order.customer_name.ilike(pattern),
            )
        )
    if date_from:
        query = query.where(func.date(Order.created_at) >= date_from)
    if date_to:
        query = query.where(func.date(Order.created_at) <= date_to)
    return query
