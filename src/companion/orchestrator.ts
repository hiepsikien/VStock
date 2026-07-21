import AsyncStorage from '@react-native-async-storage/async-storage';
import { getRecentCompanionEvents, type CompanionEvent } from './behavior';
import {
  bondToContextDto,
  loadCompanionBond,
  type CompanionBond,
} from './chatStore';
import { DEFAULT_COMPANION_ID } from './characters';

const COOLDOWN_KEY = 'vstock.companion.nudgeCooldownUntil';
const DISMISS_KEY = 'vstock.companion.nudgeDismissedAt';

export type CompanionContextPayload = {
  screen: 'Watchlist' | 'Detail';
  symbol?: string;
  sessionLabel?: string;
  watchlistSymbols?: string[];
  avgChange?: number;
  recentEvents?: CompanionEvent[];
  bond?: ReturnType<typeof bondToContextDto>;
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
  partial: Omit<CompanionContextPayload, 'recentEvents' | 'bond'>,
  bondOverride?: CompanionBond | null,
): Promise<CompanionContextPayload> {
  const recentEvents = await getRecentCompanionEvents(20);
  const bond =
    bondOverride !== undefined
      ? bondOverride
      : await loadCompanionBond(DEFAULT_COMPANION_ID);
  return {
    ...partial,
    recentEvents,
    bond: bondToContextDto(bond),
  };
}

export function localNudgeEligible(events: CompanionEvent[]): boolean {
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
