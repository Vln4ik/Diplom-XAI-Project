"""expand document file_type length

Revision ID: 0003_document_file_type_255
Revises: 0002_report_versions
Create Date: 2026-05-06 13:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_document_file_type_255"
down_revision = "0002_report_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column(
            "file_type",
            existing_type=sa.String(length=64),
            type_=sa.String(length=255),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column(
            "file_type",
            existing_type=sa.String(length=255),
            type_=sa.String(length=64),
            existing_nullable=False,
        )
