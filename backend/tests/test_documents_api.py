from email.message import EmailMessage

from app.api.routes.documents import get_aws_document_processing_service
from app.main import app
from app.services.aws_document_processing import LesninaMappedItem, LesninaTableMapping, TextractJobResult, TextractJobStart


class FakeAwsDocumentProcessingService:
    def start_table_analysis(self, filename, content):
        assert filename == "order.tiff"
        assert content == b"fake-tiff"
        return TextractJobStart(job_id="job-api", bucket="test-bucket", object_key="textract-input/order.tiff")

    def get_table_analysis(self, job_id):
        assert job_id == "job-api"
        return TextractJobResult(job_id=job_id, status="IN_PROGRESS")


class CompletedFakeAwsDocumentProcessingService(FakeAwsDocumentProcessingService):
    def get_table_analysis(self, job_id):
        return TextractJobResult(
            job_id=job_id,
            status="SUCCEEDED",
            lesnina_mapping=LesninaTableMapping(
                items=[
                    LesninaMappedItem(
                        model_number="OJ00",
                        article_number="30155",
                        quantity=2,
                        position="1.1",
                        source_page=2,
                        source_row=5,
                        confidence=98.0,
                    )
                ]
            ),
        )


def build_lesnina_email():
    message = EmailMessage()
    message["From"] = "crm@staudmoebel.de"
    message["To"] = "orders@example.com"
    message["Subject"] = "Bestellung HVSTUE von Lutz"
    message.set_content(
        "ANLIEFERUNG: Šijanska cesta 60, HR-52215 Vodnjan\n"
        "Liefertermin: KW37/2026\nROSSI\nKomm: HVSTUE-1\nPREMA SKICI"
    )
    message.add_attachment(b"tiff", maintype="image", subtype="tiff", filename="EX-00001.TIF")
    return message.as_bytes()


def test_textract_job_endpoints_are_authenticated_and_do_not_call_aws(client, auth_headers):
    app.dependency_overrides[get_aws_document_processing_service] = lambda: FakeAwsDocumentProcessingService()
    try:
        started = client.post(
            "/api/v1/documents/textract/jobs",
            files={"file": ("order.tiff", b"fake-tiff", "image/tiff")},
            headers=auth_headers,
        )
        polled = client.get("/api/v1/documents/textract/jobs/job-api", headers=auth_headers)
    finally:
        app.dependency_overrides.pop(get_aws_document_processing_service, None)

    assert started.status_code == 202
    assert started.json()["job_id"] == "job-api"
    assert polled.status_code == 200
    assert polled.json()["status"] == "IN_PROGRESS"


def test_completed_job_can_merge_lesnina_items_with_email_headers(client, auth_headers):
    app.dependency_overrides[get_aws_document_processing_service] = lambda: CompletedFakeAwsDocumentProcessingService()
    try:
        response = client.post(
            "/api/v1/documents/textract/jobs/job-api/lesnina-order",
            files={"email_file": ("order.eml", build_lesnina_email(), "message/rfc822")},
            headers=auth_headers,
        )
    finally:
        app.dependency_overrides.pop(get_aws_document_processing_service, None)

    assert response.status_code == 200
    assert response.json()["requires_review"] is False
    assert response.json()["order"] == {
        "store_address": None,
        "delivery_address": "Šijanska cesta 60, HR-52215 Vodnjan",
        "preferred_delivery_week": "KW37/2026",
        "commission_name": "ROSSI",
        "commission_number": "HVSTUE-1",
        "items": [{"model_number": "OJ00", "article_number": "30155", "quantity": 2, "position": "1.1"}],
    }
