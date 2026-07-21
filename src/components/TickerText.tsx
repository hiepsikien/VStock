import React, { memo, useMemo } from 'react';
import { StyleSheet, Text, type StyleProp, type TextStyle } from 'react-native';

export type TextPart =
  | { type: 'text'; value: string }
  | { type: 'ticker'; value: string };

const TICKER_RE = /\b([A-Z]{3})\b/g;

/** Words that look like tickers but aren't HOSE/HNX codes in casual VN chat. */
const FALSE_TICKERS = new Set([
  'NAY',
  'TIN',
  'SAO',
  'THE',
  'ROI',
  'CUA',
  'CHO',
  'VAO',
  'VOI',
  'MOT',
  'HAI',
  'BON',
  'NAM',
  'SAU',
  'BAY',
  'TAM',
  'HON',
  'RAT',
  'LAI',
  'VAN',
  'DEN',
  'NUA',
  'THI',
  'NEU',
  'KHI',
  'LAM',
  'CAI',
  'DAY',
  'NOI',
  'XEM',
  'HOI',
  'GIA',
  'MUC',
  'LOI',
  'NEN',
  'BAN',
  'MUA',
  'NHA',
  'ONG',
  'CHI',
  'ANH',
  'TOI',
  'APP',
  'API',
  'CEO',
  'ETF',
  'USD',
  'VND',
  'AND',
  'FOR',
  'YOU',
  'ALL',
  'CAN',
  'HOW',
  'NEW',
  'NOW',
  'OLD',
  'SEE',
  'TWO',
  'WAY',
  'WHO',
  'DID',
  'ITS',
  'LET',
  'PUT',
  'SAY',
  'SHE',
  'TOO',
  'USE',
  'BUT',
  'NOT',
  'ARE',
  'WAS',
  'ONE',
  'OUR',
  'OUT',
  'DAY',
  'GET',
  'HAS',
  'HIM',
  'HIS',
  'HER',
  'ATC',
  'ATO',
  'IPO',
  'FOMO',
]);

export function splitTickerParts(
  text: string,
  allowlist?: ReadonlySet<string> | null,
): TextPart[] {
  const parts: TextPart[] = [];
  let last = 0;
  const re = new RegExp(TICKER_RE.source, 'g');
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const sym = m[1];
    const start = m.index;
    if (start > last) {
      parts.push({ type: 'text', value: text.slice(last, start) });
    }
    const ok =
      !FALSE_TICKERS.has(sym) &&
      (!allowlist || allowlist.size === 0 || allowlist.has(sym));
    parts.push(ok ? { type: 'ticker', value: sym } : { type: 'text', value: sym });
    last = start + sym.length;
  }
  if (last < text.length) {
    parts.push({ type: 'text', value: text.slice(last) });
  }
  return parts.length ? parts : [{ type: 'text', value: text }];
}

type Props = {
  text: string;
  style?: StyleProp<TextStyle>;
  linkColor?: string;
  /** If set, only these symbols become tappable (plus still not false tickers). */
  allowlist?: ReadonlySet<string> | null;
  onPressSymbol?: (symbol: string) => void;
};

function TickerTextInner({
  text,
  style,
  linkColor,
  allowlist,
  onPressSymbol,
}: Props) {
  const parts = useMemo(
    () => splitTickerParts(text, allowlist),
    [allowlist, text],
  );

  if (!onPressSymbol) {
    return <Text style={style}>{text}</Text>;
  }

  return (
    <Text style={style}>
      {parts.map((part, i) =>
        part.type === 'ticker' ? (
          <Text
            key={`${part.value}-${i}`}
            style={[styles.link, linkColor ? { color: linkColor } : null]}
            onPress={() => onPressSymbol(part.value)}
          >
            {part.value}
          </Text>
        ) : (
          <Text key={`t-${i}`}>{part.value}</Text>
        ),
      )}
    </Text>
  );
}

export const TickerText = memo(TickerTextInner);

const styles = StyleSheet.create({
  link: {
    fontWeight: '700',
    textDecorationLine: 'underline',
  },
});
