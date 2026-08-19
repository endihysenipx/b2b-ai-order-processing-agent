import random
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.models.base import new_id
from app.models.client import Client
from app.models.email import Email
from app.models.feedback_issue import FeedbackIssue
from app.models.generated_xml import GeneratedXML
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.user import User
from app.models.validation_issue import ValidationIssue

DEMO_ORDER_COUNT = 1_000
DEMO_WINDOW_DAYS = 30
DEMO_CLIENT_PREFIX = "DEMO-"
DEMO_MESSAGE_PREFIX = "DEMO-DATA-"

STATUS_COUNTS = {
    "OK": 440,
    "Human in the Loop": 180,
    "Waiting for Reply": 130,
    "Approved": 80,
    "ERP Ready": 70,
    "XMLs Sent": 60,
    "Failed": 30,
    "Rejected": 10,
}

CLIENTS = (
    ("Alpine Workspace Demo", "DEMO-1001", "alpine-workspace.example"),
    ("Beacon Retail Demo", "DEMO-1002", "beacon-retail.example"),
    ("Cedar Hospitality Demo", "DEMO-1003", "cedar-hospitality.example"),
    ("Dunewood Interiors Demo", "DEMO-1004", "dunewood-interiors.example"),
    ("Evergreen Stores Demo", "DEMO-1005", "evergreen-stores.example"),
    ("Foundry Offices Demo", "DEMO-1006", "foundry-offices.example"),
)

PRODUCTS = (
    ("CHAIR-AERO", "AERO-01", Decimal("129.00")),
    ("DESK-LIFT", "LIFT-02", Decimal("549.00")),
    ("LAMP-NOVA", "NOVA-03", Decimal("79.50")),
    ("SHELF-MOD", "MOD-04", Decimal("235.00")),
    ("SOFA-LOUNGE", "LOUNGE-05", Decimal("899.00")),
    ("TABLE-MEET", "MEET-06", Decimal("680.00")),
    ("PANEL-ACOUSTIC", "QUIET-07", Decimal("118.00")),
    ("STORAGE-MOBILE", "MOBILE-08", Decimal("315.00")),
)


class DemoDataStatus(BaseModel):
    generated: bool
    order_count: int
    target_order_count: int = DEMO_ORDER_COUNT
    window_days: int = DEMO_WINDOW_DAYS
    date_from: date | None
    date_to: date | None
    client_count: int
    status_counts: dict[str, int]
    currency_value_totals: dict[str, str]
    message: str


def _demo_status(db: Session, message: str | None = None) -> DemoDataStatus:
    demo_filter = Order.is_demo.is_(True)
    order_count = db.scalar(select(func.count(Order.id)).where(demo_filter)) or 0
    status_counts = dict(
        db.execute(select(Order.status, func.count(Order.id)).where(demo_filter).group_by(Order.status)).all()
    )
    date_from, date_to = db.execute(
        select(func.min(func.date(Order.created_at)), func.max(func.date(Order.created_at))).where(demo_filter)
    ).one()
    client_count = (
        db.scalar(select(func.count(func.distinct(Order.client_id))).where(demo_filter)) or 0
    )
    currency_rows = db.execute(
        select(Order.currency, func.sum(Order.total_price))
        .where(demo_filter, Order.total_price.is_not(None))
        .group_by(Order.currency)
    )
    return DemoDataStatus(
        generated=order_count > 0,
        order_count=order_count,
        date_from=date_from,
        date_to=date_to,
        client_count=client_count,
        status_counts=status_counts,
        currency_value_totals={currency or "UNSPECIFIED": str(value) for currency, value in currency_rows},
        message=message
        or (
            "The synthetic demonstration dataset is ready."
            if order_count
            else "No synthetic demonstration orders exist yet."
        ),
    )


def get_demo_data_status(db: Session) -> DemoDataStatus:
    return _demo_status(db)


