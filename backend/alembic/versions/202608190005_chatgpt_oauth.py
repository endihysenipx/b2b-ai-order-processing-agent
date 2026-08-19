"""add ChatGPT OAuth grants

Revision ID: 202608190005
Revises: 202608050004
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202608190005"
down_revision: str | None = "202608050004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_authorization_codes",
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=512), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("auth_version", sa.Integer(), nullable=False),
        sa.Column("redirect_uri", sa.String(length=1024), nullable=False),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("resource", sa.String(length=512), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oauth_authorization_codes_client_id", "oauth_authorization_codes", ["client_id"])
    op.create_index("ix_oauth_authorization_codes_code_hash", "oauth_authorization_codes", ["code_hash"], unique=True)
    op.create_index("ix_oauth_authorization_codes_expires_at", "oauth_authorization_codes", ["expires_at"])
    op.create_index("ix_oauth_authorization_codes_user_id", "oauth_authorization_codes", ["user_id"])

    op.create_table(
        "oauth_refresh_tokens",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(), nullable=False),
        sa.Column("client_id", sa.String(length=512), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("auth_version", sa.Integer(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("resource", sa.String(length=512), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oauth_refresh_tokens_client_id", "oauth_refresh_tokens", ["client_id"])
    op.create_index("ix_oauth_refresh_tokens_expires_at", "oauth_refresh_tokens", ["expires_at"])
    op.create_index("ix_oauth_refresh_tokens_family_id", "oauth_refresh_tokens", ["family_id"])
    op.create_index("ix_oauth_refresh_tokens_token_hash", "oauth_refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_oauth_refresh_tokens_user_id", "oauth_refresh_tokens", ["user_id"])

    op.create_table(
        "oauth_client_assertions",
        sa.Column("jti_hash", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=512), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oauth_client_assertions_client_id", "oauth_client_assertions", ["client_id"])
    op.create_index("ix_oauth_client_assertions_expires_at", "oauth_client_assertions", ["expires_at"])
    op.create_index("ix_oauth_client_assertions_jti_hash", "oauth_client_assertions", ["jti_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("oauth_client_assertions")
    op.drop_table("oauth_refresh_tokens")
    op.drop_table("oauth_authorization_codes")
