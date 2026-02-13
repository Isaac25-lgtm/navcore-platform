export type PeriodStatus = 'draft' | 'review' | 'closed';
export type Mode = 'basic' | 'intelligent';
export type Severity = 'info' | 'warn' | 'critical';

export interface ClubSummary {
  id: number;
  code: string;
  name: string;
  currency: string;
  is_active: boolean;
}

export interface InvestorSummary {
  id: number;
  club_id: number;
  investor_code: string;
  name: string;
  is_active: boolean;
}

export interface PeriodSummary {
  id: number;
  club_id: number;
  year: number;
  month: number;
  status: PeriodStatus;
  opening_nav: string;
  closing_nav: string;
  reconciliation_diff: string;
  locked_at: string | null;
  closed_at: string | null;
}

export interface PeriodMetricSummary {
  period_id: number;
  year: number;
  month: number;
  status: PeriodStatus;
  opening_nav: string;
  contributions: string;
  withdrawals: string;
  income: string;
  expenses: string;
  net_result: string;
  closing_nav: string;
  mismatch: string;
  return_pct: string;
}

export interface ClubMetricSummary {
  id: number;
  code: string;
  name: string;
  currency: string;
  is_active: boolean;
  investor_count: number;
  latest_period: PeriodMetricSummary | null;
}

export interface PositionState {
  investor_id: number;
  investor_name: string;
  opening_balance: string;
  ownership_pct: string;
  income_alloc?: string;
  expense_alloc?: string;
  contributions: string;
  withdrawals: string;
  net_allocation: string;
  closing_balance: string;
}

export interface PeriodState {
  period_id: number;
  club_id: number;
  year: number;
  month: number;
  status: PeriodStatus;
  opening_nav: string;
  closing_nav: string;
  reconciliation_diff: string;
  locked_at: string | null;
  totals: Record<string, string>;
  positions: PositionState[];
}

export interface LedgerEntry {
  id: number;
  club_id: number;
  period_id: number;
  investor_id: number | null;
  entry_type: 'contribution' | 'withdrawal' | 'income' | 'expense' | 'adjustment';
  amount: string;
  category: string;
  tx_date: string;
  description: string;
  note: string | null;
  reference: string | null;
  attachment_url: string | null;
  created_by_user_id: number;
  created_at: string;
}

export interface ReconciliationStamp {
  reconciled: boolean;
  stamp: string;
  mismatch_ugx: string;
  club_closing_nav: string;
  investor_total: string;
}

export interface ReconciliationDetails {
  passed: boolean;
  mismatch: string;
  reasons: string[];
}

export interface CloseChecklist {
  can_close: boolean;
  checklist: Record<string, boolean>;
  reconciliation_stamp: string;
  mismatch_ugx: string;
}

export interface InsightItem {
  code: string;
  severity: Severity;
  title: string;
  description: string;
  evidence: string;
  numeric_evidence: Record<string, string | number | boolean | null>;
  drilldown_path: string;
}

export interface InsightsResponse {
  mode: Mode;
  items: InsightItem[];
  anomalies?: AnalyticsAnomaly[];
  integrity?: AnalyticsIntegrityStamp;
}

export interface AnalyticsAnomaly {
  code: string;
  severity: Severity;
  title: string;
  message: string;
  evidence: string;
  numeric_evidence: Record<string, string | number | boolean | null>;
  drilldown_path: string;
}

export interface AnalyticsIntegrityStamp {
  reconciled: boolean;
  stamp: string;
  mismatch_ugx: string;
  reasons: string[];
}

export interface AnalyticsMetrics {
  opening_nav: string;
  closing_nav: string;
  contributions: string;
  withdrawals: string;
  income: string;
  expenses: string;
  net_result: string;
  net_inflow: string;
  expense_ratio_pct: string;
  reconciled: boolean;
  mismatch: string;
  top3_share_pct: string;
  aum_growth_rate_pct: string;
  inflow_3m_avg: string;
  dormant_investors: number;
  churn_risk_flags: number;
  return_decomposition: {
    cashflows: string;
    income: string;
    expenses: string;
    net_result: string;
  };
}

export interface AnalyticsResponse {
  metrics: AnalyticsMetrics;
  insights: InsightItem[];
  anomalies: AnalyticsAnomaly[];
  integrity: AnalyticsIntegrityStamp;
  charts: Record<string, Array<Record<string, string | number | boolean | null>>>;
}

export interface ScenarioProjectionPoint {
  month_index: number;
  assumption: Record<string, string | number>;
  base_nav: string;
  best_nav: string;
  worst_nav: string;
  low_band_nav: string;
  high_band_nav: string;
}

export interface ScenarioGoal {
  target_amount: string;
  target_date: string;
  required_monthly_contribution: string;
  months_to_goal: number;
}

export interface ScenarioProjectionResponse {
  assumptions: Record<string, string | number>;
  projection: ScenarioProjectionPoint[];
  goal?: ScenarioGoal | null;
}

export interface ForecastPoint {
  month_index: number;
  rolling_forecast_nav: string;
  regression_forecast_nav: string;
  arima_forecast_nav: string | null;
  low_band_nav: string;
  high_band_nav: string;
}

export interface ForecastResponse {
  method: string;
  confidence_level: string;
  explanation: string;
  points: ForecastPoint[];
}

export interface CopilotSource {
  type: string;
  ref: string;
}

export interface CopilotChatResponse {
  response: string;
  sources: CopilotSource[];
}

export interface ReportSnapshot {
  id: number;
  club_id: number;
  period_id: number;
  investor_id: number | null;
  report_type: 'monthly_club' | 'investor_statement';
  file_name: string;
  file_hash: string;
  created_at: string;
}
