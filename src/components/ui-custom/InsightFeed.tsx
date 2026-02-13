import { AlertCircle, CheckCircle2, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { AnalyticsAnomaly, InsightItem, Severity } from '@/types/platform';

interface InsightFeedProps {
  insights: InsightItem[];
  anomalies: AnalyticsAnomaly[];
}

function levelClass(level: Severity) {
  if (level === 'critical') {
    return {
      card: 'border-red-200',
      iconWrap: 'bg-red-100',
      icon: <AlertCircle className="w-5 h-5 text-red-600" />,
      text: 'text-red-600',
    };
  }
  if (level === 'warn') {
    return {
      card: 'border-amber-200',
      iconWrap: 'bg-amber-100',
      icon: <AlertCircle className="w-5 h-5 text-amber-600" />,
      text: 'text-amber-600',
    };
  }
  return {
    card: 'border-emerald-200',
    iconWrap: 'bg-emerald-100',
    icon: <CheckCircle2 className="w-5 h-5 text-emerald-600" />,
    text: 'text-emerald-600',
  };
}

export function InsightFeed({ insights, anomalies }: InsightFeedProps) {
  const combined = [
    ...insights.map((item) => ({
      key: `insight-${item.code}`,
      title: item.title,
      description: item.description,
      evidence: item.evidence,
      level: item.severity,
      tag: 'Insight',
      drilldownPath: item.drilldown_path,
    })),
    ...anomalies.map((item) => ({
      key: `anomaly-${item.code}`,
      title: item.title,
      description: item.message,
      evidence: item.evidence,
      level: item.severity,
      tag: 'Anomaly',
      drilldownPath: item.drilldown_path,
    })),
  ];

  if (combined.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center">
            <Info className="w-4 h-4 text-slate-500" />
          </div>
          <p className="text-sm text-slate-500">No insights or anomalies for this period.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {combined.map((item) => {
        const style = levelClass(item.level);
        return (
          <div key={item.key} className={cn('bg-white rounded-xl shadow-sm border p-5', style.card)}>
            <div className="flex items-start gap-3">
              <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center shrink-0', style.iconWrap)}>
                {style.icon}
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <h4 className="font-semibold text-slate-800 capitalize">{item.title}</h4>
                  <span className={cn('text-xs font-medium uppercase', style.text)}>{item.tag}</span>
                </div>
                <p className="text-sm text-slate-500">{item.description}</p>
                <p className="text-xs text-slate-500 mt-2">Evidence: {item.evidence}</p>
                <button
                  className="text-xs text-blue-600 hover:text-blue-700 mt-2"
                  onClick={() => {
                    if (!item.drilldownPath) return;
                    window.history.pushState({}, '', item.drilldownPath);
                    window.dispatchEvent(new PopStateEvent('popstate'));
                  }}
                >
                  Drill-down
                </button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
