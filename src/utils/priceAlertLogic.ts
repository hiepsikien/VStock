import type { Stock } from '../types';
import type { PriceAlert } from '../storage/alerts';

export type QuoteLike = Pick<Stock, 'symbol' | 'name' | 'price'> & {
  unavailable?: boolean;
};

/** HOSE/HNX quotes are two-decimal. Avoid float equality misses like 80.1 vs 80.099999. */
export function roundAlertPrice(value: number): number {
  return Math.round(value * 100) / 100;
}

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
  const live = roundAlertPrice(currentPrice);
  const level = roundAlertPrice(target);
  return condition === 'above' ? live >= level : live <= level;
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

  const live = roundAlertPrice(price);
  const previous = roundAlertPrice(lastSeenPrice);
  const target = roundAlertPrice(alert.price);

  if (alert.condition === 'above') {
    if (previous < target) return live >= target;
    return previous === target && live > target;
  }

  if (previous > target) return live <= target;
  return previous === target && live < target;
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

    const live = roundAlertPrice(stock.price);
    const fire = shouldTriggerPriceAlert(alert, live, alert.lastSeenPrice);
    const lastSeenChanged = alert.lastSeenPrice == null || roundAlertPrice(alert.lastSeenPrice) !== live;
    const updated: PriceAlert = lastSeenChanged ? { ...alert, lastSeenPrice: live } : alert;

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

function alertIdentityChanged(current: PriceAlert, snapshot: PriceAlert): boolean {
  return (
    current.symbol !== snapshot.symbol ||
    current.condition !== snapshot.condition ||
    roundAlertPrice(current.price) !== roundAlertPrice(snapshot.price) ||
    current.enabled !== snapshot.enabled
  );
}

/**
 * Apply an evaluation onto the latest persisted list so a concurrent upsert/delete
 * is not overwritten by a lastSeen tick.
 */
export function mergeEvaluatedAlerts(
  latest: PriceAlert[],
  evaluated: PriceAlert[],
  snapshot: PriceAlert[],
): PriceAlert[] {
  const evaluatedById = new Map(evaluated.map((alert) => [alert.id, alert]));
  const snapshotById = new Map(snapshot.map((alert) => [alert.id, alert]));

  return latest.map((current) => {
    const ev = evaluatedById.get(current.id);
    const snap = snapshotById.get(current.id);
    if (!ev || !snap || alertIdentityChanged(current, snap)) {
      return current;
    }

    return {
      ...current,
      lastSeenPrice: ev.lastSeenPrice ?? current.lastSeenPrice,
      enabled: ev.enabled,
      triggeredAt: ev.triggeredAt ?? current.triggeredAt,
    };
  });
}
