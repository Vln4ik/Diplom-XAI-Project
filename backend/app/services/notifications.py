from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MemberRole, Notification, NotificationStatus, OrganizationMember, Report, Risk


def create_notification(
    db: Session,
    *,
    title: str,
    body: str,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Notification:
    notification = Notification(
        organization_id=organization_id,
        user_id=user_id,
        title=title,
        body=body,
        status=NotificationStatus.unread,
    )
    db.add(notification)
    db.flush()
    return notification


def list_notifications_for_user(
    db: Session,
    *,
    user_id: str,
    organization_id: str | None = None,
    status: NotificationStatus | None = None,
    limit: int = 50,
) -> list[Notification]:
    query = select(Notification).where(Notification.user_id == user_id)
    if organization_id is not None:
        query = query.where(Notification.organization_id == organization_id)
    if status is not None:
        query = query.where(Notification.status == status)
    query = query.order_by(Notification.created_at.desc()).limit(limit)
    return list(db.scalars(query))


def mark_notification_read(db: Session, notification: Notification) -> Notification:
    notification.status = NotificationStatus.read
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_notifications_read(db: Session, *, user_id: str, organization_id: str | None = None) -> int:
    notifications = list_notifications_for_user(
        db,
        user_id=user_id,
        organization_id=organization_id,
        status=NotificationStatus.unread,
        limit=500,
    )
    if not notifications:
        return 0
    for notification in notifications:
        notification.status = NotificationStatus.read
        db.add(notification)
    db.commit()
    return len(notifications)


def _recipient_ids_for_roles(
    db: Session,
    *,
    organization_id: str,
    roles: Iterable[MemberRole],
    exclude_user_ids: set[str] | None = None,
) -> list[str]:
    memberships = list(
        db.scalars(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.role.in_(list(roles)),
            )
        )
    )
    excluded = exclude_user_ids or set()
    recipient_ids: list[str] = []
    for membership in memberships:
        if membership.user_id in excluded or membership.user_id in recipient_ids:
            continue
        recipient_ids.append(membership.user_id)
    return recipient_ids


def notify_report_submitted_for_approval(db: Session, *, report: Report, triggered_by_id: str | None) -> None:
    recipients = _recipient_ids_for_roles(
        db,
        organization_id=report.organization_id,
        roles=[MemberRole.org_admin, MemberRole.approver],
        exclude_user_ids={triggered_by_id} if triggered_by_id else None,
    )
    for recipient_id in recipients:
        create_notification(
            db,
            organization_id=report.organization_id,
            user_id=recipient_id,
            title="Отчет ожидает согласования",
            body=f"Отчет '{report.title}' переведен в статус согласования и требует проверки.",
        )


def notify_report_approved(db: Session, *, report: Report, triggered_by_id: str | None) -> None:
    recipients = _recipient_ids_for_roles(
        db,
        organization_id=report.organization_id,
        roles=[MemberRole.org_admin],
        exclude_user_ids={triggered_by_id} if triggered_by_id else None,
    )
    if report.responsible_user_id and report.responsible_user_id not in recipients and report.responsible_user_id != triggered_by_id:
        recipients.append(report.responsible_user_id)
    for recipient_id in recipients:
        create_notification(
            db,
            organization_id=report.organization_id,
            user_id=recipient_id,
            title="Отчет согласован",
            body=f"Отчет '{report.title}' получил статус approved и готов к финальной выдаче.",
        )


def notify_report_returned_to_revision(db: Session, *, report: Report, triggered_by_id: str | None) -> None:
    recipients = _recipient_ids_for_roles(
        db,
        organization_id=report.organization_id,
        roles=[MemberRole.org_admin, MemberRole.specialist],
        exclude_user_ids={triggered_by_id} if triggered_by_id else None,
    )
    if report.responsible_user_id and report.responsible_user_id not in recipients and report.responsible_user_id != triggered_by_id:
        recipients.append(report.responsible_user_id)
    for recipient_id in recipients:
        create_notification(
            db,
            organization_id=report.organization_id,
            user_id=recipient_id,
            title="Отчет возвращен на доработку",
            body=f"Отчет '{report.title}' возвращен в revision и требует доработки перед повторным согласованием.",
        )


def notify_risk_assigned(db: Session, *, risk: Risk, triggered_by_id: str | None) -> None:
    if not risk.assigned_to_id or risk.assigned_to_id == triggered_by_id:
        return
    create_notification(
        db,
        organization_id=risk.organization_id,
        user_id=risk.assigned_to_id,
        title="Вам назначен риск",
        body=f"Риск '{risk.title}' назначен вам для отработки.",
    )


def notify_risk_resolved(db: Session, *, risk: Risk, triggered_by_id: str | None) -> None:
    recipients = _recipient_ids_for_roles(
        db,
        organization_id=risk.organization_id,
        roles=[MemberRole.org_admin],
        exclude_user_ids={triggered_by_id} if triggered_by_id else None,
    )
    for recipient_id in recipients:
        create_notification(
            db,
            organization_id=risk.organization_id,
            user_id=recipient_id,
            title="Риск устранен",
            body=f"Риск '{risk.title}' переведен в resolved.",
        )
