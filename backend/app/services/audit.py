from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User


def log_audit(
    db: Session,
    *,
    actor: User,
    tenant_id: int = 1,
    action: str,
    entity_type: str,
    entity_id: str,
    club_id: int | None = None,
    period_id: int | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        club_id=club_id,
        period_id=period_id,
        before_state=before_state,
        after_state=after_state,
    )
    db.add(log)
    return log
