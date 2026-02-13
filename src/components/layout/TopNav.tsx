import { cn } from '@/lib/utils';
import {
  Bell,
  Search,
  User,
  Menu,
  ChevronDown,
  Settings,
  LogOut,
  Lock,
  Moon,
  Sun,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { usePlatform } from '@/context/PlatformContext';
import { ModeToggle } from '@/components/ui-custom/ModeToggle';

interface TopNavProps {
  activeView: string;
  onViewChange: (view: string) => void;
  onToggleSidebar: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

const basicNavItems = [
  { id: 'dashboard', label: 'Overview' },
  { id: 'clubs', label: 'Clubs' },
  { id: 'investors', label: 'Investors' },
  { id: 'ledger', label: 'Ledger' },
  { id: 'reports', label: 'Reports' },
  { id: 'close-month', label: 'Close Month' },
];

const intelligentNavItems = [
  { id: 'analysis', label: 'Analysis' },
  { id: 'copilot', label: 'Copilot' },
];

export function TopNav({ activeView, onViewChange, onToggleSidebar, theme, onToggleTheme }: TopNavProps) {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [modeNotice, setModeNotice] = useState<string | null>(null);
  const {
    clubs,
    periods,
    selectedClubId,
    selectedPeriodId,
    status,
    locked,
    reconciliation,
    mode,
    setMode,
    setSelectedClubId,
    setSelectedPeriodId,
  } = usePlatform();
  const navItems = mode === 'intelligent' ? [...basicNavItems, ...intelligentNavItems] : basicNavItems;

  const statusClass = useMemo(
    () =>
      cn(
        'text-xs px-2 py-1 rounded-full font-medium',
        status === 'draft' && 'bg-slate-100 text-slate-700',
        status === 'review' && 'bg-amber-100 text-amber-700',
        status === 'closed' && 'bg-emerald-100 text-emerald-700',
      ),
    [status],
  );

  useEffect(() => {
    if (!modeNotice) return;
    const timer = window.setTimeout(() => setModeNotice(null), 3200);
    return () => window.clearTimeout(timer);
  }, [modeNotice]);

  function handleModeChange(nextMode: 'basic' | 'intelligent') {
    setMode(nextMode);
    setModeNotice(
      nextMode === 'intelligent'
        ? 'You are now in Intelligent Mode. Insights, scenarios, forecasts, and Copilot are active.'
        : 'You are now in Basic Mode. Core operations are active and AI features are hidden.',
    );
  }

  return (
    <>
      <header className="fixed top-0 left-0 right-0 z-50 bg-gradient-to-r from-slate-800 to-slate-900 h-16">
      <div className="flex items-center h-full px-4 gap-3">
        <div className="flex items-center gap-3 w-64">
          <button
            onClick={onToggleSidebar}
            className="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-400 to-blue-500 rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/30">
              <span className="text-white font-bold text-sm">N</span>
            </div>
            <span className="font-semibold text-white">NAVFund</span>
          </div>
        </div>

        <nav className="hidden xl:flex items-center gap-1 flex-1 justify-center">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={cn(
                'px-3 py-2 text-sm font-medium rounded-lg transition-all',
                activeView === item.id
                  ? 'text-white bg-white/15'
                  : 'text-slate-300 hover:text-white hover:bg-white/10',
              )}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-2 max-w-[58vw] overflow-x-auto">
          <Select
            value={selectedClubId ? String(selectedClubId) : ''}
            onValueChange={(value) => setSelectedClubId(Number(value))}
          >
            <SelectTrigger className="h-9 w-[120px] sm:w-[180px] bg-white/5 border-white/10 text-slate-200 text-xs">
              <SelectValue placeholder="Club" />
            </SelectTrigger>
            <SelectContent>
              {clubs.map((club) => (
                <SelectItem key={club.id} value={String(club.id)}>
                  {club.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={selectedPeriodId ? String(selectedPeriodId) : ''}
            onValueChange={(value) => setSelectedPeriodId(Number(value))}
          >
            <SelectTrigger className="h-9 w-[100px] sm:w-[130px] bg-white/5 border-white/10 text-slate-200 text-xs">
              <SelectValue placeholder="Period" />
            </SelectTrigger>
            <SelectContent>
              {periods.map((period) => (
                <SelectItem key={period.id} value={String(period.id)}>
                  {period.year}-{String(period.month).padStart(2, '0')}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <span className={statusClass}>{status.toUpperCase()}</span>
          <span
            className={cn(
              'text-xs px-2 py-1 rounded-full font-medium',
              reconciliation?.reconciled ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700',
            )}
          >
            {reconciliation?.stamp ?? 'Reconcile pending'}
          </span>
          {locked && (
            <span className="text-xs px-2 py-1 rounded-full font-medium bg-amber-100 text-amber-700 flex items-center gap-1">
              <Lock className="w-3 h-3" />
              Read-only
            </span>
          )}
          <ModeToggle mode={mode} onChange={handleModeChange} />
          <button
            onClick={onToggleTheme}
            className={cn(
              'h-9 px-3 text-xs rounded-lg border transition-colors flex items-center gap-1.5',
              theme === 'dark'
                ? 'bg-slate-700/60 text-slate-100 border-slate-500/60'
                : 'bg-white/5 text-slate-300 border-white/10',
            )}
          >
            {theme === 'dark' ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
            {theme === 'dark' ? 'Night' : 'Day'}
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button className="hidden md:inline-flex p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
            <Search className="w-5 h-5" />
          </button>
          <button className="hidden md:inline-flex p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors relative">
            <Bell className="w-5 h-5" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-slate-800" />
          </button>
          <div className="h-6 w-px bg-slate-700 mx-1" />

          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-2 p-1.5 pr-3 hover:bg-white/10 rounded-lg transition-colors"
            >
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center">
                <User className="w-4 h-4 text-white" />
              </div>
              <span className="text-sm text-slate-300 hidden sm:block">Administrator</span>
              <ChevronDown className="w-4 h-4 text-slate-400 hidden sm:block" />
            </button>

            {showUserMenu && (
              <div className="absolute right-0 top-full mt-2 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-2 animate-fade-in">
                <div className="px-4 py-2 border-b border-slate-100">
                  <p className="text-sm font-medium text-slate-800">Administrator</p>
                  <p className="text-xs text-slate-500">admin@navfund.com</p>
                </div>
                <button className="w-full flex items-center gap-3 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 transition-colors">
                  <Settings className="w-4 h-4" />
                  Settings
                </button>
                <button className="w-full flex items-center gap-3 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 transition-colors">
                  <LogOut className="w-4 h-4" />
                  Sign Out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      </header>
      {modeNotice && (
        <div className="fixed top-20 right-4 z-[70] bg-white border border-slate-200 shadow-lg rounded-xl px-4 py-3 max-w-md">
          <p className="text-xs text-slate-700">{modeNotice}</p>
        </div>
      )}
    </>
  );
}
