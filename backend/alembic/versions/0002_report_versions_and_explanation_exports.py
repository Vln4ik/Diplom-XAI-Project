"""report versions and explanations export

Revision ID: 0002_report_versions
Revises: 0001_initial_schema
Create Date: 2026-05-05 12:20:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_report_versions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE exporttype ADD VALUE IF NOT EXISTS 'explanations'")

    report_status = sa.Enum(
        "draft",
        "analyzing",
        "requires_review",
        "in_revision",
        "awaiting_approval",
        "approved",
        "exported",
        "archived",
        name="reportstatus",
        create_type=False,
    )

    op.create_table(
        "report_versions",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_id", sa.String(length=36), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("report_status", report_status, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("report_type", sa.String(length=128), nullable=False),
        sa.Column("readiness_percent", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("sections_json", sa.JSON(), nullable=False),
        sa.Column("matrix_json", sa.JSON(), nullable=False),
        sa.Column("explanations_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("report_id", "version_number", name="uq_report_versions_report_version_number"),
    )
    op.create_index(op.f("ix_report_versions_organization_id"), "report_versions", ["organization_id"], unique=False)
    op.create_index(op.f("ix_report_versions_report_id"), "report_versions", ["report_id"], unique=False)


def downgrade() -> None:
    op.drop_table("report_versions")
