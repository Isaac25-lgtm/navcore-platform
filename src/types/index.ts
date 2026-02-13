export interface Club {
  id: string;
  name: string;
  nav: number;
  return: number;
  returnTrend: 'up' | 'down' | 'stable';
  investors: number;
  status: 'active' | 'review' | 'closed';
  openingNAV: number;
  contributions: number;
  withdrawals: number;
  income: number;
  expenses: number;
  closingNAV: number;
}

export interface Investor {
  id: string;
  name: string;
  openingBalance: number;
  ownership: number;
  contribution: number;
  withdrawal: number;
  netAllocation: number;
  closingBalance: number;
  clubId: string;
}

export interface MonthlyData {
  month: string;
  openingNAV: number;
  contributions: number;
  withdrawals: number;
  income: number;
  expenses: number;
  closingNAV: number;
}

export interface Insight {
  id: string;
  type: 'positive' | 'neutral' | 'warning';
  title: string;
  description: string;
  metric?: string;
  trend?: string;
}

export interface Report {
  id: string;
  name: string;
  description: string;
  lastGenerated: string;
  icon: string;
}

export interface ProcessStep {
  id: string;
  title: string;
  description: string;
  status: 'complete' | 'in-progress' | 'pending';
}

export interface NavMetric {
  label: string;
  value: number;
  prefix?: string;
  suffix?: string;
  trend?: number;
  trendLabel?: string;
}
