from __future__ import annotations

import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.models import (
    Document,
    DocumentCategory,
    DocumentStatus,
    Organization,
    OrganizationType,
    Report,
    ReportStatus,
    Requirement,
    RequirementStatus,
    Risk,
    RiskLevel,
    RiskStatus,
)
from app.services.auth import create_user
from app.services.documents import describe_processing_error, recover_stale_processing_documents
from app.services.estimate_expertise import ensure_estimate_expertise_workflow, recalculate_workflow_metrics


def test_describe_processing_error_returns_user_facing_reason():
    assert "Формат файла .dwg пока не поддерживается" in describe_processing_error(ValueError("Unsupported document format: .dwg"))
    assert "превысила лимит времени" in describe_processing_error(TimeoutError("task time limit exceeded"))
    assert "Исходный файл не найден" in describe_processing_error(FileNotFoundError("missing.pdf"))


def _auth_headers(test_client, email: str, password: str) -> dict[str, str]:
    response = test_client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    access_token = response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def _workflow_findings(workflow: dict) -> list[dict]:
    return [finding for stage in workflow["stages"] for finding in stage["findings"]]


def _blocking_findings(workflow: dict, stage_key: str | None = None) -> list[dict]:
    findings = _workflow_findings(workflow)
    if stage_key is not None:
        findings = [finding for finding in findings if finding["stage_key"] == stage_key]
    return [
        finding
        for finding in findings
        if finding["severity"] in {"warning", "danger"} and not finding.get("decision")
    ]


def _advance_workflow_until_stage(test_client, headers: dict[str, str], workflow: dict, target_stage_key: str) -> dict:
    latest = workflow
    for _ in range(30):
        target_stage = next(stage for stage in latest["stages"] if stage["stage_key"] == target_stage_key)
        if target_stage["findings"] or target_stage["status"] in {"blocked", "completed", "running"}:
            return latest
        blockers = _blocking_findings(latest)
        assert blockers, f"Workflow did not reach {target_stage_key}; current={latest.get('current_stage_key')}"
        for finding in blockers:
            response = test_client.post(
                f"/api/estimate-expertise/findings/{finding['id']}/skip",
                headers=headers,
                json={},
            )
            assert response.status_code == 200
            latest = response.json()
    raise AssertionError(f"Workflow did not reach {target_stage_key}")


def test_dashboard_readiness_uses_documents_reports_requirements_and_unresolved_risks(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="dashboard-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "dashboard-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Dashboard Progress Company", "organization_type": "educational"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    empty_dashboard_response = test_client.get(f"/api/organizations/{organization_id}/dashboard", headers=headers)
    assert empty_dashboard_response.status_code == 200
    assert empty_dashboard_response.json()["readiness_percent"] == 0

    with session_factory() as session:
        processed_document = Document(
            organization_id=organization_id,
            file_name="processed.txt",
            original_file_name="processed.txt",
            file_type="text/plain",
            file_size=100,
            category=DocumentCategory.evidence,
            storage_path="processed.txt",
            status=DocumentStatus.processed,
        )
        queued_document = Document(
            organization_id=organization_id,
            file_name="queued.txt",
            original_file_name="queued.txt",
            file_type="text/plain",
            file_size=100,
            category=DocumentCategory.evidence,
            storage_path="queued.txt",
            status=DocumentStatus.queued,
        )
        report = Report(
            organization_id=organization_id,
            title="Dashboard report",
            regulator="rosobrnadzor",
            report_type="rosobrnadzor_education",
            status=ReportStatus.requires_review,
            readiness_percent=80,
        )
        session.add_all([processed_document, queued_document, report])
        session.flush()
        requirement = Requirement(
            organization_id=organization_id,
            report_id=report.id,
            category="Документы",
            title="Подтверждение",
            text="Требование подтверждено evidence.",
            status=RequirementStatus.confirmed,
            confidence_score=0.9,
            required_data=["evidence"],
            found_data=["processed.txt"],
        )
        session.add(requirement)
        session.flush()
        risk = Risk(
            organization_id=organization_id,
            report_id=report.id,
            requirement_id=requirement.id,
            title="Высокий риск",
            description="Есть открытый риск.",
            risk_level=RiskLevel.high,
            status=RiskStatus.new,
        )
        session.add(risk)
        session.commit()

    dashboard_response = test_client.get(f"/api/organizations/{organization_id}/dashboard", headers=headers)
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["processed_documents"] == 1
    assert dashboard["active_reports"] == 1
    assert dashboard["total_requirements"] == 1
    assert dashboard["high_risks"] == 1
    assert dashboard["readiness_percent"] > empty_dashboard_response.json()["readiness_percent"]

    with session_factory() as session:
        document = session.scalar(
            select(Document).where(Document.organization_id == organization_id, Document.file_name == "queued.txt")
        )
        document.status = DocumentStatus.processed
        risk = session.scalar(select(Risk).where(Risk.organization_id == organization_id))
        risk.status = RiskStatus.resolved
        session.commit()

    improved_dashboard_response = test_client.get(f"/api/organizations/{organization_id}/dashboard", headers=headers)
    assert improved_dashboard_response.status_code == 200
    improved_dashboard = improved_dashboard_response.json()
    assert improved_dashboard["processed_documents"] == 2
    assert improved_dashboard["high_risks"] == 0
    assert improved_dashboard["readiness_percent"] > dashboard["readiness_percent"]


def test_folder_upload_preserves_relative_paths(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="folder-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "folder-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Folder Upload College", "organization_type": "educational"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        files=[
            ("category", (None, "evidence")),
            ("relative_paths", (None, "audit-pack/license/license.txt")),
            ("relative_paths", (None, "audit-pack/staff/staff.txt")),
            ("files", ("license.txt", b"license evidence", "text/plain")),
            ("files", ("staff.txt", b"staff evidence", "text/plain")),
        ],
    )
    assert upload_response.status_code == 201
    payload = upload_response.json()
    assert [item["relative_path"] for item in payload] == [
        "audit-pack/license/license.txt",
        "audit-pack/staff/staff.txt",
    ]

    documents_response = test_client.get(f"/api/organizations/{organization_id}/documents", headers=headers)
    assert documents_response.status_code == 200
    listed_paths = {item["relative_path"] for item in documents_response.json()}
    assert "audit-pack/license/license.txt" in listed_paths
    assert "audit-pack/staff/staff.txt" in listed_paths


