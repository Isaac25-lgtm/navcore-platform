# Audit and Controls

## Audit Log Coverage
The platform writes `audit_logs` entries for:
- club create/update/delete
- investor create/update/deactivate
- membership create/delete
- period create/status changes/submit-review/close
- ledger create/update/delete
- report generation events

Each entry includes:
- actor (`actor_user_id`)
- tenant, club, period scope
- action, entity type, entity id
- before/after JSON state when applicable
- timestamp

## Reconciliation Controls
- NAV preview is deterministic and formula-based.
- Close month is blocked when:
  - checklist conditions are not satisfied
  - reconciliation mismatch is non-zero
- UI surfaces:
  - `Reconciled ✅`
  - `Mismatch ❌ UGX X`

## Snapshot Immutability
- Mutable draft/review data remains in `accounting_periods`, `investor_positions`, `ledger_entries`.
- Immutable closed records are copied to:
  - `nav_snapshots`
  - `investor_balances`
- Reports are generated from closed period context and stored as file snapshots with hashes.

## Regulator-Friendly Exports
- CSV export endpoint:
  - `/clubs/{club_id}/periods/{period_id}/exports/csv`
- Excel export endpoint:
  - `/clubs/{club_id}/periods/{period_id}/exports/excel`

