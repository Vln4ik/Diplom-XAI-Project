from __future__ import annotations

from enum import Enum

from sqlalchemy.orm import Session

from app.models import Risk, RiskStatus
from app.services.audit import log_action
from app.services.notifications import notify_risk_assigned, notify_risk_resolved


def _serialize_detail(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    return value


def update_risk(
    db: Session,
    risk: Risk,
    *,
    changes: dict,
    user_id: str | None,
) -> Risk:
    previous_assigned_to_id = risk.assigned_to_id
    previous_status = risk.status
    changed_fields: dict[str, dict[str, object | None]] = {}
    for field, value in changes.items():
        current_value = getattr(risk, field)
        if current_value == value:
            continue
        changed_fields[field] = {
            "from": _serialize_detail(current_value),
            "to": _serialize_detail(value),
        }
        setattr(risk, field, value)

    db.add(risk)
    if changed_fields:
        log_action(
            db,
            action="risk_updated",
            entity_type="risk",
            entity_id=risk.id,
            organization_id=risk.organization_id,
            user_id=user_id,
            details={"report_id": risk.report_id, "changes": changed_fields},
        )
        if risk.assigned_to_id and risk.assigned_to_id != previous_assigned_to_id:
            notify_risk_assigned(db, risk=risk, triggered_by_id=user_id)
        if risk.status == RiskStatus.resolved and previous_status != RiskStatus.resolved:
            notify_risk_resolved(db, risk=risk, triggered_by_id=user_id)

    db.commit()
    db.refresh(risk)
    return risk


def resolve_risk(db: Session, risk: Risk, *, user_id: str | None) -> Risk:
    if risk.status == RiskStatus.resolved:
        db.refresh(risk)
        return risk
    return update_risk(db, risk, changes={"status": RiskStatus.resolved}, user_id=user_id)
