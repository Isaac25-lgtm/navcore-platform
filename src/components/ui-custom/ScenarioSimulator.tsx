import { useMemo, useState } from 'react';
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
import { Input } from '@/components/ui/input';
import { formatCurrency } from '@/lib/utils';
import type { ScenarioProjectionResponse } from '@/types/platform';

interface ScenarioRunPayload {
  monthly_contribution: number;
  monthly_withdrawal: number;
  annual_yield_low_pct: number;
  annual_yield_high_pct: number;
  expense_rate_pct: number;
  months: number;
  goal_target_amount?: number | null;
  goal_target_date?: string | null;
}

interface ScenarioSimulatorProps {
  scenario: ScenarioProjectionResponse | null;
  disabled: boolean;
  running: boolean;
  onRun: (payload: ScenarioRunPayload) => Promise<void>;
}

function toNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function toNumberLoose(value: string | number | null | undefined): number {
  if (typeof value === 'number') return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

export function ScenarioSimulator({ scenario, disabled, running, onRun }: ScenarioSimulatorProps) {
  const [monthlyContribution, setMonthlyContribution] = useState('0');
  const [monthlyWithdrawal, setMonthlyWithdrawal] = useState('0');
  const [yieldLow, setYieldLow] = useState('6');
  const [yieldHigh, setYieldHigh] = useState('14');
  const [expenseRate, setExpenseRate] = useState('1.5');
  const [months, setMonths] = useState('24');
  const [goalAmount, setGoalAmount] = useState('');
  const [goalDate, setGoalDate] = useState('');

  const scenarioData = useMemo(
    () =>
      (scenario?.projection ?? []).map((row) => ({
        month: row.month_index,
        base: Number(row.base_nav),
        low: Number(row.low_band_nav),
        high: Number(row.high_band_nav),
      })),
    [scenario?.projection],
  );

  const explanation = useMemo(() => {
    if (!scenario || scenario.projection.length === 0) return null;
    const last = scenario.projection[scenario.projection.length - 1];
    const annualLow = toNumberLoose(scenario.assumptions.annual_yield_low_pct as string | number);
    const annualHigh = toNumberLoose(scenario.assumptions.annual_yield_high_pct as string | number);
    const expenseRateAssumed = toNumberLoose(scenario.assumptions.expense_rate_pct as string | number);
    const monthlyContributionAssumed = toNumberLoose(
      scenario.assumptions.monthly_contribution as string | number,
    );
    const monthlyWithdrawalAssumed = toNumberLoose(
      scenario.assumptions.monthly_withdrawal as string | number,
    );
    const netMonthlyFlow = monthlyContributionAssumed - monthlyWithdrawalAssumed;
    const best = Number(last.best_nav);
    const base = Number(last.base_nav);
    const worst = Number(last.worst_nav);
    const band = best - worst;
    const monthsHorizon =
      toNumberLoose(scenario.assumptions.months as string | number) || scenario.projection.length;

    return {
      annualLow,
      annualHigh,
      expenseRateAssumed,
      monthlyContributionAssumed,
      monthlyWithdrawalAssumed,
      netMonthlyFlow,
      best,
      base,
      worst,
      band,
      monthsHorizon,
    };
  }, [scenario]);

  const horizonBars = useMemo(() => {
    if (!explanation) return [];
    return [
      { name: 'Worst', value: explanation.worst, color: '#ef4444' },
      { name: 'Base', value: explanation.base, color: '#2563eb' },
      { name: 'Best', value: explanation.best, color: '#10b981' },
    ];
  }, [explanation]);

  async function run() {
    await onRun({
      monthly_contribution: toNumber(monthlyContribution),
      monthly_withdrawal: toNumber(monthlyWithdrawal),
      annual_yield_low_pct: toNumber(yieldLow),
      annual_yield_high_pct: toNumber(yieldHigh),
      expense_rate_pct: toNumber(expenseRate),
      months: Math.max(12, Math.min(36, Math.round(toNumber(months) || 24))),
      goal_target_amount: goalAmount.trim() ? toNumber(goalAmount) : null,
      goal_target_date: goalDate.trim() || null,
    });
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-800">Scenario Simulator</h3>
          <p className="text-xs text-slate-500">Deterministic what-if projection for 12-36 months.</p>
        </div>
        <Button
          className="bg-blue-600 hover:bg-blue-700 text-white"
          onClick={() => void run()}
          disabled={disabled || running}
        >
          Run Scenario
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Input value={monthlyContribution} onChange={(event) => setMonthlyContribution(event.target.value)} placeholder="Monthly contribution" className="bg-white border-slate-200" />
        <Input value={monthlyWithdrawal} onChange={(event) => setMonthlyWithdrawal(event.target.value)} placeholder="Monthly withdrawal" className="bg-white border-slate-200" />
        <Input value={yieldLow} onChange={(event) => setYieldLow(event.target.value)} placeholder="Yield low %" className="bg-white border-slate-200" />
        <Input value={yieldHigh} onChange={(event) => setYieldHigh(event.target.value)} placeholder="Yield high %" className="bg-white border-slate-200" />
        <Input value={expenseRate} onChange={(event) => setExpenseRate(event.target.value)} placeholder="Expense rate %" className="bg-white border-slate-200" />
        <Input value={months} onChange={(event) => setMonths(event.target.value)} placeholder="Months (12-36)" className="bg-white border-slate-200" />
        <Input value={goalAmount} onChange={(event) => setGoalAmount(event.target.value)} placeholder="Goal amount (optional)" className="bg-white border-slate-200" />
        <Input value={goalDate} onChange={(event) => setGoalDate(event.target.value)} placeholder="Goal date YYYY-MM" className="bg-white border-slate-200" />
      </div>
      <p className="text-xs text-slate-500 mt-3">
        Assumptions: no black-box ML, monthly compounding from selected period NAV, explicit yield and expense rates.
      </p>

      {scenarioData.length > 0 && (
        <div className="h-[280px] mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={scenarioData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="scenarioBandIntelligence" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#93c5fd" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#93c5fd" stopOpacity={0.1} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(value) => `${Math.round(value / 1_000_000)}M`} />
              <Tooltip
                contentStyle={{ backgroundColor: 'white', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px' }}
                formatter={(value: number) => [formatCurrency(value), '']}
              />
              <Area type="monotone" dataKey="high" stroke="#60a5fa" fill="url(#scenarioBandIntelligence)" />
              <Area type="monotone" dataKey="low" stroke="#93c5fd" fillOpacity={0} />
              <Area type="monotone" dataKey="base" stroke="#2563eb" fillOpacity={0} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {scenario?.goal && (
        <div className="mt-4 p-3 rounded-xl bg-blue-50 border border-blue-200">
          <p className="text-xs text-blue-700">
            Goal {scenario.goal.target_date}: need {formatCurrency(Number(scenario.goal.required_monthly_contribution))} monthly contribution
            to target {formatCurrency(Number(scenario.goal.target_amount))}.
          </p>
        </div>
      )}

      {explanation && (
        <div className="mt-4 bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-4">
          <div>
            <p className="text-sm font-semibold text-slate-800">Scenario Explanation</p>
            <p className="text-xs text-slate-500 mt-0.5">
              What this run means for your selected horizon and assumptions.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Base outcome ({explanation.monthsHorizon} months)</p>
              <p className="text-sm font-semibold text-blue-700 mt-1">{formatCurrency(explanation.base)}</p>
              <p className="text-xs text-slate-500 mt-1">
                Yield range {explanation.annualLow.toFixed(2)}% - {explanation.annualHigh.toFixed(2)}% per year.
              </p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Sensitivity band</p>
              <p className="text-sm font-semibold text-slate-700 mt-1">{formatCurrency(explanation.band)}</p>
              <p className="text-xs text-slate-500 mt-1">
                Best {formatCurrency(explanation.best)} vs worst {formatCurrency(explanation.worst)}.
              </p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Net monthly flow</p>
              <p className={`text-sm font-semibold mt-1 ${explanation.netMonthlyFlow >= 0 ? 'text-emerald-700' : 'text-red-600'}`}>
                {explanation.netMonthlyFlow >= 0 ? '+' : '-'}
                {formatCurrency(Math.abs(explanation.netMonthlyFlow))}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Contribution {formatCurrency(explanation.monthlyContributionAssumed)} vs withdrawal {formatCurrency(explanation.monthlyWithdrawalAssumed)}.
              </p>
            </div>
          </div>

          <div className="h-[170px] bg-white rounded-xl border border-slate-200 p-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={horizonBars} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(value) => `${Math.round(value / 1_000_000)}M`} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'white', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px' }}
                  formatter={(value: number) => [formatCurrency(value), 'Projected NAV']}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {horizonBars.map((row) => (
                    <Cell key={row.name} fill={row.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-3">
            <p className="text-xs text-slate-700">
              Interpretation: This scenario is deterministic. It uses yield assumptions and an annual expense rate of {explanation.expenseRateAssumed.toFixed(2)}%.
              If net monthly flow is negative for long periods, future NAV depends more heavily on yield performance.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
