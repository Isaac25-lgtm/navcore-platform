# Backup and Migration Safety

## Backup Strategy
- Full PostgreSQL nightly backup.
- WAL/point-in-time recovery enabled for production.
- Keep at least:
  - 7 daily backups
  - 4 weekly backups
  - 3 monthly backups
- Periodically run restore drills in non-production.

## Migration Safety Checklist
Before migration:
1. Verify latest backup completed successfully.
2. Run migrations in staging against production-like data.
3. Validate Alembic head alignment (`alembic heads`, `alembic current`).

During migration:
1. Apply migrations in maintenance window where possible.
2. Monitor lock time and statement timeouts.
3. Run smoke checks on critical endpoints:
   - clubs list
   - period state/reconciliation
   - nav preview/close
   - report generation

After migration:
1. Validate counts and key reconciliation constraints.
2. Confirm `nav_snapshots` and `investor_balances` write paths.
3. Confirm audit logging and report storage are operational.

## Rollback Approach
- Prefer forward-fix migrations for data-bearing releases.
- For severe incidents:
  - roll back app deploy,
  - restore database to latest known good backup if required by impact assessment.

