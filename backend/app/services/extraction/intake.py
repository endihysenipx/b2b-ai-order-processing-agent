"""Persist OpenAI extraction during initial intake, before operator approval."""

from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.attachment import Attachment
from app.models.client import Client
from app.models.email import Email
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.validation_issue import ValidationIssue
from app.services.document_processing.service import extract_pdf_text
from app.services.extraction.service import AIExtractionError, ExtractionDocument, build_ai_extraction_service
from app.services.validation.service import validate_order_data


def _text(value, limit: int) -> str | None:
    if value is None:
        return None
    value = str(value)
    if len(value) > limit:
        raise ValueError("Extracted field exceeds database length")
    return value


def _number(value, *, quantity=False):
    if value is None:
        return None
    number = Decimal(str(value))
    if not number.is_finite() or number < 0 or (quantity and number == 0):
        raise ValueError("Invalid extracted number")
    if quantity:
        if number != number.to_integral_value() or number > 2_147_483_647:
            raise ValueError("Quantity must be a positive integer")
        return int(number)
    if number >= Decimal("10000000000") or number != number.quantize(Decimal("0.01")):
        raise ValueError("Price exceeds supported precision")
    return number


def _read_document(attachment: Attachment) -> str:
    try:
        if Path(attachment.file_path).suffix.lower() == ".pdf":
            return extract_pdf_text(attachment.file_path)
        return Path(attachment.file_path).read_text(encoding="utf-8")
    except Exception as exc:
        # PDF parsers raise several library-specific errors for malformed/encrypted files.
        raise AIExtractionError("An attachment could not be read; review the original document.") from exc


def extract_intake_order(
    db: Session, settings: Settings, email: Email, client: Client,
    orders: list[Order], attachments: list[Attachment],
) -> None:
    if len(orders) > 1:
        return  # Preserve the established multi-commission parser.
    order = orders[0] if orders else Order(
        email_id=email.id, client_id=client.id, customer_name=client.client_name,
        status="Human in the Loop", is_scanned_source=any(a.is_scanned for a in attachments),
    )
    db.add(order)
    db.flush()
    for attachment in attachments:
        attachment.order_id = order.id
    message = "OpenAI extraction completed; verify the source evidence before approval."
    issue_type = "manual_review_required"
    try:
        service = build_ai_extraction_service(settings)
        documents = []
        for attachment in attachments:
            suffix = Path(attachment.file_path).suffix.lower()
            if suffix not in {".pdf", ".txt", ".csv"}:
                continue
            content = _read_document(attachment)
            if content.strip():
                documents.append(ExtractionDocument(file_name=attachment.file_name, content=content))
        extracted = service.extract_order(
            client.extraction_prompt or "Extract the purchase-order fields and line items.",
            f"Subject: {email.subject}\n{email.body or ''}", documents,
        )
        header = {
            name: _text(extracted.header[name].value, limit)
            for name, limit in {
                "ticket_number": 100, "customer_number": 100,
                "commission_number": 100, "delivery_address": 500,
            }.items()
        }
        items = []
        for item in extracted.items:
            items.append({
                "article_number": _text(item.article_number.value, 100),
                "model_number": _text(item.model_number.value, 100) if item.model_number else None,
                "quantity": _number(item.quantity.value, quantity=True),
                "unit_price": _number(item.unit_price.value) if item.unit_price else None,
                "currency": _text(item.currency.value, 10) if item.currency else None,
            })
        # Persist provenance alongside the original email, never in public assets.
        evidence_path = Path(settings.storage_root) / "emails" / f"{email.id}.extraction.json"
        evidence_path.write_text(extracted.model_dump_json(indent=2), encoding="utf-8")
        for name, value in header.items():
            setattr(order, name, value)
        order.items = [OrderItem(**item) for item in items]
        order.validation_issues = [ValidationIssue(
            field_name=issue.field_name, issue_type=issue.issue_type,
            message=issue.message, severity=issue.severity,
        ) for issue in validate_order_data(header, items, order.is_scanned_source, db=db, client_id=client.id,
                                           order_id=order.id, is_demo=order.is_demo)]
        if not items:
            order.validation_issues.append(ValidationIssue(
                field_name="items", issue_type="missing_required_field",
                message="No line items were extracted; review the original order.", severity="error",
            ))
    except AIExtractionError as exc:
        message = str(exc)
        issue_type = "ai_extraction_failed"
    except (ValueError, KeyError, OSError, InvalidOperation):
        message = "Order evidence could not be read or mapped safely; review the original documents."
        issue_type = "ai_extraction_failed"
    order.status = "Human in the Loop"
    order.validation_issues.append(ValidationIssue(
        field_name="extraction", issue_type=issue_type, message=message, severity="warning",
    ))
