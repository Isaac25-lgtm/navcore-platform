from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ScenarioRequest(BaseModel):
    monthly_contribution: Decimal = Field(default=Decimal("0"))
    monthly_withdrawal: Decimal = Field(default=Decimal("0"))
    annual_yield_low_pct: Decimal = Field(default=Decimal("6"))
    annual_yield_high_pct: Decimal = Field(default=Decimal("14"))
    months: int = Field(default=24, ge=12, le=36)


class InvestorExplainabilityOut(BaseModel):
    investor_id: int
    ownership_pct: Decimal
    income_share: Decimal
    expense_share: Decimal
    net_alloc: Decimal
    closing_balance: Decimal


class NavPreviewOut(BaseModel):
    club_id: int
    period_id: int
    opening_nav: Decimal
    contributions_total: Decimal
    withdrawals_total: Decimal
    income_total: Decimal
    expenses_total: Decimal
    closing_nav: Decimal
    reconciled: bool
    mismatch: Decimal
    reasons: list[str]
    explainability: list[InvestorExplainabilityOut]


class NavSnapshotOut(BaseModel):
    id: int
    tenant_id: int
    club_id: int
    period_id: int
    opening_nav: Decimal
    contributions_total: Decimal
    withdrawals_total: Decimal
    income_total: Decimal
    expenses_total: Decimal
    closing_nav: Decimal
    created_at: datetime


class CloseMonthResponse(BaseModel):
    period_id: int
    status: str
    snapshot_id: int
    message: str
