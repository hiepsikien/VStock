import * as BackgroundTask from 'expo-background-task';
import * as TaskManager from 'expo-task-manager';

import { fetchWatchlist } from '../api/client';
import { loadPriceAlerts } from '../storage/alerts';
import { notificationsSupported, requestNotificationPermission } from '../utils/priceAlertNotify';
import { processPriceAlerts } from '../utils/priceAlertEngine';

export const PRICE_ALERT_BACKGROUND_TASK = 'vstock-price-alert-check';

TaskManager.defineTask(PRICE_ALERT_BACKGROUND_TASK, async () => {
  try {
    if (!notificationsSupported()) {
      return BackgroundTask.BackgroundTaskResult.Success;
    }

    const alerts = await loadPriceAlerts();
    const active = alerts.filter((alert) => alert.enabled);
    if (!active.length) {
      return BackgroundTask.BackgroundTaskResult.Success;
    }

    const symbols = [...new Set(active.map((alert) => alert.symbol))];
    const stocks = await fetchWatchlist(symbols);
    const result = await processPriceAlerts(alerts, stocks);

    return result.triggered > 0
      ? BackgroundTask.BackgroundTaskResult.Success
      : BackgroundTask.BackgroundTaskResult.Success;
  } catch {
    return BackgroundTask.BackgroundTaskResult.Failed;
  }
});

const BACKGROUND_INTERVAL_MINUTES = 15;

export async function syncPriceAlertBackgroundTask(): Promise<void> {
  if (!notificationsSupported()) return;

  const registered = await TaskManager.isTaskRegisteredAsync(PRICE_ALERT_BACKGROUND_TASK);
  const alerts = await loadPriceAlerts();
  const hasActive = alerts.some((alert) => alert.enabled);

  if (hasActive) {
    const granted = await requestNotificationPermission();
    if (!granted) return;

    if (!registered) {
      await BackgroundTask.registerTaskAsync(PRICE_ALERT_BACKGROUND_TASK, {
        minimumInterval: BACKGROUND_INTERVAL_MINUTES,
      });
    }
    return;
  }

  if (registered) {
    await BackgroundTask.unregisterTaskAsync(PRICE_ALERT_BACKGROUND_TASK);
  }
}
