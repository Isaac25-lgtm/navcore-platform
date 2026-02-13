import { useEffect, useRef, useState } from 'react';
import { cn, formatCurrency, formatPercentage, formatNumber } from '@/lib/utils';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: number;
  prefix?: string;
  suffix?: string;
  trend?: number;
  trendLabel?: string;
  format?: 'currency' | 'percentage' | 'number';
  currency?: string;
  className?: string;
  delay?: number;
  subValue?: string;
}

export function MetricCard({
  title,
  value,
  prefix = '',
  suffix = '',
  trend,
  trendLabel,
  format = 'number',
  currency = 'UGX',
  className,
  delay = 0,
  subValue,
}: MetricCardProps) {
  const valueRef = useRef<HTMLSpanElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), delay);
    return () => clearTimeout(timer);
  }, [delay]);

  useEffect(() => {
    if (isVisible && valueRef.current) {
      const formatter = (val: number) => {
        let formatted = '';
        switch (format) {
          case 'currency':
            formatted = formatCurrency(val, currency);
            break;
          case 'percentage':
            formatted = formatPercentage(val);
            break;
          case 'number':
          default:
            formatted = formatNumber(val);
        }
        return `${prefix}${formatted}${suffix}`;
      };

      const duration = 800;
      const startTime = performance.now();
      const startValue = 0;

      const animate = (currentTime: number) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = startValue + (value - startValue) * easeOut;

        if (valueRef.current) {
          valueRef.current.textContent = formatter(current);
        }

        if (progress < 1) {
          requestAnimationFrame(animate);
        }
      };

      requestAnimationFrame(animate);
    }
  }, [isVisible, value, format, currency, prefix, suffix]);

  const getTrendIcon = () => {
    if (trend === undefined || trend === 0) return <Minus className="w-3 h-3" />;
    if (trend > 0) return <TrendingUp className="w-3 h-3" />;
    return <TrendingDown className="w-3 h-3" />;
  };

  const getTrendColor = () => {
    if (trend === undefined || trend === 0) return 'text-slate-500';
    if (trend > 0) return 'text-emerald-400';
    return 'text-red-400';
  };

  return (
    <div
      className={cn(
        'bg-[#0f1117] border border-slate-800 p-4',
        'hover:border-slate-700 transition-colors duration-200',
        className
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">{title}</span>
        {trend !== undefined && (
          <div className={cn('flex items-center gap-1 text-xs', getTrendColor())}>
            {getTrendIcon()}
            <span>{trend > 0 ? '+' : ''}{trend}%</span>
          </div>
        )}
      </div>

      <div className="space-y-1">
        <span
          ref={valueRef}
          className="text-2xl font-semibold font-mono text-slate-100 block"
        >
          {prefix}
          {format === 'currency' && formatCurrency(0, currency)}
          {format === 'percentage' && formatPercentage(0)}
          {format === 'number' && formatNumber(0)}
          {suffix}
        </span>
        
        {subValue && (
          <span className="text-xs text-slate-600">{subValue}</span>
        )}
        
        {trendLabel && !subValue && (
          <span className="text-xs text-slate-600">{trendLabel}</span>
        )}
      </div>
    </div>
  );
}
