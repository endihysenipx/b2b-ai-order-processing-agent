from sqlalchemy import JSON, BigInteger, Boolean, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin

user_client_access = Table(
    "user_client_access",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("client_id", ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
)


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_version: Mapped[int] = mapped_column(Integer, default=0)
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_pending_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_last_used_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    recovery_code_hashes: Mapped[list[str]] = mapped_column(JSON, default=list)

    approved_orders = relationship("Order", back_populates="approved_by")
    clients = relationship("Client", secondary=user_client_access, back_populates="users")

    @property
    def client_ids(self) -> list[str]:
        return [client.id for client in self.clients]
