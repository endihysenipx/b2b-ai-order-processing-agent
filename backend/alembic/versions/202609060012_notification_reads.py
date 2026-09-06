"""Per-user acknowledgement of current order notifications."""

import sqlalchemy as sa

from alembic import op

revision = "202609060012"
down_revision = "202609060011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("notification_reads",
                    sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
                    sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True),
                    sa.Column("fingerprint", sa.String(64), nullable=False),
                    sa.Column("is_read", sa.Boolean(), nullable=False),
                    sa.Column("updated_at", sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table("notification_reads")
