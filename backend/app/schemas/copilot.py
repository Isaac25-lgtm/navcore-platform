from pydantic import BaseModel, Field


class CopilotChatRequest(BaseModel):
    club_id: int
    period_id: int
    message: str = Field(min_length=2, max_length=4000)


class CopilotSourceOut(BaseModel):
    type: str
    ref: str


class CopilotChatResponse(BaseModel):
    response: str
    sources: list[CopilotSourceOut]
