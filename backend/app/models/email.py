from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin


class Email(IdMixin, Base):
    __tablename__ = "emails"

    external_message_id: Mapped[str] = mapped_column(String(255), unique=True)
    conversation_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    sender_email: Mapped[str] = mapped_column(String(255))
    reply_to_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mail_to_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime)
    classification_status: Mapped[str] = mapped_column(String(50))
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    client = relationship("Client", back_populates="emails")
    order = relationship("Order", back_populates="email", uselist=False)
    attachments = relationship("Attachment", back_populates="email")
