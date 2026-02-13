# Multi-Club NAV Schema and API

## ERD-Style Relationships
- `tenants (1) -> (N) clubs`
- `tenants (1) -> (N) user_roles -> (N) users`
- `roles (1) -> (N) user_roles`
- `clubs (1) -> (N) investors`
- `clubs (1) -> (N) accounting_periods`
- `clubs (1) -> (N) club_memberships` (user or investor scoped membership)
- `accounting_periods (1) -> (N) ledger_entries`
- `accounting_periods (1) -> (N) investor_positions` (mutable draft/review positions)
- `accounting_periods (1) -> (1) nav_snapshots` (immutable close snapshot)
- `nav_snapshots (1) -> (N) investor_balances` (immutable close balances)
- `clubs/accounting_periods/users -> audit_logs`
- `clubs/accounting_periods/investors/users -> report_snapshots`

## SQLAlchemy Models
Implemented under `backend/app/models`:
- `tenant.py`: `Tenant`, `Role`, `UserRole`
- `user.py`: `User`
- `club.py`: `Club`, `ClubMembership`
- `investor.py`: `Investor`
- `period.py`: `AccountingPeriod`, `InvestorPosition`
- `ledger.py`: `LedgerEntry`
- `nav.py`: `NavSnapshot`, `InvestorBalance`
- `audit.py`: `AuditLog`
- `report.py`: `ReportSnapshot`

Money columns use `Numeric(24, 2)`; ownership uses `Numeric(12, 6)`.

## Alembic Migration Outline
- Initial baseline: `20260213_0001_initial.py`
- Multi-tenant + NAV immutable snapshot extension:
  - `20260213_0002_multitenant_nav_engine.py`
  - Adds `tenants`, `roles`, `user_roles`
  - Adds tenant scoping to core tables
  - Adds `year_month`, ledger metadata fields
  - Adds `income_alloc`, `expense_alloc`
  - Adds `nav_snapshots` and `investor_balances`

## FastAPI Endpoint Surface
- Clubs / investors / memberships:
  - `GET/POST/PATCH/DELETE /clubs...`
  - `GET/POST/PATCH/DELETE /clubs/{club_id}/investors...`
  - `GET/POST/DELETE /clubs/{club_id}/memberships...`
- Periods:
  - `GET/POST /clubs/{club_id}/periods`
  - `GET /clubs/{club_id}/periods/{period_id}/state`
  - `GET /clubs/{club_id}/periods/{period_id}/summary`
  - `PATCH /clubs/{club_id}/periods/{period_id}/status`
  - `POST /clubs/{club_id}/periods/{period_id}/submit-review`
  - `POST /clubs/{club_id}/periods/{period_id}/close`
- Transactions/Ledger:
  - `GET/POST/PATCH/DELETE /clubs/{club_id}/periods/{period_id}/ledger...`
  - `POST /clubs/{club_id}/periods/{period_id}/ledger/bulk-import`
  - alias endpoints under `/transactions`
- NAV/Reconciliation:
  - `POST /clubs/{club_id}/periods/{period_id}/nav/preview`
  - `GET /clubs/{club_id}/periods/{period_id}/nav/reconciliation`
  - `GET /clubs/{club_id}/periods/{period_id}/nav/snapshot`
  - `POST /clubs/{club_id}/periods/{period_id}/nav/close`
- Reports:
  - generate/download/list endpoints under `/clubs/{club_id}/periods/{period_id}/reports...`
- Analytics:
  - `/analytics/metrics`, `/analytics/insights`, `/analytics/charts/nav`, `/analytics/charts/flows`, `/analytics/scenario`
- Copilot:
  - `POST /copilot/chat`
- Audit:
  - `GET /clubs/{club_id}/audit`
- Exports:
  - `/clubs/{club_id}/periods/{period_id}/exports/csv|excel`

