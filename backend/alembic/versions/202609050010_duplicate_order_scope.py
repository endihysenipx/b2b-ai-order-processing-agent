"""Index customer-scoped duplicate order lookups."""

from alembic import op

revision = "202609050010"
down_revision = "202609050009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_orders_duplicate_scope", "orders", ["client_id", "is_demo"])


def downgrade():
    op.drop_index("ix_orders_duplicate_scope", table_name="orders")
