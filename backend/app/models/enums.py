from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    pass


class UserStatus(StrEnum):
    active = "active"
    invited = "invited"
    blocked = "blocked"


class MemberRole(StrEnum):
    system_admin = "system_admin"
    org_admin = "org_admin"
    specialist = "specialist"
    approver = "approver"
    viewer = "viewer"
    external_expert = "external_expert"


class MemberStatus(StrEnum):
    invited = "invited"
    active = "active"
    blocked = "blocked"


class OrganizationType(StrEnum):
    educational = "educational"
    other = "other"


class DocumentStatus(StrEnum):
    uploaded = "uploaded"
    queued = "queued"
    processing = "processing"
    processed = "processed"
    requires_review = "requires_review"
    failed = "failed"
    outdated = "outdated"
    archived = "archived"


class DocumentCategory(StrEnum):
    normative = "normative"
    methodological = "methodological"
    template = "template"
    internal_policy = "internal_policy"
    local_act = "local_act"
    data_table = "data_table"
    evidence = "evidence"
    prescription = "prescription"
    inspection_act = "inspection_act"
    previous_report = "previous_report"
    other = "other"


class ReportStatus(StrEnum):
    draft = "draft"
    analyzing = "analyzing"
    requires_review = "requires_review"
    in_revision = "in_revision"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    exported = "exported"
    archived = "archived"


class RequirementStatus(StrEnum):
    new = "new"
    applicable = "applicable"
    not_applicable = "not_applicable"
    needs_clarification = "needs_clarification"
    data_found = "data_found"
    data_partial = "data_partial"
    data_missing = "data_missing"
    confirmed = "confirmed"
    rejected = "rejected"
    included_in_report = "included_in_report"
    archived = "archived"


class ApplicabilityStatus(StrEnum):
    applicable = "applicable"
    not_applicable = "not_applicable"
    needs_clarification = "needs_clarification"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskStatus(StrEnum):
    new = "new"
    in_progress = "in_progress"
    resolved = "resolved"
    accepted = "accepted"
    rejected = "rejected"
    needs_review = "needs_review"


class ExportStatus(StrEnum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class ExportType(StrEnum):
    docx = "docx"
    matrix = "matrix"
    explanations = "explanations"
    package = "package"


class NotificationStatus(StrEnum):
    unread = "unread"
    read = "read"


class FragmentType(StrEnum):
    paragraph = "paragraph"
    table_row = "table_row"
    sheet_row = "sheet_row"
    page = "page"
