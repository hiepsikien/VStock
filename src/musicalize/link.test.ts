import { formatLink, parseLink, type LinkState } from './link';

function equal<T>(actual: T, expected: T, label = '') {
  if (actual !== expected) {
    throw new Error(`${label} expected ${String(expected)}, got ${String(actual)}`);
  }
}

const defaults = parseLink('');
equal(defaults.symbol, 'VNM', 'default symbol');
equal(defaults.span, '1D', 'default span');
equal(defaults.date, null, 'default date');
equal(defaults.genre, 'symphony', 'default genre');
equal(defaults.ensemble, null, 'default ensemble');
equal(defaults.humanize, true, 'default humanize');
equal(defaults.color, true, 'default color');

const full = parseLink('?s=fpt&r=1W&g=jazz&e=trio&h=0&c=0');
equal(full.symbol, 'FPT', 'symbol is uppercased');
equal(full.span, '1W', 'span parsed');
equal(full.genre, 'jazz', 'genre parsed');
equal(full.ensemble, 'trio', 'ensemble passes through');
equal(full.humanize, false, 'humanize off');
equal(full.color, false, 'color off');
equal(full.date, null, 'date absent');

const daily = parseLink('?s=vnm&r=1D&d=2026-05-04');
equal(daily.date, '2026-05-04', 'date kept for a daily session');

const weekly = parseLink('?s=vnm&r=1M&d=2026-05-04');
equal(weekly.date, null, 'date dropped outside 1D');

const badDate = parseLink('?r=1D&d=2026-5-4');
equal(badDate.date, null, 'malformed date dropped');

const badSymbol = parseLink('?s=%20%3Cscript%3E');
equal(badSymbol.symbol, 'VNM', 'invalid symbol falls back');
equal(parseLink('?s=abc', 'fpt').symbol, 'ABC', 'fallback is ignored when the symbol is valid');
equal(parseLink('', 'hpg').symbol, 'HPG', 'custom fallback is uppercased');

equal(parseLink('?r=2D').span, '1D', 'invalid span falls back');
equal(parseLink('?g=rock').genre, 'symphony', 'invalid genre falls back');

equal(parseLink('?h=1').humanize, true, 'h=1 is true');
equal(parseLink('?h=0').humanize, false, 'h=0 is false');
equal(parseLink('?h=yes').humanize, true, 'unknown h keeps the default');
equal(parseLink('?c=x').color, true, 'unknown c keeps the default');

const state: LinkState = {
  symbol: 'vnm',
  span: '1D',
  date: '2026-05-04',
  genre: 'ambient',
  ensemble: 'choir',
  humanize: false,
  color: true,
};
equal(
  formatLink(state),
  's=VNM&r=1D&g=ambient&d=2026-05-04&e=choir&h=0&c=1',
  'format writes a stable order',
);

const noDate: LinkState = { ...state, date: null };
equal(formatLink(noDate), 's=VNM&r=1D&g=ambient&e=choir&h=0&c=1', 'no date key when unset');

const longSpan: LinkState = { ...state, span: '1Y' };
equal(formatLink(longSpan).includes('&d='), false, 'format never writes a date outside 1D');

const roundTrip = parseLink(`?${formatLink(state)}`);
equal(roundTrip.symbol, 'VNM', 'round trip symbol');
equal(roundTrip.span, '1D', 'round trip span');
equal(roundTrip.date, '2026-05-04', 'round trip date');
equal(roundTrip.genre, 'ambient', 'round trip genre');
equal(roundTrip.ensemble, 'choir', 'round trip ensemble');
equal(roundTrip.humanize, state.humanize, 'round trip humanize');
equal(roundTrip.color, state.color, 'round trip color');

const bare = parseLink('s=fpt&r=1W');
equal(bare.symbol, 'FPT', 'accepts a search string without the question mark');

console.log('musicalize link tests passed');
