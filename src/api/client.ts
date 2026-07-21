import type { ChartRange, Stock } from '../types';
import type { NewsItem } from '../types/news';
import { readNewsCache, readNewsMemory, writeNewsCache } from '../storage/newsCache';
import {
  readDetailCache,
  readDetailCacheStale,
  readHistoryCache,
  readHistoryCacheStale,
  readIndicesCache,
  readIndicesCacheStale,
  readQuotesCache,
  readQuotesCacheStale,
  writeDetailCache,
  writeHistoryCache,
  writeIndicesCache,
  writeQuotesCache,
} from '../storage/marketCache';
import type { IndexQuote } from '../components/WatchlistSummary';
import { sanitizePriceChange } from '../utils/sanitizePriceChange';

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
  priorClose?: number | null;
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
  const change = sanitizePriceChange(dto.price, dto.change, dto.changePercent);
  return {
    symbol: dto.symbol,
    name: dto.name,
    exchange: dto.exchange,
    price: dto.price,
    change,
    changePercent: dto.changePercent,
    open: dto.open,
    high: dto.high,
    low: dto.low,
    priorClose: dto.priorClose ?? null,
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
  try {
    const rows = await apiGet<WatchlistDto[]>(`/v1/watchlist?symbols=${encodeURIComponent(qs)}`);
    const stocks = rows.map((row) =>
      toStock({
        ...row,
        open: row.price,
        high: row.price,
        low: row.price,
        marketCap: '—',
        pe: null,
      }),
    );
    await writeQuotesCache(stocks);
    return stocks;
  } catch (err) {
    const stale = await readQuotesCacheStale(symbols);
    if (stale?.items.length) return stale.items;
    throw err;
  }
}

