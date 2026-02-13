from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.utils.decimal_math import money, pct


@dataclass(frozen=True)
class AllocationSnapshotInput:
    opening_nav: Decimal
    contributions_total: Decimal
    withdrawals_total: Decimal
    income_total: Decimal
    expenses_total: Decimal
    closing_nav: Decimal


@dataclass(frozen=True)
class InvestorOpeningInput:
    investor_id: int
    opening_balance: Decimal
    contributions: Decimal = Decimal("0")
    withdrawals: Decimal = Decimal("0")


@dataclass(frozen=True)
class InvestorAllocationResult:
    investor_id: int
    opening_balance: Decimal
    ownership_pct: Decimal
    income_share: Decimal
    expense_share: Decimal
    net_alloc: Decimal
    contributions: Decimal
    withdrawals: Decimal
    closing_balance: Decimal


def _validate_non_negative(name: str, value: Decimal) -> None:
    if money(value) < money(0):
        raise ValueError(f"{name} must be >= 0.")


def _allocate_component(
    amount: Decimal,
    ownership_pct_values: list[Decimal],
) -> list[Decimal]:
    if not ownership_pct_values:
        return []

    total_amount = money(amount)
    running = money(0)
    shares: list[Decimal] = []
    for index, ownership_pct_value in enumerate(ownership_pct_values):
        if index < len(ownership_pct_values) - 1:
            share = money((total_amount * ownership_pct_value) / Decimal("100"))
            running = money(running + share)
        else:
            share = money(total_amount - running)
        shares.append(share)
    return shares


def allocate_returns(
    snapshot: AllocationSnapshotInput,
    investor_opening_balances: list[InvestorOpeningInput],
) -> list[InvestorAllocationResult]:
    opening_nav = money(snapshot.opening_nav)
    if opening_nav < money(0):
        raise ValueError("opening_nav must be >= 0.")

    _validate_non_negative("income_total", money(snapshot.income_total))
    _validate_non_negative("expenses_total", money(snapshot.expenses_total))
    _validate_non_negative("contributions_total", money(snapshot.contributions_total))
    _validate_non_negative("withdrawals_total", money(snapshot.withdrawals_total))

    if len(investor_opening_balances) == 0:
        return []

    for row in investor_opening_balances:
        _validate_non_negative("opening_balance", money(row.opening_balance))
        _validate_non_negative("contributions", money(row.contributions))
        _validate_non_negative("withdrawals", money(row.withdrawals))

    opening_sum = money(sum(money(row.opening_balance) for row in investor_opening_balances))
    if opening_nav == money(0) and opening_sum != money(0):
        raise ValueError("opening_nav cannot be 0 when investor openings are non-zero.")
    if opening_nav != money(0) and opening_sum != opening_nav:
        raise ValueError("Investor opening balances must sum exactly to opening_nav.")

    ownerships = [
        pct((money(row.opening_balance) / opening_nav) * Decimal("100")) if opening_nav != 0 else pct(0)
        for row in investor_opening_balances
    ]

    income_shares = _allocate_component(money(snapshot.income_total), ownerships)
    expense_shares = _allocate_component(money(snapshot.expenses_total), ownerships)

    rows: list[InvestorAllocationResult] = []
    for index, row in enumerate(investor_opening_balances):
        income_share = income_shares[index] if index < len(income_shares) else money(0)
        expense_share = expense_shares[index] if index < len(expense_shares) else money(0)
        net_alloc = money(income_share - expense_share)
        closing_balance = money(
            money(row.opening_balance)
            + net_alloc
            + money(row.contributions)
            - money(row.withdrawals)
        )
        rows.append(
            InvestorAllocationResult(
                investor_id=row.investor_id,
                opening_balance=money(row.opening_balance),
                ownership_pct=ownerships[index],
                income_share=income_share,
                expense_share=expense_share,
                net_alloc=net_alloc,
                contributions=money(row.contributions),
                withdrawals=money(row.withdrawals),
                closing_balance=closing_balance,
            )
        )

    return rows
