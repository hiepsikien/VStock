import { useCallback, useEffect } from 'react';
import type { Stock } from '../types';
import { ensureNotificationHandler } from '../utils/priceAlertNotify';
import { runPriceAlertCheck } from '../utils/runPriceAlertCheck';
import { syncPriceAlertBackgroundTask } from '../tasks/priceAlertBackgroundTask';

export function usePriceAlerts(stocks: Stock[], enabled: boolean) {
  useEffect(() => {
    void ensureNotificationHandler();
    void syncPriceAlertBackgroundTask();
  }, []);

  const checkAlerts = useCallback(async () => {
    if (!enabled) return;
    await runPriceAlertCheck(stocks);
  }, [enabled, stocks]);

  useEffect(() => {
    void checkAlerts();
  }, [checkAlerts]);
}
