"""Customer catalog, pricing and stock snapshots."""
import sqlalchemy as sa

from alembic import op

revision = "202609050008"
down_revision = "202608190007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clients", sa.Column("contact_name", sa.String(200), nullable=True))
    op.add_column("clients", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("clients", sa.Column("approved_delivery_addresses", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("clients", sa.Column("master_data_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "products",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("client_id", sa.String(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("minimum_quantity", sa.Integer(), nullable=False),
        sa.Column("warehouse", sa.String(100), nullable=False),
        sa.Column("on_hand", sa.Integer(), nullable=True),
        sa.Column("reserved", sa.Integer(), nullable=False),
        sa.Column("stock_updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("client_id", "sku", name="uq_product_client_sku"),
    )
    op.create_index("ix_products_client_id", "products", ["client_id"])


def downgrade():
    op.drop_table("products")
    for column in ["master_data_enabled", "approved_delivery_addresses", "phone", "contact_name"]:
        op.drop_column("clients", column)
