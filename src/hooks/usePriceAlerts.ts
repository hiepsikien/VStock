import { useCallback, useEffect, useRef } from 'react';
import type { Stock } from '../types';
import {
  loadPriceAlerts,
  savePriceAlerts,
  type PriceAlert,
} from '../storage/alerts';
import {
  deliverPriceAlert,
  requestNotificationPermission,
} from '../utils/priceAlertNotify';

function shouldTrigger(alert: PriceAlert, price: number): boolean {
  if (alert.condition === 'above') return price >= alert.price;
  return price <= alert.price;
}

export function usePriceAlerts(stocks: Stock[], enabled: boolean) {
  const alertsRef = useRef<PriceAlert[]>([]);
  const firedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    void requestNotificationPermission();
    void loadPriceAlerts().then((a) => {
      alertsRef.current = a;
    });
  }, []);

  const checkAlerts = useCallback(async () => {
    if (!enabled) return;
    const alerts = await loadPriceAlerts();
    alertsRef.current = alerts;
    const active = alerts.filter((a) => a.enabled);
    if (!active.length) return;

    const priceMap = new Map(stocks.map((s) => [s.symbol, s]));
    let changed = false;

    for (const alert of active) {
      const stock = priceMap.get(alert.symbol);
      if (!stock) continue;
      if (!shouldTrigger(alert, stock.price)) continue;
      if (firedRef.current.has(alert.id)) continue;

      firedRef.current.add(alert.id);
      await deliverPriceAlert(alert, stock);
      alert.triggeredAt = new Date().toISOString();
      alert.enabled = false;
      changed = true;
    }

    if (changed) {
      await savePriceAlerts(alerts);
      alertsRef.current = alerts;
    }
  }, [enabled, stocks]);

  useEffect(() => {
    void checkAlerts();
  }, [checkAlerts]);
}
