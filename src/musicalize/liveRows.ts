export type TapeSymbol = { symbol: string; base: string };

export type LiveListRow = {
  key: string;
  symbol: string;
  source: 'live' | 'history';
  title: string;
  subtitle: string | null;
};

/** Top pairs, plus the BTC history tape directly under BTC. It is still a stream. */
export function liveListRows(symbols: TapeSymbol[]): LiveListRow[] {
  const rows: LiveListRow[] = [];
  let sawBtc = false;
  for (const item of symbols) {
    rows.push({
      key: `live:${item.symbol}`,
      symbol: item.symbol,
      source: 'live',
      title: item.symbol,
      subtitle: null,
    });
    if (item.symbol === 'BTCUSDT') {
      sawBtc = true;
      rows.push(historyRow());
    }
  }
  if (!sawBtc) rows.push(historyRow());
  return rows;
}

/** Keep the highlight and the transport on the same row after the list refreshes. */
export function pickLiveRow(rows: LiveListRow[], selectedKey: string): LiveListRow | null {
  if (!rows.length) return null;
  return rows.find((row) => row.key === selectedKey) ?? rows[0];
}

function historyRow(): LiveListRow {
  return {
    key: 'history:BTCUSDT',
    symbol: 'BTCUSDT',
    source: 'history',
    title: 'BTCUSDT',
    subtitle: 'đoạn ~90s',
  };
}
