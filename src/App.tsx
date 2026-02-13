import { useEffect, useMemo, useState } from 'react';
import { Sidebar } from '@/components/layout/Sidebar';
import { TopNav } from '@/components/layout/TopNav';
import { DashboardView } from '@/views/DashboardView';
import { ClubsView } from '@/views/ClubsView';
import { InvestorsView } from '@/views/InvestorsView';
import { AnalyticsView } from '@/views/AnalyticsView';
import { ReportsView } from '@/views/ReportsView';
import { LedgerView } from '@/views/LedgerView';
import { CloseMonthView } from '@/views/CloseMonthView';
import { CopilotView } from '@/views/CopilotView';
import { FloatingCopilotWidget } from '@/components/ui-custom/FloatingCopilotWidget';
import { usePlatform } from '@/context/PlatformContext';
import { cn } from '@/lib/utils';
import './App.css';

type AppView =
  | 'dashboard'
  | 'clubs'
  | 'investors'
  | 'analysis'
  | 'reports'
  | 'ledger'
  | 'close-month'
  | 'copilot';

interface ParsedRoute {
  view: AppView;
  clubId: number | null;
  yyyymm: string | null;
}

interface SectionGuide {
  title: string;
  details: string;
  flow: string;
}

const SECTION_GUIDES: Record<AppView, SectionGuide> = {
  dashboard: {
    title: 'Overview',
    details: 'Shows NAV movement, cash flow, and current portfolio health for the selected club and period.',
    flow: 'Review trends -> open Club/Investor/Ledger sections -> return here for consolidated analysis.',
  },
  clubs: {
    title: 'Clubs',
    details: 'Manages club-level structure and period-level performance comparisons.',
    flow: 'Create club -> create periods -> manage club-level analytics and status.',
  },
  investors: {
    title: 'Investors',
    details: 'Maintains investor master records and period balances derived from NAV allocation.',
    flow: 'Add/edit investor -> post transactions in Ledger -> monitor ownership and closing balances.',
  },
  ledger: {
    title: 'Ledger',
    details: 'Captures monthly contributions, withdrawals, income, expenses, and adjustments.',
    flow: 'Post entries -> verify reconciliation stamp -> submit review/close month.',
  },
  'close-month': {
    title: 'Close Month',
    details: 'Runs close checklist, enforces reconciliation gate, and locks immutable closed state.',
    flow: 'Submit review -> ensure checklist passes -> run close -> generate reports.',
  },
  reports: {
    title: 'Reports',
    details: 'Generates and downloads immutable PDFs and regulator-friendly exports.',
    flow: 'Close period -> generate monthly and investor reports -> download PDF/CSV/Excel outputs.',
  },
  analysis: {
    title: 'Analysis',
    details: 'Provides metrics, insights, anomaly flags, and scenario simulation for selected scope.',
    flow: 'Read insights -> inspect anomalies -> run scenarios -> validate decision impacts.',
  },
  copilot: {
    title: 'Copilot',
    details: 'Read-only assistant scoped to selected club and period with source citations.',
    flow: 'Ask scoped questions -> review cited sources -> use output for investor updates and decisions.',
  },
};

function parsePath(pathname: string): ParsedRoute {
  if (pathname === '/clubs' || pathname === '/clubs/') {
    return { view: 'clubs', clubId: null, yyyymm: null };
  }
  const route = pathname.match(
    /^\/clubs\/(?<club>\d+)\/periods\/(?<yyyymm>\d{6})(?:\/(?<page>ledger|close|reports|analysis|copilot|investors))?\/?$/,
  );
  if (!route?.groups) {
    return { view: 'dashboard', clubId: null, yyyymm: null };
  }
  const page = route.groups.page;
  const view: AppView =
    page === 'ledger'
      ? 'ledger'
      : page === 'close'
        ? 'close-month'
        : page === 'reports'
          ? 'reports'
          : page === 'analysis'
            ? 'analysis'
            : page === 'copilot'
              ? 'copilot'
              : page === 'investors'
                ? 'investors'
                : 'dashboard';
  return {
    view,
    clubId: Number(route.groups.club),
    yyyymm: route.groups.yyyymm,
  };
}

function pathForView(
  view: AppView,
  clubId: number | null,
  yyyymm: string | null,
): string {
  if (view === 'clubs') return '/clubs';
  if (!clubId || !yyyymm) return '/';
  const base = `/clubs/${clubId}/periods/${yyyymm}`;
  if (view === 'ledger') return `${base}/ledger`;
  if (view === 'close-month') return `${base}/close`;
  if (view === 'reports') return `${base}/reports`;
  if (view === 'analysis') return `${base}/analysis`;
  if (view === 'copilot') return `${base}/copilot`;
  if (view === 'investors') return `${base}/investors`;
  return base;
}

