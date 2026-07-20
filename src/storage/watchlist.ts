import AsyncStorage from '@react-native-async-storage/async-storage';
import { DEFAULT_SYMBOLS } from '../api/client';

const KEY = 'vstock.watchlist.symbols';

export async function loadWatchlistSymbols(): Promise<string[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return [...DEFAULT_SYMBOLS];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed) || parsed.length === 0) {
      return [...DEFAULT_SYMBOLS];
    }
    return parsed
      .map((s) => String(s).toUpperCase().trim())
      .filter(Boolean);
  } catch {
    return [...DEFAULT_SYMBOLS];
  }
}

export async function saveWatchlistSymbols(symbols: string[]): Promise<void> {
  const unique = [...new Set(symbols.map((s) => s.toUpperCase().trim()).filter(Boolean))];
  await AsyncStorage.setItem(KEY, JSON.stringify(unique));
}

export async function addWatchlistSymbol(symbol: string): Promise<string[]> {
  const current = await loadWatchlistSymbols();
  const next = current.includes(symbol.toUpperCase())
    ? current
    : [...current, symbol.toUpperCase()];
  await saveWatchlistSymbols(next);
  return next;
}

export async function removeWatchlistSymbol(symbol: string): Promise<string[]> {
  const current = await loadWatchlistSymbols();
  const next = current.filter((s) => s !== symbol.toUpperCase());
  await saveWatchlistSymbols(next.length ? next : [...DEFAULT_SYMBOLS]);
  return next.length ? next : [...DEFAULT_SYMBOLS];
}
