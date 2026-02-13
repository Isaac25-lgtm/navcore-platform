from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import median
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import LedgerEntryType, PeriodStatus
from app.models.investor import Investor
from app.models.ledger import LedgerEntry
from app.models.period import AccountingPeriod
from app.services.nav_engine import NavSnapshotPreview, compute_monthly_nav
from app.utils.decimal_math import money, pct


SEVERITY_WEIGHT = {"info": 1, "warn": 2, "critical": 3}


@dataclass(frozen=True)
class AnalyticsPayload:
    metrics: dict[str, Any]
    insights: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]
    integrity: dict[str, Any]
    charts: dict[str, list[dict[str, Any]]]


@dataclass(frozen=True)
class ScenarioProjection:
    points: list[dict[str, Any]]
    goal: dict[str, Any] | None


def _period_or_404(db: Session, club_id: int, period_id: int) -> AccountingPeriod:
    period = db.scalar(
        select(AccountingPeriod).where(
            AccountingPeriod.club_id == club_id,
            AccountingPeriod.id == period_id,
        )
    )
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found.")
    return period


def _period_key(period: AccountingPeriod) -> int:
    return period.year * 100 + period.month


def _period_yyyymm(period: AccountingPeriod) -> str:
    return f"{period.year:04d}{period.month:02d}"


def _safe_pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return pct(0)
    return pct((numerator / denominator) * Decimal("100"))


def _as_decimal(value: Any, *, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _totals_template() -> dict[str, Decimal]:
    return {
        "contributions": money(0),
        "withdrawals": money(0),
        "income": money(0),
        "expenses": money(0),
    }


def _apply_entry(totals: dict[str, Decimal], entry: LedgerEntry) -> None:
    amount = money(entry.amount)
    if entry.entry_type == LedgerEntryType.contribution:
        totals["contributions"] = money(totals["contributions"] + amount)
        return
    if entry.entry_type == LedgerEntryType.withdrawal:
        totals["withdrawals"] = money(totals["withdrawals"] + amount)
        return
    if entry.entry_type == LedgerEntryType.income:
        totals["income"] = money(totals["income"] + amount)
        return
    if entry.entry_type == LedgerEntryType.expense:
        totals["expenses"] = money(totals["expenses"] + amount)
        return
    if entry.entry_type != LedgerEntryType.adjustment:
        return

    if entry.investor_id is None:
        if amount >= 0:
            totals["income"] = money(totals["income"] + amount)
        else:
            totals["expenses"] = money(totals["expenses"] + abs(amount))
    else:
        if amount >= 0:
            totals["contributions"] = money(totals["contributions"] + amount)
        else:
            totals["withdrawals"] = money(totals["withdrawals"] + abs(amount))


def _aggregate_entries(entries: list[LedgerEntry]) -> dict[str, Decimal]:
    totals = _totals_template()
    for entry in entries:
        _apply_entry(totals, entry)
    return totals


def _history_periods(db: Session, club_id: int, period: AccountingPeriod) -> list[AccountingPeriod]:
    rows = list(
        db.scalars(
            select(AccountingPeriod)
            .where(
                AccountingPeriod.club_id == club_id,
                (AccountingPeriod.year * 100 + AccountingPeriod.month) <= _period_key(period),
            )
            .order_by(AccountingPeriod.year.asc(), AccountingPeriod.month.asc())
        ).all()
    )
    return rows[-36:] if len(rows) > 36 else rows


def _history_chart_rows(
    db: Session,
    *,
    club_id: int,
    period: AccountingPeriod,
) -> list[dict[str, Any]]:
    periods = _history_periods(db, club_id, period)
    if not periods:
        return []
    period_ids = [row.id for row in periods]
    entry_rows = list(
        db.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.period_id.in_(period_ids))
            .order_by(LedgerEntry.period_id.asc(), LedgerEntry.tx_date.asc(), LedgerEntry.id.asc())
        ).all()
    )
    totals_by_period: dict[int, dict[str, Decimal]] = {row.id: _totals_template() for row in periods}
    for entry in entry_rows:
        bucket = totals_by_period.get(entry.period_id)
        if bucket is None:
            continue
        _apply_entry(bucket, entry)

    rows: list[dict[str, Any]] = []
    for row in periods:
        totals = totals_by_period.get(row.id, _totals_template())
        opening_nav = money(row.opening_nav)
        closing_nav = money(
            opening_nav
            + totals["contributions"]
            - totals["withdrawals"]
            + totals["income"]
            - totals["expenses"]
        )
        rows.append(
            {
                "period_id": row.id,
                "period": f"{row.year:04d}-{row.month:02d}",
                "status": row.status.value,
                "opening_nav": opening_nav,
                "contributions": money(totals["contributions"]),
                "withdrawals": money(totals["withdrawals"]),
                "income": money(totals["income"]),
                "expenses": money(totals["expenses"]),
                "net_result": money(totals["income"] - totals["expenses"]),
                "closing_nav": closing_nav,
                "return_pct": _safe_pct(closing_nav - opening_nav, opening_nav),
            }
        )
    return rows


