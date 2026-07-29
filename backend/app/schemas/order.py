from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.client import ClientOut
from app.schemas.order_item import OrderItemOut


class EmailMetadataOut(BaseModel):
    id: str
    sender_email: str
    reply_to_email: str | None
    mail_to_email: str | None
    subject: str
    received_at: datetime
    classification_status: str

    model_config = {"from_attributes": True}


class AttachmentOut(BaseModel):
    id: str
    file_name: str
    file_type: str
    file_path: str
    is_scanned: bool
    processing_status: str
    textract_job_id: str | None
    extracted_text: str | None
    processing_error: str | None
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class ValidationIssueOut(BaseModel):
    id: str
    field_name: str
    issue_type: str
    message: str
    severity: str
    is_resolved: bool

    model_config = {"from_attributes": True}


class GeneratedXmlOut(BaseModel):
    id: str
    xml_type: str
    file_path: str
    status: str
    generated_at: datetime
    sent_at: datetime | None

    model_config = {"from_attributes": True}


class OrderListOut(BaseModel):
    id: str
    ticket_number: str | None
    commission_number: str | None
    customer_name: str | None
    delivery_week: str | None
    status: str
    created_at: datetime
    client: ClientOut

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    items: list[OrderListOut]
    total: int
    page: int
    page_size: int


class OrderDetailOut(OrderListOut):
    email: EmailMetadataOut
    items: list[OrderItemOut]
    attachments: list[AttachmentOut]
    validation_issues: list[ValidationIssueOut]
    generated_xmls: list[GeneratedXmlOut]
    customer_number: str | None
    commission_name: str | None
    store_address: str | None
    delivery_address: str | None
    order_date: date | None
    requested_delivery_date: date | None
    contact_person: str | None
    phone_number: str | None
    total_price: Decimal | None
    currency: str | None
    approved_at: datetime | None


class OrderUpdate(BaseModel):
    ticket_number: str | None = None
    customer_number: str | None = None
    customer_name: str | None = None
    commission_number: str | None = None
    commission_name: str | None = None
    store_address: str | None = None
    delivery_address: str | None = None
    delivery_week: str | None = None
    order_date: date | None = None
    requested_delivery_date: date | None = None
    contact_person: str | None = None
    phone_number: str | None = None
    total_price: Decimal | None = None
    currency: str | None = None


class RejectRequest(BaseModel):
    reason: str


class ReportIssueRequest(BaseModel):
    category: str
    title: str
    description: str


class XmlActionResponse(BaseModel):
    status: str
    message: str
    files: list[str] = []
