from decimal import Decimal

import pytest

from app.services.allocation import AllocationSnapshotInput, InvestorOpeningInput, allocate_returns
from app.services.reconciliation import validate
from app.utils.decimal_math import money


def test_allocate_multiple_investors_uneven_balances() -> None:
    snapshot = AllocationSnapshotInput(
        opening_nav=money("1000.00"),
        contributions_total=money("150.00"),
        withdrawals_total=money("20.00"),
        income_total=money("80.00"),
        expenses_total=money("30.00"),
        closing_nav=money("1180.00"),
    )
    openings = [
        InvestorOpeningInput(investor_id=1, opening_balance=money("600.00"), contributions=money("100.00")),
        InvestorOpeningInput(investor_id=2, opening_balance=money("300.00"), contributions=money("50.00")),
        InvestorOpeningInput(investor_id=3, opening_balance=money("100.00"), withdrawals=money("20.00")),
    ]
    rows = allocate_returns(snapshot, openings)
    assert len(rows) == 3
    rec = validate(snapshot.closing_nav, rows)
    assert rec.passed is True
    assert rec.mismatch == money(0)


def test_allocate_zero_contributions_only_income() -> None:
    snapshot = AllocationSnapshotInput(
        opening_nav=money("500.00"),
        contributions_total=money("0.00"),
        withdrawals_total=money("0.00"),
        income_total=money("50.00"),
        expenses_total=money("0.00"),
        closing_nav=money("550.00"),
    )
    openings = [
        InvestorOpeningInput(investor_id=10, opening_balance=money("250.00")),
        InvestorOpeningInput(investor_id=11, opening_balance=money("250.00")),
    ]
    rows = allocate_returns(snapshot, openings)
    assert rows[0].income_share == money("25.00")
    assert rows[1].income_share == money("25.00")
    assert validate(snapshot.closing_nav, rows).passed is True


def test_allocate_expenses_greater_than_income() -> None:
    snapshot = AllocationSnapshotInput(
        opening_nav=money("1000.00"),
        contributions_total=money("0.00"),
        withdrawals_total=money("0.00"),
        income_total=money("10.00"),
        expenses_total=money("40.00"),
        closing_nav=money("970.00"),
    )
    openings = [
        InvestorOpeningInput(investor_id=1, opening_balance=money("700.00")),
        InvestorOpeningInput(investor_id=2, opening_balance=money("300.00")),
    ]
    rows = allocate_returns(snapshot, openings)
    assert rows[0].net_alloc < 0
    assert rows[1].net_alloc < 0
    assert validate(snapshot.closing_nav, rows).passed is True


def test_rounding_edge_case_remainder_assignment_keeps_exact_reconciliation() -> None:
    snapshot = AllocationSnapshotInput(
        opening_nav=money("100.00"),
        contributions_total=money("0.00"),
        withdrawals_total=money("0.00"),
        income_total=money("0.01"),
        expenses_total=money("0.00"),
        closing_nav=money("100.01"),
    )
    openings = [
        InvestorOpeningInput(investor_id=1, opening_balance=money("33.33")),
        InvestorOpeningInput(investor_id=2, opening_balance=money("33.33")),
        InvestorOpeningInput(investor_id=3, opening_balance=money("33.34")),
    ]
    rows = allocate_returns(snapshot, openings)
    total_income = money(sum(row.income_share for row in rows))
    assert total_income == money("0.01")
    rec = validate(snapshot.closing_nav, rows)
    assert rec.passed is True
    assert rec.mismatch == money(0)


@pytest.mark.parametrize(
    "opening_nav, open_a, open_b",
    [
        (Decimal("-1"), Decimal("0"), Decimal("0")),
        (Decimal("10"), Decimal("-1"), Decimal("11")),
        (Decimal("10"), Decimal("6"), Decimal("5")),
    ],
)
def test_invalid_inputs_rejected(opening_nav: Decimal, open_a: Decimal, open_b: Decimal) -> None:
    snapshot = AllocationSnapshotInput(
        opening_nav=opening_nav,
        contributions_total=money("0"),
        withdrawals_total=money("0"),
        income_total=money("0"),
        expenses_total=money("0"),
        closing_nav=money("0"),
    )
    openings = [
        InvestorOpeningInput(investor_id=1, opening_balance=open_a),
        InvestorOpeningInput(investor_id=2, opening_balance=open_b),
    ]
    with pytest.raises(ValueError):
        allocate_returns(snapshot, openings)
