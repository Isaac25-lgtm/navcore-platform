from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.club import Club
from app.models.enums import LedgerEntryType, PeriodStatus
from app.models.investor import Investor
from app.models.ledger import LedgerEntry
from app.models.period import AccountingPeriod, InvestorPosition
from app.models.user import User
from app.services.allocation import AllocationSnapshotInput, InvestorOpeningInput, allocate_returns
from app.utils.decimal_math import money, pct


@dataclass
class PeriodTotals:
    contributions: Decimal
    withdrawals: Decimal
    income: Decimal
    expenses: Decimal
    net_result: Decimal
    closing_nav: Decimal
    investor_total: Decimal
    mismatch: Decimal


def get_period_or_404(db: Session, club_id: int, period_id: int) -> AccountingPeriod:
    period = db.scalar(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.club_id == club_id,
        )
    )
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found.")
    return period


def assert_period_writable(period: AccountingPeriod) -> None:
    if period.status == PeriodStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Period is closed and locked. Post adjustments in a later month.",
        )


def _empty_totals() -> PeriodTotals:
    return PeriodTotals(
        contributions=money(0),
        withdrawals=money(0),
        income=money(0),
        expenses=money(0),
        net_result=money(0),
        closing_nav=money(0),
        investor_total=money(0),
        mismatch=money(0),
    )


def recalculate_period(db: Session, period: AccountingPeriod) -> PeriodTotals:
    entries = list(
        db.scalars(
            select(LedgerEntry).where(LedgerEntry.period_id == period.id).order_by(LedgerEntry.id)
        ).all()
    )
    positions = list(
        db.scalars(
            select(InvestorPosition)
            .where(InvestorPosition.period_id == period.id)
            .order_by(InvestorPosition.investor_id)
        ).all()
    )

    totals = _empty_totals()
    investor_contrib: dict[int, Decimal] = {}
    investor_withdraw: dict[int, Decimal] = {}

    for entry in entries:
        amount = money(entry.amount)
        if entry.entry_type == LedgerEntryType.contribution:
            totals.contributions = money(totals.contributions + amount)
            if entry.investor_id is not None:
                investor_contrib[entry.investor_id] = money(
                    investor_contrib.get(entry.investor_id, money(0)) + amount
                )
        elif entry.entry_type == LedgerEntryType.withdrawal:
            totals.withdrawals = money(totals.withdrawals + amount)
            if entry.investor_id is not None:
                investor_withdraw[entry.investor_id] = money(
                    investor_withdraw.get(entry.investor_id, money(0)) + amount
                )
        elif entry.entry_type == LedgerEntryType.income:
            totals.income = money(totals.income + amount)
        elif entry.entry_type == LedgerEntryType.expense:
            totals.expenses = money(totals.expenses + amount)
        elif entry.entry_type == LedgerEntryType.adjustment:
            if entry.investor_id is None:
                if amount >= 0:
                    totals.income = money(totals.income + amount)
                else:
                    totals.expenses = money(totals.expenses + abs(amount))
            else:
                if amount >= 0:
                    totals.contributions = money(totals.contributions + amount)
                    investor_contrib[entry.investor_id] = money(
                        investor_contrib.get(entry.investor_id, money(0)) + amount
                    )
                else:
                    withdraw_amount = abs(amount)
                    totals.withdrawals = money(totals.withdrawals + withdraw_amount)
                    investor_withdraw[entry.investor_id] = money(
                        investor_withdraw.get(entry.investor_id, money(0)) + withdraw_amount
                    )

    opening_nav = money(period.opening_nav)
    totals.net_result = money(totals.income - totals.expenses)
    totals.closing_nav = money(
        opening_nav + totals.contributions - totals.withdrawals + totals.income - totals.expenses
    )

    if not positions:
        period.closing_nav = totals.closing_nav
        totals.investor_total = money(0)
        totals.mismatch = money(totals.investor_total - totals.closing_nav)
        period.reconciliation_diff = totals.mismatch
        return totals

    snapshot = AllocationSnapshotInput(
        opening_nav=opening_nav,
        contributions_total=totals.contributions,
        withdrawals_total=totals.withdrawals,
        income_total=totals.income,
        expenses_total=totals.expenses,
        closing_nav=totals.closing_nav,
    )
    opening_rows = [
        InvestorOpeningInput(
            investor_id=position.investor_id,
            opening_balance=money(position.opening_balance),
            contributions=money(investor_contrib.get(position.investor_id, money(0))),
            withdrawals=money(investor_withdraw.get(position.investor_id, money(0))),
        )
        for position in positions
    ]
    allocations = allocate_returns(snapshot, opening_rows)
    allocation_by_investor = {allocation.investor_id: allocation for allocation in allocations}
    for position in positions:
        row = allocation_by_investor.get(position.investor_id)
        if row is None:
            continue
        position.ownership_pct = row.ownership_pct
        position.income_alloc = row.income_share
        position.expense_alloc = row.expense_share
        position.net_allocation = row.net_alloc
        position.contributions = row.contributions
        position.withdrawals = row.withdrawals
        position.closing_balance = row.closing_balance

    totals.investor_total = money(sum(money(pos.closing_balance) for pos in positions))
    totals.mismatch = money(totals.investor_total - totals.closing_nav)
    period.closing_nav = totals.closing_nav
    period.reconciliation_diff = totals.mismatch
    return totals


