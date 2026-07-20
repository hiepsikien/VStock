import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'vstock.recent.symbols';
const MAX = 10;

export async function loadRecentSymbols(limit = MAX): Promise<string[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((s) => String(s).toUpperCase().trim())
      .filter(Boolean)
      .slice(0, limit);
  } catch {
    return [];
  }
}

export async function addRecentSymbol(symbol: string): Promise<string[]> {
  const sym = symbol.toUpperCase().trim();
  if (!sym) return loadRecentSymbols();
  const current = await loadRecentSymbols(MAX);
  const next = [sym, ...current.filter((s) => s !== sym)].slice(0, MAX);
  await AsyncStorage.setItem(KEY, JSON.stringify(next));
  return next;
}

export async function clearRecentSymbols(): Promise<void> {
  await AsyncStorage.removeItem(KEY);
}
