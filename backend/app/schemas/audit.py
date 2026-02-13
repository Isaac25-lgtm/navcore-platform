from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    tenant_id: int
    club_id: int | None
    period_id: int | None
    actor_user_id: int
    action: str
    entity_type: str
    entity_id: str
    before_state: dict | None
    after_state: dict | None
    created_at: datetime
