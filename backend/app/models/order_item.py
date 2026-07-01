from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class OrderItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    article_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    order = relationship("Order", back_populates="items")
