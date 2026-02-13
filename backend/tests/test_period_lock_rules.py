from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.club import Club
from app.models.enums import LedgerEntryType, PeriodStatus, RoleName
from app.models.investor import Investor
from app.models.ledger import LedgerEntry
from app.models.period import AccountingPeriod, InvestorPosition
from app.models.tenant import Tenant
from app.models.user import User
from app.services.accounting import assert_period_writable, recalculate_period
from app.utils.decimal_math import money


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()


def test_closed_period_is_immutable_for_writes() -> None:
    db = _session()
    tenant = Tenant(id=1, code="T1", name="Tenant 1", is_active=True)
    user = User(email="admin@test.com", full_name="Admin", role=RoleName.admin, is_active=True)
    club = Club(tenant_id=1, code="LOCK", name="Locked Club", currency="UGX", is_active=True)
    db.add_all([tenant, user, club])
    db.flush()
    period = AccountingPeriod(
        tenant_id=1,
        club_id=club.id,
        year=2026,
        month=4,
        year_month="2026-04",
        status=PeriodStatus.closed,
        opening_nav=money("100.00"),
        closing_nav=money("100.00"),
        reconciliation_diff=money("0.00"),
    )
    db.add(period)
    db.flush()

    with pytest.raises(HTTPException):
        assert_period_writable(period)


def test_adjustment_is_reflected_in_open_period_recalculation() -> None:
    db = _session()
    tenant = Tenant(id=1, code="T1", name="Tenant 1", is_active=True)
    user = User(email="admin@test.com", full_name="Admin", role=RoleName.admin, is_active=True)
    club = Club(tenant_id=1, code="ADJ", name="Adjustment Club", currency="UGX", is_active=True)
    db.add_all([tenant, user, club])
    db.flush()
    investor = Investor(tenant_id=1, club_id=club.id, investor_code="INV-1", name="Investor One", is_active=True)
    db.add(investor)
    db.flush()
    period = AccountingPeriod(
        tenant_id=1,
        club_id=club.id,
        year=2026,
        month=5,
        year_month="2026-05",
        status=PeriodStatus.review,
        opening_nav=money("500.00"),
        closing_nav=money("500.00"),
        reconciliation_diff=money("0.00"),
    )
    db.add(period)
    db.flush()
    db.add(
        InvestorPosition(
            period_id=period.id,
            investor_id=investor.id,
            opening_balance=money("500.00"),
            ownership_pct=Decimal("0"),
            contributions=money("0"),
            withdrawals=money("0"),
            income_alloc=money("0"),
            expense_alloc=money("0"),
            net_allocation=money("0"),
            closing_balance=money("500.00"),
        )
    )
    db.add(
        LedgerEntry(
            tenant_id=1,
            club_id=club.id,
            period_id=period.id,
            investor_id=investor.id,
            entry_type=LedgerEntryType.adjustment,
            amount=money("50.00"),
            category="capital",
            tx_date=date(2026, 5, 10),
            description="Post-close correction through new open period",
            created_by_user_id=user.id,
        )
    )
    db.flush()

    totals = recalculate_period(db, period)
    assert totals.contributions == money("50.00")
    assert totals.closing_nav == money("550.00")
