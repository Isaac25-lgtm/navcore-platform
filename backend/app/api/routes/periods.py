from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_club_access
from app.core.security import require_roles
from app.models.enums import PeriodStatus, RoleName
from app.models.investor import Investor
from app.models.nav import InvestorBalance, NavSnapshot
from app.models.period import InvestorPosition
from app.models.user import User
from app.schemas.ledger import ReconciliationStamp
from app.schemas.periods import (
    CloseActionResponse,
    CloseChecklistResponse,
    InsightItem,
    InsightsResponse,
    PeriodStateResponse,
    PositionState,
)
from app.services.accounting import (
    build_intelligent_insights,
    close_checklist,
    close_period,
    get_period_or_404,
    recalculate_period,
    reconciliation_stamp,
    submit_for_review,
)
from app.services.audit import log_audit
from app.services.nav_engine import compute_monthly_nav
from app.utils.decimal_math import money


router = APIRouter(prefix="/clubs/{club_id}/periods/{period_id}", tags=["periods"])


@router.get("/state", response_model=PeriodStateResponse)
def get_period_state(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_club_access(db, current_user, club_id)
    period = get_period_or_404(db, club_id, period_id)
    totals = recalculate_period(db, period)
    db.commit()

    positions = list(
        db.scalars(
            select(InvestorPosition)
            .where(InvestorPosition.period_id == period.id)
            .order_by(InvestorPosition.investor_id)
        ).all()
    )
    investor_map = {
        investor.id: investor.name
        for investor in db.scalars(select(Investor).where(Investor.club_id == club_id)).all()
    }
    return PeriodStateResponse(
        period_id=period.id,
        club_id=period.club_id,
        year=period.year,
        month=period.month,
        status=period.status,
        opening_nav=money(period.opening_nav),
        closing_nav=money(period.closing_nav),
        reconciliation_diff=money(period.reconciliation_diff),
        locked_at=period.locked_at,
        totals={
            "contributions": money(totals.contributions),
            "withdrawals": money(totals.withdrawals),
            "income": money(totals.income),
            "expenses": money(totals.expenses),
            "net_result": money(totals.net_result),
            "closing_nav": money(totals.closing_nav),
            "investor_total": money(totals.investor_total),
            "mismatch": money(totals.mismatch),
        },
        positions=[
            PositionState(
                investor_id=position.investor_id,
                investor_name=investor_map.get(position.investor_id, f"Investor {position.investor_id}"),
                opening_balance=money(position.opening_balance),
                ownership_pct=position.ownership_pct,
                income_alloc=money(position.income_alloc),
                expense_alloc=money(position.expense_alloc),
                contributions=money(position.contributions),
                withdrawals=money(position.withdrawals),
                net_allocation=money(position.net_allocation),
                closing_balance=money(position.closing_balance),
            )
            for position in positions
        ],
    )


@router.get("/summary")
def get_period_summary(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_club_access(db, current_user, club_id)
    period = get_period_or_404(db, club_id, period_id)
    totals = recalculate_period(db, period)
    db.commit()
    stamp = reconciliation_stamp(period, totals.investor_total)
    return {
        "period_id": period.id,
        "club_id": period.club_id,
        "year": period.year,
        "month": period.month,
        "status": period.status.value,
        "opening_nav": money(period.opening_nav),
        "closing_nav": money(period.closing_nav),
        "totals": {
            "contributions": money(totals.contributions),
            "withdrawals": money(totals.withdrawals),
            "income": money(totals.income),
            "expenses": money(totals.expenses),
            "net_result": money(totals.net_result),
            "investor_total": money(totals.investor_total),
            "mismatch": money(totals.mismatch),
        },
        "reconciliation": {
            "reconciled": bool(stamp["reconciled"]),
            "stamp": str(stamp["stamp"]),
            "mismatch_ugx": money(stamp["mismatch_ugx"]),
            "reasons": [] if bool(stamp["reconciled"]) else [str(stamp["stamp"])],
        },
    }


@router.get("/reconcile", response_model=ReconciliationStamp)
def reconcile_period(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_club_access(db, current_user, club_id)
    period = get_period_or_404(db, club_id, period_id)
    totals = recalculate_period(db, period)
    db.commit()
    stamp = reconciliation_stamp(period, totals.investor_total)
    return ReconciliationStamp(
        reconciled=bool(stamp["reconciled"]),
        stamp=str(stamp["stamp"]),
        mismatch_ugx=money(stamp["mismatch_ugx"]),
        club_closing_nav=money(stamp["club_closing_nav"]),
        investor_total=money(stamp["investor_total"]),
    )


@router.get("/close-checklist", response_model=CloseChecklistResponse)
def get_close_checklist(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_club_access(db, current_user, club_id)
    period = get_period_or_404(db, club_id, period_id)
    totals = recalculate_period(db, period)
    db.commit()
    checklist = close_checklist(db, period)
    stamp = reconciliation_stamp(period, totals.investor_total)
    return CloseChecklistResponse(
        can_close=bool(checklist["can_close"]),
        checklist=checklist,
        reconciliation_stamp=str(stamp["stamp"]),
        mismatch_ugx=money(stamp["mismatch_ugx"]),
    )


@router.post("/submit-review", response_model=CloseActionResponse)
def submit_period_for_review(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_club_access(db, current_user, club_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant, RoleName.advisor])
    period = get_period_or_404(db, club_id, period_id)
    previous_status = period.status.value
    submit_for_review(period)
    log_audit(
        db,
        actor=current_user,
        tenant_id=period.tenant_id,
        action="period.submit_review",
        entity_type="period",
        entity_id=str(period.id),
        club_id=club_id,
        period_id=period.id,
        before_state={"status": previous_status},
        after_state={"status": period.status.value},
    )
    db.commit()
    db.refresh(period)
    return CloseActionResponse(
        period_id=period.id,
        status=period.status,
        locked_at=period.locked_at,
        closed_at=period.closed_at,
        message="Period moved to review.",
    )


@router.post("/close", response_model=CloseActionResponse)
def close_current_period(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_club_access(db, current_user, club_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant])
    period = get_period_or_404(db, club_id, period_id)
    totals = recalculate_period(db, period)
    checklist = close_checklist(db, period)
    preview = compute_monthly_nav(club_id, period_id, db=db)
    if not preview.reconciliation.passed:
        raise HTTPException(
            status_code=409,
            detail=f"Reconciliation failed: mismatch UGX {abs(preview.reconciliation.mismatch):,.2f}.",
        )

    snapshot = db.scalar(
        select(NavSnapshot).where(NavSnapshot.club_id == club_id, NavSnapshot.period_id == period_id)
    )
    if snapshot is None:
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

    close_period(period, current_user, checklist)
    log_audit(
        db,
        actor=current_user,
        tenant_id=period.tenant_id,
        action="period.close",
        entity_type="period",
        entity_id=str(period.id),
        club_id=club_id,
        period_id=period.id,
        before_state={"status": "review"},
        after_state={
            "status": period.status.value,
            "closing_nav": str(period.closing_nav),
            "mismatch": str(totals.mismatch),
            "snapshot_id": snapshot.id,
        },
    )
    db.commit()
    db.refresh(period)
    return CloseActionResponse(
        period_id=period.id,
        status=period.status,
        locked_at=period.locked_at,
        closed_at=period.closed_at,
        message="Period closed and locked.",
    )


@router.patch("/status", response_model=CloseActionResponse)
def set_period_status(
    club_id: int,
    period_id: int,
    status_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_club_access(db, current_user, club_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant])
    period = get_period_or_404(db, club_id, period_id)
    if period.status == PeriodStatus.closed:
        raise HTTPException(status_code=409, detail="Closed period is immutable.")

    normalized = status_name.lower().strip()
    if normalized not in {"draft", "review"}:
        raise HTTPException(status_code=400, detail="Status must be draft or review.")
    previous = period.status.value
    period.status = PeriodStatus.review if normalized == "review" else PeriodStatus.draft
    log_audit(
        db,
        actor=current_user,
        tenant_id=period.tenant_id,
        action="period.set_status",
        entity_type="period",
        entity_id=str(period.id),
        club_id=club_id,
        period_id=period.id,
        before_state={"status": previous},
        after_state={"status": period.status.value},
    )
    db.commit()
    db.refresh(period)
    return CloseActionResponse(
        period_id=period.id,
        status=period.status,
        locked_at=period.locked_at,
        closed_at=period.closed_at,
        message=f"Period moved to {period.status.value}.",
    )


@router.get("/insights", response_model=InsightsResponse)
def get_intelligent_insights(
    club_id: int,
    period_id: int,
    mode: str = "basic",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_club_access(db, current_user, club_id)
    period = get_period_or_404(db, club_id, period_id)
    totals = recalculate_period(db, period)
    db.commit()
    if mode.lower() != "intelligent":
        return InsightsResponse(mode="basic", items=[])

    insights = [
        InsightItem(
            code=item["code"],
            level=item["level"],
            title=item["title"],
            description=item["description"],
        )
        for item in build_intelligent_insights(period, totals)
    ]
    return InsightsResponse(mode="intelligent", items=insights)
