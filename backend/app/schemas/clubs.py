from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import PeriodStatus
from app.schemas.common import ORMModel


class ClubCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=255)
    currency: str = Field(default="UGX", min_length=3, max_length=10)


class ClubUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    currency: str | None = Field(default=None, min_length=3, max_length=10)
    is_active: bool | None = None


class ClubSummary(ORMModel):
    id: int
    code: str
    name: str
    currency: str
    is_active: bool


class InvestorCreateRequest(BaseModel):
    investor_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=255)


class InvestorUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None


class InvestorSummary(ORMModel):
    id: int
    club_id: int
    investor_code: str
    name: str
    is_active: bool


class InvestorOpeningInput(BaseModel):
    investor_id: int
    opening_balance: Decimal = Field(default=Decimal("0.00"))


class PeriodCreateRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    opening_nav: Decimal | None = None
    investor_openings: list[InvestorOpeningInput] | None = None


class PeriodSummary(ORMModel):
    id: int
    tenant_id: int
    club_id: int
    year: int
    month: int
    year_month: str
    status: PeriodStatus
    opening_nav: Decimal
    closing_nav: Decimal
    reconciliation_diff: Decimal
    locked_at: datetime | None = None
    closed_at: datetime | None = None


class PeriodMetricSummary(BaseModel):
    period_id: int
    year: int
    month: int
    status: PeriodStatus
    opening_nav: Decimal
    contributions: Decimal
    withdrawals: Decimal
    income: Decimal
    expenses: Decimal
    net_result: Decimal
    closing_nav: Decimal
    mismatch: Decimal
    return_pct: Decimal


class ClubMetricSummary(BaseModel):
    id: int
    code: str
    name: str
    currency: str
    is_active: bool
    investor_count: int
    latest_period: PeriodMetricSummary | None


class MembershipCreateRequest(BaseModel):
    investor_id: int


class MembershipSummary(ORMModel):
    id: int
    tenant_id: int
    club_id: int
    investor_id: int | None = None
    user_id: int | None = None
