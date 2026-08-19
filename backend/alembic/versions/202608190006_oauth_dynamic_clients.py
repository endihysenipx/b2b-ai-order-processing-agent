"""add OAuth dynamic clients

Revision ID: 202608190006
Revises: 202608190005
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202608190006"
down_revision: str | None = "202608190005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_dynamic_clients",
        sa.Column("client_id", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oauth_dynamic_clients_client_id", "oauth_dynamic_clients", ["client_id"], unique=True)


def downgrade() -> None:
    op.drop_table("oauth_dynamic_clients")
