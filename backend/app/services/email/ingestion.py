from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.core.config import Settings
from app.models.attachment import Attachment
from app.models.client import Client
from app.models.email import Email
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.validation_issue import ValidationIssue
from app.services.aws_document_processing import TextractJobProcessor
from app.services.decision.service import decide_order_status
from app.services.email.gmail import GmailGateway, GmailImapGateway, GmailMessage
from app.services.email.intake import EmailIntakeParseError, EmailIntakePreview, IntakeNextAction, parse_email_intake
from app.services.email.profile_detection import ClientProfile
from app.services.validation.service import ValidationResult, validate_order_data

logger = logging.getLogger(__name__)


class GmailPollResult(BaseModel):
    fetched: int = 0
    imported: int = 0
    duplicates: int = 0
    orders_created: int = 0
    manual_review: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


class GmailIngestionStatus(BaseModel):
    enabled: bool
    configured: bool
    username: str | None
    folder: str
    search_criteria: str
    poll_interval_seconds: int


class IntelligenceTimelineStep(BaseModel):
    key: str
    label: str
    status: Literal["completed", "attention", "queued"]
    detail: str


class IntelligenceAttachmentSummary(BaseModel):
    file_name: str
    is_scanned: bool
    processing_status: str


class IntelligenceOrderSummary(BaseModel):
    id: str
    ticket_number: str | None
    commission_number: str | None
    delivery_week: str | None
    status: str
    item_count: int
    issue_count: int


class OrderIntelligenceResult(BaseModel):
    duplicate: bool
    email_id: str
    subject: str
    sender_email: str
    classification: str
    client_profile: str | None
    client_name: str | None
    client_confidence: float
    client_evidence: list[str] = Field(default_factory=list)
    next_action: str
    reference_codes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    attachments: list[IntelligenceAttachmentSummary] = Field(default_factory=list)
    orders: list[IntelligenceOrderSummary] = Field(default_factory=list)
    requires_review: bool
    clarification_draft: str | None = None
    timeline: list[IntelligenceTimelineStep] = Field(default_factory=list)


