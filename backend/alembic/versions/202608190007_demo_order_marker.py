"""mark synthetic demonstration orders

Revision ID: 202608190007
Revises: 202608190006
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202608190007"
down_revision: str | None = "202608190006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index("ix_orders_is_demo", "orders", ["is_demo"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orders_is_demo", table_name="orders")
    op.drop_column("orders", "is_demo")
