/** VN equity indices — tap opens Detail chart. */
export const MARKET_INDEX_SYMBOLS = new Set(['VNINDEX', 'HNX']);

/** Commodity strip symbols — tap opens Detail (Yahoo chart + news). */
export const COMMODITY_STRIP_SYMBOLS = new Set(['XAU', 'WTI']);

export function isMarketIndex(symbol: string): boolean {
  return MARKET_INDEX_SYMBOLS.has(symbol.toUpperCase());
}

export function isCommodityStrip(symbol: string): boolean {
  return COMMODITY_STRIP_SYMBOLS.has(symbol.toUpperCase());
}

/** Index-like Detail: OHLC summary, no alerts, related news. */
export function isIndexLikeDetail(symbol: string): boolean {
  return isMarketIndex(symbol) || isCommodityStrip(symbol);
}

export function formatIndexPrice(price: number, currency?: string): string {
  if (currency === 'USD') {
    return `$${price.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
  return price.toFixed(2);
}
