from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from docx import Document as DocxDocument
from openpyxl import load_workbook
from pypdf import PdfReader

from app.core.config import get_settings
from app.integrations.ocr import OCRError, get_ocr_provider
from app.models import FragmentType


@dataclass
class FragmentSeed:
    text: str
    fragment_type: FragmentType
    page_number: int | None = None
    sheet_name: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    paragraph_number: int | None = None


@dataclass
class ExtractionResult:
    text: str
    fragments: list[FragmentSeed]
    requires_review: bool = False
    page_count: int | None = None
    review_reasons: list[str] = field(default_factory=list)


NESTED_EXTRACTABLE_SUFFIXES = {
    ".txt",
    ".md",
    ".log",
    ".html",
    ".htm",
    ".rtf",
    ".json",
    ".csv",
    ".xlsx",
    ".xlsm",
    ".xls",
    ".docx",
    ".doc",
    ".xml",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
    ".sig",
    ".p7s",
    ".sign",
    ".gge",
    ".gsfx",
}


def _mark_requires_review(result: ExtractionResult, reason: str) -> ExtractionResult:
    result.requires_review = True
    if reason not in result.review_reasons:
        result.review_reasons.append(reason)
    return result


def _review_result(text: str, fragments: list[FragmentSeed], *, reason: str, page_count: int | None = None) -> ExtractionResult:
    return ExtractionResult(text=text, fragments=fragments, requires_review=True, page_count=page_count, review_reasons=[reason])


def _page_fragment_from_text(text: str, *, page_number: int) -> FragmentSeed:
    return FragmentSeed(text=text.strip(), fragment_type=FragmentType.page, page_number=page_number)


def _paragraph_fragments(text: str, *, max_fragments: int = 250) -> list[FragmentSeed]:
    return [
        FragmentSeed(text=chunk.strip(), fragment_type=FragmentType.paragraph, paragraph_number=index + 1)
        for index, chunk in enumerate(text.splitlines()[:max_fragments])
        if chunk.strip()
    ]


def _clean_xml_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _strip_invalid_xml_chars(value: str) -> str:
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", value)


def _looks_like_xml_payload(raw: bytes) -> bool:
    text = raw[:4096].decode("utf-8", errors="ignore").lstrip("\ufeff \t\r\n")
    return text.startswith("<?xml") or bool(re.match(r"<[A-Za-z_][\w:.-]*(\s|>|/)", text))


def _xml_lines_from_root(root: ElementTree.Element) -> list[str]:
    lines: list[str] = [f"XML document: {_clean_xml_tag(root.tag)}"]

    def visit(element: ElementTree.Element, trail: list[str]) -> None:
        tag = _clean_xml_tag(element.tag)
        current_trail = [*trail, tag]
        prefix = "/".join(current_trail)
        for key, value in sorted(element.attrib.items()):
            cleaned_value = " ".join(str(value).split())
            if cleaned_value:
                lines.append(f"{prefix} @{_clean_xml_tag(key)}: {cleaned_value}")
        text = " ".join((element.text or "").split())
        if text:
            lines.append(f"{prefix}: {text}")
        for child in list(element):
            visit(child, current_trail)

    visit(root, [])
    return lines


def _extract_text_file(path: Path) -> ExtractionResult:
    text = path.read_text(encoding="utf-8", errors="ignore")
    fragments = _paragraph_fragments(text)
    return ExtractionResult(text=text, fragments=fragments, page_count=len(fragments) or 1)


