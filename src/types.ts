export type ChartRange = '1D' | '1W' | '1M' | '3M' | '1Y' | '5Y';

export type IncomePeriod = {
  periodType: 'annual' | 'quarter';
  fiscalDate: string;
  year: number;
  quarter?: number | null;
  netRevenue?: number | null;
  netIncome?: number | null;
};

export type Stock = {
  symbol: string;
  name: string;
  exchange: string;
  price: number;
  change: number;
  changePercent: number;
  open: number;
  high: number;
  low: number;
  priorClose?: number | null;
  volume: number;
  marketCap: string;
  pe: number | null;
  eps?: number | null;
  pb?: number | null;
  roe?: number | null;
  roa?: number | null;
  dividendYield?: number | null;
  revenueLabel?: string | null;
  incomeLatestAnnual?: IncomePeriod | null;
  incomeLastQuarters?: IncomePeriod[];
  currency: string;
  sparkline: number[];
  history: Record<ChartRange, number[]>;
  /** Listed symbol but quote feed has no live data yet */
  unavailable?: boolean;
};
