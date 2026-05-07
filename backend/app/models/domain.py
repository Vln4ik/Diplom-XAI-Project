from __future__ import annotations

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.models.base import Base, IdMixin, TimestampMixin, utcnow
from app.models.enums import (
    ApplicabilityStatus,
    DocumentCategory,
    DocumentStatus,
    ExportStatus,
    ExportType,
    FragmentType,
    MemberRole,
    MemberStatus,
    NotificationStatus,
    OrganizationType,
    ReportStatus,
    RequirementStatus,
    RiskLevel,
    RiskStatus,
    UserStatus,
)

EmbeddingType = Vector(get_settings().embedding_size).with_variant(JSON(), "sqlite")


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.active)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list["OrganizationMember"]] = relationship(back_populates="user")


class Organization(IdMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255))
    short_name: Mapped[str | None] = mapped_column(String(255))
    inn: Mapped[str | None] = mapped_column(String(12), index=True)
    kpp: Mapped[str | None] = mapped_column(String(9))
    ogrn: Mapped[str | None] = mapped_column(String(13))
    legal_address: Mapped[str | None] = mapped_column(String(512))
    actual_address: Mapped[str | None] = mapped_column(String(512))
    organization_type: Mapped[OrganizationType] = mapped_column(Enum(OrganizationType), default=OrganizationType.educational)
    okved: Mapped[str | None] = mapped_column(String(32))
    website: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    director_name: Mapped[str | None] = mapped_column(String(255))
    responsible_person: Mapped[str | None] = mapped_column(String(255))
    profile_json: Mapped[dict] = mapped_column(JSON, default=dict)

    members: Mapped[list["OrganizationMember"]] = relationship(back_populates="organization")
    documents: Mapped[list["Document"]] = relationship(back_populates="organization")
    reports: Mapped[list["Report"]] = relationship(back_populates="organization")


class OrganizationMember(IdMixin, TimestampMixin, Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[MemberRole] = mapped_column(Enum(MemberRole), default=MemberRole.specialist)
    status: Mapped[MemberStatus] = mapped_column(Enum(MemberStatus), default=MemberStatus.active)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped[Organization] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Document(IdMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    uploaded_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    file_name: Mapped[str] = mapped_column(String(255))
    original_file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(Integer)
    category: Mapped[DocumentCategory] = mapped_column(Enum(DocumentCategory), default=DocumentCategory.other)
    storage_path: Mapped[str] = mapped_column(String(512))
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), default=DocumentStatus.uploaded)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    document_date: Mapped[date | None] = mapped_column(Date)
    validity_until: Mapped[date | None] = mapped_column(Date)
    processing_error: Mapped[str | None] = mapped_column(Text)

    organization: Mapped[Organization] = relationship(back_populates="documents")
    fragments: Mapped[list["DocumentFragment"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentFragment(IdMixin, TimestampMixin, Base):
    __tablename__ = "document_fragments"

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    fragment_text: Mapped[str] = mapped_column(Text)
    search_text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    sheet_name: Mapped[str | None] = mapped_column(String(255))
    row_start: Mapped[int | None] = mapped_column(Integer)
    row_end: Mapped[int | None] = mapped_column(Integer)
    paragraph_number: Mapped[int | None] = mapped_column(Integer)
    fragment_type: Mapped[FragmentType] = mapped_column(Enum(FragmentType), default=FragmentType.paragraph)
    embedding_vector: Mapped[list[float] | None] = mapped_column(EmbeddingType)

    document: Mapped[Document] = relationship(back_populates="fragments")


class Report(IdMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    regulator: Mapped[str] = mapped_column(String(128), default="rosobrnadzor")
    report_type: Mapped[str] = mapped_column(String(128))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.draft)
    readiness_percent: Mapped[float] = mapped_column(Float, default=0.0)
    responsible_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    comment: Mapped[str | None] = mapped_column(Text)
    selected_document_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    organization: Mapped[Organization] = relationship(back_populates="reports")
    sections: Mapped[list["ReportSection"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    versions: Mapped[list["ReportVersion"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class ReportSection(IdMixin, TimestampMixin, Base):
    __tablename__ = "report_sections"

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    order_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(64), default="draft")
    source_requirement_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    report: Mapped[Report] = relationship(back_populates="sections")


class ReportVersion(IdMixin, TimestampMixin, Base):
    __tablename__ = "report_versions"
    __table_args__ = (UniqueConstraint("report_id", "version_number", name="uq_report_versions_report_version_number"),)

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    report_status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.draft)
    title: Mapped[str] = mapped_column(String(255))
    report_type: Mapped[str] = mapped_column(String(128))
    readiness_percent: Mapped[float] = mapped_column(Float, default=0.0)
    comment: Mapped[str | None] = mapped_column(Text)
    sections_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    matrix_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    explanations_json: Mapped[list[dict]] = mapped_column(JSON, default=list)

    report: Mapped[Report] = relationship(back_populates="versions")


class Requirement(IdMixin, TimestampMixin, Base):
    __tablename__ = "requirements"

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    regulator: Mapped[str] = mapped_column(String(128), default="rosobrnadzor")
    category: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    source_fragment_id: Mapped[str | None] = mapped_column(ForeignKey("document_fragments.id", ondelete="SET NULL"))
    applicability_status: Mapped[ApplicabilityStatus] = mapped_column(
        Enum(ApplicabilityStatus), default=ApplicabilityStatus.needs_clarification
    )
    applicability_reason: Mapped[str | None] = mapped_column(Text)
    required_data: Mapped[list[str]] = mapped_column(JSON, default=list)
    found_data: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[RequirementStatus] = mapped_column(Enum(RequirementStatus), default=RequirementStatus.new)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), default=RiskLevel.low)
    user_comment: Mapped[str | None] = mapped_column(Text)


class Evidence(IdMixin, TimestampMixin, Base):
    __tablename__ = "evidence"

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    fragment_id: Mapped[str | None] = mapped_column(ForeignKey("document_fragments.id", ondelete="SET NULL"))
    evidence_type: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(64), default="candidate")


class Explanation(IdMixin, TimestampMixin, Base):
    __tablename__ = "explanations"

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"), index=True)
    report_section_id: Mapped[str | None] = mapped_column(ForeignKey("report_sections.id", ondelete="SET NULL"))
    conclusion: Mapped[str] = mapped_column(Text)
    logic_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    source_fragment_id: Mapped[str | None] = mapped_column(ForeignKey("document_fragments.id", ondelete="SET NULL"))
    evidence_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), default=RiskLevel.low)
    explanation_text: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(Text)


class Risk(IdMixin, TimestampMixin, Base):
    __tablename__ = "risks"

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    requirement_id: Mapped[str | None] = mapped_column(ForeignKey("requirements.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), default=RiskLevel.low)
    status: Mapped[RiskStatus] = mapped_column(Enum(RiskStatus), default=RiskStatus.new)
    recommended_action: Mapped[str | None] = mapped_column(Text)
    assigned_to_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Notification(IdMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[NotificationStatus] = mapped_column(Enum(NotificationStatus), default=NotificationStatus.unread)


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_logs"

    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    entity_type: Mapped[str] = mapped_column(String(128))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(128))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExportFile(IdMixin, TimestampMixin, Base):
    __tablename__ = "export_files"

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    export_type: Mapped[ExportType] = mapped_column(Enum(ExportType))
    file_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(512))
    status: Mapped[ExportStatus] = mapped_column(Enum(ExportStatus), default=ExportStatus.pending)
