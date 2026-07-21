import type { ChartRange, Stock } from '../types';

export type WatchlistSort = 'change' | 'symbol';

export type WatchlistSection = {
  key: string;
  title: string;
  data: Stock[];
};

export function orderWithPins(stocks: Stock[], pinnedSymbols: string[]): Stock[] {
  if (!pinnedSymbols.length) return stocks;
  const pinSet = new Set(pinnedSymbols);
  const pinned = pinnedSymbols
    .map((sym) => stocks.find((s) => s.symbol === sym))
    .filter(Boolean) as Stock[];
  const rest = stocks.filter((s) => !pinSet.has(s.symbol));
  return [...pinned, ...rest];
}

export function sortStocks(stocks: Stock[], sort: WatchlistSort): Stock[] {
  const copy = [...stocks];
  switch (sort) {
    case 'symbol':
      return copy.sort((a, b) => a.symbol.localeCompare(b.symbol));
    case 'change':
    default:
      return copy.sort((a, b) => b.changePercent - a.changePercent);
  }
}

export function buildWatchlistSections(
  stocks: Stock[],
  sort: WatchlistSort,
  pinnedSymbols: string[] = [],
): WatchlistSection[] {
  const ordered = orderWithPins(stocks, pinnedSymbols);
  const sorted = sortStocks(ordered, sort);

  if (sort !== 'change') {
    const pinnedSet = new Set(pinnedSymbols);
    const pinned = sorted.filter((s) => pinnedSet.has(s.symbol));
    const rest = sorted.filter((s) => !pinnedSet.has(s.symbol));
    const data = [...pinned, ...rest];
    const title = pinned.length ? 'Danh sách theo dõi' : 'Danh sách theo dõi';
    return [{ key: 'all', title, data }];
  }

  const pinnedSet = new Set(pinnedSymbols);
  const pinned = sorted.filter((s) => pinnedSet.has(s.symbol));
  const unpinned = sorted.filter((s) => !pinnedSet.has(s.symbol));

  const sections: WatchlistSection[] = [];
  if (pinned.length) sections.push({ key: 'pinned', title: 'Đã ghim', data: pinned });

  const gainers = unpinned.filter((s) => s.changePercent > 0);
  const losers = unpinned.filter((s) => s.changePercent < 0);
  const flat = unpinned.filter((s) => s.changePercent === 0);

  if (gainers.length) sections.push({ key: 'up', title: 'Tăng giá', data: gainers });
  if (losers.length) sections.push({ key: 'down', title: 'Giảm giá', data: losers });
  if (flat.length) sections.push({ key: 'flat', title: 'Đi ngang', data: flat });
  if (!sections.length) sections.push({ key: 'empty', title: 'Danh sách theo dõi', data: [] });

  return sections;
}

export function watchlistStats(stocks: Stock[]) {
  const gainers = stocks.filter((s) => s.changePercent > 0).length;
  const losers = stocks.filter((s) => s.changePercent < 0).length;
  const flat = stocks.length - gainers - losers;
  const avgChange =
    stocks.length > 0
      ? stocks.reduce((sum, s) => sum + s.changePercent, 0) / stocks.length
      : 0;
  return { gainers, losers, flat, avgChange, total: stocks.length };
}

function sparklinesEqual(a: number[], b: number[]): boolean {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

/** Preserve object identity for unchanged rows so memoized list items skip re-render. */
export function mergeStockUpdates(prev: Stock[], incoming: Stock[]): Stock[] {
  if (prev.length !== incoming.length) return incoming;

  const prevBySymbol = new Map(prev.map((s) => [s.symbol, s]));
  let changed = false;
  const next: Stock[] = [];

  for (const stock of incoming) {
    const old = prevBySymbol.get(stock.symbol);
    if (!old) {
      changed = true;
      next.push(stock);
      continue;
    }
    if (
      old.price === stock.price &&
      old.change === stock.change &&
      old.changePercent === stock.changePercent &&
      sparklinesEqual(old.sparkline, stock.sparkline)
    ) {
      next.push(old);
    } else {
      changed = true;
      next.push(stock);
    }
  }

  return changed ? next : prev;
}

const EMPTY_HISTORY: Record<ChartRange, number[]> = {
  '1D': [],
  '1W': [],
  '1M': [],
  '3M': [],
  '1Y': [],
  '5Y': [],
};

/** Placeholder row when symbol is in watchlist but quotes are unavailable. */
export function placeholderStock(
  symbol: string,
  meta?: { name?: string; exchange?: string },
): Stock {
  const sym = symbol.toUpperCase();
  return {
    symbol: sym,
    name: meta?.name ?? sym,
    exchange: meta?.exchange ?? '—',
    price: 0,
    change: 0,
    changePercent: 0,
    open: 0,
    high: 0,
    low: 0,
    volume: 0,
    marketCap: '—',
    pe: null,
    currency: '₫',
    sparkline: [],
    history: { ...EMPTY_HISTORY },
    unavailable: true,
  };
}

/** Keep one row per stored symbol — order matches watchlist storage. */
export function alignStocksToSymbolList(symbols: string[], stocks: Stock[]): Stock[] {
  const bySym = new Map(stocks.map((s) => [s.symbol.toUpperCase(), s]));
  return symbols.map((sym) => {
    const key = sym.toUpperCase();
    return bySym.get(key) ?? placeholderStock(key);
  });
}
