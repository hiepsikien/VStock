import type { ChartRange, Stock } from '../types';

function series(
  base: number,
  points: number,
  volatility: number,
  trend: number,
): number[] {
  const values: number[] = [];
  let price = base * (1 - trend * 0.5);
  for (let i = 0; i < points; i++) {
    const wave = Math.sin(i / 3.2) * volatility * base * 0.15;
    const noise = Math.sin(i * 1.7 + base) * volatility * base * 0.08;
    price = price + trend * (base / points) + wave * 0.02 + noise * 0.015;
    values.push(Number(price.toFixed(2)));
  }
  return values;
}

function buildHistory(base: number, changePercent: number): Record<ChartRange, number[]> {
  const trend = changePercent / 100;
  return {
    '1D': series(base, 78, 0.35, trend * 0.4),
    '1W': series(base, 48, 0.55, trend * 0.7),
    '1M': series(base, 42, 0.7, trend),
    '3M': series(base, 60, 0.9, trend * 1.2),
    '1Y': series(base, 72, 1.1, trend * 1.6),
    '5Y': series(base, 84, 1.4, trend * 2.2),
  };
}

function stock(
  partial: Omit<Stock, 'sparkline' | 'history' | 'change'> & { changePercent: number },
): Stock {
  const change = Number(((partial.price * partial.changePercent) / 100).toFixed(2));
  const history = buildHistory(partial.price, partial.changePercent);
  return {
    ...partial,
    change,
    sparkline: history['1D'],
    history,
  };
}

/** Offline fallback — VN blue chips only. */
export const FALLBACK_WATCHLIST: Stock[] = [
  stock({
    symbol: 'VNM',
    name: 'Vinamilk',
    exchange: 'HOSE',
    price: 64.5,
    changePercent: 1.26,
    open: 63.8,
    high: 64.9,
    low: 63.5,
    volume: 4_820_000,
    marketCap: '138.2T',
    pe: 16.4,
    currency: '₫',
  }),
  stock({
    symbol: 'FPT',
    name: 'FPT Corporation',
    exchange: 'HOSE',
    price: 128.3,
    changePercent: 2.15,
    open: 125.9,
    high: 129.1,
    low: 125.4,
    volume: 6_140_000,
    marketCap: '186.7T',
    pe: 22.1,
    currency: '₫',
  }),
  stock({
    symbol: 'VIC',
    name: 'Vingrouproup',
    exchange: 'HOSE',
    price: 42.15,
    changePercent: -0.82,
    open: 42.6,
    high: 42.85,
    low: 41.9,
    volume: 9_230_000,
    marketCap: '161.4T',
    pe: 28.7,
    currency: '₫',
  }),
  stock({
    symbol: 'HPG',
    name: 'Hòa Phát Group',
    exchange: 'HOSE',
    price: 27.85,
    changePercent: 0.54,
    open: 27.7,
    high: 28.05,
    low: 27.55,
    volume: 18_450_000,
    marketCap: '164.9T',
    pe: 11.2,
    currency: '₫',
  }),
  stock({
    symbol: 'MWG',
    name: 'Mobile World',
    exchange: 'HOSE',
    price: 61.2,
    changePercent: -1.45,
    open: 62.1,
    high: 62.3,
    low: 60.8,
    volume: 5_670_000,
    marketCap: '89.6T',
    pe: 14.8,
    currency: '₫',
  }),
  stock({
    symbol: 'VCB',
    name: 'Vietcombank',
    exchange: 'HOSE',
    price: 92.4,
    changePercent: 0.33,
    open: 92.1,
    high: 93.0,
    low: 91.8,
    volume: 3_210_000,
    marketCap: '517.8T',
    pe: 13.5,
    currency: '₫',
  }),
  stock({
    symbol: 'TCB',
    name: 'Techcombank',
    exchange: 'HOSE',
    price: 24.8,
    changePercent: 0.81,
    open: 24.6,
    high: 25.0,
    low: 24.5,
    volume: 12_100_000,
    marketCap: '175.0T',
    pe: 9.8,
    currency: '₫',
  }),
  stock({
    symbol: 'MBB',
    name: 'MB Bank',
    exchange: 'HOSE',
    price: 24.15,
    changePercent: -0.41,
    open: 24.3,
    high: 24.45,
    low: 24.0,
    volume: 15_600_000,
    marketCap: '128.4T',
    pe: 7.6,
    currency: '₫',
  }),
  stock({
    symbol: 'GAS',
    name: 'PetroVietnam Gas',
    exchange: 'HOSE',
    price: 74.2,
    changePercent: 0.27,
    open: 74.0,
    high: 74.8,
    low: 73.6,
    volume: 1_450_000,
    marketCap: '142.0T',
    pe: 15.2,
    currency: '₫',
  }),
  stock({
    symbol: 'MSN',
    name: 'Masan Group',
    exchange: 'HOSE',
    price: 72.5,
    changePercent: -1.09,
    open: 73.4,
    high: 73.6,
    low: 72.1,
    volume: 3_880_000,
    marketCap: '104.3T',
    pe: 31.5,
    currency: '₫',
  }),
];

export function getFallbackStock(symbol: string): Stock | undefined {
  return FALLBACK_WATCHLIST.find((s) => s.symbol === symbol.toUpperCase());
}

export function formatPrice(price: number, currency: string): string {
  if (currency === 'USD' || currency === '$') {
    return `$${price.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
  if (currency === '₫') {
    return price.toLocaleString('vi-VN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  return price.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatChange(change: number): string {
  const sign = change >= 0 ? '+' : '';
  return `${sign}${change.toFixed(2)}`;
}

export function formatPercent(percent: number): string {
  const sign = percent >= 0 ? '+' : '';
  return `${sign}${percent.toFixed(2)}%`;
}

export function formatVolume(volume: number): string {
  if (volume >= 1_000_000_000) return `${(volume / 1_000_000_000).toFixed(2)}B`;
  if (volume >= 1_000_000) return `${(volume / 1_000_000).toFixed(2)}M`;
  if (volume >= 1_000) return `${(volume / 1_000).toFixed(1)}K`;
  return String(volume);
}

/** Compact market-cap labels (Apple Stocks style): nghìn tỷ → NT. */
export function formatMarketCapLabel(cap: string): string {
  return cap
    .replace(/\s*nghìn\s*tỷ/gi, ' NT')
    .replace(/\s*tỷ\b/gi, ' T')
    .replace(/\s*triệu\b/gi, ' Tr')
    .trim();
}
