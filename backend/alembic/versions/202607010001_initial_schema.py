"""initial schema

Revision ID: 202607010001
Revises:
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607010001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
    )
    op.create_table(
        "clients",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("customer_number", sa.String(length=100), nullable=False, unique=True),
        sa.Column("default_email", sa.String(length=255), nullable=True),
        sa.Column("email_domain", sa.String(length=150), nullable=False),
        sa.Column("extraction_prompt", sa.Text(), nullable=False),
        sa.Column("required_fields", sa.JSON(), nullable=False),
        sa.Column("validation_rules", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
    )
    op.create_table(
        "emails",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("external_message_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("conversation_id", sa.String(length=255), nullable=True, index=True),
        sa.Column("sender_email", sa.String(length=255), nullable=False),
        sa.Column("reply_to_email", sa.String(length=255), nullable=True),
        sa.Column("mail_to_email", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("classification_status", sa.String(length=50), nullable=False),
        sa.Column("client_id", sa.String(), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email_id", sa.String(), sa.ForeignKey("emails.id"), nullable=False),
        sa.Column("client_id", sa.String(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("ticket_number", sa.String(length=100), nullable=True),
        sa.Column("customer_number", sa.String(length=100), nullable=True),
        sa.Column("customer_name", sa.String(length=200), nullable=True),
        sa.Column("commission_number", sa.String(length=100), nullable=True),
        sa.Column("commission_name", sa.String(length=200), nullable=True),
        sa.Column("store_address", sa.String(length=500), nullable=True),
        sa.Column("delivery_address", sa.String(length=500), nullable=True),
        sa.Column("delivery_week", sa.String(length=50), nullable=True),
        sa.Column("order_date", sa.Date(), nullable=True),
        sa.Column("requested_delivery_date", sa.Date(), nullable=True),
        sa.Column("contact_person", sa.String(length=200), nullable=True),
        sa.Column("phone_number", sa.String(length=100), nullable=True),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, index=True),
        sa.Column("is_scanned_source", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approved_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        *timestamps(),
    )
    op.create_table(
        "order_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("article_number", sa.String(length=100), nullable=True),
        sa.Column("model_number", sa.String(length=100), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        *timestamps(),
    )
    op.create_table(
        "attachments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email_id", sa.String(), sa.ForeignKey("emails.id"), nullable=False),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("is_scanned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "validation_issues",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_name", sa.String(length=150), nullable=False),
        sa.Column("issue_type", sa.String(length=100), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "generated_xmls",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("xml_type", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "feedback_issues",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("reported_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("feedback_issues")
    op.drop_table("generated_xmls")
    op.drop_table("validation_issues")
    op.drop_table("attachments")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("emails")
    op.drop_table("clients")
    op.drop_table("users")
