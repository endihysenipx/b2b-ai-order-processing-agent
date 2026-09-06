from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.api.dependencies import get_current_user
from app.db.session import SessionLocal
from app.main import app
from app.models.client import Client
from app.models.email import Email
from app.models.notification_read import NotificationRead
from app.models.order import Order
from app.models.user import User


@pytest.fixture
def notification_orders():
    with SessionLocal() as db:
        customer = Client(client_name="Notification test", customer_number=str(uuid4()), email_domain="notify.invalid",
                          extraction_prompt="")
        email = Email(external_message_id=str(uuid4()), sender_email="test@notify.invalid", subject="Test", body="Test",
                      received_at=datetime.now(UTC).replace(tzinfo=None), classification_status="order")
        db.add_all([customer, email])
        db.flush()
        statuses = ["Failed", "Human in the Loop", "Waiting for Reply", "OK", "OK", "Rejected", "XMLs Sent", "Failed"]
        orders = [Order(client_id=customer.id, email_id=email.id, status=status, ticket_number=f"NOTICE-{i}",
                        commission_number="DUP" if i in (3, 4) else f"REF-{i}", is_demo=i == 7)
                  for i, status in enumerate(statuses)]
        db.add_all(orders)
        db.commit()
        ids, customer_id, email_id = [o.id for o in orders], customer.id, email.id
    yield ids, customer_id
    with SessionLocal() as db:
        db.execute(delete(NotificationRead).where(NotificationRead.order_id.in_(ids)))
        for oid in ids:
            db.delete(db.get(Order, oid))
        db.flush()
        db.delete(db.get(Email, email_id))
        db.delete(db.get(Client, customer_id))
        db.commit()


def notifications(client, auth_headers):
    response = client.get("/api/v1/notifications?page_size=100", headers=auth_headers)
    assert response.status_code == 200, response.text
    return {item["order_id"]: item for item in response.json()["items"]}


def test_live_categories_read_is_personal_and_order_unchanged(client, auth_headers, notification_orders):
    ids, _ = notification_orders
    items = notifications(client, auth_headers)
    assert [items[oid]["category"] for oid in ids[:5]] == ["failed", "review", "waiting", "duplicate", "duplicate"]
    assert all(oid not in items for oid in ids[5:])
    payload = {"fingerprint": items[ids[0]]["fingerprint"], "is_read": True}
    for _ in range(2):
        assert client.put(f"/api/v1/notifications/{ids[0]}/read", headers=auth_headers, json=payload).status_code == 200
    assert notifications(client, auth_headers)[ids[0]]["is_read"]
    unread = client.get("/api/v1/notifications?unread_only=true&page_size=100", headers=auth_headers).json()
    assert ids[0] not in {i["order_id"] for i in unread["items"]}
    with SessionLocal() as db:
        assert db.get(Order, ids[0]).status == "Failed"
        other = User(full_name="Other", email=f"{uuid4()}@notify.invalid", password_hash="unused", role="manager")
        db.add(other)
        db.commit()
        other_id = other.id
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=other_id, role="manager")
    try:
        assert not notifications(client, auth_headers)[ids[0]]["is_read"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        with SessionLocal() as db:
            db.delete(db.get(User, other_id))
            db.commit()


def test_changed_and_resolved_orders(client, auth_headers, notification_orders):
    ids, _ = notification_orders
    item = notifications(client, auth_headers)[ids[0]]
    client.put(f"/api/v1/notifications/{ids[0]}/read", headers=auth_headers,
               json={"fingerprint": item["fingerprint"]})
    with SessionLocal() as db:
        db.get(Order, ids[0]).status = "Waiting for Reply"
        db.get(Order, ids[4]).status = "Rejected"
        db.commit()
    current = notifications(client, auth_headers)
    assert not current[ids[0]]["is_read"]
    assert ids[3] not in current and ids[4] not in current
    assert client.put(f"/api/v1/notifications/{ids[0]}/read", headers=auth_headers,
                      json={"fingerprint": item["fingerprint"]}).status_code == 409


def test_access_filters_and_pagination(client, auth_headers, notification_orders):
    ids, customer_id = notification_orders
    item = notifications(client, auth_headers)[ids[0]]
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="unassigned", role="operator", clients=[])
    try:
        result = client.get("/api/v1/notifications", headers=auth_headers).json()
        assert result["total"] == result["unread_count"] == 0
        assert client.put(f"/api/v1/notifications/{ids[0]}/read", headers=auth_headers,
                          json={"fingerprint": item["fingerprint"]}).status_code == 404
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id="assigned", role="operator", clients=[SimpleNamespace(id=customer_id)])
        result = client.get("/api/v1/notifications?page_size=2", headers=auth_headers).json()
        assert result["total"] == result["unread_count"] == 5 and len(result["items"]) == 2
        result = client.get("/api/v1/notifications?category=failed&include_demo=true", headers=auth_headers).json()
        assert result["total"] == 2
        assert client.get("/api/v1/notifications?page=0", headers=auth_headers).status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_auth_required(client):
    assert client.get("/api/v1/notifications").status_code == 401
