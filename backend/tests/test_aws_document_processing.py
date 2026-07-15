from app.core.config import Settings
from app.services.aws_document_processing import AwsDocumentProcessingService


class FakeS3Client:
    def __init__(self):
        self.uploads = []

    def upload_fileobj(self, fileobj, bucket, key, ExtraArgs):
        self.uploads.append((fileobj.read(), bucket, key, ExtraArgs))


class FakeTextractClient:
    def __init__(self):
        self.started = []
        self.responses = []

    def start_document_analysis(self, **kwargs):
        self.started.append(kwargs)
        return {"JobId": "job-123"}

    def get_document_analysis(self, **kwargs):
        return self.responses.pop(0)


def build_service(s3=None, textract=None):
    return AwsDocumentProcessingService(
        Settings(aws_s3_bucket="test-order-bucket", aws_region="eu-central-1"),
        s3_client=s3 or FakeS3Client(),
        textract_client=textract or FakeTextractClient(),
    )


def test_start_table_analysis_uploads_private_source_and_starts_tables_job():
    s3 = FakeS3Client()
    textract = FakeTextractClient()
    service = build_service(s3, textract)

    result = service.start_table_analysis("Lesnina order 01.TIF", b"tiff-bytes")

    assert result.job_id == "job-123"
    assert result.bucket == "test-order-bucket"
    assert result.object_key.startswith("textract-input/")
    assert result.object_key.endswith("/Lesnina-order-01.TIF")
    assert s3.uploads[0][0] == b"tiff-bytes"
    assert s3.uploads[0][3] == {"ContentType": "image/tiff"}
    assert textract.started[0]["FeatureTypes"] == ["TABLES"]
    assert textract.started[0]["DocumentLocation"]["S3Object"]["Name"] == result.object_key


def test_get_table_analysis_reconstructs_lines_and_table_cells_across_pages():
    textract = FakeTextractClient()
    textract.responses = [
        {
            "JobStatus": "SUCCEEDED",
            "DocumentMetadata": {"Pages": 2},
            "NextToken": "next-page",
            "Blocks": [
                {"Id": "line-1", "BlockType": "LINE", "Page": 1, "Text": "Poz. Br.art. Opis", "Confidence": 99.2},
                {"Id": "table-1", "BlockType": "TABLE", "Page": 1, "Relationships": [{"Type": "CHILD", "Ids": ["cell-1"]}]},
                {
                    "Id": "cell-1",
                    "BlockType": "CELL",
                    "Page": 1,
                    "RowIndex": 1,
                    "ColumnIndex": 1,
                    "Confidence": 98.1,
                    "Relationships": [{"Type": "CHILD", "Ids": ["word-1", "word-2"]}],
                },
                {"Id": "word-1", "BlockType": "WORD", "Text": "Br.art.", "Confidence": 97.4},
            ],
        },
        {
            "JobStatus": "SUCCEEDED",
            "Blocks": [
                {"Id": "word-2", "BlockType": "WORD", "Text": "04617", "Confidence": 96.7},
                {"Id": "line-2", "BlockType": "LINE", "Page": 2, "Text": "CQ9696TA", "Confidence": 97.5},
            ],
        },
    ]
    service = build_service(textract=textract)

    result = service.get_table_analysis("job-123")

    assert result.status == "SUCCEEDED"
    assert result.pages == 2
    assert [line.text for line in result.lines] == ["Poz. Br.art. Opis", "CQ9696TA"]
    assert result.tables[0].cells[0].model_dump() == {"row": 1, "column": 1, "text": "Br.art. 04617", "confidence": 96.7}


def test_get_table_analysis_returns_without_blocks_while_job_is_running():
    textract = FakeTextractClient()
    textract.responses = [{"JobStatus": "IN_PROGRESS"}]
    service = build_service(textract=textract)

    result = service.get_table_analysis("job-123")

    assert result.status == "IN_PROGRESS"
    assert result.lines == []
    assert result.tables == []
