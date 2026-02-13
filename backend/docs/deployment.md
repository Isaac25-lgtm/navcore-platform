# Deployment Notes

## Containerization (Docker)
Recommended container split:
- `api`: FastAPI + Uvicorn
- `db`: PostgreSQL
- optional `worker`: background report jobs (if async jobs are introduced)

Minimal API startup flow:
1. Apply DB migrations (`alembic upgrade head`).
2. Start FastAPI (`uvicorn app.main:app --host 0.0.0.0 --port 8000`).

## Required Environment Variables
- `DATABASE_URL`
- `CORS_ORIGINS`
- `API_PREFIX` (optional override)
- `REPORTS_DIR`
- `RATE_LIMIT_REQUESTS`
- `RATE_LIMIT_WINDOW_SECONDS`
- `AUTO_CREATE_SCHEMA` (disable in production, rely on Alembic)

## Secrets Management
- Store secrets in cloud secret manager or orchestrator secret store.
- Rotate DB credentials on schedule.
- Never embed secrets in container images or committed files.

## Monitoring and Logging
- Request/response timing is logged by middleware.
- Unhandled exceptions are logged with stack traces.
- Configure external aggregation (ELK/CloudWatch/Datadog/Sentry) in production.

## Job Failure Handling
- Report generation errors should be captured and retried by orchestration policy if moved to async workers.
- Keep audit trail for failed close/report attempts at API boundary.

