from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from docx import Document as DocxDocument
from openpyxl import load_workbook
from pypdf import PdfReader

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


NESTED_EXTRACTABLE_SUFFIXES = {
    ".txt",
    ".md",
    ".log",
    ".json",
    ".csv",
    ".xlsx",
    ".xlsm",
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
    ".gge",
}
MAX_ZIP_ENTRIES = 220
MAX_ZIP_MEMBER_BYTES = 25 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 80 * 1024 * 1024
MAX_PDF_OCR_PAGES = 3


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


def _extract_text_file(path: Path) -> ExtractionResult:
    text = path.read_text(encoding="utf-8", errors="ignore")
    fragments = _paragraph_fragments(text)
    return ExtractionResult(text=text, fragments=fragments, page_count=len(fragments) or 1)


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
        result = subprocess.run(
            [antiword_path, "-m", "UTF-8", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout

    soffice_path = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice_path:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = subprocess.run(
                [soffice_path, "--headless", "--convert-to", "txt:Text", "--outdir", tmp_dir, str(path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            converted_path = Path(tmp_dir) / f"{path.stem}.txt"
            if result.returncode == 0 and converted_path.exists():
                return converted_path.read_text(encoding="utf-8", errors="ignore")

    return ""


def _extract_legacy_doc_fallback(path: Path) -> str:
    raw = path.read_bytes()
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
        text = "\n".join(dict.fromkeys(useful_lines[:600]))
        cyrillic_score = len(re.findall(r"[А-Яа-яЁё]{3,}", text))
        word_score = len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]{3,}", text))
        longest_line_score = min(200, max((len(line) for line in useful_lines), default=0))
        candidates.append((cyrillic_score * 3 + word_score + longest_line_score, text))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1] if candidates else ""


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
    extraction_note = "legacy DOC extracted with local converter"
    if not text.strip():
        text = _extract_legacy_doc_fallback(path)
        if _looks_like_noisy_binary_text(text):
            text = ""
        requires_review = True
        extraction_note = "legacy DOC fallback extracted readable binary strings; verify formatting manually"

    if not text.strip():
        text = (
            "Legacy Microsoft Word .doc file.\n"
            "EvidenceXAI could not extract stable text with available local tools.\n"
            f"SHA256: {hashlib.sha256(path.read_bytes()).hexdigest()}"
        )
        requires_review = True

    text = f"{extraction_note}\n\n{text.strip()}"
    fragments = _paragraph_fragments(text)
    return ExtractionResult(text=text, fragments=fragments, requires_review=requires_review, page_count=len(fragments) or 1)


def _extract_xml(path: Path) -> ExtractionResult:
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return ExtractionResult(text=text, fragments=_paragraph_fragments(text), requires_review=True, page_count=1)

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
    extracted = "\n".join(lines)
    return ExtractionResult(text=extracted, fragments=_paragraph_fragments(extracted), page_count=1)


def _extract_pdf(path: Path) -> ExtractionResult:
    if zipfile.is_zipfile(path):
        result = _extract_zip(path)
        result.text = "File has .pdf extension but is ZIP-compatible container.\n" + result.text
        result.requires_review = True
        return result

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
        return ExtractionResult(text=text, fragments=_paragraph_fragments(text), requires_review=True, page_count=1)

    fragments: list[FragmentSeed] = []
    lines: list[str] = []
    requires_review = False
    ocr_pages_used = 0
    for page_index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            if ocr_pages_used >= MAX_PDF_OCR_PAGES:
                requires_review = True
                lines.append(
                    f"[page {page_index}] OCR skipped: demo runtime limit is {MAX_PDF_OCR_PAGES} scanned PDF pages per document."
                )
                continue
            text = _extract_pdf_page_with_ocr(path, page_index)
            ocr_pages_used += 1
        if not text:
            requires_review = True
            continue
        lines.append(text)
        fragments.append(_page_fragment_from_text(text, page_number=page_index))
    return ExtractionResult(text="\n\n".join(lines), fragments=fragments, requires_review=requires_review, page_count=len(reader.pages))


def _extract_image(path: Path) -> ExtractionResult:
    try:
        ocr_result = get_ocr_provider().extract_text(path)
    except Exception:
        return ExtractionResult(text="", fragments=[], requires_review=True, page_count=1)

    fragments = [_page_fragment_from_text(ocr_result.text, page_number=1)] if ocr_result.text.strip() else []
    return ExtractionResult(text=ocr_result.text, fragments=fragments, requires_review=not bool(fragments), page_count=1)


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
        pil_image = page.render(scale=2.0).to_pil()
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
        result = subprocess.run(
            [openssl_path, "pkcs7", "-inform", input_format, "-in", str(path), "-print_certs", "-noout"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        if result.returncode == 0 and output.strip():
            return [f"OpenSSL pkcs7 format: {input_format}", output]
    return ["OpenSSL could not decode this file as plain PKCS#7. It may be CAdES/CMS detached signature or vendor-specific signature."]


def _extract_signature(path: Path) -> ExtractionResult:
    raw = path.read_bytes()
    source_name = path.name
    for suffix in (".sig", ".p7s"):
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
    extracted_bytes = 0

    try:
        with zipfile.ZipFile(path) as archive:
            members = [member for member in archive.infolist() if not member.is_dir() and _is_safe_zip_member(member.filename)]
            lines.append(f"Entries: {len(members)}")
            if len(members) > MAX_ZIP_ENTRIES:
                requires_review = True
                lines.append(f"Archive has more than {MAX_ZIP_ENTRIES} entries; only first entries were inspected.")
            for index, member in enumerate(members[:MAX_ZIP_ENTRIES], start=1):
                suffix = Path(member.filename).suffix.lower()
                member_line = f"[{index}] {member.filename} | {member.file_size} bytes | suffix={suffix or 'none'}"
                lines.append(member_line)
                fragments.append(FragmentSeed(text=member_line, fragment_type=FragmentType.paragraph, paragraph_number=len(fragments) + 1))
                if nested_depth > 0 or suffix not in NESTED_EXTRACTABLE_SUFFIXES:
                    requires_review = requires_review or suffix not in {".ds_store"}
                    continue
                if member.file_size > MAX_ZIP_MEMBER_BYTES or extracted_bytes + member.file_size > MAX_ZIP_TOTAL_BYTES:
                    requires_review = True
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
                        requires_review = requires_review or nested_result.requires_review
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
                    lines.append(f"Could not extract {member.filename}: {exc}")
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid ZIP/container file") from exc

    text = "\n".join(lines)
    if not fragments:
        fragments = _paragraph_fragments(text)
    return ExtractionResult(text=text, fragments=fragments, requires_review=requires_review, page_count=max(1, len(fragments)))


def _extract_gge(path: Path) -> ExtractionResult:
    if zipfile.is_zipfile(path):
        result = _extract_zip(path)
        result.text = "GGE estimate container parsed as ZIP-compatible archive.\n" + result.text
        return result

    raw = path.read_bytes()
    text = "\n".join(
        [
            "GGE estimate container.",
            "The file is not a ZIP-compatible archive in the current runtime.",
            "EvidenceXAI saved binary metadata so the file can stay linked to the evidence package.",
            f"Size: {len(raw)} bytes",
            f"SHA256: {hashlib.sha256(raw).hexdigest()}",
            "Action: add a dedicated GGE parser/converter if this format must be inspected semantically.",
        ]
    )
    return ExtractionResult(text=text, fragments=_paragraph_fragments(text), requires_review=True, page_count=1)


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
    if suffix == ".json":
        return _extract_json(path)
    if suffix == ".csv":
        return _extract_csv(path)
    if suffix in {".xlsx", ".xlsm"}:
        return _extract_xlsx(path)
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
    if suffix in {".sig", ".p7s"}:
        return _extract_signature(path)
    if suffix == ".gge":
        return _extract_gge(path)
    raise ValueError(f"Unsupported document format: {suffix}")


def extract_document(path_str: str) -> ExtractionResult:
    return _extract_by_suffix(Path(path_str), nested_depth=0)
