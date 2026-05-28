from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.local import get_llm_provider
from app.models import Document, DocumentFragment, DocumentStatus
from app.schemas import OrganizationAutofillResponse

MAX_CORPUS_CHARS = 60000


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.strip().split())


def _first_match(text: str, patterns: list[str], *, flags: int = re.IGNORECASE) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if not match:
            continue
        value = _normalize_whitespace(match.group(1))
        if value:
            return value
    return None


def _first_global_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    return _normalize_whitespace(match.group(0))


def _pick_phone(text: str) -> str | None:
    pattern = r"(?:\+7|8)[\s(.-]*\d{3}[\s).-]*\d{3}[\s.-]*\d{2}[\s.-]*\d{2}"
    value = _first_global_match(text, pattern)
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11:
        if digits.startswith("8"):
            digits = f"7{digits[1:]}"
        return f"+7 {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return value


def _extract_json_object(raw: str) -> dict[str, str | None] | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    normalized: dict[str, str | None] = {}
    for key, value in payload.items():
        if value is None:
            normalized[str(key)] = None
        elif isinstance(value, str):
            text = _normalize_whitespace(value)
            normalized[str(key)] = text if text else None
    return normalized


def _collect_document_corpus(db: Session, organization_id: str) -> tuple[str, list[str]]:
    documents = list(
        db.scalars(
            select(Document)
            .where(
                Document.organization_id == organization_id,
                Document.status.in_([DocumentStatus.processed, DocumentStatus.requires_review]),
            )
            .order_by(Document.created_at.desc())
        )
    )
    if not documents:
        return "", []

    texts: list[str] = []
    for document in documents:
        if document.extracted_text:
            texts.append(document.extracted_text[:12000])
            continue
        fragments = list(
            db.scalars(
                select(DocumentFragment.fragment_text)
                .where(DocumentFragment.document_id == document.id)
                .order_by(DocumentFragment.created_at)
            )
        )
        if fragments:
            texts.append("\n".join(fragment for fragment in fragments[:40]))

    return "\n\n".join(texts)[:MAX_CORPUS_CHARS], [document.file_name for document in documents]


def _llm_extract_profile(corpus: str) -> dict[str, str | None]:
    provider = get_llm_provider()
    response = provider.complete(
        prompt=(
            "Извлеки из корпуса документов реквизиты образовательной организации. "
            "Верни только JSON без пояснений. Если поле не найдено, верни null.\n\n"
            "Поля JSON: "
            "name, short_name, inn, kpp, ogrn, legal_address, actual_address, okved, website, email, phone, director_name, responsible_person.\n\n"
            f"Корпус:\n{corpus[:12000]}"
        ),
        system=(
            "Ты извлекаешь реквизиты организации из вложенных документов. "
            "Не выдумывай данные. Возвращай строго один JSON-объект, без markdown и без комментариев."
        ),
        max_tokens=320,
    )
    if not response:
        return {}
    return _extract_json_object(response) or {}


def suggest_organization_profile_from_documents(db: Session, organization_id: str) -> OrganizationAutofillResponse:
    corpus, source_documents = _collect_document_corpus(db, organization_id)
    if not corpus:
        return OrganizationAutofillResponse(source_documents=[], processed_documents_count=0, matched_fields=[])

    suggestions = OrganizationAutofillResponse(
        name=_first_match(
            corpus,
            [
                r"(?:полное\s+наименование|наименование\s+организации)\s*[:\-]\s*([^\n]{8,220})",
                r'организация\s+["«]([^"\n»]{6,200})["»]',
            ],
        ),
        short_name=_first_match(
            corpus,
            [
                r"(?:сокращенн(?:ое|ое)\s+наименование|краткое\s+наименование)\s*[:\-]\s*([^\n]{2,120})",
                r"(?:короткое\s+наименование)\s*[:\-]\s*([^\n]{2,120})",
            ],
        ),
        inn=_first_match(corpus, [r"\bИНН\b\s*[:№-]*\s*(\d{10,12})"], flags=re.IGNORECASE),
        kpp=_first_match(corpus, [r"\bКПП\b\s*[:№-]*\s*(\d{9})"], flags=re.IGNORECASE),
        ogrn=_first_match(corpus, [r"\bОГРН\b\s*[:№-]*\s*(\d{13})"], flags=re.IGNORECASE),
        legal_address=_first_match(
            corpus,
            [
                r"(?:юридический\s+адрес|адрес\s+местонахождения)\s*[:\-]\s*([^\n]{12,260})",
            ],
        ),
        actual_address=_first_match(
            corpus,
            [
                r"(?:фактический\s+адрес|почтовый\s+адрес)\s*[:\-]\s*([^\n]{12,260})",
            ],
        ),
        okved=_first_match(corpus, [r"\bОКВЭД\b\s*[:№-]*\s*([\d.,\s]{4,40})"], flags=re.IGNORECASE),
        website=_first_global_match(corpus, r"https?://[^\s)>,]+") or _first_global_match(corpus, r"(?:www\.)[^\s)>,]+"),
        email=_first_global_match(corpus, r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}"),
        phone=_pick_phone(corpus),
        director_name=_first_match(
            corpus,
            [
                r"(?:директор|руководитель)\s*[:\-]\s*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2})",
            ],
        ),
        responsible_person=_first_match(
            corpus,
            [
                r"(?:ответственн(?:ое|ый)\s+лицо|ответственный\s+за\s+подготовку)\s*[:\-]\s*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2})",
            ],
        ),
        source_documents=source_documents,
        processed_documents_count=len(source_documents),
    )

    llm_fields = _llm_extract_profile(corpus)
    for field in (
        "name",
        "short_name",
        "inn",
        "kpp",
        "ogrn",
        "legal_address",
        "actual_address",
        "okved",
        "website",
        "email",
        "phone",
        "director_name",
        "responsible_person",
    ):
        if getattr(suggestions, field) is None and llm_fields.get(field):
            setattr(suggestions, field, llm_fields[field])

    suggestions.matched_fields = [
        field
        for field in (
            "name",
            "short_name",
            "inn",
            "kpp",
            "ogrn",
            "legal_address",
            "actual_address",
            "okved",
            "website",
            "email",
            "phone",
            "director_name",
            "responsible_person",
        )
        if getattr(suggestions, field)
    ]
    return suggestions
