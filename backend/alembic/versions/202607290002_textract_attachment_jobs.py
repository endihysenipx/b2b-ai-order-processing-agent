"""persist Textract attachment jobs

Revision ID: 202607290002
Revises: 202607010001
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607290002"
down_revision: str | None = "202607010001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "attachments",
        sa.Column("processing_status", sa.String(length=50), nullable=False, server_default="not_required"),
    )
    op.add_column("attachments", sa.Column("textract_job_id", sa.String(length=255), nullable=True))
    op.add_column("attachments", sa.Column("s3_object_key", sa.String(length=500), nullable=True))
    op.add_column("attachments", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.add_column("attachments", sa.Column("processing_error", sa.String(length=1000), nullable=True))
    op.add_column("attachments", sa.Column("processed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_attachments_processing_status", "attachments", ["processing_status"])
    op.create_index("ix_attachments_textract_job_id", "attachments", ["textract_job_id"])


def downgrade() -> None:
    op.drop_index("ix_attachments_textract_job_id", table_name="attachments")
    op.drop_index("ix_attachments_processing_status", table_name="attachments")
    op.drop_column("attachments", "processed_at")
    op.drop_column("attachments", "processing_error")
    op.drop_column("attachments", "extracted_text")
    op.drop_column("attachments", "s3_object_key")
    op.drop_column("attachments", "textract_job_id")
    op.drop_column("attachments", "processing_status")
