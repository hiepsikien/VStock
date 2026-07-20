import type { ChartRange, Stock } from '../types';
import type { NewsItem } from '../types/news';

const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
);

export const DEFAULT_SYMBOLS = [
  'VNM',
  'FPT',
  'VIC',
  'HPG',
  'MWG',
  'VCB',
  'TCB',
  'MBB',
  'GAS',
  'MSN',
];

type WatchlistDto = {
  symbol: string;
  name: string;
  exchange: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  currency: string;
  sparkline: number[];
};

type StockDetailDto = WatchlistDto & {
  open: number;
  high: number;
  low: number;
  marketCap: string;
  pe: number | null;
};

type HistoryDto = {
  symbol: string;
  range: ChartRange;
  prices: number[];
};

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

function toStock(dto: StockDetailDto, history?: Partial<Record<ChartRange, number[]>>): Stock {
  return {
    symbol: dto.symbol,
    name: dto.name,
    exchange: dto.exchange,
    price: dto.price,
    change: dto.change,
    changePercent: dto.changePercent,
    open: dto.open,
    high: dto.high,
    low: dto.low,
    volume: dto.volume,
    marketCap: dto.marketCap,
    pe: dto.pe,
    currency: dto.currency || '₫',
    sparkline: dto.sparkline ?? [],
    history: {
      '1D': history?.['1D'] ?? dto.sparkline ?? [],
      '1W': history?.['1W'] ?? [],
      '1M': history?.['1M'] ?? [],
      '3M': history?.['3M'] ?? [],
      '1Y': history?.['1Y'] ?? [],
      '5Y': history?.['5Y'] ?? [],
    },
  };
}

export async function fetchWatchlist(symbols: string[] = DEFAULT_SYMBOLS): Promise<Stock[]> {
  const qs = symbols.join(',');
  const rows = await apiGet<WatchlistDto[]>(`/v1/watchlist?symbols=${encodeURIComponent(qs)}`);
  return rows.map((row) =>
    toStock({
      ...row,
      open: row.price,
      high: row.price,
      low: row.price,
      marketCap: '—',
      pe: null,
    }),
  );
}

export async function fetchStockDetail(symbol: string): Promise<Stock> {
  const detail = await apiGet<StockDetailDto>(`/v1/stocks/${encodeURIComponent(symbol)}`);
  const day = await apiGet<HistoryDto>(
    `/v1/stocks/${encodeURIComponent(symbol)}/history?range=1D`,
  ).catch(() => ({ symbol, range: '1D' as const, prices: detail.sparkline }));

  return toStock(detail, { '1D': day.prices });
}

export async function fetchHistory(symbol: string, range: ChartRange): Promise<number[]> {
  const data = await apiGet<HistoryDto>(
    `/v1/stocks/${encodeURIComponent(symbol)}/history?range=${range}`,
  );
  return data.prices;
}

export type MarketSymbol = {
  symbol: string;
  name: string;
  exchange: string;
};

export async function fetchMarketSymbols(exchange?: 'HOSE' | 'HNX'): Promise<MarketSymbol[]> {
  const qs = exchange ? `?exchange=${exchange}` : '';
  const data = await apiGet<{ count: number; symbols: MarketSymbol[] }>(`/v1/symbols${qs}`);
  return data.symbols;
}

export async function searchMarketSymbols(query: string, limit = 30): Promise<MarketSymbol[]> {
  const q = query.trim();
  if (!q) return [];
  return apiGet<MarketSymbol[]>(
    `/v1/symbols/search?q=${encodeURIComponent(q)}&limit=${limit}`,
  );
}

export async function fetchMarketNews(limit = 30): Promise<NewsItem[]> {
  const data = await apiGet<{ items: NewsItem[] }>(`/v1/news/market?limit=${limit}`);
  return data.items;
}

export async function fetchSymbolNews(symbol: string, limit = 15): Promise<NewsItem[]> {
  const data = await apiGet<{ items: NewsItem[] }>(
    `/v1/news/symbols/${encodeURIComponent(symbol)}?limit=${limit}`,
  );
  return data.items;
}

export function getApiUrl(): string {
  return API_URL;
}
