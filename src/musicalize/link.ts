import type { RecapEnsemble, RecapVariant } from '../api/client';
import { GENRES, LISTEN_SPANS, type ListenSpan } from './labels';

export type LinkState = {
  symbol: string;
  span: ListenSpan;
  date: string | null;
  genre: RecapVariant;
  /** Not validated against the genre here; the room falls back to `classic`. */
  ensemble: RecapEnsemble | null;
  humanize: boolean;
  color: boolean;
};

const DEFAULT_SYMBOL = 'VNM';
const DEFAULT_GENRE: RecapVariant = 'symphony';
const DEFAULT_SPAN: ListenSpan = '1D';
const SPANS = new Set<string>(LISTEN_SPANS);
const GENRES_BY_ID = new Set<string>(GENRES.map((item) => item.id));
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const SYMBOL = /^[A-Z0-9._-]{1,16}$/;

function flag(value: string | null, fallback: boolean): boolean {
  if (value === '1') return true;
  if (value === '0') return false;
  return fallback;
}

/**
 * Read the deep link. Anything unknown falls back silently: a bad URL should
 * still open a working room.
 */
export function parseLink(search: string, fallbackSymbol = DEFAULT_SYMBOL): LinkState {
  const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  const rawSymbol = (params.get('s') ?? '').trim().toUpperCase();
  const symbol = SYMBOL.test(rawSymbol) ? rawSymbol : fallbackSymbol.toUpperCase();

  const rawSpan = params.get('r') ?? '';
  const span = SPANS.has(rawSpan) ? (rawSpan as ListenSpan) : DEFAULT_SPAN;

  const rawDate = params.get('d') ?? '';
  const date = span === '1D' && DATE.test(rawDate) ? rawDate : null;

  const rawGenre = params.get('g') ?? '';
  const genre = GENRES_BY_ID.has(rawGenre) ? (rawGenre as RecapVariant) : DEFAULT_GENRE;

  const rawEnsemble = (params.get('e') ?? '').trim();
  const ensemble = rawEnsemble ? (rawEnsemble as RecapEnsemble) : null;

  return {
    symbol,
    span,
    date,
    genre,
    ensemble,
    humanize: flag(params.get('h'), true),
    color: flag(params.get('c'), true),
  };
}

/** Query string without the leading `?`, stable order. */
export function formatLink(state: LinkState): string {
  const params = new URLSearchParams();
  params.set('s', state.symbol.toUpperCase());
  params.set('r', state.span);
  params.set('g', state.genre);
  if (state.span === '1D' && state.date) params.set('d', state.date);
  if (state.ensemble) params.set('e', state.ensemble);
  params.set('h', state.humanize ? '1' : '0');
  params.set('c', state.color ? '1' : '0');
  return params.toString();
}

type WebLocation = {
  pathname: string;
  hash: string;
  search: string;
  href: string;
};

function webLocation(): WebLocation | null {
  const loc = (globalThis as { location?: WebLocation }).location;
  return loc && typeof loc.href === 'string' ? loc : null;
}

type HistoryLike = {
  replaceState?: (data: unknown, unused: string, url: string) => void;
};

/** Initial room state from the URL. Native has no location and gets defaults. */
export function readLink(fallbackSymbol = DEFAULT_SYMBOL): LinkState {
  const loc = webLocation();
  return parseLink(loc?.search ?? '', fallbackSymbol);
}

/** Keep the URL shareable without adding history entries on every tune. */
export function writeLink(state: LinkState): void {
  const loc = webLocation();
  const history = (globalThis as { history?: HistoryLike }).history;
  if (!loc || !history?.replaceState) return;
  const query = formatLink(state);
  try {
    history.replaceState(null, '', `${loc.pathname}${query ? `?${query}` : ''}${loc.hash}`);
  } catch {
    // A sandboxed document can refuse the rewrite; the room still works.
  }
}

export function linkSupported(): boolean {
  const nav = (globalThis as { navigator?: { clipboard?: { writeText?: unknown } } }).navigator;
  return Boolean(webLocation() && nav?.clipboard?.writeText);
}

/** Copy the address bar. The URL is already kept current by `writeLink`. */
export async function copyCurrentLink(): Promise<boolean> {
  const loc = webLocation();
  const nav = (globalThis as { navigator?: { clipboard?: { writeText?: (text: string) => Promise<void> } } })
    .navigator;
  if (!loc || !nav?.clipboard?.writeText) return false;
  try {
    await nav.clipboard.writeText(loc.href);
    return true;
  } catch {
    return false;
  }
}