class GmailIngestionService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        *,
        gateway_factory=None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.gateway_factory = gateway_factory or (lambda: GmailImapGateway(settings))
        self.textract_processor = TextractJobProcessor(settings, session_factory)

    def status(self) -> GmailIngestionStatus:
        return GmailIngestionStatus(
            enabled=self.settings.gmail_ingestion_enabled,
            configured=bool(self.settings.gmail_username and self.settings.gmail_app_password),
            username=self.settings.gmail_username,
            folder=self.settings.gmail_imap_folder,
            search_criteria=self.settings.gmail_search_criteria,
            poll_interval_seconds=self.settings.gmail_poll_interval_seconds,
        )

    def poll_once(self) -> GmailPollResult:
        gateway: GmailGateway = self.gateway_factory()
        result = GmailPollResult()
        try:
            messages = gateway.fetch_messages(self.settings.gmail_max_messages_per_poll)
            result.fetched = len(messages)
            for message in messages:
                try:
                    outcome = self._import_message(message)
                    if outcome.duplicate:
                        result.duplicates += 1
                    else:
                        result.imported += 1
                        result.orders_created += len(outcome.orders)
                        result.manual_review += int(outcome.requires_review)
                    if self.settings.gmail_mark_as_read:
                        gateway.mark_as_read(message.uid)
                except Exception as exc:
                    logger.exception("Gmail message UID %s could not be imported", message.uid)
                    result.failed += 1
                    result.errors.append(f"UID {message.uid}: {exc}")
        finally:
            gateway.close()
        return result

    def import_uploaded_message(self, content: bytes) -> OrderIntelligenceResult:
        """Import one uploaded RFC 822 message through the production intake pipeline."""
        digest = hashlib.sha256(content).hexdigest()
        return self._import_message(GmailMessage(uid=f"upload:{digest}", content=content))

    def _import_message(self, gmail_message: GmailMessage) -> OrderIntelligenceResult:
        parsed = BytesParser(policy=policy.default).parsebytes(gmail_message.content)
        external_id = self._external_message_id(parsed, gmail_message.uid)
        preview, parse_error = self._preview(gmail_message.content)
        with self.session_factory() as db:
            existing = db.scalar(select(Email).where(Email.external_message_id == external_id))
            if existing is not None:
                return self._build_intelligence_result(db, existing, preview, parse_error, duplicate=True)

            sender = self._first_address(parsed.get_all("From", []))
            client = self._resolve_client(db, preview, sender)
            stored_email = Email(
                external_message_id=external_id,
                conversation_id=self._conversation_id(parsed),
                sender_email=sender or "unknown@invalid.local",
                reply_to_email=self._first_address(parsed.get_all("Reply-To", [])) or sender,
                mail_to_email=self._first_address(parsed.get_all("To", [])),
                subject=str(parsed.get("Subject", "")),
                body=self._message_body(parsed),
                received_at=self._received_at(parsed),
                classification_status=self._classification_status(preview, parse_error),
                client_id=client.id if client else None,
            )
            db.add(stored_email)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                existing = db.scalar(select(Email).where(Email.external_message_id == external_id))
                if existing is None:
                    raise
                return self._build_intelligence_result(db, existing, preview, parse_error, duplicate=True)

            attachments = self._store_message_files(stored_email, parsed, gmail_message.content)
            self._create_orders(db, stored_email, client, preview, attachments)
            db.flush()
            self.textract_processor.start_for_attachments(db, attachments)
            db.flush()
            result = self._build_intelligence_result(db, stored_email, preview, parse_error, duplicate=False)
            db.commit()
            return result

    @staticmethod
    def _preview(content: bytes) -> tuple[EmailIntakePreview | None, str | None]:
        try:
            return parse_email_intake(content), None
        except EmailIntakeParseError as exc:
            return None, str(exc)

    def _resolve_client(
        self,
        db: Session,
        preview: EmailIntakePreview | None,
        sender_email: str | None,
    ) -> Client | None:
        sender_domain = sender_email.rsplit("@", maxsplit=1)[-1].casefold() if sender_email and "@" in sender_email else None
        if sender_domain:
            client = db.scalar(
                select(Client).where(Client.is_active.is_(True), Client.email_domain.ilike(sender_domain))
            )
            if client:
                return client
        if preview is None or preview.client_profile is None:
            return None

        profile = preview.client_profile
        customer_number = f"AUTO-{profile.value.upper()}"
        client = db.scalar(select(Client).where(Client.customer_number == customer_number))
        if client:
            return client

        client = Client(
            client_name="Lutz" if profile is ClientProfile.LUTZ else "Lesnina",
            customer_number=customer_number,
            default_email=sender_email,
            email_domain=sender_domain or f"{profile.value}.invalid",
            extraction_prompt=f"Extract {profile.value} purchase-order fields and line items.",
            required_fields=[
                "ticket_number",
                "customer_number",
                "commission_number",
                "delivery_address",
                "article_number",
                "quantity",
            ],
            validation_rules={"currency_required_when_price_present": True, "scanned_requires_review": True},
        )
        db.add(client)
        db.flush()
        return client

    def _store_message_files(
        self,
        stored_email: Email,
        parsed: EmailMessage,
        raw_content: bytes,
    ) -> list[Attachment]:
        email_directory = Path(self.settings.storage_root) / "emails"
        attachment_directory = Path(self.settings.storage_root) / "attachments" / stored_email.id
        email_directory.mkdir(parents=True, exist_ok=True)
        attachment_directory.mkdir(parents=True, exist_ok=True)
        (email_directory / f"{stored_email.id}.eml").write_bytes(raw_content)

        attachments: list[Attachment] = []
        used_names: set[str] = set()
        for index, part in enumerate(parsed.iter_attachments(), start=1):
            original_name = part.get_filename() or f"attachment-{index}"
            safe_name = self._safe_filename(original_name)
            if safe_name in used_names:
                safe_name = f"{Path(safe_name).stem}-{uuid4().hex[:8]}{Path(safe_name).suffix}"
            used_names.add(safe_name)
            content = part.get_payload(decode=True) or b""
            path = attachment_directory / safe_name
            path.write_bytes(content)
            suffix = path.suffix.casefold().lstrip(".")
            attachment = Attachment(
                email_id=stored_email.id,
                file_name=original_name,
                file_type=suffix or part.get_content_type(),
                file_path=str(path),
                is_scanned=suffix in {"tif", "tiff", "png", "jpg", "jpeg"},
            )
            attachments.append(attachment)
        return attachments

    @staticmethod
    def _create_orders(
        db: Session,
        stored_email: Email,
        client: Client | None,
        preview: EmailIntakePreview | None,
        attachments: list[Attachment],
    ) -> list[Order]:
        db.add_all(attachments)
        if client is None or preview is None or preview.message_type.value != "order":
            return []

        is_scanned = any(attachment.is_scanned for attachment in attachments)
        created_orders: list[Order] = []
        for index, parsed_order in enumerate(preview.orders):
            ticket_number = preview.reference_codes[0] if preview.reference_codes else None
            order = Order(
                email_id=stored_email.id,
                client_id=client.id,
                ticket_number=ticket_number,
                customer_number=client.customer_number,
                customer_name=client.client_name,
                commission_number=parsed_order.commission_number,
                commission_name=parsed_order.commission_name,
                store_address=parsed_order.store_address,
                delivery_address=parsed_order.delivery_address,
                delivery_week=parsed_order.preferred_delivery_week,
                status="Processing",
                is_scanned_source=is_scanned,
            )
            db.add(order)
            db.flush()
            created_orders.append(order)
            items = [
                OrderItem(
                    order_id=order.id,
                    article_number=item.article_number,
                    model_number=item.model_number,
                    quantity=item.quantity,
                )
                for item in parsed_order.items
            ]
            db.add_all(items)
            issues = validate_order_data(
                {
                    "ticket_number": order.ticket_number,
                    "customer_number": order.customer_number,
                    "commission_number": order.commission_number,
                    "delivery_address": order.delivery_address,
                    "total_price": order.total_price,
                    "currency": order.currency,
                },
                [
                    {
                        "article_number": item.article_number,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "total_price": item.total_price,
                        "currency": item.currency,
                    }
                    for item in items
                ],
                is_scanned_source=is_scanned,
            )
            if not items:
                issues.append(
                    ValidationResult(
                        field_name="items",
                        issue_type="manual_review_required",
                        message="No line items were extracted from the email body.",
                        severity="warning",
                    )
                )
            order.status = decide_order_status(issues, is_scanned_source=is_scanned)
            db.add_all(
                [
                    ValidationIssue(
                        order_id=order.id,
                        field_name=issue.field_name,
                        issue_type=issue.issue_type,
                        message=issue.message,
                        severity=issue.severity,
                    )
                    for issue in issues
                ]
            )
            if index == 0:
                for attachment in attachments:
                    attachment.order_id = order.id
        return created_orders

    def _build_intelligence_result(
        self,
        db: Session,
        stored_email: Email,
        preview: EmailIntakePreview | None,
        parse_error: str | None,
        *,
        duplicate: bool,
    ) -> OrderIntelligenceResult:
        orders = list(
            db.scalars(
                select(Order)
                .options(selectinload(Order.items), selectinload(Order.validation_issues))
                .where(Order.email_id == stored_email.id)
                .order_by(Order.created_at)
            )
        )
        attachments = list(
            db.scalars(select(Attachment).where(Attachment.email_id == stored_email.id).order_by(Attachment.created_at))
        )
        client = db.get(Client, stored_email.client_id) if stored_email.client_id else None
        review_actions = {
            IntakeNextAction.MANUAL_REVIEW,
            IntakeNextAction.NEEDS_OCR,
            IntakeNextAction.RETURN_REVIEW,
            IntakeNextAction.CONFIRMATION_RESPONSE,
        }
        requires_review = (
            preview is None
            or client is None
            or preview.next_action in review_actions
            or any(order.status in {"Human in the Loop", "Waiting for Reply", "Failed"} for order in orders)
        )
        summaries = [
            IntelligenceOrderSummary(
                id=order.id,
                ticket_number=order.ticket_number,
                commission_number=order.commission_number,
                delivery_week=order.delivery_week,
                status=order.status,
                item_count=len(order.items),
                issue_count=sum(not issue.is_resolved for issue in order.validation_issues),
            )
            for order in orders
        ]
        notes = list(preview.notes if preview else [])
        if parse_error:
            notes.append(parse_error)
        attachment_summaries = [
            IntelligenceAttachmentSummary(
                file_name=attachment.file_name,
                is_scanned=attachment.is_scanned,
                processing_status=attachment.processing_status or "not_required",
            )
            for attachment in attachments
        ]
        return OrderIntelligenceResult(
            duplicate=duplicate,
            email_id=stored_email.id,
            subject=stored_email.subject,
            sender_email=stored_email.sender_email,
            classification=stored_email.classification_status,
            client_profile=preview.client_profile.value if preview and preview.client_profile else None,
            client_name=client.client_name if client else None,
            client_confidence=preview.client_detection.confidence if preview else 0,
            client_evidence=list(preview.client_detection.evidence if preview else []),
            next_action=preview.next_action.value if preview else IntakeNextAction.MANUAL_REVIEW.value,
            reference_codes=list(preview.reference_codes if preview else []),
            notes=notes,
            attachments=attachment_summaries,
            orders=summaries,
            requires_review=requires_review,
            clarification_draft=self._clarification_draft(stored_email, orders, preview, requires_review),
            timeline=self._intelligence_timeline(
                stored_email,
                preview,
                parse_error,
                client,
                summaries,
                attachment_summaries,
                requires_review,
                duplicate,
            ),
        )

    @staticmethod
    def _clarification_draft(
        stored_email: Email,
        orders: list[Order],
        preview: EmailIntakePreview | None,
        requires_review: bool,
    ) -> str | None:
        if not requires_review:
            return None
        references = [order.ticket_number or order.commission_number for order in orders]
        reference = ", ".join(value for value in references if value) or stored_email.subject or "your order"
        issue_messages = list(
            dict.fromkeys(
                issue.message
                for order in orders
                for issue in order.validation_issues
                if not issue.is_resolved
            )
        )
        if preview and preview.next_action is IntakeNextAction.NEEDS_OCR:
            issue_messages.append("Please confirm the line items shown in the scanned attachment.")
        if not issue_messages:
            issue_messages.append("Please confirm the order details and provide any missing line-item information.")
        bullets = "\n".join(f"- {message}" for message in dict.fromkeys(issue_messages))
        return (
            f"Hello,\n\nWe are reviewing {reference} and need the following information before processing:\n"
            f"{bullets}\n\nPlease reply with the corrected or missing details.\n\nKind regards,\nOrder Processing Team"
        )

    @staticmethod
    def _intelligence_timeline(
        stored_email: Email,
        preview: EmailIntakePreview | None,
        parse_error: str | None,
        client: Client | None,
        orders: list[IntelligenceOrderSummary],
        attachments: list[IntelligenceAttachmentSummary],
        requires_review: bool,
        duplicate: bool,
    ) -> list[IntelligenceTimelineStep]:
        issue_count = sum(order.issue_count for order in orders)
        item_count = sum(order.item_count for order in orders)
        ocr_attachments = [item for item in attachments if item.is_scanned]
        extraction_status: Literal["completed", "attention", "queued"] = "completed"
        extraction_detail = f"Extracted {len(orders)} order(s) and {item_count} line item(s)."
        if ocr_attachments:
            processing = {item.processing_status for item in ocr_attachments}
            extraction_status = "queued" if processing & {"pending", "in_progress"} else "attention"
            extraction_detail = f"{len(ocr_attachments)} scanned attachment(s) require OCR review."
        elif not orders:
            extraction_status = "attention"
            extraction_detail = "No order record was created; manual classification is required."

        return [
            IntelligenceTimelineStep(
                key="received",
                label="Message received",
                status="completed",
                detail=("Previously imported; existing records were reused." if duplicate else "Stored safely with duplicate protection."),
            ),
            IntelligenceTimelineStep(
                key="classified",
                label="Message classified",
                status="attention" if parse_error or preview is None else "completed",
                detail=parse_error or f"Classified as {stored_email.classification_status.replace('_', ' ')}.",
            ),
            IntelligenceTimelineStep(
                key="client",
                label="Client identified",
                status="completed" if client else "attention",
                detail=(f"Matched {client.client_name}." if client else "No authorized client profile matched automatically."),
            ),
            IntelligenceTimelineStep(
                key="extracted",
                label="Evidence extracted",
                status=extraction_status,
                detail=extraction_detail,
            ),
            IntelligenceTimelineStep(
                key="validated",
                label="Business rules validated",
                status="attention" if issue_count or not orders else "completed",
                detail=(f"Found {issue_count} validation issue(s)." if issue_count else "Required order fields passed validation."),
            ),
            IntelligenceTimelineStep(
                key="review",
                label="Human decision",
                status="attention" if requires_review else "completed",
                detail=("Review is required before approval or ERP preparation." if requires_review else "Ready for an operator to approve explicitly."),
            ),
        ]

    @staticmethod
    def _external_message_id(message: EmailMessage, uid: str) -> str:
        message_id = str(message.get("Message-ID", "")).strip()
        return message_id[:255] if message_id else f"gmail-imap:{uid}"

    @staticmethod
    def _conversation_id(message: EmailMessage) -> str | None:
        value = str(message.get("In-Reply-To", "") or message.get("References", "")).strip()
        return value[:255] or None

    @staticmethod
    def _first_address(headers: list[str]) -> str | None:
        return next((address for _, address in getaddresses(headers) if address), None)

    @staticmethod
    def _message_body(message: EmailMessage) -> str:
        return ClientEmailBody.body(message)

    @staticmethod
    def _received_at(message: EmailMessage) -> datetime:
        try:
            value = parsedate_to_datetime(str(message.get("Date", "")))
            if value.tzinfo is None:
                return value
            return value.astimezone(UTC).replace(tzinfo=None)
        except (TypeError, ValueError):
            return datetime.now(UTC).replace(tzinfo=None)

    @staticmethod
    def _classification_status(preview: EmailIntakePreview | None, parse_error: str | None) -> str:
        if parse_error:
            return "parse_error"
        if preview is None:
            return "manual_review"
        return preview.message_type.value

    @staticmethod
    def _safe_filename(filename: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(filename).name).strip(".-")
        return safe or f"attachment-{uuid4().hex}"


class ClientEmailBody:
    @staticmethod
    def body(message: EmailMessage) -> str:
        part = message.get_body(preferencelist=("plain", "html"))
        if part is None:
            return ""
        content = part.get_content()
        if part.get_content_type() == "text/html":
            content = re.sub(r"(?i)<br\s*/?>|</p\s*>", "\n", content)
            content = re.sub(r"<[^>]+>", " ", content)
        return content
