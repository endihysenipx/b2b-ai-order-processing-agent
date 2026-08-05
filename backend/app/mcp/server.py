import logging
from datetime import date
from decimal import Decimal
from urllib.parse import urlsplit

from jose import JWTError
from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import AuthContextMiddleware, get_access_token
from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend, RequireAuthMiddleware
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from starlette.middleware.authentication import AuthenticationMiddleware

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.attachment import Attachment
from app.models.order import Order
from app.models.user import User
from app.models.validation_issue import ValidationIssue
from app.repositories.orders import build_order_query, get_order
from app.services.validation.service import validate_order_data

logger = logging.getLogger(__name__)

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


class OrderSummary(BaseModel):
    id: str
    ticket_number: str | None
    commission_number: str | None
    customer_name: str | None
    client_name: str
    delivery_week: str | None
    status: str
    created_at: str


class SearchOrdersResult(BaseModel):
    orders: list[OrderSummary]
    returned: int
    total: int


class OrderItemResult(BaseModel):
    id: str
    article_number: str | None
    model_number: str | None
    quantity: int | None
    unit_price: str | None
    total_price: str | None
    currency: str | None


class ValidationIssueResult(BaseModel):
    field_name: str
    issue_type: str
    message: str
    severity: str
    is_resolved: bool


class AttachmentMetadata(BaseModel):
    id: str
    file_name: str
    file_type: str
    is_scanned: bool
    processing_status: str
    processed_at: str | None


class OrderDetailResult(BaseModel):
    id: str
    ticket_number: str | None
    customer_number: str | None
    customer_name: str | None
    client_name: str
    commission_number: str | None
    commission_name: str | None
    delivery_address: str | None
    delivery_week: str | None
    order_date: str | None
    requested_delivery_date: str | None
    total_price: str | None
    currency: str | None
    status: str
    is_scanned_source: bool
    created_at: str
    approved_at: str | None
    email_subject: str
    items: list[OrderItemResult]
    validation_issues: list[ValidationIssueResult]
    attachments: list[AttachmentMetadata]


class EvidenceAttachment(BaseModel):
    id: str
    file_name: str
    file_type: str
    is_scanned: bool
    processing_status: str
    extracted_text_excerpt: str | None
    processing_error: str | None


class OrderEvidenceResult(BaseModel):
    order_id: str
    email_subject: str
    email_received_at: str
    email_classification_status: str
    email_body_excerpt: str
    attachments: list[EvidenceAttachment]
    text_was_truncated: bool


class ValidationResult(BaseModel):
    order_id: str
    persisted_issues: list[ValidationIssueResult]
    current_issues: list[ValidationIssueResult]


class ProcessingSummaryResult(BaseModel):
    date_from: str | None
    date_to: str | None
    total_orders: int
    orders_by_status: dict[str, int]
    attachments_by_processing_status: dict[str, int]
    unresolved_validation_issues: int


