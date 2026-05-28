from __future__ import annotations

from app.services.terminology_quality import assess_terminology_quality, describe_terminology_quality_rules


def test_terminology_quality_detects_spelling_and_domain_term_issues():
    text = "Сметнная стоимоть указана в сметовом расчете. Обьектная ведомасть приложена."

    issues = assess_terminology_quality(text)
    by_match = {issue.matched_text.lower(): issue for issue in issues}

    assert "сметнная" in by_match
    assert "стоимоть" in by_match
    assert "сметовом" in by_match
    assert "обьектная" in by_match
    assert "ведомасть" in by_match
    assert by_match["сметовом"].issue_type == "terminology"


def test_terminology_quality_detects_mixed_script_ocr_noise():
    text = "В cметной документации найден лoкальный расчет и проектная документация."

    issues = assess_terminology_quality(text)

    assert any(issue.issue_type == "ocr_noise" and issue.matched_text == "cметной" for issue in issues)
    assert any(issue.suggestion.startswith("смет") for issue in issues)


def test_terminology_quality_does_not_flag_allowed_abbreviations():
    text = "ЛСР, ОСР, ССР, ВОР, ГИП, СРО и М.П. указаны в комплекте."

    issues = assess_terminology_quality(text)

    assert issues == []


def test_terminology_quality_rules_status_is_local():
    status = describe_terminology_quality_rules()

    assert status["provider"] == "local-terminology-rules-v1"
    assert status["runtime_scope"] == "local_server"
    assert status["sends_documents_to_external_services"] is False
    assert "ocr_mixed_script_noise" in status["checks"]
