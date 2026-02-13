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

MIN_PERIODS_FOR_CHARTS = 6


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


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _initial_opening_map(
    investors: list[Investor],
    *,
    total_nav: Decimal,
) -> dict[int, Decimal]:
    if not investors:
        return {}

    total = money(total_nav)
    if len(investors) == 1:
        return {investors[0].id: total}
    if len(investors) == 2:
        first = money(total * Decimal("0.60"))
        second = money(total - first)
        return {investors[0].id: first, investors[1].id: second}
    if len(investors) == 3:
        first = money(total * Decimal("0.45"))
        second = money(total * Decimal("0.32"))
        third = money(total - first - second)
        return {
            investors[0].id: first,
            investors[1].id: second,
            investors[2].id: third,
        }

    per_investor = money(total / Decimal(len(investors)))
    opening_map = {investor.id: per_investor for investor in investors}
    assigned = money(sum(opening_map.values()))
    opening_map[investors[0].id] = money(opening_map[investors[0].id] + (total - assigned))
    return opening_map


def _closing_map_for_period(
    db: Session,
    *,
    period_id: int,
    investors: list[Investor],
    fallback: dict[int, Decimal],
) -> dict[int, Decimal]:
    rows = list(
        db.scalars(
            select(InvestorPosition).where(InvestorPosition.period_id == period_id)
        ).all()
    )
    if not rows:
        return fallback

    by_investor = {row.investor_id: money(row.closing_balance) for row in rows}
    return {
        investor.id: money(by_investor.get(investor.id, fallback.get(investor.id, money(0))))
        for investor in investors
    }


def _seed_period_entries(
    db: Session,
    *,
    tenant_id: int,
    club: Club,
    period: AccountingPeriod,
    investors: list[Investor],
    created_by_user_id: int,
    scale: Decimal,
) -> None:
    if not investors:
        return
    seed = period.year * 100 + period.month
    inv_a = investors[seed % len(investors)].id
    inv_b = investors[(seed + 1) % len(investors)].id
    inv_c = investors[(seed + 2) % len(investors)].id

    contribution_a = money((Decimal("12000000") + Decimal(seed % 7) * Decimal("1500000")) * scale)
    contribution_b = money((Decimal("6000000") + Decimal(seed % 5) * Decimal("1100000")) * scale)
    withdrawal = money((Decimal("3500000") + Decimal(seed % 4) * Decimal("900000")) * scale)
    income = money((Decimal("26000000") + Decimal(seed % 6) * Decimal("2800000")) * scale)
    expense = money((Decimal("5500000") + Decimal(seed % 5) * Decimal("750000")) * scale)

    period_key = f"{period.year:04d}{period.month:02d}"
    prefix = f"AUTO-{club.code}-{period_key}"
    _ensure_ledger_entry(
        db,
        tenant_id=tenant_id,
        club_id=club.id,
        period_id=period.id,
        investor_id=inv_a,
        entry_type=LedgerEntryType.contribution,
        category="capital",
        tx_date=date(period.year, period.month, 3),
        amount=contribution_a,
        description="Auto-seeded contribution",
        note="Synthetic chart history",
        reference=f"{prefix}-C1",
        created_by_user_id=created_by_user_id,
    )
    _ensure_ledger_entry(
        db,
        tenant_id=tenant_id,
        club_id=club.id,
        period_id=period.id,
        investor_id=inv_b,
        entry_type=LedgerEntryType.contribution,
        category="capital",
        tx_date=date(period.year, period.month, 8),
        amount=contribution_b,
        description="Auto-seeded contribution",
        note="Synthetic chart history",
        reference=f"{prefix}-C2",
        created_by_user_id=created_by_user_id,
    )
    _ensure_ledger_entry(
        db,
        tenant_id=tenant_id,
        club_id=club.id,
        period_id=period.id,
        investor_id=inv_c,
        entry_type=LedgerEntryType.withdrawal,
        category="capital",
        tx_date=date(period.year, period.month, 12),
        amount=withdrawal,
        description="Auto-seeded withdrawal",
        note="Synthetic chart history",
        reference=f"{prefix}-W1",
        created_by_user_id=created_by_user_id,
    )
    _ensure_ledger_entry(
        db,
        tenant_id=tenant_id,
        club_id=club.id,
        period_id=period.id,
        investor_id=None,
        entry_type=LedgerEntryType.income,
        category="yield",
        tx_date=date(period.year, period.month, 20),
        amount=income,
        description="Auto-seeded income",
        note="Synthetic chart history",
        reference=f"{prefix}-I1",
        created_by_user_id=created_by_user_id,
    )
    _ensure_ledger_entry(
        db,
        tenant_id=tenant_id,
        club_id=club.id,
        period_id=period.id,
        investor_id=None,
        entry_type=LedgerEntryType.expense,
        category="opex",
        tx_date=date(period.year, period.month, 25),
        amount=expense,
        description="Auto-seeded expense",
        note="Synthetic chart history",
        reference=f"{prefix}-E1",
        created_by_user_id=created_by_user_id,
    )


