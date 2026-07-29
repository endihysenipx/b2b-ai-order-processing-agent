import json

import pytest

from app.core.config import Settings
from app.services.extraction import (
    AIExtractionError,
    BedrockAIExtractionService,
    ExtractionConfigurationError,
    ExtractionDocument,
    MockAIExtractionService,
    build_ai_extraction_service,
)


def extracted_order_payload():
    def field(value, source_type="email", source_file=None, confidence=0.97):
        return {
            "value": value,
            "source_type": source_type,
            "source_file": source_file,
            "confidence": confidence,
        }

    return {
        "header": {
            "ticket_number": field("TCK-100"),
            "customer_number": field("CUST-200"),
            "commission_number": field("COM-300", "document", "order.txt"),
            "delivery_address": field("42 Example Street"),
        },
        "items": [
            {
                "article_number": field("ART-1", "document", "order.txt"),
                "model_number": field("MODEL-A", "document", "order.txt"),
                "quantity": field(2, "document", "order.txt"),
                "unit_price": field("125.00", "document", "order.txt"),
                "currency": field("EUR", "document", "order.txt"),
            }
        ],
    }


class FakeBedrockClient:
    def __init__(self, response_text):
        self.response_text = response_text
        self.requests = []

    def converse(self, **request):
        self.requests.append(request)
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": self.response_text}],
                }
            }
        }


def test_bedrock_extraction_invokes_converse_and_validates_response():
    client = FakeBedrockClient(json.dumps(extracted_order_payload()))
    service = BedrockAIExtractionService(
        Settings(
            ai_provider="bedrock",
            bedrock_model_id="test.model-v1:0",
            bedrock_max_tokens=2048,
            bedrock_temperature=0,
        ),
        bedrock_client=client,
    )

    result = service.extract_order(
        "Extract the client purchase order.",
        "Ticket TCK-100 for customer CUST-200.",
        [ExtractionDocument(file_name="order.txt", content="Article ART-1, quantity 2")],
    )

    assert result.header["ticket_number"].value == "TCK-100"
    assert result.items[0].unit_price.value == "125.00"
    assert client.requests[0]["modelId"] == "test.model-v1:0"
    assert client.requests[0]["inferenceConfig"] == {
        "maxTokens": 2048,
        "temperature": 0.0,
    }
    assert "order.txt" in client.requests[0]["messages"][0]["content"][0]["text"]
    assert "untrusted evidence" in client.requests[0]["system"][0]["text"]


def test_bedrock_extraction_accepts_json_code_fence():
    response = f"```json\n{json.dumps(extracted_order_payload())}\n```"
    service = BedrockAIExtractionService(
        Settings(ai_provider="bedrock", bedrock_model_id="test.model-v1:0"),
        bedrock_client=FakeBedrockClient(response),
    )

    result = service.extract_order("Extract.", "", [])

    assert result.items[0].article_number.value == "ART-1"


def test_bedrock_extraction_rejects_invalid_model_output():
    service = BedrockAIExtractionService(
        Settings(ai_provider="bedrock", bedrock_model_id="test.model-v1:0"),
        bedrock_client=FakeBedrockClient("not valid JSON"),
    )

    with pytest.raises(AIExtractionError, match="invalid order extraction"):
        service.extract_order("Extract.", "", [])


def test_extraction_provider_factory_defaults_to_mock():
    assert isinstance(
        build_ai_extraction_service(Settings(ai_provider="mock")),
        MockAIExtractionService,
    )


def test_bedrock_provider_requires_model_id():
    with pytest.raises(ExtractionConfigurationError, match="BEDROCK_MODEL_ID"):
        build_ai_extraction_service(Settings(ai_provider="bedrock", bedrock_model_id=""))
