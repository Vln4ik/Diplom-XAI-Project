from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import ensure_org_access, get_current_user, get_db
from app.core.config import get_settings
from app.models import (
    Document,
    DocumentCategory,
    DocumentStatus,
    Evidence,
    ExpertiseFinding,
    ExpertiseUserDecision,
    ExpertiseWorkflow,
    ExpertiseWorkflowStage,
    Explanation,
    ExportFile,
    MemberRole,
    Organization,
    Report,
    ReportSection,
    ReportStatus,
    ReportVersion,
    Requirement,
    Risk,
    User,
)
from app.schemas import (
    EstimateExpertiseDecisionRequest,
    EstimateExpertiseDecisionLogResponse,
    EstimateExpertiseWorkflowResponse,
    ExportFileResponse,
    ReportCreate,
    ReportMatrixRowResponse,
    ReportResponse,
    ReportSectionResponse,
    ReportSectionUpdate,
    ReportUpdate,
    ReportVersionResponse,
)
from app.services.documents import create_document_record
from app.services.estimate_expertise import (
    ensure_estimate_expertise_workflow,
    mark_workflow_start_queued,
    record_replacement_started,
    record_finding_decision,
    serialize_workflow,
    workflow_needs_pipeline_run,
)
from app.services.exports import export_evidence_package, export_explanations_html, export_matrix_xlsx, export_report_docx
from app.services.reports import (
    approve_report,
    build_report_matrix,
    restore_report_version,
    return_report_to_revision,
    submit_report_for_approval,
)
from app.services.report_types import requires_special_workflow
from app.services.storage import storage
from app.workers.tasks import (
    document_process_task,
    estimate_expertise_replacement_recheck_task,
    estimate_expertise_start_task,
    report_analyze_task,
    report_generate_task,
)

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


def _ensure_special_workflow_report(report: Report) -> None:
    if not requires_special_workflow(report.report_type):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This report type does not use the state expertise workflow",
        )


def _get_expertise_finding_or_404(db: Session, finding_id: str) -> ExpertiseFinding:
    finding = db.scalar(select(ExpertiseFinding).where(ExpertiseFinding.id == finding_id))
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expertise finding not found")
    return finding


def _format_decision_log_label(status_value: str) -> str:
    return {
        "approved": "Пользователь одобрил вывод и разрешил использовать его дальше в проверке.",
        "skipped": "Пользователь пропустил вывод и исключил его из дальнейшей проверки.",
    }.get(status_value, "Решение пользователя сохранено.")


def _dedupe_ids(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _validate_selected_document_ids(
    db: Session,
    *,
    organization_id: str,
    document_ids: list[str],
    report_type: str,
) -> list[str]:
    unique_ids = _dedupe_ids(document_ids)
    settings = get_settings()
    max_documents = (
        settings.special_workflow_max_selected_documents
        if requires_special_workflow(report_type)
        else settings.report_max_selected_documents
    )
    if len(unique_ids) > max_documents:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Too many selected documents: {len(unique_ids)}. Limit: {max_documents}.",
        )
    if not unique_ids:
        return []

    owned_ids = set(
        db.scalars(
            select(Document.id).where(
                Document.organization_id == organization_id,
                Document.id.in_(unique_ids),
            )
        )
    )
    missing_or_forbidden = [document_id for document_id in unique_ids if document_id not in owned_ids]
    if missing_or_forbidden:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Selected documents must belong to the report organization.",
        )
    return unique_ids


def _count_special_workflow_documents(db: Session, report: Report) -> int:
    query = select(Document.id).where(
        Document.organization_id == report.organization_id,
        Document.status.in_((DocumentStatus.processed, DocumentStatus.requires_review)),
    )
    if report.selected_document_ids:
        query = query.where(Document.id.in_(report.selected_document_ids))
    return len(list(db.scalars(query)))


def _ensure_special_workflow_volume(db: Session, report: Report) -> None:
    max_documents = get_settings().special_workflow_max_selected_documents
    document_count = _count_special_workflow_documents(db, report)
    if document_count > max_documents:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Special workflow selected {document_count} ready documents. "
                f"Limit is {max_documents}; split the package or select a smaller folder."
            ),
        )