def _dormant_and_churn_metrics(
    db: Session,
    *,
    club_id: int,
    history_rows: list[dict[str, Any]],
    preview: NavSnapshotPreview,
) -> tuple[int, int]:
    if not history_rows:
        return 0, 0
    recent_ids = [int(row["period_id"]) for row in history_rows[-3:]]
    if not recent_ids:
        return 0, 0

    entries = list(
        db.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.club_id == club_id,
                LedgerEntry.period_id.in_(recent_ids),
                LedgerEntry.investor_id.is_not(None),
                LedgerEntry.entry_type.in_(
                    [LedgerEntryType.contribution, LedgerEntryType.withdrawal, LedgerEntryType.adjustment]
                ),
            )
        ).all()
    )
    by_investor: dict[int, dict[str, Decimal]] = {}
    for entry in entries:
        if entry.investor_id is None:
            continue
        row = by_investor.setdefault(entry.investor_id, {"contributions": money(0), "withdrawals": money(0)})
        amount = money(entry.amount)
        if entry.entry_type == LedgerEntryType.contribution:
            row["contributions"] = money(row["contributions"] + amount)
        elif entry.entry_type == LedgerEntryType.withdrawal:
            row["withdrawals"] = money(row["withdrawals"] + amount)
        elif entry.entry_type == LedgerEntryType.adjustment:
            if amount >= 0:
                row["contributions"] = money(row["contributions"] + amount)
            else:
                row["withdrawals"] = money(row["withdrawals"] + abs(amount))

    investors = list(
        db.scalars(
            select(Investor.id).where(Investor.club_id == club_id, Investor.is_active.is_(True))
        ).all()
    )
    dormant_count = 0
    churn_risk_count = 0
    opening_by_investor = {row.investor_id: money(row.opening_balance) for row in preview.allocations}
    for investor_id in investors:
        flow = by_investor.get(investor_id)
        if flow is None:
            dormant_count += 1
            continue
        net = money(flow["contributions"] - flow["withdrawals"])
        opening = opening_by_investor.get(investor_id, money(0))
        if net < 0 and opening > 0 and abs(net) >= money(opening * Decimal("0.05")):
            churn_risk_count += 1
    return dormant_count, churn_risk_count


def _build_integrity(preview: NavSnapshotPreview) -> dict[str, Any]:
    mismatch = money(abs(preview.reconciliation.mismatch))
    reconciled = bool(preview.reconciliation.passed)
    stamp = "Reconciled ✅" if reconciled else f"Mismatch ❌ UGX {mismatch:,.2f}"
    return {
        "reconciled": reconciled,
        "stamp": stamp,
        "mismatch_ugx": mismatch,
        "reasons": list(preview.reconciliation.reasons),
    }


