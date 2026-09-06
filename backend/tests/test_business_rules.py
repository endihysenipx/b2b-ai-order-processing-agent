from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4
from xml.etree import ElementTree

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audit_event import AuditEvent
from app.models.client import Client
from app.models.email import Email
from app.models.generated_xml import GeneratedXML
from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas.business_rules import BusinessRules
from app.services.business_rules import evaluate, order_terms


@pytest.mark.parametrize(("subtotal", "freight"), [("499.99", "35.00"), ("500", "0.00"), ("500.01", "0.00")])
def test_freight_boundary(subtotal, freight):
    result = evaluate(BusinessRules(freight_enabled=True), Decimal(subtotal), "EUR")
    assert result["freight"] == freight
    assert Decimal(result["total"]) == Decimal(subtotal) + Decimal(freight)


def test_discount_rounding_minimum_and_review():
    rules = BusinessRules(discount_enabled=True, discount_from=0, discount_percent=5,
                          freight_enabled=True, minimum_enabled=True, minimum_order=300,
                          review_enabled=True, review_from=35)
    result = evaluate(rules, Decimal("0.10"), "EUR")
    assert result["discount"] == "0.01"
    assert result["total"] == "35.09"
    assert result["blockers"] and result["review_required"]
    assert evaluate(rules, None, "EUR")["total"] is None
    assert evaluate(rules, 1500, "USD")["blockers"]


def test_line_subtotal_prevents_compounding_and_mixed_currency():
    order = Order(client=Client(validation_rules={"business_rules": {"freight_enabled": True}}), total_price=455,
                  currency="EUR", items=[OrderItem(quantity=2, unit_price=Decimal("210"), currency="EUR")])
    assert order_terms(order)["total"] == "455.00"
    assert order_terms(order)["total"] == "455.00"
    order.items[0].quantity = 3
    assert order_terms(order)["total"] == "630.00"
    order.items[0].currency = "USD"
    assert order_terms(order)["total"] is None


@pytest.fixture
def rules_order():
    with SessionLocal() as db:
        client = Client(client_name="Rules test", customer_number=str(uuid4()), email_domain="rules.test",
                        extraction_prompt="Test", validation_rules={"keep_existing": True})
        email = Email(external_message_id=str(uuid4()), subject="WG: Bestellung test", sender_email="original@test.test",
                      body="Original source", received_at=datetime.now(UTC).replace(tzinfo=None), classification_status="order")
        order = Order(client=client, email=email, status="OK", ticket_number="RULES", customer_number=client.customer_number,
                      commission_number=str(uuid4()), delivery_address="Test dock", currency="EUR", total_price=420,
                      items=[OrderItem(article_number="TEST", quantity=2, unit_price=210, total_price=420, currency="EUR")])
        db.add(order)
        db.commit()
        ids = client.id, order.id, order.items[0].id, email.id
    yield ids
    with SessionLocal() as db:
        db.delete(db.get(Order, ids[1]))
        db.flush()
        db.delete(db.get(Email, ids[3]))
        db.flush()
        db.delete(db.get(Client, ids[0]))
        db.commit()


def test_rule_save_edits_xml_and_invalidation(client, auth_headers, rules_order):
    customer, order_id, item_id, _ = rules_order
    path = f"/api/v1/orders/{order_id}"
    response = client.put(f"/api/v1/business-rules/clients/{customer}", headers=auth_headers, json={"freight_enabled": True})
    assert response.status_code == 200, response.text
    assert response.json()["updated_orders"] == 1
    assert client.get(path, headers=auth_headers).json()["commercial_terms"]["total"] == "455.00"
    response = client.post(path + "/generate-xml", headers=auth_headers)
    assert response.status_code == 200, response.text
    xml = ElementTree.parse(response.json()["files"][0])
    assert xml.findtext("CommercialTerms/Freight") == "35.00"
    assert xml.findtext("CommercialTerms/TotalPayable") == "455.00"
    response = client.patch(path + f"/items/{item_id}", headers=auth_headers, json={"quantity": 3})
    assert response.status_code == 200, response.text
    assert response.json()["commercial_terms"]["total"] == "630.00"
    assert response.json()["generated_xmls"] == []
    with SessionLocal() as db:
        assert db.get(Client, customer).validation_rules["keep_existing"] is True


