import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(value: number, currency: string = 'UGX'): string {
  if (value >= 1000000000) {
    return `${currency} ${(value / 1000000000).toFixed(2)}B`;
  } else if (value >= 1000000) {
    return `${currency} ${(value / 1000000).toFixed(2)}M`;
  } else if (value >= 1000) {
    return `${currency} ${(value / 1000).toFixed(2)}K`;
  }
  return `${currency} ${value.toFixed(2)}`;
}

export function formatNumber(value: number): string {
  if (value >= 1000000000) {
    return `${(value / 1000000000).toFixed(2)}B`;
  } else if (value >= 1000000) {
    return `${(value / 1000000).toFixed(2)}M`;
  } else if (value >= 1000) {
    return `${(value / 1000).toFixed(2)}K`;
  }
  return value.toFixed(2);
}

export function formatPercentage(value: number, decimals: number = 1): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

export function calculateOwnership(openingBalance: number, totalOpeningNAV: number): number {
  if (totalOpeningNAV === 0) return 0;
  return (openingBalance / totalOpeningNAV) * 100;
}

export function calculateNetAllocation(
  ownership: number,
  totalIncome: number,
  totalExpenses: number
): number {
  const netIncome = totalIncome - totalExpenses;
  return (ownership / 100) * netIncome;
}

export function calculateClosingBalance(
  openingBalance: number,
  contribution: number,
  withdrawal: number,
  netAllocation: number
): number {
  return openingBalance + contribution - withdrawal + netAllocation;
}

export function getTrendColor(trend: 'up' | 'down' | 'stable'): string {
  switch (trend) {
    case 'up':
      return 'text-success';
    case 'down':
      return 'text-danger';
    case 'stable':
      return 'text-muted-foreground';
    default:
      return 'text-muted-foreground';
  }
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'active':
      return 'bg-success';
    case 'review':
      return 'bg-warning';
    case 'closed':
      return 'bg-muted';
    case 'complete':
      return 'bg-success';
    case 'in-progress':
      return 'bg-warning';
    case 'pending':
      return 'bg-muted';
    default:
      return 'bg-muted';
  }
}

export function getInsightColor(type: 'positive' | 'neutral' | 'warning'): string {
  switch (type) {
    case 'positive':
      return 'border-success/30 bg-success/5';
    case 'neutral':
      return 'border-muted/30 bg-muted/5';
    case 'warning':
      return 'border-warning/30 bg-warning/5';
    default:
      return 'border-muted/30 bg-muted/5';
  }
}

export function getInsightIconColor(type: 'positive' | 'neutral' | 'warning'): string {
  switch (type) {
    case 'positive':
      return 'text-success';
    case 'neutral':
      return 'text-muted-foreground';
    case 'warning':
      return 'text-warning';
    default:
      return 'text-muted-foreground';
  }
}

export function animateCountUp(
  element: HTMLElement,
  start: number,
  end: number,
  duration: number = 1500,
  formatter: (val: number) => string = (val) => val.toFixed(0)
): void {
  const startTime = performance.now();
  
  function update(currentTime: number) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    
    // Ease out cubic
    const easeOut = 1 - Math.pow(1 - progress, 3);
    const current = start + (end - start) * easeOut;
    
    element.textContent = formatter(current);
    
    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }
  
  requestAnimationFrame(update);
}

export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null;
  
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

export function throttle<T extends (...args: unknown[]) => unknown>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false;
  
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}