def _ranked(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(row: dict[str, Any]) -> tuple[int, Decimal]:
        severity = str(row.get("severity", "info"))
        weight = SEVERITY_WEIGHT.get(severity, 1)
        magnitude = _as_decimal(row.get("rank_magnitude"), default=Decimal("0"))
        return weight, magnitude

    ordered = sorted(items, key=key, reverse=True)
    for row in ordered:
        row.pop("rank_magnitude", None)
    return ordered


def _build_insights(
    *,
    club_id: int,
    period: AccountingPeriod,
    preview: NavSnapshotPreview,
    history_rows: list[dict[str, Any]],
    top3_share_pct: Decimal,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    yyyymm = _period_yyyymm(period)
    opening_nav = money(preview.opening_nav)
    nav_delta = money(preview.closing_nav - preview.opening_nav)
    component_rows = [
        ("contributions", money(preview.contributions_total), "Contributions"),
        ("withdrawals", money(-preview.withdrawals_total), "Withdrawals"),
        ("income", money(preview.income_total), "Income"),
        ("expenses", money(-preview.expenses_total), "Expenses"),
    ]
    for code, impact, label in sorted(component_rows, key=lambda item: abs(item[1]), reverse=True):
        if impact == 0:
            continue
        severity = "info"
        if nav_delta != 0 and abs(impact) >= abs(nav_delta):
            severity = "warn"
        if opening_nav > 0 and abs(impact) >= money(opening_nav * Decimal("0.25")):
            severity = "critical" if impact < 0 else "warn"
        direction = "increased" if impact > 0 else "reduced"
        rows.append(
            {
                "code": f"nav-driver-{code}",
                "severity": severity,
                "title": f"NAV driver: {label}",
                "description": f"{label} {direction} NAV by UGX {abs(impact):,.2f} this month.",
                "evidence": (
                    f"Opening NAV {preview.opening_nav:,.2f}, component impact {impact:,.2f}, "
                    f"closing NAV {preview.closing_nav:,.2f}."
                ),
                "numeric_evidence": {
                    "impact_ugx": impact,
                    "opening_nav": preview.opening_nav,
                    "closing_nav": preview.closing_nav,
                    "period_id": period.id,
                },
                "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/ledger?type={code.rstrip('s')}",
                "rank_magnitude": abs(impact),
            }
        )

    previous = history_rows[-2] if len(history_rows) >= 2 else None
    if previous is not None:
        prev_contrib = money(previous["contributions"])
        prev_withdraw = money(previous["withdrawals"])
        prev_income = money(previous["income"])
        prev_expenses = money(previous["expenses"])
        prev_opening = money(previous["opening_nav"])
        curr_contrib = money(preview.contributions_total)
        curr_withdraw = money(preview.withdrawals_total)
        curr_income = money(preview.income_total)
        curr_expenses = money(preview.expenses_total)

        if prev_contrib > 0 and curr_contrib >= money(prev_contrib * Decimal("1.50")):
            rows.append(
                {
                    "code": "contribution-spike",
                    "severity": "warn" if curr_contrib < money(prev_contrib * Decimal("2.50")) else "critical",
                    "title": "Contribution spike",
                    "description": "Contributions increased sharply versus prior month.",
                    "evidence": (
                        f"Current contributions UGX {curr_contrib:,.2f} vs previous UGX {prev_contrib:,.2f}."
                    ),
                    "numeric_evidence": {
                        "current_contributions": curr_contrib,
                        "previous_contributions": prev_contrib,
                        "change_pct": _safe_pct(curr_contrib - prev_contrib, prev_contrib),
                    },
                    "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/ledger?type=contribution",
                    "rank_magnitude": abs(curr_contrib - prev_contrib),
                }
            )
        if prev_withdraw > 0 and curr_withdraw >= money(prev_withdraw * Decimal("1.50")):
            rows.append(
                {
                    "code": "withdrawal-spike",
                    "severity": "warn" if curr_withdraw < money(prev_withdraw * Decimal("2.00")) else "critical",
                    "title": "Withdrawal spike",
                    "description": "Withdrawals increased sharply versus prior month.",
                    "evidence": (
                        f"Current withdrawals UGX {curr_withdraw:,.2f} vs previous UGX {prev_withdraw:,.2f}."
                    ),
                    "numeric_evidence": {
                        "current_withdrawals": curr_withdraw,
                        "previous_withdrawals": prev_withdraw,
                        "change_pct": _safe_pct(curr_withdraw - prev_withdraw, prev_withdraw),
                    },
                    "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/ledger?type=withdrawal",
                    "rank_magnitude": abs(curr_withdraw - prev_withdraw),
                }
            )

        if prev_income > 0:
            change_pct = _safe_pct(curr_income - prev_income, prev_income)
            if abs(change_pct) >= Decimal("20"):
                rows.append(
                    {
                        "code": "income-shift",
                        "severity": "warn" if change_pct < 0 else "info",
                        "title": "Income shift",
                        "description": "Income changed materially from prior month.",
                        "evidence": f"Income moved from UGX {prev_income:,.2f} to UGX {curr_income:,.2f}.",
                        "numeric_evidence": {
                            "current_income": curr_income,
                            "previous_income": prev_income,
                            "change_pct": change_pct,
                        },
                        "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/ledger?type=income",
                        "rank_magnitude": abs(curr_income - prev_income),
                    }
                )

        current_expense_ratio = _safe_pct(curr_expenses, opening_nav if opening_nav > 0 else money(1))
        previous_expense_ratio = _safe_pct(prev_expenses, prev_opening if prev_opening > 0 else money(1))
        ratio_diff = money(current_expense_ratio - previous_expense_ratio)
        if abs(ratio_diff) >= Decimal("0.40"):
            rows.append(
                {
                    "code": "expense-ratio-shift",
                    "severity": "warn" if ratio_diff > 0 else "info",
                    "title": "Expense ratio change",
                    "description": "Expense ratio changed versus prior month.",
                    "evidence": (
                        f"Expense ratio {current_expense_ratio:.4f}% vs {previous_expense_ratio:.4f}% prior month."
                    ),
                    "numeric_evidence": {
                        "current_expense_ratio_pct": current_expense_ratio,
                        "previous_expense_ratio_pct": previous_expense_ratio,
                        "delta_pct_points": ratio_diff,
                    },
                    "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/ledger?type=expense",
                    "rank_magnitude": abs(ratio_diff),
                }
            )

        prev_net_inflow = money(prev_contrib - prev_withdraw)
        current_net_inflow = money(curr_contrib - curr_withdraw)
        if prev_net_inflow >= 0 and current_net_inflow < 0:
            rows.append(
                {
                    "code": "negative-net-inflow",
                    "severity": "critical",
                    "title": "Net inflow turned negative",
                    "description": "Contributions no longer cover withdrawals this month.",
                    "evidence": (
                        f"Net inflow moved from UGX {prev_net_inflow:,.2f} to UGX {current_net_inflow:,.2f}."
                    ),
                    "numeric_evidence": {
                        "current_net_inflow": current_net_inflow,
                        "previous_net_inflow": prev_net_inflow,
                    },
                    "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/ledger?type=contribution",
                    "rank_magnitude": abs(current_net_inflow - prev_net_inflow),
                }
            )

    if top3_share_pct >= Decimal("80"):
        severity = "critical"
    elif top3_share_pct >= Decimal("65"):
        severity = "warn"
    else:
        severity = "info"
    if severity != "info":
        rows.append(
            {
                "code": "investor-concentration-risk",
                "severity": severity,
                "title": "Investor concentration risk",
                "description": "Top 3 investors hold a high share of club NAV.",
                "evidence": f"Top 3 investors represent {top3_share_pct:.4f}% of closing NAV.",
                "numeric_evidence": {"top3_share_pct": top3_share_pct, "closing_nav": preview.closing_nav},
                "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/investors",
                "rank_magnitude": top3_share_pct,
            }
        )

    if preview.reconciliation.mismatch != 0:
        rows.append(
            {
                "code": "allocation-drift-detected",
                "severity": "critical",
                "title": "Allocation drift detected",
                "description": "Investor balances do not reconcile exactly to closing NAV.",
                "evidence": (
                    f"Mismatch is UGX {abs(preview.reconciliation.mismatch):,.2f}. "
                    "Close month is blocked until exact reconciliation."
                ),
                "numeric_evidence": {
                    "mismatch_ugx": abs(preview.reconciliation.mismatch),
                    "closing_nav": preview.closing_nav,
                },
                "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/close",
                "rank_magnitude": abs(preview.reconciliation.mismatch),
            }
        )

    unusual = [
        row
        for row in preview.allocations
        if row.opening_balance > 0
        and abs(_safe_pct(row.net_alloc, row.opening_balance)) >= Decimal("15")
    ]
    if unusual:
        top = sorted(
            unusual,
            key=lambda row: abs(_safe_pct(row.net_alloc, row.opening_balance)),
            reverse=True,
        )[0]
        return_pct_value = _safe_pct(top.net_alloc, top.opening_balance)
        rows.append(
            {
                "code": "unusual-investor-return",
                "severity": "warn",
                "title": "Unusual investor return",
                "description": "One investor has an outlier net allocation versus opening balance.",
                "evidence": (
                    f"Investor {top.investor_id} net allocation UGX {top.net_alloc:,.2f} "
                    f"on opening UGX {top.opening_balance:,.2f} ({return_pct_value:.4f}%)."
                ),
                "numeric_evidence": {
                    "investor_id": top.investor_id,
                    "net_alloc": top.net_alloc,
                    "opening_balance": top.opening_balance,
                    "return_pct": return_pct_value,
                },
                "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/investors",
                "rank_magnitude": abs(return_pct_value),
            }
        )

    return _ranked(rows)


def _build_anomalies(
    *,
    club_id: int,
    period: AccountingPeriod,
    preview: NavSnapshotPreview,
    entries: list[LedgerEntry],
    outlier_threshold_pct: Decimal,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    yyyymm = _period_yyyymm(period)
    opening_nav = money(preview.opening_nav if preview.opening_nav > 0 else Decimal("1"))
    absolute_threshold = money(opening_nav * (outlier_threshold_pct / Decimal("100")))

    duplicate_map: dict[tuple[str, Decimal, str, str], list[LedgerEntry]] = {}
    for entry in entries:
        key = (
            entry.entry_type.value,
            money(entry.amount),
            entry.tx_date.isoformat(),
            (entry.reference or "").strip().lower(),
        )
        duplicate_map.setdefault(key, []).append(entry)

    for key, dupes in duplicate_map.items():
        if len(dupes) < 2:
            continue
        rows.append(
            {
                "code": "duplicate-transaction",
                "severity": "warn",
                "title": "Duplicate transaction candidate",
                "message": "Multiple transactions have identical type, amount, date, and reference.",
                "evidence": (
                    f"{len(dupes)} rows share type={key[0]}, amount={key[1]}, date={key[2]}, reference={key[3] or '-'}."
                ),
                "numeric_evidence": {
                    "duplicate_count": len(dupes),
                    "amount": key[1],
                    "entry_ids": ",".join(str(row.id) for row in dupes),
                },
                "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/ledger",
                "rank_magnitude": Decimal(len(dupes)),
            }
        )

    expense_or_withdraw = [
        row
        for row in entries
        if row.entry_type in {LedgerEntryType.expense, LedgerEntryType.withdrawal}
    ]
    if expense_or_withdraw:
        sample = [money(row.amount) for row in expense_or_withdraw]
        baseline = money(Decimal(str(median(sample))))
        threshold = max(absolute_threshold, money(baseline * Decimal("3")))
        outliers = [row for row in expense_or_withdraw if money(row.amount) > threshold]
        for row in outliers[:5]:
            rows.append(
                {
                    "code": "outlier-cash-out",
                    "severity": "warn" if money(row.amount) < money(threshold * Decimal("1.8")) else "critical",
                    "title": "Outlier cash-out entry",
                    "message": "Expense/withdrawal exceeds configured outlier threshold.",
                    "evidence": (
                        f"Entry {row.id} amount UGX {money(row.amount):,.2f} exceeds threshold UGX {threshold:,.2f}."
                    ),
                    "numeric_evidence": {
                        "entry_id": row.id,
                        "amount": money(row.amount),
                        "threshold": threshold,
                        "threshold_pct_opening_nav": outlier_threshold_pct,
                    },
                    "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/ledger?type={row.entry_type.value}",
                    "rank_magnitude": money(row.amount),
                }
            )

    month_start = date(period.year, period.month, 1)
    backdated = [row for row in entries if row.tx_date < month_start]
    if backdated:
        rows.append(
            {
                "code": "backdated-entries",
                "severity": "warn" if period.status == PeriodStatus.draft else "critical",
                "title": "Backdated transaction warning",
                "message": "Entries exist before the selected period start date.",
                "evidence": (
                    f"{len(backdated)} entries are dated before {month_start.isoformat()}. "
                    "Backdated entries are allowed only in draft with explicit review."
                ),
                "numeric_evidence": {
                    "count": len(backdated),
                    "period_start": month_start.isoformat(),
                },
                "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/ledger",
                "rank_magnitude": Decimal(len(backdated)),
            }
        )

    if preview.reconciliation.mismatch != 0:
        rows.append(
            {
                "code": "reconciliation-mismatch",
                "severity": "critical",
                "title": "Rounding/reconciliation drift",
                "message": "Investor total does not equal club closing NAV.",
                "evidence": f"Mismatch UGX {abs(preview.reconciliation.mismatch):,.2f}.",
                "numeric_evidence": {
                    "mismatch_ugx": abs(preview.reconciliation.mismatch),
                    "closing_nav": preview.closing_nav,
                },
                "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/close",
                "rank_magnitude": abs(preview.reconciliation.mismatch),
            }
        )

    incomplete = [
        row
        for row in entries
        if not (row.category or "").strip() or not (row.description or "").strip()
    ]
    if incomplete:
        rows.append(
            {
                "code": "incomplete-posting",
                "severity": "warn",
                "title": "Incomplete transaction posting",
                "message": "Some transactions are missing category or description.",
                "evidence": f"{len(incomplete)} entries require completion for audit traceability.",
                "numeric_evidence": {
                    "count": len(incomplete),
                    "entry_ids": ",".join(str(row.id) for row in incomplete[:10]),
                },
                "drilldown_path": f"/clubs/{club_id}/periods/{yyyymm}/ledger",
                "rank_magnitude": Decimal(len(incomplete)),
            }
        )

    return _ranked(rows)


def generate_metrics(
    db: Session,
    club_id: int,
    period_id: int,
    *,
    outlier_threshold_pct: Decimal = Decimal("5"),
) -> AnalyticsPayload:
    if outlier_threshold_pct <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="outlier_threshold_pct must be > 0.")
    period = _period_or_404(db, club_id, period_id)
    preview = compute_monthly_nav(club_id, period_id, db=db)
    entries = list(
        db.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.club_id == club_id, LedgerEntry.period_id == period_id)
            .order_by(LedgerEntry.tx_date.asc(), LedgerEntry.id.asc())
        ).all()
    )
    history_rows = _history_chart_rows(db, club_id=club_id, period=period)
    previous = history_rows[-2] if len(history_rows) >= 2 else None
    previous_closing = money(previous["closing_nav"]) if previous else money(0)
    net_inflow = money(preview.contributions_total - preview.withdrawals_total)
    expense_ratio_pct = _safe_pct(preview.expenses_total, preview.opening_nav if preview.opening_nav > 0 else money(1))
    top_allocations = sorted(preview.allocations, key=lambda row: row.closing_balance, reverse=True)
    top3_total = money(sum(row.closing_balance for row in top_allocations[:3]))
    top3_share_pct = _safe_pct(top3_total, preview.closing_nav if preview.closing_nav > 0 else money(1))
    aum_growth_rate_pct = _safe_pct(preview.closing_nav - previous_closing, previous_closing if previous_closing > 0 else money(1))
    recent_inflows = [money(row["contributions"]) - money(row["withdrawals"]) for row in history_rows[-3:]]
    inflow_3m_avg = money(sum(recent_inflows) / Decimal(len(recent_inflows))) if recent_inflows else money(0)

    dormant_investors, churn_risk = _dormant_and_churn_metrics(
        db,
        club_id=club_id,
        history_rows=history_rows,
        preview=preview,
    )

    metrics = {
        "opening_nav": money(preview.opening_nav),
        "closing_nav": money(preview.closing_nav),
        "contributions": money(preview.contributions_total),
        "withdrawals": money(preview.withdrawals_total),
        "income": money(preview.income_total),
        "expenses": money(preview.expenses_total),
        "net_result": money(preview.income_total - preview.expenses_total),
        "net_inflow": net_inflow,
        "expense_ratio_pct": expense_ratio_pct,
        "reconciled": bool(preview.reconciliation.passed),
        "mismatch": money(preview.reconciliation.mismatch),
        "top3_share_pct": top3_share_pct,
        "aum_growth_rate_pct": aum_growth_rate_pct,
        "inflow_3m_avg": inflow_3m_avg,
        "dormant_investors": dormant_investors,
        "churn_risk_flags": churn_risk,
        "return_decomposition": {
            "cashflows": money(preview.contributions_total - preview.withdrawals_total),
            "income": money(preview.income_total),
            "expenses": money(preview.expenses_total),
            "net_result": money(preview.income_total - preview.expenses_total),
        },
    }

    insights = _build_insights(
        club_id=club_id,
        period=period,
        preview=preview,
        history_rows=history_rows,
        top3_share_pct=top3_share_pct,
    )
    anomalies = _build_anomalies(
        club_id=club_id,
        period=period,
        preview=preview,
        entries=entries,
        outlier_threshold_pct=outlier_threshold_pct,
    )
    integrity = _build_integrity(preview)

    charts = {
        "nav_curve": history_rows,
        "return_decomposition": [
            {
                "cashflows": metrics["return_decomposition"]["cashflows"],
                "income": metrics["return_decomposition"]["income"],
                "expenses": metrics["return_decomposition"]["expenses"],
                "net_result": metrics["return_decomposition"]["net_result"],
            }
        ],
        "concentration": [
            {
                "investor_id": row.investor_id,
                "closing_balance": money(row.closing_balance),
                "ownership_pct": row.ownership_pct,
            }
            for row in top_allocations[:10]
        ],
        "allocation_explainability": [
            {
                "investor_id": row.investor_id,
                "opening_balance": money(row.opening_balance),
                "ownership_pct": row.ownership_pct,
                "income_share": money(row.income_share),
                "expense_share": money(row.expense_share),
                "net_alloc": money(row.net_alloc),
                "contributions": money(row.contributions),
                "withdrawals": money(row.withdrawals),
                "closing_balance": money(row.closing_balance),
            }
            for row in preview.allocations
        ],
    }

    return AnalyticsPayload(
        metrics=metrics,
        insights=insights,
        anomalies=anomalies,
        integrity=integrity,
        charts=charts,
    )