def test_minimum_blocks_approval_and_high_value_requires_approval(client, auth_headers, rules_order):
    customer, order_id, _, _ = rules_order
    rules_path = f"/api/v1/business-rules/clients/{customer}"
    path = f"/api/v1/orders/{order_id}"
    assert client.put(rules_path, headers=auth_headers, json={"minimum_enabled": True, "minimum_order": 500}).status_code == 200
    assert client.post(path + "/approve", headers=auth_headers).status_code == 409
    assert client.post(path + "/generate-xml", headers=auth_headers).status_code == 409
    assert client.put(rules_path, headers=auth_headers, json={"review_enabled": True, "review_from": 400}).status_code == 200
    assert client.post(path + "/generate-xml", headers=auth_headers).status_code == 409
    assert client.post(path + "/approve", headers=auth_headers).status_code == 200
    assert client.post(path + "/generate-xml", headers=auth_headers).status_code == 200


def test_rule_change_preserves_sent_terms(client, auth_headers, rules_order):
    customer, order_id, _, _ = rules_order
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        order.generated_xmls = [GeneratedXML(xml_type="header", file_path="test.xml", status="sent",
                                            generated_at=datetime.now(UTC), sent_at=datetime.now(UTC))]
        db.commit()
    response = client.put(f"/api/v1/business-rules/clients/{customer}", headers=auth_headers, json={"freight_enabled": True})
    assert response.status_code == 200, response.text
    assert response.json()["updated_orders"] == 0
    terms = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["commercial_terms"]
    assert not terms["enabled"] and terms["total"] == "420.00"


def test_conversion_is_audited_and_cannot_repeat(client, auth_headers, rules_order):
    from types import SimpleNamespace

    from app.services.aws_document_processing.processing import TextractJobProcessor

    customer, order_id, _, email_id = rules_order
    payload = {"email_id": email_id, "client_id": customer, "label": "Freight case", "article_number": "CASE-CHAIR", "quantity": 2, "unit_price": "210"}
    response = client.post("/api/v1/business-rules/cases", headers=auth_headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == order_id
    detail = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()
    assert detail["case_source"]["label"] == "Freight case" and detail["is_demo"]
    assert detail["email"]["sender_email"] == "orders@rules.test"
    assert detail["items"][0]["article_number"] == "CASE-CHAIR"
    assert client.post("/api/v1/business-rules/cases", headers=auth_headers, json=payload).status_code == 409
    with SessionLocal() as db:
        assert TextractJobProcessor._apply_mapping(db, SimpleNamespace(order_id=order_id), SimpleNamespace(items=[object()])) == 0
        audit = db.scalar(select(AuditEvent).where(AuditEvent.order_id == order_id, AuditEvent.action == "source_converted_to_client_case"))
        assert audit.changes["email"]["before"]["body"] == "Original source"


def test_invalid_rules_rejected(client, auth_headers, rules_order):
    path = f"/api/v1/business-rules/clients/{rules_order[0]}"
    for invalid in ({"discount_percent": 101}, {"freight_charge": -1}, {"currency": "eur"}, {"freight_below": "NaN"}):
        assert client.put(path, headers=auth_headers, json=invalid).status_code == 422
    assert client.get("/api/v1/business-rules").status_code == 401


def test_permissions_and_tenant_boundaries(client, rules_order):
    from types import SimpleNamespace

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="operator", clients=[])
    try:
        assert client.get("/api/v1/business-rules").json() == []
        assert client.get("/api/v1/business-rules/cases").json() == []
        assert client.get("/api/v1/business-rules/sources").status_code == 403
        assert client.put(f"/api/v1/business-rules/clients/{rules_order[0]}", json={}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user)
