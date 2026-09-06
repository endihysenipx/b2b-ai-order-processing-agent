from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class StockReservation(IdMixin, TimestampMixin, Base):
    __tablename__ = "stock_reservations"
    __table_args__ = (UniqueConstraint("order_id", "product_id", name="uq_reservation_order_product"),
                      CheckConstraint("quantity > 0", name="ck_reservation_positive"))

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
