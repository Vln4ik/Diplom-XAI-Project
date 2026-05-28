from __future__ import annotations

import pytest

from app.models import Document, DocumentCategory, DocumentStatus
from app.services.estimate_expertise import _build_quality_findings
from app.services.visual_quality import assess_visual_quality, describe_visual_quality_provider
from app.services.visual_signatures import describe_visual_signature_provider, detect_visual_signature_or_seal


@pytest.mark.skipif(pytest.importorskip("PIL", reason="Pillow is required for visual signature tests") is None, reason="Pillow unavailable")
def test_layout_baseline_detects_signature_and_seal(tmp_path):
    from PIL import Image, ImageDraw

    path = tmp_path / "signed-page.png"
    image = Image.new("RGB", (900, 1200), "white")
    draw = ImageDraw.Draw(image)
    draw.line([(240, 930), (300, 900), (360, 940), (430, 905), (520, 925)], fill=(20, 20, 20), width=7)
    draw.ellipse((620, 850, 760, 990), outline=(190, 30, 30), width=8)
    image.save(path)

    result = detect_visual_signature_or_seal(str(path))

    assert result.available is True
    assert result.signature_like is True
    assert result.seal_like is True
    assert result.confidence > 0.5
    assert any(mark.bbox for mark in result.marks)


def test_visual_signature_provider_status_is_reportable():
    status = describe_visual_signature_provider()

    assert status["configured_provider"] == "layout_baseline"
    assert status["provider"] == "layout-baseline-v1"
    assert status["runtime_scope"] == "local_server"
    assert status["sends_documents_to_external_services"] is False
    assert status["returns"] == ["bbox", "confidence", "evidence"]


def test_visual_quality_provider_status_is_reportable():
    status = describe_visual_quality_provider()

    assert status["configured_provider"] == "layout_baseline"
    assert status["provider"] == "layout-quality-baseline-v1"
    assert status["runtime_scope"] == "local_server"
    assert status["sends_documents_to_external_services"] is False
    assert status["returns"] == ["contrast_score", "sharpness_score", "blank_like", "low_resolution", "evidence"]


@pytest.mark.skipif(pytest.importorskip("PIL", reason="Pillow is required for visual quality tests") is None, reason="Pillow unavailable")
def test_layout_quality_baseline_flags_low_quality_scan(tmp_path):
    from PIL import Image, ImageDraw, ImageFilter

    path = tmp_path / "low-quality-scan.png"
    image = Image.new("RGB", (420, 560), (248, 248, 248))
    draw = ImageDraw.Draw(image)
    draw.text((40, 80), "Сметнная стоимоть", fill=(205, 205, 205))
    image = image.filter(ImageFilter.GaussianBlur(radius=1.4))
    image.save(path)

    result = assess_visual_quality(str(path))

    assert result.available is True
    assert "low_resolution" in result.issue_keys
    assert "low_contrast" in result.issue_keys or "low_detail_or_blur" in result.issue_keys
    assert result.confidence > 0.5


@pytest.mark.skipif(pytest.importorskip("PIL", reason="Pillow is required for visual signature tests") is None, reason="Pillow unavailable")
def test_quality_stage_uses_layout_signature_detector(tmp_path):
    from PIL import Image, ImageDraw

    path = tmp_path / "signed-page.png"
    image = Image.new("RGB", (900, 1200), "white")
    draw = ImageDraw.Draw(image)
    draw.line([(240, 930), (300, 900), (360, 940), (430, 905), (520, 925)], fill=(20, 20, 20), width=7)
    draw.ellipse((620, 850, 760, 990), outline=(190, 30, 30), width=8)
    image.save(path)

    document = Document(
        id="visual-doc",
        organization_id="org",
        uploaded_by_id=None,
        file_name="Подписной_лист.png",
        original_file_name="Подписной_лист.png",
        relative_path="estimate/Подписной_лист.png",
        file_type="image/png",
        file_size=path.stat().st_size,
        category=DocumentCategory.evidence,
        storage_path=str(path),
        status=DocumentStatus.processed,
        extracted_text="",
        page_count=1,
        tags=[],
    )

    findings = _build_quality_findings([document])
    visual_finding = next(finding for finding in findings if finding["title"] == "Визуальные признаки подписи или печати найдены")

    assert visual_finding["severity"] == "info"
    assert visual_finding["confidence_score"] > 0.5
    assert "bbox=" in " ".join(visual_finding["xai_json"])


@pytest.mark.skipif(pytest.importorskip("PIL", reason="Pillow is required for visual quality tests") is None, reason="Pillow unavailable")
def test_quality_stage_adds_visual_quality_finding(tmp_path):
    from PIL import Image, ImageDraw, ImageFilter

    path = tmp_path / "low-quality-scan.png"
    image = Image.new("RGB", (420, 560), (248, 248, 248))
    draw = ImageDraw.Draw(image)
    draw.text((40, 80), "Локальный сметный расчет", fill=(205, 205, 205))
    image = image.filter(ImageFilter.GaussianBlur(radius=1.4))
    image.save(path)

    document = Document(
        id="visual-quality-doc",
        organization_id="org",
        uploaded_by_id=None,
        file_name="Некачественный_скан.png",
        original_file_name="Некачественный_скан.png",
        relative_path="estimate/Некачественный_скан.png",
        file_type="image/png",
        file_size=path.stat().st_size,
        category=DocumentCategory.evidence,
        storage_path=str(path),
        status=DocumentStatus.processed,
        extracted_text="Локальный сметный расчет",
        page_count=1,
        tags=[],
    )

    findings = _build_quality_findings([document])
    quality_finding = next(finding for finding in findings if finding["title"] == "Визуальное качество документа требует проверки")

    assert quality_finding["severity"] == "warning"
    assert "локально" in " ".join(quality_finding["xai_json"]).lower()
    assert "quality_score" in " ".join(quality_finding["xai_json"])