async function fetchWatchlistNetwork(symbols: string[]): Promise<Stock[]> {
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

/** Stale-while-revalidate for watchlist quotes. */
export async function loadWatchlist(
  symbols: string[],
  handlers: {
    onData: (stocks: Stock[], fromCache: boolean, fetchedAt?: number) => void;
    refresh?: boolean;
  },
): Promise<void> {
  if (symbols.length === 0) {
    handlers.onData([], false);
    return;
  }

  let showedCache = false;

  if (!handlers.refresh) {
    const cached = await readQuotesCache(symbols);
    if (cached?.items.length) {
      showedCache = true;
      handlers.onData(
        cached.items.map((stock) => ({
          ...stock,
          change: sanitizePriceChange(stock.price, stock.change, stock.changePercent),
        })),
        true,
        cached.fetchedAt,
      );
    }
  }

  try {
    const stocks = await fetchWatchlistNetwork(symbols);
    await writeQuotesCache(stocks);
    if (!showedCache || stocks.length > 0) {
      handlers.onData(stocks, false);
    }
  } catch {
    if (!showedCache) {
      const stale = await readQuotesCacheStale(symbols);
      if (stale?.items.length) {
        handlers.onData(stale.items, true, stale.fetchedAt);
        return;
      }
      throw new Error('Không kết nối được máy chủ');
    }
  }
}

async function fetchStockDetailNetwork(symbol: string): Promise<Stock> {
  const sym = symbol.toUpperCase();
  const detail = await apiGet<StockDetailDto>(`/v1/stocks/${encodeURIComponent(sym)}`);
  const day = await apiGet<HistoryDto>(
    `/v1/stocks/${encodeURIComponent(sym)}/history?range=1D`,
  ).catch(() => ({ symbol: sym, range: '1D' as const, prices: detail.sparkline }));

  return toStock(detail, { '1D': day.prices });
}

export async function fetchStockDetail(symbol: string): Promise<Stock> {
  try {
    const stock = await fetchStockDetailNetwork(symbol);
    await writeDetailCache(stock);
    await writeHistoryCache(symbol, '1D', stock.history['1D']);
    return stock;
  } catch (err) {
    const stale = await readDetailCacheStale(symbol);
    if (stale) return stale.data;
    throw err;
  }
}

/** Stale-while-revalidate for stock detail + 1D chart. */
export async function loadStockDetail(
  symbol: string,
  handlers: {
    onData: (stock: Stock, fromCache: boolean, fetchedAt?: number) => void;
    refresh?: boolean;
  },
): Promise<void> {
  const sym = symbol.toUpperCase();
  let showedCache = false;

  if (!handlers.refresh) {
    const cached = await readDetailCache(sym);
    if (cached) {
      showedCache = true;
      const entry = await readDetailCacheStale(sym);
      handlers.onData(cached, true, entry?.fetchedAt);
    }
  }

  try {
    const stock = await fetchStockDetailNetwork(sym);
    await writeDetailCache(stock);
    await writeHistoryCache(sym, '1D', stock.history['1D']);
    handlers.onData(stock, false);
  } catch {
    if (!showedCache) {
      const stale = await readDetailCacheStale(sym);
      if (stale) {
        handlers.onData(stale.data, true, stale.fetchedAt);
        return;
      }
      throw new Error('Không kết nối được máy chủ');
    }
  }
}

async function fetchHistoryNetwork(symbol: string, range: ChartRange): Promise<number[]> {
  const sym = symbol.toUpperCase();
  const data = await apiGet<HistoryDto>(
    `/v1/stocks/${encodeURIComponent(sym)}/history?range=${range}`,
  );
  return data.prices;
}

export async function fetchHistory(symbol: string, range: ChartRange): Promise<number[]> {
  try {
    const prices = await fetchHistoryNetwork(symbol, range);
    await writeHistoryCache(symbol, range, prices);
    return prices;
  } catch (err) {
    const stale = await readHistoryCacheStale(symbol, range);
    if (stale) return stale.data;
    throw err;
  }
}

/** Stale-while-revalidate for chart history. */
export async function loadHistory(
  symbol: string,
  range: ChartRange,
  handlers: {
    onData: (prices: number[], fromCache: boolean, fetchedAt?: number) => void;
    refresh?: boolean;
  },
): Promise<void> {
  const sym = symbol.toUpperCase();
  let showedCache = false;

  if (!handlers.refresh) {
    const cached = await readHistoryCache(sym, range);
    if (cached?.length) {
      showedCache = true;
      const entry = await readHistoryCacheStale(sym, range);
      handlers.onData(cached, true, entry?.fetchedAt);
    }
  }

  try {
    const prices = await fetchHistoryNetwork(sym, range);
    await writeHistoryCache(sym, range, prices);
    handlers.onData(prices, false);
  } catch {
    if (!showedCache) {
      const stale = await readHistoryCacheStale(sym, range);
      if (stale) {
        handlers.onData(stale.data, true, stale.fetchedAt);
        return;
      }
      throw new Error('Không tải được biểu đồ');
    }
  }
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

async function fetchMarketNewsNetwork(
  limit: number,
  category?: string,
): Promise<NewsItem[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (category && category !== 'all') {
    params.set('category', category);
  }
  const data = await apiGet<{ items: NewsItem[] }>(`/v1/news/market?${params.toString()}`);
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
  options?: { refresh?: boolean; category?: string },
): Promise<NewsItem[]> {
  const category = options?.category && options.category !== 'all' ? options.category : undefined;
  const cacheKey = `market:${limit}:${category ?? 'all'}`;
  if (!options?.refresh) {
    const cached = await readNewsCache(cacheKey);
    if (cached) return cached;
  }

  const items = await fetchMarketNewsNetwork(limit, category);
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
    category?: string;
  },
): Promise<void> {
  const category =
    handlers.category && handlers.category !== 'all' ? handlers.category : undefined;
  const cacheKey = `market:${limit}:${category ?? 'all'}`;
  let showedCache = false;

  if (!handlers.refresh) {
    const cached = readNewsMemory(cacheKey) ?? (await readNewsCache(cacheKey));
    if (cached?.length) {
      showedCache = true;
      handlers.onData(cached, true);
    } else if (!category) {
      const legacy = await readMarketNewsCache(limit);
      if (legacy?.length) {
        showedCache = true;
        handlers.onData(legacy, true);
      }
    }
  }

  try {
    const items = await fetchMarketNewsNetwork(limit, category);
    await writeNewsCache(cacheKey, items);
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

async function fetchMarketIndicesNetwork(): Promise<IndexQuote[]> {
  const data = await apiGet<{ items: IndexQuote[] }>('/v1/indices');
  return data.items;
}

export async function fetchMarketIndices(): Promise<IndexQuote[]> {
  try {
    const items = await fetchMarketIndicesNetwork();
    await writeIndicesCache(items);
    return items;
  } catch (err) {
    const stale = await readIndicesCacheStale();
    if (stale?.items.length) return stale.items;
    throw err;
  }
}

/** Stale-while-revalidate for market indices. */
export async function loadMarketIndices(handlers: {
  onData: (items: IndexQuote[], fromCache: boolean, fetchedAt?: number) => void;
  refresh?: boolean;
}): Promise<void> {
  let showedCache = false;

  if (!handlers.refresh) {
    const cached = await readIndicesCache();
    if (cached?.items.length) {
      showedCache = true;
      handlers.onData(cached.items, true, cached.fetchedAt);
    }
  }

  try {
    const items = await fetchMarketIndicesNetwork();
    await writeIndicesCache(items);
    if (!showedCache || items.length > 0) {
      handlers.onData(items, false);
    }
  } catch {
    if (!showedCache) {
      const stale = await readIndicesCacheStale();
      if (stale?.items.length) {
        handlers.onData(stale.items, true, stale.fetchedAt);
        return;
      }
    }
    handlers.onData([], false);
  }
}

export type ProviderHealth = {
  kind: string;
  name: string;
  status: string;
  lastSuccessAt?: string | null;
  lastErrorAt?: string | null;
  lastError?: string | null;
  lastItemCount: number;
  stale: boolean;
};

export type StoreHealth = {
  quotesCount: number;
  quotesLatestAt?: string | null;
  newsCount: number;
  newsLatestAt?: string | null;
  indicesCount: number;
  indicesLatestAt?: string | null;
  historyCount: number;
  historyLatestAt?: string | null;
  symbolsCount: number;
  symbolsLatestAt?: string | null;
  fundamentalsCount: number;
  fundamentalsLatestAt?: string | null;
};

export type JobHealth = {
  name: string;
  lastRunAt?: string | null;
  lastSuccessAt?: string | null;
  lastErrorAt?: string | null;
  lastError?: string | null;
  lastItemCount: number;
};

export type SourceHealthResponse = {
  status: string;
  checkedAt: string;
  marketOpen: boolean;
  store: StoreHealth;
  providers: ProviderHealth[];
  jobs: JobHealth[];
};

export async function fetchSourceHealth(): Promise<SourceHealthResponse> {
  return apiGet<SourceHealthResponse>('/v1/health/sources');
}

export type CompanionChatMessage = {
  role: 'user' | 'assistant';
  content: string;
};

export type CompanionContextDto = {
  screen?: string;
  symbol?: string;
  sessionLabel?: string;
  watchlistSymbols?: string[];
  avgChange?: number;
  recentEvents?: Array<{ type: string; symbol?: string; ts: number; meta?: string }>;
};

export async function fetchCompanionHealth(): Promise<{ configured: boolean }> {
  return apiGet<{ configured: boolean }>('/v1/companion/health');
}

export async function requestCompanionNudge(body: {
  context?: CompanionContextDto;
  events?: CompanionContextDto['recentEvents'];
  cooldownUntil?: number;
}): Promise<{ show: boolean; message: string | null }> {
  const res = await fetch(`${API_URL}/v1/companion/nudge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<{ show: boolean; message: string | null }>;
}

/** Non-streaming companion chat (simpler for MVP UI). */
export async function sendCompanionChat(
  messages: CompanionChatMessage[],
  context?: CompanionContextDto,
): Promise<string> {
  const res = await fetch(`${API_URL}/v1/companion/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ messages, context, stream: false }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  const data = (await res.json()) as { message: string };
  return data.message;
}

/** SSE streaming companion chat. Calls onDelta for each chunk. */
export async function streamCompanionChat(
  messages: CompanionChatMessage[],
  context: CompanionContextDto | undefined,
  onDelta: (delta: string) => void,
  onReplace?: (text: string) => void,
): Promise<string> {
  const res = await fetch(`${API_URL}/v1/companion/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ messages, context, stream: true }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  if (!res.body) {
    // RN fetch may not expose body stream — fall back.
    return sendCompanionChat(messages, context);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let assembled = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';
    for (const block of parts) {
      const line = block
        .split('\n')
        .map((l) => l.trim())
        .find((l) => l.startsWith('data:'));
      if (!line) continue;
      try {
        const payload = JSON.parse(line.slice(5).trim()) as {
          delta?: string;
          replace?: string;
          done?: boolean;
          error?: string;
        };
        if (payload.error) throw new Error(payload.error);
        if (payload.replace != null) {
          assembled = payload.replace;
          onReplace?.(assembled);
        } else if (payload.delta) {
          assembled += payload.delta;
          onDelta(payload.delta);
        }
      } catch (err) {
        if (err instanceof SyntaxError) continue;
        throw err;
      }
    }
  }
  return assembled;
}
