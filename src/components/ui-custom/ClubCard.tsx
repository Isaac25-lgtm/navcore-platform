import { cn, formatCurrency, formatPercentage } from '@/lib/utils';
import { Building2, Users, TrendingUp, TrendingDown, Minus, ArrowUpRight } from 'lucide-react';

interface ClubCardProps {
  name: string;
  nav: number;
  return: number;
  returnTrend: 'up' | 'down' | 'stable';
  investors: number;
  status: 'active' | 'review' | 'closed';
  onClick?: () => void;
}

export function ClubCard({
  name,
  nav,
  return: returnValue,
  returnTrend,
  investors,
  status,
  onClick,
}: ClubCardProps) {
  const getTrendIcon = () => {
    switch (returnTrend) {
      case 'up':
        return <TrendingUp className="w-3.5 h-3.5" />;
      case 'down':
        return <TrendingDown className="w-3.5 h-3.5" />;
      default:
        return <Minus className="w-3.5 h-3.5" />;
    }
  };

  const getTrendColor = () => {
    switch (returnTrend) {
      case 'up':
        return 'text-emerald-400';
      case 'down':
        return 'text-red-400';
      default:
        return 'text-slate-500';
    }
  };

  const getStatusBadge = () => {
    switch (status) {
      case 'active':
        return (
          <span className="flex items-center gap-1.5 text-xs">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />
            <span className="text-emerald-400">Active</span>
          </span>
        );
      case 'review':
        return (
          <span className="flex items-center gap-1.5 text-xs">
            <span className="w-1.5 h-1.5 bg-amber-500 rounded-full" />
            <span className="text-amber-400">Review</span>
          </span>
        );
      case 'closed':
        return (
          <span className="flex items-center gap-1.5 text-xs">
            <span className="w-1.5 h-1.5 bg-slate-500 rounded-full" />
            <span className="text-slate-500">Closed</span>
          </span>
        );
    }
  };

  return (
    <div
      onClick={onClick}
      className={cn(
        'bg-[#0f1117] border border-slate-800 p-4 cursor-pointer',
        'hover:border-slate-700 transition-all duration-200',
        'group'
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-slate-800 rounded flex items-center justify-center">
            <Building2 className="w-4 h-4 text-slate-400" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-slate-200 group-hover:text-blue-400 transition-colors">
              {name}
            </h3>
            {getStatusBadge()}
          </div>
        </div>
        <ArrowUpRight className="w-4 h-4 text-slate-600 group-hover:text-blue-400 transition-colors opacity-0 group-hover:opacity-100" />
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-4 mb-3">
        <div>
          <p className="text-xs text-slate-500 mb-1">NAV</p>
          <p className="text-lg font-mono font-medium text-slate-200">
            {formatCurrency(nav)}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-500 mb-1">Return</p>
          <div className={cn('flex items-center gap-1', getTrendColor())}>
            {getTrendIcon()}
            <span className="text-lg font-mono font-medium">
              {formatPercentage(returnValue)}
            </span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-slate-800/50">
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <Users className="w-3.5 h-3.5" />
          <span>{investors} Investors</span>
        </div>
        <div className="flex -space-x-1.5">
          {[...Array(Math.min(3, investors))].map((_, i) => (
            <div 
              key={i} 
              className="w-5 h-5 rounded-full bg-slate-700 border border-[#0f1117] flex items-center justify-center"
            >
              <span className="text-[8px] text-slate-400">{String.fromCharCode(65 + i)}</span>
            </div>
          ))}
          {investors > 3 && (
            <div className="w-5 h-5 rounded-full bg-slate-800 border border-[#0f1117] flex items-center justify-center">
              <span className="text-[8px] text-slate-500">+{investors - 3}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
