from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_club_access
from app.core.security import require_roles
from app.models.enums import RoleName
from app.models.nav import InvestorBalance, NavSnapshot
from app.models.user import User
from app.schemas.nav import CloseMonthResponse, InvestorExplainabilityOut, NavPreviewOut, NavSnapshotOut
from app.services.accounting import close_checklist, close_period, get_period_or_404
from app.services.audit import log_audit
from app.services.nav_engine import compute_monthly_nav
from app.utils.decimal_math import money


router = APIRouter(prefix="/clubs/{club_id}/periods/{period_id}/nav", tags=["nav"])


@router.post("/preview", response_model=NavPreviewOut)
def compute_nav_preview(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NavPreviewOut:
    require_club_access(db, current_user, club_id)
    preview = compute_monthly_nav(club_id, period_id, db=db)
    return NavPreviewOut(
        club_id=preview.club_id,
        period_id=preview.period_id,
        opening_nav=money(preview.opening_nav),
        contributions_total=money(preview.contributions_total),
        withdrawals_total=money(preview.withdrawals_total),
        income_total=money(preview.income_total),
        expenses_total=money(preview.expenses_total),
        closing_nav=money(preview.closing_nav),
        reconciled=preview.reconciliation.passed,
        mismatch=money(preview.reconciliation.mismatch),
        reasons=preview.reconciliation.reasons,
        explainability=[
            InvestorExplainabilityOut(
                investor_id=item.investor_id,
                ownership_pct=item.ownership_pct,
                income_share=item.income_share,
                expense_share=item.expense_share,
                net_alloc=item.net_alloc,
                closing_balance=item.closing_balance,
            )
            for item in preview.allocations
        ],
    )


@router.get("/snapshot", response_model=NavSnapshotOut)
def get_nav_snapshot(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NavSnapshotOut:
    require_club_access(db, current_user, club_id)
    snapshot = db.scalar(
        select(NavSnapshot).where(NavSnapshot.club_id == club_id, NavSnapshot.period_id == period_id)
    )
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No immutable snapshot found for this period.",
        )
    return NavSnapshotOut(
        id=snapshot.id,
        tenant_id=snapshot.tenant_id,
        club_id=snapshot.club_id,
        period_id=snapshot.period_id,
        opening_nav=snapshot.opening_nav,
        contributions_total=snapshot.contributions_total,
        withdrawals_total=snapshot.withdrawals_total,
        income_total=snapshot.income_total,
        expenses_total=snapshot.expenses_total,
        closing_nav=snapshot.closing_nav,
        created_at=snapshot.created_at,
    )


@router.get("/reconciliation")
def get_reconciliation(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    require_club_access(db, current_user, club_id)
    preview = compute_monthly_nav(club_id, period_id, db=db)
    return {
        "passed": preview.reconciliation.passed,
        "mismatch": money(preview.reconciliation.mismatch),
        "reasons": preview.reconciliation.reasons,
    }


@router.post("/close", response_model=CloseMonthResponse)
def run_close_month(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CloseMonthResponse:
    require_club_access(db, current_user, club_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant])
    period = get_period_or_404(db, club_id, period_id)
    preview = compute_monthly_nav(club_id, period_id, db=db)
    if not preview.reconciliation.passed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Reconciliation failed: mismatch UGX {abs(preview.reconciliation.mismatch):,.2f}.",
        )

    checklist = close_checklist(db, period)
    if not checklist.get("can_close", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Close checklist has pending items.",
        )

    existing_snapshot = db.scalar(
        select(NavSnapshot).where(NavSnapshot.club_id == club_id, NavSnapshot.period_id == period_id)
    )
    if existing_snapshot is None:
        snapshot = NavSnapshot(
            tenant_id=period.tenant_id,
            club_id=club_id,
            period_id=period_id,
            opening_nav=money(preview.opening_nav),
            contributions_total=money(preview.contributions_total),
            withdrawals_total=money(preview.withdrawals_total),
            income_total=money(preview.income_total),
            expenses_total=money(preview.expenses_total),
            closing_nav=money(preview.closing_nav),
        )
        db.add(snapshot)
        db.flush()

        for allocation in preview.allocations:
            db.add(
                InvestorBalance(
                    tenant_id=period.tenant_id,
                    club_id=club_id,
                    investor_id=allocation.investor_id,
                    period_id=period_id,
                    snapshot_id=snapshot.id,
                    opening_balance=allocation.opening_balance,
                    ownership_pct=allocation.ownership_pct,
                    income_alloc=allocation.income_share,
                    expense_alloc=allocation.expense_share,
                    net_alloc=allocation.net_alloc,
                    contributions=allocation.contributions,
                    withdrawals=allocation.withdrawals,
                    closing_balance=allocation.closing_balance,
                )
            )
    else:
        snapshot = existing_snapshot

    close_period(period, current_user, checklist)
    log_audit(
        db,
        actor=current_user,
        tenant_id=period.tenant_id,
        action="period.close_month",
        entity_type="period",
        entity_id=str(period.id),
        club_id=club_id,
        period_id=period_id,
        after_state={
            "status": period.status.value,
            "snapshot_id": snapshot.id,
            "closing_nav": str(snapshot.closing_nav),
        },
    )
    db.commit()
    return CloseMonthResponse(
        period_id=period.id,
        status=period.status.value,
        snapshot_id=snapshot.id,
        message="Period closed with immutable snapshot.",
    )
