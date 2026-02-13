from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_club_access
from app.models.period import AccountingPeriod
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsResponse,
    ForecastResponse,
    ScenarioProjectionResponse,
)
from app.services.analytics import build_scenario_projection, generate_forecast, generate_metrics
from app.services.nav_engine import compute_monthly_nav
from app.utils.decimal_math import money


router = APIRouter(tags=["analytics"])


@router.get("/analytics/metrics", response_model=AnalyticsResponse)
def get_analytics_metrics(
    club_id: int = Query(...),
    period_id: int = Query(...),
    outlier_threshold_pct: Decimal = Query(default=Decimal("5"), gt=Decimal("0")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyticsResponse:
    require_club_access(db, current_user, club_id)
    payload = generate_metrics(db, club_id, period_id, outlier_threshold_pct=outlier_threshold_pct)
    return AnalyticsResponse(
        metrics=payload.metrics,
        insights=payload.insights,
        anomalies=payload.anomalies,
        integrity=payload.integrity,
        charts=payload.charts,
    )


@router.get("/analytics/insights")
def get_analytics_insights(
    club_id: int = Query(...),
    period_id: int = Query(...),
    outlier_threshold_pct: Decimal = Query(default=Decimal("5"), gt=Decimal("0")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    require_club_access(db, current_user, club_id)
    payload = generate_metrics(db, club_id, period_id, outlier_threshold_pct=outlier_threshold_pct)
    return {"items": payload.insights, "anomalies": payload.anomalies, "integrity": payload.integrity}


@router.get("/analytics/anomalies")
def get_analytics_anomalies(
    club_id: int = Query(...),
    period_id: int = Query(...),
    outlier_threshold_pct: Decimal = Query(default=Decimal("5"), gt=Decimal("0")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    require_club_access(db, current_user, club_id)
    payload = generate_metrics(db, club_id, period_id, outlier_threshold_pct=outlier_threshold_pct)
    return {"items": payload.anomalies, "integrity": payload.integrity}


@router.get("/analytics/charts/nav")
def get_nav_chart(
    club_id: int = Query(...),
    period_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    require_club_access(db, current_user, club_id)
    payload = generate_metrics(db, club_id, period_id)
    return {"nav_curve": payload.charts.get("nav_curve", [])}


@router.get("/analytics/charts/flows")
def get_flow_chart(
    club_id: int = Query(...),
    period_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    require_club_access(db, current_user, club_id)
    preview = compute_monthly_nav(club_id, period_id, db=db)
    return {
        "contributions_total": money(preview.contributions_total),
        "withdrawals_total": money(preview.withdrawals_total),
        "income_total": money(preview.income_total),
        "expenses_total": money(preview.expenses_total),
    }


def _run_scenario_projection(
    *,
    club_id: int,
    period_id: int,
    monthly_contribution: Decimal,
    monthly_withdrawal: Decimal,
    annual_yield_low_pct: Decimal,
    annual_yield_high_pct: Decimal,
    expense_rate_pct: Decimal,
    months: int,
    goal_target_amount: Decimal | None,
    goal_target_date: str | None,
    db: Session,
    current_user: User,
) -> ScenarioProjectionResponse:
    require_club_access(db, current_user, club_id)
    period = db.scalar(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.club_id == club_id,
        )
    )
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found.")

    preview = compute_monthly_nav(club_id, period_id, db=db)
    projection = build_scenario_projection(
        current_nav=preview.closing_nav,
        monthly_contribution=monthly_contribution,
        monthly_withdrawal=monthly_withdrawal,
        annual_yield_low_pct=annual_yield_low_pct,
        annual_yield_high_pct=annual_yield_high_pct,
        expense_rate_pct=expense_rate_pct,
        months=months,
        current_year=period.year,
        current_month=period.month,
        goal_target_amount=goal_target_amount,
        goal_target_date=goal_target_date,
    )
    return ScenarioProjectionResponse(
        assumptions={
            "monthly_contribution": money(monthly_contribution),
            "monthly_withdrawal": money(monthly_withdrawal),
            "annual_yield_low_pct": annual_yield_low_pct,
            "annual_yield_high_pct": annual_yield_high_pct,
            "expense_rate_pct": expense_rate_pct,
            "months": months,
            "goal_target_amount": money(goal_target_amount) if goal_target_amount is not None else None,
            "goal_target_date": goal_target_date,
        },
        projection=projection.points,
        goal=projection.goal,
    )


@router.get("/analytics/scenarios", response_model=ScenarioProjectionResponse)
def run_scenario_projection(
    club_id: int = Query(...),
    period_id: int = Query(...),
    monthly_contribution: Decimal = Query(default=Decimal("0"), ge=Decimal("0")),
    monthly_withdrawal: Decimal = Query(default=Decimal("0"), ge=Decimal("0")),
    annual_yield_low_pct: Decimal = Query(default=Decimal("6"), ge=Decimal("0")),
    annual_yield_high_pct: Decimal = Query(default=Decimal("14"), ge=Decimal("0")),
    expense_rate_pct: Decimal = Query(default=Decimal("1.5"), ge=Decimal("0")),
    months: int = Query(default=24, ge=12, le=36),
    goal_target_amount: Decimal | None = Query(default=None),
    goal_target_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScenarioProjectionResponse:
    return _run_scenario_projection(
        club_id=club_id,
        period_id=period_id,
        monthly_contribution=monthly_contribution,
        monthly_withdrawal=monthly_withdrawal,
        annual_yield_low_pct=annual_yield_low_pct,
        annual_yield_high_pct=annual_yield_high_pct,
        expense_rate_pct=expense_rate_pct,
        months=months,
        goal_target_amount=goal_target_amount,
        goal_target_date=goal_target_date,
        db=db,
        current_user=current_user,
    )


@router.get("/analytics/scenario", response_model=ScenarioProjectionResponse)
def run_scenario_projection_legacy(
    club_id: int = Query(...),
    period_id: int = Query(...),
    monthly_contribution: Decimal = Query(default=Decimal("0"), ge=Decimal("0")),
    monthly_withdrawal: Decimal = Query(default=Decimal("0"), ge=Decimal("0")),
    annual_yield_low_pct: Decimal = Query(default=Decimal("6"), ge=Decimal("0")),
    annual_yield_high_pct: Decimal = Query(default=Decimal("14"), ge=Decimal("0")),
    expense_rate_pct: Decimal = Query(default=Decimal("1.5"), ge=Decimal("0")),
    months: int = Query(default=24, ge=12, le=36),
    goal_target_amount: Decimal | None = Query(default=None),
    goal_target_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScenarioProjectionResponse:
    return _run_scenario_projection(
        club_id=club_id,
        period_id=period_id,
        monthly_contribution=monthly_contribution,
        monthly_withdrawal=monthly_withdrawal,
        annual_yield_low_pct=annual_yield_low_pct,
        annual_yield_high_pct=annual_yield_high_pct,
        expense_rate_pct=expense_rate_pct,
        months=months,
        goal_target_amount=goal_target_amount,
        goal_target_date=goal_target_date,
        db=db,
        current_user=current_user,
    )


@router.get("/analytics/forecast", response_model=ForecastResponse)
def get_forecast(
    club_id: int = Query(...),
    period_id: int = Query(...),
    months: int = Query(default=12, ge=12, le=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ForecastResponse:
    require_club_access(db, current_user, club_id)
    payload = generate_forecast(db, club_id=club_id, period_id=period_id, months=months)
    return ForecastResponse(
        method=payload["method"],
        confidence_level=payload["confidence_level"],
        explanation=payload["explanation"],
        points=payload["points"],
    )
