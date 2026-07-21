import { useCallback, useEffect, useState } from 'react';
import type { NavigationProp } from '@react-navigation/native';
import { requestCompanionNudge } from '../api/client';
import {
  buildCompanionContext,
  getNudgeCooldownUntil,
  markNudgeDismissed,
  pickNudgeKind,
  setNudgeCooldown,
  type NudgeKind,
} from '../companion/orchestrator';
import { getRecentCompanionEvents } from '../companion/behavior';
import {
  buildMoodCheckInMessage,
  loadCompanionBond,
  loadCompanionPrefs,
  markMoodCheckInDone,
  markRecallNudgeShown,
  MOOD_CHECKIN_REPLIES,
  moodSeedFromReply,
} from '../companion/chatStore';
import { DEFAULT_COMPANION_ID } from '../companion/characters';
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
  const [nudgeKind, setNudgeKind] = useState<NudgeKind | null>(null);
  const [nudgeQuickReplies, setNudgeQuickReplies] = useState<string[]>([]);
  const [badge, setBadge] = useState(false);

  const clearNudge = useCallback(() => {
    setNudgeMessage(null);
    setNudgeKind(null);
    setNudgeQuickReplies([]);
    setBadge(false);
  }, []);

  const openChat = useCallback(
    (seedUserMessage?: string, seedAssistantMessage?: string) => {
      clearNudge();
      navigation.navigate('CompanionChat', {
        seedUserMessage,
        seedAssistantMessage,
        screen,
        symbol,
        watchlistSymbols,
        avgChange,
        sessionLabel,
      });
    },
    [
      avgChange,
      clearNudge,
      navigation,
      screen,
      sessionLabel,
      symbol,
      watchlistSymbols,
    ],
  );

  const dismissNudge = useCallback(() => {
    if (nudgeKind === 'mood') {
      void markMoodCheckInDone(DEFAULT_COMPANION_ID);
    }
    clearNudge();
    void markNudgeDismissed();
  }, [clearNudge, nudgeKind]);

  const replyNudge = useCallback(() => {
    openChat(undefined, nudgeMessage ?? undefined);
  }, [nudgeMessage, openChat]);

  const replyNudgeChip = useCallback(
    (chip: string) => {
      if (nudgeKind === 'mood') {
        void markMoodCheckInDone(DEFAULT_COMPANION_ID, chip);
      }
      clearNudge();
      openChat(moodSeedFromReply(chip), nudgeMessage ?? undefined);
    },
    [clearNudge, nudgeKind, nudgeMessage, openChat],
  );

  const evaluateNudge = useCallback(async () => {
    if (!enabled) return;
    const cooldownUntil = await getNudgeCooldownUntil();
    if (Date.now() < cooldownUntil) return;

    const [events, bond, prefs] = await Promise.all([
      getRecentCompanionEvents(30),
      loadCompanionBond(DEFAULT_COMPANION_ID),
      loadCompanionPrefs(DEFAULT_COMPANION_ID),
    ]);

    const kind = pickNudgeKind(events, bond, prefs, { avgChange });
    if (!kind) return;

    if (kind === 'mood') {
      setNudgeMessage(buildMoodCheckInMessage(bond));
      setNudgeKind('mood');
      setNudgeQuickReplies([...MOOD_CHECKIN_REPLIES]);
      setBadge(true);
      await setNudgeCooldown(60 * 60 * 1000);
      return;
    }

    const daysSinceLastChat = bond
      ? Math.floor((Date.now() - bond.lastChatAt) / (24 * 60 * 60 * 1000))
      : 0;

    const context = await buildCompanionContext(
      {
        screen,
        symbol,
        sessionLabel,
        watchlistSymbols,
        avgChange,
        nudgeKind: kind,
        recallTopic: bond?.symbolsOfInterest[0],
        daysSinceLastChat,
      },
      bond,
    );

    try {
      const res = await requestCompanionNudge({
        context,
        events: context.recentEvents,
        cooldownUntil: cooldownUntil || undefined,
      });
      if (res.show && res.message) {
        setNudgeMessage(res.message);
        setNudgeKind(kind);
        setNudgeQuickReplies([]);
        setBadge(true);
        await setNudgeCooldown(60 * 60 * 1000);
        if (kind === 'recall') {
          await markRecallNudgeShown(DEFAULT_COMPANION_ID);
        }
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
    nudgeKind,
    nudgeQuickReplies,
    badge,
    openChat,
    dismissNudge,
    replyNudge,
    replyNudgeChip,
  };
}
