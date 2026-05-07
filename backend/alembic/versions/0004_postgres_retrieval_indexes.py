"""postgres retrieval indexes

Revision ID: 0004_postgres_retrieval_indexes
Revises: 0003_document_file_type_255
Create Date: 2026-05-07 01:45:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_postgres_retrieval_indexes"
down_revision = "0003_document_file_type_255"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_org_status_category "
        "ON documents (organization_id, status, category)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_fragments_document_created_at "
        "ON document_fragments (document_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_fragments_search_tsv_russian "
        "ON document_fragments USING GIN (to_tsvector('russian', search_text))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_fragments_embedding_ivfflat "
        "ON document_fragments USING ivfflat (embedding_vector vector_cosine_ops) "
        "WITH (lists = 32)"
    )
    op.execute("ANALYZE documents")
    op.execute("ANALYZE document_fragments")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_document_fragments_embedding_ivfflat")
    op.execute("DROP INDEX IF EXISTS ix_document_fragments_search_tsv_russian")
    op.execute("DROP INDEX IF EXISTS ix_document_fragments_document_created_at")
    op.execute("DROP INDEX IF EXISTS ix_documents_org_status_category")
