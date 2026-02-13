import type {
  AnalyticsResponse,
  AnalyticsAnomaly,
  AnalyticsIntegrityStamp,
  ClubSummary,
  ClubMetricSummary,
  CopilotChatResponse,
  CloseChecklist,
  ForecastResponse,
  InsightsResponse,
  InvestorSummary,
  LedgerEntry,
  PeriodMetricSummary,
  PeriodState,
  PeriodSummary,
  ReconciliationDetails,
  ReconciliationStamp,
  ReportSnapshot,
  ScenarioProjectionResponse,
} from '@/types/platform';

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000/api/v1';
const DEV_USER_ID = (import.meta.env.VITE_USER_ID as string | undefined) ?? '';
const DEV_TENANT_ID = (import.meta.env.VITE_TENANT_ID as string | undefined) ?? '';

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers ?? {});
  headers.set('Content-Type', 'application/json');
  if (DEV_USER_ID) {
    headers.set('X-User-Id', DEV_USER_ID);
  }
  if (DEV_TENANT_ID) {
    headers.set('X-Tenant-Id', DEV_TENANT_ID);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `API request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function fetchClubs(): Promise<ClubSummary[]> {
  return apiFetch<ClubSummary[]>('/clubs');
}

export async function createClub(
  payload: {
    code: string;
    name: string;
    currency: string;
  },
): Promise<ClubSummary> {
  return apiFetch<ClubSummary>('/clubs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchPeriods(clubId: number): Promise<PeriodSummary[]> {
  return apiFetch<PeriodSummary[]>(`/clubs/${clubId}/periods`);
}

export async function fetchClubMetrics(): Promise<ClubMetricSummary[]> {
  return apiFetch<ClubMetricSummary[]>('/clubs/metrics');
}

export async function fetchPeriodMetrics(clubId: number, limit = 12): Promise<PeriodMetricSummary[]> {
  return apiFetch<PeriodMetricSummary[]>(`/clubs/${clubId}/period-metrics?limit=${limit}`);
}

export async function fetchInvestors(clubId: number): Promise<InvestorSummary[]> {
  return apiFetch<InvestorSummary[]>(`/clubs/${clubId}/investors`);
}

export async function createInvestor(
  clubId: number,
  payload: {
    investor_code: string;
    name: string;
  },
): Promise<InvestorSummary> {
  return apiFetch<InvestorSummary>(`/clubs/${clubId}/investors`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateInvestor(
  clubId: number,
  investorId: number,
  payload: {
    name?: string;
    is_active?: boolean;
  },
): Promise<InvestorSummary> {
  return apiFetch<InvestorSummary>(`/clubs/${clubId}/investors/${investorId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteInvestor(clubId: number, investorId: number): Promise<void> {
  await apiFetch(`/clubs/${clubId}/investors/${investorId}`, {
    method: 'DELETE',
  });
}

export async function fetchPeriodState(clubId: number, periodId: number): Promise<PeriodState> {
  return apiFetch<PeriodState>(`/clubs/${clubId}/periods/${periodId}/state`);
}

export async function fetchReconciliation(clubId: number, periodId: number): Promise<ReconciliationStamp> {
  return apiFetch<ReconciliationStamp>(`/clubs/${clubId}/periods/${periodId}/reconcile`);
}

export async function fetchCloseChecklist(clubId: number, periodId: number): Promise<CloseChecklist> {
  return apiFetch<CloseChecklist>(`/clubs/${clubId}/periods/${periodId}/close-checklist`);
}

export async function submitReview(clubId: number, periodId: number): Promise<void> {
  await apiFetch(`/clubs/${clubId}/periods/${periodId}/submit-review`, { method: 'POST' });
}

export async function closeMonth(clubId: number, periodId: number): Promise<void> {
  await apiFetch(`/clubs/${clubId}/periods/${periodId}/nav/close`, { method: 'POST' });
}

export async function fetchLedger(clubId: number, periodId: number): Promise<LedgerEntry[]> {
  return apiFetch<LedgerEntry[]>(`/clubs/${clubId}/periods/${periodId}/ledger`);
}

export async function createLedgerEntry(
  clubId: number,
  periodId: number,
  payload: {
    entry_type: 'contribution' | 'withdrawal' | 'income' | 'expense' | 'adjustment';
    amount: number;
    description: string;
    category?: string;
    tx_date?: string;
    note?: string;
    investor_id?: number;
    reference?: string;
    attachment_url?: string;
  },
): Promise<LedgerEntry> {
  return apiFetch<LedgerEntry>(`/clubs/${clubId}/periods/${periodId}/ledger`, {
    method: 'POST',
    body: JSON.stringify({
      category: payload.category ?? 'general',
      ...payload,
    }),
  });
}

export async function updateLedgerEntry(
  clubId: number,
  periodId: number,
  entryId: number,
  payload: {
    amount?: number;
    description?: string;
    category?: string;
    tx_date?: string;
    note?: string;
    reference?: string;
    attachment_url?: string;
  },
): Promise<LedgerEntry> {
  return apiFetch<LedgerEntry>(`/clubs/${clubId}/periods/${periodId}/ledger/${entryId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteLedgerEntry(clubId: number, periodId: number, entryId: number): Promise<void> {
  await apiFetch(`/clubs/${clubId}/periods/${periodId}/ledger/${entryId}`, {
    method: 'DELETE',
  });
}

export async function fetchInsights(
  clubId: number,
  periodId: number,
  mode: 'basic' | 'intelligent',
): Promise<InsightsResponse> {
  if (mode === 'basic') {
    return {
      mode: 'basic',
      items: [],
      anomalies: [],
      integrity: { reconciled: false, stamp: 'Preview', mismatch_ugx: '0', reasons: [] },
    };
  }
  const response = await apiFetch<{
    items: InsightsResponse['items'];
    anomalies: InsightsResponse['anomalies'];
    integrity?: AnalyticsIntegrityStamp;
  }>(
    `/analytics/insights?club_id=${clubId}&period_id=${periodId}`,
  );
  return {
    mode: 'intelligent',
    items: response.items ?? [],
    anomalies: response.anomalies ?? [],
    integrity: response.integrity,
  };
}

export async function fetchAnalyticsMetrics(clubId: number, periodId: number): Promise<AnalyticsResponse> {
  return apiFetch<AnalyticsResponse>(`/analytics/metrics?club_id=${clubId}&period_id=${periodId}`);
}

export async function fetchScenarioProjection(
  clubId: number,
  periodId: number,
  payload: {
    monthly_contribution: number;
    monthly_withdrawal: number;
    annual_yield_low_pct: number;
    annual_yield_high_pct: number;
    expense_rate_pct: number;
    months: number;
    goal_target_amount?: number | null;
    goal_target_date?: string | null;
  },
): Promise<ScenarioProjectionResponse> {
  const query = new URLSearchParams({
    club_id: String(clubId),
    period_id: String(periodId),
    monthly_contribution: String(payload.monthly_contribution),
    monthly_withdrawal: String(payload.monthly_withdrawal),
    annual_yield_low_pct: String(payload.annual_yield_low_pct),
    annual_yield_high_pct: String(payload.annual_yield_high_pct),
    expense_rate_pct: String(payload.expense_rate_pct),
    months: String(payload.months),
  });
  if (payload.goal_target_amount !== null && payload.goal_target_amount !== undefined) {
    query.set('goal_target_amount', String(payload.goal_target_amount));
  }
  if (payload.goal_target_date) {
    query.set('goal_target_date', payload.goal_target_date);
  }
  return apiFetch<ScenarioProjectionResponse>(`/analytics/scenarios?${query.toString()}`);
}

export async function fetchAnalyticsAnomalies(
  clubId: number,
  periodId: number,
): Promise<{ items: AnalyticsAnomaly[]; integrity: AnalyticsIntegrityStamp }> {
  return apiFetch<{ items: AnalyticsAnomaly[]; integrity: AnalyticsIntegrityStamp }>(
    `/analytics/anomalies?club_id=${clubId}&period_id=${periodId}`,
  );
}

export async function fetchAnalyticsForecast(
  clubId: number,
  periodId: number,
  months: number,
): Promise<ForecastResponse> {
  return apiFetch<ForecastResponse>(`/analytics/forecast?club_id=${clubId}&period_id=${periodId}&months=${months}`);
}

export async function fetchReconciliationDetails(
  clubId: number,
  periodId: number,
): Promise<ReconciliationDetails> {
  return apiFetch<ReconciliationDetails>(`/clubs/${clubId}/periods/${periodId}/nav/reconciliation`);
}

export async function chatCopilot(
  clubId: number,
  periodId: number,
  message: string,
): Promise<CopilotChatResponse> {
  return apiFetch<CopilotChatResponse>('/copilot/chat', {
    method: 'POST',
    body: JSON.stringify({
      club_id: clubId,
      period_id: periodId,
      message,
    }),
  });
}

export async function listReports(clubId: number, periodId: number): Promise<ReportSnapshot[]> {
  return apiFetch<ReportSnapshot[]>(`/clubs/${clubId}/periods/${periodId}/reports`);
}

export async function generateMonthlyReport(clubId: number, periodId: number): Promise<{ download_url: string }> {
  return apiFetch<{ download_url: string }>(`/clubs/${clubId}/periods/${periodId}/reports/monthly-club`, {
    method: 'POST',
  });
}

export async function generateInvestorReport(
  clubId: number,
  periodId: number,
  investorId: number,
): Promise<{ download_url: string }> {
  return apiFetch<{ download_url: string }>(
    `/clubs/${clubId}/periods/${periodId}/reports/investor/${investorId}`,
    { method: 'POST' },
  );
}

export function getCsvExportUrl(clubId: number, periodId: number): string {
  return `${API_BASE}/clubs/${clubId}/periods/${periodId}/exports/csv`;
}

export function getExcelExportUrl(clubId: number, periodId: number): string {
  return `${API_BASE}/clubs/${clubId}/periods/${periodId}/exports/excel`;
}
