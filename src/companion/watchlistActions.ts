import type { WatchlistsState } from '../storage/watchlist';

export type CompanionWatchlistAction =
  | {
      type: 'add_symbol';
      symbol: string;
      watchlistId?: string;
      watchlistName?: string;
    }
  | {
      type: 'create_watchlist';
      name: string;
      symbol?: string;
    }
  | {
      type: 'suggest_add_symbol';
      symbol: string;
      reason?: string;
    };

export type WatchlistsContextDto = {
  activeId: string;
  lists: Array<{ id: string; name: string; symbols: string[] }>;
};

export function watchlistsToContext(state: WatchlistsState): WatchlistsContextDto {
  return {
    activeId: state.activeId,
    lists: state.lists.map((l) => ({
      id: l.id,
      name: l.name,
      symbols: l.symbols,
    })),
  };
}

export function suggestionForAddSymbol(symbol: string): string {
  return `Thêm ${symbol.toUpperCase()} vào danh sách`;
}
