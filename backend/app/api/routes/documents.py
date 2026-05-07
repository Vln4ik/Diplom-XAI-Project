from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ensure_org_access, get_current_user, get_db
from app.models import Document, DocumentCategory, DocumentFragment, DocumentStatus, MemberRole, Organization, User
from app.schemas import DocumentFragmentResponse, DocumentProcessResponse, DocumentResponse, DocumentSearchMatchResponse
from app.services.documents import create_document, search_document_fragments
from app.workers.tasks import document_process_task

router = APIRouter(tags=["documents"])


@router.get("/organizations/{organization_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    ensure_org_access(db, organization_id=organization_id, user=user)
    return list(db.scalars(select(Document).where(Document.organization_id == organization_id).order_by(Document.created_at.desc())))


@router.get("/organizations/{organization_id}/documents/search", response_model=list[DocumentSearchMatchResponse])
def search_documents(
    organization_id: str,
    query: str = Query(min_length=1),
    category: DocumentCategory | None = None,
    status: DocumentStatus | None = None,
    tag: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    ensure_org_access(db, organization_id=organization_id, user=user)
    return search_document_fragments(
        db,
        organization_id=organization_id,
        query=query,
        category=category,
        status=status,
        tag=tag,
        limit=limit,
    )


@router.post("/organizations/{organization_id}/documents", response_model=list[DocumentResponse], status_code=status.HTTP_201_CREATED)
async def upload_documents(
    organization_id: str,
    files: list[UploadFile] = File(...),
    category: DocumentCategory = Form(default=DocumentCategory.other),
    tags: str = Form(default=""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    ensure_org_access(db, organization_id=organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    organization = db.scalar(select(Organization).where(Organization.id == organization_id))
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    saved: list[Document] = []
    tag_list = [item.strip() for item in tags.split(",") if item.strip()]
    for file in files:
        content = await file.read()
        saved.append(
            create_document(
                db,
                organization_id=organization.id,
                uploaded_by_id=user.id,
                file_name=file.filename or "document.bin",
                content=content,
                content_type=file.content_type,
                category=category,
                tags=tag_list,
            )
        )
    return saved


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Document:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    ensure_org_access(db, organization_id=document.organization_id, user=user)
    return document


@router.delete("/documents/{document_id}", response_model=DocumentResponse)
def delete_document(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Document:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    ensure_org_access(db, organization_id=document.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    db.delete(document)
    db.commit()
    return document


@router.post("/documents/{document_id}/process", response_model=DocumentProcessResponse)
def process_uploaded_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentProcessResponse:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    ensure_org_access(db, organization_id=document.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    document.status = DocumentStatus.queued
    db.add(document)
    db.commit()
    task = document_process_task.delay(document_id)
    db.refresh(document)
    return DocumentProcessResponse(document_id=document.id, status=document.status, task_id=task.id)


@router.get("/documents/{document_id}/fragments", response_model=list[DocumentFragmentResponse])
def list_document_fragments(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentFragment]:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    ensure_org_access(db, organization_id=document.organization_id, user=user)
    return list(db.scalars(select(DocumentFragment).where(DocumentFragment.document_id == document_id).order_by(DocumentFragment.created_at)))
