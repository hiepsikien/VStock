import type { Stock } from '../types';
import type { PriceAlert } from '../storage/alerts';

export type QuoteLike = Pick<Stock, 'symbol' | 'name' | 'price'> & {
  unavailable?: boolean;
};

export function isUsableQuotePrice(stock: QuoteLike): boolean {
  return !stock.unavailable && Number.isFinite(stock.price) && stock.price > 0;
}

/** True when the live price is already on the trigger side of the target. */
export function isPriceAlreadyThroughAlert(
  condition: PriceAlert['condition'],
  target: number,
  currentPrice: number,
): boolean {
  if (!Number.isFinite(target) || !Number.isFinite(currentPrice) || currentPrice <= 0) {
    return false;
  }
  return condition === 'above' ? currentPrice >= target : currentPrice <= target;
}

/**
 * Fire only on a real cross:
 * - from below the target to at/above (above alerts)
 * - from above the target to at/below (below alerts)
 * - if armed exactly at the target, wait for the next tick through it
 *
 * Missing/invalid lastSeenPrice arms the alert without firing.
 */
export function shouldTriggerPriceAlert(
  alert: PriceAlert,
  price: number,
  lastSeenPrice?: number,
): boolean {
  if (!Number.isFinite(price) || price <= 0) return false;
  if (lastSeenPrice == null || !Number.isFinite(lastSeenPrice) || lastSeenPrice <= 0) {
    return false;
  }

  if (alert.condition === 'above') {
    if (lastSeenPrice < alert.price) return price >= alert.price;
    return lastSeenPrice === alert.price && price > alert.price;
  }

  if (lastSeenPrice > alert.price) return price <= alert.price;
  return lastSeenPrice === alert.price && price < alert.price;
}

export type PriceAlertDelivery = {
  alert: PriceAlert;
  stock: QuoteLike;
};

export type PriceAlertEvaluation = {
  alerts: PriceAlert[];
  deliveries: PriceAlertDelivery[];
  changed: boolean;
};

export function evaluatePriceAlerts(
  alerts: PriceAlert[],
  stocks: QuoteLike[],
  nowIso: string,
): PriceAlertEvaluation {
  const priceMap = new Map(stocks.filter(isUsableQuotePrice).map((stock) => [stock.symbol, stock]));
  const next: PriceAlert[] = [];
  const deliveries: PriceAlertDelivery[] = [];
  let changed = false;

  for (const alert of alerts) {
    if (!alert.enabled) {
      next.push(alert);
      continue;
    }

    const stock = priceMap.get(alert.symbol);
    if (!stock) {
      next.push(alert);
      continue;
    }

    const fire = shouldTriggerPriceAlert(alert, stock.price, alert.lastSeenPrice);
    const lastSeenChanged = alert.lastSeenPrice !== stock.price;
    const updated: PriceAlert = lastSeenChanged
      ? { ...alert, lastSeenPrice: stock.price }
      : alert;

    if (fire) {
      const triggered: PriceAlert = {
        ...updated,
        enabled: false,
        triggeredAt: nowIso,
      };
      next.push(triggered);
      deliveries.push({ alert: triggered, stock });
      changed = true;
      continue;
    }

    if (lastSeenChanged) changed = true;
    next.push(updated);
  }

  return { alerts: next, deliveries, changed };
}
