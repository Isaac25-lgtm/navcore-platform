from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.club import Club
from app.models.enums import LedgerEntryType, PeriodStatus, RoleName
from app.models.investor import Investor
from app.models.ledger import LedgerEntry
from app.models.period import AccountingPeriod, InvestorPosition
from app.models.tenant import Tenant
from app.models.user import User
from app.services.analytics import build_scenario_projection, generate_forecast, generate_metrics
from app.utils.decimal_math import money


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()


def test_generate_metrics_returns_anomalies_and_integrity_stamp() -> None:
    db = _session()
    tenant = Tenant(id=1, code='T1', name='Tenant 1', is_active=True)
    user = User(email='admin@test.com', full_name='Admin', role=RoleName.admin, is_active=True)
    club = Club(tenant_id=1, code='ALPHA', name='Alpha', currency='UGX', is_active=True)
    db.add_all([tenant, user, club])
    db.flush()

    period = AccountingPeriod(
        tenant_id=1,
        club_id=club.id,
        year=2026,
        month=3,
        year_month='2026-03',
        status=PeriodStatus.review,
        opening_nav=money('1000.00'),
        closing_nav=money('1000.00'),
        reconciliation_diff=money('0.00'),
    )
    db.add(period)
    db.flush()

    db.add_all(
        [
            LedgerEntry(
                tenant_id=1,
                club_id=club.id,
                period_id=period.id,
                investor_id=None,
                entry_type=LedgerEntryType.expense,
                amount=money('100.00'),
                category='opex',
                tx_date=date(2026, 3, 7),
                description='Expense one',
                reference='EXP-1',
                created_by_user_id=user.id,
            ),
            LedgerEntry(
                tenant_id=1,
                club_id=club.id,
                period_id=period.id,
                investor_id=None,
                entry_type=LedgerEntryType.expense,
                amount=money('100.00'),
                category='opex',
                tx_date=date(2026, 3, 7),
                description='Expense duplicate',
                reference='EXP-1',
                created_by_user_id=user.id,
            ),
        ]
    )
    db.flush()

    payload = generate_metrics(db, club.id, period.id)
    anomaly_codes = {item['code'] for item in payload.anomalies}
    assert 'duplicate-transaction' in anomaly_codes
    assert 'reconciliation-mismatch' in anomaly_codes
    assert payload.integrity['reconciled'] is False


def test_build_scenario_projection_includes_goal_requirement() -> None:
    scenario = build_scenario_projection(
        current_nav=money('1000000.00'),
        monthly_contribution=money('10000.00'),
        monthly_withdrawal=money('2000.00'),
        annual_yield_low_pct=Decimal('5'),
        annual_yield_high_pct=Decimal('11'),
        expense_rate_pct=Decimal('1.5'),
        months=24,
        current_year=2026,
        current_month=3,
        goal_target_amount=money('1500000.00'),
        goal_target_date='2028-03',
    )
    assert len(scenario.points) == 24
    assert scenario.goal is not None
    assert scenario.goal['months_to_goal'] == 24
    assert scenario.goal['required_monthly_contribution'] >= money('0.00')


def test_generate_forecast_outputs_confidence_band_points() -> None:
    db = _session()
    tenant = Tenant(id=1, code='T1', name='Tenant 1', is_active=True)
    user = User(email='admin@test.com', full_name='Admin', role=RoleName.admin, is_active=True)
    club = Club(tenant_id=1, code='BETA', name='Beta', currency='UGX', is_active=True)
    db.add_all([tenant, user, club])
    db.flush()
    investor = Investor(tenant_id=1, club_id=club.id, investor_code='INV-1', name='Investor One', is_active=True)
    db.add(investor)
    db.flush()

    opening = money('1000.00')
    for month in range(1, 10):
        period = AccountingPeriod(
            tenant_id=1,
            club_id=club.id,
            year=2026,
            month=month,
            year_month=f'2026-{month:02d}',
            status=PeriodStatus.closed,
            opening_nav=opening,
            closing_nav=opening,
            reconciliation_diff=money('0.00'),
        )
        db.add(period)
        db.flush()
        db.add(
            InvestorPosition(
                period_id=period.id,
                investor_id=investor.id,
                opening_balance=opening,
                ownership_pct=Decimal('100'),
                contributions=money('0.00'),
                withdrawals=money('0.00'),
                income_alloc=money('0.00'),
                expense_alloc=money('0.00'),
                net_allocation=money('0.00'),
                closing_balance=opening,
            )
        )
        db.add(
            LedgerEntry(
                tenant_id=1,
                club_id=club.id,
                period_id=period.id,
                investor_id=None,
                entry_type=LedgerEntryType.income,
                amount=money(str(40 + month * 5)),
                category='yield',
                tx_date=date(2026, month, 20),
                description='Monthly income',
                reference=f'INC-{month}',
                created_by_user_id=user.id,
            )
        )
        opening = money(opening + money(str(40 + month * 5)))

    db.flush()
    target_period = db.scalar(
        select(AccountingPeriod).where(AccountingPeriod.club_id == club.id, AccountingPeriod.month == 9)
    )
    assert target_period is not None

    forecast = generate_forecast(db, club_id=club.id, period_id=target_period.id, months=12)
    assert len(forecast['points']) == 12
    assert forecast['method'] == 'rolling_average + linear_regression'
    assert all(point['high_band_nav'] >= point['low_band_nav'] for point in forecast['points'])
