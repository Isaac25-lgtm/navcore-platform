from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.club import Club, ClubMembership
from app.models.enums import LedgerEntryType, PeriodStatus, RoleName
from app.models.investor import Investor
from app.models.ledger import LedgerEntry
from app.models.period import AccountingPeriod, InvestorPosition
from app.models.tenant import Role, Tenant, UserRole
from app.models.user import User
from app.services.accounting import recalculate_period
from app.utils.decimal_math import money


def seed_demo_data(db: Session) -> None:
    existing_user = db.scalar(select(User.id).limit(1))
    if existing_user is not None:
        return

    tenant = Tenant(code="NAVFUND", name="NAVFund Operator", is_active=True)
    db.add(tenant)
    db.flush()

    role_names = [RoleName.admin, RoleName.fund_accountant, RoleName.advisor, RoleName.investor]
    roles: dict[RoleName, Role] = {}
    for role_name in role_names:
        role = Role(name=role_name.value, description=role_name.value.replace("_", " ").title())
        db.add(role)
        roles[role_name] = role
    db.flush()

    admin = User(
        email="admin@navfund.com",
        full_name="Administrator",
        role=RoleName.admin,
        is_active=True,
    )
    accountant = User(
        email="accountant@navfund.com",
        full_name="Fund Accountant",
        role=RoleName.manager,
        is_active=True,
    )
    advisor = User(
        email="advisor@navfund.com",
        full_name="Advisor User",
        role=RoleName.analyst,
        is_active=True,
    )
    investor_user = User(
        email="investor@navfund.com",
        full_name="Investor Viewer",
        role=RoleName.viewer,
        is_active=True,
    )
    db.add_all([admin, accountant, advisor, investor_user])
    db.flush()

    db.add_all(
        [
            UserRole(tenant_id=tenant.id, user_id=admin.id, role_id=roles[RoleName.admin].id),
            UserRole(tenant_id=tenant.id, user_id=accountant.id, role_id=roles[RoleName.fund_accountant].id),
            UserRole(tenant_id=tenant.id, user_id=advisor.id, role_id=roles[RoleName.advisor].id),
            UserRole(tenant_id=tenant.id, user_id=investor_user.id, role_id=roles[RoleName.investor].id),
        ]
    )

    alpha = Club(
        tenant_id=tenant.id,
        code="ALPHA",
        name="Alpha Growth Fund",
        currency="UGX",
        is_active=True,
    )
    beta = Club(
        tenant_id=tenant.id,
        code="BETA",
        name="Beta Income Club",
        currency="UGX",
        is_active=True,
    )
    db.add_all([alpha, beta])
    db.flush()

    # user-club access rows
    db.add_all(
        [
            ClubMembership(tenant_id=tenant.id, user_id=accountant.id, club_id=alpha.id),
            ClubMembership(tenant_id=tenant.id, user_id=advisor.id, club_id=alpha.id),
            ClubMembership(tenant_id=tenant.id, user_id=advisor.id, club_id=beta.id),
            ClubMembership(tenant_id=tenant.id, user_id=investor_user.id, club_id=alpha.id),
        ]
    )

    alpha_investors = [
        Investor(tenant_id=tenant.id, club_id=alpha.id, investor_code="INV-001", name="John Mukasa"),
        Investor(tenant_id=tenant.id, club_id=alpha.id, investor_code="INV-002", name="Sarah Namuli"),
        Investor(tenant_id=tenant.id, club_id=alpha.id, investor_code="INV-003", name="David Ochieng"),
    ]
    beta_investors = [
        Investor(tenant_id=tenant.id, club_id=beta.id, investor_code="INV-004", name="Grace Auma"),
        Investor(tenant_id=tenant.id, club_id=beta.id, investor_code="INV-005", name="Peter Okello"),
    ]
    db.add_all(alpha_investors + beta_investors)
    db.flush()

    # investor-club membership rows
    db.add_all(
        [
            ClubMembership(tenant_id=tenant.id, investor_id=row.id, club_id=alpha.id) for row in alpha_investors
        ]
        + [ClubMembership(tenant_id=tenant.id, investor_id=row.id, club_id=beta.id) for row in beta_investors]
    )

    period = AccountingPeriod(
        tenant_id=tenant.id,
        club_id=alpha.id,
        year=2026,
        month=1,
        year_month="2026-01",
        status=PeriodStatus.review,
        opening_nav=money(1_050_000_000),
        closing_nav=money(1_050_000_000),
        reconciliation_diff=money(0),
    )
    db.add(period)
    db.flush()

    openings = {
        alpha_investors[0].id: money(450_000_000),
        alpha_investors[1].id: money(320_000_000),
        alpha_investors[2].id: money(280_000_000),
    }
    for investor_id, opening in openings.items():
        db.add(
            InvestorPosition(
                period_id=period.id,
                investor_id=investor_id,
                opening_balance=opening,
                ownership_pct=Decimal("0"),
                contributions=money(0),
                withdrawals=money(0),
                income_alloc=money(0),
                expense_alloc=money(0),
                net_allocation=money(0),
                closing_balance=opening,
            )
        )
    db.flush()

    db.add_all(
        [
            LedgerEntry(
                tenant_id=tenant.id,
                club_id=alpha.id,
                period_id=period.id,
                investor_id=alpha_investors[0].id,
                entry_type=LedgerEntryType.contribution,
                category="capital",
                tx_date=date(2026, 1, 4),
                amount=money(30_000_000),
                description="Top-up contribution",
                note="Investor top-up",
                reference="CAP-2026-0001",
                created_by_user_id=accountant.id,
            ),
            LedgerEntry(
                tenant_id=tenant.id,
                club_id=alpha.id,
                period_id=period.id,
                investor_id=alpha_investors[1].id,
                entry_type=LedgerEntryType.withdrawal,
                category="capital",
                tx_date=date(2026, 1, 11),
                amount=money(10_000_000),
                description="Partial redemption",
                note="Approved redemption",
                reference="WDL-2026-0001",
                created_by_user_id=accountant.id,
            ),
            LedgerEntry(
                tenant_id=tenant.id,
                club_id=alpha.id,
                period_id=period.id,
                investor_id=None,
                entry_type=LedgerEntryType.income,
                category="yield",
                tx_date=date(2026, 1, 24),
                amount=money(75_000_000),
                description="Interest and dividend income",
                note="Monthly income",
                reference="INC-2026-0001",
                created_by_user_id=accountant.id,
            ),
            LedgerEntry(
                tenant_id=tenant.id,
                club_id=alpha.id,
                period_id=period.id,
                investor_id=None,
                entry_type=LedgerEntryType.expense,
                category="opex",
                tx_date=date(2026, 1, 27),
                amount=money(12_000_000),
                description="Management and admin expenses",
                note="Monthly opex",
                reference="EXP-2026-0001",
                created_by_user_id=accountant.id,
            ),
        ]
    )

    recalculate_period(db, period)
    db.commit()
