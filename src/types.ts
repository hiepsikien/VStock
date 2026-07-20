export type ChartRange = '1D' | '1W' | '1M' | '3M' | '1Y' | '5Y';

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
  currency: string;
  sparkline: number[];
  history: Record<ChartRange, number[]>;
};
