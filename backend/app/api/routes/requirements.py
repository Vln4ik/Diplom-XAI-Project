from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ensure_org_access, get_current_user, get_db
from app.models import MemberRole, Requirement, RequirementStatus, User
from app.schemas import ExplanationResponse, RequirementBulkUpdate, RequirementResponse, RequirementUpdate
from app.services.requirements import (
    bulk_update_requirements,
    get_requirement_explanation,
    set_requirement_status,
    sync_requirement_artifacts,
    update_requirement as update_requirement_service,
)

router = APIRouter(tags=["requirements"])


@router.get("/organizations/{organization_id}/requirements", response_model=list[RequirementResponse])
def list_requirements(
    organization_id: str,
    status_filter: RequirementStatus | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Requirement]:
    ensure_org_access(db, organization_id=organization_id, user=user)
    query = select(Requirement).where(Requirement.organization_id == organization_id)
    if status_filter is not None:
        query = query.where(Requirement.status == status_filter)
    return list(db.scalars(query.order_by(Requirement.created_at.desc())))


@router.get("/requirements/{requirement_id}", response_model=RequirementResponse)
def get_requirement(requirement_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Requirement:
    requirement = db.scalar(select(Requirement).where(Requirement.id == requirement_id))
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    ensure_org_access(db, organization_id=requirement.organization_id, user=user)
    return requirement


@router.patch("/requirements/{requirement_id}", response_model=RequirementResponse)
def update_requirement(
    requirement_id: str,
    payload: RequirementUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Requirement:
    requirement = db.scalar(select(Requirement).where(Requirement.id == requirement_id))
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    ensure_org_access(db, organization_id=requirement.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    requirement = update_requirement_service(db, requirement, changes=payload.model_dump(exclude_unset=True), user_id=user.id)
    return sync_requirement_artifacts(db, requirement, user_id=user.id)


@router.post("/organizations/{organization_id}/requirements/bulk-update", response_model=list[RequirementResponse])
def bulk_update(
    organization_id: str,
    payload: RequirementBulkUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Requirement]:
    ensure_org_access(
        db,
        organization_id=organization_id,
        user=user,
        allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin],
    )
    if not payload.requirement_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requirement ids are required")
    requirements = list(
        db.scalars(
            select(Requirement).where(
                Requirement.organization_id == organization_id,
                Requirement.id.in_(payload.requirement_ids),
            )
        )
    )
    if len(requirements) != len(set(payload.requirement_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more requirements not found")
    changes = payload.model_dump(exclude={"requirement_ids"}, exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes provided")
    requirements = bulk_update_requirements(db, requirements, changes=changes, user_id=user.id)
    return [sync_requirement_artifacts(db, requirement, user_id=user.id) for requirement in requirements]


@router.post("/requirements/{requirement_id}/confirm", response_model=RequirementResponse)
def confirm_requirement(requirement_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Requirement:
    requirement = db.scalar(select(Requirement).where(Requirement.id == requirement_id))
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    ensure_org_access(db, organization_id=requirement.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    requirement = set_requirement_status(db, requirement, RequirementStatus.confirmed, user_id=user.id)
    return sync_requirement_artifacts(db, requirement, user_id=user.id)


@router.post("/requirements/{requirement_id}/reject", response_model=RequirementResponse)
def reject_requirement(requirement_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Requirement:
    requirement = db.scalar(select(Requirement).where(Requirement.id == requirement_id))
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    ensure_org_access(db, organization_id=requirement.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin])
    requirement = set_requirement_status(db, requirement, RequirementStatus.rejected, user_id=user.id)
    return sync_requirement_artifacts(db, requirement, user_id=user.id)


@router.post("/requirements/{requirement_id}/refresh-artifacts", response_model=RequirementResponse)
def refresh_requirement_artifacts(
    requirement_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Requirement:
    requirement = db.scalar(select(Requirement).where(Requirement.id == requirement_id))
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    ensure_org_access(
        db,
        organization_id=requirement.organization_id,
        user=user,
        allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.system_admin],
    )
    return sync_requirement_artifacts(db, requirement, user_id=user.id)


@router.get("/requirements/{requirement_id}/explanation", response_model=ExplanationResponse)
def get_explanation(requirement_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    requirement = db.scalar(select(Requirement).where(Requirement.id == requirement_id))
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    ensure_org_access(db, organization_id=requirement.organization_id, user=user)
    explanation = get_requirement_explanation(db, requirement_id)
    if explanation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Explanation not found")
    return explanation
