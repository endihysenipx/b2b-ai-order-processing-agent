"""Track order stock allocations separately from external reservations."""

import sqlalchemy as sa

from alembic import op

revision = "202609060011"
down_revision = "202609050010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stock_reservations",
                    sa.Column("id", sa.String(), primary_key=True),
                    sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id"), nullable=False),
                    sa.Column("product_id", sa.String(), sa.ForeignKey("products.id"), nullable=False),
                    sa.Column("quantity", sa.Integer(), nullable=False),
                    sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
                    sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
                    sa.UniqueConstraint("order_id", "product_id", name="uq_reservation_order_product"),
                    sa.CheckConstraint("quantity > 0", name="ck_reservation_positive"))
    op.create_index("ix_stock_reservations_order_id", "stock_reservations", ["order_id"])
    op.create_index("ix_stock_reservations_product_id", "stock_reservations", ["product_id"])


def downgrade():
    op.drop_table("stock_reservations")
