import { useEffect, useMemo, useState } from 'react';
import {
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  Users,
  Building2,
  Activity,
  Calendar,
  MoreHorizontal,
  Download,
  ChevronRight,
  Lightbulb,
  Newspaper,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePlatform } from '@/context/PlatformContext';
import { fetchClubMetrics, fetchPeriodMetrics, getCsvExportUrl, submitReview } from '@/lib/api';
import { extractApiErrorMessage } from '@/lib/feedback';
import type { ClubMetricSummary, PeriodMetricSummary } from '@/types/platform';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';
import { formatCurrency, cn } from '@/lib/utils';

function toNumber(value: string | null | undefined): number {
  if (!value) return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function toMonthLabel(year: number, month: number): string {
  const date = new Date(Date.UTC(year, month - 1, 1));
  return date.toLocaleString('en-US', { month: 'short' });
}

function CircularProgress({
  value,
  max,
  size = 120,
  strokeWidth = 10,
  color = '#3b82f6',
}: {
  value: number;
  max: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
}) {
  const percentage = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="#e2e8f0" strokeWidth={strokeWidth} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.5s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xl font-bold text-slate-800">{formatCurrency(value)}</span>
        <span className="text-xs text-slate-500">of {formatCurrency(max)}</span>
      </div>
    </div>
  );
}

function SemiCircleProgress({
  value,
  max,
  label,
}: {
  value: number;
  max: number;
  label: string;
}) {
  const percentage = max > 0 ? Math.min((value / max) * 100, 100) : 0;

  return (
    <div className="relative w-full h-32 flex flex-col items-center">
      <div className="relative w-48 h-24 overflow-hidden">
        <div
          className="absolute w-48 h-48 rounded-full border-[16px] border-slate-200"
          style={{ clipPath: 'polygon(0 0, 100% 0, 100% 50%, 0 50%)' }}
        />
        <div
          className="absolute w-48 h-48 rounded-full border-[16px] border-emerald-500"
          style={{
            clipPath: `polygon(0 0, ${percentage}% 0, ${percentage}% 50%, 0 50%)`,
            transition: 'clip-path 0.5s ease',
          }}
        />
      </div>
      <div className="text-center -mt-4">
        <p className="text-2xl font-bold text-emerald-600">{formatCurrency(value)}</p>
        <p className="text-sm text-slate-500">of {formatCurrency(max)}</p>
        <p className="text-xs text-slate-400 mt-1">{label}</p>
      </div>
    </div>
  );
}