class ApplicationJwtVerifier(TokenVerifier):
    """Validate the same short-lived JWT bearer tokens used by the web API."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            expires_at = payload.get("exp")
        except JWTError:
            return None

        if (
            not isinstance(user_id, str)
            or not user_id
            or payload.get("token_type") != "access"
            or "otp" not in payload.get("amr", [])
        ):
            return None

        with SessionLocal() as db:
            user = db.get(User, user_id)
            if user is None or not user.is_active:
                return None
            if payload.get("auth_version") != user.auth_version:
                return None
            role = user.role
            client_ids = [client.id for client in user.clients]

        return AccessToken(
            token=token,
            client_id="b2b-order-processing-agent",
            scopes=["orders:read", f"role:{role}"],
            expires_at=int(expires_at) if expires_at is not None else None,
            subject=user_id,
            claims={"role": role, "client_ids": client_ids},
        )


def _transport_security() -> TransportSecuritySettings:
    frontend = urlsplit(settings.frontend_url)
    allowed_hosts = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*", "testserver"]
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    if frontend.hostname:
        allowed_hosts.extend([frontend.hostname, f"{frontend.hostname}:*"])
    if frontend.netloc:
        allowed_hosts.append(frontend.netloc)
    if frontend.scheme and frontend.netloc:
        allowed_origins.append(f"{frontend.scheme}://{frontend.netloc}")

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(dict.fromkeys(allowed_hosts)),
        allowed_origins=list(dict.fromkeys(allowed_origins)),
    )


def _decimal(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _excerpt(value: str | None, max_chars: int) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    if len(value) <= max_chars:
        return value, False
    return f"{value[:max_chars].rstrip()}…", True


def _audit(tool_name: str, order_id: str | None = None) -> None:
    token = get_access_token()
    logger.info(
        "MCP read tool invoked: tool=%s user_id=%s order_id=%s",
        tool_name,
        token.subject if token else "unknown",
        order_id,
    )


def _accessible_client_ids() -> set[str] | None:
    token = get_access_token()
    if token is None:
        return set()
    if token.claims.get("role") == "admin":
        return None
    return set(token.claims.get("client_ids", []))


def _summary(order: Order) -> OrderSummary:
    return OrderSummary(
        id=order.id,
        ticket_number=order.ticket_number,
        commission_number=order.commission_number,
        customer_name=order.customer_name,
        client_name=order.client.client_name,
        delivery_week=order.delivery_week,
        status=order.status,
        created_at=order.created_at.isoformat(),
    )


def _validation_issue(issue, *, is_resolved: bool | None = None) -> ValidationIssueResult:
    return ValidationIssueResult(
        field_name=issue.field_name,
        issue_type=issue.issue_type,
        message=issue.message,
        severity=issue.severity,
        is_resolved=issue.is_resolved if is_resolved is None else is_resolved,
    )


server = MCPServer(
    name="b2b-order-processing",
    title="B2B Order Processing",
    version="1.0.0",
    instructions=(
        "Use these read-only tools to find and explain B2B orders. "
        "Never claim that an order was changed, approved, emailed, exported, or sent to ERP. "
        "Use get_order_evidence only when source evidence is necessary for the user's request."
    ),
)


@server.tool(
    title="Search orders",
    description="Find orders by workflow status, client, text, or creation date. Use this before requesting one order by ID.",
    annotations=READ_ONLY,
)
def search_orders(
    status: str | None = None,
    client_id: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Field(default=20, ge=1, le=100),
) -> SearchOrdersResult:
    _audit("search_orders")
    with SessionLocal() as db:
        query = build_order_query(
            status,
            client_id,
            search,
            date_from,
            date_to,
            accessible_client_ids=_accessible_client_ids(),
        )
        total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
        selected = list(db.scalars(query.limit(limit)).unique())
        return SearchOrdersResult(
            orders=[_summary(order) for order in selected],
            returned=len(selected),
            total=total,
        )


@server.tool(
    title="Get order",
    description="Get structured details for one order, including items, attachment metadata, and persisted validation issues.",
    annotations=READ_ONLY,
)
def get_order_details(order_id: str) -> OrderDetailResult:
    _audit("get_order_details", order_id)
    with SessionLocal() as db:
        order = get_order(db, order_id, _accessible_client_ids())
        if order is None:
            raise ValueError("Order not found")

        return OrderDetailResult(
            id=order.id,
            ticket_number=order.ticket_number,
            customer_number=order.customer_number,
            customer_name=order.customer_name,
            client_name=order.client.client_name,
            commission_number=order.commission_number,
            commission_name=order.commission_name,
            delivery_address=order.delivery_address,
            delivery_week=order.delivery_week,
            order_date=_iso(order.order_date),
            requested_delivery_date=_iso(order.requested_delivery_date),
            total_price=_decimal(order.total_price),
            currency=order.currency,
            status=order.status,
            is_scanned_source=order.is_scanned_source,
            created_at=order.created_at.isoformat(),
            approved_at=_iso(order.approved_at),
            email_subject=order.email.subject,
            items=[
                OrderItemResult(
                    id=item.id,
                    article_number=item.article_number,
                    model_number=item.model_number,
                    quantity=item.quantity,
                    unit_price=_decimal(item.unit_price),
                    total_price=_decimal(item.total_price),
                    currency=item.currency,
                )
                for item in order.items
            ],
            validation_issues=[_validation_issue(issue) for issue in order.validation_issues],
            attachments=[
                AttachmentMetadata(
                    id=attachment.id,
                    file_name=attachment.file_name,
                    file_type=attachment.file_type,
                    is_scanned=attachment.is_scanned,
                    processing_status=attachment.processing_status,
                    processed_at=_iso(attachment.processed_at),
                )
                for attachment in order.attachments
            ],
        )


@server.tool(
    title="Get order evidence",
    description=(
        "Get bounded excerpts of the source email and extracted attachment text for one order. "
        "Call this only when source evidence is needed to answer the user."
    ),
    annotations=READ_ONLY,
)
def get_order_evidence(
    order_id: str,
    max_chars_per_source: int = Field(default=4000, ge=200, le=10000),
) -> OrderEvidenceResult:
    _audit("get_order_evidence", order_id)
    with SessionLocal() as db:
        order = get_order(db, order_id, _accessible_client_ids())
        if order is None:
            raise ValueError("Order not found")

        email_excerpt, email_truncated = _excerpt(order.email.body, max_chars_per_source)
        text_was_truncated = email_truncated
        attachments = []
        for attachment in order.attachments:
            extracted_text, was_truncated = _excerpt(attachment.extracted_text, max_chars_per_source)
            text_was_truncated = text_was_truncated or was_truncated
            attachments.append(
                EvidenceAttachment(
                    id=attachment.id,
                    file_name=attachment.file_name,
                    file_type=attachment.file_type,
                    is_scanned=attachment.is_scanned,
                    processing_status=attachment.processing_status,
                    extracted_text_excerpt=extracted_text,
                    processing_error=attachment.processing_error,
                )
            )

        return OrderEvidenceResult(
            order_id=order.id,
            email_subject=order.email.subject,
            email_received_at=order.email.received_at.isoformat(),
            email_classification_status=order.email.classification_status,
            email_body_excerpt=email_excerpt or "",
            attachments=attachments,
            text_was_truncated=text_was_truncated,
        )


@server.tool(
    title="Get validation issues",
    description="Explain persisted and currently computed validation issues for one order without changing it.",
    annotations=READ_ONLY,
)
def get_validation_issues(order_id: str) -> ValidationResult:
    _audit("get_validation_issues", order_id)
    with SessionLocal() as db:
        order = get_order(db, order_id, _accessible_client_ids())
        if order is None:
            raise ValueError("Order not found")

        current = validate_order_data(
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
                for item in order.items
            ],
            is_scanned_source=order.is_scanned_source,
        )
        return ValidationResult(
            order_id=order.id,
            persisted_issues=[_validation_issue(issue) for issue in order.validation_issues],
            current_issues=[_validation_issue(issue, is_resolved=False) for issue in current],
        )


@server.tool(
    title="Get processing summary",
    description="Summarize order statuses, attachment processing, and unresolved validation work for an optional date range.",
    annotations=READ_ONLY,
)
def get_processing_summary(
    date_from: date | None = None,
    date_to: date | None = None,
) -> ProcessingSummaryResult:
    _audit("get_processing_summary")
    with SessionLocal() as db:
        order_filters = []
        allowed = _accessible_client_ids()
        if allowed is not None:
            order_filters.append(Order.client_id.in_(allowed) if allowed else Order.id.is_(None))
        if date_from is not None:
            order_filters.append(func.date(Order.created_at) >= date_from)
        if date_to is not None:
            order_filters.append(func.date(Order.created_at) <= date_to)

        status_query = select(Order.status, func.count(Order.id)).group_by(Order.status)
        if order_filters:
            status_query = status_query.where(*order_filters)
        orders_by_status = {status: count for status, count in db.execute(status_query)}

        attachment_query = (
            select(Attachment.processing_status, func.count(Attachment.id))
            .join(Order, Attachment.order_id == Order.id)
            .group_by(Attachment.processing_status)
        )
        if order_filters:
            attachment_query = attachment_query.where(*order_filters)
        attachments_by_status = {status: count for status, count in db.execute(attachment_query)}

        unresolved_query = (
            select(func.count())
            .select_from(Order)
            .join(ValidationIssue, ValidationIssue.order_id == Order.id)
            .where(ValidationIssue.is_resolved.is_(False))
        )
        if order_filters:
            unresolved_query = unresolved_query.where(*order_filters)
        unresolved = db.scalar(unresolved_query) or 0

        return ProcessingSummaryResult(
            date_from=date_from.isoformat() if date_from else None,
            date_to=date_to.isoformat() if date_to else None,
            total_orders=sum(orders_by_status.values()),
            orders_by_status=orders_by_status,
            attachments_by_processing_status=attachments_by_status,
            unresolved_validation_issues=unresolved,
        )


lifespan_app = server.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    transport_security=_transport_security(),
)

# The application currently issues first-party JWTs rather than OAuth tokens.
# Apply the SDK's bearer-token middleware directly so phase-one MCP clients can
# reuse those JWTs without advertising an OAuth discovery flow we do not serve.
http_app = AuthenticationMiddleware(
    AuthContextMiddleware(
        RequireAuthMiddleware(
            lifespan_app,
            required_scopes=["orders:read"],
        )
    ),
    backend=BearerAuthBackend(ApplicationJwtVerifier()),
)
