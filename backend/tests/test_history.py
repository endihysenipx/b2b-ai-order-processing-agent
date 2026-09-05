from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audit_event import AuditEvent
from app.models.client import Client
from app.models.email import Email
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product


@pytest.fixture
def history_customer():
    with SessionLocal() as db:
        customer = Client(client_name="History test", customer_number="HISTORY", email_domain="history.test", extraction_prompt="private prompt")
        db.add(customer)
        db.commit()
        client_id = customer.id
    yield client_id
    with SessionLocal() as db:
        for order in db.scalars(select(Order).where(Order.client_id == client_id)):
            db.delete(order)
        db.flush()
        for email in db.scalars(select(Email).where(Email.client_id == client_id)):
            db.delete(email)
        for product in db.scalars(select(Product).where(Product.client_id == client_id)):
            db.delete(product)
        db.flush()
        db.delete(db.get(Client, client_id))
        db.commit()


def entries(client, headers, customer, extra=""):
    result = client.get(f"/api/v1/history?client_id={customer}{extra}", headers=headers)
    assert result.status_code == 200, result.text
    return result.json()


def test_customer_changes_and_noop(client, auth_headers, history_customer):
    path = f"/api/v1/clients/{history_customer}/customer-data"
    payload = {"contact_name": "New contact", "phone": "123", "approved_delivery_addresses": ["Address"]}
    assert client.put(path, headers=auth_headers, json=payload).status_code == 200
    result = entries(client, auth_headers, history_customer)
    entry = result["items"][0]
    assert result["total"] == 1
    assert entry["actor_name"] and entry["actor_id"]
    assert entry["changes"]["contact_name"] == {"before": None, "after": "New contact"}
    assert "extraction_prompt" not in entry["changes"]
    assert entry["created_at"].endswith("Z")
    assert client.put(path, headers=auth_headers, json=payload).status_code == 200
    assert entries(client, auth_headers, history_customer)["total"] == 1


def test_price_stock_and_name_snapshot(client, auth_headers, history_customer):
    path = f"/api/v1/clients/{history_customer}/products"
    data = {"sku": "H1", "description": "History", "unit_price": "10.00", "currency": "EUR",
            "on_hand": 20, "reserved": 2, "stock_updated_at": datetime.now(UTC).isoformat()}
    product = client.post(path, headers=auth_headers, json=data).json()
    data.update(unit_price="12.50", on_hand=15)
    response = client.put(path + "/" + product["id"], headers=auth_headers, json=data)
    assert response.status_code == 200
    events = entries(client, auth_headers, history_customer)["items"]
    assert len(events) == 2
    changes = events[0]["changes"]
    assert changes["unit_price"] == {"before": "10.00", "after": "12.50"}
    assert changes["on_hand"] == {"before": 20, "after": 15}
    assert "reserved" not in changes
    # Audit display does not depend on a live user join.
    from app.models.user import User
    with SessionLocal() as db:
        actor = db.get(User, events[0]["actor_id"])
        original = actor.full_name
        actor.full_name = "Renamed temporarily"
        db.flush()
        assert db.get(AuditEvent, events[0]["id"]).actor_name == original
        db.rollback()
    with SessionLocal() as db:
        db.delete(db.get(Product, product["id"]))
        db.commit()
    assert entries(client, auth_headers, history_customer, "&entity_id=" + product["id"])["total"] == 2


def test_import_grouping_preview_and_rollback(client, auth_headers, history_customer, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    base = f"/api/v1/clients/{history_customer}/catalog-import"
    files = {"file": ("catalog.csv", b"sku,description\nA,One\nB,Two\n", "text/csv")}
    preview = client.post(base + "/preview", headers=auth_headers, files=files).json()
    assert entries(client, auth_headers, history_customer)["total"] == 0

    def fail(session):
        session.flush()
        raise IntegrityError("simulated", {}, Exception("Conflict"))

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail)
        response = client.post(base + "/confirm", headers=auth_headers, files=files,
                               data={"token": preview["token"], "confirmed": "true"})
    assert response.status_code == 409
    assert entries(client, auth_headers, history_customer)["total"] == 0
    response = client.post(base + "/confirm", headers=auth_headers, files=files,
                           data={"token": preview["token"], "confirmed": "true"})
    assert response.status_code == 200
    records = entries(client, auth_headers, history_customer)["items"]
    assert len(records) == 2
    assert records[0]["batch_id"] and records[0]["batch_id"] == records[1]["batch_id"]
    assert all(event["action"] == "catalog_import" for event in records)


