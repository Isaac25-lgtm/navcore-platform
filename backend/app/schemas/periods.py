from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import PeriodStatus


class PositionState(BaseModel):
    investor_id: int
    investor_name: str
    opening_balance: Decimal
    ownership_pct: Decimal
    income_alloc: Decimal | None = None
    expense_alloc: Decimal | None = None
    contributions: Decimal
    withdrawals: Decimal
    net_allocation: Decimal
    closing_balance: Decimal


class PeriodStateResponse(BaseModel):
    period_id: int
    club_id: int
    year: int
    month: int
    status: PeriodStatus
    opening_nav: Decimal
    closing_nav: Decimal
    reconciliation_diff: Decimal
    locked_at: datetime | None
    totals: dict[str, Decimal]
    positions: list[PositionState]


class CloseChecklistResponse(BaseModel):
    can_close: bool
    checklist: dict[str, bool]
    reconciliation_stamp: str
    mismatch_ugx: Decimal


class CloseActionResponse(BaseModel):
    period_id: int
    status: PeriodStatus
    locked_at: datetime | None
    closed_at: datetime | None
    message: str


class InsightItem(BaseModel):
    code: str
    level: str
    title: str
    description: str


class InsightsResponse(BaseModel):
    mode: str
    items: list[InsightItem]
