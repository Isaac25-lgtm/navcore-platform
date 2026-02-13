# PRD Mental Model

## Core Formula
`opening_nav + contributions - withdrawals + income - expenses = closing_nav`

## Ownership and Allocation
- Ownership is fixed at start-of-month:
  - `ownership_pct = investor_opening_balance / club_opening_nav`
- Income and expenses are allocated by ownership percentage.
- Investor closing:
  - `opening + net_alloc + contributions - withdrawals = closing`

## Reconciliation Invariant
- Sum of investor closing balances must equal club closing NAV exactly.
- If mismatch exists, close is blocked.

## Data Lifecycle
- Draft/Review: mutable operational data.
- Closed: immutable snapshot and balances.
- Post-close corrections: next-period adjustments only.

## Multi-Club Isolation
- Clubs do not mix money.
- Access and data are isolated by tenant and club.

