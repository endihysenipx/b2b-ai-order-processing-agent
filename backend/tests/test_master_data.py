from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.client import Client
from app.models.product import Product
from app.services.decision.service import decide_order_status
from app.services.validation.service import ValidationResult, validate_order_data


@pytest.fixture
def catalog():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        customer = Client(
            client_name="Test", customer_number="C1", email_domain="example.test", extraction_prompt="", master_data_enabled=True, approved_delivery_addresses=["Test Address"]
        )
        db.add(customer)
        db.flush()
        product = Product(
            client_id=customer.id,
            sku="SKU1",
            description="Test",
            aliases=["ALIAS"],
            unit_price=Decimal("10.00"),
            currency="EUR",
            on_hand=12,
            reserved=2,
            stock_updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(product)
        db.commit()
        yield db, customer, product
    engine.dispose()


def check(catalog, items=None):
    db, customer, _ = catalog
    return validate_order_data(
        dict(ticket_number="T", customer_number="C1", commission_number="C", delivery_address="test  address"),
        items if items is not None else [dict(article_number="ALIAS", quantity=5, unit_price=10, currency="EUR")],
        db=db,
        client_id=customer.id,
    )


def test_valid_alias_and_combined_shortage(catalog):
    assert check(catalog) == []
    issues = check(catalog, [dict(article_number=sku, quantity=6, unit_price=10, currency="EUR") for sku in ["SKU1", "ALIAS"]])
    assert {i.issue_type for i in issues} == {"stock_shortage"}
    assert decide_order_status(issues) == "Human in the Loop"


def test_stale_unknown_price_and_inactive(catalog):
    _, customer, product = catalog
    product.stock_updated_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2)
    product.is_active = False
    customer.is_active = False
    customer.approved_delivery_addresses = []
    product.unit_price = Decimal("11")
    kinds = {i.issue_type for i in check(catalog)}
    assert {"stock_stale", "inactive_customer", "inactive_product", "address_unverified", "price_mismatch"} <= kinds
    product.on_hand = None
    assert "stock_unknown" in {i.issue_type for i in check(catalog)}


def test_unknown_product_and_empty_order(catalog):
    assert "unknown_product" in {i.issue_type for i in check(catalog, [dict(article_number="OTHER", quantity=1)])}
    assert decide_order_status(check(catalog, [])) == "Waiting for Reply"


def test_errors_and_warnings_require_review():
    for severity in ["error", "warning"]:
        assert decide_order_status([ValidationResult("quantity", "invalid_quantity", "Invalid", severity)]) == "Human in the Loop"
    assert decide_order_status([]) == "OK"


def test_incorrect_line_total_requires_review(catalog):
    issues = check(catalog, [dict(article_number="SKU1", quantity=5, unit_price=10,
                                 total_price=1, currency="EUR")])
    assert any(issue.field_name == "items[1].total_price" for issue in issues)
    assert decide_order_status(issues) == "Human in the Loop"


def test_stock_api_timestamp_can_be_saved_again(catalog):
    from app.schemas.master_data import ProductInput, ProductOut

    _, _, product = catalog
    payload = ProductOut.model_validate(product).model_dump(mode="json", exclude={"id", "client_id"})
    assert payload["stock_updated_at"].endswith("Z")
    assert ProductInput.model_validate(payload).stock_updated_at.tzinfo == UTC


@pytest.mark.parametrize("stock", [
    {"on_hand": 2, "reserved": 3, "stock_updated_at": "2026-01-01T00:00:00Z"},
    {"on_hand": 2, "stock_updated_at": "2026-01-01T00:00:00"},
    {"on_hand": 2, "stock_updated_at": "2099-01-01T00:00:00Z"},
])
def test_invalid_stock_observations_are_rejected(stock):
    from pydantic import ValidationError

    from app.schemas.master_data import ProductInput

    with pytest.raises(ValidationError):
        ProductInput(sku="SKU", description="Test", **stock)


def test_api_validation_conflicts_and_auth(client, auth_headers):
    customers = client.get("/api/v1/clients", headers=auth_headers).json()
    path = f"/api/v1/clients/{customers[0]['id']}/products"
    assert client.get(path).status_code == 401
    assert client.post(path, headers=auth_headers, json={"sku": "TEST", "description": "Test", "reserved": 1}).status_code == 422
    response = client.post(path, headers=auth_headers, json={"sku": "TEST", "description": "Test", "aliases": ["ALT"]})
    assert response.status_code == 201
    assert client.post(path, headers=auth_headers, json={"sku": "ALT", "description": "Conflict"}).status_code == 409
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        db.delete(db.get(Product, response.json()["id"]))
        db.commit()


def test_enabled_customer_blocks_approval_and_export(client, auth_headers):
    from app.db.session import SessionLocal
    from app.models.email import Email
    from app.models.order import Order
    from app.models.order_item import OrderItem

    with SessionLocal() as db:
        customer = Client(
            client_name="Gate test", customer_number="GATE", email_domain="gate.test", extraction_prompt="", master_data_enabled=True, approved_delivery_addresses=["Address"]
        )
        email = Email(
            sender_email="test@gate.test",
            subject="Gate",
            classification_status="order",
            external_message_id="gate-test",
            body="Test",
            received_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add_all([customer, email])
        db.flush()
        order = Order(client_id=customer.id, email_id=email.id, ticket_number="G", customer_number="GATE", commission_number="G", delivery_address="Address", status="OK")
        order.items = [OrderItem(article_number="UNKNOWN", quantity=1)]
        db.add(order)
        db.commit()
        order_id, customer_id, email_id = order.id, customer.id, email.id
    try:
        for action in ["approve", "generate-xml", "send-xml"]:
            assert client.post(f"/api/v1/orders/{order_id}/{action}", headers=auth_headers).status_code == 409
        detail = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()
        assert detail["status"] == "Human in the Loop"
        assert any(i["issue_type"] == "unknown_product" for i in detail["validation_issues"])
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Order, order_id))
            db.flush()
            db.delete(db.get(Email, email_id))
            db.delete(db.get(Client, customer_id))
            db.commit()
