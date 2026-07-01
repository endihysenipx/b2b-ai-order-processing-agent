from decimal import Decimal

from pydantic import BaseModel


class OrderItemOut(BaseModel):
    id: str
    article_number: str | None
    model_number: str | None
    quantity: int | None
    unit_price: Decimal | None
    total_price: Decimal | None
    currency: str | None

    model_config = {"from_attributes": True}


class OrderItemUpdate(BaseModel):
    article_number: str | None = None
    model_number: str | None = None
    quantity: int | None = None
    unit_price: Decimal | None = None
