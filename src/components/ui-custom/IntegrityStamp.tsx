import { cn, formatCurrency } from '@/lib/utils';
import type { AnalyticsIntegrityStamp } from '@/types/platform';

interface IntegrityStampProps {
  integrity: AnalyticsIntegrityStamp | null;
}

export function IntegrityStamp({ integrity }: IntegrityStampProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
      <h3 className="text-base font-semibold text-slate-800 mb-2">Integrity</h3>
      <p
        className={cn(
          'text-sm font-medium',
          integrity?.reconciled ? 'text-emerald-600' : 'text-red-500',
        )}
      >
        {integrity?.stamp ?? 'Reconciliation pending'}
      </p>
      <p className="text-xs text-slate-500 mt-1">
        Mismatch: {formatCurrency(Number(integrity?.mismatch_ugx ?? 0))}
      </p>
      {(integrity?.reasons ?? []).length > 0 && (
        <div className="mt-2 p-2 rounded-lg bg-red-50 border border-red-100 space-y-1">
          {integrity?.reasons.map((reason, index) => (
            <p key={`${reason}-${index}`} className="text-xs text-red-600">
              {reason}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
