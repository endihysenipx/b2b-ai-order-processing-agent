from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin


class FeedbackIssue(IdMixin, Base):
    __tablename__ = "feedback_issues"

    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    reported_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="Open")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    order = relationship("Order", back_populates="feedback_issues")
