import { useEffect, useState } from 'react';
import { Platform } from 'react-native';
import { fetchRangeSparklines } from '../api/client';
import type { ChartRange } from '../types';

export type Quote = {
  changePercent: number | null;
  sparkline: number[];
  /** The range actually served when the requested one was missing. */
  rangeUsed?: string;
};

type QuoteState = {
  range: ChartRange;
  data: Record<string, Quote>;
};

const QUOTE_POLL_MS = 30_000;
const QUOTE_LIMIT = 17;

function pageHidden(): boolean {
  if (Platform.OS !== 'web') return false;
  const doc = (globalThis as { document?: { visibilityState?: string } }).document;
  return doc?.visibilityState === 'hidden';
}

/**
 * Change and sparkline for the rail, in the selected range. One stored-only
 * request for the visible symbols, refreshed every 30s while the page is
 * visible. A failed request leaves the rail on names only — it never blocks
 * the list.
 */
export function useQuotes(
  symbols: string[],
  range: ChartRange,
): Record<string, Quote> | null {
  // A joined key keeps the polling effect stable while the set is unchanged;
  // the caller rebuilds the array on every fetch.
  const key = symbols.slice(0, QUOTE_LIMIT).join(',');
  const [state, setState] = useState<QuoteState | null>(null);

  useEffect(() => {
    if (!key) return;
    const list = key.split(',');
    let stopped = false;

    const load = async () => {
      if (pageHidden()) return;
      try {
        const rows = await fetchRangeSparklines(list, range);
        if (stopped || !rows.length) return;
        const data: Record<string, Quote> = {};
        for (const row of rows) {
          data[row.symbol] = {
            changePercent: row.changePercent,
            sparkline: row.sparkline,
            rangeUsed: row.rangeUsed,
          };
        }
        setState({ range, data });
      } catch {
        // Quotes are a bonus. Keep whatever the rail already had.
      }
    };

    // Typing a filter rebuilds the symbol list. A short delay keeps that from
    // turning every keystroke into a quote request.
    const first = setTimeout(() => void load(), 150);
    const timer = setInterval(() => void load(), QUOTE_POLL_MS);
    return () => {
      stopped = true;
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [key, range]);

  // Never paint a 1M sparkline under a 1Y tab while the new request is in
  // flight (or forever, if it fails).
  return state?.range === range ? state.data : null;
}