def test_upload_batch_total_limit_rolls_back_partial_uploads(client, monkeypatch):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="upload-limit-owner@example.com", password="ChangeMe123!")

    from app.core.config import get_settings

    monkeypatch.setenv("XAI_APP_UPLOAD_MAX_TOTAL_BYTES", "10")
    get_settings.cache_clear()

    headers = _auth_headers(test_client, "upload-limit-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Upload Limit Company", "organization_type": "educational"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": "evidence"},
        files=[
            ("files", ("small-a.txt", b"12345", "text/plain")),
            ("files", ("small-b.txt", b"123456", "text/plain")),
        ],
    )
    assert upload_response.status_code == 413

    documents_response = test_client.get(f"/api/organizations/{organization_id}/documents", headers=headers)
    assert documents_response.status_code == 200
    assert documents_response.json() == []
    get_settings.cache_clear()


def test_document_process_endpoint_is_idempotent_for_active_documents(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="idempotent-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "idempotent-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Idempotent Queue Company", "organization_type": "educational"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": "evidence"},
        files={"files": ("active.txt", "active document".encode("utf-8"), "text/plain")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()[0]["id"]

    with session_factory() as session:
        document = session.get(Document, document_id)
        document.status = DocumentStatus.queued
        session.add(document)
        session.commit()

    process_response = test_client.post(f"/api/documents/{document_id}/process", headers=headers)
    assert process_response.status_code == 200
    payload = process_response.json()
    assert payload["status"] == "queued"
    assert payload["task_id"] is None


def test_recover_stale_processing_documents_marks_timed_out_files_failed(client):
    _test_client, session_factory = client
    with session_factory() as session:
        user = create_user(session, full_name="Stale Owner", email="stale-owner@example.com", password="ChangeMe123!")
        organization_response = Organization(name="Stale Processing Company", organization_type=OrganizationType.educational)
        session.add(organization_response)
        session.commit()
        stale_document = Document(
            organization_id=organization_response.id,
            uploaded_by_id=user.id,
            file_name="stale.pdf",
            original_file_name="stale.pdf",
            file_type="application/pdf",
            file_size=100,
            category=DocumentCategory.evidence,
            storage_path="stale.pdf",
            status=DocumentStatus.processing,
            updated_at=datetime.now(UTC) - timedelta(minutes=20),
        )
        active_document = Document(
            organization_id=organization_response.id,
            uploaded_by_id=user.id,
            file_name="active.pdf",
            original_file_name="active.pdf",
            file_type="application/pdf",
            file_size=100,
            category=DocumentCategory.evidence,
            storage_path="active.pdf",
            status=DocumentStatus.processing,
            updated_at=datetime.now(UTC),
        )
        session.add_all([stale_document, active_document])
        session.commit()

        recovered_count = recover_stale_processing_documents(
            session,
            organization_id=organization_response.id,
            stale_after_minutes=8,
        )

        assert recovered_count == 1
        session.refresh(stale_document)
        session.refresh(active_document)
        assert stale_document.status == DocumentStatus.failed
        assert "оставался в статусе" in (stale_document.processing_error or "")
        assert active_document.status == DocumentStatus.processing

def test_state_expertise_estimate_cost_report_type_is_special_workflow(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="estimate-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "estimate-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Estimate Expertise Company", "organization_type": "other"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    report_response = test_client.post(
        f"/api/organizations/{organization_id}/reports",
        headers=headers,
        json={
            "title": "Отчет государственной экспертизы по сметной стоимости",
            "report_type": "state_expertise_estimate_cost_verification",
            "selected_document_ids": [],
        },
    )
    assert report_response.status_code == 201
    payload = report_response.json()
    assert payload["report_type"] == "state_expertise_estimate_cost_verification"

    analyze_response = test_client.post(f"/api/reports/{payload['id']}/analyze", headers=headers)
    assert analyze_response.status_code == 409
    assert "specialized state expertise workflow" in analyze_response.json()["detail"]

    generate_response = test_client.post(f"/api/reports/{payload['id']}/generate", headers=headers)
    assert generate_response.status_code == 409
    assert "specialized state expertise workflow" in generate_response.json()["detail"]

    invalid_response = test_client.post(
        f"/api/organizations/{organization_id}/reports",
        headers=headers,
        json={"title": "Invalid", "report_type": "unknown_report_type"},
    )
    assert invalid_response.status_code == 422


def test_report_can_be_deleted_from_api(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="delete-report-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "delete-report-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Delete Report Company", "organization_type": "educational"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    report_response = test_client.post(
        f"/api/organizations/{organization_id}/reports",
        headers=headers,
        json={"title": "Удаляемый отчет", "report_type": "readiness_report"},
    )
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]

    delete_response = test_client.delete(f"/api/reports/{report_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == report_id

    get_response = test_client.get(f"/api/reports/{report_id}", headers=headers)
    assert get_response.status_code == 404
    list_response = test_client.get(f"/api/organizations/{organization_id}/reports", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_report_rejects_foreign_selected_document_ids(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="tenant-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "tenant-owner@example.com", "ChangeMe123!")
    first_org_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Tenant A", "organization_type": "educational"},
    )
    second_org_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Tenant B", "organization_type": "educational"},
    )
    assert first_org_response.status_code == 201
    assert second_org_response.status_code == 201
    first_org_id = first_org_response.json()["id"]
    second_org_id = second_org_response.json()["id"]

    upload_response = test_client.post(
        f"/api/organizations/{first_org_id}/documents",
        headers=headers,
        data={"category": "evidence"},
        files={"files": ("tenant-a.txt", b"tenant a evidence", "text/plain")},
    )
    assert upload_response.status_code == 201
    foreign_document_id = upload_response.json()[0]["id"]

    create_response = test_client.post(
        f"/api/organizations/{second_org_id}/reports",
        headers=headers,
        json={
            "title": "Cross tenant report",
            "report_type": "readiness_report",
            "selected_document_ids": [foreign_document_id],
        },
    )
    assert create_response.status_code == 403
    assert "Selected documents must belong" in create_response.json()["detail"]


def test_state_expertise_workflow_persists_findings_and_user_decisions(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="workflow-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "workflow-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Estimate Workflow Company", "organization_type": "other"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": "evidence"},
        files={"files": ("ЛСР_работы.txt", "Локальный сметный расчет по работам".encode("utf-8"), "text/plain")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()[0]["id"]

    process_response = test_client.post(f"/api/documents/{document_id}/process", headers=headers)
    assert process_response.status_code == 200

    report_response = test_client.post(
        f"/api/organizations/{organization_id}/reports",
        headers=headers,
        json={
            "title": "Спецотчет по сметной стоимости",
            "report_type": "state_expertise_estimate_cost_verification",
            "selected_document_ids": [document_id],
        },
    )
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]

    start_response = test_client.post(f"/api/reports/{report_id}/estimate-expertise/start", headers=headers)
    assert start_response.status_code == 200
    workflow = start_response.json()
    assert workflow["report_id"] == report_id
    assert workflow["total_files"] == 1
    findings = [finding for stage in workflow["stages"] for finding in stage["findings"]]
    assert any("ПП РФ N 145" in finding["normative_basis"] for finding in findings)
    unresolved_before = workflow["unresolved_findings"]
    assert unresolved_before > 0

    finding_to_approve = next(finding for finding in findings if finding["severity"] in {"warning", "danger"})
    approve_response = test_client.post(
        f"/api/estimate-expertise/findings/{finding_to_approve['id']}/approve",
        headers=headers,
        json={},
    )
    assert approve_response.status_code == 200
    approved_workflow = approve_response.json()
    assert approved_workflow["unresolved_findings"] == unresolved_before - 1
    approved_finding = next(
        finding
        for stage in approved_workflow["stages"]
        for finding in stage["findings"]
        if finding["id"] == finding_to_approve["id"]
    )
    assert approved_finding["decision"]["status"] == "approved"

    replacement_target = next(
        finding
        for stage in approved_workflow["stages"]
        for finding in stage["findings"]
        if finding["severity"] in {"warning", "danger"} and finding["id"] != finding_to_approve["id"]
    )
    replacement_response = test_client.post(
        f"/api/estimate-expertise/findings/{replacement_target['id']}/replacement",
        headers=headers,
        files={"file": ("ССР.txt", "Сводный сметный расчет".encode("utf-8"), "text/plain")},
    )
    assert replacement_response.status_code == 200
    replacement_workflow = replacement_response.json()
    replacement_finding = next(
        finding
        for stage in replacement_workflow["stages"]
        for finding in stage["findings"]
        if finding["id"] == replacement_target["id"]
    )
    assert replacement_finding["decision"]["status"] == "replacement_resolved"
    assert replacement_finding["decision"]["replacement_file_name"] == "ССР.txt"
    assert replacement_finding["decision"]["replacement_progress"] == 100

    state_response = test_client.get(f"/api/reports/{report_id}/estimate-expertise/state", headers=headers)
    assert state_response.status_code == 200
    persisted_findings = [finding for stage in state_response.json()["stages"] for finding in stage["findings"]]
    assert any(finding["decision"] and finding["decision"]["status"] == "approved" for finding in persisted_findings)


    assert any(finding["decision"] and finding["decision"]["status"] == "replacement_resolved" for finding in persisted_findings)

    export_docx = test_client.post(f"/api/reports/{report_id}/export/docx", headers=headers)
    assert export_docx.status_code == 200
    assert export_docx.json()["file_name"].endswith("_state_expertise_summary.docx")
    assert Path(export_docx.json()["storage_path"]).exists()

    export_matrix = test_client.post(f"/api/reports/{report_id}/export/matrix", headers=headers)
    assert export_matrix.status_code == 200
    assert export_matrix.json()["file_name"].endswith("_state_expertise_findings.xlsx")
    assert Path(export_matrix.json()["storage_path"]).exists()

    export_xai = test_client.post(f"/api/reports/{report_id}/export/explanations", headers=headers)
    assert export_xai.status_code == 200
    xai_path = Path(export_xai.json()["storage_path"])
    assert xai_path.exists()
    assert "XAI-объяснения спецпроверки" in xai_path.read_text(encoding="utf-8")

    export_package = test_client.post(f"/api/reports/{report_id}/export/package", headers=headers)
    assert export_package.status_code == 200
    package_path = Path(export_package.json()["storage_path"])
    assert package_path.exists()
    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
    assert {"summary.docx", "findings.xlsx", "xai.html", "workflow.json"}.issubset(names)
    assert any(name.startswith("source_documents/") for name in names)

    audit_response = test_client.get(f"/api/organizations/{organization_id}/audit-logs", headers=headers)
    assert audit_response.status_code == 200
    audit_actions = {item["action"] for item in audit_response.json()}
    assert "estimate_expertise_finding_approved" in audit_actions
    assert "estimate_expertise_replacement_started" in audit_actions
    assert "estimate_expertise_finding_replacement_resolved" in audit_actions
    replacement_audit = next(item for item in audit_response.json() if item["action"] == "estimate_expertise_replacement_started")
    assert replacement_audit["details"]["xai_summary"]


def test_state_expertise_queued_workflow_is_not_marked_completed_by_state_recalculation(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="queued-workflow-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "queued-workflow-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Queued Workflow Company", "organization_type": "other"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": "evidence"},
        files={"files": ("ЛСР_работы.txt", "Локальный сметный расчет по работам".encode("utf-8"), "text/plain")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()[0]["id"]
    assert test_client.post(f"/api/documents/{document_id}/process", headers=headers).status_code == 200

    report_response = test_client.post(
        f"/api/organizations/{organization_id}/reports",
        headers=headers,
        json={
            "title": "Очередь госэкспертизы",
            "report_type": "state_expertise_estimate_cost_verification",
            "selected_document_ids": [document_id],
        },
    )
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]

    with session_factory() as session:
        report = session.get(Report, report_id)
        workflow = ensure_estimate_expertise_workflow(session, report)
        recalculate_workflow_metrics(session, workflow)
        session.commit()
        session.refresh(workflow)

        assert workflow.status == "queued"
        assert workflow.progress == 0
        stages = sorted(workflow.stages, key=lambda item: item.order_number)
        assert all(stage.status == "pending" for stage in stages)
        assert all(stage.progress == 0 for stage in stages)


def test_state_expertise_workflow_uses_extracted_text_for_mismatch_and_quality_findings(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="text-rules-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "text-rules-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Text Rules Estimate Company", "organization_type": "other"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    mismatched_text = """
    Коммерческое предложение на поставку оборудования.
    Сметнная стоимоть оборудования приведена без подписи ответственного лица.
    """.strip()
    upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": "evidence"},
        files={"files": ("ЛСР_оборудование.txt", mismatched_text.encode("utf-8"), "text/plain")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()[0]["id"]

    process_response = test_client.post(f"/api/documents/{document_id}/process", headers=headers)
    assert process_response.status_code == 200

    report_response = test_client.post(
        f"/api/organizations/{organization_id}/reports",
        headers=headers,
        json={
            "title": "Спецотчет с расхождением имени и содержания",
            "report_type": "state_expertise_estimate_cost_verification",
            "selected_document_ids": [document_id],
        },
    )
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]

    start_response = test_client.post(f"/api/reports/{report_id}/estimate-expertise/start", headers=headers)
    assert start_response.status_code == 200
    workflow = start_response.json()
    findings = _workflow_findings(workflow)

    mismatch_finding = next(finding for finding in findings if finding["title"] == "Название файла не совпадает с извлеченным содержанием")
    assert mismatch_finding["severity"] == "danger"
    assert "Локальные сметные расчеты" in mismatch_finding["description"]
    assert "Обоснования стоимости" in mismatch_finding["description"]
    assert any("Пересечения" in step for step in mismatch_finding["xai_summary"])

    workflow = _advance_workflow_until_stage(test_client, headers, workflow, "quality_spell_signature")
    quality_findings = _workflow_findings(workflow)

    typo_finding = next(finding for finding in quality_findings if finding["title"] == "Найдены подозрительные орфографические ошибки")
    assert typo_finding["severity"] == "warning"
    assert "сметнная" in typo_finding["description"]
    assert "стоимоть" in typo_finding["description"]

    signature_finding = next(finding for finding in quality_findings if finding["title"] == "Не найдены текстовые признаки подписи или печати")
    assert signature_finding["severity"] == "info"
    assert "layout-aware vision" in " ".join(signature_finding["xai_summary"])

    replacement_response = test_client.post(
        f"/api/estimate-expertise/findings/{mismatch_finding['id']}/replacement",
        headers=headers,
        files={
            "file": (
                "ЛСР_замена.txt",
                "Коммерческое предложение на поставку оборудования без подписи.".encode("utf-8"),
                "text/plain",
            )
        },
    )
    assert replacement_response.status_code == 200
    replacement_findings = [finding for stage in replacement_response.json()["stages"] for finding in stage["findings"]]
    replacement_recheck_finding = next(
        finding for finding in replacement_findings if finding["title"].startswith("После замены: Название файла не совпадает")
    )
    assert replacement_recheck_finding["severity"] == "danger"
    assert "backend re-check replacement-файла" in " ".join(replacement_recheck_finding["xai_summary"])


def test_state_expertise_filename_classifier_can_use_llm_provider(client, monkeypatch):
    test_client, session_factory = client

    class FakeLLMProvider:
        @property
        def provider_name(self) -> str:
            return "fake-llm"

        def complete(self, prompt: str, *, system: str = "", max_tokens: int = 256) -> str:
            return '{"label": "price_justification", "confidence": 0.91, "reason": "Текст содержит коммерческое предложение."}'

    from app.services import estimate_expertise

    monkeypatch.setattr(estimate_expertise, "get_llm_provider", lambda: FakeLLMProvider())

    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="llm-classifier-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "llm-classifier-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "LLM Classifier Estimate Company", "organization_type": "other"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": "evidence"},
        files={
            "files": (
                "ЛСР_оборудование.txt",
                "Коммерческое предложение на поставку оборудования. Стоимость оборудования указана поставщиком.".encode(
                    "utf-8"
                ),
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()[0]["id"]

    process_response = test_client.post(f"/api/documents/{document_id}/process", headers=headers)
    assert process_response.status_code == 200

    report_response = test_client.post(
        f"/api/organizations/{organization_id}/reports",
        headers=headers,
        json={
            "title": "Спецотчет с LLM-классификатором",
            "report_type": "state_expertise_estimate_cost_verification",
            "selected_document_ids": [document_id],
        },
    )
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]

    start_response = test_client.post(f"/api/reports/{report_id}/estimate-expertise/start", headers=headers)
    assert start_response.status_code == 200
    workflow = _advance_workflow_until_stage(test_client, headers, start_response.json(), "quality_spell_signature")
    findings = _workflow_findings(workflow)
    mismatch_finding = next(finding for finding in findings if finding["title"] == "Название файла не совпадает с извлеченным содержанием")

    xai_text = " ".join(mismatch_finding["xai_summary"])
    assert "LLM-классификатор" in xai_text
    assert "price_justification" in xai_text
    assert "Текст содержит коммерческое предложение" in xai_text


def test_state_expertise_completeness_pack_marks_mandatory_and_conditional_groups(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="completeness-pack-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "completeness-pack-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Completeness Pack Estimate Company", "organization_type": "other"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": "evidence"},
        files=[
            (
                "files",
                (
                    "Заявление.txt",
                    "Заявление о проведении государственной экспертизы".encode("utf-8"),
                    "text/plain",
                ),
            ),
            (
                "files",
                (
                    "Проектная_документация.txt",
                    "Проектная документация объекта капитального строительства".encode("utf-8"),
                    "text/plain",
                ),
            ),
        ],
    )
    assert upload_response.status_code == 201
    document_ids = [item["id"] for item in upload_response.json()]
    for document_id in document_ids:
        process_response = test_client.post(f"/api/documents/{document_id}/process", headers=headers)
        assert process_response.status_code == 200

    report_response = test_client.post(
        f"/api/organizations/{organization_id}/reports",
        headers=headers,
        json={
            "title": "Спецотчет с проверкой комплектности",
            "report_type": "state_expertise_estimate_cost_verification",
            "selected_document_ids": document_ids,
        },
    )
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]

    start_response = test_client.post(f"/api/reports/{report_id}/estimate-expertise/start", headers=headers)
    assert start_response.status_code == 200
    findings = [finding for stage in start_response.json()["stages"] for finding in stage["findings"]]
    completeness_findings = [finding for finding in findings if finding["stage_key"] == "completeness"]

    assert all("Заявление о проведении" not in finding["title"] for finding in completeness_findings)
    assert all("Проектная документация" not in finding["title"] for finding in completeness_findings)
    assert any("ПП РФ N 145" in finding["normative_basis"] for finding in completeness_findings)
    assert any("обязательная группа базового профиля" in " ".join(finding["xai_summary"]) for finding in completeness_findings)
    assert any(finding["severity"] == "info" and "условная группа" in " ".join(finding["xai_summary"]) for finding in completeness_findings)


def test_state_expertise_pp87_report_uses_pp87_completeness_rules(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="pp87-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "pp87-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "PP87 Estimate Company", "organization_type": "other"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": "evidence"},
        files=[
            (
                "files",
                (
                    "Пояснительная_записка.txt",
                    "Пояснительная записка. Исходные данные и технико экономические показатели.".encode("utf-8"),
                    "text/plain",
                ),
            ),
            (
                "files",
                (
                    "Смета_на_строительство.txt",
                    "Смета на строительство. Сводный сметный расчет и локальный сметный расчет.".encode("utf-8"),
                    "text/plain",
                ),
            ),
        ],
    )
    assert upload_response.status_code == 201
    document_ids = [item["id"] for item in upload_response.json()]
    for document_id in document_ids:
        process_response = test_client.post(f"/api/documents/{document_id}/process", headers=headers)
        assert process_response.status_code == 200

    report_response = test_client.post(
        f"/api/organizations/{organization_id}/reports",
        headers=headers,
        json={
            "title": "Спецотчет по ПП 87",
            "report_type": "state_expertise_estimate_cost_verification_pp87",
            "selected_document_ids": document_ids,
        },
    )
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]

    start_response = test_client.post(f"/api/reports/{report_id}/estimate-expertise/start", headers=headers)
    assert start_response.status_code == 200
    payload = _advance_workflow_until_stage(test_client, headers, start_response.json(), "section_content")
    stage_keys = [stage["stage_key"] for stage in payload["stages"]]
    findings = [finding for stage in payload["stages"] for finding in stage["findings"]]
    completeness_findings = [finding for finding in findings if finding["stage_key"] == "completeness"]
    section_content_findings = [finding for finding in findings if finding["stage_key"] == "section_content"]

    assert payload["rule_version"] == "estimate-cost-pp87-rules-pack-v3"
    assert "completeness" not in stage_keys
    assert "section_content" in stage_keys
    assert completeness_findings == []
    assert section_content_findings
    assert any("Содержание раздела требует проверки по ПП 87" in finding["title"] for finding in section_content_findings)
    assert any("ПП РФ N 87" in finding["normative_basis"] for finding in findings)
    assert all("ПП РФ N 145" not in finding["normative_basis"] for finding in findings)


def test_state_expertise_quality_stage_flags_scan_like_low_text_density(client):
    test_client, session_factory = client
    with session_factory() as session:
        user = create_user(session, full_name="Org Admin", email="quality-stage-owner@example.com", password="ChangeMe123!")
        user_id = user.id

    headers = _auth_headers(test_client, "quality-stage-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Quality Stage Estimate Company", "organization_type": "other"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    with session_factory() as session:
        document = Document(
            organization_id=organization_id,
            uploaded_by_id=user_id,
            file_name="Скан_подписного_листа.pdf",
            original_file_name="Скан_подписного_листа.pdf",
            relative_path="estimate-pack/Скан_подписного_листа.pdf",
            file_type="application/pdf",
            file_size=256,
            category=DocumentCategory.evidence,
            storage_path="/tmp/scan.pdf",
            status=DocumentStatus.processed,
            extracted_text="Подпись",
            page_count=2,
            tags=[],
        )
        session.add(document)
        session.commit()
        document_id = document.id

    report_response = test_client.post(
        f"/api/organizations/{organization_id}/reports",
        headers=headers,
        json={
            "title": "Спецотчет с визуальным PDF",
            "report_type": "state_expertise_estimate_cost_verification",
            "selected_document_ids": [document_id],
        },
    )
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]

    start_response = test_client.post(f"/api/reports/{report_id}/estimate-expertise/start", headers=headers)
    assert start_response.status_code == 200
    workflow = _advance_workflow_until_stage(test_client, headers, start_response.json(), "quality_spell_signature")
    findings = _workflow_findings(workflow)

    density_finding = next(finding for finding in findings if finding["title"] == "Низкая плотность извлеченного текста")
    assert density_finding["severity"] == "warning"
    assert "Плотность текста" in " ".join(density_finding["xai_summary"])

    signature_hint = next(finding for finding in findings if finding["title"] == "Текстовые признаки подписи или печати найдены")
    assert signature_hint["severity"] == "info"
    assert "vision detector" in " ".join(signature_hint["xai_summary"])


def test_document_to_report_pipeline(client, tmp_path):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "owner@example.com", "ChangeMe123!")

    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Test College", "organization_type": "educational"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    approver_response = test_client.post(
        f"/api/organizations/{organization_id}/members",
        headers=headers,
        json={
            "full_name": "Approver User",
            "email": "approver@example.com",
            "password": "ChangeMe123!",
            "role": "approver",
        },
    )
    assert approver_response.status_code == 201
    approver_headers = _auth_headers(test_client, "approver@example.com", "ChangeMe123!")

    sample_text = """
    Организация должна разместить сведения о реализуемых образовательных программах.
    Необходимо предоставить сведения о лицензии и кадровом составе.
    На официальном сайте требуется опубликовать локальные нормативные акты.
    Необходимо предоставить сведения о лицензии и кадровом составе.
    """.strip()
    evidence_text = """
    Лицензия на образовательную деятельность размещена в открытом доступе.
    Кадровый состав опубликован на официальном сайте организации.
    Локальные нормативные акты доступны в разделе "Сведения об образовательной организации".
    """.strip()

    upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": "normative"},
        files={"files": ("requirements.txt", sample_text.encode("utf-8"), "text/plain")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()[0]["id"]

    evidence_upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": "evidence"},
        files={"files": ("evidence.txt", evidence_text.encode("utf-8"), "text/plain")},
    )
    assert evidence_upload_response.status_code == 201
    evidence_document_id = evidence_upload_response.json()[0]["id"]

    process_response = test_client.post(f"/api/documents/{document_id}/process", headers=headers)
    assert process_response.status_code == 200
    assert process_response.json()["status"] in {"processed", "requires_review", "queued"}

    evidence_process_response = test_client.post(f"/api/documents/{evidence_document_id}/process", headers=headers)
    assert evidence_process_response.status_code == 200
    assert evidence_process_response.json()["status"] in {"processed", "requires_review", "queued"}

    search_response = test_client.get(
        f"/api/organizations/{organization_id}/documents/search",
        headers=headers,
        params={"query": "лицензии кадровом"},
    )
    assert search_response.status_code == 200
    search_matches = search_response.json()
    assert len(search_matches) >= 1
    assert search_matches[0]["document_id"] in {document_id, evidence_document_id}
    assert "keyword_score" in search_matches[0]
    assert "vector_score" in search_matches[0]

    report_response = test_client.post(
        f"/api/organizations/{organization_id}/reports",
        headers=headers,
        json={
            "title": "Readiness Report",
            "report_type": "readiness_report",
            "selected_document_ids": [document_id, evidence_document_id],
        },
    )
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]

    analyze_response = test_client.post(f"/api/reports/{report_id}/analyze", headers=headers)
    assert analyze_response.status_code == 200

    requirements_response = test_client.get(f"/api/organizations/{organization_id}/requirements", headers=headers)
    assert requirements_response.status_code == 200
    requirements = requirements_response.json()
    assert len(requirements) == 3
    assert len({item["title"] for item in requirements}) == len(requirements)

    requirement_update_response = test_client.patch(
        f"/api/requirements/{requirements[0]['id']}",
        headers=headers,
        json={
            "title": "Ручная редакция требования",
            "text": "Организация обязана опубликовать сведения о лицензии и кадровом обеспечении на официальном сайте.",
            "applicability_status": "applicable",
            "applicability_reason": "Проверено специалистом организации.",
            "user_comment": "Подтверждено вручную до генерации отчета.",
        },
    )
    assert requirement_update_response.status_code == 200
    assert requirement_update_response.json()["title"] == "Ручная редакция требования"
    assert requirement_update_response.json()["applicability_status"] == "applicable"
    assert requirement_update_response.json()["found_data"]

    refresh_requirement_response = test_client.post(
        f"/api/requirements/{requirements[0]['id']}/refresh-artifacts",
        headers=headers,
    )
    assert refresh_requirement_response.status_code == 200
    assert refresh_requirement_response.json()["confidence_score"] > 0

    requirement_bulk_update_response = test_client.post(
        f"/api/organizations/{organization_id}/requirements/bulk-update",
        headers=headers,
        json={
            "requirement_ids": [requirements[0]["id"]],
            "status": "confirmed",
        },
    )
    assert requirement_bulk_update_response.status_code == 200
    assert requirement_bulk_update_response.json()[0]["status"] == "confirmed"

    matrix_response = test_client.get(f"/api/reports/{report_id}/matrix", headers=headers)
    assert matrix_response.status_code == 200
    matrix_rows = matrix_response.json()
    assert len(matrix_rows) >= 1
    assert "evidence" in matrix_rows[0]
    updated_matrix_row = next(item for item in matrix_rows if item["requirement_id"] == requirements[0]["id"])
    assert updated_matrix_row["user_comment"] == "Подтверждено вручную до генерации отчета."

    explanation_response = test_client.get(f"/api/requirements/{requirements[0]['id']}/explanation", headers=headers)
    assert explanation_response.status_code == 200
    assert "Ручная редакция требования" in explanation_response.json()["conclusion"]
    assert len(explanation_response.json()["evidence_json"]) >= 1
    assert any("Наиболее релевантное подтверждение" in item for item in explanation_response.json()["logic_json"])
    assert "Лучшее подтверждение" in explanation_response.json()["explanation_text"]

    generate_response = test_client.post(f"/api/reports/{report_id}/generate", headers=headers)
    assert generate_response.status_code == 200

    sections_response = test_client.get(f"/api/reports/{report_id}/sections", headers=headers)
    assert sections_response.status_code == 200
    assert len(sections_response.json()) >= 3
    section_titles = {section["title"]: section["content"] for section in sections_response.json()}
    assert "Перечень применимых требований" in section_titles
    assert "категория:" in section_titles["Перечень применимых требований"]
    non_empty_requirement_sets = {
        tuple(section["source_requirement_ids"]) for section in sections_response.json() if section["source_requirement_ids"]
    }
    assert len(non_empty_requirement_sets) >= 2

    versions_response = test_client.get(f"/api/reports/{report_id}/versions", headers=headers)
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert len(versions) >= 1
    assert versions[0]["version_number"] >= 1
    assert len(versions[0]["sections_json"]) >= 1
    original_first_section = versions[0]["sections_json"][0]["content"]

    section_update_response = test_client.patch(
        f"/api/reports/{report_id}/sections/{sections_response.json()[0]['id']}",
        headers=headers,
        json={"content": "Пользовательская правка раздела"},
    )
    assert section_update_response.status_code == 200
    assert section_update_response.json()["content"] == "Пользовательская правка раздела"

    restore_version_response = test_client.post(
        f"/api/report-versions/{versions[0]['id']}/restore",
        headers=headers,
    )
    assert restore_version_response.status_code == 200
    assert restore_version_response.json()["status"] == "in_revision"

    restored_sections_response = test_client.get(f"/api/reports/{report_id}/sections", headers=headers)
    assert restored_sections_response.status_code == 200
    assert restored_sections_response.json()[0]["content"] == original_first_section

    versions_after_restore_response = test_client.get(f"/api/reports/{report_id}/versions", headers=headers)
    assert versions_after_restore_response.status_code == 200
    versions_after_restore = versions_after_restore_response.json()
    assert len(versions_after_restore) >= 2
    assert versions_after_restore[0]["version_number"] > versions[0]["version_number"]

    with session_factory() as session:
        risk = Risk(
            organization_id=organization_id,
            report_id=report_id,
            requirement_id=requirements[0]["id"],
            title="Недостаточно подтверждений по лицензии",
            description="Необходимо перепроверить комплект подтверждающих документов.",
            risk_level=RiskLevel.high,
            status=RiskStatus.new,
            recommended_action="Назначить исполнителя и закрыть замечание.",
        )
        session.add(risk)
        session.commit()
        risk_id = risk.id

    assign_risk_response = test_client.patch(
        f"/api/risks/{risk_id}",
        headers=headers,
        json={"assigned_to_id": approver_response.json()["user_id"]},
    )
    assert assign_risk_response.status_code == 200
    assert assign_risk_response.json()["assigned_to_id"] == approver_response.json()["user_id"]

    approver_notifications_after_assignment = test_client.get(
        f"/api/organizations/{organization_id}/notifications",
        headers=approver_headers,
    )
    assert approver_notifications_after_assignment.status_code == 200
    assert any(item["title"] == "Вам назначен риск" for item in approver_notifications_after_assignment.json())

    resolve_risk_response = test_client.post(
        f"/api/risks/{risk_id}/resolve",
        headers=approver_headers,
    )
    assert resolve_risk_response.status_code == 200
    assert resolve_risk_response.json()["status"] == "resolved"

    submit_response = test_client.post(f"/api/reports/{report_id}/submit-for-approval", headers=headers)
    assert submit_response.status_code == 200
    assert submit_response.json()["status"] == "awaiting_approval"

    approver_notifications = test_client.get(
        f"/api/organizations/{organization_id}/notifications",
        headers=approver_headers,
    )
    assert approver_notifications.status_code == 200
    approver_notification_items = approver_notifications.json()
    assert len(approver_notification_items) >= 1
    assert approver_notification_items[0]["title"] == "Отчет ожидает согласования"

    approver_dashboard = test_client.get(
        f"/api/organizations/{organization_id}/dashboard",
        headers=approver_headers,
    )
    assert approver_dashboard.status_code == 200
    assert approver_dashboard.json()["unread_notifications"] >= 1
    assert approver_dashboard.json()["reports_awaiting_approval"] == 1

    submit_again_response = test_client.post(f"/api/reports/{report_id}/submit-for-approval", headers=headers)
    assert submit_again_response.status_code == 409

    revision_response = test_client.post(f"/api/reports/{report_id}/return-to-revision", headers=approver_headers)
    assert revision_response.status_code == 200
    assert revision_response.json()["status"] == "in_revision"

    owner_notifications_after_revision = test_client.get(
        f"/api/organizations/{organization_id}/notifications",
        headers=headers,
    )
    assert owner_notifications_after_revision.status_code == 200
    assert any(item["title"] == "Отчет возвращен на доработку" for item in owner_notifications_after_revision.json())
    assert any(item["title"] == "Риск устранен" for item in owner_notifications_after_revision.json())

    submit_again_response = test_client.post(f"/api/reports/{report_id}/submit-for-approval", headers=headers)
    assert submit_again_response.status_code == 200
    assert submit_again_response.json()["status"] == "awaiting_approval"

    approve_response = test_client.post(f"/api/reports/{report_id}/approve", headers=approver_headers)
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    owner_notifications = test_client.get(
        f"/api/organizations/{organization_id}/notifications",
        headers=headers,
    )
    assert owner_notifications.status_code == 200
    owner_notification_items = owner_notifications.json()
    approved_notification = next(item for item in owner_notification_items if item["title"] == "Отчет согласован")

    read_notification = test_client.post(
        f"/api/notifications/{approved_notification['id']}/read",
        headers=headers,
    )
    assert read_notification.status_code == 200
    assert read_notification.json()["status"] == "read"

    read_all_response = test_client.post(
        f"/api/organizations/{organization_id}/notifications/read-all",
        headers=approver_headers,
    )
    assert read_all_response.status_code == 200
    assert read_all_response.json()["updated"] >= 1

    audit_logs_response = test_client.get(
        f"/api/organizations/{organization_id}/audit-logs",
        headers=headers,
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()
    assert any(item["action"] == "report_submitted_for_approval" for item in audit_logs)
    assert any(item["action"] == "report_approved" for item in audit_logs)
    assert any(item["action"] == "report_version_restored" for item in audit_logs)
    assert any(item["action"] == "risk_updated" for item in audit_logs)
    assert any(item["action"] == "requirement_updated" for item in audit_logs)
    assert any(item["action"] == "requirement_bulk_updated" for item in audit_logs)

    export_docx = test_client.post(f"/api/reports/{report_id}/export/docx", headers=headers)
    assert export_docx.status_code == 200
    assert Path(export_docx.json()["storage_path"]).exists()

    export_matrix = test_client.post(f"/api/reports/{report_id}/export/matrix", headers=headers)
    assert export_matrix.status_code == 200
    assert Path(export_matrix.json()["storage_path"]).exists()

    export_package = test_client.post(f"/api/reports/{report_id}/export/package", headers=headers)
    assert export_package.status_code == 200
    assert Path(export_package.json()["storage_path"]).exists()

    export_explanations = test_client.post(f"/api/reports/{report_id}/export/explanations", headers=headers)
    assert export_explanations.status_code == 200
    assert Path(export_explanations.json()["storage_path"]).exists()


def test_organization_update_and_delete(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="org-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "org-owner@example.com", "ChangeMe123!")

    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={
            "name": "Editable College",
            "short_name": "EC",
            "organization_type": "educational",
            "website": "https://example.edu",
            "email": "office@example.edu",
            "phone": "+7 900 000-00-00",
        },
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    update_response = test_client.patch(
        f"/api/organizations/{organization_id}",
        headers=headers,
        json={
            "name": "Editable College Updated",
            "short_name": "ECU",
            "phone": "+7 900 123-45-67",
            "director_name": "Иван Иванов",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Editable College Updated"
    assert update_response.json()["short_name"] == "ECU"
    assert update_response.json()["phone"] == "+7 900 123-45-67"
    assert update_response.json()["director_name"] == "Иван Иванов"

    delete_response = test_client.delete(f"/api/organizations/{organization_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == organization_id

    list_response = test_client.get("/api/organizations", headers=headers)
    assert list_response.status_code == 200
    assert all(item["id"] != organization_id for item in list_response.json())


def test_organization_autofill_from_processed_documents(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="autofill-owner@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "autofill-owner@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Autofill College", "organization_type": "educational"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    source_text = """
    Полное наименование: Государственное бюджетное профессиональное образовательное учреждение «Колледж цифровых технологий»
    Сокращенное наименование: ГБПОУ «КЦТ»
    ИНН: 7701234567
    КПП: 770101001
    ОГРН: 1027700123456
    Юридический адрес: 101000, г. Москва, ул. Учебная, д. 10
    Фактический адрес: 101000, г. Москва, ул. Практическая, д. 12
    ОКВЭД: 85.21
    Официальный сайт: https://college.example.ru
    Электронная почта: info@college.example.ru
    Телефон: +7 (495) 123-45-67
    Директор: Иванов Иван Иванович
    Ответственный за подготовку: Петров Петр Петрович
    """.strip()

    upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": "evidence"},
        files={"files": ("org_profile.txt", source_text.encode("utf-8"), "text/plain")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()[0]["id"]

    process_response = test_client.post(f"/api/documents/{document_id}/process", headers=headers)
    assert process_response.status_code == 200

    autofill_response = test_client.post(f"/api/organizations/{organization_id}/autofill", headers=headers)
    assert autofill_response.status_code == 200
    payload = autofill_response.json()
    assert payload["inn"] == "7701234567"
    assert payload["kpp"] == "770101001"
    assert payload["ogrn"] == "1027700123456"
    assert payload["website"] == "https://college.example.ru"
    assert payload["email"] == "info@college.example.ru"
    assert payload["phone"] == "+7 495 123-45-67"
    assert "org_profile.txt" in payload["source_documents"]
    assert "inn" in payload["matched_fields"]


def test_organization_autofill_uses_llm_refinement(client, monkeypatch):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Org Admin", email="llm-autofill@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "llm-autofill@example.com", "ChangeMe123!")
    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "LLM Autofill College", "organization_type": "educational"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    source_text = """
    Образовательная организация публикует сведения о лицензии, сайте и документах.
    Реквизиты в явном виде в текстовом корпусе не выделены.
    """.strip()

    upload_response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": "evidence"},
        files={"files": ("llm_profile.txt", source_text.encode("utf-8"), "text/plain")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()[0]["id"]
    process_response = test_client.post(f"/api/documents/{document_id}/process", headers=headers)
    assert process_response.status_code == 200

    class DummyProvider:
        provider_name = "dummy"

        def summarize(self, text: str) -> str:
            return text

        def generate_section(self, title: str, context: str) -> str:
            return context

        def complete(self, prompt: str, *, system: str = "", max_tokens: int = 256) -> str | None:
            return """
            {
              "website": "https://llm-demo.example.org",
              "email": "office@llm-demo.example.org",
              "responsible_person": "Сидорова Анна Игоревна"
            }
            """

        def status(self) -> dict[str, object]:
            return {"provider": self.provider_name, "mode": "model"}

    monkeypatch.setattr("app.services.organization_autofill.get_llm_provider", lambda: DummyProvider())

    autofill_response = test_client.post(f"/api/organizations/{organization_id}/autofill", headers=headers)
    assert autofill_response.status_code == 200
    payload = autofill_response.json()
    assert payload["website"] == "https://llm-demo.example.org"
    assert payload["email"] == "office@llm-demo.example.org"
    assert payload["responsible_person"] == "Сидорова Анна Игоревна"
