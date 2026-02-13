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
from app.services.nav_engine import compute_monthly_nav
from app.utils.decimal_math import money


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()


def test_compute_monthly_nav_preview_with_explainability() -> None:
    db = _session()
    tenant = Tenant(id=1, code="T1", name="Tenant 1", is_active=True)
    user = User(email="u@test.com", full_name="U", role=RoleName.admin, is_active=True)
    club = Club(tenant_id=1, code="CLB", name="Club", currency="UGX", is_active=True)
    db.add_all([tenant, user, club])
    db.flush()
    inv1 = Investor(tenant_id=1, club_id=club.id, investor_code="I1", name="A", is_active=True)
    inv2 = Investor(tenant_id=1, club_id=club.id, investor_code="I2", name="B", is_active=True)
    db.add_all([inv1, inv2])
    db.flush()
    period = AccountingPeriod(
        tenant_id=1,
        club_id=club.id,
        year=2026,
        month=3,
        year_month="2026-03",
        status=PeriodStatus.draft,
        opening_nav=money("1000.00"),
        closing_nav=money("1000.00"),
        reconciliation_diff=money("0"),
    )
    db.add(period)
    db.flush()
    db.add_all(
        [
            InvestorPosition(
                period_id=period.id,
                investor_id=inv1.id,
                opening_balance=money("600.00"),
                ownership_pct=Decimal("0"),
                contributions=money("0"),
                withdrawals=money("0"),
                income_alloc=money("0"),
                expense_alloc=money("0"),
                net_allocation=money("0"),
                closing_balance=money("600.00"),
            ),
            InvestorPosition(
                period_id=period.id,
                investor_id=inv2.id,
                opening_balance=money("400.00"),
                ownership_pct=Decimal("0"),
                contributions=money("0"),
                withdrawals=money("0"),
                income_alloc=money("0"),
                expense_alloc=money("0"),
                net_allocation=money("0"),
                closing_balance=money("400.00"),
            ),
            LedgerEntry(
                tenant_id=1,
                club_id=club.id,
                period_id=period.id,
                investor_id=None,
                entry_type=LedgerEntryType.income,
                amount=money("100.00"),
                category="yield",
                tx_date=date(2026, 3, 10),
                description="Income",
                created_by_user_id=user.id,
            ),
        ]
    )
    db.flush()

    preview = compute_monthly_nav(club.id, period.id, db=db)
    assert preview.closing_nav == money("1100.00")
    assert preview.reconciliation.passed is True
    assert len(preview.explainability) == 2
    assert preview.explainability[0].income_share == money("60.00")
    assert preview.explainability[1].income_share == money("40.00")
