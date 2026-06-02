from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Document, DocumentCategory, DocumentFragment, DocumentStatus, FragmentType
from app.processors.documents import extract_document
from app.services.audit import log_action
from app.services.retrieval import compute_embeddings, rank_fragments, tokenize
from app.services.storage import storage


def describe_processing_error(exc: Exception) -> str:
    raw_message = str(exc).strip()
    raw = raw_message or exc.__class__.__name__
    normalized = f"{exc.__class__.__name__}: {raw}".lower()

    if "unsupported document format" in normalized:
        suffix = raw.split(":", 1)[-1].strip() if ":" in raw else "неизвестный формат"
        return (
            f"Формат файла {suffix} пока не поддерживается контуром извлечения текста. "
            "Загрузите документ в PDF, DOCX, DOC, XLS/XLSX, CSV, TXT, JSON, XML, ZIP, SIG/P7S/SIGN, GGE, GSFX "
            "или графическом формате, либо предварительно конвертируйте файл."
        )

    if "invalid zip/container file" in normalized or "badzipfile" in normalized or "file is not a zip file" in normalized:
        return "Архив или контейнер поврежден либо имеет неверную структуру. Проверьте файл, распакуйте его локально или загрузите корректную копию."

    if "jsondecodeerror" in normalized or "expecting value" in normalized:
        return "JSON-файл не удалось прочитать: внутри нарушена структура JSON. Проверьте синтаксис или загрузите исправленную выгрузку."

    if "permission" in normalized or "permission denied" in normalized:
        return "Backend не получил доступ к файлу в локальном хранилище. Проверьте права на файл и повторите обработку."

    if "filenotfounderror" in normalized or "no such file" in normalized:
        return "Исходный файл не найден в локальном хранилище. Вероятно, файл был удален или перемещен после загрузки; загрузите его повторно."

    if "softtimelimit" in normalized or "timelimit" in normalized or "time limit" in normalized or "timeout" in normalized:
        return (
            "Обработка превысила лимит времени: файл слишком тяжёлый для текущего профиля worker или OCR/конвертация заняли слишком много времени. "
            "В активной версии лимит увеличен, а embeddings считаются пакетно; повторите обработку. Если ошибка сохранится, уменьшите число OCR-страниц, "
            "разделите архив на подпапки или загрузите PDF с текстовым слоем."
        )

    if "ocr" in normalized or "tesseract" in normalized or "pdf ocr rendering" in normalized:
        return "OCR-контур не смог распознать текст или подготовить страницу к распознаванию. Проверьте качество скана и доступность локальных OCR-зависимостей."

    if "pdf" in normalized and ("eof" in normalized or "xref" in normalized or "startxref" in normalized or "malformed" in normalized):
        return "PDF-файл выглядит поврежденным или неполным. Откройте его локально, пересохраните в PDF и загрузите новую копию."

    if "encrypted" in normalized or "password" in normalized:
        return "Документ защищен паролем или шифрованием. Снимите защиту или загрузите экспортируемую копию без пароля."

    if "docx" in normalized or "package not found" in normalized or "word file" in normalized:
        return "DOCX/DOC-файл не удалось разобрать как корректный документ Word. Проверьте, что файл не поврежден, и при необходимости пересохраните его."

    if "openpyxl" in normalized or "excel" in normalized or "workbook" in normalized:
        return "Excel-файл не удалось открыть как корректную книгу. Проверьте формат, защиту и целостность XLS/XLSX/XLSM-файла."

    return f"Не удалось обработать документ: {raw}"


def describe_stale_processing_error(stale_after_minutes: int) -> str:
    return (
        "Обработка была остановлена по тайм-ауту или после перезапуска worker: документ оставался в статусе "
        f"`processing` больше {stale_after_minutes} мин. Повторите обработку или загрузите облегченную копию файла."
    )


def recover_stale_processing_documents(
    db: Session,
    *,
    organization_id: str | None = None,
    stale_after_minutes: int | None = None,
) -> int:
    actual_stale_after_minutes = max(1, stale_after_minutes or get_settings().document_processing_stale_minutes)
    threshold = datetime.now(UTC) - timedelta(minutes=actual_stale_after_minutes)
    query = select(Document).where(Document.status == DocumentStatus.processing, Document.updated_at < threshold)
    if organization_id is not None:
        query = query.where(Document.organization_id == organization_id)

    stale_documents = list(db.scalars(query))
    if not stale_documents:
        return 0

    reason = describe_stale_processing_error(actual_stale_after_minutes)
    for document in stale_documents:
        document.status = DocumentStatus.failed
        document.processing_error = reason
        db.add(document)
    db.commit()
    return len(stale_documents)


def create_document(
    db: Session,
    *,
    organization_id: str,
    uploaded_by_id: str | None,
    file_name: str,
    content: bytes,
    content_type: str | None,
    category: DocumentCategory,
    tags: list[str] | None = None,
    relative_path: str | None = None,
) -> Document:
    normalized_relative_path = normalize_document_relative_path(relative_path, fallback_file_name=file_name)
    storage_path = storage.save_document_bytes(organization_id, file_name, content)
    return create_document_record(
        db,
        organization_id=organization_id,
        uploaded_by_id=uploaded_by_id,
        file_name=file_name,
        storage_path=storage_path,
        file_size=len(content),
        content_type=content_type,
        category=category,
        tags=tags,
        relative_path=normalized_relative_path,
    )


