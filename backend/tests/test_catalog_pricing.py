from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audit_event import AuditEvent
from app.models.client import Client
from app.models.email import Email
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.services.catalog_pricing import apply_catalog_prices


def test_catalog_fills_only_missing_matching_prices_and_audits():
    with SessionLocal() as db:
        client = Client(client_name="Pricing test", customer_number=str(uuid4()), email_domain="pricing.example",
                        extraction_prompt="Test", master_data_enabled=True)
        other = Client(client_name="Other", customer_number=str(uuid4()), email_domain="other.example", extraction_prompt="Test")
        email = Email(external_message_id=str(uuid4()), sender_email="orders@pricing.example", subject="Pricing", body="Test",
                      received_at=datetime.now(UTC), classification_status="order")
        order = Order(client=client, email=email, status="Processing", items=[
            OrderItem(article_number="A", quantity=2), OrderItem(article_number="ALIAS", quantity=1),
            OrderItem(article_number="A", quantity=1, unit_price=Decimal("99"), currency="EUR"),
            OrderItem(article_number="A", quantity=1, currency="USD"),
            OrderItem(article_number="A", quantity=1, total_price=Decimal("88")),
            OrderItem(article_number="OTHER-ONLY", quantity=1),
        ])
        db.add_all([order, other])
        db.flush()
        db.add_all([Product(client_id=client.id, sku="A", aliases=["ALIAS"], description="Example", unit_price=Decimal("12.50"), currency="EUR"),
                    Product(client_id=other.id, sku="OTHER-ONLY", description="Other", unit_price=1, currency="EUR")])
        db.flush()
        assert apply_catalog_prices(db, order) == 2
        assert order.items[0].total_price == Decimal("25.00")
        assert order.items[2].unit_price == Decimal("99")
        assert all(item.unit_price is None for item in order.items[3:])
        assert apply_catalog_prices(db, order) == 0
        db.flush()
        assert len(list(db.scalars(select(AuditEvent).where(AuditEvent.order_id == order.id)))) == 2
        order.items[0].unit_price = None
        order.approved_at = datetime.now(UTC)
        assert apply_catalog_prices(db, order) == 0
        db.rollback()
