from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, Field

from app.core.config import Settings

SUPPORTED_DOCUMENT_SUFFIXES = {".pdf", ".tif", ".tiff", ".png", ".jpg", ".jpeg"}
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


class AwsDocumentProcessingError(RuntimeError):
    pass


class TextractLine(BaseModel):
    page: int | None = None
    text: str
    confidence: float | None = None


class TextractTableCell(BaseModel):
    row: int
    column: int
    text: str
    confidence: float | None = None


class TextractTable(BaseModel):
    page: int | None = None
    cells: list[TextractTableCell] = Field(default_factory=list)


class TextractJobStart(BaseModel):
    job_id: str
    bucket: str
    object_key: str
    status: str = "IN_PROGRESS"


class TextractJobResult(BaseModel):
    job_id: str
    status: str
    status_message: str | None = None
    pages: int | None = None
    lines: list[TextractLine] = Field(default_factory=list)
    tables: list[TextractTable] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class AwsDocumentProcessingService:
    def __init__(
        self,
        settings: Settings,
        *,
        s3_client: Any | None = None,
        textract_client: Any | None = None,
    ) -> None:
        if not settings.aws_s3_bucket:
            raise AwsDocumentProcessingError("AWS_S3_BUCKET is not configured.")

        self.bucket = settings.aws_s3_bucket
        self.region = settings.aws_region
        if s3_client is None or textract_client is None:
            session_arguments: dict[str, str] = {"region_name": self.region}
            if settings.aws_profile:
                session_arguments["profile_name"] = settings.aws_profile
            session = boto3.Session(**session_arguments)
            s3_client = s3_client or session.client("s3")
            textract_client = textract_client or session.client("textract")

        self.s3 = s3_client
        self.textract = textract_client

    def start_table_analysis(self, filename: str, content: bytes) -> TextractJobStart:
        suffix = Path(filename).suffix.casefold()
        if suffix not in SUPPORTED_DOCUMENT_SUFFIXES:
            raise AwsDocumentProcessingError("Textract accepts only .pdf, .tif, .tiff, .png, .jpg, or .jpeg files here.")
        if not content:
            raise AwsDocumentProcessingError("The uploaded document is empty.")

        safe_name = self._safe_filename(filename)
        object_key = f"textract-input/{uuid4()}/{safe_name}"
        request_token = uuid4().hex

        try:
            self.s3.upload_fileobj(
                BytesIO(content),
                self.bucket,
                object_key,
                ExtraArgs={"ContentType": CONTENT_TYPES[suffix]},
            )
            response = self.textract.start_document_analysis(
                DocumentLocation={"S3Object": {"Bucket": self.bucket, "Name": object_key}},
                FeatureTypes=["TABLES"],
                ClientRequestToken=request_token,
                JobTag="b2b-order-agent-dev",
            )
        except (BotoCoreError, ClientError, OSError) as exc:
            raise AwsDocumentProcessingError(f"AWS could not start document analysis: {exc}") from exc

        return TextractJobStart(
            job_id=response["JobId"],
            bucket=self.bucket,
            object_key=object_key,
        )

    def get_table_analysis(self, job_id: str) -> TextractJobResult:
        try:
            first_page = self.textract.get_document_analysis(JobId=job_id)
        except (BotoCoreError, ClientError) as exc:
            raise AwsDocumentProcessingError(f"AWS could not retrieve document analysis: {exc}") from exc

        status = first_page["JobStatus"]
        if status != "SUCCEEDED":
            return TextractJobResult(
                job_id=job_id,
                status=status,
                status_message=first_page.get("StatusMessage"),
                pages=first_page.get("DocumentMetadata", {}).get("Pages"),
                warnings=first_page.get("Warnings", []),
            )

        responses = [first_page]
        next_token = first_page.get("NextToken")
        while next_token:
            try:
                page = self.textract.get_document_analysis(JobId=job_id, NextToken=next_token)
            except (BotoCoreError, ClientError) as exc:
                raise AwsDocumentProcessingError(f"AWS could not retrieve all analysis pages: {exc}") from exc
            responses.append(page)
            next_token = page.get("NextToken")

        blocks = [block for response in responses for block in response.get("Blocks", [])]
        return TextractJobResult(
            job_id=job_id,
            status=status,
            pages=first_page.get("DocumentMetadata", {}).get("Pages"),
            lines=self._extract_lines(blocks),
            tables=self._extract_tables(blocks),
            warnings=[warning for response in responses for warning in response.get("Warnings", [])],
        )

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = Path(filename).name
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
        return safe_name or "document.tiff"

    @staticmethod
    def _extract_lines(blocks: list[dict[str, Any]]) -> list[TextractLine]:
        return [
            TextractLine(page=block.get("Page"), text=block.get("Text", ""), confidence=block.get("Confidence"))
            for block in blocks
            if block.get("BlockType") == "LINE" and block.get("Text")
        ]

    @staticmethod
    def _extract_tables(blocks: list[dict[str, Any]]) -> list[TextractTable]:
        by_id = {block["Id"]: block for block in blocks if block.get("Id")}
        tables: list[TextractTable] = []
        for table_block in (block for block in blocks if block.get("BlockType") == "TABLE"):
            cells: list[TextractTableCell] = []
            for cell_id in AwsDocumentProcessingService._relationship_ids(table_block, "CHILD"):
                cell = by_id.get(cell_id)
                if not cell or cell.get("BlockType") != "CELL":
                    continue
                words: list[str] = []
                for child_id in AwsDocumentProcessingService._relationship_ids(cell, "CHILD"):
                    child = by_id.get(child_id, {})
                    if child.get("BlockType") == "WORD" and child.get("Text"):
                        words.append(child["Text"])
                    elif child.get("BlockType") == "SELECTION_ELEMENT" and child.get("SelectionStatus") == "SELECTED":
                        words.append("X")
                cells.append(
                    TextractTableCell(
                        row=cell.get("RowIndex", 0),
                        column=cell.get("ColumnIndex", 0),
                        text=" ".join(words),
                        confidence=cell.get("Confidence"),
                    )
                )
            tables.append(TextractTable(page=table_block.get("Page"), cells=sorted(cells, key=lambda item: (item.row, item.column))))
        return tables

    @staticmethod
    def _relationship_ids(block: dict[str, Any], relationship_type: str) -> list[str]:
        return [
            relationship_id
            for relationship in block.get("Relationships", [])
            if relationship.get("Type") == relationship_type
            for relationship_id in relationship.get("Ids", [])
        ]