function App() {
  const [activeView, setActiveView] = useState<AppView>('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [routeHint, setRouteHint] = useState<ParsedRoute>(() => parsePath(window.location.pathname));
  const [routePending, setRoutePending] = useState(true);
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const stored = window.localStorage.getItem('navfund-theme');
    return stored === 'dark' ? 'dark' : 'light';
  });
  const {
    loading,
    error,
    locked,
    status,
    mode,
    periods,
    selectedClub,
    selectedClubId,
    selectedPeriod,
    selectedPeriodId,
    setSelectedClubId,
    setSelectedPeriodId,
  } = usePlatform();

  const selectedYearMonth = useMemo(
    () =>
      selectedPeriod
        ? `${selectedPeriod.year}${String(selectedPeriod.month).padStart(2, '0')}`
        : null,
    [selectedPeriod],
  );

  const sectionGuide = useMemo(
    () => SECTION_GUIDES[activeView],
    [activeView],
  );

  useEffect(() => {
    const applyPath = () => {
      const parsed = parsePath(window.location.pathname);
      setRouteHint(parsed);
      setActiveView(parsed.view);
      setRoutePending(true);
    };
    applyPath();
    const onPopState = () => applyPath();
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    if (mode === 'basic' && (activeView === 'analysis' || activeView === 'copilot')) {
      setActiveView('dashboard');
    }
  }, [activeView, mode]);

  useEffect(() => {
    if (!routePending) return;
    if (!routeHint.clubId) {
      setRoutePending(false);
      return;
    }
    if (routeHint.clubId !== selectedClubId) {
      setSelectedClubId(routeHint.clubId);
      return;
    }
    if (!routeHint.yyyymm) {
      setRoutePending(false);
    }
  }, [routeHint.clubId, routeHint.yyyymm, routePending, selectedClubId, setSelectedClubId]);

  useEffect(() => {
    if (!routePending) return;
    if (!routeHint.yyyymm) {
      setRoutePending(false);
      return;
    }
    if (periods.length === 0) return;
    const match = periods.find(
      (period) =>
        `${period.year}${String(period.month).padStart(2, '0')}` === routeHint.yyyymm,
    );
    if (match && match.id !== selectedPeriodId) {
      setSelectedPeriodId(match.id);
    }
    setRoutePending(false);
  }, [periods, routeHint.yyyymm, routePending, selectedPeriodId, setSelectedPeriodId]);

  useEffect(() => {
    if (routePending) return;
    const pathname = pathForView(activeView, selectedClubId, selectedYearMonth);
    if (window.location.pathname !== pathname) {
      window.history.replaceState({}, '', pathname);
    }
  }, [activeView, routePending, selectedClubId, selectedYearMonth]);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('theme-dark');
    } else {
      root.classList.remove('theme-dark');
    }
    window.localStorage.setItem('navfund-theme', theme);
  }, [theme]);

  const renderView = () => {
    switch (activeView) {
      case 'dashboard':
        return <DashboardView />;
      case 'clubs':
        return <ClubsView />;
      case 'investors':
        return <InvestorsView />;
      case 'analysis':
        return <AnalyticsView />;
      case 'reports':
        return <ReportsView />;
      case 'ledger':
        return <LedgerView />;
      case 'close-month':
        return <CloseMonthView />;
      case 'copilot':
        return <CopilotView />;
      default:
        return <DashboardView />;
    }
  };

  return (
    <div className={cn('min-h-screen', theme === 'dark' ? 'bg-slate-950' : 'bg-[#f1f5f9]')}>
      <TopNav
        activeView={activeView}
        onViewChange={(view) => setActiveView(view as AppView)}
        onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
        theme={theme}
        onToggleTheme={() => setTheme((current) => (current === 'light' ? 'dark' : 'light'))}
      />

      <Sidebar
        activeView={activeView}
        onViewChange={(view) => setActiveView(view as AppView)}
        collapsed={sidebarCollapsed}
      />

      <main
        className={cn(
          'pt-16 transition-all duration-300 min-h-screen',
          sidebarCollapsed ? 'pl-16' : 'pl-72',
        )}
      >
        <div className="p-6">
          {loading ? (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 text-sm text-slate-500">
              Loading platform context...
            </div>
          ) : (
            <div className="space-y-4">
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-700">
                    {selectedClub?.name ?? 'No club selected'} |{' '}
                    {selectedPeriod
                      ? `${selectedPeriod.year}-${String(selectedPeriod.month).padStart(2, '0')}`
                      : 'No period'}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">Status: {status}</p>
                </div>
                <div className="flex items-center gap-2">
                  {(status === 'draft' || status === 'review') && (
                    <span className="text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-700 font-medium">
                      Preview
                    </span>
                  )}
                  {locked && (
                    <span className="text-xs px-2 py-1 rounded-full bg-amber-100 text-amber-700 font-medium">
                      Locked Read-Only
                    </span>
                  )}
                </div>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-3">
                <p className="text-xs text-blue-700 font-medium">{sectionGuide.title}</p>
                <p className="text-xs text-blue-700 mt-1">{sectionGuide.details}</p>
                <p className="text-xs text-blue-600 mt-1">Flow: {sectionGuide.flow}</p>
              </div>
              {error ? (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
                  {error}
                </div>
              ) : (
                <div className="relative">
                  {renderView()}
                  {locked && (
                    <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                      <span className="text-[96px] font-semibold text-slate-300/30 tracking-[0.4em] select-none">
                        LOCKED
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </main>
      <FloatingCopilotWidget />
    </div>
  );
}

export default App;
