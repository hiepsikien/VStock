export type RootStackParamList = {
  Watchlist: undefined;
  News: undefined;
  Detail: { symbol: string };
  Health: undefined;
  CompanionChat: {
    seedMessage?: string;
    screen?: 'Watchlist' | 'Detail';
    symbol?: string;
    watchlistSymbols?: string[];
    avgChange?: number;
    sessionLabel?: string;
  };
};