def test_approval_correction_and_blocked_validation_are_audited(client, auth_headers, history_customer):
    with SessionLocal() as db:
        email = Email(client_id=history_customer, external_message_id="history-order", sender_email="test@history.test",
                      subject="History", body="Test", received_at=datetime.now(UTC).replace(tzinfo=None), classification_status="order")
        db.add(email)
        db.flush()
        order = Order(client_id=history_customer, email_id=email.id, status="OK", ticket_number="HISTORY-ORDER",
                      customer_number="HISTORY", commission_number="C", delivery_address="Address")
        order.items = [OrderItem(article_number="ITEM", quantity=1, unit_price=10, total_price=10, currency="EUR")]
        db.add(order)
        db.commit()
        order_id, item_id = order.id, order.items[0].id
    base = f"/api/v1/orders/{order_id}"
    assert client.post(base + "/approve", headers=auth_headers).status_code == 200
    approved = entries(client, auth_headers, history_customer)["items"][0]
    assert approved["action"] == "order_approved"
    assert approved["changes"]["status"] == {"before": "OK", "after": "Approved"}
    assert approved["changes"]["approved_by_user_id"]["after"] == approved["actor_id"]
    assert client.patch(base + f"/items/{item_id}", headers=auth_headers, json={"unit_price": "12.00"}).status_code == 200
    records = entries(client, auth_headers, history_customer, f"&order_id={order_id}")["items"]
    cleared = next(e for e in records if e["action"] == "approval_cleared_by_correction")
    assert cleared["changes"]["approved_at"]["after"] is None
    line = next(e for e in records if e["entity_type"] == "order_item")
    assert line["changes"]["unit_price"] == {"before": "10.00", "after": "12.00"}
    assert client.post(base + "/approve", headers=auth_headers).status_code == 200
    with SessionLocal() as db:
        db.get(Client, history_customer).master_data_enabled = True
        db.commit()
    assert client.post(base + "/generate-xml", headers=auth_headers).status_code == 409
    blocked = entries(client, auth_headers, history_customer)["items"][0]
    assert blocked["action"] == "validation_blocked_action"
    assert blocked["changes"]["approved_at"]["after"] is None


def test_history_scopes_pagination_and_immutability(client, auth_headers, history_customer):
    from app.api.dependencies import get_current_user
    from app.main import app
    from app.models.user import User

    path = f"/api/v1/clients/{history_customer}/customer-data"
    for phone in ["1", "2", "3"]:
        client.put(path, headers=auth_headers, json={"phone": phone})
    first = entries(client, auth_headers, history_customer, "&page_size=1")
    second = entries(client, auth_headers, history_customer, "&page_size=1&page=2")
    assert first["total"] == 3 and first["items"][0]["id"] != second["items"][0]["id"]
    assert entries(client, auth_headers, history_customer, "&entity_type=product")["total"] == 0
    assert client.get("/api/v1/history").status_code == 401
    app.dependency_overrides[get_current_user] = lambda: User(id="unassigned", full_name="Reader", role="operator")
    try:
        assert client.get(f"/api/v1/history?client_id={history_customer}").json()["total"] == 0
        assert client.get(f"/api/v1/history?entity_id={history_customer}").json()["total"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user)
    with SessionLocal() as db:
        assigned_user = User(id="assigned", full_name="Assigned reader", role="operator")
        assigned_user.clients = [db.get(Client, history_customer)]
    app.dependency_overrides[get_current_user] = lambda: assigned_user
    try:
        assert client.get(f"/api/v1/history?client_id={history_customer}").json()["total"] == 3
    finally:
        app.dependency_overrides.pop(get_current_user)
    assert entries(client, auth_headers, history_customer, "&actor=DOES-NOT-EXIST")["total"] == 0
    assert entries(client, auth_headers, history_customer, "&date_to=2000-01-01")["total"] == 0
    assert client.get("/api/v1/history?date_from=2026-09-05&date_to=2026-09-01", headers=auth_headers).status_code == 422
    with SessionLocal() as db:
        event = db.get(AuditEvent, first["items"][0]["id"])
        event.actor_name = "Tampered"
        with pytest.raises(ValueError, match="cannot be edited"):
            db.commit()
        db.rollback()
        db.delete(db.get(AuditEvent, first["items"][0]["id"]))
        with pytest.raises(ValueError, match="cannot be edited"):
            db.commit()
        db.rollback()
