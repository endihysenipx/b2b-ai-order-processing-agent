from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import accessible_client_ids, get_current_user, require_admin
from app.db.session import get_db
from app.models.feedback_issue import FeedbackIssue
from app.models.generated_xml import GeneratedXML
from app.models.order import Order
from app.models.order_item import OrderItem
from app.repositories.orders import build_order_query, get_order
from app.schemas.feedback import FeedbackIssueOut
from app.schemas.order import (
    OrderDetailOut,
    OrderListResponse,
    OrderUpdate,
    RejectRequest,
    ReportIssueRequest,
    XmlActionResponse,
)
from app.schemas.order_item import OrderItemUpdate
from app.services.validation.service import validate_order_data
from app.services.xml.service import generate_header_xml, generate_items_xml, simulate_send_xml

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=OrderListResponse)
def list_orders(
    status: str | None = None,
    client_id: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    is_demo: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> OrderListResponse:
    query = build_order_query(
        status,
        client_id,
        search,
        date_from,
        date_to,
        accessible_client_ids=accessible_client_ids(current_user),
        is_demo=is_demo,
    )
    all_items = list(db.scalars(query).unique())
    start = (page - 1) * page_size
    return OrderListResponse(
        items=all_items[start : start + page_size], total=len(all_items), page=page, page_size=page_size
    )


@router.get("/{order_id}", response_model=OrderDetailOut)
def get_order_detail(order_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> Order:
    order = get_order(db, order_id, accessible_client_ids(current_user))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}", response_model=OrderDetailOut)
def update_order(
    order_id: str,
    payload: OrderUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Order:
    order = get_order(db, order_id, accessible_client_ids(current_user))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(order, field, value)
    db.commit()
    return get_order(db, order_id, accessible_client_ids(current_user))


@router.patch("/{order_id}/items/{item_id}", response_model=OrderDetailOut)
def update_order_item(
    order_id: str,
    item_id: str,
    payload: OrderItemUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Order:
    order = get_order(db, order_id, accessible_client_ids(current_user))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    item = db.get(OrderItem, item_id)
    if item is None or item.order_id != order_id:
        raise HTTPException(status_code=404, detail="Order item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    if item.quantity is not None and item.unit_price is not None:
        item.total_price = item.quantity * item.unit_price
    db.commit()
    return get_order(db, order_id, accessible_client_ids(current_user))


@router.post("/{order_id}/approve", response_model=OrderDetailOut)
def approve_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Order:
    order = get_order(db, order_id, accessible_client_ids(current_user))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = "Approved"
    order.approved_by_user_id = current_user.id
    order.approved_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return get_order(db, order_id, accessible_client_ids(current_user))


@router.post("/{order_id}/reject", response_model=OrderDetailOut)
def reject_order(
    order_id: str,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Order:
    if not payload.reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required")
    order = get_order(db, order_id, accessible_client_ids(current_user))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = "Rejected"
    issue = FeedbackIssue(
        order_id=order.id,
        category="rejection",
        title="Order rejected",
        description=payload.reason,
        status="Open",
    )
    db.add(issue)
    db.commit()
    return get_order(db, order_id, accessible_client_ids(current_user))


@router.post("/{order_id}/report-issue", response_model=FeedbackIssueOut)
def report_order_issue(
    order_id: str,
    payload: ReportIssueRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> FeedbackIssue:
    if get_order(db, order_id, accessible_client_ids(current_user)) is None:
        raise HTTPException(status_code=404, detail="Order not found")
    issue = FeedbackIssue(
        order_id=order_id,
        category=payload.category,
        title=payload.title,
        description=payload.description,
        status="Open",
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


@router.post("/{order_id}/validate", response_model=list[dict])
def validate_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[dict]:
    order = get_order(db, order_id, accessible_client_ids(current_user))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
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
            for item in order.items
        ],
        is_scanned_source=order.is_scanned_source,
    )
    return [issue.__dict__ for issue in issues]


@router.post("/{order_id}/generate-xml", response_model=XmlActionResponse)
def generate_xml(
    order_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
) -> XmlActionResponse:
    order = get_order(db, order_id, accessible_client_ids(current_user))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    header_path = generate_header_xml(order)
    items_path = generate_items_xml(order)
    now = datetime.now(UTC).replace(tzinfo=None)
    for xml_type, path in [("header", header_path), ("items", items_path)]:
        existing = db.scalar(
            select(GeneratedXML).where(GeneratedXML.order_id == order.id, GeneratedXML.xml_type == xml_type)
        )
        if existing:
            existing.file_path = path
            existing.status = "generated"
            existing.generated_at = now
            existing.sent_at = None
        else:
            db.add(
                GeneratedXML(order_id=order.id, xml_type=xml_type, file_path=path, status="generated", generated_at=now)
            )
    order.status = "ERP Ready"
    db.commit()
    return XmlActionResponse(
        status="ERP Ready", message="Header and Items XML generated.", files=[header_path, items_path]
    )


@router.post("/{order_id}/send-xml", response_model=XmlActionResponse)
def send_xml(
    order_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
) -> XmlActionResponse:
    order = get_order(db, order_id, accessible_client_ids(current_user))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if len(order.generated_xmls) < 2:
        raise HTTPException(status_code=400, detail="Generate Header and Items XML before sending")
    simulated = simulate_send_xml(order)
    sent_at = datetime.now(UTC).replace(tzinfo=None)
    for xml in order.generated_xmls:
        xml.status = "sent"
        xml.sent_at = sent_at
    order.status = "XMLs Sent"
    db.commit()
    return XmlActionResponse(
        status="XMLs Sent", message=simulated["message"], files=[xml.file_path for xml in order.generated_xmls]
    )
