import { useCallback, useEffect, useRef } from 'react';
import type { Stock } from '../types';
import { loadPriceAlerts } from '../storage/alerts';
import { requestNotificationPermission } from '../utils/priceAlertNotify';
import { processPriceAlerts } from '../utils/priceAlertEngine';
import { syncPriceAlertBackgroundTask } from '../tasks/priceAlertBackgroundTask';

export function usePriceAlerts(stocks: Stock[], enabled: boolean) {
  const firedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    void requestNotificationPermission();
    void syncPriceAlertBackgroundTask();
  }, []);

  const checkAlerts = useCallback(async () => {
    if (!enabled) return;
    const alerts = await loadPriceAlerts();
    await processPriceAlerts(alerts, stocks, { skipIds: firedRef.current });
    void syncPriceAlertBackgroundTask();
  }, [enabled, stocks]);

  useEffect(() => {
    void checkAlerts();
  }, [checkAlerts]);
}
