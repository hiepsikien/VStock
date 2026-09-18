import type { Stock } from '../types';
import { loadPriceAlerts, savePriceAlerts, type PriceAlert } from '../storage/alerts';
import { deliverPriceAlert } from './priceAlertNotify';
import {
  evaluatePriceAlerts,
  shouldTriggerPriceAlert,
  type PriceAlertEvaluation,
} from './priceAlertLogic';

export { shouldTriggerPriceAlert } from './priceAlertLogic';
export type { PriceAlertEvaluation };

export type PriceAlertProcessResult = {
  alerts: PriceAlert[];
  triggered: number;
  changed: boolean;
};

let processQueue: Promise<unknown> = Promise.resolve();

function enqueue<T>(work: () => Promise<T>): Promise<T> {
  const run = processQueue.then(work, work);
  processQueue = run.then(
    () => undefined,
    () => undefined,
  );
  return run;
}

export async function processPriceAlerts(
  _alerts: PriceAlert[],
  stocks: Pick<Stock, 'symbol' | 'name' | 'price'>[],
): Promise<PriceAlertProcessResult> {
  return enqueue(async () => {
    const latest = await loadPriceAlerts();
    const result = evaluatePriceAlerts(latest, stocks, new Date().toISOString());

    for (const delivery of result.deliveries) {
      await deliverPriceAlert(delivery.alert, delivery.stock as Stock);
    }

    if (result.changed) {
      await savePriceAlerts(result.alerts);
    }

    return {
      alerts: result.alerts,
      triggered: result.deliveries.length,
      changed: result.changed,
    };
  });
}