def _projection_step(
    nav: Decimal,
    *,
    monthly_contribution: Decimal,
    monthly_withdrawal: Decimal,
    monthly_yield_pct: Decimal,
    monthly_expense_pct: Decimal,
) -> Decimal:
    growth = money(nav * (monthly_yield_pct / Decimal("100")))
    costs = money(nav * (monthly_expense_pct / Decimal("100")))
    return money(nav + monthly_contribution - monthly_withdrawal + growth - costs)


def _months_between(current_year: int, current_month: int, target_year: int, target_month: int) -> int:
    return (target_year - current_year) * 12 + (target_month - current_month)


def _required_contribution_to_goal(
    *,
    current_nav: Decimal,
    target_amount: Decimal,
    months: int,
    monthly_net_yield_pct: Decimal,
) -> Decimal:
    if months <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Goal date must be in the future.")
    rate = monthly_net_yield_pct / Decimal("100")
    growth_factor = (Decimal("1") + rate) ** months
    future_without_contrib = money(current_nav * growth_factor)
    if target_amount <= future_without_contrib:
        return money(0)
    if rate == 0:
        return money((target_amount - future_without_contrib) / Decimal(months))
    annuity_factor = ((Decimal("1") + rate) ** months - Decimal("1")) / rate
    if annuity_factor <= 0:
        return money(0)
    return money((target_amount - future_without_contrib) / annuity_factor)


