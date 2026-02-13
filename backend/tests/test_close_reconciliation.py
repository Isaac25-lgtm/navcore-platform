from datetime import date
from decimal import Decimal

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
from app.services.accounting import close_checklist, close_period, recalculate_period
from app.utils.decimal_math import money


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()


def test_reconciliation_and_close_month_flow() -> None:
    db = _session()
    tenant = Tenant(id=1, code="T1", name="Tenant 1", is_active=True)
    user = User(email="admin@test.com", full_name="Admin", role=RoleName.admin, is_active=True)
    club = Club(tenant_id=1, code="ALPHA", name="Alpha", currency="UGX", is_active=True)
    db.add_all([tenant, user, club])
    db.flush()

    inv1 = Investor(tenant_id=1, club_id=club.id, investor_code="I1", name="Investor One", is_active=True)
    inv2 = Investor(tenant_id=1, club_id=club.id, investor_code="I2", name="Investor Two", is_active=True)
    db.add_all([inv1, inv2])
    db.flush()

    period = AccountingPeriod(
        tenant_id=1,
        club_id=club.id,
        year=2026,
        month=1,
        year_month="2026-01",
        status=PeriodStatus.review,
        opening_nav=money("1000.00"),
        closing_nav=money("1000.00"),
        reconciliation_diff=money("0.00"),
    )
    db.add(period)
    db.flush()

    db.add_all(
        [
            InvestorPosition(
                period_id=period.id,
                investor_id=inv1.id,
                opening_balance=money("700.00"),
                ownership_pct=Decimal("0"),
                contributions=money("0"),
                withdrawals=money("0"),
                income_alloc=money("0"),
                expense_alloc=money("0"),
                net_allocation=money("0"),
                closing_balance=money("700.00"),
            ),
            InvestorPosition(
                period_id=period.id,
                investor_id=inv2.id,
                opening_balance=money("300.00"),
                ownership_pct=Decimal("0"),
                contributions=money("0"),
                withdrawals=money("0"),
                income_alloc=money("0"),
                expense_alloc=money("0"),
                net_allocation=money("0"),
                closing_balance=money("300.00"),
            ),
        ]
    )
    db.flush()
    db.add_all(
        [
            LedgerEntry(
                tenant_id=1,
                club_id=club.id,
                period_id=period.id,
                investor_id=inv1.id,
                entry_type=LedgerEntryType.contribution,
                amount=money("50.00"),
                category="capital",
                tx_date=date(2026, 1, 3),
                description="Contribution",
                created_by_user_id=user.id,
            ),
            LedgerEntry(
                tenant_id=1,
                club_id=club.id,
                period_id=period.id,
                investor_id=None,
                entry_type=LedgerEntryType.income,
                amount=money("20.00"),
                category="yield",
                tx_date=date(2026, 1, 12),
                description="Income",
                created_by_user_id=user.id,
            ),
            LedgerEntry(
                tenant_id=1,
                club_id=club.id,
                period_id=period.id,
                investor_id=None,
                entry_type=LedgerEntryType.expense,
                amount=money("10.00"),
                category="opex",
                tx_date=date(2026, 1, 20),
                description="Expense",
                created_by_user_id=user.id,
            ),
        ]
    )
    db.flush()

    totals = recalculate_period(db, period)
    assert totals.mismatch == money(0)
    checklist = close_checklist(db, period)
    assert checklist["can_close"] is True

    close_period(period, user, checklist)
    assert period.status == PeriodStatus.closed
    assert period.locked_at is not None
    assert period.closed_at is not None


def test_reconciliation_mismatch_blocks_close() -> None:
    db = _session()
    tenant = Tenant(id=1, code="T1", name="Tenant 1", is_active=True)
    user = User(email="admin@test.com", full_name="Admin", role=RoleName.admin, is_active=True)
    club = Club(tenant_id=1, code="BETA", name="Beta", currency="UGX", is_active=True)
    db.add_all([tenant, user, club])
    db.flush()

    inv = Investor(tenant_id=1, club_id=club.id, investor_code="I1", name="Investor One", is_active=True)
    db.add(inv)
    db.flush()

    period = AccountingPeriod(
        tenant_id=1,
        club_id=club.id,
        year=2026,
        month=2,
        year_month="2026-02",
        status=PeriodStatus.review,
        opening_nav=money("100.00"),
        closing_nav=money("100.00"),
        reconciliation_diff=money("0.00"),
    )
    db.add(period)
    db.flush()
    position = InvestorPosition(
        period_id=period.id,
        investor_id=inv.id,
        opening_balance=money("100.00"),
        ownership_pct=Decimal("100"),
        contributions=money("0"),
        withdrawals=money("0"),
        income_alloc=money("0"),
        expense_alloc=money("0"),
        net_allocation=money("0"),
        closing_balance=money("99.00"),
    )
    db.add(position)
    db.flush()

    checklist = close_checklist(db, period)
    assert checklist["reconciled"] is False
    assert checklist["can_close"] is False
