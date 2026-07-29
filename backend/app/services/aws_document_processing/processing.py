from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.attachment import Attachment
from app.models.validation_issue import ValidationIssue
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


class TextractJobProcessor:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        *,
        service_factory=None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.service_factory = service_factory or (lambda: AwsDocumentProcessingService(settings))

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
            if not attachments:
                return summary

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
                attachment.processing_error = (result.status_message or f"Textract job ended with {result.status}.")[:1000]
                attachment.processed_at = datetime.now(UTC).replace(tzinfo=None)
                self._add_failure_issue(db, attachment)
                summary.failed += 1
            db.commit()
        return summary

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
