from __future__ import annotations

from pathlib import Path

from app.services.auth import create_user

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples" / "documents"


def _auth_headers(test_client, email: str, password: str) -> dict[str, str]:
    response = test_client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    access_token = response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def _upload_file(test_client, headers: dict[str, str], organization_id: str, filename: str, category: str) -> str:
    file_path = SAMPLES_DIR / filename
    response = test_client.post(
        f"/api/organizations/{organization_id}/documents",
        headers=headers,
        data={"category": category},
        files={"files": (filename, file_path.read_bytes(), "application/octet-stream")},
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


def test_acceptance_web_mvp_demo_flow(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Demo Admin", email="demo-admin@example.com", password="ChangeMe123!")

    headers = _auth_headers(test_client, "demo-admin@example.com", "ChangeMe123!")

    organization_response = test_client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Demo College", "organization_type": "educational"},
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["id"]

    document_ids = [
        _upload_file(test_client, headers, organization_id, "rosobrnadzor_sample.txt", "normative"),
        _upload_file(test_client, headers, organization_id, "rosobrnadzor_evidence_site.txt", "evidence"),
        _upload_file(test_client, headers, organization_id, "organization_profile.json", "other"),
        _upload_file(test_client, headers, organization_id, "education_metrics.csv", "data_table"),
    ]

    for document_id in document_ids:
        process_response = test_client.post(f"/api/documents/{document_id}/process", headers=headers)
        assert process_response.status_code == 200

    search_response = test_client.get(
        f"/api/organizations/{organization_id}/documents/search",
        headers=headers,
        params={"query": "лицензия локальные акты"},
    )
    assert search_response.status_code == 200
    search_results = search_response.json()
    assert len(search_results) >= 2
    assert search_results[0]["score"] >= search_results[-1]["score"]

    report_response = test_client.post(
        f"/api/organizations/{organization_id}/reports",
        headers=headers,
        json={
            "title": "Acceptance Demo Report",
            "report_type": "readiness_report",
            "selected_document_ids": document_ids,
        },
    )
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]

    analyze_response = test_client.post(f"/api/reports/{report_id}/analyze", headers=headers)
    assert analyze_response.status_code == 200

    requirements_response = test_client.get(f"/api/organizations/{organization_id}/requirements", headers=headers)
    assert requirements_response.status_code == 200
    requirements = requirements_response.json()
    assert len(requirements) >= 3
    assert len({item["title"] for item in requirements}) == len(requirements)

    matrix_response = test_client.get(f"/api/reports/{report_id}/matrix", headers=headers)
    assert matrix_response.status_code == 200
    matrix_rows = matrix_response.json()
    assert len(matrix_rows) == len(requirements)
    assert all(isinstance(row["evidence"], list) for row in matrix_rows)

    for requirement in requirements:
        explanation_response = test_client.get(f"/api/requirements/{requirement['id']}/explanation", headers=headers)
        assert explanation_response.status_code == 200
        explanation = explanation_response.json()
        assert explanation["logic_json"]
        assert explanation["source_fragment_id"] or explanation["evidence_json"]

    generate_response = test_client.post(f"/api/reports/{report_id}/generate", headers=headers)
    assert generate_response.status_code == 200

    sections_response = test_client.get(f"/api/reports/{report_id}/sections", headers=headers)
    assert sections_response.status_code == 200
    sections = sections_response.json()
    assert len(sections) >= 5

    included_requirement_ids = {requirement_id for section in sections for requirement_id in section["source_requirement_ids"]}
    assert included_requirement_ids
    for requirement_id in included_requirement_ids:
        explanation_response = test_client.get(f"/api/requirements/{requirement_id}/explanation", headers=headers)
        assert explanation_response.status_code == 200
        explanation = explanation_response.json()
        assert explanation["evidence_json"]

    for export_kind in ("docx", "matrix", "package", "explanations"):
        export_response = test_client.post(f"/api/reports/{report_id}/export/{export_kind}", headers=headers)
        assert export_response.status_code == 200
        assert Path(export_response.json()["storage_path"]).exists()

    submit_response = test_client.post(f"/api/reports/{report_id}/submit-for-approval", headers=headers)
    assert submit_response.status_code == 200
    assert submit_response.json()["status"] == "awaiting_approval"