def reconciliation_stamp(period: AccountingPeriod, investor_total: Decimal) -> dict[str, Decimal | str | bool]:
    mismatch = money(investor_total - money(period.closing_nav))
    reconciled = mismatch == money(0)
    stamp = "Reconciled ✅" if reconciled else f"Mismatch ❌ UGX {abs(mismatch):,.2f}"
    return {
        "reconciled": reconciled,
        "stamp": stamp,
        "mismatch_ugx": abs(mismatch),
        "club_closing_nav": money(period.closing_nav),
        "investor_total": money(investor_total),
    }


def close_checklist(db: Session, period: AccountingPeriod) -> dict[str, bool]:
    entries_exist = db.scalar(
        select(LedgerEntry.id).where(LedgerEntry.period_id == period.id).limit(1)
    )
    positions = list(
        db.scalars(select(InvestorPosition).where(InvestorPosition.period_id == period.id)).all()
    )
    investor_total = money(sum(money(pos.closing_balance) for pos in positions))
    stamp = reconciliation_stamp(period, investor_total)

    checklist = {
        "has_positions": len(positions) > 0,
        "has_ledger_entries": entries_exist is not None,
        "submitted_for_review": period.status in {PeriodStatus.review, PeriodStatus.closed},
        "reconciled": bool(stamp["reconciled"]),
        "not_already_closed": period.status != PeriodStatus.closed,
    }
    checklist["can_close"] = all(
        [
            checklist["has_positions"],
            checklist["has_ledger_entries"],
            checklist["submitted_for_review"],
            checklist["reconciled"],
            checklist["not_already_closed"],
        ]
    )
    return checklist


def submit_for_review(period: AccountingPeriod) -> None:
    assert_period_writable(period)
    if period.status == PeriodStatus.draft:
        period.status = PeriodStatus.review


def close_period(period: AccountingPeriod, user: User, checklist: dict[str, bool]) -> None:
    assert_period_writable(period)
    if not checklist.get("can_close", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Period cannot be closed until checklist passes and reconciliation is exact.",
        )
    period.status = PeriodStatus.closed
    now = datetime.now(timezone.utc)
    period.closed_at = now
    period.locked_at = now
    period.closed_by_user_id = user.id


