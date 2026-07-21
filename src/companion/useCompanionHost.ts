import { useCallback, useEffect, useState } from 'react';
import type { NavigationProp } from '@react-navigation/native';
import {
  requestCompanionNudge,
} from '../api/client';
import {
  buildCompanionContext,
  getNudgeCooldownUntil,
  localNudgeEligible,
  markNudgeDismissed,
  setNudgeCooldown,
} from '../companion/orchestrator';
import { getRecentCompanionEvents } from '../companion/behavior';
import type { RootStackParamList } from '../navigation/types';

type Nav = NavigationProp<RootStackParamList>;

type Args = {
  navigation: Nav;
  screen: 'Watchlist' | 'Detail';
  symbol?: string;
  watchlistSymbols?: string[];
  avgChange?: number;
  sessionLabel?: string;
  enabled?: boolean;
};

export function useCompanionHost({
  navigation,
  screen,
  symbol,
  watchlistSymbols,
  avgChange,
  sessionLabel,
  enabled = true,
}: Args) {
  const [nudgeMessage, setNudgeMessage] = useState<string | null>(null);
  const [badge, setBadge] = useState(false);

  const openChat = useCallback(
    (seedMessage?: string) => {
      setNudgeMessage(null);
      setBadge(false);
      navigation.navigate('CompanionChat', {
        seedMessage,
        screen,
        symbol,
        watchlistSymbols,
        avgChange,
        sessionLabel,
      });
    },
    [avgChange, navigation, screen, sessionLabel, symbol, watchlistSymbols],
  );

  const dismissNudge = useCallback(() => {
    setNudgeMessage(null);
    setBadge(false);
    void markNudgeDismissed();
  }, []);

  const evaluateNudge = useCallback(async () => {
    if (!enabled) return;
    const cooldownUntil = await getNudgeCooldownUntil();
    if (Date.now() < cooldownUntil) return;

    const events = await getRecentCompanionEvents(30);
    if (!localNudgeEligible(events)) return;

    const context = await buildCompanionContext({
      screen,
      symbol,
      sessionLabel,
      watchlistSymbols,
      avgChange,
    });

    try {
      const res = await requestCompanionNudge({
        context,
        events: context.recentEvents,
        cooldownUntil: cooldownUntil || undefined,
      });
      if (res.show && res.message) {
        setNudgeMessage(res.message);
        setBadge(true);
        await setNudgeCooldown(60 * 60 * 1000);
      }
    } catch {
      // Offline / API down — silent for MVP.
    }
  }, [avgChange, enabled, screen, sessionLabel, symbol, watchlistSymbols]);

  useEffect(() => {
    if (!enabled) return;
    const t = setTimeout(() => {
      void evaluateNudge();
    }, 2500);
    return () => clearTimeout(t);
  }, [enabled, evaluateNudge, symbol]);

  return {
    nudgeMessage,
    badge,
    openChat,
    dismissNudge,
    replyNudge: () => openChat(nudgeMessage ?? undefined),
  };
}
