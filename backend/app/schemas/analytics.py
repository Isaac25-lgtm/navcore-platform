from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel


Severity = Literal["info", "warn", "critical"]


class AnalyticsInsightOut(BaseModel):
    code: str
    severity: Severity
    title: str
    description: str
    evidence: str
    numeric_evidence: dict[str, Any]
    drilldown_path: str


class AnalyticsAnomalyOut(BaseModel):
    code: str
    severity: Severity
    title: str
    message: str
    evidence: str
    numeric_evidence: dict[str, Any]
    drilldown_path: str


class IntegrityStampOut(BaseModel):
    reconciled: bool
    stamp: str
    mismatch_ugx: Decimal
    reasons: list[str]


class AnalyticsResponse(BaseModel):
    metrics: dict[str, Any]
    insights: list[AnalyticsInsightOut]
    anomalies: list[AnalyticsAnomalyOut]
    integrity: IntegrityStampOut
    charts: dict[str, list[dict[str, Any]]]


class ScenarioProjectionPointOut(BaseModel):
    month_index: int
    assumption: dict[str, Any]
    base_nav: Decimal
    best_nav: Decimal
    worst_nav: Decimal
    low_band_nav: Decimal
    high_band_nav: Decimal


class ScenarioGoalOut(BaseModel):
    target_amount: Decimal
    target_date: str
    required_monthly_contribution: Decimal
    months_to_goal: int


class ScenarioProjectionResponse(BaseModel):
    assumptions: dict[str, Any]
    projection: list[ScenarioProjectionPointOut]
    goal: ScenarioGoalOut | None = None


class ForecastPointOut(BaseModel):
    month_index: int
    rolling_forecast_nav: Decimal
    regression_forecast_nav: Decimal
    arima_forecast_nav: Decimal | None = None
    low_band_nav: Decimal
    high_band_nav: Decimal


class ForecastResponse(BaseModel):
    method: str
    confidence_level: str
    explanation: str
    points: list[ForecastPointOut]
