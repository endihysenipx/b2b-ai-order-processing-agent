"""Customer-facing questions use explicit templates, never raw validation messages."""

import re
from email.utils import parseaddr

from app.services.validation.service import validate_order_data

FIELDS = {
    "ticket_number": "the order reference", "customer_number": "your customer account number",
    "commission_number": "your PO / commission number", "delivery_address": "the full delivery address",
    "items": "the order line items, including article numbers and quantities",
    "article_number": "the article number", "quantity": "the required quantity",
    "currency": "the currency", "unit_price": "the unit price", "total_price": "the line total",
}
QUESTIONS = {
    "invalid_quantity": "Please confirm a positive whole-number quantity.",
    "unknown_product": "Please confirm the article number or provide a product description.",
    "price_mismatch": "Please confirm the agreed unit price, line total and currency.",
    "minimum_quantity": "Please confirm the requested quantity so we can check the minimum order requirement.",
    "address_mismatch": "Please confirm the full delivery address for this order.",
    "customer_mismatch": "Please confirm your customer account number.",
    "duplicate_order": "We have another order with this PO / commission number. Is this a replacement or an additional order?",
}
INTERNAL = {
    "stock_unknown": "Confirm stock availability internally.",
    "stock_stale": "Refresh the stock snapshot internally.",
    "stock_shortage": "Resolve stock availability before promising quantities or delivery dates.",
    "inactive_customer": "Review the customer account internally.",
    "unknown_customer": "Identify the customer account internally.",
    "address_unverified": "Configure or verify approved delivery addresses internally.",
    "inactive_product": "Review product availability internally.",
}


def clean(value):
    return " ".join(str(value or "").split())


def questions_for(issues):
    questions, notes = [], []
    for issue in issues:
        if getattr(issue, "is_resolved", False):
            continue
        field, kind = issue.field_name, issue.issue_type
        line = re.fullmatch(r"items\[(\d+)\]\.(\w+)", field)
        label = line.group(2) if line else field
        prefix = f"Line {line.group(1)}: " if line else ""
        if kind == "missing_required_field" and label in FIELDS:
            questions.append(prefix + f"Please provide {FIELDS[label]}.")
        elif kind in QUESTIONS:
            questions.append(prefix + QUESTIONS[kind])
        else:
            notes.append(prefix + INTERNAL.get(kind, "Review the source document and extraction internally."))
    return list(dict.fromkeys(questions)), list(dict.fromkeys(notes))


def draft_body(reference, questions):
    if not questions:
        return ""
    bullets = "\n".join(f"- {question}" for question in questions)
    return (f"Hello,\n\nThank you for your order ({clean(reference)}). Could you please clarify the following?\n\n"
            f"{bullets}\n\nPlease reply with the confirmed or corrected details.\n\nKind regards,\nOrder Processing Team")


def build_clarification(db, order):
    header = {key: getattr(order, key) for key in ["ticket_number", "customer_number", "commission_number",
                                                  "delivery_address", "total_price", "currency"]}
    items = [{key: getattr(item, key) for key in ["article_number", "quantity", "unit_price", "total_price", "currency"]}
             for item in order.items]
    current = validate_order_data(header, items, order.is_scanned_source, db=db,
                                  client_id=order.client_id, order_id=order.id, is_demo=order.is_demo)
    current.extend(i for i in order.validation_issues if i.field_name == "extraction" and not i.is_resolved)
    questions, notes = questions_for(current)
    reference = order.commission_number or order.ticket_number or "reference not yet confirmed"
    recipient = ""
    for candidate in [order.email.reply_to_email, order.email.sender_email, order.client.default_email]:
        if candidate and not any(c in candidate for c in "\r\n"):
            address = parseaddr(candidate)[1]
            if re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", address):
                recipient = address
                break
    return {"recipient": recipient, "subject": f"Clarification requested: {clean(reference)}",
            "body": draft_body(reference, questions), "questions": questions, "internal_notes": notes}
