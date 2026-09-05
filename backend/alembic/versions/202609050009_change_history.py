"""Transactional change history, retained independently of source records."""

import sqlalchemy as sa

from alembic import op

revision = "202609050009"
down_revision = "202609050008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("client_name", sa.String(200), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("entity_label", sa.String(200), nullable=False),
        sa.Column("order_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("batch_id", sa.String(), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_client_time", "audit_events", ["client_id", "created_at", "id"])
    op.create_index("ix_audit_entity_time", "audit_events", ["entity_type", "entity_id", "created_at"])
    op.create_index("ix_audit_order_time", "audit_events", ["order_id", "created_at"])
    op.create_index("ix_audit_events_batch_id", "audit_events", ["batch_id"])


def downgrade():
    op.drop_table("audit_events")
