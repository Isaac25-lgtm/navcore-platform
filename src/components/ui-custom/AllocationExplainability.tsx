import { useMemo, useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { formatCurrency, formatPercentage } from '@/lib/utils';

interface AllocationRow {
  investor_id: number;
  opening_balance: number;
  ownership_pct: number;
  income_share: number;
  expense_share: number;
  net_alloc: number;
  contributions: number;
  withdrawals: number;
  closing_balance: number;
}

interface AllocationExplainabilityProps {
  rows: AllocationRow[];
  returnDecomposition: {
    cashflows: number;
    income: number;
    expenses: number;
    net_result: number;
  } | null;
}

export function AllocationExplainability({ rows, returnDecomposition }: AllocationExplainabilityProps) {
  const [selectedInvestorId, setSelectedInvestorId] = useState<number | null>(rows[0]?.investor_id ?? null);

  const selected = useMemo(
    () => rows.find((row) => row.investor_id === selectedInvestorId) ?? rows[0] ?? null,
    [rows, selectedInvestorId],
  );

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-800">Allocation Explainability</h3>
          <p className="text-xs text-slate-500">Ownership and allocation decomposition for selected investor.</p>
        </div>
        <Select
          value={selected ? String(selected.investor_id) : ''}
          onValueChange={(value) => setSelectedInvestorId(Number(value))}
        >
          <SelectTrigger className="w-[140px] bg-white border-slate-200">
            <SelectValue placeholder="Investor" />
          </SelectTrigger>
          <SelectContent>
            {rows.map((row) => (
              <SelectItem key={row.investor_id} value={String(row.investor_id)}>
                Investor {row.investor_id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <div className="bg-slate-50 p-3 rounded-xl">
          <p className="text-xs text-slate-500">Ownership %</p>
          <p className="text-sm text-slate-700">= Opening Balance / Club Opening NAV</p>
        </div>
        <div className="bg-slate-50 p-3 rounded-xl">
          <p className="text-xs text-slate-500">Net Allocation</p>
          <p className="text-sm text-slate-700">= Income Share - Expense Share</p>
        </div>
        <div className="bg-slate-50 p-3 rounded-xl">
          <p className="text-xs text-slate-500">Closing Balance</p>
          <p className="text-sm text-slate-700">= Opening + Net + Contributions - Withdrawals</p>
        </div>
      </div>

      {selected ? (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="bg-blue-50 rounded-xl p-3">
            <p className="text-xs text-blue-700">Ownership</p>
            <p className="text-sm font-semibold text-blue-700">{formatPercentage(selected.ownership_pct, 2)}</p>
          </div>
          <div className="bg-emerald-50 rounded-xl p-3">
            <p className="text-xs text-emerald-700">Income Share</p>
            <p className="text-sm font-semibold text-emerald-700">{formatCurrency(selected.income_share)}</p>
          </div>
          <div className="bg-red-50 rounded-xl p-3">
            <p className="text-xs text-red-700">Expense Share</p>
            <p className="text-sm font-semibold text-red-700">{formatCurrency(selected.expense_share)}</p>
          </div>
          <div className="bg-slate-50 rounded-xl p-3">
            <p className="text-xs text-slate-600">Net Allocation</p>
            <p className="text-sm font-semibold text-slate-700">{formatCurrency(selected.net_alloc)}</p>
          </div>
          <div className="bg-amber-50 rounded-xl p-3">
            <p className="text-xs text-amber-700">Closing Balance</p>
            <p className="text-sm font-semibold text-amber-700">{formatCurrency(selected.closing_balance)}</p>
          </div>
        </div>
      ) : (
        <p className="text-sm text-slate-500">No investor allocation rows available for this period.</p>
      )}

      {returnDecomposition && (
        <div className="mt-4 p-3 rounded-xl bg-slate-50 border border-slate-200">
          <p className="text-xs text-slate-600">Return decomposition</p>
          <p className="text-xs text-slate-500 mt-1">
            Cashflows {formatCurrency(returnDecomposition.cashflows)} | Income {formatCurrency(returnDecomposition.income)} |
            Expenses {formatCurrency(returnDecomposition.expenses)} | Net {formatCurrency(returnDecomposition.net_result)}
          </p>
        </div>
      )}
    </div>
  );
}
