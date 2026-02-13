from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.enums import LedgerEntryType
from app.models.ledger import LedgerEntry
from app.models.period import AccountingPeriod, InvestorPosition
from app.services.allocation import (
    AllocationSnapshotInput,
    InvestorAllocationResult,
    InvestorOpeningInput,
    allocate_returns,
)
from app.services.reconciliation import ReconciliationResult, validate
from app.utils.decimal_math import money


@dataclass(frozen=True)
class InvestorExplanation:
    investor_id: int
    ownership_pct: Decimal
    income_share: Decimal
    expense_share: Decimal
    net_alloc: Decimal
    closing_balance: Decimal


@dataclass(frozen=True)
class NavSnapshotPreview:
    club_id: int
    period_id: int
    opening_nav: Decimal
    contributions_total: Decimal
    withdrawals_total: Decimal
    income_total: Decimal
    expenses_total: Decimal
    closing_nav: Decimal
    allocations: list[InvestorAllocationResult]
    explainability: list[InvestorExplanation]
    reconciliation: ReconciliationResult


def _get_period_or_404(db: Session, club_id: int, period_id: int) -> AccountingPeriod:
    period = db.scalar(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.club_id == club_id,
        )
    )
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found.")
    return period


def _aggregate_totals(entries: list[LedgerEntry]) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    contributions = money(0)
    withdrawals = money(0)
    income = money(0)
    expenses = money(0)

    for entry in entries:
        amount = money(entry.amount)
        if entry.entry_type == LedgerEntryType.contribution:
            contributions = money(contributions + amount)
        elif entry.entry_type == LedgerEntryType.withdrawal:
            withdrawals = money(withdrawals + amount)
        elif entry.entry_type == LedgerEntryType.income:
            income = money(income + amount)
        elif entry.entry_type == LedgerEntryType.expense:
            expenses = money(expenses + amount)
        elif entry.entry_type == LedgerEntryType.adjustment:
            if entry.investor_id is None:
                if amount >= 0:
                    income = money(income + amount)
                else:
                    expenses = money(expenses + abs(amount))
            else:
                if amount >= 0:
                    contributions = money(contributions + amount)
                else:
                    withdrawals = money(withdrawals + abs(amount))
    return contributions, withdrawals, income, expenses


def _build_investor_openings(
    positions: list[InvestorPosition],
    entries: list[LedgerEntry],
) -> list[InvestorOpeningInput]:
    contrib_by_investor: dict[int, Decimal] = {}
    withdraw_by_investor: dict[int, Decimal] = {}

    for entry in entries:
        if entry.investor_id is None:
            continue
        amount = money(entry.amount)
        if entry.entry_type == LedgerEntryType.contribution:
            contrib_by_investor[entry.investor_id] = money(
                contrib_by_investor.get(entry.investor_id, money(0)) + amount
            )
        elif entry.entry_type == LedgerEntryType.withdrawal:
            withdraw_by_investor[entry.investor_id] = money(
                withdraw_by_investor.get(entry.investor_id, money(0)) + amount
            )
        elif entry.entry_type == LedgerEntryType.adjustment:
            if amount >= 0:
                contrib_by_investor[entry.investor_id] = money(
                    contrib_by_investor.get(entry.investor_id, money(0)) + amount
                )
            else:
                withdraw_by_investor[entry.investor_id] = money(
                    withdraw_by_investor.get(entry.investor_id, money(0)) + abs(amount)
                )

    rows: list[InvestorOpeningInput] = []
    for position in positions:
        rows.append(
            InvestorOpeningInput(
                investor_id=position.investor_id,
                opening_balance=money(position.opening_balance),
                contributions=money(contrib_by_investor.get(position.investor_id, money(0))),
                withdrawals=money(withdraw_by_investor.get(position.investor_id, money(0))),
            )
        )
    return rows


def compute_monthly_nav(
    club_id: int,
    period_id: int,
    *,
    db: Session | None = None,
) -> NavSnapshotPreview:
    manage_session = db is None
    session = db if db is not None else SessionLocal()
    try:
        period = _get_period_or_404(session, club_id, period_id)
        entries = list(
            session.scalars(
                select(LedgerEntry).where(LedgerEntry.period_id == period.id).order_by(LedgerEntry.id)
            ).all()
        )
        positions = list(
            session.scalars(
                select(InvestorPosition)
                .where(InvestorPosition.period_id == period.id)
                .order_by(InvestorPosition.investor_id)
            ).all()
        )

        opening_nav = money(period.opening_nav)
        contributions, withdrawals, income, expenses = _aggregate_totals(entries)
        closing_nav = money(opening_nav + contributions - withdrawals + income - expenses)

        snapshot = AllocationSnapshotInput(
            opening_nav=opening_nav,
            contributions_total=contributions,
            withdrawals_total=withdrawals,
            income_total=income,
            expenses_total=expenses,
            closing_nav=closing_nav,
        )
        openings = _build_investor_openings(positions, entries)
        allocations = allocate_returns(snapshot, openings)
        reconciliation = validate(closing_nav, allocations)

        explainability = [
            InvestorExplanation(
                investor_id=row.investor_id,
                ownership_pct=row.ownership_pct,
                income_share=row.income_share,
                expense_share=row.expense_share,
                net_alloc=row.net_alloc,
                closing_balance=row.closing_balance,
            )
            for row in allocations
        ]

        return NavSnapshotPreview(
            club_id=club_id,
            period_id=period_id,
            opening_nav=opening_nav,
            contributions_total=contributions,
            withdrawals_total=withdrawals,
            income_total=income,
            expenses_total=expenses,
            closing_nav=closing_nav,
            allocations=allocations,
            explainability=explainability,
            reconciliation=reconciliation,
        )
    finally:
        if manage_session:
            session.close()
