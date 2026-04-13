from __future__ import annotations


def test_ui_and_generate_override(tmp_path, monkeypatch):
    monkeypatch.setenv("DIPLOM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DIPLOM_LLM_ENABLED", "1")

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)

    ui_resp = client.get("/ui")
    assert ui_resp.status_code == 200
    assert "XAI Report Builder UI" in ui_resp.text

    create_resp = client.post(
        "/reports/create",
        json={
            "title": "UI generate override test",
            "profile_id": "rosobrnadzor",
        },
    )
    report_id = create_resp.json()["report_id"]

    sample_text = """
    Полное наименование организации: ГБПОУ Тестовый колледж
    ИНН: 7701234567
    ОГРН: 1027700123456
    Численность обучающихся: 1200
    """.strip()

    upload_resp = client.post(
        f"/reports/{report_id}/documents",
        files={"files": ("sample.txt", sample_text.encode("utf-8"), "text/plain")},
    )
    assert upload_resp.status_code == 200

    extract_resp = client.post(f"/reports/{report_id}/extract")
    assert extract_resp.status_code == 200

    generate_off = client.post(f"/reports/{report_id}/generate?use_llm=false")
    assert generate_off.status_code == 200
    meta_off = generate_off.json()["generation_meta"]
    assert meta_off["llm_enabled"] is False
    assert meta_off["llm_mode"] == "disabled"

    generate_on = client.post(f"/reports/{report_id}/generate?use_llm=true")
    assert generate_on.status_code == 200
    meta_on = generate_on.json()["generation_meta"]
    assert meta_on["llm_enabled"] is True
    assert meta_on["llm_mode"] in {"applied", "fallback"}

