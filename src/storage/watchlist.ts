import AsyncStorage from '@react-native-async-storage/async-storage';
import { DEFAULT_SYMBOLS } from '../api/client';

export type Watchlist = {
  id: string;
  name: string;
  symbols: string[];
  pinnedSymbols: string[];
};

export type WatchlistsState = {
  activeId: string;
  lists: Watchlist[];
};

const KEY = 'vstock.watchlists.v2';
const LEGACY_KEY = 'vstock.watchlist.symbols';

function defaultState(): WatchlistsState {
  return {
    activeId: 'main',
    lists: [
      {
        id: 'main',
        name: 'Theo dõi',
        symbols: [...DEFAULT_SYMBOLS],
        pinnedSymbols: [],
      },
    ],
  };
}

function normalizeState(raw: unknown): WatchlistsState {
  if (!raw || typeof raw !== 'object') return defaultState();
  const data = raw as Partial<WatchlistsState>;
  if (!Array.isArray(data.lists) || data.lists.length === 0) return defaultState();

  const lists = data.lists.map((list) => ({
    id: String(list.id ?? 'main'),
    name: String(list.name ?? 'Theo dõi'),
    symbols: Array.isArray(list.symbols)
      ? list.symbols.map((s) => String(s).toUpperCase().trim()).filter(Boolean)
      : [...DEFAULT_SYMBOLS],
    pinnedSymbols: Array.isArray(list.pinnedSymbols)
      ? list.pinnedSymbols.map((s) => String(s).toUpperCase().trim()).filter(Boolean)
      : [],
  }));

  const activeId = lists.some((l) => l.id === data.activeId)
    ? String(data.activeId)
    : lists[0].id;

  return { activeId, lists };
}

async function migrateLegacy(): Promise<WatchlistsState | null> {
  try {
    const raw = await AsyncStorage.getItem(LEGACY_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed) || parsed.length === 0) return null;
    const symbols = parsed
      .map((s) => String(s).toUpperCase().trim())
      .filter(Boolean);
    return {
      activeId: 'main',
      lists: [{ id: 'main', name: 'Theo dõi', symbols, pinnedSymbols: [] }],
    };
  } catch {
    return null;
  }
}

export async function loadWatchlistsState(): Promise<WatchlistsState> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) {
      const migrated = await migrateLegacy();
      const state = migrated ?? defaultState();
      await saveWatchlistsState(state);
      return state;
    }
    return normalizeState(JSON.parse(raw));
  } catch {
    return defaultState();
  }
}

export async function saveWatchlistsState(state: WatchlistsState): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(state));
}

export function getActiveWatchlist(state: WatchlistsState): Watchlist {
  return state.lists.find((l) => l.id === state.activeId) ?? state.lists[0];
}

export async function setActiveWatchlist(id: string): Promise<WatchlistsState> {
  const state = await loadWatchlistsState();
  if (!state.lists.some((l) => l.id === id)) return state;
  const next = { ...state, activeId: id };
  await saveWatchlistsState(next);
  return next;
}

export async function createWatchlist(name: string): Promise<WatchlistsState> {
  const state = await loadWatchlistsState();
  const id = `wl_${Date.now()}`;
  const next: WatchlistsState = {
    activeId: id,
    lists: [
      ...state.lists,
      { id, name: name.trim() || 'Danh sách mới', symbols: [], pinnedSymbols: [] },
    ],
  };
  await saveWatchlistsState(next);
  return next;
}

export async function renameWatchlist(id: string, name: string): Promise<WatchlistsState> {
  const state = await loadWatchlistsState();
  const next = {
    ...state,
    lists: state.lists.map((l) =>
      l.id === id ? { ...l, name: name.trim() || l.name } : l,
    ),
  };
  await saveWatchlistsState(next);
  return next;
}

