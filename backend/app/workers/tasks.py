from __future__ import annotations

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import Report, ReportStatus
from app.services.documents import process_document
from app.services.exports import export_evidence_package, export_matrix_xlsx, export_report_docx
from app.services.reports import analyze_report, generate_report_sections
from app.workers.celery_app import celery_app


@celery_app.task(name="document_process")
def document_process_task(document_id: str) -> str:
    session = get_session_factory()()
    try:
        process_document(session, document_id)
        return document_id
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
