import { cn, getInsightColor, getInsightIconColor } from '@/lib/utils';
import { AlertTriangle, CheckCircle, Info } from 'lucide-react';

interface InsightCardProps {
  type: 'positive' | 'neutral' | 'warning';
  title: string;
  description: string;
  metric?: string;
  trend?: string;
  delay?: number;
}

export function InsightCard({
  type,
  title,
  description,
  metric,
  trend,
  delay = 0,
}: InsightCardProps) {
  const getIcon = () => {
    switch (type) {
      case 'positive':
        return <CheckCircle className="w-6 h-6" />;
      case 'warning':
        return <AlertTriangle className="w-6 h-6" />;
      case 'neutral':
      default:
        return <Info className="w-6 h-6" />;
    }
  };

  const getTypeLabel = () => {
    switch (type) {
      case 'positive':
        return 'Positive';
      case 'warning':
        return 'Attention';
      case 'neutral':
      default:
        return 'Info';
    }
  };

  return (
    <div
      className={cn(
        'relative p-5 rounded-xl border overflow-hidden group',
        'transition-all duration-500 hover:shadow-lg',
        'hover:-translate-y-1',
        getInsightColor(type),
        'animate-slide-up'
      )}
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className={cn('p-2.5 rounded-lg', getInsightIconColor(type))}>
          {getIcon()}
        </div>
        <span className={cn(
          'text-xs font-medium px-2 py-1 rounded-full',
          type === 'positive' && 'bg-success/20 text-success',
          type === 'warning' && 'bg-warning/20 text-warning',
          type === 'neutral' && 'bg-muted/50 text-muted-foreground'
        )}>
          {getTypeLabel()}
        </span>
      </div>

      {/* Content */}
      <div className="space-y-2">
        <h4 className="font-semibold text-white">{title}</h4>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {description}
        </p>
      </div>

      {/* Metric */}
      {metric && (
        <div className="mt-4 pt-4 border-t border-border/30">
          <div className="flex items-center justify-between">
            <span className={cn('text-2xl font-bold font-mono', getInsightIconColor(type))}>
              {metric}
            </span>
            {trend && (
              <span className="text-sm text-muted-foreground">{trend}</span>
            )}
          </div>
        </div>
      )}

      {/* Hover effect */}
      <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
    </div>
  );
}
