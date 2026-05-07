from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ensure_org_access, get_current_user, get_db
from app.models import MemberRole, Risk, User
from app.schemas import RiskResponse, RiskUpdate
from app.services.risks import resolve_risk as resolve_risk_service
from app.services.risks import update_risk as update_risk_service

router = APIRouter(tags=["risks"])


@router.get("/organizations/{organization_id}/risks", response_model=list[RiskResponse])
def list_risks(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Risk]:
    ensure_org_access(db, organization_id=organization_id, user=user)
    return list(db.scalars(select(Risk).where(Risk.organization_id == organization_id).order_by(Risk.created_at.desc())))


@router.get("/risks/{risk_id}", response_model=RiskResponse)
def get_risk(risk_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Risk:
    risk = db.scalar(select(Risk).where(Risk.id == risk_id))
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    ensure_org_access(db, organization_id=risk.organization_id, user=user)
    return risk


@router.patch("/risks/{risk_id}", response_model=RiskResponse)
def update_risk(
    risk_id: str,
    payload: RiskUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Risk:
    risk = db.scalar(select(Risk).where(Risk.id == risk_id))
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    ensure_org_access(db, organization_id=risk.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.approver, MemberRole.system_admin])
    return update_risk_service(db, risk, changes=payload.model_dump(exclude_unset=True), user_id=user.id)


@router.post("/risks/{risk_id}/resolve", response_model=RiskResponse)
def resolve_risk(risk_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Risk:
    risk = db.scalar(select(Risk).where(Risk.id == risk_id))
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    ensure_org_access(db, organization_id=risk.organization_id, user=user, allowed_roles=[MemberRole.org_admin, MemberRole.specialist, MemberRole.approver, MemberRole.system_admin])
    return resolve_risk_service(db, risk, user_id=user.id)
