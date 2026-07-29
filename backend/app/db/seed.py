from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.attachment import Attachment
from app.models.base import Base
from app.models.client import Client
from app.models.email import Email
from app.models.feedback_issue import FeedbackIssue
from app.models.generated_xml import GeneratedXML
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.user import User
from app.models.validation_issue import ValidationIssue


def seed_database(db: Session, *, include_demo_data: bool = False) -> None:
    admin = db.scalar(select(User).where(User.email == "admin@example.com"))
    if admin is None:
        admin = User(
            full_name="Endi Hyseni",
            email="admin@example.com",
            password_hash=hash_password("Admin123!"),
            role="admin",
        )
        db.add(admin)

    operator = db.scalar(select(User).where(User.email == "operator@example.com"))
    if operator is None:
        operator = User(
            full_name="Imane Operator",
            email="operator@example.com",
            password_hash=hash_password("Operator123!"),
            role="operator",
        )
        db.add(operator)
    db.flush()

    if not include_demo_data:
        db.commit()
        return
    if db.scalar(select(Email).where(Email.external_message_id == "MSG-W3-1")):
        db.commit()
        return

    required_fields = [
        "ticket_number",
        "customer_number",
        "commission_number",
        "delivery_address",
        "article_number",
        "quantity",
    ]
    northwind = Client(
        client_name="Northwind Retail Group",
        customer_number="CUST-1001",
        default_email="orders@northwind.example",
        email_domain="northwind.example",
        extraction_prompt="Extract Northwind retail order header and item fields with source and confidence.",
        required_fields=required_fields,
        validation_rules={"currency_required_when_price_present": True, "scanned_requires_review": True},
    )
    contoso = Client(
        client_name="Contoso Interior Supply",
        customer_number="CUST-2002",
        default_email="orders@contoso.example",
        email_domain="contoso.example",
        extraction_prompt="Extract Contoso interior supply orders and preserve commission references.",
        required_fields=required_fields,
        validation_rules={"currency_required_when_price_present": True, "scanned_requires_review": True},
    )
    db.add_all([northwind, contoso])
    db.flush()

    now = datetime.now(UTC).replace(tzinfo=None)
    scenarios = [
        ("OK", northwind, "TCK-10001", "COM-5001", False, "northwind_order_10001.pdf"),
        ("Human in the Loop", northwind, "TCK-10002", "COM-5002", True, "northwind_scan_10002.pdf"),
        ("Waiting for Reply", contoso, "TCK-10003", None, False, "contoso_order_10003.docx"),
        ("Failed", contoso, "TCK-10004", "COM-5004", False, "contoso_corrupted_10004.bin"),
        ("ERP Ready", northwind, "TCK-10005", "COM-5005", False, "northwind_order_10005.xlsx"),
    ]

    for index, (status, client, ticket, commission, scanned, attachment_name) in enumerate(scenarios, start=1):
        email = Email(
            external_message_id=f"MSG-W3-{index}",
            conversation_id=f"CONV-W3-{index if index != 3 else 30}",
            sender_email=f"buyer{index}@{client.email_domain}",
            reply_to_email=f"buyer{index}@{client.email_domain}",
            mail_to_email="orders@supplier.example",
            subject=f"Purchase order {ticket}",
            body=f"Please process order {ticket} for {client.client_name}.",
            received_at=now - timedelta(days=index),
            classification_status="order",
            client_id=client.id,
        )
        db.add(email)
        db.flush()
        order = Order(
            email_id=email.id,
            client_id=client.id,
            ticket_number=ticket,
            customer_number=client.customer_number,
            customer_name=client.client_name,
            commission_number=commission,
            commission_name=f"Store rollout {index}",
            store_address=f"{index} Market Street, Example City",
            delivery_address=f"{index} Warehouse Avenue, Example City",
            delivery_week=f"2026-W{28 + index}",
            order_date=now.date() - timedelta(days=index),
            requested_delivery_date=now.date() + timedelta(days=7 + index),
            contact_person=f"Buyer {index}",
            phone_number=f"+1-555-010{index}",
            total_price=Decimal("450.00") + Decimal(index * 100),
            currency="EUR",
            status=status,
            is_scanned_source=scanned,
            approved_by_user_id=admin.id if status == "ERP Ready" else None,
            approved_at=now - timedelta(hours=4) if status == "ERP Ready" else None,
        )
        db.add(order)
        db.flush()
        db.add(
            Attachment(
                email_id=email.id,
                order_id=order.id,
                file_name=attachment_name,
                file_type=attachment_name.split(".")[-1],
                file_path=f"storage/attachments/{attachment_name}",
                is_scanned=scanned,
            )
        )
        item_count = 2 if index in (1, 5) else 1
        for item_index in range(1, item_count + 1):
            quantity = 3 + item_index
            unit_price = Decimal("75.00") + Decimal(index * 10)
            db.add(
                OrderItem(
                    order_id=order.id,
                    article_number=f"ART-{index:02d}-{item_index:02d}",
                    model_number=f"MODEL-{chr(64 + index)}{item_index}",
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=unit_price * quantity,
                    currency="EUR",
                )
            )
        if status == "Waiting for Reply":
            db.add(
                ValidationIssue(
                    order_id=order.id,
                    field_name="commission_number",
                    issue_type="missing_required_field",
                    message="missing commission number",
                    severity="error",
                )
            )
        if status == "Human in the Loop":
            db.add(
                ValidationIssue(
                    order_id=order.id,
                    field_name="attachments",
                    issue_type="manual_review_required",
                    message="scanned or image document requires Human in the Loop review",
                    severity="warning",
                )
            )
        if status == "ERP Ready":
            generated_at = now - timedelta(hours=3)
            db.add_all(
                [
                    GeneratedXML(
                        order_id=order.id,
                        xml_type="header",
                        file_path=f"storage/xml/{order.id}/header.xml",
                        status="generated",
                        generated_at=generated_at,
                    ),
                    GeneratedXML(
                        order_id=order.id,
                        xml_type="items",
                        file_path=f"storage/xml/{order.id}/items.xml",
                        status="generated",
                        generated_at=generated_at,
                    ),
                ]
            )

    db.add(
        FeedbackIssue(
            category="extraction",
            title="Verify scanned order confidence",
            description="Sample issue for the Feedback & Issues page.",
            status="Open",
            reported_by_user_id=operator.id,
        )
    )
    db.commit()


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db, include_demo_data=settings.seed_demo_data)


if __name__ == "__main__":
    main()
