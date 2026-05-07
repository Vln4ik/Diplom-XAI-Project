"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-04 17:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, create_type=False)


USER_STATUS = _enum("userstatus", "active", "invited", "blocked")
MEMBER_ROLE = _enum(
    "memberrole",
    "system_admin",
    "org_admin",
    "specialist",
    "approver",
    "viewer",
    "external_expert",
)
MEMBER_STATUS = _enum("memberstatus", "invited", "active", "blocked")
ORGANIZATION_TYPE = _enum("organizationtype", "educational", "other")
DOCUMENT_STATUS = _enum(
    "documentstatus",
    "uploaded",
    "queued",
    "processing",
    "processed",
    "requires_review",
    "failed",
    "outdated",
    "archived",
)
DOCUMENT_CATEGORY = _enum(
    "documentcategory",
    "normative",
    "methodological",
    "template",
    "internal_policy",
    "local_act",
    "data_table",
    "evidence",
    "prescription",
    "inspection_act",
    "previous_report",
    "other",
)
REPORT_STATUS = _enum(
    "reportstatus",
    "draft",
    "analyzing",
    "requires_review",
    "in_revision",
    "awaiting_approval",
    "approved",
    "exported",
    "archived",
)
REQUIREMENT_STATUS = _enum(
    "requirementstatus",
    "new",
    "applicable",
    "not_applicable",
    "needs_clarification",
    "data_found",
    "data_partial",
    "data_missing",
    "confirmed",
    "rejected",
    "included_in_report",
    "archived",
)
APPLICABILITY_STATUS = _enum("applicabilitystatus", "applicable", "not_applicable", "needs_clarification")
RISK_LEVEL = _enum("risklevel", "low", "medium", "high", "critical")
RISK_STATUS = _enum("riskstatus", "new", "in_progress", "resolved", "accepted", "rejected", "needs_review")
EXPORT_STATUS = _enum("exportstatus", "pending", "ready", "failed")
EXPORT_TYPE = _enum("exporttype", "docx", "matrix", "package")
NOTIFICATION_STATUS = _enum("notificationstatus", "unread", "read")
FRAGMENT_TYPE = _enum("fragmenttype", "paragraph", "table_row", "sheet_row", "page")


def _all_enums() -> tuple[sa.Enum, ...]:
    return (
        USER_STATUS,
        MEMBER_ROLE,
        MEMBER_STATUS,
        ORGANIZATION_TYPE,
        DOCUMENT_STATUS,
        DOCUMENT_CATEGORY,
        REPORT_STATUS,
        REQUIREMENT_STATUS,
        APPLICABILITY_STATUS,
        RISK_LEVEL,
        RISK_STATUS,
        EXPORT_STATUS,
        EXPORT_TYPE,
        NOTIFICATION_STATUS,
        FRAGMENT_TYPE,
    )


def _id_column() -> sa.Column:
    return sa.Column("id", sa.String(length=36), primary_key=True, nullable=False)


def _created_at_column() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _updated_at_column() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)


def _embedding_column_type() -> sa.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return Vector(32)
    return sa.JSON()


def _create_enum_types() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def _drop_enum_types() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for enum_type in reversed(_all_enums()):
        enum_type.drop(bind, checkfirst=True)


