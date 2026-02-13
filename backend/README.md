# NAVFund Backend (FastAPI + Postgres)

## Run locally

1. Create and activate a virtualenv.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy env file:
   - `cp .env.example .env`
4. Run migrations:
   - `alembic upgrade head`
5. Start API:
   - `uvicorn app.main:app --reload --port 8000`

## Auth model (dev)

- The API reads `X-User-Id` header.
- If header is missing, it falls back to seeded `admin@navfund.com`.
- Seeded users are created automatically on first startup when schema is empty.

## Gemini Copilot

- Configure `GEMINI_API_KEY` and optional `GEMINI_MODEL` in `.env`.
- Default model is `gemini-3-flash` with automatic fallback to flash variants if unavailable.
- Copilot remains read-only and club+period scoped on the server.

## Guarantees implemented

- Club-level data isolation with RBAC.
- Strict decimal accounting and deterministic rounding.
- Period lock on close.
- Reconciliation stamp and close blocking on mismatch.
- Audit log for writes.
- PDF reports from closed snapshots with stored file metadata.

## Documentation

- `docs/schema_and_api.md`
- `docs/security.md`
- `docs/audit.md`
- `docs/deployment.md`
- `docs/backup_and_migration.md`
- `docs/coverage_report.md`