export async function deleteWatchlist(id: string): Promise<WatchlistsState> {
  const state = await loadWatchlistsState();
  if (state.lists.length <= 1) return state;
  const lists = state.lists.filter((l) => l.id !== id);
  const activeId = state.activeId === id ? lists[0].id : state.activeId;
  const next = { activeId, lists };
  await saveWatchlistsState(next);
  return next;
}

function patchActive(
  state: WatchlistsState,
  patch: (list: Watchlist) => Watchlist,
): WatchlistsState {
  return {
    ...state,
    lists: state.lists.map((l) => (l.id === state.activeId ? patch(l) : l)),
  };
}

export async function addWatchlistSymbol(symbol: string): Promise<WatchlistsState> {
  const state = await loadWatchlistsState();
  return addSymbolToWatchlist(symbol, getActiveWatchlist(state).id);
}

/** Add symbol to a specific watchlist by id. */
export async function addSymbolToWatchlist(
  symbol: string,
  watchlistId: string,
): Promise<WatchlistsState> {
  const sym = symbol.toUpperCase().trim();
  const state = await loadWatchlistsState();
  const target = state.lists.find((l) => l.id === watchlistId);
  if (!target || target.symbols.includes(sym)) return state;
  const next: WatchlistsState = {
    ...state,
    lists: state.lists.map((l) =>
      l.id === watchlistId ? { ...l, symbols: [...l.symbols, sym] } : l,
    ),
  };
  await saveWatchlistsState(next);
  return next;
}

/** Remove symbol from a specific watchlist by id. */
export async function removeSymbolFromWatchlist(
  symbol: string,
  watchlistId: string,
): Promise<WatchlistsState> {
  const sym = symbol.toUpperCase().trim();
  const state = await loadWatchlistsState();
  const target = state.lists.find((l) => l.id === watchlistId);
  if (!target || !target.symbols.includes(sym)) return state;
  const next: WatchlistsState = {
    ...state,
    lists: state.lists.map((l) =>
      l.id === watchlistId
        ? {
            ...l,
            symbols: l.symbols.filter((s) => s !== sym),
            pinnedSymbols: l.pinnedSymbols.filter((s) => s !== sym),
          }
        : l,
    ),
  };
  await saveWatchlistsState(next);
  return next;
}

export async function removeWatchlistSymbol(symbol: string): Promise<WatchlistsState> {
  const sym = symbol.toUpperCase().trim();
  const state = await loadWatchlistsState();
  const active = getActiveWatchlist(state);
  let symbols = active.symbols.filter((s) => s !== sym);
  if (symbols.length === 0) symbols = [...DEFAULT_SYMBOLS];
  const next = patchActive(state, (l) => ({
    ...l,
    symbols,
    pinnedSymbols: l.pinnedSymbols.filter((s) => s !== sym),
  }));
  await saveWatchlistsState(next);
  return next;
}

export async function togglePinSymbol(symbol: string): Promise<WatchlistsState> {
  const sym = symbol.toUpperCase().trim();
  const state = await loadWatchlistsState();
  const next = patchActive(state, (l) => {
    const pinned = l.pinnedSymbols.includes(sym)
      ? l.pinnedSymbols.filter((s) => s !== sym)
      : [sym, ...l.pinnedSymbols.filter((s) => s !== sym)];
    return { ...l, pinnedSymbols: pinned };
  });
  await saveWatchlistsState(next);
  return next;
}

/** @deprecated use loadWatchlistsState */
export async function loadWatchlistSymbols(): Promise<string[]> {
  const state = await loadWatchlistsState();
  return getActiveWatchlist(state).symbols;
}

/** @deprecated use saveWatchlistsState */
export async function saveWatchlistSymbols(symbols: string[]): Promise<void> {
  const state = await loadWatchlistsState();
  const unique = [...new Set(symbols.map((s) => s.toUpperCase().trim()).filter(Boolean))];
  const next = patchActive(state, (l) => ({ ...l, symbols: unique }));
  await saveWatchlistsState(next);
}