export function DashboardView() {
  const {
    mode,
    insights,
    selectedClubId,
    selectedPeriodId,
    selectedPeriod,
    status,
    periodState,
    refresh,
  } = usePlatform();
  const [timeline, setTimeline] = useState<PeriodMetricSummary[]>([]);
  const [clubMetrics, setClubMetrics] = useState<ClubMetricSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [rangeMonths, setRangeMonths] = useState(24);
  const [learnMoreOpen, setLearnMoreOpen] = useState(false);
  const [reviewBusy, setReviewBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const requests: [Promise<ClubMetricSummary[]>, Promise<PeriodMetricSummary[]>] = [
          fetchClubMetrics(),
          selectedClubId ? fetchPeriodMetrics(selectedClubId, rangeMonths) : Promise.resolve([]),
        ];
        const [clubRows, timelineRows] = await Promise.all(requests);
        if (!cancelled) {
          setClubMetrics(clubRows);
          setTimeline(timelineRows);
        }
      } catch (err) {
        if (!cancelled) {
          setError(extractApiErrorMessage(err, 'Failed to load dashboard data.'));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [rangeMonths, selectedClubId, selectedPeriodId, periodState?.closing_nav, periodState?.reconciliation_diff]);

  const orderedTimeline = useMemo(
    () =>
      [...timeline].sort(
        (left, right) =>
          left.year * 100 + left.month - (right.year * 100 + right.month),
      ),
    [timeline],
  );

  const chartData = orderedTimeline.map((period) => ({
    month: toMonthLabel(period.year, period.month),
    nav: toNumber(period.closing_nav) / 1_000_000_000,
    change: toNumber(period.return_pct),
  }));

  const cashFlowData = orderedTimeline.map((period) => ({
    month: toMonthLabel(period.year, period.month),
    inflow: toNumber(period.contributions) / 1_000_000,
    outflow: toNumber(period.withdrawals) / 1_000_000,
  }));

  const totalClubs = clubMetrics.length;
  const activeClubs = clubMetrics.filter((club) => club.is_active).length;
  const totalInvestors = clubMetrics.reduce((sum, club) => sum + club.investor_count, 0);
  const totalAUM = clubMetrics.reduce(
    (sum, club) => sum + toNumber(club.latest_period?.closing_nav ?? '0'),
    0,
  );

  const marketMovers = useMemo(
    () =>
      clubMetrics
        .filter((club) => club.latest_period !== null)
        .map((club) => ({
          symbol: `NAV-${club.code}`,
          name: club.name,
          change: toNumber(club.latest_period?.return_pct ?? '0'),
          up: toNumber(club.latest_period?.return_pct ?? '0') >= 0,
        }))
        .sort((left, right) => Math.abs(right.change) - Math.abs(left.change))
        .slice(0, 5),
    [clubMetrics],
  );

  const latestPoint = chartData.length > 0 ? chartData[chartData.length - 1] : null;
  const baselinePoint = chartData.length > 2 ? chartData[chartData.length - 3] : chartData[0];
  const nav90DayChange =
    latestPoint && baselinePoint && baselinePoint.nav > 0
      ? ((latestPoint.nav - baselinePoint.nav) / baselinePoint.nav) * 100
      : 0;
  const nav1DayChange = latestPoint?.change ?? 0;

  const latestPeriod = orderedTimeline.length > 0 ? orderedTimeline[orderedTimeline.length - 1] : null;
  const latestContrib = toNumber(latestPeriod?.contributions);
  const latestWithdraw = toNumber(latestPeriod?.withdrawals);
  const latestIncome = toNumber(latestPeriod?.income);
  const latestExpenses = toNumber(latestPeriod?.expenses);
  const netThisMonth = latestContrib - latestWithdraw;
  const investableCash = latestContrib - latestWithdraw + latestIncome - latestExpenses;

  const annualTarget = totalAUM > 0 ? totalAUM * 1.2 : 3_000_000_000;

  function navigateTo(path: string) {
    window.history.pushState({}, '', path);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }

  function handleToggleRange() {
    setRangeMonths((current) => (current === 24 ? 6 : 24));
  }

  function handleExport() {
    if (!selectedClubId || !selectedPeriodId) {
      setError('Select club and period before exporting.');
      return;
    }
    window.open(getCsvExportUrl(selectedClubId, selectedPeriodId), '_blank', 'noopener,noreferrer');
  }

  async function handleScheduleReview() {
    if (!selectedClubId || !selectedPeriodId) {
      setError('Select club and period before scheduling review.');
      return;
    }
    setReviewBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (status === 'draft') {
        await submitReview(selectedClubId, selectedPeriodId);
        await refresh();
        setMessage('Period submitted for review.');
      } else if (status === 'review') {
        setMessage('Period is already in review.');
      } else {
        setMessage('Period is closed. No further review scheduling is needed.');
      }
      if (selectedPeriod) {
        const yyyymm = `${selectedPeriod.year}${String(selectedPeriod.month).padStart(2, '0')}`;
        navigateTo(`/clubs/${selectedClubId}/periods/${yyyymm}/close`);
      }
    } catch (err) {
      setError(extractApiErrorMessage(err, 'Unable to schedule review.'));
    } finally {
      setReviewBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Overview</h1>
          <p className="text-sm text-slate-500 mt-0.5">Here's what's happening with your portfolio</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-sm"
            onClick={handleToggleRange}
          >
            <Calendar className="w-4 h-4" />
            {rangeMonths === 24 ? 'Last 6 Months' : 'Last 24 Months'}
          </button>
          <button
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-sm"
            onClick={handleExport}
          >
            <Download className="w-4 h-4" />
            Export
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {error}
        </div>
      )}
      {message && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-emerald-700">
          {message}
        </div>
      )}

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-8 space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-800">Net Asset Value</h3>
                <p className="text-sm text-slate-500">Total portfolio value over time</p>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <span className="text-2xl font-bold text-slate-800">{formatCurrency(totalAUM)}</span>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="flex items-center gap-1 text-sm text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
                      <TrendingUp className="w-3.5 h-3.5" />
                      90-Day {nav90DayChange >= 0 ? '+' : ''}
                      {nav90DayChange.toFixed(1)}%
                    </span>
                    <span
                      className={cn(
                        'flex items-center gap-1 text-sm px-2 py-0.5 rounded-full',
                        nav1DayChange >= 0 ? 'text-emerald-600 bg-emerald-50' : 'text-red-500 bg-red-50',
                      )}
                    >
                      {nav1DayChange >= 0 ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                      1-Day {nav1DayChange >= 0 ? '+' : ''}
                      {nav1DayChange.toFixed(1)}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="navGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis
                    stroke="#94a3b8"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${value}B`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'white',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                      padding: '12px',
                    }}
                    labelStyle={{ color: '#64748b', marginBottom: '4px', fontSize: '12px' }}
                    itemStyle={{ color: '#1e293b', fontSize: '13px' }}
                    formatter={(value: number) => [formatCurrency(value * 1_000_000_000), 'NAV']}
                  />
                  <Area type="monotone" dataKey="nav" stroke="#3b82f6" strokeWidth={2} fill="url(#navGradient)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-base font-semibold text-slate-800">Cash Flow</h3>
                  <p className="text-xs text-slate-500">Contributions vs Withdrawals</p>
                </div>
                <div className="text-right">
                  <span className={cn('text-lg font-semibold', netThisMonth >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                    {netThisMonth >= 0 ? '+' : ''}
                    {formatCurrency(netThisMonth)}
                  </span>
                  <p className="text-xs text-slate-500">net this month</p>
                </div>
              </div>
              <div className="h-[200px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={cashFlowData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="month" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis
                      stroke="#94a3b8"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(value) => `${value}M`}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'white',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                        padding: '10px',
                      }}
                      formatter={(value: number) => [formatCurrency(value * 1_000_000)]}
                    />
                    <Bar dataKey="inflow" fill="#10b981" radius={[3, 3, 0, 0]} name="Inflow" />
                    <Bar dataKey="outflow" fill="#ef4444" radius={[3, 3, 0, 0]} name="Outflow" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-slate-500 mt-3 text-center">
                Net cash movement this month:{' '}
                <span className={cn('font-medium', netThisMonth >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                  {formatCurrency(netThisMonth)}
                </span>
              </p>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-base font-semibold text-slate-800">Monthly Budget</h3>
                  <p className="text-xs text-slate-500">Income vs Expenses Target</p>
                </div>
                <button className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
                  <MoreHorizontal className="w-4 h-4" />
                </button>
              </div>
              <div className="flex items-center justify-center py-4">
                <CircularProgress value={latestIncome} max={Math.max(latestIncome + latestExpenses, 1)} size={140} strokeWidth={12} color="#f59e0b" />
              </div>
              <div className="space-y-2 mt-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-500">Income</span>
                  <span className="font-medium text-emerald-600">{formatCurrency(latestIncome)}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-500">Expenses</span>
                  <span className="font-medium text-red-500">{formatCurrency(latestExpenses)}</span>
                </div>
                <div className="flex items-center justify-between text-sm pt-2 border-t border-slate-100">
                  <span className="text-slate-500">Net</span>
                  <span className={cn('font-medium', latestIncome - latestExpenses >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                    {formatCurrency(latestIncome - latestExpenses)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-semibold text-slate-800">Portfolio Balances</h3>
                <p className="text-xs text-slate-500">Club performance over time</p>
              </div>
              <span className="text-lg font-semibold text-emerald-600">{formatCurrency(totalAUM)}</span>
            </div>
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="portfolioGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="month" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis
                    stroke="#94a3b8"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${value}B`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'white',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      padding: '10px',
                    }}
                    formatter={(value: number) => [formatCurrency(value * 1_000_000_000), 'Balance']}
                  />
                  <Area type="monotone" dataKey="nav" stroke="#10b981" strokeWidth={2} fill="url(#portfolioGradient)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4 space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-semibold text-slate-800 mb-4">Key Metrics</h3>
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl">
                <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
                  <Building2 className="w-5 h-5 text-blue-600" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-500">Active Clubs</p>
                  <p className="text-lg font-semibold text-slate-800">
                    {activeClubs} <span className="text-sm font-normal text-slate-400">/ {totalClubs}</span>
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl">
                <div className="w-10 h-10 bg-emerald-100 rounded-xl flex items-center justify-center">
                  <Users className="w-5 h-5 text-emerald-600" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-500">Total Investors</p>
                  <p className="text-lg font-semibold text-slate-800">{totalInvestors}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl">
                <div className="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center">
                  <Activity className="w-5 h-5 text-amber-600" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-500">Monthly Return</p>
                  <p className={cn('text-lg font-semibold', nav1DayChange >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                    {nav1DayChange >= 0 ? '+' : ''}
                    {nav1DayChange.toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-800">Club Performance</h3>
              <button
                className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                onClick={() => navigateTo('/clubs')}
              >
                View All
              </button>
            </div>
            <div className="space-y-3">
              {marketMovers.map((mover) => (
                <div key={mover.symbol} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{mover.symbol}</p>
                    <p className="text-xs text-slate-500">{mover.name}</p>
                  </div>
                  <div className="text-right">
                    <span className={cn('flex items-center gap-1 text-sm font-medium', mover.up ? 'text-emerald-600' : 'text-red-500')}>
                      {mover.up ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                      {mover.up ? '+' : ''}
                      {mover.change.toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-800">Investable Cash</h3>
              <span className={cn('text-lg font-semibold', investableCash >= 0 ? 'text-slate-800' : 'text-red-600')}>
                {formatCurrency(investableCash)}
              </span>
            </div>
            <p className="text-xs text-slate-500 mb-3">Based on current month net movement</p>
            <div className="h-[100px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={cashFlowData.slice(-6)} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                  <Bar dataKey="inflow" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-semibold text-slate-800 mb-2">Annual Target</h3>
            <p className="text-xs text-slate-500 mb-4">Projected year-end NAV</p>
            <SemiCircleProgress value={totalAUM} max={annualTarget} label={`of ${formatCurrency(annualTarget)} target`} />
            <p className="text-xs text-slate-500 text-center mt-2">
              Need <span className="text-emerald-600 font-medium">{formatCurrency(Math.max(annualTarget - totalAUM, 0))}</span> more to hit target
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="h-24 bg-gradient-to-r from-blue-500 to-blue-600 flex items-center justify-center">
              <Newspaper className="w-10 h-10 text-white/80" />
            </div>
            <div className="p-4">
              <h4 className="text-sm font-semibold text-slate-800 mb-1">Operational Recap</h4>
              <p className="text-xs text-slate-500 mb-3">
                Closing NAV and investor balances are sourced from the selected club period snapshot.
              </p>
              <button
                className="text-xs text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1"
                onClick={() => setLearnMoreOpen(true)}
              >
                Read More
                <ChevronRight className="w-3 h-3" />
              </button>
            </div>
          </div>

          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-100 p-5">
            <div className="flex items-start gap-3 mb-3">
              <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center shrink-0">
                <Lightbulb className="w-4 h-4 text-blue-600" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-slate-800">Portfolio Advice</h4>
                <p className="text-xs text-slate-500">Based on current selected period</p>
              </div>
            </div>
            <div className="space-y-2 mb-4">
              <p className="text-sm text-slate-700">- Monitor net cash movement before month close.</p>
              <p className="text-sm text-slate-700">- Review reconciliation stamp before locking the period.</p>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 text-white text-xs"
                onClick={() => setLearnMoreOpen(true)}
              >
                Learn More
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="border-blue-200 text-blue-600 hover:bg-blue-50 text-xs"
                disabled={reviewBusy}
                onClick={() => void handleScheduleReview()}
              >
                Schedule Review
              </Button>
            </div>
          </div>

          {mode === 'intelligent' && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-slate-800">Copilot Insights</h4>
                <span className="text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-700 font-medium">
                  Intelligent
                </span>
              </div>
              <div className="space-y-2">
                {(insights?.items ?? []).length === 0 ? (
                  <p className="text-xs text-slate-500">No anomaly flags for the selected period.</p>
                ) : (
                  insights?.items.map((item) => (
                    <div key={item.code} className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                      <p className="text-xs font-medium text-slate-700">{item.title}</p>
                      <p className="text-xs text-slate-500 mt-0.5">{item.description}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {loading && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 text-xs text-slate-500">
              Loading dashboard metrics...
            </div>
          )}
        </div>
      </div>

      <Dialog open={learnMoreOpen} onOpenChange={setLearnMoreOpen}>
        <DialogContent className="bg-white border-slate-200">
          <DialogHeader>
            <DialogTitle className="text-slate-800">Portfolio Guidance</DialogTitle>
            <DialogDescription className="text-slate-500">
              Guidance for the selected club period.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 text-sm text-slate-700">
            <p>1. Verify contributions and withdrawals in Ledger before moving period to review.</p>
            <p>2. Confirm reconciliation stamp is exact before closing month.</p>
            <p>3. Use reports after close for immutable audit-ready outputs.</p>
          </div>
          <DialogFooter>
            <Button variant="outline" className="border-slate-200 text-slate-700" onClick={() => setLearnMoreOpen(false)}>
              Close
            </Button>
            <Button
              className="bg-blue-600 hover:bg-blue-700 text-white"
              onClick={() => {
                setLearnMoreOpen(false);
                navigateTo('/clubs');
              }}
            >
              View Clubs
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