def upgrade() -> None:
    _create_enum_types()

    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("short_name", sa.String(length=255), nullable=True),
        sa.Column("inn", sa.String(length=12), nullable=True),
        sa.Column("kpp", sa.String(length=9), nullable=True),
        sa.Column("ogrn", sa.String(length=13), nullable=True),
        sa.Column("legal_address", sa.String(length=512), nullable=True),
        sa.Column("actual_address", sa.String(length=512), nullable=True),
        sa.Column("organization_type", ORGANIZATION_TYPE, nullable=False),
        sa.Column("okved", sa.String(length=32), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("director_name", sa.String(length=255), nullable=True),
        sa.Column("responsible_person", sa.String(length=255), nullable=True),
        sa.Column("profile_json", sa.JSON(), nullable=False),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index(op.f("ix_organizations_inn"), "organizations", ["inn"], unique=False)

    op.create_table(
        "users",
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("status", USER_STATUS, nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "organization_members",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", MEMBER_ROLE, nullable=False),
        sa.Column("status", MEMBER_STATUS, nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )
    op.create_index(op.f("ix_organization_members_organization_id"), "organization_members", ["organization_id"], unique=False)
    op.create_index(op.f("ix_organization_members_user_id"), "organization_members", ["user_id"], unique=False)

    op.create_table(
        "documents",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("uploaded_by_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("original_file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("category", DOCUMENT_CATEGORY, nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("status", DOCUMENT_STATUS, nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("document_date", sa.Date(), nullable=True),
        sa.Column("validity_until", sa.Date(), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index(op.f("ix_documents_organization_id"), "documents", ["organization_id"], unique=False)

    op.create_table(
        "reports",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("regulator", sa.String(length=128), nullable=False),
        sa.Column("report_type", sa.String(length=128), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("status", REPORT_STATUS, nullable=False),
        sa.Column("readiness_percent", sa.Float(), nullable=False),
        sa.Column(
            "responsible_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("selected_document_ids", sa.JSON(), nullable=False),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index(op.f("ix_reports_organization_id"), "reports", ["organization_id"], unique=False)

    op.create_table(
        "report_sections",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_id", sa.String(length=36), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("order_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("source_requirement_ids", sa.JSON(), nullable=False),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index(op.f("ix_report_sections_organization_id"), "report_sections", ["organization_id"], unique=False)
    op.create_index(op.f("ix_report_sections_report_id"), "report_sections", ["report_id"], unique=False)

    op.create_table(
        "document_fragments",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fragment_text", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("sheet_name", sa.String(length=255), nullable=True),
        sa.Column("row_start", sa.Integer(), nullable=True),
        sa.Column("row_end", sa.Integer(), nullable=True),
        sa.Column("paragraph_number", sa.Integer(), nullable=True),
        sa.Column("fragment_type", FRAGMENT_TYPE, nullable=False),
        sa.Column("embedding_vector", _embedding_column_type(), nullable=True),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index(op.f("ix_document_fragments_organization_id"), "document_fragments", ["organization_id"], unique=False)
    op.create_index(op.f("ix_document_fragments_document_id"), "document_fragments", ["document_id"], unique=False)

    op.create_table(
        "requirements",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_id", sa.String(length=36), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=True),
        sa.Column("regulator", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "source_document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_fragment_id",
            sa.String(length=36),
            sa.ForeignKey("document_fragments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("applicability_status", APPLICABILITY_STATUS, nullable=False),
        sa.Column("applicability_reason", sa.Text(), nullable=True),
        sa.Column("required_data", sa.JSON(), nullable=False),
        sa.Column("found_data", sa.JSON(), nullable=False),
        sa.Column("status", REQUIREMENT_STATUS, nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("risk_level", RISK_LEVEL, nullable=False),
        sa.Column("user_comment", sa.Text(), nullable=True),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index(op.f("ix_requirements_organization_id"), "requirements", ["organization_id"], unique=False)
    op.create_index(op.f("ix_requirements_report_id"), "requirements", ["report_id"], unique=False)

    op.create_table(
        "evidence",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requirement_id",
            sa.String(length=36),
            sa.ForeignKey("requirements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "fragment_id",
            sa.String(length=36),
            sa.ForeignKey("document_fragments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("evidence_type", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index(op.f("ix_evidence_organization_id"), "evidence", ["organization_id"], unique=False)
    op.create_index(op.f("ix_evidence_requirement_id"), "evidence", ["requirement_id"], unique=False)

    op.create_table(
        "explanations",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requirement_id",
            sa.String(length=36),
            sa.ForeignKey("requirements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_section_id",
            sa.String(length=36),
            sa.ForeignKey("report_sections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("conclusion", sa.Text(), nullable=False),
        sa.Column("logic_json", sa.JSON(), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "source_fragment_id",
            sa.String(length=36),
            sa.ForeignKey("document_fragments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("risk_level", RISK_LEVEL, nullable=False),
        sa.Column("explanation_text", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index(op.f("ix_explanations_organization_id"), "explanations", ["organization_id"], unique=False)
    op.create_index(op.f("ix_explanations_requirement_id"), "explanations", ["requirement_id"], unique=False)

    op.create_table(
        "risks",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_id", sa.String(length=36), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=True),
        sa.Column(
            "requirement_id",
            sa.String(length=36),
            sa.ForeignKey("requirements.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("risk_level", RISK_LEVEL, nullable=False),
        sa.Column("status", RISK_STATUS, nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("assigned_to_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index(op.f("ix_risks_organization_id"), "risks", ["organization_id"], unique=False)
    op.create_index(op.f("ix_risks_report_id"), "risks", ["report_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", NOTIFICATION_STATUS, nullable=False),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index(op.f("ix_notifications_organization_id"), "notifications", ["organization_id"], unique=False)
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _id_column(),
    )
    op.create_index(op.f("ix_audit_logs_organization_id"), "audit_logs", ["organization_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False)

    op.create_table(
        "export_files",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_id", sa.String(length=36), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_by_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("export_type", EXPORT_TYPE, nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("status", EXPORT_STATUS, nullable=False),
        _id_column(),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index(op.f("ix_export_files_organization_id"), "export_files", ["organization_id"], unique=False)
    op.create_index(op.f("ix_export_files_report_id"), "export_files", ["report_id"], unique=False)


def downgrade() -> None:
    op.drop_table("export_files")
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("risks")
    op.drop_table("explanations")
    op.drop_table("evidence")
    op.drop_table("requirements")
    op.drop_table("document_fragments")
    op.drop_table("report_sections")
    op.drop_table("reports")
    op.drop_table("documents")
    op.drop_table("organization_members")
    op.drop_table("users")
    op.drop_table("organizations")
    _drop_enum_types()
