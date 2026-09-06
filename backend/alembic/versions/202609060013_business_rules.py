"""Commercial rule snapshots and traceable client cases."""

import sqlalchemy as sa

from alembic import op

revision = "202609060013"
down_revision = "202609060012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", sa.Column("business_rules_snapshot", sa.JSON(), nullable=True))
    op.add_column("orders", sa.Column("case_source", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("orders", "case_source")
    op.drop_column("orders", "business_rules_snapshot")
