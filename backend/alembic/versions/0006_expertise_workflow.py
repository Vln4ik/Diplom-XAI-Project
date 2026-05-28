"""expertise workflow

Revision ID: 0006_expertise_workflow
Revises: 0005_document_relative_path
Create Date: 2026-05-28 22:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_expertise_workflow"
down_revision = "0005_document_relative_path"
branch_labels = None
depends_on = None


def _id_column() -> sa.Column:
    return sa.Column("id", sa.String(length=36), primary_key=True, nullable=False)


def _created_at_column() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _updated_at_column() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "expertise_workflows",
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_id", sa.String(length=36), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("eta_seconds", sa.Integer(), nullable=False),
        sa.Column("checked_files", sa.Integer(), nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False),
        sa.Column("unresolved_findings", sa.Integer(), nullable=False),
        sa.Column("current_stage_key", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("rule_version", sa.String(length=128), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("report_id", name="uq_expertise_workflows_report_id"),
    )
    op.create_index("ix_expertise_workflows_organization_id", "expertise_workflows", ["organization_id"])
    op.create_index("ix_expertise_workflows_report_id", "expertise_workflows", ["report_id"])

    op.create_table(
        "expertise_workflow_stages",
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), sa.ForeignKey("expertise_workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("short_title", sa.String(length=128), nullable=False),
        sa.Column("order_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("checked_files", sa.Integer(), nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False),
        sa.Column("findings_count", sa.Integer(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("workflow_id", "stage_key", name="uq_expertise_stage_workflow_key"),
    )
    op.create_index("ix_expertise_workflow_stages_organization_id", "expertise_workflow_stages", ["organization_id"])
    op.create_index("ix_expertise_workflow_stages_workflow_id", "expertise_workflow_stages", ["workflow_id"])

    op.create_table(
        "expertise_findings",
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_id", sa.String(length=36), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), sa.ForeignKey("expertise_workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", sa.String(length=36), sa.ForeignKey("expertise_workflow_stages.id", ondelete="CASCADE"), nullable=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stage_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("normative_basis", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("xai_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("user_decision_status", sa.String(length=64), nullable=True),
        sa.Column("replacement_document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("replacement_file_name", sa.String(length=255), nullable=True),
        sa.Column("replacement_progress", sa.Integer(), nullable=False),
    )
    op.create_index("ix_expertise_findings_organization_id", "expertise_findings", ["organization_id"])
    op.create_index("ix_expertise_findings_report_id", "expertise_findings", ["report_id"])
    op.create_index("ix_expertise_findings_workflow_id", "expertise_findings", ["workflow_id"])
    op.create_index("ix_expertise_findings_stage_id", "expertise_findings", ["stage_id"])
    op.create_index("ix_expertise_findings_document_id", "expertise_findings", ["document_id"])

    op.create_table(
        "expertise_user_decisions",
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), sa.ForeignKey("expertise_workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", sa.String(length=36), sa.ForeignKey("expertise_findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decision_type", sa.String(length=64), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("replacement_document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("replacement_file_name", sa.String(length=255), nullable=True),
        sa.Column("replacement_progress", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_expertise_user_decisions_organization_id", "expertise_user_decisions", ["organization_id"])
    op.create_index("ix_expertise_user_decisions_workflow_id", "expertise_user_decisions", ["workflow_id"])
    op.create_index("ix_expertise_user_decisions_finding_id", "expertise_user_decisions", ["finding_id"])
    op.create_index("ix_expertise_user_decisions_user_id", "expertise_user_decisions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_expertise_user_decisions_user_id", table_name="expertise_user_decisions")
    op.drop_index("ix_expertise_user_decisions_finding_id", table_name="expertise_user_decisions")
    op.drop_index("ix_expertise_user_decisions_workflow_id", table_name="expertise_user_decisions")
    op.drop_index("ix_expertise_user_decisions_organization_id", table_name="expertise_user_decisions")
    op.drop_table("expertise_user_decisions")

    op.drop_index("ix_expertise_findings_document_id", table_name="expertise_findings")
    op.drop_index("ix_expertise_findings_stage_id", table_name="expertise_findings")
    op.drop_index("ix_expertise_findings_workflow_id", table_name="expertise_findings")
    op.drop_index("ix_expertise_findings_report_id", table_name="expertise_findings")
    op.drop_index("ix_expertise_findings_organization_id", table_name="expertise_findings")
    op.drop_table("expertise_findings")

    op.drop_index("ix_expertise_workflow_stages_workflow_id", table_name="expertise_workflow_stages")
    op.drop_index("ix_expertise_workflow_stages_organization_id", table_name="expertise_workflow_stages")
    op.drop_table("expertise_workflow_stages")

    op.drop_index("ix_expertise_workflows_report_id", table_name="expertise_workflows")
    op.drop_index("ix_expertise_workflows_organization_id", table_name="expertise_workflows")
    op.drop_table("expertise_workflows")
