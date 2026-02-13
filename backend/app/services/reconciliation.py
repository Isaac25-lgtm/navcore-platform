from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.services.allocation import InvestorAllocationResult
from app.utils.decimal_math import money


@dataclass(frozen=True)
class ReconciliationResult:
    passed: bool
    mismatch: Decimal
    reasons: list[str]


def validate(
    snapshot_or_closing_nav: Decimal | object,
    investor_balances: list[InvestorAllocationResult],
) -> ReconciliationResult:
    if hasattr(snapshot_or_closing_nav, "closing_nav"):
        target = money(getattr(snapshot_or_closing_nav, "closing_nav"))
    else:
        target = money(snapshot_or_closing_nav)
    investor_total = money(sum(money(item.closing_balance) for item in investor_balances))
    mismatch = money(investor_total - target)

    reasons: list[str] = []
    if mismatch != money(0):
        reasons.append(
            f"Investor total UGX {investor_total:,.2f} differs from closing NAV UGX {target:,.2f} by UGX {abs(mismatch):,.2f}."
        )
    if any(item.ownership_pct < 0 for item in investor_balances):
        reasons.append("Negative ownership percentage detected.")
    if any(item.closing_balance < 0 for item in investor_balances):
        reasons.append("Negative investor closing balance detected.")

    return ReconciliationResult(
        passed=mismatch == money(0) and len(reasons) == 0,
        mismatch=mismatch,
        reasons=reasons,
    )
