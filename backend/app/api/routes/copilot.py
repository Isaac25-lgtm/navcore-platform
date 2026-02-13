from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_club_access
from app.models.user import User
from app.schemas.copilot import CopilotChatRequest, CopilotChatResponse, CopilotSourceOut
from app.services.copilot import answer_chat


router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/chat", response_model=CopilotChatResponse)
def chat(
    payload: CopilotChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CopilotChatResponse:
    require_club_access(db, current_user, payload.club_id)
    answer = answer_chat(
        db,
        club_id=payload.club_id,
        period_id=payload.period_id,
        message=payload.message,
    )
    return CopilotChatResponse(
        response=answer.response,
        sources=[CopilotSourceOut(type=source.type, ref=source.ref) for source in answer.sources],
    )