def generate_demo_data(db: Session, admin: User) -> DemoDataStatus:
    existing = db.scalar(select(func.count(Order.id)).where(Order.is_demo.is_(True))) or 0
    if existing:
        return _demo_status(db, f"Demo data already exists ({existing:,} orders); no duplicates were created.")

    rng = random.Random(20260819)
    now = datetime.now(UTC).replace(tzinfo=None)
    required_fields = [
        "ticket_number",
        "customer_number",
        "commission_number",
        "delivery_address",
        "article_number",
        "quantity",
    ]
    clients = [
        Client(
            id=new_id(),
            client_name=name,
            customer_number=customer_number,
            default_email=f"orders@{domain}",
            email_domain=domain,
            extraction_prompt="Synthetic demo client: extract order headers and line items with confidence evidence.",
            required_fields=required_fields,
            validation_rules={"currency_required_when_price_present": True, "scanned_requires_review": True},
        )
        for name, customer_number, domain in CLIENTS
    ]
    db.add_all(clients)

    statuses = [status for status, count in STATUS_COUNTS.items() for _ in range(count)]
    rng.shuffle(statuses)
    currencies = ("EUR", "EUR", "EUR", "USD", "GBP")
    objects: list[object] = []

    for index, status in enumerate(statuses, start=1):
        client = clients[(index - 1) % len(clients)]
        day_offset = (index - 1) % DEMO_WINDOW_DAYS
        created_date = now.date() - timedelta(days=day_offset)
        latest_minute = (now.hour * 60 + now.minute) if day_offset == 0 else (24 * 60 - 1)
        created_at = datetime.combine(created_date, time.min) + timedelta(minutes=rng.randint(0, latest_minute))
        order_date = created_at.date()
        delivery_date = order_date + timedelta(days=rng.randint(5, 28))
        delivery_year, delivery_week, _ = delivery_date.isocalendar()
        currency = rng.choice(currencies)
        ticket = f"DEMO-{index:06d}"
        order_id = new_id()
        email_id = new_id()
        is_scanned = status == "Human in the Loop"
        is_failed = status == "Failed"
        requires_commission = status != "Waiting for Reply" or index % 2 == 0
        commission = f"DM-COM-{rng.randint(10000, 99999)}" if requires_commission else None

        email = Email(
            id=email_id,
            external_message_id=f"{DEMO_MESSAGE_PREFIX}{index:06d}",
            conversation_id=f"DEMO-CONVERSATION-{(index - 1) // 3:06d}",
            sender_email=f"buyer{(index % 25) + 1}@{client.email_domain}",
            reply_to_email=f"buyer{(index % 25) + 1}@{client.email_domain}",
            mail_to_email="demo-orders@supplier.example",
            subject=f"[SYNTHETIC DEMO] Purchase order {ticket}",
            body=(
                "Synthetic demonstration message. It contains no customer data and must not be fulfilled. "
                f"Please process demo purchase order {ticket}."
            ),
            received_at=created_at,
            classification_status="order",
            client_id=client.id,
            created_at=created_at,
        )
        order = Order(
            id=order_id,
            email_id=email_id,
            client_id=client.id,
            ticket_number=ticket,
            customer_number=client.customer_number,
            customer_name=client.client_name,
            commission_number=commission,
            commission_name=f"Synthetic rollout phase {(index % 12) + 1}",
            store_address=f"{(index % 180) + 1} Demo Market Street, Example City",
            delivery_address=(
                None
                if status == "Waiting for Reply" and index % 2 == 0
                else f"{(index % 90) + 1} Simulation Warehouse Road, Example City"
            ),
            delivery_week=f"KW{delivery_week:02d}/{delivery_year}",
            order_date=order_date,
            requested_delivery_date=delivery_date,
            contact_person=f"Demo Buyer {(index % 25) + 1}",
            phone_number=f"+1-202-555-{(index % 10000):04d}",
            total_price=Decimal("0"),
            currency=currency,
            status=status,
            is_scanned_source=is_scanned,
            is_demo=True,
            approved_by_user_id=admin.id if status in {"Approved", "ERP Ready", "XMLs Sent"} else None,
            approved_at=(created_at + timedelta(hours=2)) if status in {"Approved", "ERP Ready", "XMLs Sent"} else None,
            created_at=created_at,
            updated_at=min(now, created_at + timedelta(hours=rng.randint(0, 36))),
        )
        total = Decimal("0")
        item_count = rng.randint(1, 5)
        for item_index in range(1, item_count + 1):
            article, model, unit_price = rng.choice(PRODUCTS)
            quantity = rng.randint(1, 24)
            line_total = unit_price * quantity
            total += line_total
            objects.append(
                OrderItem(
                    id=new_id(),
                    order_id=order_id,
                    article_number=f"{article}-{item_index:02d}",
                    model_number=model,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=line_total,
                    currency=currency,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
        order.total_price = total
        extension = "png" if is_scanned else "pdf"
        objects.extend(
            [
                email,
                order,
                Attachment(
                    id=new_id(),
                    email_id=email_id,
                    order_id=order_id,
                    file_name=f"synthetic_demo_order_{index:06d}.{extension}",
                    file_type=extension,
                    file_path=f"demo://attachments/{ticket}.{extension}",
                    is_scanned=is_scanned,
                    processing_status="failed" if is_failed else "succeeded",
                    extracted_text=(
                        f"SYNTHETIC DEMO DOCUMENT — {ticket} — no fulfillment permitted."
                        if not is_failed
                        else None
                    ),
                    processing_error="Synthetic corrupted-file scenario" if is_failed else None,
                    processed_at=None if is_failed else created_at + timedelta(minutes=8),
                    created_at=created_at,
                ),
            ]
        )

        if status == "Human in the Loop":
            objects.append(
                ValidationIssue(
                    id=new_id(),
                    order_id=order_id,
                    field_name="attachments",
                    issue_type="manual_review_required",
                    message="Synthetic scanned document requires human review.",
                    severity="warning",
                    created_at=created_at,
                )
            )
        elif status == "Waiting for Reply":
            field_name = "commission_number" if commission is None else "delivery_address"
            objects.append(
                ValidationIssue(
                    id=new_id(),
                    order_id=order_id,
                    field_name=field_name,
                    issue_type="missing_required_field",
                    message=f"Synthetic scenario is missing {field_name.replace('_', ' ')}.",
                    severity="error",
                    created_at=created_at,
                )
            )
        elif status == "Failed":
            objects.append(
                ValidationIssue(
                    id=new_id(),
                    order_id=order_id,
                    field_name="attachments",
                    issue_type="document_processing_failed",
                    message="Synthetic attachment processing failure.",
                    severity="error",
                    created_at=created_at,
                )
            )

        if status in {"ERP Ready", "XMLs Sent"}:
            generated_at = created_at + timedelta(hours=3)
            for xml_type in ("header", "items"):
                objects.append(
                    GeneratedXML(
                        id=new_id(),
                        order_id=order_id,
                        xml_type=xml_type,
                        file_path=f"demo://xml/{ticket}/{xml_type}.xml",
                        status="sent" if status == "XMLs Sent" else "generated",
                        generated_at=generated_at,
                        sent_at=generated_at + timedelta(minutes=10) if status == "XMLs Sent" else None,
                    )
                )
        if status == "Rejected":
            objects.append(
                FeedbackIssue(
                    id=new_id(),
                    order_id=order_id,
                    reported_by_user_id=admin.id,
                    category="synthetic-rejection",
                    title="Synthetic demo order rejected",
                    description="Demonstration scenario: duplicate commission reference.",
                    status="Open",
                    created_at=created_at,
                )
            )

    db.add_all(objects)
    db.commit()
    return _demo_status(db, "Created exactly 1,000 synthetic orders across the previous 30 days.")


def delete_demo_data(db: Session) -> DemoDataStatus:
    demo_order_ids = select(Order.id).where(Order.is_demo.is_(True))
    demo_email_ids = select(Email.id).where(Email.external_message_id.like(f"{DEMO_MESSAGE_PREFIX}%"))

    db.execute(delete(FeedbackIssue).where(FeedbackIssue.order_id.in_(demo_order_ids)))
    db.execute(delete(GeneratedXML).where(GeneratedXML.order_id.in_(demo_order_ids)))
    db.execute(delete(ValidationIssue).where(ValidationIssue.order_id.in_(demo_order_ids)))
    db.execute(delete(OrderItem).where(OrderItem.order_id.in_(demo_order_ids)))
    db.execute(
        delete(Attachment).where(
            Attachment.order_id.in_(demo_order_ids) | Attachment.email_id.in_(demo_email_ids)
        )
    )
    deleted = db.execute(delete(Order).where(Order.is_demo.is_(True))).rowcount or 0
    db.execute(delete(Email).where(Email.external_message_id.like(f"{DEMO_MESSAGE_PREFIX}%")))
    demo_customer_numbers = [customer_number for _, customer_number, _ in CLIENTS]
    db.execute(delete(Client).where(Client.customer_number.in_(demo_customer_numbers)))
    db.commit()
    return _demo_status(db, f"Removed {deleted:,} synthetic orders. Existing non-demo orders were not changed.")
