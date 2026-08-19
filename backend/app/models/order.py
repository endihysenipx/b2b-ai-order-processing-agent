from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class Order(IdMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    email_id: Mapped[str] = mapped_column(ForeignKey("emails.id"))
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"))
    ticket_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customer_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    commission_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    commission_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    store_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivery_week: Mapped[str | None] = mapped_column(String(50), nullable=True)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    requested_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(50), index=True)
    is_scanned_source: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    email = relationship("Email", back_populates="orders")
    client = relationship("Client", back_populates="orders")
    approved_by = relationship("User", back_populates="approved_orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="order")
    validation_issues = relationship("ValidationIssue", back_populates="order", cascade="all, delete-orphan")
    generated_xmls = relationship("GeneratedXML", back_populates="order", cascade="all, delete-orphan")
    feedback_issues = relationship("FeedbackIssue", back_populates="order")
