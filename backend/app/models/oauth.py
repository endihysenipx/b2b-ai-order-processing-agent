from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class OAuthAuthorizationCode(Base, IdMixin, TimestampMixin):
    __tablename__ = "oauth_authorization_codes"

    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    client_id: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    auth_version: Mapped[int] = mapped_column(nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    resource: Mapped[str] = mapped_column(String(512), nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OAuthRefreshToken(Base, IdMixin, TimestampMixin):
    __tablename__ = "oauth_refresh_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    family_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    client_id: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    auth_version: Mapped[int] = mapped_column(nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    resource: Mapped[str] = mapped_column(String(512), nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OAuthClientAssertion(Base, IdMixin, TimestampMixin):
    __tablename__ = "oauth_client_assertions"

    jti_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    client_id: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
