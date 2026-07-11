from app.api.routes.documents import get_aws_document_processing_service
from app.main import app
from app.services.aws_document_processing import TextractJobResult, TextractJobStart


class FakeAwsDocumentProcessingService:
    def start_table_analysis(self, filename, content):
        assert filename == "order.tiff"
        assert content == b"fake-tiff"
        return TextractJobStart(job_id="job-api", bucket="test-bucket", object_key="textract-input/order.tiff")

    def get_table_analysis(self, job_id):
        assert job_id == "job-api"
        return TextractJobResult(job_id=job_id, status="IN_PROGRESS")


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
