from app.api.routes.extraction import get_ai_extraction_service
from app.main import app
from app.services.extraction import ExtractedField, ExtractedOrder, ExtractedOrderItem


class FakeAIExtractionService:
    def extract_order(self, client_prompt, email_content, documents):
        assert client_prompt == "Extract this client's order."
        assert email_content == "Order email body"
        assert documents[0].file_name == "order.txt"
        return ExtractedOrder(
            header={
                "ticket_number": ExtractedField(
                    value="TCK-API-1",
                    source_type="email",
                    source_file=None,
                    confidence=0.99,
                )
            },
            items=[
                ExtractedOrderItem(
                    article_number=ExtractedField(
                        value="ART-API-1",
                        source_type="document",
                        source_file="order.txt",
                        confidence=0.98,
                    ),
                    quantity=ExtractedField(
                        value=3,
                        source_type="document",
                        source_file="order.txt",
                        confidence=0.98,
                    ),
                )
            ],
        )


def test_extract_order_endpoint_is_authenticated_and_uses_provider(client, auth_headers):
    unauthenticated = client.post(
        "/api/v1/extraction/order",
        json={
            "client_prompt": "Extract this client's order.",
            "email_content": "Order email body",
        },
    )
    assert unauthenticated.status_code == 401

    app.dependency_overrides[get_ai_extraction_service] = lambda: FakeAIExtractionService()
    try:
        response = client.post(
            "/api/v1/extraction/order",
            json={
                "client_prompt": "Extract this client's order.",
                "email_content": "Order email body",
                "documents": [
                    {
                        "file_name": "order.txt",
                        "content": "ART-API-1 x 3",
                    }
                ],
            },
            headers=auth_headers,
        )
    finally:
        app.dependency_overrides.pop(get_ai_extraction_service, None)

    assert response.status_code == 200
    assert response.json()["header"]["ticket_number"]["value"] == "TCK-API-1"
    assert response.json()["items"][0]["quantity"]["value"] == 3