def build_scenario_projection(
    *,
    current_nav: Decimal,
    monthly_contribution: Decimal,
    monthly_withdrawal: Decimal,
    annual_yield_low_pct: Decimal,
    annual_yield_high_pct: Decimal,
    expense_rate_pct: Decimal,
    months: int,
    current_year: int | None = None,
    current_month: int | None = None,
    goal_target_amount: Decimal | None = None,
    goal_target_date: str | None = None,
) -> ScenarioProjection:
    nav = money(current_nav)
    contribution = money(monthly_contribution)
    withdrawal = money(monthly_withdrawal)
    low = Decimal(str(annual_yield_low_pct))
    high = Decimal(str(annual_yield_high_pct))
    annual_expense = Decimal(str(expense_rate_pct))

    if contribution < 0 or withdrawal < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Monthly contribution/withdrawal must be >= 0.")
    if low < 0 or high < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Yield range must be >= 0.")
    if high < low:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="annual_yield_high_pct must be >= annual_yield_low_pct.")
    if annual_expense < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="expense_rate_pct must be >= 0.")
    if months < 12 or months > 36:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="months must be between 12 and 36.")

    low_monthly = low / Decimal("12")
    high_monthly = high / Decimal("12")
    base_monthly = (low_monthly + high_monthly) / Decimal("2")
    monthly_expense = annual_expense / Decimal("12")

    base_nav = nav
    best_nav = nav
    worst_nav = nav
    rows: list[dict[str, Any]] = []
    for index in range(1, months + 1):
        base_nav = _projection_step(
            base_nav,
            monthly_contribution=contribution,
            monthly_withdrawal=withdrawal,
            monthly_yield_pct=base_monthly,
            monthly_expense_pct=monthly_expense,
        )
        best_nav = _projection_step(
            best_nav,
            monthly_contribution=contribution,
            monthly_withdrawal=withdrawal,
            monthly_yield_pct=high_monthly,
            monthly_expense_pct=monthly_expense,
        )
        worst_nav = _projection_step(
            worst_nav,
            monthly_contribution=contribution,
            monthly_withdrawal=withdrawal,
            monthly_yield_pct=low_monthly,
            monthly_expense_pct=monthly_expense,
        )
        rows.append(
            {
                "month_index": index,
                "assumption": {
                    "monthly_contribution": contribution,
                    "monthly_withdrawal": withdrawal,
                    "monthly_yield_base_pct": pct(base_monthly),
                    "monthly_expense_pct": pct(monthly_expense),
                },
                "base_nav": money(base_nav),
                "best_nav": money(best_nav),
                "worst_nav": money(worst_nav),
                "low_band_nav": money(worst_nav),
                "high_band_nav": money(best_nav),
            }
        )

    goal: dict[str, Any] | None = None
    if goal_target_amount is not None and goal_target_date:
        if current_year is None or current_month is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current period date is required for goal projection.")
        try:
            year_text, month_text = goal_target_date.split("-")
            target_year = int(year_text)
            target_month = int(month_text)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="goal_target_date must be YYYY-MM.") from exc
        if target_month < 1 or target_month > 12:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="goal_target_date month must be 01..12.")
        goal_months = _months_between(current_year, current_month, target_year, target_month)
        target_amount = money(goal_target_amount)
        required = _required_contribution_to_goal(
            current_nav=nav,
            target_amount=target_amount,
            months=goal_months,
            monthly_net_yield_pct=base_monthly - monthly_expense,
        )
        goal = {
            "target_amount": target_amount,
            "target_date": f"{target_year:04d}-{target_month:02d}",
            "required_monthly_contribution": required,
            "months_to_goal": goal_months,
        }

    return ScenarioProjection(points=rows, goal=goal)


