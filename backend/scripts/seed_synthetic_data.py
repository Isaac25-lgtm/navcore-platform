from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import and_, select

from app.db.session import SessionLocal
from app.models.club import Club
from app.models.enums import LedgerEntryType, PeriodStatus, RoleName
from app.models.investor import Investor
from app.models.ledger import LedgerEntry
from app.models.nav import InvestorBalance, NavSnapshot
from app.models.period import AccountingPeriod
from app.models.user import User
from app.services.accounting import (
    close_checklist,
    close_period,
    create_period_with_openings,
    recalculate_period,
    submit_for_review,
)
from app.services.nav_engine import compute_monthly_nav
from app.utils.decimal_math import money


def _period_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _admin_user(db) -> User:
    admin = db.scalar(select(User).where(User.role == RoleName.admin).limit(1))
    if admin is None:
        admin = db.scalar(select(User).limit(1))
    if admin is None:
        raise RuntimeError("No users available. Start backend once to seed base tenant/users.")
    return admin


def _ensure_period(
    db,
    *,
    club_id: int,
    year: int,
    month: int,
    opening_nav: Decimal | None = None,
    investor_openings: dict[int, Decimal] | None = None,
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
    period = create_period_with_openings(
        db,
        club_id=club_id,
        year=year,
        month=month,
        opening_nav=opening_nav,
        investor_openings=investor_openings,
    )
    db.flush()
    return period


def _add_entry_if_missing(
    db,
    *,
    tenant_id: int,
    club_id: int,
    period_id: int,
    reference: str,
    entry_type: LedgerEntryType,
    amount: Decimal,
    tx_date: date,
    description: str,
    category: str,
    created_by_user_id: int,
    investor_id: int | None = None,
    note: str | None = None,
) -> None:
    exists = db.scalar(
        select(LedgerEntry.id).where(
            LedgerEntry.club_id == club_id,
            LedgerEntry.period_id == period_id,
            LedgerEntry.reference == reference,
        )
    )
    if exists is not None:
        return
    db.add(
        LedgerEntry(
            tenant_id=tenant_id,
            club_id=club_id,
            period_id=period_id,
            investor_id=investor_id,
            entry_type=entry_type,
            amount=money(amount),
            category=category,
            tx_date=tx_date,
            description=description,
            note=note,
            reference=reference,
            created_by_user_id=created_by_user_id,
        )
    )


def _seed_period_entries(
    db,
    *,
    club: Club,
    period: AccountingPeriod,
    investors: list[Investor],
    created_by_user_id: int,
) -> None:
    if not investors:
        return
    if db.scalar(select(LedgerEntry.id).where(LedgerEntry.period_id == period.id).limit(1)) is not None:
        recalculate_period(db, period)
        return

    month_seed = period.year * 100 + period.month
    inv0 = investors[0].id
    inv1 = investors[1].id if len(investors) > 1 else investors[0].id
    inv2 = investors[2].id if len(investors) > 2 else investors[0].id

    contrib_a = money(18_000_000 + (month_seed % 5) * 2_500_000)
    contrib_b = money(7_000_000 + (month_seed % 3) * 1_750_000)
    withdrawal = money(4_000_000 + (month_seed % 4) * 1_500_000)
    income = money(42_000_000 + (month_seed % 6) * 5_250_000)
    expenses = money(8_500_000 + (month_seed % 5) * 1_250_000)

    prefix = f"SYN-{club.code}-{period.year}{period.month:02d}"
    _add_entry_if_missing(
        db,
        tenant_id=club.tenant_id,
        club_id=club.id,
        period_id=period.id,
        reference=f"{prefix}-C1",
        entry_type=LedgerEntryType.contribution,
        amount=contrib_a,
        tx_date=date(period.year, period.month, 4),
        description="Synthetic contribution",
        category="capital",
        created_by_user_id=created_by_user_id,
        investor_id=inv0,
        note="Synthetic dataset",
    )
    _add_entry_if_missing(
        db,
        tenant_id=club.tenant_id,
        club_id=club.id,
        period_id=period.id,
        reference=f"{prefix}-C2",
        entry_type=LedgerEntryType.contribution,
        amount=contrib_b,
        tx_date=date(period.year, period.month, 9),
        description="Synthetic top-up",
        category="capital",
        created_by_user_id=created_by_user_id,
        investor_id=inv1,
        note="Synthetic dataset",
    )
    _add_entry_if_missing(
        db,
        tenant_id=club.tenant_id,
        club_id=club.id,
        period_id=period.id,
        reference=f"{prefix}-W1",
        entry_type=LedgerEntryType.withdrawal,
        amount=withdrawal,
        tx_date=date(period.year, period.month, 13),
        description="Synthetic withdrawal",
        category="capital",
        created_by_user_id=created_by_user_id,
        investor_id=inv2,
        note="Synthetic dataset",
    )
    _add_entry_if_missing(
        db,
        tenant_id=club.tenant_id,
        club_id=club.id,
        period_id=period.id,
        reference=f"{prefix}-I1",
        entry_type=LedgerEntryType.income,
        amount=income,
        tx_date=date(period.year, period.month, 21),
        description="Synthetic monthly income",
        category="yield",
        created_by_user_id=created_by_user_id,
        note="Synthetic dataset",
    )
    _add_entry_if_missing(
        db,
        tenant_id=club.tenant_id,
        club_id=club.id,
        period_id=period.id,
        reference=f"{prefix}-E1",
        entry_type=LedgerEntryType.expense,
        amount=expenses,
        tx_date=date(period.year, period.month, 25),
        description="Synthetic monthly expenses",
        category="opex",
        created_by_user_id=created_by_user_id,
        note="Synthetic dataset",
    )

    db.flush()
    recalculate_period(db, period)


def _ensure_snapshot_and_close(
    db,
    *,
    period: AccountingPeriod,
    admin_user: User,
) -> None:
    if period.status == PeriodStatus.closed:
        return

    if period.status == PeriodStatus.draft:
        submit_for_review(period)

    recalculate_period(db, period)
    checklist = close_checklist(db, period)
    if not checklist.get("can_close", False):
        raise RuntimeError(f"Cannot close period {_period_key(period.year, period.month)} for club {period.club_id}.")

    snapshot = db.scalar(
        select(NavSnapshot).where(
            NavSnapshot.club_id == period.club_id,
            NavSnapshot.period_id == period.id,
        )
    )
    preview = compute_monthly_nav(period.club_id, period.id, db=db)
    if not preview.reconciliation.passed:
        raise RuntimeError(
            f"Reconciliation failed for period {_period_key(period.year, period.month)} with mismatch {preview.reconciliation.mismatch}."
        )

    if snapshot is None:
        snapshot = NavSnapshot(
            tenant_id=period.tenant_id,
            club_id=period.club_id,
            period_id=period.id,
            opening_nav=money(preview.opening_nav),
            contributions_total=money(preview.contributions_total),
            withdrawals_total=money(preview.withdrawals_total),
            income_total=money(preview.income_total),
            expenses_total=money(preview.expenses_total),
            closing_nav=money(preview.closing_nav),
        )
        db.add(snapshot)
        db.flush()
        for allocation in preview.allocations:
            db.add(
                InvestorBalance(
                    tenant_id=period.tenant_id,
                    club_id=period.club_id,
                    investor_id=allocation.investor_id,
                    period_id=period.id,
                    snapshot_id=snapshot.id,
                    opening_balance=allocation.opening_balance,
                    ownership_pct=allocation.ownership_pct,
                    income_alloc=allocation.income_share,
                    expense_alloc=allocation.expense_share,
                    net_alloc=allocation.net_alloc,
                    contributions=allocation.contributions,
                    withdrawals=allocation.withdrawals,
                    closing_balance=allocation.closing_balance,
                )
            )

    close_period(period, admin_user, checklist)
    db.flush()


def _active_investors(db, club_id: int) -> list[Investor]:
    return list(
        db.scalars(
            select(Investor)
            .where(and_(Investor.club_id == club_id, Investor.is_active.is_(True)))
            .order_by(Investor.id)
        ).all()
    )


def _seed_alpha(db, admin_user: User) -> None:
    alpha = db.scalar(select(Club).where(Club.code == "ALPHA"))
    if alpha is None:
        return
    investors = _active_investors(db, alpha.id)
    if not investors:
        return

    opening_map: dict[int, Decimal] = {}
    if len(investors) == 1:
        opening_map[investors[0].id] = money(900_000_000)
    elif len(investors) == 2:
        opening_map[investors[0].id] = money(540_000_000)
        opening_map[investors[1].id] = money(360_000_000)
    else:
        opening_map[investors[0].id] = money(405_000_000)
        opening_map[investors[1].id] = money(270_000_000)
        opening_map[investors[2].id] = money(225_000_000)
    opening_nav = money(sum(opening_map.values()))

    closed_months = [(2025, 8), (2025, 9), (2025, 10), (2025, 11), (2025, 12)]
    for index, (year, month) in enumerate(closed_months):
        period = _ensure_period(
            db,
            club_id=alpha.id,
            year=year,
            month=month,
            opening_nav=opening_nav if index == 0 else None,
            investor_openings=opening_map if index == 0 else None,
        )
        _seed_period_entries(
            db,
            club=alpha,
            period=period,
            investors=investors,
            created_by_user_id=admin_user.id,
        )
        _ensure_snapshot_and_close(db, period=period, admin_user=admin_user)

    jan_2026 = _ensure_period(db, club_id=alpha.id, year=2026, month=1, opening_nav=None, investor_openings=None)
    _seed_period_entries(
        db,
        club=alpha,
        period=jan_2026,
        investors=investors,
        created_by_user_id=admin_user.id,
    )
    if jan_2026.status == PeriodStatus.draft:
        submit_for_review(jan_2026)

    feb_2026 = _ensure_period(db, club_id=alpha.id, year=2026, month=2, opening_nav=None, investor_openings=None)
    _seed_period_entries(
        db,
        club=alpha,
        period=feb_2026,
        investors=investors,
        created_by_user_id=admin_user.id,
    )
    if feb_2026.status == PeriodStatus.closed:
        march_2026 = _ensure_period(db, club_id=alpha.id, year=2026, month=3, opening_nav=None, investor_openings=None)
        _seed_period_entries(
            db,
            club=alpha,
            period=march_2026,
            investors=investors,
            created_by_user_id=admin_user.id,
        )
        march_2026.status = PeriodStatus.draft
        recalculate_period(db, march_2026)
    else:
        feb_2026.status = PeriodStatus.draft
        recalculate_period(db, feb_2026)


def _seed_beta(db, admin_user: User) -> None:
    beta = db.scalar(select(Club).where(Club.code == "BETA"))
    if beta is None:
        return
    investors = _active_investors(db, beta.id)
    if not investors:
        return

    if len(investors) >= 2:
        opening_map = {
            investors[0].id: money(360_000_000),
            investors[1].id: money(240_000_000),
        }
    else:
        opening_map = {investors[0].id: money(600_000_000)}
    opening_nav = money(sum(opening_map.values()))

    closed_months = [(2025, 10), (2025, 11), (2025, 12)]
    for index, (year, month) in enumerate(closed_months):
        period = _ensure_period(
            db,
            club_id=beta.id,
            year=year,
            month=month,
            opening_nav=opening_nav if index == 0 else None,
            investor_openings=opening_map if index == 0 else None,
        )
        _seed_period_entries(
            db,
            club=beta,
            period=period,
            investors=investors,
            created_by_user_id=admin_user.id,
        )
        _ensure_snapshot_and_close(db, period=period, admin_user=admin_user)

    jan_2026 = _ensure_period(db, club_id=beta.id, year=2026, month=1, opening_nav=None, investor_openings=None)
    _seed_period_entries(
        db,
        club=beta,
        period=jan_2026,
        investors=investors,
        created_by_user_id=admin_user.id,
    )
    if jan_2026.status == PeriodStatus.closed:
        feb_2026 = _ensure_period(db, club_id=beta.id, year=2026, month=2, opening_nav=None, investor_openings=None)
        _seed_period_entries(
            db,
            club=beta,
            period=feb_2026,
            investors=investors,
            created_by_user_id=admin_user.id,
        )
        feb_2026.status = PeriodStatus.review
        recalculate_period(db, feb_2026)
    else:
        jan_2026.status = PeriodStatus.review
        recalculate_period(db, jan_2026)


def main() -> None:
    with SessionLocal() as db:
        admin_user = _admin_user(db)
        _seed_alpha(db, admin_user)
        _seed_beta(db, admin_user)
        db.commit()
        print("Synthetic data seeded successfully.")


if __name__ == "__main__":
    main()
