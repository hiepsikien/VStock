import type { Stock } from '../types';

export type WatchlistSort = 'change' | 'symbol' | 'name';

export type WatchlistSection = {
  key: string;
  title: string;
  data: Stock[];
};

export function sortStocks(stocks: Stock[], sort: WatchlistSort): Stock[] {
  const copy = [...stocks];
  switch (sort) {
    case 'symbol':
      return copy.sort((a, b) => a.symbol.localeCompare(b.symbol));
    case 'name':
      return copy.sort((a, b) => a.name.localeCompare(b.name, 'vi'));
    case 'change':
    default:
      return copy.sort((a, b) => b.changePercent - a.changePercent);
  }
}

export function buildWatchlistSections(
  stocks: Stock[],
  sort: WatchlistSort,
): WatchlistSection[] {
  const sorted = sortStocks(stocks, sort);

  if (sort !== 'change') {
    return [{ key: 'all', title: 'Danh sách theo dõi', data: sorted }];
  }

  const gainers = sorted.filter((s) => s.changePercent > 0);
  const losers = sorted.filter((s) => s.changePercent < 0);
  const flat = sorted.filter((s) => s.changePercent === 0);

  const sections: WatchlistSection[] = [];
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
