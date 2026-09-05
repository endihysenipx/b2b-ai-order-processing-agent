from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.email import Email
from app.models.generated_xml import GeneratedXML
from app.models.order import Order
from app.models.order_item import OrderItem
from app.services.email.ingestion import GmailIngestionService
from app.services.validation.duplicates import duplicate_orders


@pytest.fixture
def repeated_orders():
    with SessionLocal() as db:
        customer = Client(client_name="Duplicate test", customer_number=str(uuid4()),
                          email_domain="duplicate.invalid", extraction_prompt="Test")
        email = Email(external_message_id=str(uuid4()), sender_email="test@duplicate.invalid", subject="Test",
                      body="Test", received_at=datetime.now(UTC).replace(tzinfo=None), classification_status="order")
        db.add_all([customer, email])
        db.flush()
        orders = [Order(client_id=customer.id, email_id=email.id, ticket_number=f"DUP-{i}",
                        commission_number=reference, status="OK", customer_number=customer.customer_number,
                        delivery_address="Test", is_demo=False)
                  for i, reference in enumerate(["PO-unique-123", " po-UNIQUE-123 "])]
        for order in orders:
            order.items = [OrderItem(article_number="A", quantity=1)]
        db.add_all(orders)
        db.commit()
        ids = [order.id for order in orders]
        customer_id, email_id = customer.id, email.id
    yield ids
    with SessionLocal() as db:
        for order in db.scalars(select(Order).where(Order.client_id == customer_id)):
            db.delete(order)
        db.flush()
        db.delete(db.get(Email, email_id))
        db.delete(db.get(Client, customer_id))
        db.commit()


@pytest.mark.parametrize("action", ["approve", "generate-xml", "send-xml"])
def test_duplicate_blocks_processing_without_master_data(client, auth_headers, repeated_orders, action):
    response = client.post(f"/api/v1/orders/{repeated_orders[1]}/{action}", headers=auth_headers)
    assert response.status_code == 409, response.text
    detail = client.get(f"/api/v1/orders/{repeated_orders[1]}", headers=auth_headers).json()
    assert [match["id"] for match in detail["duplicate_orders"]] == repeated_orders[:1]
    assert any(issue["issue_type"] == "duplicate_order" for issue in detail["validation_issues"])
    assert detail["approved_at"] is None
    assert detail["generated_xmls"] == []


def test_correction_and_rejection_resolve_duplicates(client, auth_headers, repeated_orders):
    original, extra = repeated_orders
    response = client.patch(f"/api/v1/orders/{extra}", headers=auth_headers,
                            json={"commission_number": "DIFFERENT-PO"})
    assert response.status_code == 200
    assert response.json()["duplicate_orders"] == []
    assert not any(i["issue_type"] == "duplicate_order" for i in response.json()["validation_issues"])
    client.patch(f"/api/v1/orders/{extra}", headers=auth_headers, json={"commission_number": "PO-unique-123"})
    assert client.post(f"/api/v1/orders/{extra}/reject", headers=auth_headers,
                       json={"reason": "Repeated PO"}).status_code == 200
    assert client.get(f"/api/v1/orders/{original}", headers=auth_headers).json()["duplicate_orders"] == []
    assert client.post(f"/api/v1/orders/{original}/approve", headers=auth_headers).status_code == 200
    assert client.post(f"/api/v1/orders/{extra}/approve", headers=auth_headers).status_code == 409


def test_scope_self_blank_and_punctuation(repeated_orders):
    with SessionLocal() as db:
        order = db.get(Order, repeated_orders[0])
        assert len(duplicate_orders(db, order.client_id, order.commission_number, order_id=order.id)) == 1
        assert duplicate_orders(db, "another-client", order.commission_number) == []
        assert duplicate_orders(db, order.client_id, order.commission_number, is_demo=True) == []
        assert duplicate_orders(db, order.client_id, "   ") == []
        assert duplicate_orders(db, order.client_id, "POunique123") == []
        other = db.get(Order, repeated_orders[1])
        other.status = "Rejected"
        db.flush()
        assert duplicate_orders(db, order.client_id, order.commission_number, order_id=order.id) == []


def test_intake_flags_repeat_from_another_email(repeated_orders):
    with SessionLocal() as db:
        original = db.get(Order, repeated_orders[0])
        preview = SimpleNamespace(message_type=SimpleNamespace(value="order"), reference_codes=["NEW-TICKET"],
                                  orders=[SimpleNamespace(commission_number=original.commission_number,
                                                          commission_name=None, store_address=None,
                                                          delivery_address="Test", preferred_delivery_week=None,
                                                          items=[SimpleNamespace(article_number="A", model_number=None,
                                                                                 quantity=1)])])
        new_email = Email(external_message_id=str(uuid4()), sender_email="test@duplicate.invalid", subject="Repeat",
                          body="Repeat", received_at=datetime.now(UTC).replace(tzinfo=None), classification_status="order")
        db.add(new_email)
        db.flush()
        orders = GmailIngestionService._create_orders(db, new_email, original.client, preview, [])
        db.flush()
        assert any(i.issue_type == "duplicate_order" for i in orders[0].validation_issues)
        assert orders[0].status == "Human in the Loop"
        db.rollback()



def test_rejected_export_is_still_a_duplicate(repeated_orders):
    with SessionLocal() as db:
        original, extra = [db.get(Order, oid) for oid in repeated_orders]
        original.status = "Rejected"
        original.generated_xmls = [GeneratedXML(xml_type="header", file_path="test.xml", status="sent",
                                                generated_at=datetime.now(UTC).replace(tzinfo=None))]
        db.flush()
        assert duplicate_orders(db, extra.client_id, extra.commission_number, order_id=extra.id)
        db.rollback()


def test_detail_requires_customer_access(client, auth_headers, repeated_orders):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="operator", clients=[])
    try:
        response = client.get(f"/api/v1/orders/{repeated_orders[0]}", headers=auth_headers)
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
