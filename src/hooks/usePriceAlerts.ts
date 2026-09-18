import { useCallback, useEffect } from 'react';
import type { Stock } from '../types';
import { fetchLiveQuotes } from '../api/client';
import { loadPriceAlerts } from '../storage/alerts';
import { ensureNotificationHandler } from '../utils/priceAlertNotify';
import { processPriceAlerts } from '../utils/priceAlertEngine';
import { isUsableQuotePrice } from '../utils/priceAlertLogic';
import { syncPriceAlertBackgroundTask } from '../tasks/priceAlertBackgroundTask';

export function usePriceAlerts(stocks: Stock[], enabled: boolean) {
  useEffect(() => {
    void ensureNotificationHandler();
    void syncPriceAlertBackgroundTask();
  }, []);

  const checkAlerts = useCallback(async () => {
    if (!enabled) return;
    const alerts = await loadPriceAlerts();
    const active = alerts.filter((alert) => alert.enabled);
    if (!active.length) {
      void syncPriceAlertBackgroundTask();
      return;
    }

    const usable = stocks.filter(isUsableQuotePrice);
    const have = new Set(usable.map((stock) => stock.symbol));
    const missing = [...new Set(active.map((alert) => alert.symbol).filter((symbol) => !have.has(symbol)))];

    let quotes = usable;
    if (missing.length) {
      try {
        const extra = await fetchLiveQuotes(missing);
        quotes = [...quotes, ...extra.filter(isUsableQuotePrice)];
      } catch {
        /* keep watchlist quotes; background task retries later */
      }
    }

    await processPriceAlerts(quotes);
    void syncPriceAlertBackgroundTask();
  }, [enabled, stocks]);

  useEffect(() => {
    void checkAlerts();
  }, [checkAlerts]);
}
