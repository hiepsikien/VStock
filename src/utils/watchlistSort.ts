import type { Stock } from '../types';

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
