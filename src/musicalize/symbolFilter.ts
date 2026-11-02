export type FilterableSymbol = {
  symbol: string;
  name: string;
  ranges?: string[];
  kind?: 'index' | 'stock';
};

/**
 * Default view: pinned indices plus symbols with stored candles. Typing a query
 * searches every symbol so a missing-data name can still be found.
 */
export function filterSymbols<T extends FilterableSymbol>(
  symbols: T[],
  filter: string,
  selectedSymbol: string,
): T[] {
  const query = filter.trim().toUpperCase();
  const matches = query
    ? symbols.filter(
        (item) =>
          item.symbol.includes(query) || item.name.toUpperCase().includes(query),
      )
    : symbols;
  if (query) return matches;

  const hasCoverage = symbols.some(
    (item) => item.kind !== 'index' && item.ranges !== undefined,
  );
  if (!hasCoverage) return matches;

  return matches.filter(
    (item) =>
      item.kind === 'index' ||
      item.symbol === selectedSymbol ||
      (item.ranges?.length ?? 0) > 0,
  );
}
