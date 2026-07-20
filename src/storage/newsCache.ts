import AsyncStorage from '@react-native-async-storage/async-storage';
import type { NewsItem } from '../types/news';

const PREFIX = 'vstock.news.';
export const NEWS_CACHE_TTL_MS = 15 * 60 * 1000;

type CacheEntry = {
  items: NewsItem[];
  fetchedAt: number;
};

const memory = new Map<string, CacheEntry>();

function isFresh(entry: CacheEntry): boolean {
  return Date.now() - entry.fetchedAt < NEWS_CACHE_TTL_MS;
}

export function readNewsMemory(key: string): NewsItem[] | null {
  const entry = memory.get(key);
  if (!entry || !isFresh(entry)) return null;
  return entry.items;
}

export async function readNewsCache(key: string): Promise<NewsItem[] | null> {
  const fromMemory = readNewsMemory(key);
  if (fromMemory) return fromMemory;

  try {
    const raw = await AsyncStorage.getItem(PREFIX + key);
    if (!raw) return null;
    const entry = JSON.parse(raw) as CacheEntry;
    if (!Array.isArray(entry.items) || !isFresh(entry)) return null;
    memory.set(key, entry);
    return entry.items;
  } catch {
    return null;
  }
}

export async function writeNewsCache(key: string, items: NewsItem[]): Promise<void> {
  const entry: CacheEntry = { items, fetchedAt: Date.now() };
  memory.set(key, entry);
  try {
    await AsyncStorage.setItem(PREFIX + key, JSON.stringify(entry));
  } catch {
    /* disk cache is best-effort */
  }
}