def _ensure_period_history(
    db: Session,
    *,
    tenant_id: int,
    club: Club,
    investors: list[Investor],
    created_by_user_id: int,
    initial_year: int,
    initial_month: int,
    initial_opening_map: dict[int, Decimal],
    scale: Decimal,
    min_periods: int = MIN_PERIODS_FOR_CHARTS,
) -> None:
    existing = list(
        db.scalars(
            select(AccountingPeriod)
            .where(AccountingPeriod.club_id == club.id)
            .order_by(AccountingPeriod.year.asc(), AccountingPeriod.month.asc())
        ).all()
    )
    if len(existing) >= min_periods:
        return

    if existing:
        latest = existing[-1]
        recalculate_period(db, latest)
        db.flush()
        opening_map = _closing_map_for_period(
            db,
            period_id=latest.id,
            investors=investors,
            fallback=initial_opening_map,
        )
        year, month = _next_month(latest.year, latest.month)
        count = len(existing)
    else:
        opening_map = initial_opening_map
        year, month = initial_year, initial_month
        count = 0

    while count < min_periods:
        opening_nav = money(sum(opening_map.values()))
        period = _get_or_create_period(
            db,
            tenant_id=tenant_id,
            club_id=club.id,
            year=year,
            month=month,
            status=PeriodStatus.draft,
            opening_nav=opening_nav,
        )
        for investor in investors:
            _ensure_investor_position(
                db,
                period_id=period.id,
                investor_id=investor.id,
                opening_balance=money(opening_map.get(investor.id, money(0))),
            )
        _seed_period_entries(
            db,
            tenant_id=tenant_id,
            club=club,
            period=period,
            investors=investors,
            created_by_user_id=created_by_user_id,
            scale=scale,
        )
        db.flush()
        recalculate_period(db, period)
        db.flush()

        opening_map = _closing_map_for_period(
            db,
            period_id=period.id,
            investors=investors,
            fallback=opening_map,
        )
        year, month = _next_month(year, month)
        count += 1


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

    alpha_default_openings = {
        alpha_investors[0].id: Decimal("450000000.00"),
        alpha_investors[1].id: Decimal("320000000.00"),
        alpha_investors[2].id: Decimal("280000000.00"),
    }
    beta_default_openings = _initial_opening_map(
        beta_investors,
        total_nav=Decimal("600000000.00"),
    )

    _ensure_period_history(
        db,
        tenant_id=tenant.id,
        club=alpha,
        investors=alpha_investors,
        created_by_user_id=accountant.id,
        initial_year=2025,
        initial_month=8,
        initial_opening_map=alpha_default_openings,
        scale=Decimal("1.00"),
    )
    _ensure_period_history(
        db,
        tenant_id=tenant.id,
        club=beta,
        investors=beta_investors,
        created_by_user_id=accountant.id,
        initial_year=2025,
        initial_month=10,
        initial_opening_map=beta_default_openings,
        scale=Decimal("0.70"),
    )
    db.commit()
