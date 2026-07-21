import type { Watchlist } from '../storage/watchlist';
import type { WatchlistsState } from '../storage/watchlist';

export type CompanionWatchlistAction =
  | {
      type: 'add_symbol';
      symbol: string;
      watchlistId?: string;
      watchlistName?: string;
      label?: string;
    }
  | {
      type: 'create_watchlist';
      name: string;
      symbol?: string;
      symbols?: string[];
      label?: string;
    }
  | {
      type: 'suggest_add_symbol';
      symbol: string;
      reason?: string;
      label?: string;
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

export function actionLabel(action: CompanionWatchlistAction): string {
  if (action.label?.trim()) return action.label.trim();
  switch (action.type) {
    case 'create_watchlist': {
      const syms = action.symbols?.length
        ? action.symbols
        : action.symbol
          ? [action.symbol]
          : [];
      if (syms.length) {
        return `Tạo “${action.name}” (${syms.join(', ')})`;
      }
      return `Tạo danh sách “${action.name}”`;
    }
    case 'add_symbol':
      return action.watchlistName
        ? `Thêm ${action.symbol} vào “${action.watchlistName}”`
        : `Thêm ${action.symbol} vào danh sách`;
    case 'suggest_add_symbol':
      return `Thêm ${action.symbol} vào danh sách`;
    default:
      return 'Xác nhận';
  }
}

/** Expand ambiguous add into one button per watchlist. */
export function expandWatchlistActions(
  actions: CompanionWatchlistAction[],
  lists: Watchlist[],
): CompanionWatchlistAction[] {
  const out: CompanionWatchlistAction[] = [];
  for (const action of actions) {
    if (
      action.type === 'add_symbol' &&
      !action.watchlistId &&
      lists.length > 1
    ) {
      for (const list of lists) {
        if (list.symbols.includes(action.symbol.toUpperCase())) continue;
        out.push({
          type: 'add_symbol',
          symbol: action.symbol,
          watchlistId: list.id,
          watchlistName: list.name,
        });
      }
      continue;
    }
    out.push(action);
  }
  return out;
}

export function suggestionForAddSymbol(symbol: string): string {
  return `Thêm ${symbol.toUpperCase()} vào danh sách`;
}