def _linear_regression(series: list[Decimal]) -> tuple[Decimal, Decimal]:
    n = len(series)
    if n == 0:
        return Decimal("0"), Decimal("0")
    if n == 1:
        return Decimal("0"), money(series[0])
    x_sum = Decimal(sum(range(n)))
    y_sum = Decimal(sum(series))
    xx_sum = Decimal(sum(index * index for index in range(n)))
    xy_sum = Decimal(sum(Decimal(index) * series[index] for index in range(n)))
    denom = Decimal(n) * xx_sum - x_sum * x_sum
    if denom == 0:
        return Decimal("0"), money(y_sum / Decimal(n))
    slope = (Decimal(n) * xy_sum - x_sum * y_sum) / denom
    intercept = (y_sum - slope * x_sum) / Decimal(n)
    return slope, intercept


def _std(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    mean = sum(values) / Decimal(len(values))
    variance = sum((value - mean) ** 2 for value in values) / Decimal(len(values))
    return variance.sqrt() if variance > 0 else Decimal("0")


def generate_forecast(
    db: Session,
    *,
    club_id: int,
    period_id: int,
    months: int = 12,
) -> dict[str, Any]:
    if months < 12 or months > 36:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="months must be between 12 and 36.")
    period = _period_or_404(db, club_id, period_id)
    history_rows = _history_chart_rows(db, club_id=club_id, period=period)
    series = [money(row["closing_nav"]) for row in history_rows]
    if not series:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No historical NAV data found for forecast.")

    slope, intercept = _linear_regression(series)
    rolling_window = min(6, len(series))
    rolling_seed = list(series[-rolling_window:])
    regression_residuals: list[Decimal] = []
    for idx, actual in enumerate(series):
        predicted = slope * Decimal(idx) + intercept
        regression_residuals.append(actual - predicted)
    error_band = _std(regression_residuals) * Decimal("1.28")
    if error_band < 0:
        error_band = Decimal("0")

    points: list[dict[str, Any]] = []
    working_rolling = list(rolling_seed)
    for step in range(1, months + 1):
        rolling_value = money(sum(working_rolling) / Decimal(len(working_rolling)))
        working_rolling.append(rolling_value)
        if len(working_rolling) > rolling_window:
            working_rolling.pop(0)

        index = len(series) + step - 1
        regression_value = money(slope * Decimal(index) + intercept)
        points.append(
            {
                "month_index": step,
                "rolling_forecast_nav": rolling_value,
                "regression_forecast_nav": regression_value,
                "arima_forecast_nav": None,
                "low_band_nav": money(min(rolling_value, regression_value) - error_band),
                "high_band_nav": money(max(rolling_value, regression_value) + error_band),
            }
        )

    return {
        "method": "rolling_average + linear_regression",
        "confidence_level": "approx 80%",
        "explanation": (
            "Forecast uses rolling averages and linear trend regression over historical closed/draft NAV values. "
            "ARIMA is optional and omitted when statistical prerequisites are insufficient."
        ),
        "points": points,
    }