def create_period_with_openings(
    db: Session,
    *,
    club_id: int,
    year: int,
    month: int,
    opening_nav: Decimal | None,
    investor_openings: dict[int, Decimal] | None,
) -> AccountingPeriod:
    existing = db.scalar(
        select(AccountingPeriod).where(
            and_(
                AccountingPeriod.club_id == club_id,
                AccountingPeriod.year == year,
                AccountingPeriod.month == month,
            )
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Period already exists for this club and month.",
        )

    club = db.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found.")

    investors = list(
        db.scalars(
            select(Investor).where(
                Investor.club_id == club_id,
                Investor.is_active.is_(True),
            )
        ).all()
    )
    investor_ids = {inv.id for inv in investors}

    previous = db.scalar(
        select(AccountingPeriod)
        .where(
            AccountingPeriod.club_id == club_id,
            AccountingPeriod.status == PeriodStatus.closed,
            (AccountingPeriod.year * 100 + AccountingPeriod.month) < (year * 100 + month),
        )
        .order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc())
    )

    opening_map: dict[int, Decimal] = {}
    opening_nav_final: Decimal

    if investor_openings:
        unknown_ids = set(investor_openings.keys()) - investor_ids
        if unknown_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown investor IDs in opening balances: {sorted(unknown_ids)}",
            )
        opening_map = {investor_id: money(value) for investor_id, value in investor_openings.items()}
        implied_nav = money(sum(opening_map.values()))
        if opening_nav is None:
            opening_nav_final = implied_nav
        else:
            opening_nav_final = money(opening_nav)
            if opening_nav_final != implied_nav:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Opening NAV must equal the sum of investor openings.",
                )
    elif previous is not None:
        previous_positions = list(
            db.scalars(select(InvestorPosition).where(InvestorPosition.period_id == previous.id)).all()
        )
        opening_map = {
            position.investor_id: money(position.closing_balance) for position in previous_positions
        }
        opening_nav_final = money(previous.closing_nav)
    elif opening_nav is not None:
        opening_nav_final = money(opening_nav)
        opening_map = {}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="First period requires opening NAV and investor openings, or a previous closed period.",
        )

    period = AccountingPeriod(
        tenant_id=club.tenant_id,
        club_id=club_id,
        year=year,
        month=month,
        year_month=f"{year:04d}-{month:02d}",
        status=PeriodStatus.draft,
        opening_nav=opening_nav_final,
        closing_nav=opening_nav_final,
        reconciliation_diff=money(0),
    )
    db.add(period)
    db.flush()

    for investor in investors:
        opening = opening_map.get(investor.id, money(0))
        db.add(
            InvestorPosition(
                period_id=period.id,
                investor_id=investor.id,
                opening_balance=opening,
                ownership_pct=pct(0),
                contributions=money(0),
                withdrawals=money(0),
                income_alloc=money(0),
                expense_alloc=money(0),
                net_allocation=money(0),
                closing_balance=opening,
            )
        )

    db.flush()
    recalculate_period(db, period)
    return period


def build_intelligent_insights(period: AccountingPeriod, totals: PeriodTotals) -> list[dict[str, str]]:
    insights: list[dict[str, str]] = []
    if totals.expenses > 0 and period.opening_nav > 0:
        expense_ratio = (money(totals.expenses) / money(period.opening_nav)) * Decimal("100")
        if expense_ratio > Decimal("2"):
            insights.append(
                {
                    "code": "expense-spike",
                    "level": "warning",
                    "title": "Expense anomaly",
                    "description": f"Expense ratio is elevated at {expense_ratio:.2f}%.",
                }
            )

    if abs(totals.mismatch) > Decimal("0"):
        insights.append(
            {
                "code": "reconciliation-mismatch",
                "level": "critical",
                "title": "Reconciliation mismatch",
                "description": f"Mismatch detected: UGX {abs(totals.mismatch):,.2f}.",
            }
        )

    if totals.net_result > 0:
        insights.append(
            {
                "code": "net-positive",
                "level": "info",
                "title": "Positive month",
                "description": f"Net result is positive at UGX {totals.net_result:,.2f}.",
            }
        )
    return insights
