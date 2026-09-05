import json

import httpx
import pytest

from app.core.config import Settings
from app.services.extraction.openai_service import OpenAIExtractionService
from app.services.extraction.service import AIExtractionError, ExtractionConfigurationError, build_ai_extraction_service


def extracted_payload():
    def field(value):
        return {"value": value, "source_type": "email", "source_file": None, "confidence": 0.95}
    return {
        "header": {name: field(value) for name, value in {
            "ticket_number": "00012", "customer_number": "C-1",
            "commission_number": "COM-1", "delivery_address": "12 Example Street",
        }.items()},
        "items": [{name: field(value) for name, value in {
            "article_number": "00042", "model_number": None, "quantity": "2",
            "unit_price": "12.50", "currency": "EUR",
        }.items()}],
    }


def response_body(payload=None):
    return {"status": "completed", "output": [{"type": "message", "content": [{
        "type": "output_text", "text": json.dumps(payload or extracted_payload()),
    }]}]}


def service(handler):
    return OpenAIExtractionService(
        Settings(_env_file=None, openai_api_key="test-key", openai_model="test-model"),
        transport=httpx.MockTransport(handler),
    )


def test_openai_uses_strict_responses_schema_and_preserves_identifiers():
    def handler(request):
        assert str(request.url) == "https://api.openai.com/v1/responses"
        body = json.loads(request.content)
        assert body["store"] is False
        assert body["model"] == "test-model"
        assert body["text"]["format"]["strict"] is True
        assert body["text"]["format"]["schema"]["additionalProperties"] is False
        assert "untrusted" in body["instructions"]
        return httpx.Response(200, json=response_body())
    result = service(handler).extract_order("Extract order", "00042 x 2", [])
    assert result.items[0].article_number.value == "00042"
    assert result.header["ticket_number"].value == "00012"


@pytest.mark.parametrize("body", [
    {"status": "incomplete", "output": []},
    {"status": "completed", "output": []},
    {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]},
    response_body({"header": {}, "items": []}),
])
def test_rejects_unusable_responses(body):
    with pytest.raises(AIExtractionError):
        service(lambda request: httpx.Response(200, json=body)).extract_order("Extract", "body", [])


@pytest.mark.parametrize("status", [401, 429, 500])
def test_upstream_errors_do_not_leak_data(status):
    with pytest.raises(AIExtractionError) as error:
        service(lambda request: httpx.Response(status, text="secret-customer-data")).extract_order("x", "y", [])
    assert str(status) in str(error.value)
    assert "secret-customer-data" not in str(error.value)


def test_timeout_is_a_safe_provider_error():
    def handler(request):
        raise httpx.ReadTimeout("sensitive", request=request)
    with pytest.raises(AIExtractionError, match="connectivity or timeout"):
        service(handler).extract_order("x", "y", [])


def test_unknown_source_is_rejected():
    payload = extracted_payload()
    payload["header"]["ticket_number"].update(source_type="document", source_file="invented.pdf")
    with pytest.raises(AIExtractionError):
        service(lambda request: httpx.Response(200, json=response_body(payload))).extract_order("x", "y", [])


@pytest.mark.parametrize("key,model", [(None, "test"), ("test", None)])
def test_openai_requires_explicit_configuration(key, model):
    with pytest.raises(ExtractionConfigurationError):
        build_ai_extraction_service(Settings(
            _env_file=None, ai_provider="openai", openai_api_key=key, openai_model=model,
        ))


@pytest.mark.parametrize("fails", [False, True])
def test_intake_persists_openai_results_and_does_not_repeat_calls(tmp_path, monkeypatch, fails):
    from sqlalchemy import select
    from test_gmail_ingestion import build_gmail_order

    from app.db.session import SessionLocal
    from app.models.order import Order
    from app.services.email.ingestion import GmailIngestionService
    from app.services.extraction.service import ExtractedOrder

    calls = []

    class FakeProvider:
        def extract_order(self, prompt, body, documents):
            calls.append(body)
            if fails:
                raise AIExtractionError("OpenAI unavailable")
            return ExtractedOrder.model_validate(extracted_payload())

    monkeypatch.setattr("app.services.extraction.intake.build_ai_extraction_service", lambda settings: FakeProvider())
    intake = GmailIngestionService(Settings(
        _env_file=None, ai_provider="openai", storage_root=str(tmp_path),
    ), SessionLocal)
    content = build_gmail_order(f"<openai-intake-{fails}@example.com>")
    first = intake.import_uploaded_message(content)
    second = intake.import_uploaded_message(content)
    assert len(calls) == 1
    assert second.duplicate
    assert first.requires_review
    with SessionLocal() as db:
        order = db.scalar(select(Order).where(Order.email_id == first.email_id))
        assert order.status == "Human in the Loop"
        assert order.approved_at is None
        if fails:
            assert any(issue.issue_type == "ai_extraction_failed" for issue in order.validation_issues)
            assert order.items[0].article_number == "04617"
        else:
            assert order.ticket_number == "00012"
            assert order.items[0].article_number == "00042"
            assert order.items[0].quantity == 2
            assert (tmp_path / "emails" / f"{first.email_id}.extraction.json").exists()
