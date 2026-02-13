import { AlertCircle, Lock } from 'lucide-react';
import { usePlatform } from '@/context/PlatformContext';
import { CopilotChat } from '@/components/ui-custom/CopilotChat';

export function CopilotView() {
  const { selectedClubId, selectedPeriodId, selectedPeriod, mode, status, locked } = usePlatform();
  const periodLabel = selectedPeriod
    ? `${selectedPeriod.year}-${String(selectedPeriod.month).padStart(2, '0')}`
    : 'No period';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Copilot</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Gemini-powered read-only assistant scoped to selected club and period
          </p>
        </div>
      </div>

      {status !== 'closed' && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-xs text-blue-700">
          Preview mode active. Copilot answers are based on draft/review data for {periodLabel}.
        </div>
      )}

      {locked && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center gap-3">
          <Lock className="w-5 h-5 text-emerald-600" />
          <p className="text-sm text-emerald-700">
            This period is locked. Copilot remains read-only and cannot modify records.
          </p>
        </div>
      )}

      {mode !== 'intelligent' ? (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-800">Intelligent Mode Required</p>
            <p className="text-sm text-amber-700">
              Turn on Intelligent Mode in the top bar to use Copilot.
            </p>
          </div>
        </div>
      ) : (
        <CopilotChat clubId={selectedClubId} periodId={selectedPeriodId} periodLabel={periodLabel} />
      )}
    </div>
  );
}
