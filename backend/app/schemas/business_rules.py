from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Money = Annotated[Decimal, Field(ge=0, le=99999999, max_digits=10, decimal_places=2)]


class BusinessRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")
    freight_enabled: bool = False
    freight_below: Money = Decimal("500")
    freight_charge: Money = Decimal("35")
    discount_enabled: bool = False
    discount_from: Money = Decimal("1000")
    discount_percent: Decimal = Field(default=Decimal("5"), ge=0, le=100, decimal_places=2)
    minimum_enabled: bool = False
    minimum_order: Money = Decimal("250")
    review_enabled: bool = False
    review_from: Money = Decimal("2500")


class RulePreview(BaseModel):
    rules: BusinessRules
    subtotal: Money


class ClientCaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_id: str
    client_id: str
    label: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1, le=10000)
    unit_price: Money
    article_number: str = Field(min_length=1, max_length=100)
