import type { Stock } from '../types';
import type { PriceAlert } from '../storage/alerts';
import { savePriceAlerts } from '../storage/alerts';
import { deliverPriceAlert } from './priceAlertNotify';

export function shouldTriggerPriceAlert(alert: PriceAlert, price: number): boolean {
  if (alert.condition === 'above') return price >= alert.price;
  return price <= alert.price;
}

export type PriceAlertProcessResult = {
  alerts: PriceAlert[];
  triggered: number;
  changed: boolean;
};

export async function processPriceAlerts(
  alerts: PriceAlert[],
  stocks: Pick<Stock, 'symbol' | 'name' | 'price'>[],
  options?: { skipIds?: Set<string> },
): Promise<PriceAlertProcessResult> {
  const skipIds = options?.skipIds ?? new Set<string>();
  const priceMap = new Map(stocks.map((stock) => [stock.symbol, stock]));
  let changed = false;
  let triggered = 0;

  for (const alert of alerts) {
    if (!alert.enabled) continue;
    const stock = priceMap.get(alert.symbol);
    if (!stock) continue;
    if (!shouldTriggerPriceAlert(alert, stock.price)) continue;
    if (skipIds.has(alert.id)) continue;

    skipIds.add(alert.id);
    await deliverPriceAlert(alert, stock as Stock);
    alert.triggeredAt = new Date().toISOString();
    alert.enabled = false;
    changed = true;
    triggered += 1;
  }

  if (changed) {
    await savePriceAlerts(alerts);
  }

  return { alerts, triggered, changed };
}
