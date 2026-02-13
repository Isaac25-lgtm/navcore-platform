from fastapi import APIRouter

from app.api.routes import analytics, audit, clubs, copilot, exports, health, ledger, nav, periods, reports, transactions


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(clubs.router)
api_router.include_router(ledger.router)
api_router.include_router(transactions.router)
api_router.include_router(periods.router)
api_router.include_router(nav.router)
api_router.include_router(reports.router)
api_router.include_router(exports.router)
api_router.include_router(analytics.router)
api_router.include_router(copilot.router)
api_router.include_router(audit.router)
