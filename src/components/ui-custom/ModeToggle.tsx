import { Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Mode } from '@/types/platform';

interface ModeToggleProps {
  mode: Mode;
  onChange: (mode: Mode) => void;
}

export function ModeToggle({ mode, onChange }: ModeToggleProps) {
  return (
    <button
      onClick={() => onChange(mode === 'basic' ? 'intelligent' : 'basic')}
      className={cn(
        'h-9 px-3 text-xs rounded-lg border transition-colors flex items-center gap-1.5',
        mode === 'intelligent'
          ? 'bg-blue-500/20 text-blue-200 border-blue-400/40'
          : 'bg-white/5 text-slate-300 border-white/10',
      )}
    >
      <Sparkles className="w-3.5 h-3.5" />
      {mode === 'intelligent' ? 'Intelligent' : 'Basic'}
    </button>
  );
}
