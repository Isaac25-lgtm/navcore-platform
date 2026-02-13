from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import LedgerEntryType
from app.schemas.common import ORMModel


class LedgerEntryCreateRequest(BaseModel):
    entry_type: LedgerEntryType
    amount: Decimal = Field(description="Use positive amounts except adjustments.")
    description: str = Field(min_length=2, max_length=1000)
    category: str = Field(default="general", min_length=1, max_length=100)
    tx_date: date | None = None
    investor_id: int | None = None
    note: str | None = Field(default=None, max_length=3000)
    reference: str | None = Field(default=None, max_length=100)
    attachment_url: str | None = Field(default=None, max_length=1000)


class LedgerEntryUpdateRequest(BaseModel):
    amount: Decimal | None = None
    description: str | None = Field(default=None, min_length=2, max_length=1000)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    tx_date: date | None = None
    note: str | None = Field(default=None, max_length=3000)
    reference: str | None = Field(default=None, max_length=100)
    attachment_url: str | None = Field(default=None, max_length=1000)


class LedgerBulkImportRequest(BaseModel):
    entries: list[LedgerEntryCreateRequest]
    dry_run: bool = False


class LedgerEntryOut(ORMModel):
    id: int
    club_id: int
    period_id: int
    investor_id: int | None = None
    entry_type: LedgerEntryType
    amount: Decimal
    category: str
    tx_date: date
    description: str
    note: str | None = None
    reference: str | None = None
    attachment_url: str | None = None
    created_by_user_id: int
    created_at: datetime


class ReconciliationStamp(BaseModel):
    reconciled: bool
    stamp: str
    mismatch_ugx: Decimal
    club_closing_nav: Decimal
    investor_total: Decimal
