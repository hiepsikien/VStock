import type { ChartRange, Stock } from '../types';
import type { NewsItem } from '../types/news';
import { readNewsCache, readNewsMemory, writeNewsCache } from '../storage/newsCache';
import type { IndexQuote } from '../components/WatchlistSummary';

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
  if (symbols.length === 0) return [];

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

async function readMarketNewsCache(limit: number): Promise<NewsItem[] | null> {
  const exact = readNewsMemory(`market:${limit}`) ?? (await readNewsCache(`market:${limit}`));
  if (exact) return exact;

  if (limit > 30) {
    const full = readNewsMemory('market:30') ?? (await readNewsCache('market:30'));
    if (full?.length) return full.slice(0, limit);
  }
  if (limit > 5) {
    const preview = readNewsMemory('market:5') ?? (await readNewsCache('market:5'));
    if (preview?.length) return preview;
  }
  return null;
}

async function fetchMarketNewsNetwork(limit: number): Promise<NewsItem[]> {
  const data = await apiGet<{ items: NewsItem[] }>(`/v1/news/market?limit=${limit}`);
  return data.items;
}

async function fetchSymbolNewsNetwork(symbol: string, limit: number): Promise<NewsItem[]> {
  const data = await apiGet<{ items: NewsItem[] }>(
    `/v1/news/symbols/${encodeURIComponent(symbol)}?limit=${limit}`,
  );
  return data.items;
}

export async function fetchMarketNews(
  limit = 30,
  options?: { refresh?: boolean },
): Promise<NewsItem[]> {
  const cacheKey = `market:${limit}`;
  if (!options?.refresh) {
    const cached = await readMarketNewsCache(limit);
    if (cached) return cached;
  }

  const items = await fetchMarketNewsNetwork(limit);
  await writeNewsCache(cacheKey, items);
  return items;
}

export async function fetchSymbolNews(
  symbol: string,
  limit = 15,
  options?: { refresh?: boolean },
): Promise<NewsItem[]> {
  const sym = symbol.toUpperCase();
  const cacheKey = `symbol:${sym}:${limit}`;
  if (!options?.refresh) {
    const cached = readNewsMemory(cacheKey) ?? (await readNewsCache(cacheKey));
    if (cached) return cached;
  }

  const items = await fetchSymbolNewsNetwork(sym, limit);
  await writeNewsCache(cacheKey, items);
  return items;
}

/** Stale-while-revalidate: show cache immediately, fetch fresh in background. */
export async function loadMarketNews(
  limit: number,
  handlers: {
    onData: (items: NewsItem[], fromCache: boolean) => void;
    refresh?: boolean;
  },
): Promise<void> {
  let showedCache = false;

  if (!handlers.refresh) {
    const cached = await readMarketNewsCache(limit);
    if (cached?.length) {
      showedCache = true;
      handlers.onData(cached, true);
    }
  }

  try {
    const items = await fetchMarketNewsNetwork(limit);
    await writeNewsCache(`market:${limit}`, items);
    if (!showedCache || items.length > 0) {
      handlers.onData(items, false);
    }
  } catch {
    if (!showedCache) handlers.onData([], false);
  }
}

export async function loadSymbolNews(
  symbol: string,
  limit: number,
  handlers: {
    onData: (items: NewsItem[], fromCache: boolean) => void;
    refresh?: boolean;
  },
): Promise<void> {
  const sym = symbol.toUpperCase();
  const cacheKey = `symbol:${sym}:${limit}`;
  let showedCache = false;

  if (!handlers.refresh) {
    const cached = readNewsMemory(cacheKey) ?? (await readNewsCache(cacheKey));
    if (cached?.length) {
      showedCache = true;
      handlers.onData(cached, true);
    }
  }

  try {
    const items = await fetchSymbolNewsNetwork(sym, limit);
    await writeNewsCache(cacheKey, items);
    if (!showedCache || items.length > 0) {
      handlers.onData(items, false);
    }
  } catch {
    if (!showedCache) handlers.onData([], false);
  }
}

export function getApiUrl(): string {
  return API_URL;
}

export async function fetchMarketIndices(): Promise<IndexQuote[]> {
  const data = await apiGet<{ items: IndexQuote[] }>('/v1/indices');
  return data.items;
}
