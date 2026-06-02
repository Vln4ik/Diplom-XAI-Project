from __future__ import annotations

from html import escape
import json
import zipfile
from pathlib import Path

from docx import Document as DocxDocument
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, ExportFile, ExportStatus, ExportType, Explanation, Report, ReportSection, Requirement
from app.services.estimate_expertise import ensure_estimate_expertise_workflow, serialize_workflow
from app.services.reports import build_report_explanations_payload
from app.services.report_types import STATE_EXPERTISE_ESTIMATE_COST_PP87_REPORT, requires_special_workflow
from app.services.storage import storage


def export_report_docx(db: Session, report: Report, created_by_id: str | None) -> ExportFile:
    if requires_special_workflow(report.report_type):
        return export_estimate_expertise_docx(db, report, created_by_id)

    file_name = f"{report.title}_report.docx".replace(" ", "_")
    path = Path(storage.create_export_path(report.organization_id, file_name))
    document = DocxDocument()
    document.add_heading(report.title, level=1)
    for section in db.scalars(select(ReportSection).where(ReportSection.report_id == report.id).order_by(ReportSection.order_number)):
        document.add_heading(section.title, level=2)
        document.add_paragraph(section.content)
    document.save(path)
    export = ExportFile(
        organization_id=report.organization_id,
        report_id=report.id,
        created_by_id=created_by_id,
        export_type=ExportType.docx,
        file_name=file_name,
        storage_path=str(path),
        status=ExportStatus.ready,
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


def export_matrix_xlsx(db: Session, report: Report, created_by_id: str | None) -> ExportFile:
    if requires_special_workflow(report.report_type):
        return export_estimate_expertise_matrix_xlsx(db, report, created_by_id)

    file_name = f"{report.title}_matrix.xlsx".replace(" ", "_")
    path = Path(storage.create_export_path(report.organization_id, file_name))
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Matrix"
    sheet.append(["Requirement ID", "Category", "Title", "Status", "Confidence", "Risk", "Applicability"])
    for requirement in db.scalars(select(Requirement).where(Requirement.report_id == report.id).order_by(Requirement.created_at)):
        sheet.append(
            [
                requirement.id,
                requirement.category,
                requirement.title,
                requirement.status.value,
                requirement.confidence_score,
                requirement.risk_level.value,
                requirement.applicability_status.value,
            ]
        )
    workbook.save(path)
    export = ExportFile(
        organization_id=report.organization_id,
        report_id=report.id,
        created_by_id=created_by_id,
        export_type=ExportType.matrix,
        file_name=file_name,
        storage_path=str(path),
        status=ExportStatus.ready,
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


def export_explanations_html(db: Session, report: Report, created_by_id: str | None) -> ExportFile:
    if requires_special_workflow(report.report_type):
        return export_estimate_expertise_xai_html(db, report, created_by_id)

    file_name = f"{report.title}_explanations.html".replace(" ", "_")
    path = Path(storage.create_export_path(report.organization_id, file_name))
    explanations_payload = build_report_explanations_payload(db, report)
    blocks: list[str] = []
    for item in explanations_payload:
        logic_lines = "".join(f"<li>{escape(str(line))}</li>" for line in item["logic"])
        recommended = (
            f"<p><strong>Рекомендация:</strong> {escape(str(item['recommended_action']))}</p>"
            if item["recommended_action"]
            else ""
        )
        blocks.append(
            f"""
            <section class="explanation-card">
              <h2>{escape(str(item['conclusion']))}</h2>
              <p>{escape(str(item['explanation_text']))}</p>
              <p><strong>Уверенность:</strong> {escape(str(item['confidence_score']))}</p>
              <p><strong>Риск:</strong> {escape(str(item['risk_level']))}</p>
              <ul>{logic_lines}</ul>
              {recommended}
            </section>
            """
        )
    html = f"""
    <!doctype html>
    <html lang="ru">
      <head>
        <meta charset="utf-8" />
        <title>XAI explanations - {escape(report.title)}</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 2rem; color: #1d2430; }}
          .explanation-card {{ border: 1px solid #d7dde4; border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 1rem; }}
          h1 {{ margin-bottom: 1.5rem; }}
          h2 {{ font-size: 1.1rem; margin: 0 0 0.75rem; }}
        </style>
      </head>
      <body>
        <h1>XAI-объяснения: {escape(report.title)}</h1>
        {''.join(blocks) if blocks else '<p>Объяснения пока не сформированы.</p>'}
      </body>
    </html>
    """
    path.write_text(html, encoding="utf-8")
    export = ExportFile(
        organization_id=report.organization_id,
        report_id=report.id,
        created_by_id=created_by_id,
        export_type=ExportType.explanations,
        file_name=file_name,
        storage_path=str(path),
        status=ExportStatus.ready,
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


def export_evidence_package(db: Session, report: Report, created_by_id: str | None) -> ExportFile:
    if requires_special_workflow(report.report_type):
        return export_estimate_expertise_package(db, report, created_by_id)

    docx_export = export_report_docx(db, report, created_by_id)
    matrix_export = export_matrix_xlsx(db, report, created_by_id)
    explanations_export = export_explanations_html(db, report, created_by_id)
    file_name = f"{report.title}_package.zip".replace(" ", "_")
    path = Path(storage.create_export_path(report.organization_id, file_name))

    explanations_payload = build_report_explanations_payload(db, report)

    explanations_path = path.with_suffix(".json")
    explanations_path.write_text(json.dumps(explanations_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with zipfile.ZipFile(path, "w") as archive:
        archive.write(docx_export.storage_path, arcname=Path(docx_export.storage_path).name)
        archive.write(matrix_export.storage_path, arcname=Path(matrix_export.storage_path).name)
        archive.write(explanations_export.storage_path, arcname=Path(explanations_export.storage_path).name)
        archive.write(explanations_path, arcname="explanations.json")

    export = ExportFile(
        organization_id=report.organization_id,
        report_id=report.id,
        created_by_id=created_by_id,
        export_type=ExportType.package,
        file_name=file_name,
        storage_path=str(path),
        status=ExportStatus.ready,
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


def _get_estimate_expertise_payload(db: Session, report: Report) -> dict:
    workflow = ensure_estimate_expertise_workflow(db, report)
    return serialize_workflow(db, workflow)


def _iter_estimate_expertise_findings(payload: dict) -> list[dict]:
    findings: list[dict] = []
    for stage in payload.get("stages", []):
        for finding in stage.get("findings", []):
            findings.append({**finding, "stage_title": stage.get("short_title") or stage.get("title") or finding.get("stage_title")})
    return findings


def _severity_label(value: str | None) -> str:
    return {
        "danger": "Блокер",
        "warning": "Требует проверки",
        "info": "Информационный сигнал",
    }.get(value or "", value or "")


def _decision_label(finding: dict) -> str:
    decision = finding.get("decision")
    if not decision:
        return ""
    label = decision.get("label") or decision.get("status") or ""
    replacement = decision.get("replacement_file_name")
    return f"{label} Замена: {replacement}" if replacement else str(label)


def _create_export_record(
    db: Session,
    report: Report,
    created_by_id: str | None,
    *,
    export_type: ExportType,
    file_name: str,
    path: Path,
) -> ExportFile:
    export = ExportFile(
        organization_id=report.organization_id,
        report_id=report.id,
        created_by_id=created_by_id,
        export_type=export_type,
        file_name=file_name,
        storage_path=str(path),
        status=ExportStatus.ready,
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


def export_estimate_expertise_docx(db: Session, report: Report, created_by_id: str | None) -> ExportFile:
    payload = _get_estimate_expertise_payload(db, report)
    findings = _iter_estimate_expertise_findings(payload)
    regulation_label = "ПП РФ N 87" if report.report_type == STATE_EXPERTISE_ESTIMATE_COST_PP87_REPORT else "ПП РФ N 145"
    file_name = f"{report.title}_state_expertise_summary.docx".replace(" ", "_")
    path = Path(storage.create_export_path(report.organization_id, file_name))

    document = DocxDocument()
    document.add_heading(report.title, level=1)
    document.add_paragraph(
        "Тип отчета: государственная экспертиза по проверке достоверности определения сметной стоимости "
        f"согласно {regulation_label}"
    )
    document.add_paragraph(f"Статус workflow: {payload.get('status')}")
    document.add_paragraph(f"Готовность: {payload.get('progress')}%")
    document.add_paragraph(f"Проверено файлов: {payload.get('checked_files')}/{payload.get('total_files')}")
    document.add_paragraph(f"Нерешенных замечаний: {payload.get('unresolved_findings')}")
    document.add_paragraph(f"Model version: {payload.get('model_version')}")
    document.add_paragraph(f"Rule version: {payload.get('rule_version')}")

    document.add_heading("Этапы проверки", level=2)
    for stage in payload.get("stages", []):
        document.add_paragraph(
            f"{stage.get('order_number')}. {stage.get('title')} — {stage.get('status')}, "
            f"{stage.get('progress')}%, findings: {stage.get('findings_count')}"
        )

    document.add_heading("Замечания и рекомендации", level=2)
    if not findings:
        document.add_paragraph("Замечания пока не сформированы.")
    for finding in findings:
        document.add_heading(str(finding.get("title")), level=3)
        document.add_paragraph(f"Этап: {finding.get('stage_title')}")
        document.add_paragraph(f"Документ: {finding.get('document_name')}")
        document.add_paragraph(f"Критичность: {_severity_label(finding.get('severity'))}")
        document.add_paragraph(f"Confidence: {finding.get('confidence_score')}")
        document.add_paragraph(f"Описание: {finding.get('description')}")
        document.add_paragraph(f"Нормативная привязка: {finding.get('normative_basis')}")
        document.add_paragraph(f"Источник: {finding.get('source_ref')}")
        document.add_paragraph(f"Рекомендация: {finding.get('recommendation')}")
        decision = _decision_label(finding)
        if decision:
            document.add_paragraph(f"Решение пользователя: {decision}")
        xai_steps = finding.get("xai_summary") or []
        if xai_steps:
            document.add_paragraph("XAI-цепочка:")
            for step in xai_steps:
                document.add_paragraph(str(step), style="List Bullet")

    document.add_paragraph(
        "Дисклеймер: автоматизированная проверка EvidenceXAI является предварительной и не заменяет государственную экспертизу."
    )
    document.save(path)
    return _create_export_record(db, report, created_by_id, export_type=ExportType.docx, file_name=file_name, path=path)


def export_estimate_expertise_matrix_xlsx(db: Session, report: Report, created_by_id: str | None) -> ExportFile:
    payload = _get_estimate_expertise_payload(db, report)
    file_name = f"{report.title}_state_expertise_findings.xlsx".replace(" ", "_")
    path = Path(storage.create_export_path(report.organization_id, file_name))
    workbook = Workbook()

    summary = workbook.active
    summary.title = "Summary"
    summary.append(["Report", report.title])
    summary.append(["Workflow status", payload.get("status")])
    summary.append(["Progress", payload.get("progress")])
    summary.append(["Checked files", payload.get("checked_files")])
    summary.append(["Total files", payload.get("total_files")])
    summary.append(["Unresolved findings", payload.get("unresolved_findings")])
    summary.append(["Model version", payload.get("model_version")])
    summary.append(["Rule version", payload.get("rule_version")])

    stages_sheet = workbook.create_sheet("Stages")
    stages_sheet.append(["Order", "Stage key", "Title", "Status", "Progress", "Checked files", "Total files", "Findings"])
    for stage in payload.get("stages", []):
        stages_sheet.append(
            [
                stage.get("order_number"),
                stage.get("stage_key"),
                stage.get("title"),
                stage.get("status"),
                stage.get("progress"),
                stage.get("checked_files"),
                stage.get("total_files"),
                stage.get("findings_count"),
            ]
        )

    findings_sheet = workbook.create_sheet("Findings")
    findings_sheet.append(
        [
            "Stage",
            "Document",
            "Title",
            "Severity",
            "Confidence",
            "Status",
            "Decision",
            "Normative basis",
            "Source",
            "Recommendation",
            "Description",
            "XAI summary",
        ]
    )
    for finding in _iter_estimate_expertise_findings(payload):
        findings_sheet.append(
            [
                finding.get("stage_title"),
                finding.get("document_name"),
                finding.get("title"),
                finding.get("severity"),
                finding.get("confidence_score"),
                finding.get("status"),
                _decision_label(finding),
                finding.get("normative_basis"),
                finding.get("source_ref"),
                finding.get("recommendation"),
                finding.get("description"),
                "\n".join(str(item) for item in finding.get("xai_summary") or []),
            ]
        )

    workbook.save(path)
    return _create_export_record(db, report, created_by_id, export_type=ExportType.matrix, file_name=file_name, path=path)


def export_estimate_expertise_xai_html(db: Session, report: Report, created_by_id: str | None) -> ExportFile:
    payload = _get_estimate_expertise_payload(db, report)
    findings = _iter_estimate_expertise_findings(payload)
    file_name = f"{report.title}_state_expertise_xai.html".replace(" ", "_")
    path = Path(storage.create_export_path(report.organization_id, file_name))

    cards: list[str] = []
    for finding in findings:
        steps = "".join(f"<li>{escape(str(step))}</li>" for step in finding.get("xai_summary") or [])
        decision = _decision_label(finding)
        cards.append(
            f"""
            <section class="card tone-{escape(str(finding.get('severity') or 'info'))}">
              <p class="stage">{escape(str(finding.get('stage_title') or ''))}</p>
              <h2>{escape(str(finding.get('title') or ''))}</h2>
              <p><strong>Документ:</strong> {escape(str(finding.get('document_name') or 'Пакет документов'))}</p>
              <p><strong>Описание:</strong> {escape(str(finding.get('description') or ''))}</p>
              <p><strong>Нормативная привязка:</strong> {escape(str(finding.get('normative_basis') or ''))}</p>
              <p><strong>Источник:</strong> {escape(str(finding.get('source_ref') or ''))}</p>
              <p><strong>Confidence:</strong> {escape(str(finding.get('confidence_score') or ''))}</p>
              <p><strong>Рекомендация:</strong> {escape(str(finding.get('recommendation') or ''))}</p>
              {f'<p><strong>Решение пользователя:</strong> {escape(decision)}</p>' if decision else ''}
              <h3>XAI-цепочка</h3>
              <ol>{steps}</ol>
            </section>
            """
        )

    html = f"""
    <!doctype html>
    <html lang="ru">
      <head>
        <meta charset="utf-8" />
        <title>EvidenceXAI XAI — {escape(report.title)}</title>
        <style>
          body {{ font-family: Manrope, Arial, sans-serif; margin: 0; background: #f6f1e8; color: #172033; }}
          header {{ padding: 32px 42px; background: linear-gradient(135deg, #151b2d, #4338ca); color: white; }}
          main {{ padding: 28px 42px; }}
          .meta {{ display: grid; grid-template-columns: repeat(4, minmax(140px, 1fr)); gap: 12px; margin: 20px 0; }}
          .meta div, .card {{ background: white; border: 1px solid #e6dccb; border-radius: 18px; padding: 16px; box-shadow: 0 14px 38px rgba(31, 41, 55, .08); }}
          .card {{ margin: 16px 0; }}
          .stage {{ color: #635bff; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }}
          .tone-danger {{ border-left: 6px solid #dc2626; }}
          .tone-warning {{ border-left: 6px solid #d97706; }}
          .tone-info {{ border-left: 6px solid #0891b2; }}
          li {{ margin: 8px 0; }}
        </style>
      </head>
      <body>
        <header>
          <p>EvidenceXAI / EX.AI</p>
          <h1>XAI-объяснения спецпроверки</h1>
          <p>{escape(report.title)}</p>
        </header>
        <main>
          <section class="meta">
            <div><strong>Статус</strong><br />{escape(str(payload.get('status')))}</div>
            <div><strong>Готовность</strong><br />{escape(str(payload.get('progress')))}%</div>
            <div><strong>Файлы</strong><br />{escape(str(payload.get('checked_files')))} / {escape(str(payload.get('total_files')))}</div>
            <div><strong>Нерешенные findings</strong><br />{escape(str(payload.get('unresolved_findings')))}</div>
          </section>
          {''.join(cards) if cards else '<p>Findings пока не сформированы.</p>'}
        </main>
      </body>
    </html>
    """
    path.write_text(html, encoding="utf-8")
    return _create_export_record(db, report, created_by_id, export_type=ExportType.explanations, file_name=file_name, path=path)


def export_estimate_expertise_package(db: Session, report: Report, created_by_id: str | None) -> ExportFile:
    payload = _get_estimate_expertise_payload(db, report)
    docx_export = export_estimate_expertise_docx(db, report, created_by_id)
    matrix_export = export_estimate_expertise_matrix_xlsx(db, report, created_by_id)
    xai_export = export_estimate_expertise_xai_html(db, report, created_by_id)
    file_name = f"{report.title}_state_expertise_package.zip".replace(" ", "_")
    path = Path(storage.create_export_path(report.organization_id, file_name))
    workflow_json_path = path.with_suffix(".workflow.json")
    workflow_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    selected_documents = []
    if report.selected_document_ids:
        selected_documents = list(
            db.scalars(
                select(Document).where(
                    Document.organization_id == report.organization_id,
                    Document.id.in_(report.selected_document_ids),
                )
            )
        )

    with zipfile.ZipFile(path, "w") as archive:
        archive.write(docx_export.storage_path, arcname="summary.docx")
        archive.write(matrix_export.storage_path, arcname="findings.xlsx")
        archive.write(xai_export.storage_path, arcname="xai.html")
        archive.write(workflow_json_path, arcname="workflow.json")
        for document in selected_documents:
            source = Path(document.storage_path)
            if source.exists():
                archive.write(source, arcname=f"source_documents/{document.relative_path or document.file_name}")

    return _create_export_record(db, report, created_by_id, export_type=ExportType.package, file_name=file_name, path=path)