def create_document_record(
    db: Session,
    *,
    organization_id: str,
    uploaded_by_id: str | None,
    file_name: str,
    storage_path: str,
    file_size: int,
    content_type: str | None,
    category: DocumentCategory,
    tags: list[str] | None = None,
    relative_path: str | None = None,
) -> Document:
    normalized_relative_path = normalize_document_relative_path(relative_path, fallback_file_name=file_name)
    document = Document(
        organization_id=organization_id,
        uploaded_by_id=uploaded_by_id,
        file_name=file_name,
        original_file_name=file_name,
        relative_path=normalized_relative_path,
        file_type=content_type or "application/octet-stream",
        file_size=file_size,
        category=category,
        storage_path=storage_path,
        status=DocumentStatus.uploaded,
        tags=tags or [],
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def normalize_document_relative_path(relative_path: str | None, *, fallback_file_name: str) -> str | None:
    if not relative_path:
        return None

    safe_parts: list[str] = []
    for part in relative_path.replace("\\", "/").split("/"):
        cleaned = part.strip()
        if not cleaned or cleaned in {".", ".."}:
            continue
        safe_parts.append(cleaned)

    if len(safe_parts) <= 1:
        return None

    safe_parts[-1] = PurePosixPath(fallback_file_name).name
    return "/".join(safe_parts)[:1024]


def process_document(db: Session, document_id: str) -> Document:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise ValueError("Document not found")
    if document.status not in {DocumentStatus.queued, DocumentStatus.processing}:
        return document

    document.status = DocumentStatus.processing
    document.processing_error = None
    db.add(document)
    db.commit()

    try:
        extracted = extract_document(document.storage_path)
        db.execute(delete(DocumentFragment).where(DocumentFragment.document_id == document.id))
        db.commit()

        document.extracted_text = extracted.text
        document.page_count = extracted.page_count
        document.processed_at = datetime.now(UTC)
        document.status = DocumentStatus.requires_review if extracted.requires_review else DocumentStatus.processed
        document.processing_error = "\n".join(extracted.review_reasons) if extracted.requires_review else None

        fragment_embeddings = compute_embeddings([seed.text for seed in extracted.fragments])
        for seed, embedding_vector in zip(extracted.fragments, fragment_embeddings, strict=True):
            db.add(
                DocumentFragment(
                    organization_id=document.organization_id,
                    document_id=document.id,
                    fragment_text=seed.text,
                    search_text=seed.text.lower(),
                    page_number=seed.page_number,
                    sheet_name=seed.sheet_name,
                    row_start=seed.row_start,
                    row_end=seed.row_end,
                    paragraph_number=seed.paragraph_number,
                    fragment_type=seed.fragment_type if isinstance(seed.fragment_type, FragmentType) else FragmentType.paragraph,
                    embedding_vector=embedding_vector,
                )
            )

        db.add(document)
        log_action(
            db,
            action="document_processed",
            entity_type="document",
            entity_id=document.id,
            organization_id=document.organization_id,
            user_id=document.uploaded_by_id,
            details={"status": document.status.value, "fragments": len(extracted.fragments), "review_reasons": extracted.review_reasons},
        )
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:
        document.status = DocumentStatus.failed
        document.processing_error = describe_processing_error(exc)
        db.add(document)
        db.commit()
        raise


def search_document_fragments(
    db: Session,
    *,
    organization_id: str,
    query: str,
    category: DocumentCategory | None = None,
    status: DocumentStatus | None = None,
    tag: str | None = None,
    limit: int = 20,
) -> list[dict]:
    tokens = tokenize(query)
    if not tokens:
        return []

    documents_query = select(Document).where(Document.organization_id == organization_id)
    if category is not None:
        documents_query = documents_query.where(Document.category == category)
    if status is not None:
        documents_query = documents_query.where(Document.status == status)

    documents = list(db.scalars(documents_query))
    if tag is not None:
        documents = [document for document in documents if tag in document.tags]
    if not documents:
        return []

    document_ids = [document.id for document in documents]
    document_index = {document.id: document for document in documents}
    fragments = list(
        db.scalars(
            select(DocumentFragment).where(DocumentFragment.document_id.in_(document_ids)).order_by(DocumentFragment.created_at)
        )
    )

    query_text = " ".join(tokens)
    ranked = rank_fragments(
        db,
        query_text=query_text,
        fragments=fragments,
        limit=limit,
        min_score=0.08,
        max_per_document=3,
    )
    return [
        {
            "fragment_id": item.fragment.id,
            "document_id": item.fragment.document_id,
            "document_name": document_index[item.fragment.document_id].file_name,
            "fragment_text": item.fragment.fragment_text,
            "score": round(item.score, 3),
            "keyword_score": round(item.keyword_score, 3),
            "vector_score": round(item.vector_score, 3),
            "page_number": item.fragment.page_number,
            "sheet_name": item.fragment.sheet_name,
        }
        for item in ranked
    ]
