import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, Calendar, Download, Sparkles } from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Button } from '@/components/ui/button';
import { usePlatform } from '@/context/PlatformContext';
import { extractApiErrorMessage } from '@/lib/feedback';
import {
  fetchAnalyticsAnomalies,
  fetchAnalyticsForecast,
  fetchAnalyticsMetrics,
  fetchScenarioProjection,
} from '@/lib/api';
import { cn, formatCurrency, formatPercentage } from '@/lib/utils';
import type {
  AnalyticsResponse,
  ForecastResponse,
  ScenarioProjectionResponse,
} from '@/types/platform';
import { InsightFeed } from '@/components/ui-custom/InsightFeed';
import { IntegrityStamp } from '@/components/ui-custom/IntegrityStamp';
import { ScenarioSimulator } from '@/components/ui-custom/ScenarioSimulator';
import { ForecastPanel } from '@/components/ui-custom/ForecastPanel';
import { AllocationExplainability } from '@/components/ui-custom/AllocationExplainability';

function toNumber(value: string | number | boolean | null | undefined): number {
  if (typeof value === 'number') return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function monthLabel(period: string): string {
  const [yearText, monthText] = period.split('-');
  const year = Number(yearText);
  const month = Number(monthText);
  if (!Number.isFinite(year) || !Number.isFinite(month)) return period;
  const date = new Date(Date.UTC(year, month - 1, 1));
  return date.toLocaleString('en-US', { month: 'short' });
}

export function AnalyticsView() {
  const { mode, selectedClubId, selectedPeriodId, locked, status } = usePlatform();
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [scenario, setScenario] = useState<ScenarioProjectionResponse | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scenarioBusy, setScenarioBusy] = useState(false);
  const [forecastBusy, setForecastBusy] = useState(false);

  const load = useCallback(async () => {
    if (!selectedClubId || !selectedPeriodId) {
      setAnalytics(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [payload, anomalyPayload] = await Promise.all([
        fetchAnalyticsMetrics(selectedClubId, selectedPeriodId),
        fetchAnalyticsAnomalies(selectedClubId, selectedPeriodId),
      ]);
      setAnalytics({
        ...payload,
        anomalies: anomalyPayload.items,
        integrity: anomalyPayload.integrity,
      });
    } catch (err) {
      setError(extractApiErrorMessage(err, 'Failed to load analytics.'));
    } finally {
      setLoading(false);
    }
  }, [selectedClubId, selectedPeriodId]);

  useEffect(() => {
    void load();
  }, [load]);

  const navCurve = useMemo(
    () =>
      (analytics?.charts?.nav_curve ?? []).map((row) => ({
        month: monthLabel(String(row.period ?? '')),
        opening: toNumber(row.opening_nav),
        closing: toNumber(row.closing_nav),
        contributions: toNumber(row.contributions),
        withdrawals: toNumber(row.withdrawals),
        income: toNumber(row.income),
        expenses: toNumber(row.expenses),
      })),
    [analytics?.charts],
  );

  const returnData = useMemo(
    () =>
      navCurve.map((row) => ({
        month: row.month,
        return: row.opening > 0 ? ((row.closing - row.opening) / row.opening) * 100 : 0,
      })),
    [navCurve],
  );

  const cumulativeData = useMemo(() => {
    if (navCurve.length === 0) return [];
    const first = navCurve[0].opening || 1;
    return navCurve.map((row) => ({
      month: row.month,
      growth: ((row.closing - first) / first) * 100,
    }));
  }, [navCurve]);

  const openingNav = toNumber(analytics?.metrics.opening_nav);
  const closingNav = toNumber(analytics?.metrics.closing_nav);
  const contributions = toNumber(analytics?.metrics.contributions);
  const withdrawals = toNumber(analytics?.metrics.withdrawals);
  const income = toNumber(analytics?.metrics.income);
  const expenses = toNumber(analytics?.metrics.expenses);
  const netResult = toNumber(analytics?.metrics.net_result);
  const mismatch = toNumber(analytics?.metrics.mismatch);
  const expenseRatio = toNumber(analytics?.metrics.expense_ratio_pct);
  const avgReturn =
    returnData.length > 0
      ? returnData.reduce((sum, row) => sum + row.return, 0) / returnData.length
      : 0;

  const allocationRows = useMemo(
    () =>
      (analytics?.charts?.allocation_explainability ?? []).map((row) => ({
        investor_id: toNumber(row.investor_id),
        opening_balance: toNumber(row.opening_balance),
        ownership_pct: toNumber(row.ownership_pct),
        income_share: toNumber(row.income_share),
        expense_share: toNumber(row.expense_share),
        net_alloc: toNumber(row.net_alloc),
        contributions: toNumber(row.contributions),
        withdrawals: toNumber(row.withdrawals),
        closing_balance: toNumber(row.closing_balance),
      })),
    [analytics?.charts],
  );

  const returnDecomposition = useMemo(() => {
    if (!analytics?.metrics.return_decomposition) return null;
    return {
      cashflows: toNumber(analytics.metrics.return_decomposition.cashflows),
      income: toNumber(analytics.metrics.return_decomposition.income),
      expenses: toNumber(analytics.metrics.return_decomposition.expenses),
      net_result: toNumber(analytics.metrics.return_decomposition.net_result),
    };
  }, [analytics?.metrics.return_decomposition]);

  async function runScenario(payload: {
    monthly_contribution: number;
    monthly_withdrawal: number;
    annual_yield_low_pct: number;
    annual_yield_high_pct: number;
    expense_rate_pct: number;
    months: number;
    goal_target_amount?: number | null;
    goal_target_date?: string | null;
  }) {
    if (!selectedClubId || !selectedPeriodId) return;
    setScenarioBusy(true);
    setError(null);
    try {
      const result = await fetchScenarioProjection(selectedClubId, selectedPeriodId, payload);
      setScenario(result);
    } catch (err) {
      const detail = extractApiErrorMessage(err, 'Failed to run scenario.');
      setError(`${detail} Use numeric assumptions and choose 12-36 months.`);
    } finally {
      setScenarioBusy(false);
    }
  }

  async function runForecast(months: number) {
    if (!selectedClubId || !selectedPeriodId) return;
    setForecastBusy(true);
    setError(null);
    try {
      const result = await fetchAnalyticsForecast(selectedClubId, selectedPeriodId, months);
      setForecast(result);
    } catch (err) {
      setError(extractApiErrorMessage(err, 'Failed to run forecast.'));
    } finally {
      setForecastBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Analysis</h1>
          <p className="text-sm text-slate-500 mt-0.5">Metrics, anomalies, and explainable projections</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" className="border-slate-200 text-slate-600">
            <Calendar className="w-4 h-4 mr-2" />
            Last 24 Months
          </Button>
          <Button variant="outline" className="border-slate-200 text-slate-600">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {status !== 'closed' && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-xs text-blue-700">
          Preview mode active. Figures may change until period is closed.
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-1">Opening NAV</p>
          <p className="text-2xl font-semibold text-slate-800">{formatCurrency(openingNav)}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-1">Closing NAV</p>
          <p className="text-2xl font-semibold text-slate-800">{formatCurrency(closingNav)}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-1">Avg Monthly Return</p>
          <p className={cn('text-2xl font-semibold', avgReturn >= 0 ? 'text-emerald-600' : 'text-red-500')}>
            {formatPercentage(avgReturn)}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-1">Expense Ratio</p>
          <p className="text-2xl font-semibold text-blue-600">{expenseRatio.toFixed(2)}%</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <h3 className="text-base font-semibold text-slate-800 mb-4">NAV Waterfall</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { label: 'Opening NAV', value: openingNav, tone: 'bg-slate-50 text-slate-800' },
            { label: 'Contributions', value: contributions, tone: 'bg-emerald-50 text-emerald-600' },
            { label: 'Withdrawals', value: -withdrawals, tone: 'bg-red-50 text-red-500' },
            { label: 'Income', value: income, tone: 'bg-emerald-50 text-emerald-600' },
            { label: 'Expenses', value: -expenses, tone: 'bg-red-50 text-red-500' },
            { label: 'Closing NAV', value: closingNav, tone: 'bg-blue-50 text-blue-600 border-2 border-blue-200' },
          ].map((item) => (
            <div key={item.label} className={cn('p-4 rounded-xl', item.tone)}>
              <p className="text-xs text-slate-500 mb-1">{item.label}</p>
              <p className="text-lg font-semibold">
                {item.value >= 0 ? '+' : '-'}
                {formatCurrency(Math.abs(item.value))}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-4">Monthly Returns</h3>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={returnData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(value) => `${value}%`} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'white', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px' }}
                  formatter={(value: number) => [formatPercentage(value), 'Return']}
                />
                <Bar dataKey="return" radius={[4, 4, 0, 0]}>
                  {returnData.map((item, index) => (
                    <Cell key={index} fill={item.return >= 0 ? '#10b981' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-4">Cumulative Growth</h3>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={cumulativeData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="growthGradientAnalysis" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(value) => `${value}%`} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'white', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px' }}
                  formatter={(value: number) => [`${value.toFixed(2)}%`, 'Growth']}
                />
                <Area type="monotone" dataKey="growth" stroke="#10b981" strokeWidth={2} fill="url(#growthGradientAnalysis)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {mode === 'intelligent' ? (
        <>
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-blue-500" />
            <h3 className="text-base font-semibold text-slate-800">Insights Feed</h3>
          </div>
          <InsightFeed insights={analytics?.insights ?? []} anomalies={analytics?.anomalies ?? []} />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <IntegrityStamp integrity={analytics?.integrity ?? null} />
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
              <h3 className="text-base font-semibold text-slate-800 mb-2">Advisor Intelligence</h3>
              <p className="text-xs text-slate-500">Business-level flags from selected club period.</p>
              <div className="mt-3 space-y-2 text-sm">
                <p className="text-slate-700">AUM growth: <span className="font-medium">{formatPercentage(toNumber(analytics?.metrics.aum_growth_rate_pct), 2)}</span></p>
                <p className="text-slate-700">3M avg inflow: <span className="font-medium">{formatCurrency(toNumber(analytics?.metrics.inflow_3m_avg))}</span></p>
                <p className="text-slate-700">Dormant investors: <span className="font-medium">{analytics?.metrics.dormant_investors ?? 0}</span></p>
                <p className="text-slate-700">Churn-risk flags: <span className="font-medium">{analytics?.metrics.churn_risk_flags ?? 0}</span></p>
              </div>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
              <h3 className="text-base font-semibold text-slate-800 mb-2">Integrity Gate</h3>
              <p className={cn('text-sm font-medium', mismatch === 0 ? 'text-emerald-600' : 'text-red-500')}>
                {mismatch === 0 ? 'Reconciled ✅' : `Mismatch ❌ ${formatCurrency(Math.abs(mismatch))}`}
              </p>
              <p className="text-xs text-slate-500 mt-1">Close-month remains blocked if mismatch is non-zero.</p>
            </div>
          </div>

          <ScenarioSimulator
            scenario={scenario}
            disabled={locked || !selectedClubId || !selectedPeriodId}
            running={scenarioBusy}
            onRun={runScenario}
          />

          <ForecastPanel
            forecast={forecast}
            disabled={!selectedClubId || !selectedPeriodId}
            loading={forecastBusy}
            onRun={runForecast}
          />

          <AllocationExplainability rows={allocationRows} returnDecomposition={returnDecomposition} />
        </>
      ) : (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-sm text-slate-600">
          Intelligent Mode is off. Switch mode in the top bar to view insights, anomaly flags, scenarios, forecast, and copilot tools.
        </div>
      )}

      {loading && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 text-sm text-slate-500">
          Loading analytics...
        </div>
      )}

      {!loading && !analytics && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600" />
          <p className="text-sm text-amber-700">No analytics available for the selected period.</p>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <h3 className="text-base font-semibold text-slate-800 mb-2">Reconciliation Check</h3>
        <p className={cn('text-sm font-medium', mismatch === 0 ? 'text-emerald-600' : 'text-red-500')}>
          {mismatch === 0 ? 'Reconciled ✅' : `Mismatch ❌ ${formatCurrency(Math.abs(mismatch))}`}
        </p>
        <p className="text-xs text-slate-500 mt-1">Net result: {formatCurrency(netResult)}</p>
      </div>
    </div>
  );
}
