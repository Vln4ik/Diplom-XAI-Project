from __future__ import annotations

from pathlib import Path

from app.models import Risk, RiskLevel, RiskStatus
from app.services.auth import create_user


def _auth_headers(test_client, email: str, password: str) -> dict[str, str]:
    response = test_client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    access_token = response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


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
