from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    article_number: str | None = Field(None, max_length=100)
    model_number: str | None = Field(None, max_length=100)
    quantity: int | None = Field(None, ge=1, le=2147483647, strict=True)
    unit_price: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    total_price: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
