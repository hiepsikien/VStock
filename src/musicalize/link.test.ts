import { formatLink, parseLink, type LinkState } from './link';
import {
  DEFAULT_PARAMS,
  encodeParams,
  isDefaultParams,
  paramsEqual,
  paramsFromFlags,
} from './params';

function equal<T>(actual: T, expected: T, label = '') {
  if (actual !== expected) {
    throw new Error(`${label} expected ${String(expected)}, got ${String(actual)}`);
  }
}

function sameParams(actual: Record<string, number>, expected: Record<string, number>, label = '') {
  if (!paramsEqual(actual, expected)) {
    throw new Error(`${label} params differ: ${JSON.stringify(actual)} != ${JSON.stringify(expected)}`);
  }
}

const defaults = parseLink('');
equal(defaults.symbol, 'VNM', 'default symbol');
equal(defaults.span, '1D', 'default span');
equal(defaults.date, null, 'default date');
equal(defaults.genre, 'symphony', 'default genre');
equal(defaults.ensemble, null, 'default ensemble');
sameParams(defaults.params, DEFAULT_PARAMS, 'default params');

const full = parseLink('?s=fpt&r=1W&g=jazz&e=trio&h=0&c=0');
equal(full.symbol, 'FPT', 'symbol is uppercased');
equal(full.span, '1W', 'span parsed');
equal(full.genre, 'jazz', 'genre parsed');
equal(full.ensemble, 'trio', 'ensemble passes through');
sameParams(full.params, paramsFromFlags(false, false), 'legacy h/c map to params');
equal(full.date, null, 'date absent');

const legacyHumanize = parseLink('?h=0');
sameParams(
  legacyHumanize.params,
  { ...DEFAULT_PARAMS, humanize: 0, breath: 0 },
  'h=0 also stops breath',
);
const legacyColor = parseLink('?c=0');
sameParams(legacyColor.params, { ...DEFAULT_PARAMS, color: 0 }, 'c=0 stops color');
const unknownFlags = parseLink('?h=yes&c=x');
sameParams(unknownFlags.params, DEFAULT_PARAMS, 'unknown h/c keep default');

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

const shaped = { ...DEFAULT_PARAMS, tempo: 0.96, humanize: 1.1 };
const encoded = encodeParams(shaped);
sameParams(parseLink(`?p=${encoded}`).params, shaped, 'p round-trips');
sameParams(parseLink('?p=not-base64!').params, DEFAULT_PARAMS, 'bad p falls back');
sameParams(parseLink(`?p=${'A'.repeat(2049)}`).params, DEFAULT_PARAMS, 'long p falls back');
sameParams(
  parseLink(`?p=${encoded}&h=0&c=0`).params,
  shaped,
  'p wins over legacy flags',
);

const state: LinkState = {
  symbol: 'vnm',
  span: '1D',
  date: '2026-05-04',
  genre: 'ambient',
  ensemble: 'choir',
  params: shaped,
};
const text = formatLink(state);
equal(
  text.startsWith('s=VNM&r=1D&g=ambient&d=2026-05-04&e=choir&p='),
  true,
  'format writes a stable order and p last',
);
equal(text.includes('h=') || text.includes('c='), false, 'format never writes h/c');
equal(
  isDefaultParams(parseLink(`?${text}`).params),
  false,
  'format keeps non-default params',
);
sameParams(parseLink(`?${text}`).params, shaped, 'formatted p round-trips');

const legacyState = parseLink('?s=vnm&r=1D&h=0&c=0');
const rewritten = formatLink(legacyState);
equal(rewritten.includes('h=') || rewritten.includes('c='), false, 'legacy flags are converted');
equal(rewritten.includes('p='), true, 'legacy flags become p');
sameParams(parseLink(`?${rewritten}`).params, paramsFromFlags(false, false), 'converted link maps back');

const defaultState: LinkState = { ...state, params: DEFAULT_PARAMS };
equal(formatLink(defaultState).includes('p='), false, 'default omits p');

const noDate: LinkState = { ...state, date: null };
equal(formatLink(noDate).includes('&d='), false, 'no date key when unset');

const longSpan: LinkState = { ...state, span: '1Y' };
equal(formatLink(longSpan).includes('&d='), false, 'format never writes a date outside 1D');

const roundTrip = parseLink(`?${formatLink(state)}`);
equal(roundTrip.symbol, 'VNM', 'round trip symbol');
equal(roundTrip.span, '1D', 'round trip span');
equal(roundTrip.date, '2026-05-04', 'round trip date');
equal(roundTrip.genre, 'ambient', 'round trip genre');
equal(roundTrip.ensemble, 'choir', 'round trip ensemble');
sameParams(roundTrip.params, state.params, 'round trip params');

const bare = parseLink('s=fpt&r=1W');
equal(bare.symbol, 'FPT', 'accepts a search string without the question mark');

console.log('musicalize link tests passed');
