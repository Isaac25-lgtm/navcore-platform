import { cn, formatCurrency, formatPercentage } from '@/lib/utils';
import { Progress } from '@/components/ui/progress';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface InvestorRowProps {
  name: string;
  openingBalance: number;
  ownership: number;
  contribution: number;
  withdrawal: number;
  netAllocation: number;
  closingBalance: number;
  delay?: number;
}

export function InvestorRow({
  name,
  openingBalance,
  ownership,
  contribution,
  withdrawal,
  netAllocation,
  closingBalance,
  delay = 0,
}: InvestorRowProps) {
  const netChange = closingBalance - openingBalance;
  const changePercent = openingBalance > 0 ? (netChange / openingBalance) * 100 : 0;

  return (
    <tr
      className={cn(
        'group border-b border-border/30 transition-all duration-300',
        'hover:bg-white/[0.02]'
      )}
      style={{ animationDelay: `${delay}ms` }}
    >
      <td className="py-4 px-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary/30 to-cyan-500/30 flex items-center justify-center text-sm font-medium text-white">
            {name.charAt(0)}
          </div>
          <span className="font-medium text-white">{name}</span>
        </div>
      </td>
      
      <td className="py-4 px-4">
        <span className="font-mono text-muted-foreground">
          {formatCurrency(openingBalance)}
        </span>
      </td>
      
      <td className="py-4 px-4">
        <div className="flex items-center gap-3">
          <Progress 
            value={ownership} 
            className="w-20 h-1.5 bg-border"
          />
          <span className="font-mono text-sm text-white">
            {formatPercentage(ownership, 1)}
          </span>
        </div>
      </td>
      
      <td className="py-4 px-4">
        <span className="font-mono text-success">
          +{formatCurrency(contribution)}
        </span>
      </td>
      
      <td className="py-4 px-4">
        <span className="font-mono text-danger">
          -{formatCurrency(withdrawal)}
        </span>
      </td>
      
      <td className="py-4 px-4">
        <span className={cn(
          'font-mono',
          netAllocation >= 0 ? 'text-success' : 'text-danger'
        )}>
          {netAllocation >= 0 ? '+' : ''}{formatCurrency(netAllocation)}
        </span>
      </td>
      
      <td className="py-4 px-4">
        <div className="flex items-center gap-2">
          <span className="font-mono font-semibold text-white">
            {formatCurrency(closingBalance)}
          </span>
          {changePercent !== 0 && (
            <span className={cn(
              'flex items-center gap-0.5 text-xs',
              changePercent > 0 ? 'text-success' : 'text-danger'
            )}>
              {changePercent > 0 ? (
                <TrendingUp className="w-3 h-3" />
              ) : (
                <TrendingDown className="w-3 h-3" />
              )}
              {Math.abs(changePercent).toFixed(1)}%
            </span>
          )}
        </div>
      </td>
    </tr>
  );
}
