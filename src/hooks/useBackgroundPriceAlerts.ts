import { useEffect, useRef } from 'react';
import { AppState, type AppStateStatus } from 'react-native';

import { ensureNotificationHandler } from '../utils/priceAlertNotify';
import { runPriceAlertCheck } from '../utils/runPriceAlertCheck';

function isGoingToBackground(prev: AppStateStatus, next: AppStateStatus): boolean {
  // Only true background — not inactive (Control Center, notifications, calls, app switcher).
  return prev === 'active' && next === 'background';
}

/**
 * Run a final price-alert pass when the app leaves the foreground so users
 * get push notifications instead of missing in-app-only checks.
 */
export function useBackgroundPriceAlerts() {
  const appState = useRef(AppState.currentState);
  const checking = useRef(false);

  useEffect(() => {
    void ensureNotificationHandler();

    const sub = AppState.addEventListener('change', (next) => {
      const prev = appState.current;
      appState.current = next;
      if (!isGoingToBackground(prev, next) || checking.current) return;

      checking.current = true;
      void runPriceAlertCheck().finally(() => {
        checking.current = false;
      });
    });

    return () => sub.remove();
  }, []);
}
