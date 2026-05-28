from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

from docx import Document as DocxDocument
from openpyxl import Workbook
from pypdf import PdfWriter

from app.integrations.ocr import OCRResult
from app.processors.documents import extract_document


def test_extract_text_json_csv_docx_xlsx_pdf(tmp_path: Path):
    txt_path = tmp_path / "sample.txt"
    txt_path.write_text("Лицензия\nКадровый состав\n", encoding="utf-8")

    json_path = tmp_path / "profile.json"
    json_path.write_text(
        json.dumps({"website": "https://college.example.edu", "accreditation": True}, ensure_ascii=False),
        encoding="utf-8",
    )

    csv_path = tmp_path / "metrics.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["metric", "value"])
        writer.writerow(["teachers_total", "48"])

    docx_path = tmp_path / "acts.docx"
    document = DocxDocument()
    document.add_paragraph("На сайте опубликованы локальные нормативные акты.")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Кадры"
    table.rows[0].cells[1].text = "48 преподавателей"
    document.save(docx_path)

    xlsx_path = tmp_path / "programs.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Programs"
    sheet.append(["program", "status"])
    sheet.append(["Информационные системы", "active"])
    workbook.save(xlsx_path)

    pdf_path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    with pdf_path.open("wb") as file:
        writer.write(file)

    txt_result = extract_document(str(txt_path))
    json_result = extract_document(str(json_path))
    csv_result = extract_document(str(csv_path))
    docx_result = extract_document(str(docx_path))
    xlsx_result = extract_document(str(xlsx_path))
    pdf_result = extract_document(str(pdf_path))

    assert "Кадровый состав" in txt_result.text
    assert len(txt_result.fragments) == 2

    assert "accreditation" in json_result.text
    assert len(json_result.fragments) >= 1

    assert "teachers_total | 48" in csv_result.text
    assert len(csv_result.fragments) == 2

    assert "локальные нормативные акты" in docx_result.text
    assert any("48 преподавателей" in fragment.text for fragment in docx_result.fragments)

    assert "Информационные системы" in xlsx_result.text
    assert len(xlsx_result.fragments) >= 2

    assert pdf_result.requires_review is True
    assert pdf_result.page_count == 1


def test_extract_image_uses_ocr_provider(monkeypatch, tmp_path: Path):
    image_path = tmp_path / "license_scan.png"
    image_path.write_bytes(b"fake image placeholder")

    class StubOCRProvider:
        def extract_text(self, path: Path) -> OCRResult:
            return OCRResult(
                text="Скан лицензии и аккредитации",
                provider="stub-ocr",
                metadata={"source": path.name},
            )

    monkeypatch.setattr("app.processors.documents.get_ocr_provider", lambda: StubOCRProvider())

    result = extract_document(str(image_path))

    assert result.requires_review is False
    assert result.page_count == 1
    assert result.text == "Скан лицензии и аккредитации"
    assert len(result.fragments) == 1
    assert result.fragments[0].page_number == 1


def test_extract_pdf_uses_ocr_fallback_for_blank_page(monkeypatch, tmp_path: Path):
    pdf_path = tmp_path / "scanned.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    with pdf_path.open("wb") as file:
        writer.write(file)

    class StubOCRProvider:
        def extract_image_object(self, image: object, source_name: str) -> OCRResult:
            return OCRResult(
                text="Отсканированный приказ о размещении локальных актов",
                provider="stub-ocr",
                metadata={"source": source_name},
            )

    monkeypatch.setattr("app.processors.documents.get_ocr_provider", lambda: StubOCRProvider())
    monkeypatch.setattr(
        "app.processors.documents._render_pdf_page_for_ocr",
        lambda path, page_number: SimpleNamespace(page_number=page_number, path=path),
    )

    result = extract_document(str(pdf_path))

    assert result.requires_review is False
    assert result.page_count == 1
    assert "Отсканированный приказ" in result.text
    assert len(result.fragments) == 1
    assert result.fragments[0].page_number == 1


def test_extract_pdf_extension_zip_container_requires_review(tmp_path: Path):
    container_path = tmp_path / "signed-container.pdf"
    with zipfile.ZipFile(container_path, "w") as archive:
        archive.writestr("payload/readme.txt", "Контейнер с проектной документацией")

    result = extract_document(str(container_path))

    assert result.requires_review is True
    assert "ZIP-compatible container" in result.text
    assert "Контейнер с проектной документацией" in result.text


def test_extract_extended_real_case_formats(tmp_path: Path):
    xml_path = tmp_path / "ON_EMCHD.xml"
    xml_path.write_text(
        """
        <Доверенность Номер="123">
          <Доверитель>ООО ПКФ Водоканалпроект</Доверитель>
          <Представитель>Иванов Иван</Представитель>
        </Доверенность>
        """.strip(),
        encoding="utf-8",
    )

    doc_path = tmp_path / "Сводная смета.doc"
    doc_path.write_bytes("Сводный сметный расчет по объекту Водоканалпроект".encode("cp1251"))

    signature_path = tmp_path / "Сводная смета.doc.sig"
    signature_path.write_bytes(b"fake detached signature")

    p7s_path = tmp_path / "statement.xml.p7s"
    p7s_path.write_bytes(b"fake pkcs7 signature")

    zip_path = tmp_path / "package.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("docs/readme.txt", "Заявление о проведении государственной экспертизы")
        archive.writestr("docs/meta.xml", "<root><item>Комплект документов</item></root>")
        archive.writestr("__MACOSX/.DS_Store", b"ignored")

    gge_path = tmp_path / "estimate.gge"
    gge_path.write_bytes(b"GGE binary placeholder")

    ds_store_path = tmp_path / ".DS_Store"
    ds_store_path.write_bytes(b"macos metadata")

    xml_result = extract_document(str(xml_path))
    doc_result = extract_document(str(doc_path))
    sig_result = extract_document(str(signature_path))
    p7s_result = extract_document(str(p7s_path))
    zip_result = extract_document(str(zip_path))
    gge_result = extract_document(str(gge_path))
    ds_store_result = extract_document(str(ds_store_path))

    assert "ООО ПКФ Водоканалпроект" in xml_result.text
    assert "Сводный сметный расчет" in doc_result.text
    assert doc_result.requires_review is True

    assert "Electronic signature sidecar file" in sig_result.text
    assert "Likely signed source file: Сводная смета.doc" in sig_result.text
    assert sig_result.requires_review is False

    assert "Electronic signature sidecar file" in p7s_result.text
    assert "statement.xml" in p7s_result.text

    assert "package.zip" in zip_result.text
    assert "Заявление о проведении государственной экспертизы" in zip_result.text
    assert "__MACOSX" not in zip_result.text

    assert "GGE estimate container" in gge_result.text
    assert gge_result.requires_review is True

    assert ".DS_Store" in ds_store_result.text
    assert ds_store_result.requires_review is False
    assert ds_store_result.fragments == []
