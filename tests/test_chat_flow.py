from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_chat_models_and_pipeline_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("DIPLOM_DATA_DIR", str(tmp_path / "data"))

    client = TestClient(app)

    models_resp = client.get("/chat/models")
    assert models_resp.status_code == 200
    models = models_resp.json()["models"]
    assert any(item["id"] == "pipeline-basic" for item in models)
    assert any(item["id"] == "general-assistant" for item in models)

    create_resp = client.post(
        "/chat/message",
        data={
            "message": "Создай отчет для рособрнадзора",
            "profile_id": "rosobrnadzor",
            "model_id": "pipeline-basic",
        },
    )
    assert create_resp.status_code == 200
    create_payload = create_resp.json()
    report_id = create_payload["report_id"]
    assert report_id
    assert "create" in create_payload["actions"]

    sample_text = """
    Полное наименование организации: ГБПОУ Тестовый колледж
    ИНН: 7701234567
    ОГРН: 1027700123456
    Численность обучающихся: 1200
    Официальный сайт: https://test-college.ru
    """.strip()

    full_resp = client.post(
        "/chat/message",
        data={
            "message": "Сделай полный пайплайн и анализ",
            "profile_id": "rosobrnadzor",
            "model_id": "pipeline-basic",
            "report_id": report_id,
        },
        files=[("files", ("case.txt", sample_text.encode("utf-8"), "text/plain"))],
    )
    assert full_resp.status_code == 200
    payload = full_resp.json()
    assert payload["report_id"] == report_id
    assert "upload" in payload["actions"]
    assert "extract" in payload["actions"]
    assert "generate" in payload["actions"]
    assert "analysis" in payload["data"]
    assert payload.get("explanation")

    status_resp = client.get(f"/reports/{report_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "draft_generated"


def test_general_assistant_plain_text_question(tmp_path, monkeypatch):
    monkeypatch.setenv("DIPLOM_DATA_DIR", str(tmp_path / "data"))

    client = TestClient(app)
    resp = client.post(
        "/chat/message",
        data={
            "message": "Что такое переобучение модели простыми словами?",
            "profile_id": "rosobrnadzor",
            "model_id": "general-assistant",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["model_id"] == "general-assistant"
    assert "chat" in payload["actions"] or "analyze" in payload["actions"]
    assert payload["reply"]
    assert "Напишите действие:" not in payload["reply"]
    assert payload.get("explanation")


def test_general_assistant_basic_fact_is_stable(tmp_path, monkeypatch):
    monkeypatch.setenv("DIPLOM_DATA_DIR", str(tmp_path / "data"))

    client = TestClient(app)
    resp = client.post(
        "/chat/message",
        data={
            "message": "Сколько пальцев у человека?",
            "profile_id": "rosobrnadzor",
            "model_id": "general-assistant",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["model_id"] == "general-assistant"
    assert "20" in payload["reply"]


def test_file_only_message_runs_full_pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("DIPLOM_DATA_DIR", str(tmp_path / "data"))

    client = TestClient(app)
    sample_text = """
    Полное наименование организации: ГБПОУ Тестовый колледж
    ИНН: 7701234567
    ОГРН: 1027700123456
    Численность обучающихся: 1200
    """.strip()

    resp = client.post(
        "/chat/message",
        data={
            "message": "",
            "profile_id": "rosobrnadzor",
            "model_id": "pipeline-basic",
        },
        files=[("files", ("case.txt", sample_text.encode("utf-8"), "text/plain"))],
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "upload" in payload["actions"]
    assert "extract" in payload["actions"]
    assert "generate" in payload["actions"]
    assert "analysis" in payload["data"]
    assert payload["data"]["analysis"]["reason"] == "deterministic_compliance"
    assert payload["data"]["compliance"]["required_filled"] == 4
    assert payload["data"]["compliance"]["required_total"] == 4


def test_unsupported_file_skips_generate_and_analyze(tmp_path, monkeypatch):
    monkeypatch.setenv("DIPLOM_DATA_DIR", str(tmp_path / "data"))

    client = TestClient(app)
    resp = client.post(
        "/chat/message",
        data={
            "message": "",
            "profile_id": "rosobrnadzor",
            "model_id": "full-analyst",
        },
        files=[("files", ("screen.png", b"\x89PNG\r\n\x1a\n", "image/png"))],
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["data"].get("unsupported_files") == ["screen.png"]
    assert payload["data"].get("generate", {}).get("reason") == "no_extracted_values"
    assert payload["data"].get("analysis", {}).get("reason") == "no_draft"
