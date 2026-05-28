"""document relative path

Revision ID: 0005_document_relative_path
Revises: 0004_postgres_retrieval_indexes
Create Date: 2026-05-28 21:05:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_document_relative_path"
down_revision = "0004_postgres_retrieval_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("relative_path", sa.String(length=1024), nullable=True))

    op.create_index("ix_documents_org_relative_path", "documents", ["organization_id", "relative_path"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_documents_org_relative_path", table_name="documents")
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("relative_path")
