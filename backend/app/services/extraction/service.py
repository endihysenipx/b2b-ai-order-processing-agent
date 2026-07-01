from decimal import Decimal

from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    value: str | int | Decimal | None
    source_type: str
    source_file: str | None
    confidence: float = Field(ge=0, le=1)


class ExtractedOrderItem(BaseModel):
    article_number: ExtractedField
    model_number: ExtractedField | None = None
    quantity: ExtractedField
    unit_price: ExtractedField | None = None
    currency: ExtractedField | None = None


class ExtractedOrder(BaseModel):
    header: dict[str, ExtractedField]
    items: list[ExtractedOrderItem]


class AIExtractionService:
    def extract_order(self, client_prompt: str, email_content: str, documents: list[str]) -> ExtractedOrder:
        raise NotImplementedError


class MockAIExtractionService(AIExtractionService):
    def extract_order(self, client_prompt: str, email_content: str, documents: list[str]) -> ExtractedOrder:
        source_file = documents[0] if documents else None
        field = lambda value, confidence=0.94: ExtractedField(  # noqa: E731
            value=value,
            source_type="mock",
            source_file=source_file,
            confidence=confidence,
        )
        return ExtractedOrder(
            header={
                "ticket_number": field("TCK-MOCK-001"),
                "customer_number": field("CUST-1001"),
                "commission_number": field("COM-MOCK-001"),
                "delivery_address": field("42 Demo Street, Example City"),
            },
            items=[
                ExtractedOrderItem(
                    article_number=field("ART-MOCK-01"),
                    model_number=field("MODEL-A"),
                    quantity=field(2),
                    unit_price=field(Decimal("125.00")),
                    currency=field("EUR"),
                )
            ],
        )
