from sqlalchemy import select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.attachment import Attachment
from app.services.aws_document_processing import (
    TextractJobProcessor,
    TextractJobResult,
    TextractJobStart,
)
from app.services.aws_document_processing.service import TextractLine


class FakeDocumentService:
    def __init__(self) -> None:
        self.started: list[tuple[str, bytes]] = []

    def start_table_analysis(self, filename: str, content: bytes) -> TextractJobStart:
        self.started.append((filename, content))
        return TextractJobStart(
            job_id="tracked-job-1",
            bucket="test-order-bucket",
            object_key="textract-input/tracked/order.pdf",
        )

    def get_table_analysis(self, job_id: str) -> TextractJobResult:
        assert job_id == "tracked-job-1"
        return TextractJobResult(
            job_id=job_id,
            status="SUCCEEDED",
            pages=1,
            lines=[TextractLine(page=1, text="MODEL01 ART01 QUANTITY 2", confidence=99.1)],
        )


def test_textract_processor_starts_tracks_and_persists_results(tmp_path):
    document = tmp_path / "order.pdf"
    document.write_bytes(b"pdf-content")
    fake = FakeDocumentService()
    settings = Settings(
        textract_auto_processing_enabled=True,
        aws_s3_bucket="test-order-bucket",
        textract_max_jobs_per_poll=5,
    )
    processor = TextractJobProcessor(settings, SessionLocal, service_factory=lambda: fake)

    with SessionLocal() as db:
        attachment = db.scalar(select(Attachment).order_by(Attachment.created_at))
        attachment.file_name = "order.pdf"
        attachment.file_path = str(document)
        attachment.processing_status = "not_required"
        attachment.textract_job_id = None
        attachment.s3_object_key = None
        attachment.extracted_text = None
        attachment.processing_error = None
        started = processor.start_for_attachments(db, [attachment])
        attachment_id = attachment.id
        db.commit()

    assert started == 1
    assert fake.started == [("order.pdf", b"pdf-content")]

    summary = processor.poll_once()

    assert summary.model_dump() == {"checked": 1, "completed": 1, "in_progress": 0, "failed": 0}
    with SessionLocal() as db:
        attachment = db.get(Attachment, attachment_id)
        assert attachment.processing_status == "succeeded"
        assert attachment.textract_job_id == "tracked-job-1"
        assert attachment.s3_object_key == "textract-input/tracked/order.pdf"
        assert attachment.extracted_text == "MODEL01 ART01 QUANTITY 2"
        assert attachment.processed_at is not None
