import { useEffect, useState } from 'react';
import { Platform } from 'react-native';
import { fetchWatchlist } from '../api/client';

export type Quote = {
  changePercent: number;
  sparkline: number[];
};

const QUOTE_POLL_MS = 30_000;
const QUOTE_LIMIT = 12;

function pageHidden(): boolean {
  if (Platform.OS !== 'web') return false;
  const doc = (globalThis as { document?: { visibilityState?: string } }).document;
  return doc?.visibilityState === 'hidden';
}

/**
 * Day change and sparkline for the rail. One request for the visible symbols,
 * refreshed every 30s while the page is visible. A failed request leaves the
 * rail on names only — it never blocks the list.
 */
export function useQuotes(symbols: string[]): Record<string, Quote> | null {
  // A joined key keeps the polling effect stable while the set is unchanged;
  // the caller rebuilds the array on every fetch.
  const key = symbols.slice(0, QUOTE_LIMIT).join(',');
  const [quotes, setQuotes] = useState<Record<string, Quote> | null>(null);

  useEffect(() => {
    if (!key) return;
    const list = key.split(',');
    let stopped = false;

    const load = async () => {
      if (pageHidden()) return;
      try {
        const rows = await fetchWatchlist(list);
        if (stopped || !rows.length) return;
        const next: Record<string, Quote> = {};
        for (const row of rows) {
          next[row.symbol] = {
            changePercent: row.changePercent,
            sparkline: row.sparkline ?? [],
          };
        }
        setQuotes(next);
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
  }, [key]);

  return quotes;
}
