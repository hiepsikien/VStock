import type { ChartRange, Stock } from '../types';
import type { IndexQuote } from '../components/WatchlistSummary';
import {
  readCache,
  readCacheStale,
  writeCache,
  type CacheEntry,
} from './cacheUtils';

export const QUOTE_PREFIX = 'vstock.quote.v2.';
const DETAIL_PREFIX = 'vstock.detail.v2.';
const INDICES_KEY = 'market';
const INDICES_PREFIX = 'vstock.indices.';
const HISTORY_PREFIX = 'vstock.hist.';

export const QUOTES_FRESH_TTL_MS = 5 * 60 * 1000;
export const DETAIL_FRESH_TTL_MS = 5 * 60 * 1000;
export const INDICES_FRESH_TTL_MS = 5 * 60 * 1000;
export const HISTORY_FRESH_TTL_MS = 60 * 60 * 1000;
export const HISTORY_1D_FRESH_TTL_MS = 5 * 60 * 1000;

function normalizeSymbol(symbol: string): string {
  return symbol.toUpperCase().trim();
}

function historyKey(symbol: string, range: ChartRange): string {
  return `${normalizeSymbol(symbol)}.${range}`;
}

export type CachedBatch<T> = {
  items: T[];
  fetchedAt: number;
};

async function readSymbolBatch<T extends { symbol: string }>(
  prefix: string,
  symbols: string[],
  ttlMs?: number,
): Promise<CachedBatch<T> | null> {
  const items: { data: T; fetchedAt: number }[] = [];

  for (const symbol of symbols) {
    const entry = await readCacheStale<T>(prefix, normalizeSymbol(symbol));
    if (!entry) continue;
    if (ttlMs != null && Date.now() - entry.fetchedAt >= ttlMs) continue;
    items.push({ data: entry.data, fetchedAt: entry.fetchedAt });
  }

  if (!items.length) return null;

  const order = new Map(symbols.map((sym, index) => [normalizeSymbol(sym), index]));
  items.sort(
    (a, b) =>
      (order.get(normalizeSymbol(a.data.symbol)) ?? 999) -
      (order.get(normalizeSymbol(b.data.symbol)) ?? 999),
  );

  return {
    items: items.map((item) => item.data),
    fetchedAt: Math.min(...items.map((item) => item.fetchedAt)),
  };
}

async function readSymbolBatchStale<T extends { symbol: string }>(
  prefix: string,
  symbols: string[],
): Promise<CachedBatch<T> | null> {
  const items: { data: T; fetchedAt: number }[] = [];

  for (const symbol of symbols) {
    const entry = await readCacheStale<T>(prefix, normalizeSymbol(symbol));
    if (!entry) continue;
    items.push({ data: entry.data, fetchedAt: entry.fetchedAt });
  }

  if (!items.length) return null;

  const order = new Map(symbols.map((sym, index) => [normalizeSymbol(sym), index]));
  items.sort(
    (a, b) =>
      (order.get(normalizeSymbol(a.data.symbol)) ?? 999) -
      (order.get(normalizeSymbol(b.data.symbol)) ?? 999),
  );

  return {
    items: items.map((item) => item.data),
    fetchedAt: Math.min(...items.map((item) => item.fetchedAt)),
  };
}

export async function readQuotesCache(symbols: string[]): Promise<CachedBatch<Stock> | null> {
  if (!symbols.length) return null;
  return readSymbolBatch<Stock>(QUOTE_PREFIX, symbols, QUOTES_FRESH_TTL_MS);
}

export async function readQuotesCacheStale(symbols: string[]): Promise<CachedBatch<Stock> | null> {
  if (!symbols.length) return null;
  return readSymbolBatchStale<Stock>(QUOTE_PREFIX, symbols);
}

export async function writeQuotesCache(stocks: Stock[]): Promise<void> {
  await Promise.all(
    stocks.map((stock) => writeCache(QUOTE_PREFIX, normalizeSymbol(stock.symbol), stock)),
  );
}

export async function readDetailCache(symbol: string): Promise<Stock | null> {
  return readCache<Stock>(DETAIL_PREFIX, normalizeSymbol(symbol), DETAIL_FRESH_TTL_MS);
}

export async function readDetailCacheStale(symbol: string): Promise<CacheEntry<Stock> | null> {
  return readCacheStale<Stock>(DETAIL_PREFIX, normalizeSymbol(symbol));
}

export async function writeDetailCache(stock: Stock): Promise<void> {
  const sym = normalizeSymbol(stock.symbol);
  await writeCache(DETAIL_PREFIX, sym, stock);
  await writeCache(QUOTE_PREFIX, sym, stock);
}

export async function readIndicesCache(): Promise<CachedBatch<IndexQuote> | null> {
  const data = await readCache<IndexQuote[]>(INDICES_PREFIX, INDICES_KEY, INDICES_FRESH_TTL_MS);
  if (!data?.length) return null;
  const entry = await readCacheStale<IndexQuote[]>(INDICES_PREFIX, INDICES_KEY);
  return { items: data, fetchedAt: entry?.fetchedAt ?? Date.now() };
}

export async function readIndicesCacheStale(): Promise<CachedBatch<IndexQuote> | null> {
  const entry = await readCacheStale<IndexQuote[]>(INDICES_PREFIX, INDICES_KEY);
  if (!entry?.data.length) return null;
  return { items: entry.data, fetchedAt: entry.fetchedAt };
}

export async function writeIndicesCache(items: IndexQuote[]): Promise<void> {
  await writeCache(INDICES_PREFIX, INDICES_KEY, items);
}

export async function readHistoryCache(
  symbol: string,
  range: ChartRange,
): Promise<number[] | null> {
  const ttl = range === '1D' ? HISTORY_1D_FRESH_TTL_MS : HISTORY_FRESH_TTL_MS;
  return readCache<number[]>(HISTORY_PREFIX, historyKey(symbol, range), ttl);
}

export async function readHistoryCacheStale(
  symbol: string,
  range: ChartRange,
): Promise<CacheEntry<number[]> | null> {
  return readCacheStale<number[]>(HISTORY_PREFIX, historyKey(symbol, range));
}

export async function writeHistoryCache(
  symbol: string,
  range: ChartRange,
  prices: number[],
): Promise<void> {
  await writeCache(HISTORY_PREFIX, historyKey(symbol, range), prices);
}
