import AsyncStorage from '@react-native-async-storage/async-storage';
import type { CompanionCharacterId } from './characters';

export type CompanionActivityType =
  | 'add_symbol'
  | 'remove_symbol'
  | 'create_watchlist'
  | 'set_nickname';

export type CompanionActivity = {
  id: string;
  ts: number;
  type: CompanionActivityType;
  /** Short Vietnamese label shown on profile */
  label: string;
  symbol?: string;
  watchlistName?: string;
};

const ACTIVITY_PREFIX = 'vstock.companion.activity.';
const MAX_ACTIVITIES = 40;

function activityKey(id: CompanionCharacterId): string {
  return ACTIVITY_PREFIX + id;
}

export async function loadCompanionActivities(
  id: CompanionCharacterId,
): Promise<CompanionActivity[]> {
  try {
    const raw = await AsyncStorage.getItem(activityKey(id));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as CompanionActivity[];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (a) =>
          a &&
          typeof a.id === 'string' &&
          typeof a.label === 'string' &&
          typeof a.ts === 'number',
      )
      .slice(0, MAX_ACTIVITIES);
  } catch {
    return [];
  }
}

export async function saveCompanionActivities(
  id: CompanionCharacterId,
  items: CompanionActivity[],
): Promise<void> {
  await AsyncStorage.setItem(
    activityKey(id),
    JSON.stringify(items.slice(0, MAX_ACTIVITIES)),
  );
}

export async function clearCompanionActivities(
  id: CompanionCharacterId,
): Promise<void> {
  await AsyncStorage.removeItem(activityKey(id));
}

export async function appendCompanionActivity(
  id: CompanionCharacterId,
  entry: Omit<CompanionActivity, 'id' | 'ts'> & { ts?: number },
): Promise<CompanionActivity[]> {
  const prev = await loadCompanionActivities(id);
  const item: CompanionActivity = {
    id: `act-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    ts: entry.ts ?? Date.now(),
    type: entry.type,
    label: entry.label.trim().slice(0, 120),
    symbol: entry.symbol?.toUpperCase(),
    watchlistName: entry.watchlistName?.trim(),
  };
  const next = [item, ...prev].slice(0, MAX_ACTIVITIES);
  await saveCompanionActivities(id, next);
  return next;
}

export function formatActivityTime(ts: number): string {
  const d = new Date(ts);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${dd}/${mm} ${hh}:${min}`;
}
