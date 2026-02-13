from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_club_access
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut


router = APIRouter(tags=["audit"])


@router.get("/clubs/{club_id}/audit", response_model=list[AuditLogOut])
def list_club_audit_log(
    club_id: int,
    period_id: int | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuditLogOut]:
    require_club_access(db, current_user, club_id)
    query = select(AuditLog).where(AuditLog.club_id == club_id)
    if period_id is not None:
        query = query.where(AuditLog.period_id == period_id)
    rows = list(db.scalars(query.order_by(AuditLog.created_at.desc()).limit(max(1, min(limit, 500)))).all())
    return [
        AuditLogOut(
            id=row.id,
            tenant_id=row.tenant_id,
            club_id=row.club_id,
            period_id=row.period_id,
            actor_user_id=row.actor_user_id,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            before_state=row.before_state,
            after_state=row.after_state,
            created_at=row.created_at,
        )
        for row in rows
    ]
