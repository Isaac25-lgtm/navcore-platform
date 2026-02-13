from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ReportType


class ReportSnapshotOut(BaseModel):
    id: int
    tenant_id: int
    club_id: int
    period_id: int
    investor_id: int | None
    report_type: ReportType
    file_name: str
    file_hash: str
    created_at: datetime


class ReportGenerateResponse(BaseModel):
    report: ReportSnapshotOut
    download_url: str
