export type RootStackParamList = {
  Watchlist: undefined;
  News: undefined;
  Detail: { symbol: string };
  Health: undefined;
  CompanionChat: {
    seedUserMessage?: string;
    seedAssistantMessage?: string;
    screen?: 'Watchlist' | 'Detail';
    symbol?: string;
    watchlistSymbols?: string[];
    avgChange?: number;
    sessionLabel?: string;
  };
};
