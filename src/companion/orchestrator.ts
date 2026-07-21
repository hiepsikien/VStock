import AsyncStorage from '@react-native-async-storage/async-storage';
import { getRecentCompanionEvents, type CompanionEvent } from './behavior';
import {
  bondToContextDto,
  loadCompanionBond,
  loadCompanionPrefs,
  localDateString,
  RECALL_GAP_MS,
  type CompanionBond,
  type CompanionPrefs,
} from './chatStore';
import { DEFAULT_COMPANION_ID } from './characters';

const COOLDOWN_KEY = 'vstock.companion.nudgeCooldownUntil';
const DISMISS_KEY = 'vstock.companion.nudgeDismissedAt';

export type NudgeKind = 'market' | 'recall' | 'mood';

export type CompanionContextPayload = {
  screen: 'Watchlist' | 'Detail';
  symbol?: string;
  sessionLabel?: string;
  watchlistSymbols?: string[];
  avgChange?: number;
  recentEvents?: CompanionEvent[];
  bond?: ReturnType<typeof bondToContextDto>;
  characterId?: string;
  nudgeKind?: NudgeKind;
  recallTopic?: string;
  daysSinceLastChat?: number;
  todayMood?: string;
};

export async function getNudgeCooldownUntil(): Promise<number> {
  try {
    const raw = await AsyncStorage.getItem(COOLDOWN_KEY);
    return raw ? Number(raw) || 0 : 0;
  } catch {
    return 0;
  }
}

export async function setNudgeCooldown(msFromNow = 60 * 60 * 1000): Promise<void> {
  const until = Date.now() + msFromNow;
  await AsyncStorage.setItem(COOLDOWN_KEY, String(until));
}

export async function markNudgeDismissed(): Promise<void> {
  await AsyncStorage.setItem(DISMISS_KEY, String(Date.now()));
  await setNudgeCooldown(60 * 60 * 1000);
}

export async function buildCompanionContext(
  partial: Omit<
    CompanionContextPayload,
    'recentEvents' | 'bond'
  >,
  bondOverride?: CompanionBond | null,
): Promise<CompanionContextPayload> {
  const recentEvents = await getRecentCompanionEvents(20);
  const bond =
    bondOverride !== undefined
      ? bondOverride
      : await loadCompanionBond(DEFAULT_COMPANION_ID);
  const prefs = await loadCompanionPrefs(DEFAULT_COMPANION_ID);
  return {
    ...partial,
    recentEvents,
    bond: bondToContextDto(bond),
    characterId: partial.characterId ?? DEFAULT_COMPANION_ID,
    todayMood: prefs?.lastMoodResponse,
  };
}

export function localNudgeEligible(
  events: CompanionEvent[],
  opts?: { avgChange?: number },
): boolean {
  const avg = opts?.avgChange;
  if (avg != null && Number.isFinite(avg) && Math.abs(avg) >= 1.5) {
    return true;
  }

  const windowMs = 15 * 60 * 1000;
  const now = Date.now();
  const counts = new Map<string, number>();
  for (const ev of events) {
    if (ev.type !== 'view_detail' || !ev.symbol) continue;
    if (now - ev.ts > windowMs) continue;
    const n = (counts.get(ev.symbol) ?? 0) + 1;
    counts.set(ev.symbol, n);
    if (n >= 3) return true;
  }
  return false;
}

export function recallNudgeEligible(
  bond: CompanionBond | null,
  prefs: CompanionPrefs | null,
): boolean {
  if (!bond || bond.messageCount < 3) return false;
  if (Date.now() - bond.lastChatAt < RECALL_GAP_MS) return false;
  if (!bond.symbolsOfInterest.length && !bond.notes.length) return false;
  const lastRecall = prefs?.lastRecallNudgeAt ?? 0;
  if (lastRecall && Date.now() - lastRecall < 24 * 60 * 60 * 1000) return false;
  return true;
}

export function moodCheckInEligible(
  prefs: CompanionPrefs | null,
  bond: CompanionBond | null,
): boolean {
  if (!bond || bond.messageCount < 1) return false;
  if (prefs?.lastMoodCheckInDate === localDateString()) return false;
  const daysSinceChat =
    (Date.now() - bond.lastChatAt) / (24 * 60 * 60 * 1000);
  // Long absence → recall nudge; same-day return → skip duplicate vibe
  if (daysSinceChat >= RECALL_GAP_MS / (24 * 60 * 60 * 1000)) return false;
  return true;
}

/** Priority: market > recall > mood */
export function pickNudgeKind(
  events: CompanionEvent[],
  bond: CompanionBond | null,
  prefs: CompanionPrefs | null,
  opts?: { avgChange?: number },
): NudgeKind | null {
  if (localNudgeEligible(events, opts)) return 'market';
  if (recallNudgeEligible(bond, prefs)) return 'recall';
  if (moodCheckInEligible(prefs, bond)) return 'mood';
  return null;
}
