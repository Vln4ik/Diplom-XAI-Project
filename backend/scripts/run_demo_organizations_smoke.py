from __future__ import annotations

import json
import sys
from pathlib import Path

def resolve_repo_root() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2],
        Path.cwd(),
    ]
    for candidate in candidates:
        if (candidate / "samples").exists() and (candidate / "backend").exists():
            return candidate
    raise RuntimeError("Could not resolve repository root.")


ROOT = resolve_repo_root()
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, func, select

from app.db.session import get_session_factory
from app.models import Explanation, Organization, Report, ReportSection, Requirement, Risk
from app.services.reports import analyze_report, generate_report_sections

SMOKE_REPORT_TITLE = "Demo Smoke Report"


def main() -> None:
    session_factory = get_session_factory()
    results: list[dict[str, object]] = []

    with session_factory() as session:
        organizations = [
            organization
            for organization in session.scalars(select(Organization).order_by(Organization.name))
            if bool((organization.profile_json or {}).get("demo_seed_pack"))
        ]
        if not organizations:
            raise SystemExit("No demo organizations found in the current database.")

        for organization in organizations:
            existing_reports = list(
                session.scalars(
                    select(Report).where(
                        Report.organization_id == organization.id,
                        Report.title == SMOKE_REPORT_TITLE,
                    )
                )
            )
            for report in existing_reports:
                requirement_ids = list(session.scalars(select(Requirement.id).where(Requirement.report_id == report.id)))
                if requirement_ids:
                    session.execute(delete(Explanation).where(Explanation.requirement_id.in_(requirement_ids)))
                    session.execute(delete(Risk).where(Risk.report_id == report.id))
                    session.execute(delete(Requirement).where(Requirement.report_id == report.id))
                session.delete(report)
            session.commit()

            selected_document_ids = [document.id for document in organization.documents]
            report = Report(
                organization_id=organization.id,
                responsible_user_id=None,
                title=SMOKE_REPORT_TITLE,
                report_type="readiness_report",
                selected_document_ids=selected_document_ids,
            )
            session.add(report)
            session.commit()
            session.refresh(report)

            analyzed = analyze_report(session, report)
            generated = generate_report_sections(session, analyzed)

            requirements_count = session.scalar(
                select(func.count()).select_from(Requirement).where(Requirement.report_id == generated.id)
            )
            risks_count = session.scalar(
                select(func.count()).select_from(Risk).where(Risk.report_id == generated.id)
            )
            sections_count = session.scalar(
                select(func.count()).select_from(ReportSection).where(ReportSection.report_id == generated.id)
            )
            results.append(
                {
                    "organization": organization.name,
                    "report_id": generated.id,
                    "documents": len(selected_document_ids),
                    "requirements": requirements_count or 0,
                    "risks": risks_count or 0,
                    "sections": sections_count,
                    "readiness_percent": generated.readiness_percent,
                }
            )

    print(json.dumps({"organizations_processed": len(results), "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
