from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class Product(IdMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("client_id", "sku", name="uq_product_client_sku"),)

    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    sku: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500))
    unit: Mapped[str] = mapped_column(String(30), default="each")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    minimum_quantity: Mapped[int] = mapped_column(Integer, default=1)
    warehouse: Mapped[str] = mapped_column(String(100), default="Main")
    on_hand: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    stock_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
