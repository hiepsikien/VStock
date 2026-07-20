/** Market index symbols (Entrade) — must match backend INDEX_SYMBOLS. */
export const MARKET_INDEX_SYMBOLS = new Set(['VNINDEX', 'HNX']);

export function isMarketIndex(symbol: string): boolean {
  return MARKET_INDEX_SYMBOLS.has(symbol.toUpperCase());
}
