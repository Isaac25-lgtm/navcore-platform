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


def _get_or_create_tenant(db: Session, *, code: str, name: str) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.code == code))
    if tenant is not None:
        return tenant

    tenant = Tenant(code=code, name=name, is_active=True)
    db.add(tenant)
    db.flush()
    return tenant


def _get_or_create_role(db: Session, *, role_name: RoleName) -> Role:
    role = db.scalar(select(Role).where(Role.name == role_name.value))
    if role is not None:
        return role

    role = Role(name=role_name.value, description=role_name.value.replace("_", " ").title())
    db.add(role)
    db.flush()
    return role


def _get_or_create_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    role: RoleName,
) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        return user

    user = User(
        email=email,
        full_name=full_name,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _ensure_user_role(db: Session, *, tenant_id: int, user_id: int, role_id: int) -> None:
    exists = db.scalar(
        select(UserRole.id).where(
            UserRole.tenant_id == tenant_id,
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        )
    )
    if exists is None:
        db.add(UserRole(tenant_id=tenant_id, user_id=user_id, role_id=role_id))


def _get_or_create_club(
    db: Session,
    *,
    tenant_id: int,
    code: str,
    name: str,
    currency: str = "UGX",
) -> Club:
    club = db.scalar(select(Club).where(Club.tenant_id == tenant_id, Club.code == code))
    if club is not None:
        return club

    club = Club(
        tenant_id=tenant_id,
        code=code,
        name=name,
        currency=currency,
        is_active=True,
    )
    db.add(club)
    db.flush()
    return club


def _ensure_user_club_membership(db: Session, *, tenant_id: int, user_id: int, club_id: int) -> None:
    exists = db.scalar(
        select(ClubMembership.id).where(
            ClubMembership.tenant_id == tenant_id,
            ClubMembership.user_id == user_id,
            ClubMembership.club_id == club_id,
        )
    )
    if exists is None:
        db.add(ClubMembership(tenant_id=tenant_id, user_id=user_id, club_id=club_id))


def _get_or_create_investor(
    db: Session,
    *,
    tenant_id: int,
    club_id: int,
    investor_code: str,
    name: str,
) -> Investor:
    investor = db.scalar(
        select(Investor).where(
            Investor.tenant_id == tenant_id,
            Investor.club_id == club_id,
            Investor.investor_code == investor_code,
        )
    )
    if investor is not None:
        return investor

    investor = Investor(
        tenant_id=tenant_id,
        club_id=club_id,
        investor_code=investor_code,
        name=name,
    )
    db.add(investor)
    db.flush()
    return investor


def _ensure_investor_club_membership(db: Session, *, tenant_id: int, investor_id: int, club_id: int) -> None:
    exists = db.scalar(
        select(ClubMembership.id).where(
            ClubMembership.tenant_id == tenant_id,
            ClubMembership.investor_id == investor_id,
            ClubMembership.club_id == club_id,
        )
    )
    if exists is None:
        db.add(ClubMembership(tenant_id=tenant_id, investor_id=investor_id, club_id=club_id))


def _get_or_create_period(
    db: Session,
    *,
    tenant_id: int,
    club_id: int,
    year: int,
    month: int,
    status: PeriodStatus,
    opening_nav: Decimal,
) -> AccountingPeriod:
    period = db.scalar(
        select(AccountingPeriod).where(
            AccountingPeriod.club_id == club_id,
            AccountingPeriod.year == year,
            AccountingPeriod.month == month,
        )
    )
    if period is not None:
        return period

    period = AccountingPeriod(
        tenant_id=tenant_id,
        club_id=club_id,
        year=year,
        month=month,
        year_month=f"{year:04d}-{month:02d}",
        status=status,
        opening_nav=money(opening_nav),
        closing_nav=money(opening_nav),
        reconciliation_diff=money(0),
    )
    db.add(period)
    db.flush()
    return period


def _ensure_investor_position(
    db: Session,
    *,
    period_id: int,
    investor_id: int,
    opening_balance: Decimal,
) -> None:
    exists = db.scalar(
        select(InvestorPosition.id).where(
            InvestorPosition.period_id == period_id,
            InvestorPosition.investor_id == investor_id,
        )
    )
    if exists is not None:
        return

    db.add(
        InvestorPosition(
            period_id=period_id,
            investor_id=investor_id,
            opening_balance=money(opening_balance),
            ownership_pct=Decimal("0"),
            contributions=money(0),
            withdrawals=money(0),
            income_alloc=money(0),
            expense_alloc=money(0),
            net_allocation=money(0),
            closing_balance=money(opening_balance),
        )
    )


def _ensure_ledger_entry(
    db: Session,
    *,
    tenant_id: int,
    club_id: int,
    period_id: int,
    investor_id: int | None,
    entry_type: LedgerEntryType,
    category: str,
    tx_date: date,
    amount: Decimal,
    description: str,
    note: str,
    reference: str,
    created_by_user_id: int,
) -> None:
    exists = db.scalar(select(LedgerEntry.id).where(LedgerEntry.reference == reference))
    if exists is not None:
        return

    db.add(
        LedgerEntry(
            tenant_id=tenant_id,
            club_id=club_id,
            period_id=period_id,
            investor_id=investor_id,
            entry_type=entry_type,
            category=category,
            tx_date=tx_date,
            amount=money(amount),
            description=description,
            note=note,
            reference=reference,
            created_by_user_id=created_by_user_id,
        )
    )


def seed_demo_data(db: Session) -> None:
    tenant = _get_or_create_tenant(db, code="NAVFUND", name="NAVFund Operator")

    roles = {
        role_name: _get_or_create_role(db, role_name=role_name)
        for role_name in [RoleName.admin, RoleName.fund_accountant, RoleName.advisor, RoleName.investor]
    }

    admin = _get_or_create_user(
        db,
        email="admin@navfund.com",
        full_name="Administrator",
        role=RoleName.admin,
    )
    accountant = _get_or_create_user(
        db,
        email="accountant@navfund.com",
        full_name="Fund Accountant",
        role=RoleName.manager,
    )
    advisor = _get_or_create_user(
        db,
        email="advisor@navfund.com",
        full_name="Advisor User",
        role=RoleName.analyst,
    )
    investor_user = _get_or_create_user(
        db,
        email="investor@navfund.com",
        full_name="Investor Viewer",
        role=RoleName.viewer,
    )

    _ensure_user_role(db, tenant_id=tenant.id, user_id=admin.id, role_id=roles[RoleName.admin].id)
    _ensure_user_role(
        db,
        tenant_id=tenant.id,
        user_id=accountant.id,
        role_id=roles[RoleName.fund_accountant].id,
    )
    _ensure_user_role(db, tenant_id=tenant.id, user_id=advisor.id, role_id=roles[RoleName.advisor].id)
    _ensure_user_role(
        db,
        tenant_id=tenant.id,
        user_id=investor_user.id,
        role_id=roles[RoleName.investor].id,
    )

    alpha = _get_or_create_club(db, tenant_id=tenant.id, code="ALPHA", name="Alpha Growth Fund")
    beta = _get_or_create_club(db, tenant_id=tenant.id, code="BETA", name="Beta Income Club")

    _ensure_user_club_membership(db, tenant_id=tenant.id, user_id=accountant.id, club_id=alpha.id)
    _ensure_user_club_membership(db, tenant_id=tenant.id, user_id=advisor.id, club_id=alpha.id)
    _ensure_user_club_membership(db, tenant_id=tenant.id, user_id=advisor.id, club_id=beta.id)
    _ensure_user_club_membership(db, tenant_id=tenant.id, user_id=investor_user.id, club_id=alpha.id)

    alpha_investors = [
        _get_or_create_investor(
            db,
            tenant_id=tenant.id,
            club_id=alpha.id,
            investor_code="INV-001",
            name="John Mukasa",
        ),
        _get_or_create_investor(
            db,
            tenant_id=tenant.id,
            club_id=alpha.id,
            investor_code="INV-002",
            name="Sarah Namuli",
        ),
        _get_or_create_investor(
            db,
            tenant_id=tenant.id,
            club_id=alpha.id,
            investor_code="INV-003",
            name="David Ochieng",
        ),
    ]
    beta_investors = [
        _get_or_create_investor(
            db,
            tenant_id=tenant.id,
            club_id=beta.id,
            investor_code="INV-004",
            name="Grace Auma",
        ),
        _get_or_create_investor(
            db,
            tenant_id=tenant.id,
            club_id=beta.id,
            investor_code="INV-005",
            name="Peter Okello",
        ),
    ]

    for investor in alpha_investors:
        _ensure_investor_club_membership(db, tenant_id=tenant.id, investor_id=investor.id, club_id=alpha.id)
    for investor in beta_investors:
        _ensure_investor_club_membership(db, tenant_id=tenant.id, investor_id=investor.id, club_id=beta.id)

    period = _get_or_create_period(
        db,
        tenant_id=tenant.id,
        club_id=alpha.id,
        year=2026,
        month=1,
        status=PeriodStatus.review,
        opening_nav=Decimal("1050000000.00"),
    )

    openings = {
        alpha_investors[0].id: Decimal("450000000.00"),
        alpha_investors[1].id: Decimal("320000000.00"),
        alpha_investors[2].id: Decimal("280000000.00"),
    }
    for investor_id, opening in openings.items():
        _ensure_investor_position(
            db,
            period_id=period.id,
            investor_id=investor_id,
            opening_balance=opening,
        )

    _ensure_ledger_entry(
        db,
        tenant_id=tenant.id,
        club_id=alpha.id,
        period_id=period.id,
        investor_id=alpha_investors[0].id,
        entry_type=LedgerEntryType.contribution,
        category="capital",
        tx_date=date(2026, 1, 4),
        amount=Decimal("30000000.00"),
        description="Top-up contribution",
        note="Investor top-up",
        reference="CAP-2026-0001",
        created_by_user_id=accountant.id,
    )
    _ensure_ledger_entry(
        db,
        tenant_id=tenant.id,
        club_id=alpha.id,
        period_id=period.id,
        investor_id=alpha_investors[1].id,
        entry_type=LedgerEntryType.withdrawal,
        category="capital",
        tx_date=date(2026, 1, 11),
        amount=Decimal("10000000.00"),
        description="Partial redemption",
        note="Approved redemption",
        reference="WDL-2026-0001",
        created_by_user_id=accountant.id,
    )
    _ensure_ledger_entry(
        db,
        tenant_id=tenant.id,
        club_id=alpha.id,
        period_id=period.id,
        investor_id=None,
        entry_type=LedgerEntryType.income,
        category="yield",
        tx_date=date(2026, 1, 24),
        amount=Decimal("75000000.00"),
        description="Interest and dividend income",
        note="Monthly income",
        reference="INC-2026-0001",
        created_by_user_id=accountant.id,
    )
    _ensure_ledger_entry(
        db,
        tenant_id=tenant.id,
        club_id=alpha.id,
        period_id=period.id,
        investor_id=None,
        entry_type=LedgerEntryType.expense,
        category="opex",
        tx_date=date(2026, 1, 27),
        amount=Decimal("12000000.00"),
        description="Management and admin expenses",
        note="Monthly opex",
        reference="EXP-2026-0001",
        created_by_user_id=accountant.id,
    )

    db.flush()
    recalculate_period(db, period)
    db.commit()
