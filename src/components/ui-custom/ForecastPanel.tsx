import { useMemo, useState } from 'react';
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Button } from '@/components/ui/button';
import { formatCurrency } from '@/lib/utils';
import type { ForecastResponse } from '@/types/platform';

interface ForecastPanelProps {
  forecast: ForecastResponse | null;
  disabled: boolean;
  loading: boolean;
  onRun: (months: number) => Promise<void>;
}

export function ForecastPanel({ forecast, disabled, loading, onRun }: ForecastPanelProps) {
  const [months, setMonths] = useState(12);

  const chartData = useMemo(
    () =>
      (forecast?.points ?? []).map((row) => ({
        month: row.month_index,
        rolling: Number(row.rolling_forecast_nav),
        regression: Number(row.regression_forecast_nav),
        low: Number(row.low_band_nav),
        high: Number(row.high_band_nav),
      })),
    [forecast?.points],
  );

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-800">Forecast</h3>
          <p className="text-xs text-slate-500">Explainable projection with confidence bands.</p>
        </div>
        <div className="flex items-center gap-2">
          {[12, 18, 24, 36].map((option) => (
            <button
              key={option}
              className={`text-xs px-2 py-1 rounded-lg border ${months === option ? 'bg-blue-50 border-blue-200 text-blue-700' : 'bg-white border-slate-200 text-slate-600'}`}
              onClick={() => setMonths(option)}
            >
              {option}m
            </button>
          ))}
          <Button
            className="bg-blue-600 hover:bg-blue-700 text-white"
            disabled={disabled || loading}
            onClick={() => void onRun(months)}
          >
            Run Forecast
          </Button>
        </div>
      </div>

      {forecast && (
        <div className="mb-3 p-3 rounded-xl bg-slate-50 border border-slate-200">
          <p className="text-xs text-slate-700">Method: {forecast.method}</p>
          <p className="text-xs text-slate-500 mt-1">{forecast.explanation}</p>
        </div>
      )}

      {chartData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(value) => `${Math.round(value / 1_000_000)}M`} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'white', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px' }}
                  formatter={(value: number) => [formatCurrency(value), '']}
                />
                <Line type="monotone" dataKey="rolling" stroke="#0ea5e9" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="regression" stroke="#2563eb" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="forecastBand" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#bfdbfe" stopOpacity={0.5} />
                    <stop offset="95%" stopColor="#bfdbfe" stopOpacity={0.1} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(value) => `${Math.round(value / 1_000_000)}M`} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'white', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px' }}
                  formatter={(value: number) => [formatCurrency(value), '']}
                />
                <Area type="monotone" dataKey="high" stroke="#60a5fa" fill="url(#forecastBand)" />
                <Area type="monotone" dataKey="low" stroke="#93c5fd" fillOpacity={0} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
