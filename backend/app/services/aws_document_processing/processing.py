from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.attachment import Attachment
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.validation_issue import ValidationIssue
from app.services.aws_document_processing.order_mapping import TextractOrderMapper
from app.services.aws_document_processing.service import (
    SUPPORTED_DOCUMENT_SUFFIXES,
    AwsDocumentProcessingError,
    AwsDocumentProcessingService,
)

logger = logging.getLogger(__name__)


class TextractPollSummary(BaseModel):
    checked: int = 0
    completed: int = 0
    in_progress: int = 0
    failed: int = 0
    mapped_items: int = 0


class TextractJobProcessor:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        *,
        service_factory=None,
        order_mapper: TextractOrderMapper | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.service_factory = service_factory or (lambda: AwsDocumentProcessingService(settings))
        self.order_mapper = order_mapper or TextractOrderMapper()

    def start_for_attachments(self, db: Session, attachments: list[Attachment]) -> int:
        candidates = [
            attachment
            for attachment in attachments
            if Path(attachment.file_name).suffix.casefold() in SUPPORTED_DOCUMENT_SUFFIXES
            and attachment.processing_status in {None, "not_required", "failed"}
        ]
        if not self.settings.textract_auto_processing_enabled or not candidates:
            return 0

        try:
            service = self.service_factory()
        except AwsDocumentProcessingError as exc:
            for attachment in candidates:
                self._mark_start_failed(attachment, str(exc))
            return 0

        started_count = 0
        for attachment in candidates:
            attachment.processing_status = "pending"
            attachment.processing_error = None
            try:
                result = service.start_table_analysis(
                    attachment.file_name,
                    Path(attachment.file_path).read_bytes(),
                )
                attachment.textract_job_id = result.job_id
                attachment.s3_object_key = result.object_key
                attachment.processing_status = "in_progress"
                started_count += 1
            except (AwsDocumentProcessingError, OSError) as exc:
                self._mark_start_failed(attachment, str(exc))
        return started_count

    def poll_once(self) -> TextractPollSummary:
        summary = TextractPollSummary()
        with self.session_factory() as db:
            attachments = list(
                db.scalars(
                    select(Attachment)
                    .where(
                        Attachment.processing_status == "in_progress",
                        Attachment.textract_job_id.is_not(None),
                    )
                    .order_by(Attachment.created_at)
                    .limit(self.settings.textract_max_jobs_per_poll)
                )
            )
            if attachments:
                service = self.service_factory()
                for attachment in attachments:
                    summary.checked += 1
                    try:
                        result = service.get_table_analysis(attachment.textract_job_id or "")
                    except AwsDocumentProcessingError as exc:
                        attachment.processing_error = str(exc)[:1000]
                        logger.warning("Textract job %s could not be polled: %s", attachment.textract_job_id, exc)
                        continue

                    if result.status == "IN_PROGRESS":
                        summary.in_progress += 1
                        continue
                    if result.status == "SUCCEEDED":
                        attachment.processing_status = "succeeded"
                        attachment.extracted_text = "\n".join(line.text for line in result.lines)
                        attachment.processing_error = None
                        attachment.processed_at = datetime.now(UTC).replace(tzinfo=None)
                        summary.completed += 1
                        continue

                    attachment.processing_status = "failed"
                    attachment.processing_error = (
                        result.status_message or f"Textract job ended with {result.status}."
                    )[:1000]
                    attachment.processed_at = datetime.now(UTC).replace(tzinfo=None)
                    self._add_failure_issue(db, attachment)
                    summary.failed += 1

            completed_attachments = list(
                db.scalars(
                    select(Attachment)
                    .where(
                        Attachment.processing_status == "succeeded",
                        Attachment.extracted_text.is_not(None),
                        Attachment.order_id.is_not(None),
                    )
                    .order_by(Attachment.processed_at.desc())
                    .limit(self.settings.textract_max_jobs_per_poll)
                )
            )
            for attachment in completed_attachments:
                mapping = self.order_mapper.map_text(attachment.extracted_text or "")
                summary.mapped_items += self._apply_mapping(db, attachment, mapping)
            db.commit()
        return summary

    @staticmethod
    def _apply_mapping(db: Session, attachment: Attachment, mapping) -> int:
        if not attachment.order_id or not mapping.items:
            return 0

        order = db.get(Order, attachment.order_id)
        if order is None:
            return 0

        changed = 0
        existing_items = list(db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)))
        existing_by_code = {
            ((item.model_number or "").upper(), (item.article_number or "").upper()): item
            for item in existing_items
        }
        for mapped_item in mapping.items:
            key = (mapped_item.model_number.upper(), mapped_item.article_number.upper())
            item = existing_by_code.get(key)
            if item is None:
                db.add(
                    OrderItem(
                        order_id=order.id,
                        model_number=mapped_item.model_number,
                        article_number=mapped_item.article_number,
                        quantity=mapped_item.quantity,
                        unit_price=mapped_item.unit_price,
                        total_price=mapped_item.total_price,
                        currency=mapped_item.currency,
                    )
                )
                changed += 1
                continue

            for field in ("quantity", "unit_price", "total_price", "currency"):
                current_value = getattr(item, field)
                mapped_value = getattr(mapped_item, field)
                if current_value is None and mapped_value is not None:
                    setattr(item, field, mapped_value)
                    changed += 1

        if order.order_date is None and mapping.order_date is not None:
            order.order_date = mapping.order_date
        if order.total_price is None and mapping.total_price is not None:
            order.total_price = mapping.total_price
        if order.currency is None and mapping.currency is not None:
            order.currency = mapping.currency

        if changed:
            unresolved_item_issues = list(
                db.scalars(
                    select(ValidationIssue).where(
                        ValidationIssue.order_id == order.id,
                        ValidationIssue.field_name == "items",
                        ValidationIssue.is_resolved.is_(False),
                    )
                )
            )
            for issue in unresolved_item_issues:
                db.delete(issue)
        return changed

    @staticmethod
    def _mark_start_failed(attachment: Attachment, message: str) -> None:
        attachment.processing_status = "failed"
        attachment.processing_error = message[:1000]
        attachment.processed_at = datetime.now(UTC).replace(tzinfo=None)

    @staticmethod
    def _add_failure_issue(db: Session, attachment: Attachment) -> None:
        if not attachment.order_id:
            return
        existing = db.scalar(
            select(ValidationIssue).where(
                ValidationIssue.order_id == attachment.order_id,
                ValidationIssue.field_name == "attachments",
                ValidationIssue.issue_type == "textract_failed",
                ValidationIssue.is_resolved.is_(False),
            )
        )
        if existing is None:
            db.add(
                ValidationIssue(
                    order_id=attachment.order_id,
                    field_name="attachments",
                    issue_type="textract_failed",
                    message=f"Textract could not process {attachment.file_name}.",
                    severity="error",
                )
            )
