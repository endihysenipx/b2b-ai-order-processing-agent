from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin


class Attachment(IdMixin, Base):
    __tablename__ = "attachments"

    email_id: Mapped[str] = mapped_column(ForeignKey("emails.id"))
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(500))
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    email = relationship("Email", back_populates="attachments")
    order = relationship("Order", back_populates="attachments")
