import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Users,
  Search,
  Download,
  TrendingUp,
  TrendingDown,
  Filter,
  Pencil,
  Trash2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { cn, formatCurrency, formatPercentage } from '@/lib/utils';
import { extractApiErrorMessage } from '@/lib/feedback';
import { usePlatform } from '@/context/PlatformContext';
import {
  createInvestor,
  deleteInvestor,
  fetchInvestors,
  updateInvestor,
} from '@/lib/api';
import type { InvestorSummary } from '@/types/platform';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

function toNumber(value: string | undefined): number {
  if (!value) return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

type InvestorRow = {
  id: number;
  name: string;
  investorCode: string;
  openingBalance: number;
  ownership: number;
  contribution: number;
  withdrawal: number;
  netAllocation: number;
  closingBalance: number;
  editable: boolean;
};

export function InvestorsView() {
  const [searchQuery, setSearchQuery] = useState('');
  const [investorList, setInvestorList] = useState<InvestorSummary[]>([]);
  const [crudLoading, setCrudLoading] = useState(false);
  const [crudError, setCrudError] = useState<string | null>(null);
  const [crudMessage, setCrudMessage] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createCode, setCreateCode] = useState('');
  const [createName, setCreateName] = useState('');
  const [editOpen, setEditOpen] = useState(false);
  const [editingInvestor, setEditingInvestor] = useState<InvestorSummary | null>(null);
  const [editName, setEditName] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<InvestorSummary | null>(null);
  const [working, setWorking] = useState(false);

  const { selectedClubId, periodState, locked, refresh } = usePlatform();

  const loadInvestors = useCallback(async () => {
    if (!selectedClubId) {
      setInvestorList([]);
      return;
    }
    setCrudLoading(true);
    setCrudError(null);
    try {
      const rows = await fetchInvestors(selectedClubId);
      setInvestorList(rows);
    } catch (err) {
      setCrudError(extractApiErrorMessage(err, 'Failed to load investors.'));
    } finally {
      setCrudLoading(false);
    }
  }, [selectedClubId]);

  useEffect(() => {
    void loadInvestors();
  }, [loadInvestors]);

  const investors = useMemo<InvestorRow[]>(() => {
    const positions = new Map((periodState?.positions ?? []).map((position) => [position.investor_id, position]));
    const rows: InvestorRow[] = investorList.map((investor) => {
      const position = positions.get(investor.id);
      return {
        id: investor.id,
        name: investor.name,
        investorCode: investor.investor_code,
        openingBalance: toNumber(position?.opening_balance),
        ownership: toNumber(position?.ownership_pct),
        contribution: toNumber(position?.contributions),
        withdrawal: toNumber(position?.withdrawals),
        netAllocation: toNumber(position?.net_allocation),
        closingBalance: toNumber(position?.closing_balance),
        editable: true,
      };
    });
    for (const position of periodState?.positions ?? []) {
      if (rows.some((row) => row.id === position.investor_id)) continue;
      rows.push({
        id: position.investor_id,
        name: position.investor_name,
        investorCode: `INV-${position.investor_id}`,
        openingBalance: toNumber(position.opening_balance),
        ownership: toNumber(position.ownership_pct),
        contribution: toNumber(position.contributions),
        withdrawal: toNumber(position.withdrawals),
        netAllocation: toNumber(position.net_allocation),
        closingBalance: toNumber(position.closing_balance),
        editable: false,
      });
    }
    return rows;
  }, [investorList, periodState?.positions]);

  const filteredInvestors = useMemo(
    () => investors.filter((investor) => investor.name.toLowerCase().includes(searchQuery.toLowerCase())),
    [investors, searchQuery],
  );

  const totalInvested = useMemo(
    () => investors.reduce((sum, investor) => sum + investor.openingBalance, 0),
    [investors],
  );
  const totalClosing = useMemo(
    () => investors.reduce((sum, investor) => sum + investor.closingBalance, 0),
    [investors],
  );
  const totalGrowth = totalInvested > 0 ? ((totalClosing - totalInvested) / totalInvested) * 100 : 0;

  const topInvestors = useMemo(
    () =>
      [...investors]
        .sort((left, right) => right.openingBalance - left.openingBalance)
        .slice(0, 5),
    [investors],
  );
  const othersValue = useMemo(
    () =>
      [...investors]
        .sort((left, right) => right.openingBalance - left.openingBalance)
        .slice(5)
        .reduce((sum, investor) => sum + investor.openingBalance, 0),
    [investors],
  );

  const pieData = [
    ...topInvestors.map((investor) => ({
      name: investor.name.split(' ')[0],
      value: investor.openingBalance,
    })),
    ...(othersValue > 0 ? [{ name: 'Others', value: othersValue }] : []),
  ];

  const barData = filteredInvestors.map((investor) => ({
    name: investor.name.split(' ')[0],
    balance: investor.closingBalance / 1_000_000,
    growth:
      investor.openingBalance > 0
        ? ((investor.closingBalance - investor.openingBalance) / investor.openingBalance) * 100
        : 0,
  }));

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#94a3b8'];

  async function handleCreateInvestor() {
    if (!selectedClubId || locked) return;
    if (!createCode.trim() || !createName.trim()) {
      setCrudError('Investor code and name are required. Example: code INV-006, name Jane Doe.');
      return;
    }
    setWorking(true);
    setCrudError(null);
    setCrudMessage(null);
    try {
      await createInvestor(selectedClubId, {
        investor_code: createCode.trim().toUpperCase(),
        name: createName.trim(),
      });
      setCreateOpen(false);
      setCreateCode('');
      setCreateName('');
      await Promise.all([loadInvestors(), refresh()]);
      setCrudMessage(`Investor ${createName.trim()} (${createCode.trim().toUpperCase()}) created successfully.`);
    } catch (err) {
      const detail = extractApiErrorMessage(err, 'Failed to create investor.');
      setCrudError(`${detail} Use unique investor code per club.`);
    } finally {
      setWorking(false);
    }
  }

  function openEditInvestor(investor: InvestorSummary) {
    setEditingInvestor(investor);
    setEditName(investor.name);
    setEditOpen(true);
  }

  async function handleEditInvestor() {
    if (!selectedClubId || !editingInvestor || locked) return;
    if (!editName.trim()) {
      setCrudError('Investor name is required. Example: Sarah Namuli.');
      return;
    }
    setWorking(true);
    setCrudError(null);
    setCrudMessage(null);
    try {
      await updateInvestor(selectedClubId, editingInvestor.id, { name: editName.trim() });
      setEditOpen(false);
      setEditingInvestor(null);
      setEditName('');
      await Promise.all([loadInvestors(), refresh()]);
      setCrudMessage(`Investor updated: ${editingInvestor.investor_code} is now "${editName.trim()}".`);
    } catch (err) {
      setCrudError(extractApiErrorMessage(err, 'Failed to update investor.'));
    } finally {
      setWorking(false);
    }
  }

  async function handleDeleteInvestor() {
    if (!selectedClubId || !deleteTarget || locked) return;
    setWorking(true);
    setCrudError(null);
    setCrudMessage(null);
    try {
      await deleteInvestor(selectedClubId, deleteTarget.id);
      setDeleteTarget(null);
      await Promise.all([loadInvestors(), refresh()]);
      setCrudMessage(`Investor deactivated: ${deleteTarget.name}. Existing history remains intact.`);
    } catch (err) {
      setCrudError(extractApiErrorMessage(err, 'Failed to delete investor.'));
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Investors</h1>
          <p className="text-sm text-slate-500 mt-0.5">Manage investor allocations and performance</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" className="border-slate-200 text-slate-600">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
          <Button
            className="bg-blue-600 hover:bg-blue-700 text-white"
            disabled={locked || !selectedClubId}
            onClick={() => setCreateOpen(true)}
          >
            <Users className="w-4 h-4 mr-2" />
            Add Investor
          </Button>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-xs text-blue-700">
        Flow: add investor profile, then use Ledger contributions/withdrawals to move balances. Allocations and ownership are computed automatically for the selected period.
      </div>

      {locked && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-700">
          This period is closed. Investor edits are disabled in locked mode.
        </div>
      )}

      {crudError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">{crudError}</div>
      )}
      {crudMessage && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-emerald-700">
          {crudMessage}
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-1">Total Investors</p>
          <p className="text-2xl font-semibold text-slate-800">{investors.length}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-1">Total Invested</p>
          <p className="text-2xl font-semibold text-slate-800">{formatCurrency(totalInvested)}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-1">Current Value</p>
          <p className="text-2xl font-semibold text-slate-800">{formatCurrency(totalClosing)}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-sm text-slate-500 mb-1">Portfolio Growth</p>
          <p className={cn('text-2xl font-semibold', totalGrowth >= 0 ? 'text-emerald-600' : 'text-red-500')}>
            {totalGrowth >= 0 ? '+' : ''}
            {totalGrowth.toFixed(1)}%
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-4">Ownership Distribution</h3>
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
                  formatter={(value: number) => [formatCurrency(value), 'Balance']}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-3 mt-4 justify-center">
            {pieData.map((entry, index) => (
              <div key={entry.name} className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                <span className="text-sm text-slate-500">{entry.name}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-4">Investor Balances</h3>
          <div className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
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
                  formatter={(value: number) => [formatCurrency(value * 1_000_000), 'Balance']}
                />
                <Bar dataKey="balance" radius={[4, 4, 0, 0]}>
                  {barData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.growth >= 0 ? '#10b981' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <h3 className="text-base font-semibold text-slate-800 mb-4">Allocation Formula</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-50 p-4 rounded-xl">
            <p className="text-xs text-slate-500 mb-2">Ownership %</p>
            <code className="text-sm text-blue-600 font-mono bg-blue-50 px-2 py-1 rounded">
              = Investor Opening / Club Opening NAV
            </code>
          </div>
          <div className="bg-slate-50 p-4 rounded-xl">
            <p className="text-xs text-slate-500 mb-2">Net Allocation</p>
            <code className="text-sm text-blue-600 font-mono bg-blue-50 px-2 py-1 rounded">
              = Ownership % * (Income - Expenses)
            </code>
          </div>
          <div className="bg-slate-50 p-4 rounded-xl">
            <p className="text-xs text-slate-500 mb-2">Closing Balance</p>
            <code className="text-sm text-blue-600 font-mono bg-blue-50 px-2 py-1 rounded">
              = Opening + Contribution - Withdrawal + Net
            </code>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            placeholder="Search investors..."
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

      {crudLoading ? (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 text-sm text-slate-500">
          Loading investor positions...
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Investor</th>
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Opening Balance</th>
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Ownership</th>
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Contribution</th>
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Withdrawal</th>
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Net Allocation</th>
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Closing Balance</th>
                  <th className="py-3 px-4"></th>
                </tr>
              </thead>
              <tbody>
                {filteredInvestors.map((investor) => {
                  const netChange = investor.closingBalance - investor.openingBalance;
                  const changePercent =
                    investor.openingBalance > 0 ? (netChange / investor.openingBalance) * 100 : 0;

                  return (
                    <tr key={investor.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center">
                            <span className="text-white font-semibold text-sm">{investor.name.charAt(0)}</span>
                          </div>
                          <div>
                            <span className="font-medium text-slate-800">{investor.name}</span>
                            <p className="text-xs text-slate-500">{investor.investorCode}</p>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-slate-600">{formatCurrency(investor.openingBalance)}</span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <div className="w-16">
                            <Progress value={investor.ownership} className="h-1.5" />
                          </div>
                          <span className="text-sm text-slate-600">{formatPercentage(investor.ownership, 1)}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-emerald-600">+{formatCurrency(investor.contribution)}</span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-red-500">-{formatCurrency(investor.withdrawal)}</span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={investor.netAllocation >= 0 ? 'text-emerald-600' : 'text-red-500'}>
                          {investor.netAllocation >= 0 ? '+' : ''}
                          {formatCurrency(investor.netAllocation)}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-800">{formatCurrency(investor.closingBalance)}</span>
                          {changePercent !== 0 && (
                            <span
                              className={cn(
                                'flex items-center gap-0.5 text-xs',
                                changePercent > 0 ? 'text-emerald-600' : 'text-red-500',
                              )}
                            >
                              {changePercent > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                              {Math.abs(changePercent).toFixed(1)}%
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1 justify-end">
                          <button
                            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-40"
                            disabled={locked || !investor.editable}
                            onClick={() => {
                              const original = investorList.find((row) => row.id === investor.id);
                              if (original) openEditInvestor(original);
                            }}
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-40"
                            disabled={locked || !investor.editable}
                            onClick={() => {
                              const original = investorList.find((row) => row.id === investor.id);
                              if (original) setDeleteTarget(original);
                            }}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-white border-slate-200">
          <DialogHeader>
            <DialogTitle className="text-slate-800">Add Investor</DialogTitle>
            <DialogDescription className="text-slate-500">
              Create a new investor under the selected club.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <label className="text-xs text-slate-500">Investor Code</label>
              <Input
                value={createCode}
                onChange={(event) => setCreateCode(event.target.value)}
                placeholder="INV-006"
                className="bg-white border-slate-200"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-slate-500">Investor Name</label>
              <Input
                value={createName}
                onChange={(event) => setCreateName(event.target.value)}
                placeholder="Investor full name"
                className="bg-white border-slate-200"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" className="border-slate-200 text-slate-700" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button className="bg-blue-600 hover:bg-blue-700 text-white" disabled={working} onClick={() => void handleCreateInvestor()}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="bg-white border-slate-200">
          <DialogHeader>
            <DialogTitle className="text-slate-800">Edit Investor</DialogTitle>
            <DialogDescription className="text-slate-500">
              Update investor details.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <label className="text-xs text-slate-500">Investor Code</label>
              <Input value={editingInvestor?.investor_code ?? ''} readOnly className="bg-slate-50 border-slate-200" />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-slate-500">Investor Name</label>
              <Input
                value={editName}
                onChange={(event) => setEditName(event.target.value)}
                placeholder="Investor full name"
                className="bg-white border-slate-200"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" className="border-slate-200 text-slate-700" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button className="bg-blue-600 hover:bg-blue-700 text-white" disabled={working} onClick={() => void handleEditInvestor()}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteTarget !== null} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent className="bg-white border-slate-200">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-slate-800">Delete Investor</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-500">
              This will deactivate investor <span className="font-medium text-slate-700">{deleteTarget?.name ?? ''}</span>.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-slate-200 text-slate-700">Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700 text-white" onClick={() => void handleDeleteInvestor()}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
