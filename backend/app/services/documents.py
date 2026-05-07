from __future__ import annotations

from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Document, DocumentCategory, DocumentFragment, DocumentStatus, FragmentType
from app.processors.documents import extract_document
from app.services.audit import log_action
from app.services.retrieval import compute_embedding, rank_fragments, tokenize
from app.services.storage import storage


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
) -> Document:
    storage_path = storage.save_document_bytes(organization_id, file_name, content)
    document = Document(
        organization_id=organization_id,
        uploaded_by_id=uploaded_by_id,
        file_name=file_name,
        original_file_name=file_name,
        file_type=content_type or "application/octet-stream",
        file_size=len(content),
        category=category,
        storage_path=storage_path,
        status=DocumentStatus.uploaded,
        tags=tags or [],
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def process_document(db: Session, document_id: str) -> Document:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise ValueError("Document not found")

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

        for seed in extracted.fragments:
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
                    embedding_vector=compute_embedding(seed.text),
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
            details={"status": document.status.value, "fragments": len(extracted.fragments)},
        )
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:
        document.status = DocumentStatus.failed
        document.processing_error = str(exc)
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
