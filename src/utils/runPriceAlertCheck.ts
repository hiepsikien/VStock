import { fetchLiveQuotes } from '../api/client';
import { loadPriceAlerts } from '../storage/alerts';
import type { Stock } from '../types';
import { syncPriceAlertBackgroundTask } from '../tasks/priceAlertBackgroundTask';
import { processPriceAlerts } from './priceAlertEngine';
import { isUsableQuotePrice } from './priceAlertLogic';

/** Fetch quotes for active alerts and deliver any triggered notifications. */
export async function runPriceAlertCheck(seedStocks: Stock[] = []): Promise<void> {
  const alerts = await loadPriceAlerts();
  const active = alerts.filter((alert) => alert.enabled);
  if (!active.length) {
    void syncPriceAlertBackgroundTask();
    return;
  }

  const symbols = [...new Set(active.map((alert) => alert.symbol))];
  const usable = seedStocks.filter(isUsableQuotePrice);
  const have = new Set(usable.map((stock) => stock.symbol));
  const missing = symbols.filter((symbol) => !have.has(symbol));

  let quotes = usable;
  if (missing.length) {
    try {
      const extra = await fetchLiveQuotes(missing);
      quotes = [...quotes, ...extra.filter(isUsableQuotePrice)];
    } catch {
      /* keep seed quotes; background task retries later */
    }
  }

  if (quotes.length) {
    await processPriceAlerts(quotes);
  }
  void syncPriceAlertBackgroundTask();
}
