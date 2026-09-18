import type { Stock } from '../types';
import { loadPriceAlerts, mutatePriceAlerts, type PriceAlert } from '../storage/alerts';
import { deliverPriceAlert } from './priceAlertNotify';
import { evaluatePriceAlerts, mergeEvaluatedAlerts } from './priceAlertLogic';

export type PriceAlertProcessResult = {
  alerts: PriceAlert[];
  triggered: number;
  changed: boolean;
};

export async function processPriceAlerts(
  stocks: Pick<Stock, 'symbol' | 'name' | 'price'>[],
): Promise<PriceAlertProcessResult> {
  let deliveries: ReturnType<typeof evaluatePriceAlerts>['deliveries'] = [];
  let changed = false;

  const alerts = await mutatePriceAlerts(async (snapshot) => {
    const result = evaluatePriceAlerts(snapshot, stocks, new Date().toISOString());
    if (!result.changed) {
      deliveries = [];
      changed = false;
      return snapshot;
    }

    // Re-read inside the lock so a foreground upsert during evaluate is not dropped.
    const latest = await loadPriceAlerts();
    const merged = mergeEvaluatedAlerts(latest, result.alerts, snapshot);
    deliveries = result.deliveries.filter((delivery) => {
      const current = merged.find((alert) => alert.id === delivery.alert.id);
      return (
        current != null &&
        !current.enabled &&
        current.condition === delivery.alert.condition &&
        current.price === delivery.alert.price
      );
    });
    changed = true;
    return merged;
  });

  for (const delivery of deliveries) {
    await deliverPriceAlert(delivery.alert, delivery.stock as Stock);
  }

  return { alerts, triggered: deliveries.length, changed };
}
