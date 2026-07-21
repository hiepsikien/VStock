import AsyncStorage from '@react-native-async-storage/async-storage';

export type CompanionEventType =
  | 'view_detail'
  | 'search'
  | 'open_index'
  | 'open_news';

export type CompanionEvent = {
  type: CompanionEventType;
  symbol?: string;
  ts: number;
  meta?: string;
};

const STORAGE_KEY = 'vstock.companion.events.v1';
const MAX_EVENTS = 50;
const TTL_MS = 24 * 60 * 60 * 1000;

let memory: CompanionEvent[] = [];
let loaded = false;

async function ensureLoaded(): Promise<void> {
  if (loaded) return;
  loaded = true;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) {
      memory = [];
      return;
    }
    const parsed = JSON.parse(raw) as CompanionEvent[];
    const now = Date.now();
    memory = (parsed || []).filter((e) => e && now - e.ts < TTL_MS).slice(-MAX_EVENTS);
  } catch {
    memory = [];
  }
}

async function persist(): Promise<void> {
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(memory.slice(-MAX_EVENTS)));
  } catch {
    /* ignore */
  }
}

export async function trackCompanionEvent(
  type: CompanionEventType,
  opts?: { symbol?: string; meta?: string },
): Promise<void> {
  await ensureLoaded();
  const symbol = opts?.symbol?.toUpperCase();
  const now = Date.now();

  // Debounce repeat view_detail on same symbol within 8s.
  if (type === 'view_detail' && symbol) {
    const last = [...memory].reverse().find((e) => e.type === 'view_detail');
    if (last?.symbol === symbol && now - last.ts < 8000) {
      return;
    }
  }

  memory.push({
    type,
    symbol,
    meta: opts?.meta,
    ts: now,
  });
  memory = memory.filter((e) => now - e.ts < TTL_MS).slice(-MAX_EVENTS);
  await persist();
}

export async function getRecentCompanionEvents(limit = 20): Promise<CompanionEvent[]> {
  await ensureLoaded();
  const now = Date.now();
  memory = memory.filter((e) => now - e.ts < TTL_MS);
  return memory.slice(-limit);
}

export async function countRecentViewDetail(
  symbol: string,
  windowMs = 15 * 60 * 1000,
): Promise<number> {
  await ensureLoaded();
  const now = Date.now();
  const sym = symbol.toUpperCase();
  return memory.filter(
    (e) => e.type === 'view_detail' && e.symbol === sym && now - e.ts <= windowMs,
  ).length;
}
