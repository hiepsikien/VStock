import { useCallback, useRef } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import { isMarketOpen } from '../utils/marketSession';

/**
 * Poll `callback` every `intervalMs` while the screen is focused and VN market is open.
 * Skips the first immediate call if `runOnFocus` is false (default: runs once on focus).
 */
export function useMarketPolling(
  callback: () => void | Promise<void>,
  intervalMs: number,
  enabled = true,
  runOnFocus = true,
) {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useFocusEffect(
    useCallback(() => {
      if (!enabled) return;

      let timer: ReturnType<typeof setInterval> | null = null;

      const tick = () => {
        if (isMarketOpen()) {
          void callbackRef.current();
        }
      };

      if (runOnFocus) tick();

      timer = setInterval(tick, intervalMs);

      return () => {
        if (timer) clearInterval(timer);
      };
    }, [enabled, intervalMs, runOnFocus]),
  );
}
