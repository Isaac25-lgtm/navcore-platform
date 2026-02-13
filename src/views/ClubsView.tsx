import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Building2,
  Plus,
  Search,
  Filter,
  MoreHorizontal,
  TrendingUp,
  TrendingDown,
  Users,
  ArrowUpRight,
  Download,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn, formatCurrency, formatPercentage } from '@/lib/utils';
import { extractApiErrorMessage } from '@/lib/feedback';
import { createClub, fetchClubMetrics } from '@/lib/api';
import type { ClubMetricSummary } from '@/types/platform';
import { usePlatform } from '@/context/PlatformContext';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
} from 'recharts';

function toNumber(value: string | null | undefined): number {
  if (!value) return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function clubStatus(club: ClubMetricSummary): 'draft' | 'review' | 'closed' {
  return club.latest_period?.status ?? 'draft';
}

export function ClubsView() {
  const { refresh } = usePlatform();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedClub, setSelectedClub] = useState<number | null>(null);
  const [clubs, setClubs] = useState<ClubMetricSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createCode, setCreateCode] = useState('');
  const [createName, setCreateName] = useState('');
  const [createCurrency, setCreateCurrency] = useState('UGX');
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchClubMetrics();
      setClubs(rows);
    } catch (err) {
      setError(extractApiErrorMessage(err, 'Failed to load clubs.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onOpenCreate = () => setCreateOpen(true);
    window.addEventListener('clubs:new', onOpenCreate);
    return () => window.removeEventListener('clubs:new', onOpenCreate);
  }, []);

  async function handleCreateClub() {
    if (!createCode.trim() || !createName.trim()) {
      setError('Club code and name are required. Example: code GAMMA, name Gamma Balanced Club.');
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await createClub({
        code: createCode.trim().toUpperCase(),
        name: createName.trim(),
        currency: createCurrency.trim().toUpperCase() || 'UGX',
      });
      setCreateOpen(false);
      setCreateCode('');
      setCreateName('');
      setCreateCurrency('UGX');
      await Promise.all([load(), refresh()]);
      setMessage(`Club created: ${createName.trim()} (${createCode.trim().toUpperCase()}).`);
    } catch (err) {
      const detail = extractApiErrorMessage(err, 'Failed to create club.');
      setError(`${detail} Use a unique club code within this tenant.`);
    } finally {
      setSubmitting(false);
    }
  }

  const filteredClubs = useMemo(
    () => clubs.filter((club) => club.name.toLowerCase().includes(searchQuery.toLowerCase())),
    [clubs, searchQuery],
  );

  const totalNAV = useMemo(
    () => clubs.reduce((sum, club) => sum + toNumber(club.latest_period?.closing_nav ?? '0'), 0),
    [clubs],
  );
  const totalInvestors = useMemo(
    () => clubs.reduce((sum, club) => sum + club.investor_count, 0),
    [clubs],
  );
  const avgReturn = useMemo(() => {
    const withPeriods = clubs.filter((club) => club.latest_period !== null);
    if (withPeriods.length === 0) return 0;
    const total = withPeriods.reduce(
      (sum, club) => sum + toNumber(club.latest_period?.return_pct ?? '0'),
      0,
    );
    return total / withPeriods.length;
  }, [clubs]);

  const chartData = filteredClubs.map((club) => ({
    name: club.name.split(' ')[0],
    nav: toNumber(club.latest_period?.closing_nav ?? '0') / 1_000_000,
    return: toNumber(club.latest_period?.return_pct ?? '0'),
  }));

  const pieData = filteredClubs.map((club) => ({
    name: club.name.split(' ')[0],
    value: toNumber(club.latest_period?.closing_nav ?? '0'),
  }));

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];
  const selectedClubData = selectedClub ? clubs.find((club) => club.id === selectedClub) : null;

  function handleExport() {
    const rows = filteredClubs.map((club) => {
      const latest = club.latest_period;
      return [
        club.code,
        club.name,
        club.currency,
        latest?.year ?? '',
        latest?.month ?? '',
        latest?.status ?? '',
        latest?.opening_nav ?? '',
        latest?.contributions ?? '',
        latest?.withdrawals ?? '',
        latest?.income ?? '',
        latest?.expenses ?? '',
        latest?.closing_nav ?? '',
        latest?.return_pct ?? '',
        club.investor_count,
      ];
    });
    const header = [
      'code',
      'name',
      'currency',
      'year',
      'month',
      'status',
      'opening_nav',
      'contributions',
      'withdrawals',
      'income',
      'expenses',
      'closing_nav',
      'return_pct',
      'investor_count',
    ];
    const csv = [header, ...rows]
      .map((columns) => columns.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(','))
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'clubs-summary.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Investment Clubs</h1>
          <p className="text-sm text-slate-500 mt-0.5">Manage and monitor all your investment clubs</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" className="border-slate-200 text-slate-600" onClick={handleExport}>
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
          <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => setCreateOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            New Club
          </Button>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-xs text-blue-700">
        Flow: create club, add investors, create period, post ledger entries, reconcile, then close month for immutable snapshots and reports.
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {error}
        </div>
      )}
      {message && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-emerald-700">
          {message}
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-1">Total Clubs</p>
          <p className="text-2xl font-semibold text-slate-800">{clubs.length}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-1">Total NAV</p>
          <p className="text-2xl font-semibold text-slate-800">{formatCurrency(totalNAV)}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-1">Avg Return</p>
          <p className={cn('text-2xl font-semibold', avgReturn >= 0 ? 'text-emerald-600' : 'text-red-500')}>
            {formatPercentage(avgReturn)}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-1">Total Investors</p>
          <p className="text-2xl font-semibold text-slate-800">{totalInvestors}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-4">NAV by Club</h3>
          <div className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis
                  stroke="#94a3b8"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => `${value}M`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'white',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    padding: '10px',
                  }}
                  formatter={(value: number) => [formatCurrency(value * 1_000_000), 'NAV']}
                />
                <Bar dataKey="nav" radius={[4, 4, 0, 0]}>
                  {chartData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-4">Portfolio Allocation</h3>
          <div className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'white',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    padding: '10px',
                  }}
                  formatter={(value: number) => [formatCurrency(value), 'NAV']}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            placeholder="Search clubs..."
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className="pl-10 bg-white border-slate-200"
          />
        </div>
        <Button variant="outline" className="border-slate-200 text-slate-600">
          <Filter className="w-4 h-4 mr-2" />
          Filter
        </Button>
      </div>

      {loading ? (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 text-sm text-slate-500">
          Loading clubs...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredClubs.map((club) => {
            const status = clubStatus(club);
            const returnPct = toNumber(club.latest_period?.return_pct ?? '0');
            const latestClosing = toNumber(club.latest_period?.closing_nav ?? '0');

            return (
              <div
                key={club.id}
                onClick={() => setSelectedClub(club.id)}
                className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 cursor-pointer hover:shadow-md hover:border-blue-300 transition-all"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
                      <Building2 className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-800">{club.name}</h3>
                      <span
                        className={cn(
                          'text-xs px-2 py-0.5 rounded-full',
                          status === 'draft' && 'bg-emerald-100 text-emerald-700',
                          status === 'review' && 'bg-amber-100 text-amber-700',
                          status === 'closed' && 'bg-slate-100 text-slate-600',
                        )}
                      >
                        {status.charAt(0).toUpperCase() + status.slice(1)}
                      </span>
                    </div>
                  </div>
                  <button
                    className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg"
                    onClick={(event) => {
                      event.stopPropagation();
                      setSelectedClub(club.id);
                    }}
                  >
                    <MoreHorizontal className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <p className="text-xs text-slate-500 mb-1">NAV</p>
                    <p className="text-lg font-semibold text-slate-800">{formatCurrency(latestClosing)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500 mb-1">Return</p>
                    <div className={cn('flex items-center gap-1', returnPct >= 0 ? 'text-emerald-600' : 'text-red-500')}>
                      {returnPct >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                      <span className="text-lg font-semibold">{formatPercentage(returnPct)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <Users className="w-4 h-4" />
                    <span>{club.investor_count} Investors</span>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-slate-400" />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selectedClubData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setSelectedClub(null)}>
          <div
            className="w-full max-w-2xl bg-white rounded-2xl shadow-xl animate-fade-in"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between p-6 border-b border-slate-100">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
                  <Building2 className="w-7 h-7 text-white" />
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-slate-800">{selectedClubData.name}</h3>
                  <p className="text-sm text-slate-500">Investment Club Details</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedClub(null)}
                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6">
              <h4 className="text-sm font-semibold text-slate-700 mb-4">NAV Breakdown</h4>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div className="bg-slate-50 p-4 rounded-xl">
                  <p className="text-xs text-slate-500 mb-1">Opening NAV</p>
                  <p className="text-lg font-semibold text-slate-800">
                    {formatCurrency(toNumber(selectedClubData.latest_period?.opening_nav ?? '0'))}
                  </p>
                </div>
                <div className="bg-emerald-50 p-4 rounded-xl">
                  <p className="text-xs text-slate-500 mb-1">Contributions</p>
                  <p className="text-lg font-semibold text-emerald-600">
                    +{formatCurrency(toNumber(selectedClubData.latest_period?.contributions ?? '0'))}
                  </p>
                </div>
                <div className="bg-red-50 p-4 rounded-xl">
                  <p className="text-xs text-slate-500 mb-1">Withdrawals</p>
                  <p className="text-lg font-semibold text-red-500">
                    -{formatCurrency(toNumber(selectedClubData.latest_period?.withdrawals ?? '0'))}
                  </p>
                </div>
                <div className="bg-emerald-50 p-4 rounded-xl">
                  <p className="text-xs text-slate-500 mb-1">Income</p>
                  <p className="text-lg font-semibold text-emerald-600">
                    +{formatCurrency(toNumber(selectedClubData.latest_period?.income ?? '0'))}
                  </p>
                </div>
                <div className="bg-red-50 p-4 rounded-xl">
                  <p className="text-xs text-slate-500 mb-1">Expenses</p>
                  <p className="text-lg font-semibold text-red-500">
                    -{formatCurrency(toNumber(selectedClubData.latest_period?.expenses ?? '0'))}
                  </p>
                </div>
                <div className="bg-blue-50 p-4 rounded-xl border-2 border-blue-200">
                  <p className="text-xs text-slate-500 mb-1">Closing NAV</p>
                  <p className="text-lg font-semibold text-blue-600">
                    {formatCurrency(toNumber(selectedClubData.latest_period?.closing_nav ?? '0'))}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-white border-slate-200">
          <DialogHeader>
            <DialogTitle className="text-slate-800">Create Club</DialogTitle>
            <DialogDescription className="text-slate-500">
              Add a new investment club for this tenant.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <label className="text-xs text-slate-500">Club Code</label>
              <Input
                value={createCode}
                onChange={(event) => setCreateCode(event.target.value)}
                placeholder="GAMMA"
                className="bg-white border-slate-200"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-slate-500">Club Name</label>
              <Input
                value={createName}
                onChange={(event) => setCreateName(event.target.value)}
                placeholder="Gamma Balanced Club"
                className="bg-white border-slate-200"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-slate-500">Currency</label>
              <Input
                value={createCurrency}
                onChange={(event) => setCreateCurrency(event.target.value)}
                placeholder="UGX"
                className="bg-white border-slate-200"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" className="border-slate-200 text-slate-700" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              className="bg-blue-600 hover:bg-blue-700 text-white"
              disabled={submitting}
              onClick={() => void handleCreateClub()}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
