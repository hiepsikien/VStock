import AsyncStorage from '@react-native-async-storage/async-storage';

export type CacheEntry<T> = {
  data: T;
  fetchedAt: number;
};

const memory = new Map<string, CacheEntry<unknown>>();

function storageKey(prefix: string, key: string): string {
  return `${prefix}${key}`;
}

function isFresh(entry: CacheEntry<unknown>, ttlMs: number): boolean {
  return Date.now() - entry.fetchedAt < ttlMs;
}

export function formatCacheAge(fetchedAt: number): string {
  const minutes = Math.floor((Date.now() - fetchedAt) / 60_000);
  if (minutes < 1) return 'vừa xong';
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  return `${days} ngày trước`;
}

export function readCacheMemory<T>(prefix: string, key: string, ttlMs?: number): T | null {
  const entry = memory.get(storageKey(prefix, key)) as CacheEntry<T> | undefined;
  if (!entry) return null;
  if (ttlMs != null && !isFresh(entry, ttlMs)) return null;
  return entry.data;
}

export async function readCacheDisk<T>(
  prefix: string,
  key: string,
  ttlMs?: number,
): Promise<T | null> {
  try {
    const raw = await AsyncStorage.getItem(storageKey(prefix, key));
    if (!raw) return null;
    const entry = JSON.parse(raw) as CacheEntry<T>;
    if (entry?.data == null || typeof entry.fetchedAt !== 'number') return null;
    if (ttlMs != null && !isFresh(entry, ttlMs)) return null;
    memory.set(storageKey(prefix, key), entry);
    return entry.data;
  } catch {
    return null;
  }
}

export async function readCache<T>(
  prefix: string,
  key: string,
  ttlMs?: number,
): Promise<T | null> {
  const fromMemory = readCacheMemory<T>(prefix, key, ttlMs);
  if (fromMemory != null) return fromMemory;
  return readCacheDisk<T>(prefix, key, ttlMs);
}

export async function readCacheStale<T>(
  prefix: string,
  key: string,
): Promise<CacheEntry<T> | null> {
  const memKey = storageKey(prefix, key);
  const fromMemory = memory.get(memKey) as CacheEntry<T> | undefined;
  if (fromMemory) return fromMemory;

  try {
    const raw = await AsyncStorage.getItem(memKey);
    if (!raw) return null;
    const entry = JSON.parse(raw) as CacheEntry<T>;
    if (entry?.data == null || typeof entry.fetchedAt !== 'number') return null;
    memory.set(memKey, entry);
    return entry;
  } catch {
    return null;
  }
}

export async function writeCache<T>(prefix: string, key: string, data: T): Promise<void> {
  const entry: CacheEntry<T> = { data, fetchedAt: Date.now() };
  memory.set(storageKey(prefix, key), entry);
  try {
    await AsyncStorage.setItem(storageKey(prefix, key), JSON.stringify(entry));
  } catch {
    /* disk cache is best-effort */
  }
}
