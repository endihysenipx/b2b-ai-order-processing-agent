from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    contact_name: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=50)
    approved_delivery_addresses: list[str] = Field(default_factory=list, max_length=100)
    is_active: bool = True
    master_data_enabled: bool = False

    @model_validator(mode="after")
    def addresses_valid(self):
        if any(not address.strip() or len(address) > 500 for address in self.approved_delivery_addresses):
            raise ValueError("Addresses must contain 1–500 characters")
        return self


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sku: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    unit: str = Field("each", min_length=1, max_length=30)
    is_active: bool = True
    aliases: list[str] = Field(default_factory=list, max_length=100)
    unit_price: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    minimum_quantity: int = Field(1, ge=1, le=2147483647)
    warehouse: str = Field("Main", min_length=1, max_length=100)
    on_hand: int | None = Field(None, ge=0, le=2147483647)
    reserved: int = Field(0, ge=0, le=2147483647)
    stock_updated_at: datetime | None = None

    @model_validator(mode="after")
    def coherent(self):
        self.aliases = [a.strip() for a in self.aliases]
        if any(not a or len(a) > 100 for a in self.aliases):
            raise ValueError("Aliases must contain 1–100 characters")
        if len(set(self.aliases + [self.sku])) != len(self.aliases) + 1:
            raise ValueError("SKU and aliases must be distinct")
        if (self.unit_price is None) != (self.currency is None):
            raise ValueError("Price and currency must be supplied together")
        if self.on_hand is None and (self.reserved or self.stock_updated_at):
            raise ValueError("Stock quantity is required with reservations or timestamp")
        if self.on_hand is not None and (self.reserved > self.on_hand or self.stock_updated_at is None):
            raise ValueError("Stock needs a timestamp and reservations cannot exceed on-hand quantity")
        if self.stock_updated_at:
            if self.stock_updated_at.tzinfo is None:
                raise ValueError("Stock timestamp must include a timezone")
            self.stock_updated_at = self.stock_updated_at.astimezone(UTC)
            if self.stock_updated_at > datetime.now(UTC):
                raise ValueError("Stock timestamp cannot be in the future")
        return self


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    client_id: str
    sku: str
    description: str
    unit: str
    is_active: bool
    aliases: list[str]
    unit_price: Decimal | None
    currency: str | None
    minimum_quantity: int
    warehouse: str
    on_hand: int | None
    reserved: int
    stock_updated_at: datetime | None

    @field_validator("stock_updated_at")
    @classmethod
    def stock_timestamp_utc(cls, value):
        # Database timestamps are stored as naive UTC; API timestamps must be explicit.
        if value is not None:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return value
