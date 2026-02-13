import { useMemo, useState } from 'react';
import { Bot, Sparkles, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { usePlatform } from '@/context/PlatformContext';
import { CopilotChat } from '@/components/ui-custom/CopilotChat';

export function FloatingCopilotWidget() {
  const [open, setOpen] = useState(false);
  const { mode, selectedClubId, selectedPeriodId, selectedPeriod } = usePlatform();

  const periodLabel = useMemo(
    () =>
      selectedPeriod
        ? `${selectedPeriod.year}-${String(selectedPeriod.month).padStart(2, '0')}`
        : 'No period',
    [selectedPeriod],
  );

  if (mode !== 'intelligent') {
    return null;
  }

  return (
    <div className="fixed bottom-6 right-6 z-[60]">
      {open && (
        <div className="mb-3 w-[360px] sm:w-[420px] h-[620px] max-h-[78vh] bg-white rounded-2xl border border-slate-200 shadow-xl overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center">
                <Bot className="w-4 h-4" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800">Floating Copilot</p>
                <p className="text-xs text-slate-500">Club/period scoped assistant</p>
              </div>
            </div>
            <button
              className="p-1.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg"
              onClick={() => setOpen(false)}
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-3">
            <CopilotChat
              clubId={selectedClubId}
              periodId={selectedPeriodId}
              periodLabel={periodLabel}
            />
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((state) => !state)}
        className={cn(
          'h-12 px-4 rounded-full border shadow-lg transition-colors flex items-center gap-2',
          open
            ? 'bg-white text-slate-700 border-slate-200'
            : 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700',
        )}
      >
        <Sparkles className="w-4 h-4" />
        <span className="text-sm font-medium">Co Pilot</span>
      </button>
    </div>
  );
}
