from __future__ import annotations


def test_full_pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("DIPLOM_DATA_DIR", str(tmp_path / "data"))

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)

    create_resp = client.post(
        "/reports/create",
        json={
            "title": "Тестовый отчет",
            "profile_id": "rosobrnadzor",
        },
    )
    assert create_resp.status_code == 200
    report_id = create_resp.json()["report_id"]

    sample_text = """
    Полное наименование организации: ГБПОУ Тестовый колледж
    ИНН: 7701234567
    ОГРН: 1027700123456
    Численность обучающихся: 1200
    Дата самообследования: 15.03.2026
    Официальный сайт: https://test-college.ru
    """.strip()

    upload_resp = client.post(
        f"/reports/{report_id}/documents",
        files={"files": ("sample.txt", sample_text.encode("utf-8"), "text/plain")},
    )
    assert upload_resp.status_code == 200

    extract_resp = client.post(f"/reports/{report_id}/extract")
    assert extract_resp.status_code == 200
    extract_data = extract_resp.json()
    assert extract_data["required_total"] >= 4
    assert extract_data["required_filled"] >= 4

    generate_resp = client.post(f"/reports/{report_id}/generate")
    assert generate_resp.status_code == 200
    generate_data = generate_resp.json()
    assert generate_data["overall_metrics"]["Score_complete"] == 1.0
    assert len(generate_data["sections"]) >= 3

    explain_resp = client.get(f"/reports/{report_id}/explain")
    assert explain_resp.status_code == 200
    explain_data = explain_resp.json()
    assert len(explain_data["evidence_map"]) >= 1

    section_id = generate_data["sections"][0]["section_id"]
    validate_resp = client.post(
        f"/reports/{report_id}/validate",
        json={
            "section_id": section_id,
            "decision": "approved",
            "reviewer": "qa",
        },
    )
    assert validate_resp.status_code == 200
    assert validate_resp.json()["status"] in {"under_review", "validated"}