def _extract_html(path: Path) -> ExtractionResult:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    without_scripts = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", without_scripts)
    text = html.unescape(text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return ExtractionResult(text=text, fragments=_paragraph_fragments(text), page_count=1)


def _extract_rtf(path: Path) -> ExtractionResult:
    raw = path.read_text(encoding="cp1251", errors="ignore")
    text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", text)
    text = re.sub(r"[{}]", " ", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return ExtractionResult(text=text, fragments=_paragraph_fragments(text), page_count=1)


def _extract_json(path: Path) -> ExtractionResult:
    raw = json.loads(path.read_text(encoding="utf-8"))
    pretty = json.dumps(raw, ensure_ascii=False, indent=2)
    fragments = [
        FragmentSeed(text=chunk.strip(), fragment_type=FragmentType.paragraph, paragraph_number=index + 1)
        for index, chunk in enumerate(pretty.splitlines())
        if chunk.strip()
    ]
    return ExtractionResult(text=pretty, fragments=fragments, page_count=1)


def _extract_csv(path: Path) -> ExtractionResult:
    reader = csv.reader(StringIO(path.read_text(encoding="utf-8", errors="ignore")))
    fragments: list[FragmentSeed] = []
    lines: list[str] = []
    for index, row in enumerate(reader):
        if not any(cell.strip() for cell in row):
            continue
        line = " | ".join(cell.strip() for cell in row)
        lines.append(line)
        fragments.append(FragmentSeed(text=line, fragment_type=FragmentType.sheet_row, row_start=index + 1, row_end=index + 1))
    return ExtractionResult(text="\n".join(lines), fragments=fragments, page_count=1)


def _extract_xlsx(path: Path) -> ExtractionResult:
    workbook = load_workbook(path, data_only=True)
    lines: list[str] = []
    fragments: list[FragmentSeed] = []
    for sheet in workbook.worksheets:
        for row_index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            values = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
            if not values:
                continue
            line = " | ".join(values)
            lines.append(f"[{sheet.title}] {line}")
            fragments.append(
                FragmentSeed(
                    text=line,
                    fragment_type=FragmentType.sheet_row,
                    sheet_name=sheet.title,
                    row_start=row_index,
                    row_end=row_index,
                )
            )
    return ExtractionResult(text="\n".join(lines), fragments=fragments, page_count=len(workbook.worksheets))


def _extract_xls(path: Path) -> ExtractionResult:
    soffice_path = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice_path:
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                result = subprocess.run(
                    [soffice_path, "--headless", "--convert-to", "xlsx", "--outdir", tmp_dir, str(path)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=max(30, get_settings().document_conversion_timeout_seconds),
                )
            except subprocess.TimeoutExpired:
                result = None
            converted_path = Path(tmp_dir) / f"{path.stem}.xlsx"
            if result is not None and result.returncode == 0 and converted_path.exists():
                converted_result = _extract_xlsx(converted_path)
                converted_result.text = (
                    "Legacy XLS workbook converted to XLSX with local LibreOffice before extraction.\n"
                    f"Source file: {path.name}\n\n"
                    f"{converted_result.text}"
                )
                return converted_result

    recovered_text = _extract_readable_binary_strings(path.read_bytes(), max_lines=500)
    if _looks_like_noisy_binary_text(recovered_text):
        recovered_text = ""
    if recovered_text.strip():
        text = (
            "Legacy Excel .xls workbook.\n"
            "EvidenceXAI could not convert the file with local LibreOffice, but recovered readable strings from binary content.\n"
            f"Source file: {path.name}\n\n"
            f"{recovered_text}"
        )
        return _review_result(
            text,
            _paragraph_fragments(text),
            reason=(
                "XLS-файл обработан резервным извлечением из бинарного содержимого: "
                "таблицы, формулы и часть структуры могли быть потеряны."
            ),
            page_count=1,
        )

    text = (
        "Legacy Excel .xls workbook.\n"
        "EvidenceXAI could not convert or extract stable readable text with available local tools.\n"
        f"Source file: {path.name}\n"
        f"SHA256: {hashlib.sha256(path.read_bytes()).hexdigest()}"
    )
    return _review_result(
        text,
        _paragraph_fragments(text),
        reason=(
            "XLS-файл не удалось стабильно прочитать локальными конвертерами: "
            "нужен экспорт в XLSX/CSV или загрузка корректной копии."
        ),
        page_count=1,
    )


def _extract_docx(path: Path) -> ExtractionResult:
    document = DocxDocument(path)
    fragments: list[FragmentSeed] = []
    lines: list[str] = []
    paragraph_index = 0
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        paragraph_index += 1
        lines.append(text)
        fragments.append(FragmentSeed(text=text, fragment_type=FragmentType.paragraph, paragraph_number=paragraph_index))

    for table in document.tables:
        for row_index, row in enumerate(table.rows, start=1):
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if not cells:
                continue
            line = " | ".join(cells)
            lines.append(line)
            fragments.append(FragmentSeed(text=line, fragment_type=FragmentType.table_row, row_start=row_index, row_end=row_index))

    return ExtractionResult(text="\n".join(lines), fragments=fragments, page_count=max(paragraph_index, 1))


def _extract_doc_with_external_tool(path: Path) -> str:
    antiword_path = shutil.which("antiword")
    if antiword_path:
        try:
            result = subprocess.run(
                [antiword_path, "-m", "UTF-8", str(path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=max(10, get_settings().document_legacy_doc_timeout_seconds // 2),
            )
        except subprocess.TimeoutExpired:
            result = None
        if result is not None and result.returncode == 0 and result.stdout.strip():
            return result.stdout

    soffice_path = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice_path:
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                result = subprocess.run(
                    [soffice_path, "--headless", "--convert-to", "txt:Text", "--outdir", tmp_dir, str(path)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=max(30, get_settings().document_legacy_doc_timeout_seconds),
                )
            except subprocess.TimeoutExpired:
                result = None
            converted_path = Path(tmp_dir) / f"{path.stem}.txt"
            if result is not None and result.returncode == 0 and converted_path.exists():
                return converted_path.read_text(encoding="utf-8", errors="ignore")

    return ""


def _extract_readable_binary_strings(raw: bytes, *, max_lines: int = 600) -> str:
    candidates: list[tuple[int, str]] = []
    for encoding in ("utf-16le", "cp1251", "utf-8", "latin1"):
        decoded = raw.decode(encoding, errors="ignore").replace("\x00", " ")
        chunks = re.findall(r"[A-Za-zА-Яа-яЁё0-9№.,;:()/%+\\-«»\"'\\s]{5,}", decoded)
        lines = [" ".join(chunk.split()) for chunk in chunks]
        useful_lines = [
            line
            for line in lines
            if len(line) >= 5 and re.search(r"[A-Za-zА-Яа-яЁё]{3,}", line)
        ]
        if len(useful_lines) > 2 and sum(len(line) for line in useful_lines) / len(useful_lines) < 18:
            useful_lines = [" ".join(useful_lines)]
        text = "\n".join(dict.fromkeys(useful_lines[:max_lines]))
        cyrillic_score = len(re.findall(r"[А-Яа-яЁё]{3,}", text))
        word_score = len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]{3,}", text))
        longest_line_score = min(200, max((len(line) for line in useful_lines), default=0))
        candidates.append((cyrillic_score * 3 + word_score + longest_line_score, text))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1] if candidates else ""


def _extract_legacy_doc_fallback(path: Path) -> str:
    return _extract_readable_binary_strings(path.read_bytes())


def _looks_like_noisy_binary_text(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return True
    if re.search(r"(.)\1{24,}", compact):
        return True
    alpha_words = re.findall(r"[A-Za-zА-Яа-яЁё]{3,}", text)
    return len(alpha_words) < 3 and len(compact) > 80


def _extract_doc(path: Path) -> ExtractionResult:
    text = _extract_doc_with_external_tool(path)
    requires_review = False
    review_reasons: list[str] = []
    extraction_note = "legacy DOC extracted with local converter"
    if not text.strip():
        text = _extract_legacy_doc_fallback(path)
        if _looks_like_noisy_binary_text(text):
            text = ""
        requires_review = True
        review_reasons.append(
            "DOC-файл обработан резервным извлечением из бинарного содержимого: форматирование, таблицы и часть структуры могли быть потеряны."
        )
        extraction_note = "legacy DOC fallback extracted readable binary strings; verify formatting manually"

    if not text.strip():
        text = (
            "Legacy Microsoft Word .doc file.\n"
            "EvidenceXAI could not extract stable text with available local tools.\n"
            f"SHA256: {hashlib.sha256(path.read_bytes()).hexdigest()}"
        )
        requires_review = True
        review_reasons.append(
            "DOC-файл не удалось стабильно прочитать локальными конвертерами: в документе нет надёжно извлечённого текстового слоя."
        )

    text = f"{extraction_note}\n\n{text.strip()}"
    fragments = _paragraph_fragments(text)
    return ExtractionResult(
        text=text,
        fragments=fragments,
        requires_review=requires_review,
        page_count=len(fragments) or 1,
        review_reasons=review_reasons,
    )


def _extract_xml(path: Path) -> ExtractionResult:
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        text = path.read_text(encoding="utf-8", errors="ignore")
        cleaned_text = _strip_invalid_xml_chars(text)
        if cleaned_text != text:
            try:
                root = ElementTree.fromstring(cleaned_text)
            except ElementTree.ParseError:
                pass
            else:
                extracted = "\n".join(_xml_lines_from_root(root))
                return _review_result(
                    extracted,
                    _paragraph_fragments(extracted),
                    reason=(
                        "XML-файл удалось прочитать только после очистки недопустимых управляющих символов: "
                        "структура восстановлена частично и требует ручной проверки."
                    ),
                    page_count=1,
                )
        return _review_result(
            text,
            _paragraph_fragments(text),
            reason=f"XML-файл не прошёл синтаксический разбор: {exc}. Текст сохранён как обычный файл, но структуру XML нужно проверить вручную.",
            page_count=1,
        )

    extracted = "\n".join(_xml_lines_from_root(root))
    return ExtractionResult(text=extracted, fragments=_paragraph_fragments(extracted), page_count=1)


def _extract_pdf(path: Path) -> ExtractionResult:
    if zipfile.is_zipfile(path):
        result = _extract_zip(path)
        result.text = "File has .pdf extension but is ZIP-compatible container.\n" + result.text
        return _mark_requires_review(
            result,
            "Файл имеет расширение PDF, но фактически является ZIP-контейнером: нужно подтвердить тип файла и корректность исходного пакета.",
        )

    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raw = path.read_bytes()
        text = "\n".join(
            [
                "PDF file could not be parsed by local PDF extractor.",
                f"File: {path.name}",
                f"Size: {len(raw)} bytes",
                f"SHA256: {hashlib.sha256(raw).hexdigest()}",
                f"Parser error: {exc}",
                "Action: verify that the file is a valid PDF or replace it with an exportable copy.",
            ]
        )
        return _review_result(
            text,
            _paragraph_fragments(text),
            reason=f"PDF не удалось разобрать локальным PDF-парсером: {exc}. Проверьте, что файл не повреждён и не является контейнером другого типа.",
            page_count=1,
        )

    fragments: list[FragmentSeed] = []
    lines: list[str] = []
    requires_review = False
    review_reasons: list[str] = []
    ocr_pages_used = 0
    pdf_ocr_page_limit = max(0, get_settings().document_pdf_ocr_page_limit)
    for page_index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            if pdf_ocr_page_limit and ocr_pages_used >= pdf_ocr_page_limit:
                requires_review = True
                reason = (
                    f"PDF содержит больше отсканированных страниц, чем текущий лимит OCR ({pdf_ocr_page_limit}): "
                    f"страница {page_index} не распознана автоматически."
                )
                lines.append(
                    f"[page {page_index}] OCR skipped: runtime limit is {pdf_ocr_page_limit} scanned PDF pages per document."
                )
                if reason not in review_reasons:
                    review_reasons.append(reason)
                continue
            text = _extract_pdf_page_with_ocr(path, page_index)
            ocr_pages_used += 1
        if not text:
            requires_review = True
            review_reasons.append(
                f"На странице {page_index} нет извлекаемого текстового слоя, а OCR не вернул читаемый текст."
            )
            continue
        lines.append(text)
        fragments.append(_page_fragment_from_text(text, page_number=page_index))
    return ExtractionResult(
        text="\n\n".join(lines),
        fragments=fragments,
        requires_review=requires_review,
        page_count=len(reader.pages),
        review_reasons=review_reasons,
    )


def _extract_image(path: Path) -> ExtractionResult:
    try:
        ocr_result = get_ocr_provider().extract_text(path)
    except Exception as exc:
        return _review_result(
            "",
            [],
            reason=f"OCR изображения завершился ошибкой: {exc}. Проверьте качество изображения и локальные OCR-зависимости.",
            page_count=1,
        )

    fragments = [_page_fragment_from_text(ocr_result.text, page_number=1)] if ocr_result.text.strip() else []
    return ExtractionResult(
        text=ocr_result.text,
        fragments=fragments,
        requires_review=not bool(fragments),
        page_count=1,
        review_reasons=[] if fragments else ["OCR изображения не нашёл читаемый текст: скан пустой, низкого качества или содержит только графику."],
    )


def _render_pdf_page_for_ocr(path: Path, page_number: int) -> Any:
    try:
        import pypdfium2 as pdfium  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise OCRError("PDF OCR rendering dependencies are not installed") from exc

    pdf = None
    page = None
    try:
        pdf = pdfium.PdfDocument(str(path))
        page = pdf[page_number - 1]
        render_scale = max(1.0, float(get_settings().document_pdf_ocr_render_scale))
        pil_image = page.render(scale=render_scale).to_pil()
        return pil_image
    except Exception as exc:  # pragma: no cover - defensive
        raise OCRError(f"Unable to render PDF page {page_number} for OCR") from exc
    finally:  # pragma: no branch - defensive cleanup
        if page is not None and hasattr(page, "close"):
            page.close()
        if pdf is not None and hasattr(pdf, "close"):
            pdf.close()


def _extract_pdf_page_with_ocr(path: Path, page_number: int) -> str:
    try:
        image = _render_pdf_page_for_ocr(path, page_number)
        ocr_result = get_ocr_provider().extract_image_object(image, source_name=f"{path.name}#page={page_number}")
    except Exception:
        return ""
    return ocr_result.text.strip()


def _openssl_pkcs7_summary(path: Path) -> list[str]:
    openssl_path = shutil.which("openssl")
    if not openssl_path:
        return ["OpenSSL is not installed in runtime; certificate details were not decoded."]

    for input_format in ("DER", "PEM"):
        try:
            result = subprocess.run(
                [openssl_path, "pkcs7", "-inform", input_format, "-in", str(path), "-print_certs", "-noout"],
                check=False,
                capture_output=True,
                text=True,
                timeout=max(5, get_settings().document_signature_timeout_seconds),
            )
        except subprocess.TimeoutExpired:
            continue
        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        if result.returncode == 0 and output.strip():
            return [f"OpenSSL pkcs7 format: {input_format}", output]
    return ["OpenSSL could not decode this file as plain PKCS#7. It may be CAdES/CMS detached signature or vendor-specific signature."]


def _extract_signature(path: Path) -> ExtractionResult:
    raw = path.read_bytes()
    source_name = path.name
    for suffix in (".sig", ".p7s", ".sign"):
        if source_name.lower().endswith(suffix):
            source_name = source_name[: -len(suffix)]
            break

    lines = [
        "Electronic signature sidecar file.",
        f"Signature file: {path.name}",
        f"Likely signed source file: {source_name or 'unknown'}",
        f"Size: {len(raw)} bytes",
        f"SHA256: {hashlib.sha256(raw).hexdigest()}",
        "Verification scope: metadata extraction only; cryptographic trust validation is not performed by this extractor.",
        *_openssl_pkcs7_summary(path),
    ]
    text = "\n".join(lines)
    return ExtractionResult(text=text, fragments=_paragraph_fragments(text), requires_review=False, page_count=1)


def _is_safe_zip_member(name: str) -> bool:
    normalized = name.replace("\\", "/").strip("/")
    if not normalized or normalized.startswith("__MACOSX/") or normalized.endswith("/.DS_Store"):
        return False
    return not normalized.startswith("../") and "/../" not in normalized and not Path(normalized).is_absolute()


def _extract_zip(path: Path, *, nested_depth: int = 0) -> ExtractionResult:
    lines: list[str] = [f"Archive/container: {path.name}"]
    fragments: list[FragmentSeed] = []
    requires_review = False
    review_reasons: list[str] = []
    extracted_bytes = 0
    settings = get_settings()
    max_entries = max(1, settings.document_zip_max_entries)
    max_member_bytes = max(0, settings.document_zip_max_member_bytes)
    max_total_bytes = max(0, settings.document_zip_max_total_bytes)
    max_nested_depth = max(0, settings.document_zip_max_nested_depth)

    try:
        with zipfile.ZipFile(path) as archive:
            members = [member for member in archive.infolist() if not member.is_dir() and _is_safe_zip_member(member.filename)]
            lines.append(f"Entries: {len(members)}")
            if len(members) > max_entries:
                requires_review = True
                review_reasons.append(
                    f"Архив содержит {len(members)} файлов, что больше лимита {max_entries}: часть вложений не была проверена автоматически."
                )
                lines.append(f"Archive has more than {max_entries} entries; only first entries were inspected.")
            for index, member in enumerate(members[:max_entries], start=1):
                suffix = Path(member.filename).suffix.lower()
                member_line = f"[{index}] {member.filename} | {member.file_size} bytes | suffix={suffix or 'none'}"
                lines.append(member_line)
                fragments.append(FragmentSeed(text=member_line, fragment_type=FragmentType.paragraph, paragraph_number=len(fragments) + 1))
                if nested_depth >= max_nested_depth or suffix not in NESTED_EXTRACTABLE_SUFFIXES:
                    if suffix not in {".ds_store"}:
                        requires_review = True
                        review_reasons.append(
                            f"В архиве есть вложение `{member.filename}` с неподдерживаемым форматом `{suffix or 'без расширения'}` "
                            f"или глубиной вложенности выше текущего лимита {max_nested_depth}."
                        )
                    continue
                member_too_large = bool(max_member_bytes and member.file_size > max_member_bytes)
                total_too_large = bool(max_total_bytes and extracted_bytes + member.file_size > max_total_bytes)
                if member_too_large or total_too_large:
                    requires_review = True
                    review_reasons.append(
                        f"Вложение `{member.filename}` пропущено из-за лимита размера: файл {member.file_size} байт, "
                        f"лимит на файл {max_member_bytes or 'без ограничения'} байт, общий лимит извлечения {max_total_bytes or 'без ограничения'} байт."
                    )
                    lines.append(f"Skipped extraction for {member.filename}: size limit exceeded.")
                    continue
                try:
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        nested_path = Path(tmp_dir) / Path(member.filename).name
                        nested_path.write_bytes(archive.read(member))
                        extracted_bytes += member.file_size
                        nested_result = _extract_by_suffix(nested_path, nested_depth=nested_depth + 1)
                        nested_header = f"--- Extracted from archive: {member.filename} ---"
                        lines.append(nested_header)
                        lines.append(nested_result.text[:12000])
                        if nested_result.requires_review:
                            requires_review = True
                            nested_reasons = nested_result.review_reasons or ["вложенный файл обработан частично и требует ручной проверки."]
                            review_reasons.extend(f"Вложение `{member.filename}` требует проверки: {reason}" for reason in nested_reasons)
                        for nested_fragment in nested_result.fragments[:60]:
                            fragments.append(
                                FragmentSeed(
                                    text=f"{member.filename}: {nested_fragment.text}",
                                    fragment_type=nested_fragment.fragment_type,
                                    page_number=nested_fragment.page_number,
                                    sheet_name=nested_fragment.sheet_name,
                                    row_start=nested_fragment.row_start,
                                    row_end=nested_fragment.row_end,
                                    paragraph_number=len(fragments) + 1,
                                )
                            )
                except Exception as exc:
                    requires_review = True
                    review_reasons.append(f"Вложение `{member.filename}` не удалось извлечь из архива: {exc}.")
                    lines.append(f"Could not extract {member.filename}: {exc}")
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid ZIP/container file") from exc

    text = "\n".join(lines)
    if not fragments:
        fragments = _paragraph_fragments(text)
    return ExtractionResult(
        text=text,
        fragments=fragments,
        requires_review=requires_review,
        page_count=max(1, len(fragments)),
        review_reasons=list(dict.fromkeys(review_reasons)),
    )


def _extract_gge(path: Path) -> ExtractionResult:
    if zipfile.is_zipfile(path):
        result = _extract_zip(path)
        result.text = "GGE estimate container parsed as ZIP-compatible archive.\n" + result.text
        return result

    raw = path.read_bytes()
    if _looks_like_xml_payload(raw):
        result = _extract_xml(path)
        result.text = "GGE estimate XML document parsed directly.\n" + result.text
        return result

    recovered_text = _extract_readable_binary_strings(raw, max_lines=300)
    lines = [
        "GGE estimate container.",
        "The file is not a ZIP-compatible archive in the current runtime.",
        "EvidenceXAI saved binary metadata so the file can stay linked to the evidence package.",
        f"Size: {len(raw)} bytes",
        f"SHA256: {hashlib.sha256(raw).hexdigest()}",
    ]
    if recovered_text.strip():
        lines.extend(
            [
                "Readable text strings recovered from binary payload.",
                recovered_text[:12000],
                "Action: verify recovered strings manually or add a dedicated GGE parser for semantic checks.",
            ]
        )
        reason = (
            "GGE-файл не является ZIP-совместимым контейнером, но из бинарного содержимого удалось извлечь читаемые строки: "
            "семантическая проверка ограничена и требует ручного подтверждения."
        )
    else:
        lines.append("Action: add a dedicated GGE parser/converter if this format must be inspected semantically.")
        reason = (
            "GGE-файл не является ZIP-совместимым контейнером в текущем runtime: "
            "нужен специализированный парсер или экспорт в поддерживаемый формат."
        )
    text = "\n".join(lines)
    return _review_result(
        text,
        _paragraph_fragments(text),
        reason=reason,
        page_count=1,
    )


def _extract_gsfx(path: Path) -> ExtractionResult:
    if zipfile.is_zipfile(path):
        result = _extract_zip(path)
        result.text = "GSFX GRAND-Smeta estimate container parsed as ZIP-compatible archive.\n" + result.text
        return result

    raw = path.read_bytes()
    recovered_text = _extract_readable_binary_strings(raw, max_lines=300)
    lines = [
        "GSFX GRAND-Smeta estimate container.",
        "The file is not a ZIP-compatible archive in the current runtime.",
        "EvidenceXAI saved binary metadata so the file can stay linked to the evidence package.",
        f"Size: {len(raw)} bytes",
        f"SHA256: {hashlib.sha256(raw).hexdigest()}",
    ]
    if recovered_text.strip():
        lines.extend(
            [
                "Readable text strings recovered from binary payload.",
                recovered_text[:12000],
                "Action: verify recovered strings manually or export GSFX to XML/PDF if exact semantic checks are required.",
            ]
        )
        reason = (
            "GSFX-файл не является ZIP-совместимым контейнером, но из бинарного содержимого удалось извлечь читаемые строки: "
            "семантическая проверка ограничена и требует ручного подтверждения."
        )
    else:
        lines.append("Action: export GSFX from GRAND-Смета to XML/PDF or add a dedicated GSFX parser for semantic checks.")
        reason = (
            "GSFX-файл не является ZIP-совместимым контейнером в текущем runtime: "
            "нужен экспорт из ГРАНД-Сметы в XML/PDF или специализированный парсер."
        )
    text = "\n".join(lines)
    return _review_result(
        text,
        _paragraph_fragments(text),
        reason=reason,
        page_count=1,
    )


def _extract_macos_service_file(path: Path) -> ExtractionResult:
    text = "\n".join(
        [
            "macOS service file .DS_Store.",
            "This is not a business document and is ignored by EvidenceXAI analysis.",
            f"Size: {path.stat().st_size} bytes",
        ]
    )
    return ExtractionResult(text=text, fragments=[], requires_review=False, page_count=1)


def _extract_by_suffix(path: Path, *, nested_depth: int = 0) -> ExtractionResult:
    suffix = path.suffix.lower()
    if path.name == ".DS_Store" or suffix == ".ds_store":
        return _extract_macos_service_file(path)
    if suffix in {".txt", ".md", ".log"}:
        return _extract_text_file(path)
    if suffix in {".html", ".htm"}:
        return _extract_html(path)
    if suffix == ".rtf":
        return _extract_rtf(path)
    if suffix == ".json":
        return _extract_json(path)
    if suffix == ".csv":
        return _extract_csv(path)
    if suffix in {".xlsx", ".xlsm"}:
        return _extract_xlsx(path)
    if suffix == ".xls":
        return _extract_xls(path)
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix == ".doc":
        return _extract_doc(path)
    if suffix == ".xml":
        return _extract_xml(path)
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        return _extract_image(path)
    if suffix == ".zip":
        return _extract_zip(path, nested_depth=nested_depth)
    if suffix in {".sig", ".p7s", ".sign"}:
        return _extract_signature(path)
    if suffix == ".gge":
        return _extract_gge(path)
    if suffix == ".gsfx":
        return _extract_gsfx(path)
    raise ValueError(f"Unsupported document format: {suffix}")


def extract_document(path_str: str) -> ExtractionResult:
    return _extract_by_suffix(Path(path_str), nested_depth=0)
