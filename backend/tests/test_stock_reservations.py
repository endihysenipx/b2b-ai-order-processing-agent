from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.email import Email
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product


@pytest.fixture
def stock_orders():
    with SessionLocal() as db:
        customer = Client(client_name="Stock test", customer_number=str(uuid4()), email_domain="stock.invalid",
                          extraction_prompt="", master_data_enabled=True, approved_delivery_addresses=["Test"])
        email = Email(external_message_id=str(uuid4()), sender_email="test@stock.invalid", subject="Test", body="Test",
                      received_at=datetime.now(UTC).replace(tzinfo=None), classification_status="order")
        db.add_all([customer, email])
        db.flush()
        product = Product(client_id=customer.id, sku="A", aliases=["ALIAS"], description="Test", on_hand=10,
                          reserved=2, stock_updated_at=datetime.now(UTC).replace(tzinfo=None))
        db.add(product)
        orders = [Order(client_id=customer.id, email_id=email.id, ticket_number=f"STOCK-{i}",
                        commission_number=f"STOCK-{i}", customer_number=customer.customer_number,
                        delivery_address="Test", status="OK", is_demo=False) for i in range(2)]
        for order in orders:
            order.items = [OrderItem(article_number="A", quantity=2), OrderItem(article_number="ALIAS", quantity=3)]
        db.add_all(orders)
        db.commit()
        ids = [o.id for o in orders], customer.id, product.id, email.id
    yield ids
    with SessionLocal() as db:
        for oid in ids[0]:
            db.delete(db.get(Order, oid))
        db.flush()
        db.delete(db.get(Product, ids[2]))
        db.delete(db.get(Email, ids[3]))
        db.delete(db.get(Client, ids[1]))
        db.commit()


def test_approval_reserves_once_and_blocks_competing_order(client, auth_headers, stock_orders):
    orders, customer_id, _, _ = stock_orders
    for _ in range(2):
        result = client.post(f"/api/v1/orders/{orders[0]}/approve", headers=auth_headers)
        assert result.status_code == 200, result.text
        assert [r["quantity"] for r in result.json()["stock_reservations"]] == [5]
    products = client.get(f"/api/v1/clients/{customer_id}/products", headers=auth_headers).json()
    assert products[0]["reserved"] == 2
    assert products[0]["order_reserved"] == 5
    assert products[0]["available"] == 3
    assert client.post(f"/api/v1/orders/{orders[1]}/approve", headers=auth_headers).status_code == 409
    assert client.post(f"/api/v1/orders/{orders[0]}/reject", headers=auth_headers,
                       json={"reason": "Cancelled"}).status_code == 200
    assert client.post(f"/api/v1/orders/{orders[1]}/approve", headers=auth_headers).status_code == 200


@pytest.mark.parametrize("action", ["correction", "validate"])
def test_corrections_and_validation_release_stock(client, auth_headers, stock_orders, action):
    orders, customer_id, _, _ = stock_orders
    assert client.post(f"/api/v1/orders/{orders[0]}/approve", headers=auth_headers).status_code == 200
    if action == "correction":
        result = client.patch(f"/api/v1/orders/{orders[0]}", headers=auth_headers, json={"delivery_week": "W30"})
    else:
        result = client.post(f"/api/v1/orders/{orders[0]}/validate", headers=auth_headers)
    assert result.status_code == 200
    products = client.get(f"/api/v1/clients/{customer_id}/products", headers=auth_headers).json()
    assert products[0]["order_reserved"] == 0 and products[0]["available"] == 8


def test_export_reserves_legacy_order_and_sent_allocations_are_retained(client, auth_headers, stock_orders):
    orders, customer_id, _, _ = stock_orders
    for action in ["generate-xml", "send-xml"]:
        response = client.post(f"/api/v1/orders/{orders[0]}/{action}", headers=auth_headers)
        assert response.status_code == 200, response.text
    assert client.patch(f"/api/v1/orders/{orders[0]}", headers=auth_headers,
                        json={"delivery_week": "W31"}).status_code == 409
    assert client.post(f"/api/v1/orders/{orders[0]}/reject", headers=auth_headers,
                       json={"reason": "Cancel"}).status_code == 409
    products = client.get(f"/api/v1/clients/{customer_id}/products", headers=auth_headers).json()
    assert products[0]["order_reserved"] == 5


def test_failed_gate_releases_and_demo_does_not_reserve(client, auth_headers, stock_orders):
    orders, customer_id, product_id, _ = stock_orders
    client.post(f"/api/v1/orders/{orders[0]}/approve", headers=auth_headers)
    with SessionLocal() as db:
        db.get(Product, product_id).is_active = False
        db.commit()
    assert client.post(f"/api/v1/orders/{orders[0]}/generate-xml", headers=auth_headers).status_code == 409
    with SessionLocal() as db:
        product = db.get(Product, product_id)
        assert product.order_reserved == 0
        product.is_active = True
        db.get(Order, orders[0]).is_demo = True
        db.commit()
    response = client.post(f"/api/v1/orders/{orders[0]}/approve", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["stock_reservations"] == []


def test_catalog_import_preserves_app_reservations(client, auth_headers, stock_orders):
    orders, customer_id, _, _ = stock_orders
    client.post(f"/api/v1/orders/{orders[0]}/approve", headers=auth_headers)
    base = f"/api/v1/clients/{customer_id}/catalog-import"
    files = {"file": ("stock.csv", b"sku,description,reserved\nA,Updated,1\n", "text/csv")}
    preview = client.post(base + "/preview", headers=auth_headers, files=files)
    assert preview.status_code == 200
    confirmed = client.post(base + "/confirm", headers=auth_headers, files=files,
                            data={"token": preview.json()["token"], "confirmed": "true"})
    assert confirmed.status_code == 200, confirmed.text
    product = client.get(f"/api/v1/clients/{customer_id}/products", headers=auth_headers).json()[0]
    assert product["reserved"] == 1 and product["order_reserved"] == 5 and product["available"] == 4


def test_failed_export_rolls_back_reservations(client, auth_headers, stock_orders, monkeypatch):
    orders, customer_id, _, _ = stock_orders

    def fail(order):
        raise RuntimeError("Test export failure")

    monkeypatch.setattr("app.api.routes.orders.generate_header_xml", fail)
    with pytest.raises(RuntimeError, match="Test export failure"):
        client.post(f"/api/v1/orders/{orders[0]}/generate-xml", headers=auth_headers)
    product = client.get(f"/api/v1/clients/{customer_id}/products", headers=auth_headers).json()[0]
    assert product["order_reserved"] == 0
