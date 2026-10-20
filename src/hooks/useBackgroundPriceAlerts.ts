import { useEffect, useRef } from 'react';
import { AppState, type AppStateStatus } from 'react-native';

import { ensureNotificationHandler } from '../utils/priceAlertNotify';
import { runPriceAlertCheck } from '../utils/runPriceAlertCheck';

function isGoingToBackground(prev: AppStateStatus, next: AppStateStatus): boolean {
  // Entering background from any foreground state (iOS: active → inactive → background).
  return next === 'background' && prev !== 'background';
}

/**
 * Run a final price-alert pass when the app leaves the foreground so users
 * get push notifications instead of missing in-app-only checks.
 */
function asAppStateStatus(value: string | null | undefined): AppStateStatus {
  if (
    value === 'active' ||
    value === 'background' ||
    value === 'inactive' ||
    value === 'unknown' ||
    value === 'extension'
  ) {
    return value;
  }
  return 'unknown';
}

export function useBackgroundPriceAlerts() {
  const appState = useRef<AppStateStatus>(asAppStateStatus(AppState.currentState));
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
