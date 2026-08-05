"""add authenticator MFA and client-scoped access

Revision ID: 202608050003
Revises: 202607290002
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202608050003"
down_revision: str | None = "202607290002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_secret_encrypted", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("totp_pending_secret_encrypted", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("totp_last_used_step", sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column("recovery_code_hashes", sa.JSON(), nullable=False, server_default="[]"))
    op.create_table(
        "user_client_access",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("client_id", sa.String(), sa.ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
    )
    # Preserve existing operator visibility while making the grants explicit.
    op.execute(
        sa.text(
            "INSERT INTO user_client_access (user_id, client_id) "
            "SELECT users.id, clients.id FROM users CROSS JOIN clients "
            "WHERE users.role <> 'admin'"
        )
    )
    op.alter_column("users", "totp_enabled", server_default=None)
    op.alter_column("users", "auth_version", server_default=None)
    op.alter_column("users", "recovery_code_hashes", server_default=None)


def downgrade() -> None:
    op.drop_table("user_client_access")
    op.drop_column("users", "recovery_code_hashes")
    op.drop_column("users", "totp_last_used_step")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_pending_secret_encrypted")
    op.drop_column("users", "totp_secret_encrypted")
    op.drop_column("users", "auth_version")
