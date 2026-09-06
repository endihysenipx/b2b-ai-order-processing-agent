from types import SimpleNamespace

from app.services.email.clarification import build_clarification, questions_for
from app.services.validation.service import ValidationResult


def test_customer_questions_exclude_internal_details():
    questions, notes = questions_for([
        ValidationResult("items[2].article_number", "unknown_product", "private catalog data"),
        ValidationResult("commission_number", "duplicate_order", "internal-order-uuid"),
        ValidationResult("items[2].quantity", "stock_shortage", "Warehouse-secret: available 3"),
        ValidationResult("extraction", "ai_extraction_failed", "secret provider diagnostics"),
    ])
    assert len(questions) == 2 and questions[0].startswith("Line 2:")
    assert len(notes) == 2
    assert not any(word in " ".join(questions + notes) for word in ["secret", "uuid", "Warehouse"])


def test_draft_uses_current_validation_without_mutating(client, auth_headers):
    order = client.get("/api/v1/orders?search=TCK-10003", headers=auth_headers).json()["items"][0]
    path = f"/api/v1/orders/{order['id']}"
    before = client.get(path, headers=auth_headers).json()
    response = client.get(path + "/clarification-draft", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert "PO / commission number" in response.json()["body"]
    assert client.get(path, headers=auth_headers).json() == before


def test_draft_scopes_customer_access(client, auth_headers):
    from app.api.dependencies import get_current_user
    from app.main import app

    order = client.get("/api/v1/orders", headers=auth_headers).json()["items"][0]
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="operator", clients=[])
    try:
        assert client.get(f"/api/v1/orders/{order['id']}/clarification-draft", headers=auth_headers).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_reply_to_and_clean_reference(monkeypatch):
    monkeypatch.setattr("app.services.email.clarification.validate_order_data", lambda *a, **k: [
        ValidationResult("items[1].quantity", "missing_required_field", "unused")])
    order = SimpleNamespace(**dict.fromkeys(["ticket_number", "customer_number", "delivery_address", "total_price", "currency"]))
    order.commission_number = "PO-1\r\nInjected"
    order.items = []
    order.is_scanned_source = False
    order.client_id, order.id, order.is_demo = "c", "o", False
    order.validation_issues = []
    order.email = SimpleNamespace(reply_to_email="Buyer <buyer@example.test>", sender_email="sender@example.test")
    order.client = SimpleNamespace(default_email="default@example.test")
    draft = build_clarification(None, order)
    assert draft["recipient"] == "buyer@example.test"
    assert "\n" not in draft["subject"]
    assert "Line 1: Please provide the required quantity." in draft["body"]
