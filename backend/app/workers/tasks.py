from __future__ import annotations

from celery.signals import task_failure
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import Document, DocumentStatus, ExpertiseWorkflow, Report, ReportStatus
from app.services.documents import describe_processing_error, process_document
from app.services.estimate_expertise import complete_replacement_recheck, run_estimate_expertise_pipeline
from app.services.exports import export_evidence_package, export_matrix_xlsx, export_report_docx
from app.services.reports import analyze_report, generate_report_sections
from app.workers.celery_app import celery_app

settings = get_settings()


@celery_app.task(
    name="document_process",
    soft_time_limit=settings.document_process_soft_time_limit_seconds,
    time_limit=settings.document_process_time_limit_seconds,
)
def document_process_task(document_id: str) -> str:
    session = get_session_factory()()
    try:
        process_document(session, document_id)
        return document_id
    finally:
        session.close()


@task_failure.connect
def mark_failed_document_process_task(
    sender: object | None = None,
    exception: BaseException | None = None,
    args: tuple[object, ...] | None = None,
    kwargs: dict[str, object] | None = None,
    **_: object,
) -> None:
    if getattr(sender, "name", None) not in {"document_process", "estimate_expertise_replacement_recheck"}:
        return

    document_id: str | None = None
    if getattr(sender, "name", None) == "document_process" and args:
        document_id = str(args[0])
    if getattr(sender, "name", None) == "estimate_expertise_replacement_recheck" and args and len(args) > 1:
        document_id = str(args[1])
    if document_id is None and kwargs:
        candidate = kwargs.get("document_id") or kwargs.get("replacement_document_id")
        document_id = str(candidate) if candidate else None
    if not document_id:
        return

    session = get_session_factory()()
    try:
        document = session.get(Document, document_id)
        if document is None or document.status not in {DocumentStatus.queued, DocumentStatus.processing}:
            return
        document.status = DocumentStatus.failed
        document.processing_error = describe_processing_error(exception or TimeoutError("document_process task failed"))
        session.add(document)
        session.commit()
    finally:
        session.close()


@celery_app.task(name="report_analyze")
def report_analyze_task(report_id: str) -> str:
    session = get_session_factory()()
    report: Report | None = None
    try:
        report = session.scalar(select(Report).where(Report.id == report_id))
        if report is None:
            raise ValueError("Report not found")
        analyze_report(session, report)
        return report_id
    except Exception as exc:
        if report is not None and report.status == ReportStatus.analyzing:
            report.status = ReportStatus.draft
            report.comment = f"Analysis failed: {exc}"
            session.add(report)
            session.commit()
        raise
    finally:
        session.close()


@celery_app.task(name="report_generate")
def report_generate_task(report_id: str) -> str:
    session = get_session_factory()()
    try:
        report = session.scalar(select(Report).where(Report.id == report_id))
        if report is None:
            raise ValueError("Report not found")
        generate_report_sections(session, report)
        return report_id
    finally:
        session.close()


@celery_app.task(name="estimate_expertise_start")
def estimate_expertise_start_task(report_id: str) -> str:
    session = get_session_factory()()
    report: Report | None = None
    try:
        report = session.scalar(select(Report).where(Report.id == report_id))
        run_estimate_expertise_pipeline(session, report_id)
        return report_id
    except Exception as exc:
        workflow = session.scalar(select(ExpertiseWorkflow).where(ExpertiseWorkflow.report_id == report_id))
        if workflow is not None:
            workflow.status = "blocked"
            workflow.state_json = {
                **(workflow.state_json or {}),
                "last_error": str(exc),
            }
            session.add(workflow)
        if report is not None and report.status == ReportStatus.analyzing:
            report.status = ReportStatus.requires_review
            report.comment = f"State expertise workflow failed: {exc}"
            session.add(report)
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task(
    name="estimate_expertise_replacement_recheck",
    soft_time_limit=settings.document_process_soft_time_limit_seconds,
    time_limit=settings.document_process_time_limit_seconds,
)
def estimate_expertise_replacement_recheck_task(
    finding_id: str,
    replacement_document_id: str,
    user_id: str | None,
    comment: str | None,
) -> str:
    session = get_session_factory()()
    try:
        process_document(session, replacement_document_id)
        complete_replacement_recheck(
            session,
            finding_id=finding_id,
            replacement_document_id=replacement_document_id,
            user_id=user_id,
            comment=comment,
        )
        return replacement_document_id
    finally:
        session.close()


@celery_app.task(name="report_export")
def report_export_task(report_id: str, export_kind: str, created_by_id: str | None) -> str:
    session = get_session_factory()()
    try:
        report = session.scalar(select(Report).where(Report.id == report_id))
        if report is None:
            raise ValueError("Report not found")
        if export_kind == "docx":
            export = export_report_docx(session, report, created_by_id)
        elif export_kind == "matrix":
            export = export_matrix_xlsx(session, report, created_by_id)
        else:
            export = export_evidence_package(session, report, created_by_id)
        return export.id
    finally:
        session.close()
