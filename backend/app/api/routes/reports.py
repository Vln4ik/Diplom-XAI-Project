from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ensure_org_access, get_current_user, get_db
from app.models import ExportFile, MemberRole, Organization, Report, ReportSection, ReportStatus, ReportVersion, User
from app.schemas import (
    ExportFileResponse,
    ReportCreate,
    ReportMatrixRowResponse,
    ReportResponse,
    ReportSectionResponse,
    ReportSectionUpdate,
    ReportUpdate,
    ReportVersionResponse,
)
from app.services.exports import export_evidence_package, export_explanations_html, export_matrix_xlsx, export_report_docx
from app.services.reports import (
    approve_report,
    build_report_matrix,
    restore_report_version,
    return_report_to_revision,
    submit_report_for_approval,
)
from app.workers.tasks import report_analyze_task, report_generate_task

router = APIRouter(tags=["reports"])


def _get_report_or_404(db: Session, report_id: str) -> Report:
    report = db.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


def _ensure_report_status(report: Report, *, allowed: set[ReportStatus], action: str) -> None:
    if report.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot {action} when report status is '{report.status.value}'",
        )


@router.get("/organizations/{organization_id}/reports", response_model=list[ReportResponse])
def list_reports(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Report]:
    ensure_org_access(db, organization_id=organization_id, user=user)
    return list(db.scalars(select(Report).where(Report.organization_id == organization_id).order_by(Report.created_at.desc())))


@router.post("/organizations/{organization_id}/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    organization_id: str,
    payload: ReportCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    ensure_org_access(db, organization_id=organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    organization = db.scalar(select(Organization).where(Organization.id == organization_id))
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    report = Report(organization_id=organization_id, **payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Report:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user)
    return report


@router.patch("/reports/{report_id}", response_model=ReportResponse)
def update_report(
    report_id: str,
    payload: ReportUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, field, value)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.post("/reports/{report_id}/analyze", response_model=ReportResponse)
def analyze(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    _ensure_report_status(report, allowed={ReportStatus.draft, ReportStatus.in_revision, ReportStatus.requires_review}, action="analyze")
    report.status = ReportStatus.analyzing
    db.add(report)
    db.commit()
    report_analyze_task.delay(report.id)
    db.refresh(report)
    return report


@router.post("/reports/{report_id}/generate", response_model=ReportResponse)
def generate(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    _ensure_report_status(report, allowed={ReportStatus.requires_review, ReportStatus.in_revision, ReportStatus.draft}, action="generate")
    report_generate_task.delay(report.id)
    db.refresh(report)
    return report


@router.post("/reports/{report_id}/submit-for-approval", response_model=ReportResponse)
def submit_for_approval(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(
        db,
        organization_id=report.organization_id,
        user=user,
        allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin],
    )
    _ensure_report_status(report, allowed={ReportStatus.draft, ReportStatus.requires_review, ReportStatus.in_revision}, action="submit")
    return submit_report_for_approval(db, report, user.id)


@router.post("/reports/{report_id}/approve", response_model=ReportResponse)
def approve(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(
        db,
        organization_id=report.organization_id,
        user=user,
        allowed_roles=[MemberRole.org_admin, MemberRole.approver, MemberRole.system_admin],
    )
    _ensure_report_status(report, allowed={ReportStatus.awaiting_approval}, action="approve")
    return approve_report(db, report, user.id)


@router.post("/reports/{report_id}/return-to-revision", response_model=ReportResponse)
def return_to_revision(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(
        db,
        organization_id=report.organization_id,
        user=user,
        allowed_roles=[MemberRole.org_admin, MemberRole.approver, MemberRole.system_admin],
    )
    _ensure_report_status(report, allowed={ReportStatus.awaiting_approval}, action="return to revision")
    return return_report_to_revision(db, report, user.id)


@router.get("/reports/{report_id}/sections", response_model=list[ReportSectionResponse])
def list_sections(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ReportSection]:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user)
    return list(db.scalars(select(ReportSection).where(ReportSection.report_id == report_id).order_by(ReportSection.order_number)))


@router.get("/reports/{report_id}/matrix", response_model=list[ReportMatrixRowResponse])
def get_report_matrix(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user)
    return build_report_matrix(db, report)


@router.get("/reports/{report_id}/versions", response_model=list[ReportVersionResponse])
def list_report_versions(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ReportVersion]:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user)
    return list(
        db.scalars(
            select(ReportVersion).where(ReportVersion.report_id == report_id).order_by(ReportVersion.version_number.desc())
        )
    )


@router.get("/report-versions/{version_id}", response_model=ReportVersionResponse)
def get_report_version(version_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReportVersion:
    version = db.scalar(select(ReportVersion).where(ReportVersion.id == version_id))
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report version not found")
    ensure_org_access(db, organization_id=version.organization_id, user=user)
    return version


@router.post("/report-versions/{version_id}/restore", response_model=ReportResponse)
def restore_version(version_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Report:
    version = db.scalar(select(ReportVersion).where(ReportVersion.id == version_id))
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report version not found")
    ensure_org_access(
        db,
        organization_id=version.organization_id,
        user=user,
        allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin],
    )
    return restore_report_version(db, version, user.id)


@router.patch("/reports/{report_id}/sections/{section_id}", response_model=ReportSectionResponse)
def update_section(
    report_id: str,
    section_id: str,
    payload: ReportSectionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportSection:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.approver, MemberRole.system_admin])
    section = db.scalar(select(ReportSection).where(ReportSection.id == section_id, ReportSection.report_id == report_id))
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(section, field, value)
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.post("/reports/{report_id}/export/docx", response_model=ExportFileResponse)
def export_docx(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ExportFile:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user)
    return export_report_docx(db, report, user.id)


@router.post("/reports/{report_id}/export/matrix", response_model=ExportFileResponse)
def export_matrix(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ExportFile:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user)
    return export_matrix_xlsx(db, report, user.id)


@router.post("/reports/{report_id}/export/package", response_model=ExportFileResponse)
def export_package(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ExportFile:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user)
    return export_evidence_package(db, report, user.id)


@router.post("/reports/{report_id}/export/explanations", response_model=ExportFileResponse)
def export_explanations(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ExportFile:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user)
    return export_explanations_html(db, report, user.id)


@router.get("/exports/{export_id}", response_model=ExportFileResponse)
def get_export(export_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ExportFile:
    export = db.scalar(select(ExportFile).where(ExportFile.id == export_id))
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    ensure_org_access(db, organization_id=export.organization_id, user=user)
    return export


@router.get("/exports/{export_id}/download")
def download_export(export_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    export = db.scalar(select(ExportFile).where(ExportFile.id == export_id))
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    ensure_org_access(db, organization_id=export.organization_id, user=user)
    return FileResponse(export.storage_path, filename=Path(export.storage_path).name)