async def _save_replacement_upload_stream(
    *,
    organization_id: str,
    file: UploadFile,
    file_name: str,
) -> tuple[str, int]:
    settings = get_settings()
    target = storage.create_document_path(organization_id, file_name)
    written = 0
    try:
        with target.open("wb") as output:
            while True:
                chunk = await file.read(max(8192, settings.upload_read_chunk_bytes))
                if not chunk:
                    break
                written += len(chunk)
                if settings.upload_max_file_bytes > 0 and written > settings.upload_max_file_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"Replacement file '{file_name}' exceeds upload limit "
                            f"{settings.upload_max_file_bytes // (1024 * 1024)} MB"
                        ),
                    )
                output.write(chunk)
    except Exception:
        storage.delete_file(str(target))
        raise
    finally:
        await file.close()
    if written == 0:
        storage.delete_file(str(target))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Replacement file is empty")
    return str(target), written


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
    data = payload.model_dump()
    data["selected_document_ids"] = _validate_selected_document_ids(
        db,
        organization_id=organization_id,
        document_ids=data.get("selected_document_ids") or [],
        report_type=data["report_type"],
    )
    report = Report(organization_id=organization_id, **data)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.post("/reports/{report_id}/estimate-expertise/start", response_model=EstimateExpertiseWorkflowResponse)
