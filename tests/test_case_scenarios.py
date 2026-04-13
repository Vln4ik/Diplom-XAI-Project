from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _run_case(client: TestClient, profile_id: str, title: str, text: str) -> dict:
    create_resp = client.post(
        "/reports/create",
        json={
            "title": title,
            "profile_id": profile_id,
        },
    )
    assert create_resp.status_code == 200
    report_id = create_resp.json()["report_id"]

    upload_resp = client.post(
        f"/reports/{report_id}/documents",
        files={"files": ("case.txt", text.encode("utf-8"), "text/plain")},
    )
    assert upload_resp.status_code == 200

    extract_resp = client.post(f"/reports/{report_id}/extract")
    assert extract_resp.status_code == 200

    generate_resp = client.post(f"/reports/{report_id}/generate")
    assert generate_resp.status_code == 200

    draft_resp = client.get(f"/reports/{report_id}/draft")
    assert draft_resp.status_code == 200

    return {
        "extract": extract_resp.json(),
        "generate": generate_resp.json(),
        "draft": draft_resp.json(),
    }


def test_e2e_case_scenarios_with_llm_toggle(tmp_path, monkeypatch):
    monkeypatch.setenv("DIPLOM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DIPLOM_LLM_ENABLED", "1")
    monkeypatch.setenv("DIPLOM_LLM_BASE_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
    monkeypatch.setenv("DIPLOM_LLM_ADAPTER", "data/models/sft-qwen05b-mixv3/adapter")
    monkeypatch.setenv("DIPLOM_LLM_MAX_NEW_TOKENS", "96")
    monkeypatch.setenv("DIPLOM_LLM_LOCAL_FILES_ONLY", "1")

    client = TestClient(app)

    rosobrnadzor_text = """
    Полное наименование организации: ГБПОУ Тестовый колледж
    ИНН: 7701234567
    ОГРН: 1027700123456
    Численность обучающихся: 1200
    Дата самообследования: 15.03.2026
    Официальный сайт: https://test-college.ru
    """.strip()
    roso = _run_case(
        client,
        profile_id="rosobrnadzor",
        title="Кейс Рособрнадзор",
        text=rosobrnadzor_text,
    )
    assert roso["extract"]["required_total"] == 4
    assert roso["extract"]["required_filled"] == 4
    assert roso["generate"]["overall_metrics"]["Score_complete"] == 1.0
    assert roso["generate"]["generation_meta"]["llm_enabled"] is True
    assert roso["generate"]["generation_meta"]["llm_mode"] in {"applied", "fallback"}
    assert "7701234567" in roso["draft"]["draft"]["raw_text"]
    assert "1027700123456" in roso["draft"]["draft"]["raw_text"]

    rospotrebnadzor_text = """
    Полное наименование организации: ООО Комбинат питания Школьный
    Режим дезинфекции: обработка поверхностей каждые 2 часа, кварцевание помещений
    Ответственный за санитарный контроль: Иванова Мария Петровна
    Проведено проверок: 18
    Инцидентов: 1
    """.strip()
    rsp = _run_case(
        client,
        profile_id="rospotrebnadzor",
        title="Кейс Роспотребнадзор",
        text=rospotrebnadzor_text,
    )
    assert rsp["extract"]["required_total"] == 4
    assert rsp["extract"]["required_filled"] == 4
    assert rsp["generate"]["overall_metrics"]["Score_complete"] == 1.0
    assert rsp["generate"]["generation_meta"]["llm_enabled"] is True
    assert rsp["generate"]["generation_meta"]["llm_mode"] in {"applied", "fallback"}
    assert "18" in rsp["draft"]["draft"]["raw_text"]


def test_extract_table_like_lines_with_pipe_separator(tmp_path, monkeypatch):
    monkeypatch.setenv("DIPLOM_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(app)

    roso_table_text = """
    Показатель | Значение
    Полное наименование организации | Частное образовательное учреждение Тест
    ИНН | 7723456789
    ОГРН | 1207700456789
    Количество обучающихся | 1284 человека
    Дата самообследования | 25.03.2026
    Официальный сайт | https://example.edu
    """.strip()
    roso = _run_case(
        client,
        profile_id="rosobrnadzor",
        title="Рособрнадзор таблица",
        text=roso_table_text,
    )
    assert roso["extract"]["required_filled"] == 4
    assert roso["generate"]["overall_metrics"]["Score_complete"] == 1.0

    rsp_table_text = """
    Показатель | Значение
    Полное наименование организации | ООО Учебный центр
    Режим дезинфекции | Ежедневная влажная уборка, обработка поверхностей 2 раза в день
    Ответственный за санитарное состояние | Петрова Елена Сергеевна
    Проверки пройдены | Да, пройдены 3 плановые проверки
    Количество инцидентов | 0
    """.strip()
    rsp = _run_case(
        client,
        profile_id="rospotrebnadzor",
        title="Роспотребнадзор таблица",
        text=rsp_table_text,
    )
    assert rsp["extract"]["required_filled"] == 4
    facts = rsp["extract"]["facts"]
    incidents = [item for item in facts if item["field"] == "incidents_count"][0]
    assert incidents["value"] == 0
