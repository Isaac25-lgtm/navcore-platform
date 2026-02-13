import { cn, formatCurrency } from '@/lib/utils';
import {
  Building2,
  TrendingUp,
  CreditCard,
  FileText,
  BookText,
  ShieldCheck,
  PieChart,
  Users,
  BarChart3,
  ChevronRight,
  ChevronDown,
  Plus,
  Wallet,
  PiggyBank,
  TrendingDown,
  Bot,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { fetchClubMetrics } from '@/lib/api';
import type { ClubMetricSummary } from '@/types/platform';
import { usePlatform } from '@/context/PlatformContext';

interface SidebarProps {
  activeView: string;
  onViewChange: (view: string) => void;
  collapsed: boolean;
}

function toNumber(value: string | null | undefined): number {
  if (!value) return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function Sidebar({ activeView, onViewChange, collapsed }: SidebarProps) {
  const { selectedClubId, selectedPeriodId, periodState, mode } = usePlatform();
  const [expandedSections, setExpandedSections] = useState({
    clubs: true,
    investments: true,
    expenses: true,
  });
  const [clubs, setClubs] = useState<ClubMetricSummary[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const rows = await fetchClubMetrics();
        if (!cancelled) {
          setClubs(rows);
        }
      } catch {
        if (!cancelled) {
          setClubs([]);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [selectedClubId, selectedPeriodId, periodState?.closing_nav, periodState?.reconciliation_diff]);

  const clubAccounts = useMemo(
    () =>
      clubs.map((club) => ({
        id: club.id,
        name: club.name,
        balance: toNumber(club.latest_period?.closing_nav ?? '0'),
        change: toNumber(club.latest_period?.return_pct ?? '0'),
      })),
    [clubs],
  );

  const investmentAccounts = useMemo(
    () =>
      [...clubAccounts]
        .sort((left, right) => right.change - left.change)
        .slice(0, 4),
    [clubAccounts],
  );

  const expenseAccounts = useMemo(
    () =>
      clubs
        .filter((club) => club.latest_period !== null)
        .map((club) => ({
          id: club.id,
          name: `${club.name} Expenses`,
          balance: -toNumber(club.latest_period?.expenses ?? '0'),
        }))
        .sort((left, right) => left.balance - right.balance)
        .slice(0, 4),
    [clubs],
  );

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections((previous) => ({ ...previous, [section]: !previous[section] }));
  };

  const totalNAV = clubAccounts.reduce((sum, account) => sum + account.balance, 0);
  const totalExpenses = expenseAccounts.reduce((sum, account) => sum + account.balance, 0);
  const netWorth = totalNAV + totalExpenses;

  if (collapsed) {
    return (
      <aside className="fixed left-0 top-16 bottom-0 w-16 bg-white border-r border-slate-200 z-40">
        <div className="p-2 space-y-1">
          <button
            onClick={() => onViewChange('dashboard')}
            className={cn(
              'w-10 h-10 flex items-center justify-center rounded-xl transition-colors',
              activeView === 'dashboard' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-100',
            )}
          >
            <PieChart className="w-5 h-5" />
          </button>
          <button
            onClick={() => onViewChange('clubs')}
            className={cn(
              'w-10 h-10 flex items-center justify-center rounded-xl transition-colors',
              activeView === 'clubs' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-100',
            )}
          >
            <Building2 className="w-5 h-5" />
          </button>
          <button
            onClick={() => onViewChange('investors')}
            className={cn(
              'w-10 h-10 flex items-center justify-center rounded-xl transition-colors',
              activeView === 'investors' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-100',
            )}
          >
            <Users className="w-5 h-5" />
          </button>
          {mode === 'intelligent' && (
            <button
              onClick={() => onViewChange('analysis')}
              className={cn(
                'w-10 h-10 flex items-center justify-center rounded-xl transition-colors',
                activeView === 'analysis' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-100',
              )}
            >
              <BarChart3 className="w-5 h-5" />
            </button>
          )}
          {mode === 'intelligent' && (
            <button
              onClick={() => onViewChange('copilot')}
              className={cn(
                'w-10 h-10 flex items-center justify-center rounded-xl transition-colors',
                activeView === 'copilot' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-100',
              )}
            >
              <Bot className="w-5 h-5" />
            </button>
          )}
          <button
            onClick={() => onViewChange('reports')}
            className={cn(
              'w-10 h-10 flex items-center justify-center rounded-xl transition-colors',
              activeView === 'reports' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-100',
            )}
          >
            <FileText className="w-5 h-5" />
          </button>
          <button
            onClick={() => onViewChange('ledger')}
            className={cn(
              'w-10 h-10 flex items-center justify-center rounded-xl transition-colors',
              activeView === 'ledger' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-100',
            )}
          >
            <BookText className="w-5 h-5" />
          </button>
          <button
            onClick={() => onViewChange('close-month')}
            className={cn(
              'w-10 h-10 flex items-center justify-center rounded-xl transition-colors',
              activeView === 'close-month' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-100',
            )}
          >
            <ShieldCheck className="w-5 h-5" />
          </button>
        </div>
      </aside>
    );
  }

  return (
    <aside className="fixed left-0 top-16 bottom-0 w-72 bg-white border-r border-slate-200 z-40 overflow-y-auto">
      <div className="p-4">
        <div className="mb-6 p-5 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl text-white shadow-lg shadow-blue-200">
          <p className="text-xs text-blue-100 mb-1 uppercase tracking-wider font-medium">Net Asset Value</p>
          <p className="text-3xl font-bold">{formatCurrency(netWorth)}</p>
          <div className="flex items-center gap-2 mt-3">
            <span className="flex items-center gap-1 text-sm text-emerald-100 bg-emerald-500/30 px-2 py-1 rounded-full">
              <TrendingUp className="w-3.5 h-3.5" />
              Live
            </span>
            <span className="text-xs text-blue-200">across selected clubs</span>
          </div>
        </div>

        <div className="mb-4">
          <div className="flex items-center justify-between p-3 bg-emerald-50 rounded-xl mb-2">
            <div className="flex items-center gap-2">
              <Wallet className="w-4 h-4 text-emerald-600" />
              <span className="text-sm font-medium text-emerald-800">ASSETS</span>
            </div>
            <span className="text-sm font-semibold text-emerald-700">{formatCurrency(totalNAV)}</span>
          </div>
        </div>

        <div className="mb-4">
          <button
            onClick={() => toggleSection('clubs')}
            className="w-full flex items-center justify-between p-3 bg-slate-50 rounded-xl mb-2 hover:bg-slate-100 transition-colors"
          >
            <div className="flex items-center gap-2">
              <PiggyBank className="w-4 h-4 text-slate-500" />
              <span className="text-sm font-medium text-slate-700">CLUBS</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700">
                {formatCurrency(clubAccounts.reduce((sum, account) => sum + account.balance, 0))}
              </span>
              {expandedSections.clubs ? (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-slate-400" />
              )}
            </div>
          </button>

          {expandedSections.clubs && (
            <div className="space-y-1 pl-2">
              {clubAccounts.map((account) => (
                <div key={account.id} className="flex items-center justify-between p-3 rounded-xl hover:bg-slate-50 cursor-pointer group transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-emerald-100 rounded-lg flex items-center justify-center">
                      <Building2 className="w-4 h-4 text-emerald-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-700 group-hover:text-slate-900">{account.name}</p>
                      <p className={cn('text-xs', account.change >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                        {account.change >= 0 ? '+' : ''}
                        {account.change.toFixed(1)}%
                      </p>
                    </div>
                  </div>
                  <span className="text-sm font-semibold text-slate-700">{formatCurrency(account.balance)}</span>
                </div>
              ))}
              {clubAccounts.length === 0 && (
                <div className="p-3 text-xs text-slate-500">No club balances available.</div>
              )}
            </div>
          )}
        </div>

        <div className="mb-4">
          <button
            onClick={() => toggleSection('investments')}
            className="w-full flex items-center justify-between p-3 bg-slate-50 rounded-xl mb-2 hover:bg-slate-100 transition-colors"
          >
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-slate-500" />
              <span className="text-sm font-medium text-slate-700">INVESTMENTS</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700">
                {formatCurrency(investmentAccounts.reduce((sum, account) => sum + account.balance, 0))}
              </span>
              {expandedSections.investments ? (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-slate-400" />
              )}
            </div>
          </button>

          {expandedSections.investments && (
            <div className="space-y-1 pl-2">
              {investmentAccounts.map((account) => (
                <div key={account.id} className="flex items-center justify-between p-3 rounded-xl hover:bg-slate-50 cursor-pointer group transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                      <TrendingUp className="w-4 h-4 text-blue-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-700 group-hover:text-slate-900">{account.name}</p>
                      <p className={cn('text-xs', account.change >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                        {account.change >= 0 ? '+' : ''}
                        {account.change.toFixed(1)}%
                      </p>
                    </div>
                  </div>
                  <span className="text-sm font-semibold text-slate-700">{formatCurrency(account.balance)}</span>
                </div>
              ))}
              {investmentAccounts.length === 0 && (
                <div className="p-3 text-xs text-slate-500">No investment snapshots available.</div>
              )}
            </div>
          )}
        </div>

        <div className="mb-4">
          <button
            onClick={() => toggleSection('expenses')}
            className="w-full flex items-center justify-between p-3 bg-red-50 rounded-xl mb-2 hover:bg-red-100 transition-colors"
          >
            <div className="flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-red-500" />
              <span className="text-sm font-medium text-red-700">EXPENSES</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-red-600">{formatCurrency(totalExpenses)}</span>
              {expandedSections.expenses ? (
                <ChevronDown className="w-4 h-4 text-red-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-red-400" />
              )}
            </div>
          </button>

          {expandedSections.expenses && (
            <div className="space-y-1 pl-2">
              {expenseAccounts.map((account) => (
                <div key={account.id} className="flex items-center justify-between p-3 rounded-xl hover:bg-slate-50 cursor-pointer group transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-red-100 rounded-lg flex items-center justify-center">
                      <CreditCard className="w-4 h-4 text-red-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-700 group-hover:text-slate-900">{account.name}</p>
                    </div>
                  </div>
                  <span className="text-sm font-semibold text-red-600">{formatCurrency(account.balance)}</span>
                </div>
              ))}
              {expenseAccounts.length === 0 && (
                <div className="p-3 text-xs text-slate-500">No expense snapshots available.</div>
              )}
            </div>
          )}
        </div>

        <button
          className="w-full flex items-center justify-center gap-2 p-3 text-sm text-blue-600 hover:bg-blue-50 rounded-xl transition-colors border border-dashed border-blue-200"
          onClick={() => {
            onViewChange('clubs');
            window.setTimeout(() => window.dispatchEvent(new Event('clubs:new')), 0);
          }}
        >
          <Plus className="w-4 h-4" />
          Add Club
        </button>

        <div className="mt-6 pt-6 border-t border-slate-200">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Quick Links</p>
          <div className="space-y-1">
            <button
              onClick={() => onViewChange('dashboard')}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors',
                activeView === 'dashboard' ? 'bg-blue-50 text-blue-600 font-medium' : 'text-slate-600 hover:bg-slate-50',
              )}
            >
              <PieChart className="w-4 h-4" />
              Dashboard
            </button>
            {mode === 'intelligent' && (
              <button
                onClick={() => onViewChange('analysis')}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors',
                  activeView === 'analysis' ? 'bg-blue-50 text-blue-600 font-medium' : 'text-slate-600 hover:bg-slate-50',
                )}
              >
                <BarChart3 className="w-4 h-4" />
                Analysis
              </button>
            )}
            {mode === 'intelligent' && (
              <button
                onClick={() => onViewChange('copilot')}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors',
                  activeView === 'copilot' ? 'bg-blue-50 text-blue-600 font-medium' : 'text-slate-600 hover:bg-slate-50',
                )}
              >
                <Bot className="w-4 h-4" />
                Copilot
              </button>
            )}
            <button
              onClick={() => onViewChange('reports')}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors',
                activeView === 'reports' ? 'bg-blue-50 text-blue-600 font-medium' : 'text-slate-600 hover:bg-slate-50',
              )}
            >
              <FileText className="w-4 h-4" />
              Reports
            </button>
            <button
              onClick={() => onViewChange('ledger')}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors',
                activeView === 'ledger' ? 'bg-blue-50 text-blue-600 font-medium' : 'text-slate-600 hover:bg-slate-50',
              )}
            >
              <BookText className="w-4 h-4" />
              Ledger
            </button>
            <button
              onClick={() => onViewChange('close-month')}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors',
                activeView === 'close-month'
                  ? 'bg-blue-50 text-blue-600 font-medium'
                  : 'text-slate-600 hover:bg-slate-50',
              )}
            >
              <ShieldCheck className="w-4 h-4" />
              Close Month
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}
