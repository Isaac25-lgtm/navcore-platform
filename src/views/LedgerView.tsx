import { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus, Lock, FileText, CircleAlert, Pencil, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { createLedgerEntry, deleteLedgerEntry, fetchInvestors, fetchLedger, updateLedgerEntry } from '@/lib/api';
import { usePlatform } from '@/context/PlatformContext';
import { cn, formatCurrency } from '@/lib/utils';
import { extractApiErrorMessage, parseMoneyInput } from '@/lib/feedback';
import type { LedgerEntry } from '@/types/platform';
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

const ENTRY_TYPES: Array<LedgerEntry['entry_type']> = [
  'contribution',
  'withdrawal',
  'income',
  'expense',
  'adjustment',
];

const ENTRY_GUIDANCE: Record<LedgerEntry['entry_type'], string> = {
  contribution: 'Use positive amounts and choose the investor receiving the cash.',
  withdrawal: 'Use positive amounts and choose the investor making the withdrawal.',
  income: 'Use positive amounts, no investor selection is needed.',
  expense: 'Use positive amounts, no investor selection is needed.',
  adjustment: 'Use positive or negative amount, and optionally link to an investor.',
};

export function LedgerView() {
  const { selectedClubId, selectedPeriodId, status, locked, refresh } = usePlatform();
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [investors, setInvestors] = useState<Array<{ id: number; name: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [entryType, setEntryType] = useState<LedgerEntry['entry_type']>('contribution');
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('general');
  const [txDate, setTxDate] = useState('');
  const [note, setNote] = useState('');
  const [reference, setReference] = useState('');
  const [investorId, setInvestorId] = useState<string>('');

  const [editOpen, setEditOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState<LedgerEntry | null>(null);
  const [editAmount, setEditAmount] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editCategory, setEditCategory] = useState('');
  const [editTxDate, setEditTxDate] = useState('');
  const [editReference, setEditReference] = useState('');
  const [editNote, setEditNote] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<LedgerEntry | null>(null);

  const requiresInvestor = useMemo(
    () => entryType === 'contribution' || entryType === 'withdrawal' || entryType === 'adjustment',
    [entryType],
  );
  const canEditEntries = status === 'draft' || status === 'review';
  const canDeleteEntries = status === 'draft';

  const investorNameById = useMemo(
    () =>
      investors.reduce<Record<number, string>>((accumulator, investor) => {
        accumulator[investor.id] = investor.name;
        return accumulator;
      }, {}),
    [investors],
  );

  const entryGuide = useMemo(
    () => ENTRY_GUIDANCE[entryType],
    [entryType],
  );

  function validateEntryInput(
    amountInput: string,
    descInput: string,
    selectedInvestorId: string,
    type: LedgerEntry['entry_type'],
  ): { ok: true; amount: number; description: string } | { ok: false; message: string } {
    const parsedAmount = parseMoneyInput(amountInput);
    if (parsedAmount === null) {
      return {
        ok: false,
        message: 'Amount must be numeric. Example: 2500000 or 2,500,000.',
      };
    }
    if (parsedAmount === 0) {
      return {
        ok: false,
        message: 'Amount cannot be zero. Use a value like 1500000.',
      };
    }
    if (type !== 'adjustment' && parsedAmount < 0) {
      return {
        ok: false,
        message: `${type} must be positive. Use adjustment for negative correction values.`,
      };
    }
    const cleanDescription = descInput.trim();
    if (cleanDescription.length < 3) {
      return {
        ok: false,
        message: 'Description is required (at least 3 characters). Example: "Monthly management fee".',
      };
    }
    if ((type === 'contribution' || type === 'withdrawal' || type === 'adjustment') && !selectedInvestorId) {
      return {
        ok: false,
        message: `Select an investor for ${type} entries so allocations remain auditable.`,
      };
    }
    return { ok: true, amount: parsedAmount, description: cleanDescription };
  }

  const load = useCallback(async () => {
    if (!selectedClubId || !selectedPeriodId) {
      setLedger([]);
      setInvestors([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [ledgerRows, investorRows] = await Promise.all([
        fetchLedger(selectedClubId, selectedPeriodId),
        fetchInvestors(selectedClubId),
      ]);
      setLedger(ledgerRows);
      setInvestors(investorRows);
    } catch (err) {
      setError(extractApiErrorMessage(err, 'Failed to load ledger.'));
    } finally {
      setLoading(false);
    }
  }, [selectedClubId, selectedPeriodId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleSubmit() {
    if (!selectedClubId || !selectedPeriodId || locked) return;
    const validation = validateEntryInput(amount, description, investorId, entryType);
    if (!validation.ok) {
      setError(validation.message);
      return;
    }
    const parsedAmount = validation.amount;
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await createLedgerEntry(selectedClubId, selectedPeriodId, {
        entry_type: entryType,
        amount: parsedAmount,
        description: validation.description,
        category: category.trim() || 'general',
        tx_date: txDate || undefined,
        note: note.trim() || undefined,
        reference: reference.trim() || undefined,
        investor_id: requiresInvestor && investorId ? Number(investorId) : undefined,
      });
      setAmount('');
      setDescription('');
      setCategory('general');
      setTxDate('');
      setNote('');
      setReference('');
      setInvestorId('');
      await Promise.all([load(), refresh()]);
      const investorName = requiresInvestor && investorId ? investorNameById[Number(investorId)] : null;
      setMessage(
        `Saved ${entryType} entry for ${formatCurrency(Math.abs(parsedAmount))}${
          investorName ? ` (${investorName})` : ''
        }. This is now included in NAV preview and reconciliation.`,
      );
    } catch (err) {
      const detail = extractApiErrorMessage(err, 'Failed to post ledger entry.');
      setError(`${detail} Correct format: amount + description${requiresInvestor ? ' + investor' : ''}.`);
    } finally {
      setSubmitting(false);
    }
  }

  function openEdit(entry: LedgerEntry) {
    if (!canEditEntries || locked) return;
    setEditingEntry(entry);
    setEditAmount(String(Number(entry.amount)));
    setEditDescription(entry.description);
    setEditCategory(entry.category);
    setEditTxDate(entry.tx_date);
    setEditReference(entry.reference ?? '');
    setEditNote(entry.note ?? '');
    setEditOpen(true);
  }

  async function handleUpdateEntry() {
    if (!selectedClubId || !selectedPeriodId || !editingEntry || locked) return;
    if (status === 'closed') return;
    const editInvestorId = editingEntry.investor_id ? String(editingEntry.investor_id) : '';
    const validation = validateEntryInput(editAmount, editDescription, editInvestorId, editingEntry.entry_type);
    if (!validation.ok) {
      setError(validation.message);
      return;
    }
    const parsedAmount = validation.amount;
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await updateLedgerEntry(selectedClubId, selectedPeriodId, editingEntry.id, {
        amount: parsedAmount,
        description: validation.description,
        category: editCategory.trim() || 'general',
        tx_date: editTxDate || undefined,
        reference: editReference.trim() || undefined,
        note: editNote.trim() || undefined,
      });
      setEditOpen(false);
      setEditingEntry(null);
      await Promise.all([load(), refresh()]);
      setMessage(
        `Updated ${editingEntry.entry_type} entry to ${formatCurrency(Math.abs(parsedAmount))}. Recalculated totals are now reflected.`,
      );
    } catch (err) {
      const detail = extractApiErrorMessage(err, 'Failed to update ledger entry.');
      setError(`${detail} Correct format: valid amount and clear description.`);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteEntry() {
    if (!selectedClubId || !selectedPeriodId || !deleteTarget || locked || !canDeleteEntries) return;
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await deleteLedgerEntry(selectedClubId, selectedPeriodId, deleteTarget.id);
      setDeleteTarget(null);
      await Promise.all([load(), refresh()]);
      setMessage(
        `Deleted ${deleteTarget.entry_type} entry "${deleteTarget.description}". Totals and reconciliation were refreshed.`,
      );
    } catch (err) {
      setError(extractApiErrorMessage(err, 'Failed to delete ledger entry.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Ledger</h1>
          <p className="text-sm text-slate-500 mt-0.5">Record contributions, withdrawals, income, and expenses</p>
        </div>
      </div>

      {locked && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3">
          <Lock className="w-5 h-5 text-amber-600" />
          <p className="text-sm text-amber-700">This period is closed and read-only. Post adjustments in a later period.</p>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <h3 className="text-base font-semibold text-slate-800 mb-4">New Ledger Entry</h3>
        <div className="mb-4 bg-blue-50 border border-blue-200 rounded-xl p-3">
          <p className="text-xs text-blue-700">
            Entry guide: {entryGuide}
          </p>
          <p className="text-xs text-blue-600 mt-1">
            Example: amount `2,500,000`, description `Monthly portfolio income`.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
          <div className="space-y-2">
            <Label className="text-xs text-slate-500">Entry Type</Label>
            <Select value={entryType} onValueChange={(value) => setEntryType(value as LedgerEntry['entry_type'])}>
              <SelectTrigger className="bg-white border-slate-200">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ENTRY_TYPES.map((type) => (
                  <SelectItem key={type} value={type}>
                    {type}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-slate-500">Amount (UGX)</Label>
            <Input
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              disabled={locked || submitting}
              className="bg-white border-slate-200"
            />
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-slate-500">Investor</Label>
            <Select value={investorId} onValueChange={setInvestorId} disabled={!requiresInvestor || locked || submitting}>
              <SelectTrigger className="bg-white border-slate-200">
                <SelectValue placeholder={requiresInvestor ? 'Select investor' : 'Not required'} />
              </SelectTrigger>
              <SelectContent>
                {investors.map((investor) => (
                  <SelectItem key={investor.id} value={String(investor.id)}>
                    {investor.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-slate-500">Reference</Label>
            <Input
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="Optional"
              disabled={locked || submitting}
              className="bg-white border-slate-200"
            />
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-slate-500">Category</Label>
            <Input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="general"
              disabled={locked || submitting}
              className="bg-white border-slate-200"
            />
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-slate-500">Date</Label>
            <Input
              type="date"
              value={txDate}
              onChange={(e) => setTxDate(e.target.value)}
              disabled={locked || submitting}
              className="bg-white border-slate-200"
            />
          </div>

          <div className="space-y-2 md:col-span-2 lg:col-span-2">
            <Label className="text-xs text-slate-500">Description</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Entry description"
              disabled={locked || submitting}
              className="bg-white border-slate-200"
            />
          </div>

          <div className="space-y-2 md:col-span-2 lg:col-span-6">
            <Label className="text-xs text-slate-500">Note</Label>
            <Input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Optional note"
              disabled={locked || submitting}
              className="bg-white border-slate-200"
            />
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between">
          <div className="space-y-1">
            {error && <p className="text-sm text-red-600">{error}</p>}
            {message && <p className="text-sm text-emerald-600">{message}</p>}
          </div>
          <Button
            onClick={handleSubmit}
            disabled={locked || submitting || !selectedClubId || !selectedPeriodId}
            className="bg-blue-600 hover:bg-blue-700 text-white"
          >
            <Plus className="w-4 h-4 mr-2" />
            Post Entry
          </Button>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h3 className="text-base font-semibold text-slate-800">Ledger History</h3>
        </div>
        {loading ? (
          <div className="p-5 text-sm text-slate-500">Loading ledger...</div>
        ) : ledger.length === 0 ? (
          <div className="p-6 flex items-center gap-3 text-slate-500">
            <CircleAlert className="w-4 h-4" />
            <span>No entries for this period.</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Type</th>
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Date</th>
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Description</th>
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Amount</th>
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Investor</th>
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Reference</th>
                  <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider py-3 px-4">Posted</th>
                  <th className="py-3 px-4"></th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((entry) => {
                  const numeric = Number(entry.amount);
                  const isPositive = numeric >= 0;
                  return (
                    <tr key={entry.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                      <td className="py-3 px-4">
                        <span className="text-sm text-slate-700 capitalize">{entry.entry_type}</span>
                      </td>
                      <td className="py-3 px-4 text-sm text-slate-500">{entry.tx_date}</td>
                      <td className="py-3 px-4 text-sm text-slate-700">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-slate-400" />
                          <span>{entry.description}</span>
                          <span className="text-xs text-slate-400">({entry.category})</span>
                        </div>
                      </td>
                      <td className={cn('py-3 px-4 text-sm font-medium', isPositive ? 'text-emerald-600' : 'text-red-500')}>
                        {isPositive ? '+' : ''}
                        {formatCurrency(Math.abs(numeric))}
                      </td>
                      <td className="py-3 px-4 text-sm text-slate-600">
                        {entry.investor_id ? investorNameById[entry.investor_id] ?? entry.investor_id : '-'}
                      </td>
                      <td className="py-3 px-4 text-sm text-slate-500">{entry.reference ?? '-'}</td>
                      <td className="py-3 px-4 text-sm text-slate-500">{new Date(entry.created_at).toLocaleString()}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1 justify-end">
                          <button
                            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-40"
                            disabled={submitting || locked || !canEditEntries}
                            onClick={() => openEdit(entry)}
                            title={canEditEntries ? 'Edit entry' : 'Edit allowed only in draft/review'}
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-40"
                            disabled={submitting || locked || !canDeleteEntries}
                            onClick={() => setDeleteTarget(entry)}
                            title={canDeleteEntries ? 'Delete entry' : 'Delete allowed only in draft'}
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
        )}
      </div>

      <Dialog
        open={editOpen}
        onOpenChange={(open) => {
          setEditOpen(open);
          if (!open) setEditingEntry(null);
        }}
      >
        <DialogContent className="bg-white border-slate-200">
          <DialogHeader>
            <DialogTitle className="text-slate-800">Edit Ledger Entry</DialogTitle>
            <DialogDescription className="text-slate-500">
              Update transaction details for this period.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-xs text-slate-500">Amount (UGX)</Label>
              <Input
                value={editAmount}
                onChange={(e) => setEditAmount(e.target.value)}
                className="bg-white border-slate-200"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs text-slate-500">Date</Label>
              <Input
                type="date"
                value={editTxDate}
                onChange={(e) => setEditTxDate(e.target.value)}
                className="bg-white border-slate-200"
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label className="text-xs text-slate-500">Description</Label>
              <Input
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                className="bg-white border-slate-200"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs text-slate-500">Category</Label>
              <Input
                value={editCategory}
                onChange={(e) => setEditCategory(e.target.value)}
                className="bg-white border-slate-200"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs text-slate-500">Reference</Label>
              <Input
                value={editReference}
                onChange={(e) => setEditReference(e.target.value)}
                className="bg-white border-slate-200"
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label className="text-xs text-slate-500">Note</Label>
              <Input
                value={editNote}
                onChange={(e) => setEditNote(e.target.value)}
                className="bg-white border-slate-200"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" className="border-slate-200 text-slate-700" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button className="bg-blue-600 hover:bg-blue-700 text-white" disabled={submitting} onClick={() => void handleUpdateEntry()}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteTarget !== null} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent className="bg-white border-slate-200">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-slate-800">Delete Entry</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-500">
              This will permanently remove ledger entry{' '}
              <span className="font-medium text-slate-700">{deleteTarget?.description ?? ''}</span>.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-slate-200 text-slate-700">Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700 text-white" onClick={() => void handleDeleteEntry()}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