def start_estimate_expertise_workflow(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    _ensure_special_workflow_report(report)
    _ensure_special_workflow_volume(db, report)
    workflow = ensure_estimate_expertise_workflow(db, report)
    if workflow_needs_pipeline_run(db, workflow):
        mark_workflow_start_queued(db, workflow)
        estimate_expertise_start_task.delay(report.id)
        db.refresh(workflow)
    return serialize_workflow(db, workflow)


@router.get("/reports/{report_id}/estimate-expertise/state", response_model=EstimateExpertiseWorkflowResponse)
def get_estimate_expertise_workflow_state(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user)
    _ensure_special_workflow_report(report)
    workflow = ensure_estimate_expertise_workflow(db, report)
    return serialize_workflow(db, workflow)


@router.get("/organizations/{organization_id}/estimate-expertise/decisions", response_model=list[EstimateExpertiseDecisionLogResponse])
def list_estimate_expertise_decisions(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    ensure_org_access(db, organization_id=organization_id, user=user)
    rows = db.execute(
        select(ExpertiseUserDecision, ExpertiseFinding, Report, ExpertiseWorkflowStage, Document)
        .join(ExpertiseFinding, ExpertiseFinding.id == ExpertiseUserDecision.finding_id)
        .join(Report, Report.id == ExpertiseFinding.report_id)
        .outerjoin(ExpertiseWorkflowStage, ExpertiseWorkflowStage.id == ExpertiseFinding.stage_id)
        .outerjoin(Document, Document.id == ExpertiseFinding.document_id)
        .where(ExpertiseUserDecision.organization_id == organization_id)
        .where(ExpertiseFinding.user_decision_status.in_(["approved", "skipped"]))
        .where(ExpertiseUserDecision.decision_type.in_(["approve", "skip"]))
        .order_by(ExpertiseUserDecision.created_at.desc())
    ).all()

    latest_by_finding: dict[str, dict] = {}
    for decision, finding, report, stage, document in rows:
        if finding.id in latest_by_finding:
            continue
        decision_status = finding.user_decision_status or (decision.payload_json or {}).get("decision_status") or decision.decision_type
        latest_by_finding[finding.id] = {
            "id": decision.id,
            "created_at": decision.created_at,
            "updated_at": decision.updated_at,
            "organization_id": decision.organization_id,
            "report_id": report.id,
            "report_title": report.title,
            "report_type": report.report_type,
            "workflow_id": decision.workflow_id,
            "finding_id": finding.id,
            "finding_title": finding.title,
            "finding_description": finding.description,
            "finding_severity": finding.severity,
            "stage_key": finding.stage_key,
            "stage_title": stage.short_title if stage is not None else finding.stage_key,
            "document_id": finding.document_id,
            "document_name": document.file_name if document is not None else "Пакет документов",
            "decision_status": decision_status,
            "decision_type": decision.decision_type,
            "decision_label": _format_decision_log_label(decision_status),
            "comment": decision.comment,
            "normative_basis": finding.normative_basis,
            "source_ref": finding.source_ref,
            "recommendation": finding.recommendation,
            "confidence_score": finding.confidence_score,
            "xai_summary": finding.xai_json or [],
        }

    return list(latest_by_finding.values())


@router.post("/estimate-expertise/findings/{finding_id}/approve", response_model=EstimateExpertiseWorkflowResponse)
def approve_estimate_expertise_finding(
    finding_id: str,
    payload: EstimateExpertiseDecisionRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    finding = _get_expertise_finding_or_404(db, finding_id)
    ensure_org_access(db, organization_id=finding.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    workflow = record_finding_decision(db, finding, user_id=user.id, decision_type="approve", comment=payload.comment if payload else None)
    return serialize_workflow(db, workflow)


@router.post("/estimate-expertise/findings/{finding_id}/skip", response_model=EstimateExpertiseWorkflowResponse)
def skip_estimate_expertise_finding(
    finding_id: str,
    payload: EstimateExpertiseDecisionRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    finding = _get_expertise_finding_or_404(db, finding_id)
    ensure_org_access(db, organization_id=finding.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    workflow = record_finding_decision(db, finding, user_id=user.id, decision_type="skip", comment=payload.comment if payload else None)
    return serialize_workflow(db, workflow)


@router.post("/estimate-expertise/findings/{finding_id}/replacement", response_model=EstimateExpertiseWorkflowResponse)
async def upload_estimate_expertise_replacement(
    finding_id: str,
    file: UploadFile = File(...),
    comment: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    finding = _get_expertise_finding_or_404(db, finding_id)
    ensure_org_access(db, organization_id=finding.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    file_name = file.filename or "replacement.bin"
    storage_path, file_size = await _save_replacement_upload_stream(
        organization_id=finding.organization_id,
        file=file,
        file_name=file_name,
    )
    replacement_document = create_document_record(
        db,
        organization_id=finding.organization_id,
        uploaded_by_id=user.id,
        file_name=file_name,
        storage_path=storage_path,
        file_size=file_size,
        content_type=file.content_type,
        category=DocumentCategory.evidence,
        tags=["estimate_expertise_replacement"],
        relative_path=f"estimate-expertise/replacements/{file_name}",
    )
    replacement_document.status = DocumentStatus.queued
    db.add(replacement_document)
    db.commit()
    db.refresh(replacement_document)
    workflow = record_replacement_started(
        db,
        finding,
        user_id=user.id,
        comment=comment,
        replacement_document=replacement_document,
    )
    estimate_expertise_replacement_recheck_task.delay(finding.id, replacement_document.id, user.id, comment)
    db.expire_all()
    db.refresh(workflow)
    return serialize_workflow(db, workflow)


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
    data = payload.model_dump(exclude_unset=True)
    next_report_type = data.get("report_type", report.report_type)
    if "selected_document_ids" in data:
        data["selected_document_ids"] = _validate_selected_document_ids(
            db,
            organization_id=report.organization_id,
            document_ids=data["selected_document_ids"] or [],
            report_type=next_report_type,
        )
    for field, value in data.items():
        setattr(report, field, value)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.delete("/reports/{report_id}", response_model=ReportResponse)
def delete_report(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Report:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(
        db,
        organization_id=report.organization_id,
        user=user,
        allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin],
    )
    workflow_ids = select(ExpertiseWorkflow.id).where(ExpertiseWorkflow.report_id == report_id)
    requirement_ids = select(Requirement.id).where(Requirement.report_id == report_id)

    db.execute(delete(ExpertiseUserDecision).where(ExpertiseUserDecision.workflow_id.in_(workflow_ids)))
    db.execute(delete(ExpertiseFinding).where(ExpertiseFinding.report_id == report_id))
    db.execute(delete(ExpertiseWorkflowStage).where(ExpertiseWorkflowStage.workflow_id.in_(workflow_ids)))
    db.execute(delete(ExpertiseWorkflow).where(ExpertiseWorkflow.report_id == report_id))
    db.execute(delete(Evidence).where(Evidence.requirement_id.in_(requirement_ids)))
    db.execute(delete(Explanation).where(Explanation.requirement_id.in_(requirement_ids)))
    db.execute(delete(Risk).where(Risk.report_id == report_id))
    db.execute(delete(Requirement).where(Requirement.report_id == report_id))
    db.execute(delete(ExportFile).where(ExportFile.report_id == report_id))
    db.execute(delete(ReportSection).where(ReportSection.report_id == report_id))
    db.execute(delete(ReportVersion).where(ReportVersion.report_id == report_id))
    db.delete(report)
    db.commit()
    return report


@router.post("/reports/{report_id}/analyze", response_model=ReportResponse)
def analyze(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    report = _get_report_or_404(db, report_id)
    ensure_org_access(db, organization_id=report.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    if requires_special_workflow(report.report_type):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This report type requires a specialized state expertise workflow",
        )
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
    if requires_special_workflow(report.report_type):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This report type requires a specialized state expertise workflow",
        )
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
