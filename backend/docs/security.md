# Security Model

## RBAC Roles
- `admin`: full access across tenant-scoped clubs.
- `fund_accountant`: operational write access (periods, ledger, close month, reports).
- `advisor`: operational support (create/update investors, memberships, draft/review operations).
- `investor`: read-only access to club/period data they are authorized for.

Legacy user roles (`manager`, `analyst`, `viewer`) are mapped to modern roles for backward compatibility.

## Tenant + Club Isolation
- Every core table includes `tenant_id`.
- `require_club_access(...)` enforces:
  - club exists,
  - club belongs to request tenant (`X-Tenant-Id`),
  - user has admin role or explicit club membership.
- Copilot and analytics are always club+period scoped.

## Immutable Close Rules
- Closed periods are immutable.
- Ledger writes are blocked on closed periods.
- Corrections must be posted as adjustments in a later open period.
- Close action writes immutable rows to:
  - `nav_snapshots`
  - `investor_balances`

## API Protection Controls
- Input validation through Pydantic schemas.
- Global rate limiting middleware (`429` on limit breach).
- Request logging and centralized error handling middleware.
- Server-side reconciliation checks block close when mismatch exists.

## Secrets and Operational Security
- Use environment variables for DB credentials and runtime config.
- Never commit `.env` or secrets to source control.
- Restrict CORS origins to known frontend domains in production.

