import { Sparkles } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { Mode } from '@/types/platform';

interface ModeToggleProps {
  mode: Mode;
  onChange: (mode: Mode) => void;
}

export function ModeToggle({ mode, onChange }: ModeToggleProps) {
  const modeLabel = mode === 'intelligent' ? 'Intelligent Mode' : 'Basic Mode';

  return (
    <div className="flex items-center gap-1.5">
      <Sparkles className="w-3.5 h-3.5 text-blue-300" />
      <Select value={mode} onValueChange={(value) => onChange(value as Mode)}>
        <SelectTrigger className="h-9 w-[158px] bg-white/5 border-white/10 text-slate-200 text-xs">
          <SelectValue aria-label={modeLabel}>{modeLabel}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="basic">Basic Mode</SelectItem>
          <SelectItem value="intelligent">Intelligent Mode</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
