from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class Client(IdMixin, TimestampMixin, Base):
    __tablename__ = "clients"

    client_name: Mapped[str] = mapped_column(String(200))
    customer_number: Mapped[str] = mapped_column(String(100), unique=True)
    default_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_domain: Mapped[str] = mapped_column(String(150))
    extraction_prompt: Mapped[str] = mapped_column(Text)
    required_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    validation_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    approved_delivery_addresses: Mapped[list[str]] = mapped_column(JSON, default=list)
    master_data_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    emails = relationship("Email", back_populates="client")
    orders = relationship("Order", back_populates="client")
    users = relationship("User", secondary="user_client_access", back_populates="clients")
