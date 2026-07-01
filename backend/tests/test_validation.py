from app.services.decision.service import decide_order_status
from app.services.validation.service import validate_order_data


def test_missing_field_validation_works():
    issues = validate_order_data(
        {"ticket_number": "TCK-1", "customer_number": "CUST-1", "commission_number": None, "delivery_address": ""},
        [{"article_number": "ART-1", "quantity": 2, "unit_price": 10, "currency": "EUR"}],
    )

    assert any(issue.field_name == "commission_number" for issue in issues)
    assert any(issue.field_name == "delivery_address" for issue in issues)


def test_scanned_document_decision_returns_human_in_the_loop():
    issues = validate_order_data(
        {
            "ticket_number": "TCK-1",
            "customer_number": "CUST-1",
            "commission_number": "COM-1",
            "delivery_address": "Address",
        },
        [{"article_number": "ART-1", "quantity": 2, "unit_price": 10, "currency": "EUR"}],
        is_scanned_source=True,
    )

    assert decide_order_status(issues, is_scanned_source=True) == "Human in the Loop"


def test_missing_required_information_returns_waiting_for_reply():
    issues = validate_order_data(
        {
            "ticket_number": "TCK-1",
            "customer_number": "CUST-1",
            "commission_number": None,
            "delivery_address": "Address",
        },
        [{"article_number": "ART-1", "quantity": 2, "unit_price": 10, "currency": "EUR"}],
    )

    assert decide_order_status(issues) == "Waiting for Reply"


def test_invalid_quantity_is_detected():
    issues = validate_order_data(
        {
            "ticket_number": "TCK-1",
            "customer_number": "CUST-1",
            "commission_number": "COM-1",
            "delivery_address": "Address",
        },
        [{"article_number": "ART-1", "quantity": 0, "unit_price": 10, "currency": "EUR"}],
    )

    assert any(issue.issue_type == "invalid_quantity" for issue in issues)
