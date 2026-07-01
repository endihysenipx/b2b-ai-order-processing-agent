from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin


class ValidationIssue(IdMixin, Base):
    __tablename__ = "validation_issues"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    field_name: Mapped[str] = mapped_column(String(150))
    issue_type: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(String(500))
    severity: Mapped[str] = mapped_column(String(50))
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    order = relationship("Order", back_populates="validation_issues")
