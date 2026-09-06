"""Explicit, audited conversion of an imported email into a client example case."""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.models.client import Client
from app.models.email import Email
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.validation_issue import ValidationIssue
from app.services.audit import ITEM_FIELDS, ORDER_FIELDS, record_change, snapshot
from app.services.stock import release_stock


def convert_case(db, actor, payload):
    from app.api.routes.orders import refresh_validation

    email = db.get(Email, payload.email_id)
    if email is None:
        raise HTTPException(404, "Source email not found")
    client_ids = {payload.client_id, email.client_id} - {None}
    list(db.scalars(select(Client).where(Client.id.in_(client_ids)).order_by(Client.id).with_for_update()))
    email = db.scalar(select(Email).where(Email.id == payload.email_id).with_for_update())
    client = db.get(Client, payload.client_id)
    if client is None or not client.is_active:
        raise HTTPException(404, "Active client not found")
    orders = list(db.scalars(select(Order).where(Order.email_id == email.id).with_for_update()))
    if len(orders) > 1:
        raise HTTPException(409, "This email contains multiple orders; choose a single-order source.")
    if any(a.processing_status in {"pending", "in_progress"} for a in email.attachments):
        raise HTTPException(409, "Wait for document processing to finish before converting this source.")
    order = orders[0] if orders else Order(email=email, client=client, status="Human in the Loop", is_demo=True)
    if order.case_source:
        raise HTTPException(409, "This source is already a client case. Edit its order instead.")
    if any(xml.sent_at is not None for xml in order.generated_xmls):
        raise HTTPException(409, "Sent orders cannot be converted into client cases.")
    if payload.quantity * payload.unit_price >= 10000000000:
        raise HTTPException(422, "Case line total exceeds the supported maximum.")
    before = snapshot(order, ORDER_FIELDS)
    before["items"] = [snapshot(item, ITEM_FIELDS) for item in order.items]
    before["email"] = {key: getattr(email, key) for key in ("client_id", "subject", "sender_email", "reply_to_email", "body", "classification_status")}
    if orders:
        release_stock(db, order, actor)
    order.client = client
    order.client_id = client.id
    order.is_demo = True
    order.case_source = {"label": payload.label, "source_email_id": email.id,
                         "converted_at": datetime.now(UTC).isoformat(), "original_subject": email.subject}
    order.customer_name = client.client_name
    order.customer_number = client.customer_number
    order.ticket_number = f"CASE-{client.customer_number}"[:100]
    order.commission_number = f"CASE-{email.id[:8].upper()}"
    order.commission_name = payload.label
    order.store_address = None
    order.delivery_address = (client.approved_delivery_addresses or [f"Example receiving dock — {client.client_name}"])[0]
    order.contact_person = client.contact_name
    order.phone_number = client.phone
    order.currency = (client.validation_rules or {}).get("business_rules", {}).get("currency", "EUR")
    order.total_price = payload.quantity * payload.unit_price
    order.items = [OrderItem(article_number=payload.article_number, quantity=payload.quantity,
                            unit_price=payload.unit_price, total_price=order.total_price, currency=order.currency)]
    order.is_scanned_source = False
    order.generated_xmls.clear()
    order.validation_issues = [ValidationIssue(field_name="extraction", issue_type="manual_review_required",
        message=("Client example: sender, customer and prices were deliberately edited. "
                 "Original attachments are source references, not the case's commercial instructions."), severity="warning")]
    email.client_id = client.id
    email.subject = f"Client case: {payload.label} — {client.client_name}"[:500]
    email.sender_email = client.default_email or f"orders@{client.email_domain}"
    email.reply_to_email = email.sender_email
    email.classification_status = "order"
    email.body = (f"Edited client example for {client.client_name}.\n{payload.label}\n"
                  f"{payload.quantity} x {payload.article_number} at {payload.unit_price} {order.currency}.\n"
                  "Original attachments retained for traceability; use the editable case fields for calculations.")
    db.add(order)
    db.flush()
    for attachment in email.attachments:
        attachment.order_id = order.id
    refresh_validation(db, order)
    after = snapshot(order, ORDER_FIELDS)
    after["items"] = [snapshot(item, ITEM_FIELDS) for item in order.items]
    after["email"] = {key: getattr(email, key) for key in before["email"]}
    record_change(db, actor, client, "order", order, before, after, "source_converted_to_client_case", order_id=order.id)
    return order
