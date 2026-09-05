"""Explicit allowlists prevent secrets and unrelated data entering change history."""

from datetime import UTC, date, datetime
from decimal import Decimal

from app.models.audit_event import AuditEvent
from app.models.base import new_id

CUSTOMER_FIELDS = (
    "client_name", "customer_number", "default_email", "email_domain", "contact_name", "phone",
    "approved_delivery_addresses", "is_active", "master_data_enabled",
)
PRODUCT_FIELDS = (
    "sku", "description", "unit", "is_active", "aliases", "unit_price", "currency",
    "minimum_quantity", "warehouse", "on_hand", "reserved", "stock_updated_at",
)
ORDER_FIELDS = (
    "ticket_number", "customer_number", "customer_name", "commission_number", "commission_name",
    "store_address", "delivery_address", "delivery_week", "order_date", "requested_delivery_date",
    "contact_person", "phone_number", "total_price", "currency", "status", "approved_by_user_id", "approved_at",
)
ITEM_FIELDS = ("article_number", "model_number", "quantity", "unit_price", "total_price", "currency")


def json_value(value):
    if isinstance(value, Decimal):
        return format(value.quantize(Decimal("0.01")), "f")
    if isinstance(value, datetime):
        stamp = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return stamp.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [json_value(item) for item in value]
    return value


def snapshot(record, fields):
    return {field: json_value(getattr(record, field)) for field in fields}


def record_change(db, actor, client, entity_type, record, before, after, action, *, order_id=None, batch_id=None):
    changes = {field: {"before": before.get(field), "after": value}
               for field, value in after.items() if before.get(field) != value}
    if not changes:
        return
    if record.id is None:
        record.id = new_id()
    label = {"product": "sku", "customer": "client_name", "order": "ticket_number", "order_item": "article_number"}[entity_type]
    db.add(AuditEvent(
        client_id=client.id, client_name=client.client_name, actor_id=actor.id, actor_name=actor.full_name,
        entity_type=entity_type, entity_id=record.id, entity_label=(getattr(record, label) or record.id)[:200],
        order_id=order_id, action=action, batch_id=batch_id, changes=changes,
    ))


def order_change(db, actor, order, before, action):
    record_change(db, actor, order.client, "order", order, before, snapshot(order, ORDER_FIELDS), action, order_id=order.id)
