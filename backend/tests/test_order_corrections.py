from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.email import Email
from app.models.generated_xml import GeneratedXML
from app.models.order import Order
from app.models.order_item import OrderItem


@pytest.fixture
def correction_order():
    with SessionLocal() as db:
        customer = db.scalar(select(Client).order_by(Client.id))
        email = Email(external_message_id="correction-test", sender_email="test@example.test", subject="Test",
                      body="Test", received_at=datetime.now(UTC).replace(tzinfo=None), classification_status="order")
        db.add(email)
        db.flush()
        order = Order(client_id=customer.id, email_id=email.id, status="Approved", ticket_number="T",
                      customer_number=customer.customer_number, commission_number="C", delivery_address="Test",
                      approved_at=datetime.now(UTC).replace(tzinfo=None))
        order.items = [OrderItem(article_number="FIRST", quantity=1, unit_price=10, total_price=10, currency="EUR"),
                       OrderItem(article_number="SECOND", quantity=2, unit_price=25, total_price=50, currency="EUR")]
        order.generated_xmls = [GeneratedXML(xml_type="header", file_path="test-only.xml", status="generated",
                                            generated_at=datetime.now(UTC).replace(tzinfo=None))]
        db.add(order)
        db.commit()
        ids = order.id, order.items[0].id, order.items[1].id, email.id
    yield ids
    with SessionLocal() as db:
        db.delete(db.get(Order, ids[0]))
        db.flush()
        db.delete(db.get(Email, ids[3]))
        db.commit()


def test_correct_second_line_and_invalidate_approval(client, auth_headers, correction_order):
    order_id, first_id, second_id, _ = correction_order
    response = client.patch(f"/api/v1/orders/{order_id}/items/{second_id}", headers=auth_headers,
                            json={"article_number": "CORRECTED", "model_number": "M", "quantity": 3,
                                  "unit_price": "12.50", "currency": "USD"})
    assert response.status_code == 200, response.text
    data = response.json()
    first = next(item for item in data["items"] if item["id"] == first_id)
    second = next(item for item in data["items"] if item["id"] == second_id)
    assert first["quantity"] == 1 and first["article_number"] == "FIRST"
    assert second["total_price"] == "37.50" and second["currency"] == "USD"
    assert data["approved_at"] is None and data["generated_xmls"] == []
    assert data["status"] != "Approved"


def test_clearing_quantity_clears_stale_total(client, auth_headers, correction_order):
    order_id, _, item_id, _ = correction_order
    response = client.patch(f"/api/v1/orders/{order_id}/items/{item_id}", headers=auth_headers, json={"quantity": None})
    assert response.status_code == 200
    item = next(i for i in response.json()["items"] if i["id"] == item_id)
    assert item["total_price"] is None
    assert response.json()["status"] == "Waiting for Reply"


def test_source_total_without_unit_price_can_be_corrected(client, auth_headers, correction_order):
    order_id, _, item_id, _ = correction_order
    response = client.patch(f"/api/v1/orders/{order_id}/items/{item_id}", headers=auth_headers,
                            json={"unit_price": None, "total_price": "19.99", "currency": "EUR"})
    assert response.status_code == 200
    assert next(i for i in response.json()["items"] if i["id"] == item_id)["total_price"] == "19.99"


@pytest.mark.parametrize("payload", [
    {"quantity": 0}, {"quantity": -1}, {"quantity": 1.5}, {"quantity": True},
    {"unit_price": "-1"}, {"unit_price": "1.001"}, {"currency": "invalid"},
    {"quantity": 2147483647, "unit_price": "9999999999.99"}, {"total_price": "1"},
])
def test_invalid_corrections_leave_order_unchanged(client, auth_headers, correction_order, payload):
    order_id, _, item_id, _ = correction_order
    response = client.patch(f"/api/v1/orders/{order_id}/items/{item_id}", headers=auth_headers, json=payload)
    assert response.status_code == 422, response.text
    with SessionLocal() as db:
        item = db.get(OrderItem, item_id)
        assert item.quantity == 2 and item.total_price == 50
        assert db.get(Order, order_id).status == "Approved"


def test_cannot_edit_item_through_another_order(client, auth_headers, correction_order):
    _, _, item_id, _ = correction_order
    with SessionLocal() as db:
        other = db.scalar(select(Order).where(Order.ticket_number != "T"))
        other_id = other.id
    assert client.patch(f"/api/v1/orders/{other_id}/items/{item_id}", headers=auth_headers,
                        json={"quantity": 1}).status_code == 404
