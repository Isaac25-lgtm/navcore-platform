import { useMemo, useState } from 'react';
import { AlertCircle, Bot, CheckCircle2, Circle, Lock, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn, formatCurrency } from '@/lib/utils';
import { extractApiErrorMessage } from '@/lib/feedback';
import { closeMonth, submitReview } from '@/lib/api';
import { usePlatform } from '@/context/PlatformContext';

export function CloseMonthView() {
  const {
    selectedClubId,
    selectedPeriodId,
    checklist,
    reconciliation,
    reconciliationDetails,
    periodState,
    status,
    mode,
    insights,
    refresh,
    locked,
  } = usePlatform();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const checklistRows = useMemo(() => {
    if (!checklist) return [];
    return [
      { key: 'has_positions', label: 'Investor positions exist', pass: checklist.checklist.has_positions },
      { key: 'has_ledger_entries', label: 'Ledger entries posted', pass: checklist.checklist.has_ledger_entries },
      { key: 'submitted_for_review', label: 'Submitted for review', pass: checklist.checklist.submitted_for_review },
      { key: 'reconciled', label: 'Reconciliation exact', pass: checklist.checklist.reconciled },
      { key: 'not_already_closed', label: 'Period not already closed', pass: checklist.checklist.not_already_closed },
    ];
  }, [checklist]);

  async function handleSubmitReview() {
    if (!selectedClubId || !selectedPeriodId || locked) return;
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await submitReview(selectedClubId, selectedPeriodId);
      await refresh();
      setMessage('Submitted for review. Next step: ensure reconciliation is exact, then run close.');
    } catch (err) {
      setError(extractApiErrorMessage(err, 'Unable to submit review.'));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCloseMonth() {
    if (!selectedClubId || !selectedPeriodId) return;
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await closeMonth(selectedClubId, selectedPeriodId);
      await refresh();
      setMessage('Month closed successfully. Period is now locked and ready for report generation.');
    } catch (err) {
      setError(extractApiErrorMessage(err, 'Unable to close month.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Close Month</h1>
          <p className="text-sm text-slate-500 mt-0.5">Checklist and reconciliation gate before locking the period</p>
        </div>
      </div>

      {locked && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center gap-3">
          <Lock className="w-5 h-5 text-emerald-600" />
          <p className="text-sm text-emerald-700">This month is closed and permanently locked.</p>
        </div>
      )}

      {message && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-emerald-700">
          {message}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-slate-800">Close Checklist</h3>
            <span
              className={cn(
                'text-xs px-2 py-1 rounded-full font-medium',
                checklist?.can_close ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700',
              )}
            >
              {checklist?.can_close ? 'Ready to Close' : 'Action Required'}
            </span>
          </div>
          <div className="space-y-3">
            {checklistRows.map((item) => (
              <div key={item.key} className="flex items-center justify-between p-3 rounded-xl bg-slate-50">
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      'w-8 h-8 rounded-full flex items-center justify-center',
                      item.pass ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-100 text-slate-400',
                    )}
                  >
                    {item.pass ? <CheckCircle2 className="w-4 h-4" /> : <Circle className="w-4 h-4" />}
                  </div>
                  <p className="text-sm text-slate-700">{item.label}</p>
                </div>
                <span className={cn('text-xs font-medium', item.pass ? 'text-emerald-600' : 'text-slate-500')}>
                  {item.pass ? 'PASS' : 'PENDING'}
                </span>
              </div>
            ))}
          </div>

          <div className="mt-5 p-4 rounded-xl border border-slate-200 bg-slate-50">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-slate-500 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-slate-700">Formula</p>
                <p className="text-sm text-slate-600">
                  Opening NAV + Contributions - Withdrawals + Income - Expenses = Closing NAV
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-base font-semibold text-slate-800 mb-4">Reconciliation</h3>
            <div className="space-y-2">
              <p className="text-sm text-slate-500">Stamp</p>
              <p
                className={cn(
                  'text-sm font-semibold',
                  reconciliation?.reconciled ? 'text-emerald-600' : 'text-red-500',
                )}
              >
                {reconciliation?.stamp ?? 'Not available'}
              </p>
              <p className="text-xs text-slate-500">
                Mismatch: {formatCurrency(Number(reconciliation?.mismatch_ugx ?? 0))}
              </p>
              <p className="text-xs text-slate-500">
                Club Closing NAV: {formatCurrency(Number(periodState?.closing_nav ?? 0))}
              </p>
              {(reconciliationDetails?.reasons ?? []).length > 0 && (
                <div className="mt-2 p-2 rounded-lg bg-red-50 border border-red-100">
                  {(reconciliationDetails?.reasons ?? []).map((reason, index) => (
                    <p key={`${reason}-${index}`} className="text-xs text-red-600">
                      {reason}
                    </p>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-base font-semibold text-slate-800 mb-4">Actions</h3>
            <div className="space-y-2">
              <Button
                onClick={handleSubmitReview}
                disabled={submitting || locked || status !== 'draft'}
                variant="outline"
                className="w-full border-slate-200 text-slate-700"
              >
                Submit for Review
              </Button>
              <Button
                onClick={handleCloseMonth}
                disabled={submitting || locked || !checklist?.can_close}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white"
              >
                Run Close
              </Button>
              {error && <p className="text-xs text-red-600">{error}</p>}
            </div>
          </div>
        </div>
      </div>

      {mode === 'intelligent' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-slate-800 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-blue-500" />
              Intelligent Mode
            </h3>
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <Bot className="w-3 h-3" />
              Copilot enabled
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-xl border border-slate-200 p-4 bg-slate-50">
              <p className="text-sm font-medium text-slate-700 mb-2">Anomaly Flags</p>
              <div className="space-y-2">
                {(insights?.items ?? []).length === 0 && (insights?.anomalies ?? []).length === 0 ? (
                  <p className="text-xs text-slate-500">No anomalies for this period.</p>
                ) : (
                  <>
                    {(insights?.items ?? []).map((item) => (
                      <div key={item.code} className="text-xs text-slate-600">
                        <span className="font-medium">{item.title}:</span> {item.description}
                      </div>
                    ))}
                    {(insights?.anomalies ?? []).map((item) => (
                      <div key={item.code} className="text-xs text-red-600">
                        <span className="font-medium">{item.code}:</span> {item.message}
                      </div>
                    ))}
                  </>
                )}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 p-4 bg-slate-50">
              <p className="text-sm font-medium text-slate-700 mb-2">Scenario Sandbox</p>
              <p className="text-xs text-slate-500">
                Scenario and Copilot actions are active in intelligent mode and use current ledger state for simulation.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
