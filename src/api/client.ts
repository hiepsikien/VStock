import Constants from 'expo-constants';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import type { ChartRange, Stock } from '../types';
import type { NewsItem } from '../types/news';
import { readNewsCache, readNewsMemory, writeNewsCache } from '../storage/newsCache';
import {
  readDetailCache,
  readDetailCacheStale,
  readHistoryCache,
  readHistoryCacheStale,
  readIndicesCache,
  readIndicesCacheStale,
  readQuotesCache,
  readQuotesCacheStale,
  writeDetailCache,
  writeHistoryCache,
  writeIndicesCache,
  writeQuotesCache,
} from '../storage/marketCache';
import type { IndexQuote } from '../components/WatchlistSummary';
import {
  DEFAULT_PARAMS,
  encodeParams,
  isDefaultParams,
  LINK_SCHEMA_VERSION,
  normalizeParams,
  paramsFromFlags,
  paramsQuery as paramsSuffix,
  type SonifyParams,
} from '../musicalize/params';
import { sanitizePriceChange } from '../utils/sanitizePriceChange';
import { prefetchOutcome, type PrefetchOutcome } from './prefetchPlan';

/** True for private LAN hosts we can rewrite localhost → (not Expo tunnel domains). */
function isLanHostname(host: string): boolean {
  if (host === 'localhost' || host === '127.0.0.1' || host === '10.0.2.2') return true;
  if (/^192\.168\.\d{1,3}\.\d{1,3}$/.test(host)) return true;
  if (/^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(host)) return true;
  const m = /^172\.(\d{1,3})\.\d{1,3}\.\d{1,3}$/.exec(host);
  if (m) {
    const n = Number(m[1]);
    return n >= 16 && n <= 31;
  }
  return false;
}

function stripTrailingSlash(u: string): string {
  return u.replace(/\/$/, '');
}

/** Reject empty / malformed bases like `http://:8000`. */
function isUsableApiBase(u: string): boolean {
  try {
    const parsed = new URL(u);
    return Boolean(parsed.protocol?.startsWith('http') && parsed.hostname?.trim());
  } catch {
    return false;
  }
}

function metroLanHost(): string | null {
  const hostUri =
    Constants.expoConfig?.hostUri ??
    Constants.manifest2?.extra?.expoClient?.hostUri ??
    (Constants as { manifest?: { debuggerHost?: string } }).manifest?.debuggerHost;
  if (typeof hostUri !== 'string' || !hostUri.trim()) return null;
  // "192.168.1.3:8081" | "http://192.168.1.3:8081" | "192.168.1.3"
  const cleaned = hostUri.trim().replace(/^[a-z][a-z0-9+.-]*:\/\//i, '');
  const host = cleaned.split('/')[0]?.split(':')[0]?.trim();
  if (
    !host ||
    host === 'localhost' ||
    host === '127.0.0.1' ||
    !isLanHostname(host)
  ) {
    return null;
  }
  return host;
}

/**
 * Resolve API base URL for the current runtime.
 * Physical device + localhost → Metro LAN IP, else EXPO_PUBLIC_DEVICE_API_URL.
 */
function resolveApiUrl(): string {
  const configured = stripTrailingSlash(
    process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000',
  );
  const deviceFallback = stripTrailingSlash(
    process.env.EXPO_PUBLIC_DEVICE_API_URL ??
      process.env.EXPO_PUBLIC_API_URL_DEVICE ??
      'https://vstock-api.antunai.com',
  );

  if (!__DEV__) {
    return isUsableApiBase(configured) ? configured : deviceFallback;
  }

  try {
    const url = new URL(configured);
    if (url.hostname !== 'localhost' && url.hostname !== '127.0.0.1') {
      return isUsableApiBase(configured) ? configured : deviceFallback;
    }
    // Android emulator → host machine loopback
    if (Platform.OS === 'android' && !Device.isDevice) {
      return 'http://10.0.2.2:8000';
    }
    // iOS Simulator can reach Mac localhost
    if (Platform.OS === 'ios' && !Device.isDevice) {
      return configured;
    }
    // Browser. `expo-device` reports isDevice=true on web, so the phone
    // fallback must not rewrite localhost → GCE. A phone that opened Metro on
    // the LAN still needs the API on that same host, not 127.0.0.1.
    if (Platform.OS === 'web') {
      if (typeof window !== 'undefined') {
        const host = window.location.hostname;
        if (host && isLanHostname(host)) {
          const port = url.port || '8000';
          const local = `http://${host}:${port}`;
          if (isUsableApiBase(local)) return local;
        }
      }
      return configured;
    }
    // Physical device: cloud URL wins over Metro LAN rewrite, unless this
    // Metro session was started to talk to uvicorn on the same Mac.
    const preferLocalApi = process.env.EXPO_PUBLIC_LOCAL_API === '1';
    if (!preferLocalApi && Device.isDevice && isUsableApiBase(deviceFallback)) {
      try {
        const fbHost = new URL(deviceFallback).hostname;
        if (
          fbHost !== 'localhost' &&
          fbHost !== '127.0.0.1' &&
          !isLanHostname(fbHost)
        ) {
          return deviceFallback;
        }
      } catch {
        // fall through to LAN rewrite
      }
    }
    const lan = metroLanHost();
    if (lan) {
      const rawPort = url.port || '8000';
      const port = ['8081', '19000', '19001', '19006'].includes(rawPort)
        ? '8000'
        : rawPort;
      const local = `http://${lan}:${port}`;
      if (isUsableApiBase(local)) return local;
    }
  } catch {
    // fall through
  }

  if (Device.isDevice && isUsableApiBase(deviceFallback)) {
    return deviceFallback;
  }
  return isUsableApiBase(configured) ? configured : deviceFallback;
}

const API_URL = resolveApiUrl();

/** Resolved API base — useful for Health / debug banners. */
export function getApiBaseUrl(): string {
  return API_URL;
}

export const DEFAULT_SYMBOLS = [
  'VNM',
  'FPT',
  'VIC',
  'HPG',
  'MWG',
  'VCB',
  'TCB',
  'MBB',
  'GAS',
  'MSN',
];

type WatchlistDto = {
  symbol: string;
  name: string;
  exchange: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  currency: string;
  sparkline: number[];
  unavailable?: boolean;
};

type StockDetailDto = WatchlistDto & {
  open: number;
  high: number;
  low: number;
  priorClose?: number | null;
  marketCap: string;
  pe: number | null;
  eps?: number | null;
  pb?: number | null;
  roe?: number | null;
  roa?: number | null;
  dividendYield?: number | null;
  revenueLabel?: string | null;
  incomeLatestAnnual?: {
    periodType: 'annual' | 'quarter';
    fiscalDate: string;
    year: number;
    quarter?: number | null;
    netRevenue?: number | null;
    netIncome?: number | null;
  } | null;
  incomeLastQuarters?: Array<{
    periodType: 'annual' | 'quarter';
    fiscalDate: string;
    year: number;
    quarter?: number | null;
    netRevenue?: number | null;
    netIncome?: number | null;
  }>;
};

type HistoryDto = {
  symbol: string;
  range: ChartRange;
  prices: number[];
};

async function apiGet<T>(path: string, signal?: AbortSignal, noStore = false): Promise<T> {
  // Live prices, plans, and DFI change as soon as a movement is written. Only
  // the plan and DFI readers opt out of the HTTP cache; everything else keeps
  // normal caching so watchlist and news do not refetch on every screen.
  const res = await fetch(
    `${API_URL}${path}`,
    noStore ? { signal, cache: 'no-store' as const } : { signal },
  );
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

function toStock(dto: StockDetailDto, history?: Partial<Record<ChartRange, number[]>>): Stock {
  const change = sanitizePriceChange(dto.price, dto.change, dto.changePercent);
  return {
    symbol: dto.symbol,
    name: dto.name,
    exchange: dto.exchange,
    price: dto.price,
    change,
    changePercent: dto.changePercent,
    open: dto.open,
    high: dto.high,
    low: dto.low,
    priorClose: dto.priorClose ?? null,
    volume: dto.volume,
    marketCap: dto.marketCap,
    pe: dto.pe,
    eps: dto.eps ?? null,
    pb: dto.pb ?? null,
    roe: dto.roe ?? null,
    roa: dto.roa ?? null,
    dividendYield: dto.dividendYield ?? null,
    revenueLabel: dto.revenueLabel ?? null,
    incomeLatestAnnual: dto.incomeLatestAnnual ?? null,
    incomeLastQuarters: dto.incomeLastQuarters ?? [],
    currency: dto.currency || '₫',
    sparkline: dto.sparkline ?? [],
    history: {
      '1D': history?.['1D'] ?? dto.sparkline ?? [],
      '1W': history?.['1W'] ?? [],
      '1M': history?.['1M'] ?? [],
      '3M': history?.['3M'] ?? [],
      '1Y': history?.['1Y'] ?? [],
      '5Y': history?.['5Y'] ?? [],
    },
    unavailable: Boolean(dto.unavailable),
  };
}

async function fetchWatchlistNetwork(symbols: string[]): Promise<Stock[]> {
  if (symbols.length === 0) return [];
  const qs = symbols.join(',');
  const rows = await apiGet<WatchlistDto[]>(`/v1/watchlist?symbols=${encodeURIComponent(qs)}`);
  return rows.map((row) =>
    toStock({
      ...row,
      open: row.price,
      high: row.price,
      low: row.price,
      marketCap: '—',
      pe: null,
    }),
  );
}

/** Live quotes only — never falls back to stale cache. Used by price alerts. */
export async function fetchLiveQuotes(symbols: string[]): Promise<Stock[]> {
  if (symbols.length === 0) return [];
  const stocks = await fetchWatchlistNetwork(symbols);
  if (stocks.length) await writeQuotesCache(stocks);
  return stocks;
}

export async function fetchWatchlist(symbols: string[] = DEFAULT_SYMBOLS): Promise<Stock[]> {
  if (symbols.length === 0) return [];

  try {
    return await fetchLiveQuotes(symbols);
  } catch (err) {
    const stale = await readQuotesCacheStale(symbols);
    if (stale?.items.length) return stale.items;
    throw err;
  }
}

/** Stale-while-revalidate for watchlist quotes. */
export async function loadWatchlist(
  symbols: string[],
  handlers: {
    onData: (stocks: Stock[], fromCache: boolean, fetchedAt?: number) => void;
    refresh?: boolean;
  },
): Promise<void> {
  if (symbols.length === 0) {
    handlers.onData([], false);
    return;
  }

  let showedCache = false;

  if (!handlers.refresh) {
    const cached = await readQuotesCache(symbols);
    if (cached?.items.length) {
      showedCache = true;
      handlers.onData(
        cached.items.map((stock) => ({
          ...stock,
          change: sanitizePriceChange(stock.price, stock.change, stock.changePercent),
        })),
        true,
        cached.fetchedAt,
      );
    }
  }

  try {
    const stocks = await fetchWatchlistNetwork(symbols);
    await writeQuotesCache(stocks);
    if (!showedCache || stocks.length > 0) {
      handlers.onData(stocks, false);
    }
  } catch {
    if (!showedCache) {
      const stale = await readQuotesCacheStale(symbols);
      if (stale?.items.length) {
        handlers.onData(stale.items, true, stale.fetchedAt);
        return;
      }
      throw new Error('Không kết nối được máy chủ');
    }
  }
}

async function fetchStockDetailNetwork(symbol: string): Promise<Stock> {
  const sym = symbol.toUpperCase();
  const detail = await apiGet<StockDetailDto>(`/v1/stocks/${encodeURIComponent(sym)}`);
  const day = await apiGet<HistoryDto>(
    `/v1/stocks/${encodeURIComponent(sym)}/history?range=1D`,
  ).catch(() => ({ symbol: sym, range: '1D' as const, prices: detail.sparkline }));

  return toStock(detail, { '1D': day.prices });
}

export async function fetchStockDetail(symbol: string): Promise<Stock> {
  try {
    const stock = await fetchStockDetailNetwork(symbol);
    await writeDetailCache(stock);
    await writeHistoryCache(symbol, '1D', stock.history['1D']);
    return stock;
  } catch (err) {
    const stale = await readDetailCacheStale(symbol);
    if (stale) return stale.data;
    throw err;
  }
}

/** Stale-while-revalidate for stock detail + 1D chart. */
export async function loadStockDetail(
  symbol: string,
  handlers: {
    onData: (stock: Stock, fromCache: boolean, fetchedAt?: number) => void;
    refresh?: boolean;
  },
): Promise<void> {
  const sym = symbol.toUpperCase();
  let showedCache = false;

  if (!handlers.refresh) {
    const cached = await readDetailCache(sym);
    if (cached) {
      showedCache = true;
      const entry = await readDetailCacheStale(sym);
      handlers.onData(cached, true, entry?.fetchedAt);
    }
  }

  try {
    const stock = await fetchStockDetailNetwork(sym);
    await writeDetailCache(stock);
    await writeHistoryCache(sym, '1D', stock.history['1D']);
    handlers.onData(stock, false);
  } catch {
    if (!showedCache) {
      const stale = await readDetailCacheStale(sym);
      if (stale) {
        handlers.onData(stale.data, true, stale.fetchedAt);
        return;
      }
      throw new Error('Không kết nối được máy chủ');
    }
  }
}

async function fetchHistoryNetwork(symbol: string, range: ChartRange): Promise<number[]> {
  const sym = symbol.toUpperCase();
  const data = await apiGet<HistoryDto>(
    `/v1/stocks/${encodeURIComponent(sym)}/history?range=${range}`,
  );
  return data.prices;
}

export type RecapVariant = 'symphony' | 'jazz' | 'minimalist' | 'ambient' | 'guitar';

export type RecapEnsemble =
  | 'classic'
  | 'wood'
  | 'brass'
  | 'soul'
  | 'organ'
  | 'mallet'
  | 'guitar'
  | 'breath'
  | 'choir'
  | 'bach'
  | 'villa'
  | 'barrios'
  | 'brouwer'
  | 'torroba';

export const ENSEMBLE_ROWS: Record<RecapVariant, { id: RecapEnsemble; label: string }[]> = {
  symphony: [
    { id: 'classic', label: 'Dây' },
    { id: 'wood', label: 'Gỗ' },
    { id: 'brass', label: 'Đồng' },
  ],
  jazz: [
    { id: 'classic', label: 'Combo' },
    { id: 'soul', label: 'Soul' },
    { id: 'organ', label: 'Organ' },
  ],
  minimalist: [
    { id: 'classic', label: 'Synth' },
    { id: 'mallet', label: 'Mallet' },
    { id: 'guitar', label: 'Guitar thép' },
  ],
  ambient: [
    { id: 'classic', label: 'Kính' },
    { id: 'breath', label: 'Hơi' },
    { id: 'choir', label: 'Hợp xướng' },
  ],
  guitar: [
    { id: 'bach', label: 'Bach' },
    { id: 'classic', label: 'Sor' },
    { id: 'barrios', label: 'Barrios' },
    { id: 'villa', label: 'Lobos' },
    { id: 'brouwer', label: 'Brouwer' },
    { id: 'torroba', label: 'Torroba' },
  ],
};

export type DfiBand = 'very-clear' | 'clear' | 'fair' | 'faint' | 'very-faint';

/** The server's data-fidelity number. Zero analysis on the client. */
export type DfiBreakdown = {
  score: number;
  band: DfiBand;
  shape: number | null;
  motion: number | null;
  structure: number | null;
  resolution: number | null;
  volume: number | null;
  coverage: number;
  coverage_detail?: number | null;
  opportunity: number;
  confidence: 'low' | 'medium' | 'high';
  n_moves?: number;
  n_sounding?: number;
  /** Pair count behind Motion; low values mean low evidence. */
  motion_pairs?: number;
  version: string;
};

export type DfiSignature = {
  variant: RecapVariant;
  ensemble: string;
  bucket: 'day' | 'span';
  score: number;
  p25: number;
  p75: number;
  n: number;
  version: string;
  updatedAt: string;
  stale: boolean;
};

export type DfiPiece = {
  variant: RecapVariant;
  ensemble: string;
  movement: number | null;
  dfi: DfiBreakdown | null;
  cached: boolean;
  computedAt: string | null;
};

export type DfiPiecesResponse = {
  symbol: string;
  bucket: 'day' | 'span';
  asOf: string;
  pieces: DfiPiece[];
};

export type SessionSummary = {
  date: string;
  close: number;
  changePercent: number;
  bars: number;
};

export type SessionMinutes = {
  symbol: string;
  date: string;
  prices: number[];
  volumes?: number[];
  times: string[];
  changePercent: number;
};

export type SonifyMix = {
  humanize: boolean;
  color: boolean;
};

/** Old callers pass the two booleans; the room passes the full knob set. */
export type SonifyParamsInput = SonifyParams | SonifyMix;

function coerceParams(input?: SonifyParamsInput): SonifyParams {
  if (!input) return DEFAULT_PARAMS;
  if (typeof (input as SonifyMix).humanize === 'boolean') {
    const mix = input as SonifyMix;
    return paramsFromFlags(mix.humanize, mix.color);
  }
  return normalizeParams(input);
}

/** Query suffix for audio and peaks. Empty for Default. */
export function sonifyParamsQuery(input?: SonifyParamsInput): string {
  return paramsSuffix(coerceParams(input));
}

export type ParamsSchemaResponse = {
  schema: number;
  groups: Array<{
    id: string;
    label: string;
    fields: Array<{
      key: string;
      label: string;
      type: 'number' | 'choice' | 'toggle';
      min: number;
      max: number;
      step: number;
      default: number | string | boolean;
      unit: string;
      description: string;
      signed: boolean;
      choices: Array<{ value: string; label: string }>;
      auto: boolean;
      appliesTo: string[];
      tier: string;
    }>;
  }>;
  defaultHash: string;
  enabled: boolean;
  enabledTiers: string[];
  allTiers: string[];
};

/** Keep both A/B cache marks alive while the listener toggles. */
export async function pinParams(hashes: string[], signal?: AbortSignal): Promise<void> {
  const clean = [...new Set(hashes.filter(Boolean))].slice(0, 8);
  if (!clean.length) return;
  try {
    await fetch(`${getApiBaseUrl()}/v1/sonify/params/pin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hashes: clean, ttlSec: 600 }),
      signal,
    });
  } catch {
    // Pinning is best-effort; a miss only means LRU may evict sooner.
  }
}

/** The kill switch lives here, not in the client bundle. */
export async function fetchParamsSchema(signal?: AbortSignal): Promise<ParamsSchemaResponse> {
  return apiGet<ParamsSchemaResponse>('/v1/sonify/params/schema', signal);
}

export type RecapManifest = {
  symbol: string;
  date: string;
  variant: RecapVariant;
  ensemble: RecapEnsemble;
  durationSec: number;
  mapDurationSec: number;
  barCount: number;
  peaks: number[];
  audioUrl: string;
  character?: string | null;
  characterLabel?: string;
  keyLabel?: string;
  /** Dance the guitar writer chose. Empty for the other variants. */
  movementName?: string;
  humanize?: boolean;
  color?: boolean;
  /** Server hash after tier canonicalisation. */
  paramsHash?: string;
  dfi?: DfiBreakdown | null;
};

export function absoluteApiUrl(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${API_URL}${path}`;
}

export async function fetchSessions(symbol: string): Promise<SessionSummary[]> {
  const sym = symbol.toUpperCase();
  const data = await apiGet<{ symbol: string; sessions: SessionSummary[] }>(
    `/v1/stocks/${encodeURIComponent(sym)}/sessions?limit=7`,
  );
  return data.sessions ?? [];
}

export async function fetchSessionMinutes(
  symbol: string,
  day: string,
  signal?: AbortSignal,
): Promise<SessionMinutes> {
  const sym = symbol.toUpperCase();
  return apiGet<SessionMinutes>(
    `/v1/stocks/${encodeURIComponent(sym)}/sessions/${encodeURIComponent(day)}`,
    signal,
  );
}

export type SpanRange = '1W' | '1M' | '3M' | '1Y';

export type SpanMovement = {
  index: number;
  label: string;
  keyLabel: string;
  candleCount: number;
  durationSec: number;
  /** Written musical length. The file in `durationSec` may add a release tail. */
  mapDurationSec?: number;
  ready: boolean;
  audioUrl: string;
  restAfterSec: number;
  warmupSec: number;
  cooldownSec: number;
  prices: number[];
  volumes?: number[];
  /** Audio envelope 0..1 for a rendered movement. Empty until the file exists. */
  peaks?: number[];
  /** Absolute peak level of that file, so movements can be compared. */
  peakLevel?: number;
  character?: string | null;
  characterLabel?: string;
  sessionCharacters?: string[];
  bpm?: number;
  beats?: number;
  beatType?: number;
  /** Dance or tempo composed for this movement. */
  name?: string;
  /** Wall seconds spent inside the export slot. Zero for files written before the field existed. */
  renderSec?: number;
  /** `renderSec / musicalSec`. Used to size lookahead. */
  renderRatio?: number;
  /** Server hash after tier canonicalisation. */
  paramsHash?: string;
  dfi?: DfiBreakdown | null;
};

export type SpanManifest = {
  symbol: string;
  range: SpanRange;
  variant: RecapVariant;
  ensemble: RecapEnsemble;
  movements: SpanMovement[];
  /** Last session day covered by the span, `YYYY-MM-DD`. */
  asOf?: string;
  /** Home key of the ticker. Minor only when every movement is minor. */
  keyLabel?: string;
  humanize?: boolean;
  color?: boolean;
  /** Server hash after tier canonicalisation. */
  paramsHash?: string;
  dfi?: DfiBreakdown | null;
};

export async function fetchSpan(
  symbol: string,
  range: SpanRange,
  variant: RecapVariant,
  ensemble: RecapEnsemble = 'classic',
  signal?: AbortSignal,
  params: SonifyParamsInput = DEFAULT_PARAMS,
): Promise<SpanManifest> {
  const sym = symbol.toUpperCase();
  return apiGet<SpanManifest>(
    `/v1/stocks/${encodeURIComponent(sym)}/span?range=${range}&variant=${variant}&ensemble=${ensemble}${sonifyParamsQuery(params)}`,
    signal,
    true,
  );
}

export type SpanPeaksManifest = {
  symbol: string;
  range: SpanRange;
  variant: RecapVariant;
  /** Optional so an older API without the echo fields still merges peaks. */
  ensemble?: RecapEnsemble;
  humanize?: boolean;
  color?: boolean;
  /** Identity of the plan these rows came from. */
  asOf?: string;
  movements: Array<{
    index: number;
    peaks: number[];
    peakLevel?: number;
    /** URL and readiness let the client merge only the row it still holds. */
    audioUrl?: string;
    ready?: boolean;
    durationSec?: number;
    renderSec?: number;
    renderRatio?: number;
  }>;
};

/** Peaks only: the refresh after a movement's file is written. */
export async function fetchSpanPeaks(
  symbol: string,
  range: SpanRange,
  variant: RecapVariant,
  ensemble: RecapEnsemble = 'classic',
  signal?: AbortSignal,
  params: SonifyParamsInput = DEFAULT_PARAMS,
): Promise<SpanPeaksManifest> {
  const sym = symbol.toUpperCase();
  return apiGet<SpanPeaksManifest>(
    `/v1/stocks/${encodeURIComponent(sym)}/span/peaks?range=${range}&variant=${variant}&ensemble=${ensemble}${sonifyParamsQuery(params)}`,
    signal,
    true,
  );
}

/**
 * Ask the server to render one movement's audio without paying for the file
 * twice. A one-byte range request still runs the export before the response;
 * older servers that ignore Range answer 200, so drop that body.
 *
 * The timeout must cover the queue for the single MuseScore slot, not just the
 * export: an abort after the request entered the slot cancels the render.
 */
export async function prefetchSpanAudio(
  path: string,
  signal?: AbortSignal,
  timeoutMs = 15 * 60_000,
): Promise<PrefetchOutcome> {
  const controller = new AbortController();
  const relay = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener('abort', relay);
  const timer = setTimeout(() => controller.abort(), Math.max(1, timeoutMs));
  try {
    const response = await fetch(absoluteApiUrl(path), {
      signal: controller.signal,
      headers: { Range: 'bytes=0-0' },
    });
    const outcome = prefetchOutcome(response.status);
    if (outcome === 'ready' && response.status === 206) {
      // Consume the one byte. The server has already written the whole file.
      await response.arrayBuffer();
      return outcome;
    }
    try {
      await response.body?.cancel();
    } catch {
      // The file is already written; only a duplicate download was avoided.
    }
    return outcome;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', relay);
  }
}

export type SonifyTapeSymbol = {
  symbol: string;
  base: string;
  quote_volume: number;
  last_price: number;
};

/** Top crypto pairs for the live tape. Volume stays off the listening screen. */
export async function fetchSonifySymbols(signal?: AbortSignal): Promise<SonifyTapeSymbol[]> {
  const data = await apiGet<{ symbols: SonifyTapeSymbol[] }>('/v1/sonify/symbols', signal);
  return data.symbols ?? [];
}

export async function fetchRecap(
  symbol: string,
  day: string,
  variant: RecapVariant,
  ensemble: RecapEnsemble = 'classic',
  signal?: AbortSignal,
  params: SonifyParamsInput = DEFAULT_PARAMS,
): Promise<RecapManifest> {
  const sym = symbol.toUpperCase();
  return apiGet<RecapManifest>(
    `/v1/stocks/${encodeURIComponent(sym)}/sessions/${encodeURIComponent(day)}/recap?variant=${variant}&ensemble=${ensemble}${sonifyParamsQuery(params)}`,
    signal,
    true,
  );
}

/** Compose other genre/ensemble rows of the current session or movement. */
export async function fetchDfiPieces(
  params: {
    symbol: string;
    bucket: 'day' | 'span';
    date?: string | null;
    range?: string | null;
    movement?: number;
    variant?: RecapVariant | null;
    ensemble?: RecapEnsemble | null;
    /** The knobs. `mix` stays for the older listening surfaces. */
    params?: SonifyParamsInput;
    mix?: SonifyMix;
  },
  signal?: AbortSignal,
): Promise<DfiPiecesResponse> {
  const query = new URLSearchParams();
  query.set('symbol', params.symbol.toUpperCase());
  query.set('bucket', params.bucket);
  if (params.bucket === 'day') {
    if (params.date) query.set('date', params.date);
  } else {
    if (params.range) query.set('range', params.range);
    query.set('movement', String(params.movement ?? 0));
  }
  if (params.variant) query.set('variant', params.variant);
  if (params.ensemble) query.set('ensemble', params.ensemble);
  const shaped = coerceParams(params.params ?? params.mix);
  if (!isDefaultParams(shaped)) query.set('p', encodeParams(shaped, LINK_SCHEMA_VERSION));
  return apiGet<DfiPiecesResponse>(`/v1/sonify/dfi/pieces?${query.toString()}`, signal, true);
}

/** Corpus medians. An empty list means the offline artifact is not built yet. */
export async function fetchDfiSignatures(
  bucket: 'day' | 'span',
  variant?: RecapVariant,
  signal?: AbortSignal,
): Promise<DfiSignature[]> {
  const query = new URLSearchParams();
  query.set('bucket', bucket);
  if (variant) query.set('variant', variant);
  return apiGet<DfiSignature[]>(`/v1/sonify/dfi/signatures?${query.toString()}`, signal);
}

export async function fetchHistory(symbol: string, range: ChartRange): Promise<number[]> {
  try {
    const prices = await fetchHistoryNetwork(symbol, range);
    await writeHistoryCache(symbol, range, prices);
    return prices;
  } catch (err) {
    const stale = await readHistoryCacheStale(symbol, range);
    if (stale) return stale.data;
    throw err;
  }
}

/** Stale-while-revalidate for chart history. */
export async function loadHistory(
  symbol: string,
  range: ChartRange,
  handlers: {
    onData: (prices: number[], fromCache: boolean, fetchedAt?: number) => void;
    refresh?: boolean;
  },
): Promise<void> {
  const sym = symbol.toUpperCase();
  let showedCache = false;

  if (!handlers.refresh) {
    const cached = await readHistoryCache(sym, range);
    if (cached?.length) {
      showedCache = true;
      const entry = await readHistoryCacheStale(sym, range);
      handlers.onData(cached, true, entry?.fetchedAt);
    }
  }

  try {
    const prices = await fetchHistoryNetwork(sym, range);
    await writeHistoryCache(sym, range, prices);
    handlers.onData(prices, false);
  } catch {
    if (!showedCache) {
      const stale = await readHistoryCacheStale(sym, range);
      if (stale) {
        handlers.onData(stale.data, true, stale.fetchedAt);
        return;
      }
      throw new Error('Không tải được biểu đồ');
    }
  }
}

export type MarketSymbol = {
  symbol: string;
  name: string;
  exchange: string;
  /** Stored candle ranges. Empty means the symbol has no chart yet. */
  ranges?: string[];
};

export type RangeSparkline = {
  symbol: string;
  changePercent: number | null;
  sparkline: number[];
  /** The range actually served when the requested one was missing. */
  rangeUsed?: string;
};

/** Stored-only rail candles, downsample server-side. Never plans a sonification. */
export async function fetchRangeSparklines(
  symbols: string[],
  range: ChartRange,
): Promise<RangeSparkline[]> {
  if (symbols.length === 0) return [];
  const params = new URLSearchParams({
    symbols: symbols.join(','),
    range,
  });
  return apiGet<RangeSparkline[]>(`/v1/watchlist/sparklines?${params.toString()}`);
}

export async function fetchMarketSymbols(exchange?: 'HOSE' | 'HNX'): Promise<MarketSymbol[]> {
  const qs = exchange ? `?exchange=${exchange}` : '';
  const data = await apiGet<{ count: number; symbols: MarketSymbol[] }>(`/v1/symbols${qs}`);
  return data.symbols;
}

export async function searchMarketSymbols(query: string, limit = 30): Promise<MarketSymbol[]> {
  const q = query.trim();
  if (!q) return [];
  return apiGet<MarketSymbol[]>(
    `/v1/symbols/search?q=${encodeURIComponent(q)}&limit=${limit}`,
  );
}

async function readMarketNewsCache(limit: number): Promise<NewsItem[] | null> {
  const exact = readNewsMemory(`market:${limit}`) ?? (await readNewsCache(`market:${limit}`));
  if (exact) return exact;

  if (limit > 30) {
    const full = readNewsMemory('market:30') ?? (await readNewsCache('market:30'));
    if (full?.length) return full.slice(0, limit);
  }
  if (limit > 5) {
    const preview = readNewsMemory('market:5') ?? (await readNewsCache('market:5'));
    if (preview?.length) return preview;
  }
  return null;
}

async function fetchMarketNewsNetwork(
  limit: number,
  category?: string,
): Promise<NewsItem[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (category && category !== 'all') {
    params.set('category', category);
  }
  const data = await apiGet<{ items: NewsItem[] }>(`/v1/news/market?${params.toString()}`);
  return data.items;
}

async function fetchSymbolNewsNetwork(symbol: string, limit: number): Promise<NewsItem[]> {
  const data = await apiGet<{ items: NewsItem[] }>(
    `/v1/news/symbols/${encodeURIComponent(symbol)}?limit=${limit}`,
  );
  return data.items;
}

export async function fetchMarketNews(
  limit = 30,
  options?: { refresh?: boolean; category?: string },
): Promise<NewsItem[]> {
  const category = options?.category && options.category !== 'all' ? options.category : undefined;
  const cacheKey = `market:${limit}:${category ?? 'all'}`;
  if (!options?.refresh) {
    const cached = await readNewsCache(cacheKey);
    if (cached) return cached;
  }

  const items = await fetchMarketNewsNetwork(limit, category);
  await writeNewsCache(cacheKey, items);
  return items;
}

export async function fetchSymbolNews(
  symbol: string,
  limit = 15,
  options?: { refresh?: boolean },
): Promise<NewsItem[]> {
  const sym = symbol.toUpperCase();
  const cacheKey = `symbol:${sym}:${limit}`;
  if (!options?.refresh) {
    const cached = readNewsMemory(cacheKey) ?? (await readNewsCache(cacheKey));
    if (cached) return cached;
  }

  const items = await fetchSymbolNewsNetwork(sym, limit);
  await writeNewsCache(cacheKey, items);
  return items;
}

/** Stale-while-revalidate: show cache immediately, fetch fresh in background. */
export async function loadMarketNews(
  limit: number,
  handlers: {
    onData: (items: NewsItem[], fromCache: boolean) => void;
    refresh?: boolean;
    category?: string;
  },
): Promise<void> {
  const category =
    handlers.category && handlers.category !== 'all' ? handlers.category : undefined;
  const cacheKey = `market:${limit}:${category ?? 'all'}`;
  let showedCache = false;

  if (!handlers.refresh) {
    const cached = readNewsMemory(cacheKey) ?? (await readNewsCache(cacheKey));
    if (cached?.length) {
      showedCache = true;
      handlers.onData(cached, true);
    } else if (!category) {
      const legacy = await readMarketNewsCache(limit);
      if (legacy?.length) {
        showedCache = true;
        handlers.onData(legacy, true);
      }
    }
  }

  try {
    const items = await fetchMarketNewsNetwork(limit, category);
    await writeNewsCache(cacheKey, items);
    if (!showedCache || items.length > 0) {
      handlers.onData(items, false);
    }
  } catch {
    if (!showedCache) handlers.onData([], false);
  }
}

export async function loadSymbolNews(
  symbol: string,
  limit: number,
  handlers: {
    onData: (items: NewsItem[], fromCache: boolean) => void;
    refresh?: boolean;
  },
): Promise<void> {
  const sym = symbol.toUpperCase();
  const cacheKey = `symbol:${sym}:${limit}`;
  let showedCache = false;

  if (!handlers.refresh) {
    const cached = readNewsMemory(cacheKey) ?? (await readNewsCache(cacheKey));
    if (cached?.length) {
      showedCache = true;
      handlers.onData(cached, true);
    }
  }

  try {
    const items = await fetchSymbolNewsNetwork(sym, limit);
    await writeNewsCache(cacheKey, items);
    if (!showedCache || items.length > 0) {
      handlers.onData(items, false);
    }
  } catch {
    if (!showedCache) handlers.onData([], false);
  }
}

export function getApiUrl(): string {
  return API_URL;
}

async function fetchMarketIndicesNetwork(): Promise<IndexQuote[]> {
  const data = await apiGet<{ items: IndexQuote[] }>('/v1/indices');
  return data.items;
}

export async function fetchMarketIndices(): Promise<IndexQuote[]> {
  try {
    const items = await fetchMarketIndicesNetwork();
    await writeIndicesCache(items);
    return items;
  } catch (err) {
    const stale = await readIndicesCacheStale();
    if (stale?.items.length) return stale.items;
    throw err;
  }
}

/** Stale-while-revalidate for market indices. */
export async function loadMarketIndices(handlers: {
  onData: (items: IndexQuote[], fromCache: boolean, fetchedAt?: number) => void;
  refresh?: boolean;
}): Promise<void> {
  let showedCache = false;

  if (!handlers.refresh) {
    const cached = await readIndicesCache();
    if (cached?.items.length) {
      showedCache = true;
      handlers.onData(cached.items, true, cached.fetchedAt);
    }
  }

  try {
    const items = await fetchMarketIndicesNetwork();
    await writeIndicesCache(items);
    if (!showedCache || items.length > 0) {
      handlers.onData(items, false);
    }
  } catch {
    if (!showedCache) {
      const stale = await readIndicesCacheStale();
      if (stale?.items.length) {
        handlers.onData(stale.items, true, stale.fetchedAt);
        return;
      }
    }
    handlers.onData([], false);
  }
}

export type ProviderHealth = {
  kind: string;
  name: string;
  status: string;
  lastSuccessAt?: string | null;
  lastErrorAt?: string | null;
  lastError?: string | null;
  lastItemCount: number;
  stale: boolean;
};

export type StoreHealth = {
  quotesCount: number;
  quotesLatestAt?: string | null;
  newsCount: number;
  newsLatestAt?: string | null;
  indicesCount: number;
  indicesLatestAt?: string | null;
  historyCount: number;
  historyLatestAt?: string | null;
  symbolsCount: number;
  symbolsLatestAt?: string | null;
  fundamentalsCount: number;
  fundamentalsLatestAt?: string | null;
};

export type JobHealth = {
  name: string;
  lastRunAt?: string | null;
  lastSuccessAt?: string | null;
  lastErrorAt?: string | null;
  lastError?: string | null;
  lastItemCount: number;
};

export type SourceHealthResponse = {
  status: string;
  checkedAt: string;
  marketOpen: boolean;
  store: StoreHealth;
  providers: ProviderHealth[];
  jobs: JobHealth[];
};

export async function fetchSourceHealth(): Promise<SourceHealthResponse> {
  return apiGet<SourceHealthResponse>('/v1/health/sources');
}

export type CompanionChatMessage = {
  role: 'user' | 'assistant';
  content: string;
};

export type CompanionContextDto = {
  screen?: string;
  symbol?: string;
  sessionLabel?: string;
  watchlistSymbols?: string[];
  watchlists?: {
    activeId: string;
    lists: Array<{ id: string; name: string; symbols: string[] }>;
  };
  avgChange?: number;
  recentEvents?: Array<{ type: string; symbol?: string; ts: number; meta?: string }>;
  bond?: {
    firstMetAt?: number;
    lastChatAt?: number;
    messageCount?: number;
    symbolsOfInterest?: string[];
    notes?: string[];
    userNickname?: string;
  };
  characterId?: string;
  nudgeKind?: 'market' | 'recall' | 'mood';
  recallTopic?: string;
  daysSinceLastChat?: number;
  todayMood?: string;
};

export async function fetchCompanionHealth(): Promise<{ configured: boolean }> {
  return apiGet<{ configured: boolean }>('/v1/companion/health');
}

export async function requestCompanionNudge(body: {
  context?: CompanionContextDto;
  events?: CompanionContextDto['recentEvents'];
  cooldownUntil?: number;
}): Promise<{ show: boolean; message: string | null }> {
  const res = await fetch(`${API_URL}/v1/companion/nudge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<{ show: boolean; message: string | null }>;
}

/** Non-streaming companion chat (simpler for MVP UI). */
export type CompanionChatResult = {
  message: string;
  bubbles: string[];
  suggestions: string[];
  bondNotes?: string[] | null;
  actions?: Array<{
    type: string;
    symbol?: string;
    symbols?: string[];
    watchlistId?: string;
    watchlistName?: string;
    name?: string;
    reason?: string;
    label?: string;
  }>;
};

export async function sendCompanionChat(
  messages: CompanionChatMessage[],
  context?: CompanionContextDto,
): Promise<CompanionChatResult> {
  const res = await fetch(`${API_URL}/v1/companion/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ messages, context, stream: false }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  const data = (await res.json()) as {
    message?: string;
    bubbles?: string[];
    suggestions?: string[];
    bondNotes?: string[] | null;
    actions?: CompanionChatResult['actions'];
  };
  const message = (data.message || '').trim();
  const bubbles = (data.bubbles || []).map((b) => b.trim()).filter(Boolean);
  return {
    message,
    bubbles: bubbles.length ? bubbles : message ? [message] : [],
    suggestions: (data.suggestions || []).filter(Boolean).slice(0, 4),
    bondNotes: data.bondNotes ?? null,
    actions: data.actions ?? [],
  };
}

/** SSE streaming companion chat. Calls onDelta for each chunk.
 * On React Native, ReadableStream often yields nothing — falls back to non-stream.
 */
export async function streamCompanionChat(
  messages: CompanionChatMessage[],
  context: CompanionContextDto | undefined,
  onDelta: (delta: string) => void,
  onReplace?: (text: string) => void,
): Promise<string> {
  const res = await fetch(`${API_URL}/v1/companion/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ messages, context, stream: true }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }

  const fallback = async (): Promise<string> => {
    const result = await sendCompanionChat(messages, context);
    const text = result.message;
    onReplace?.(text);
    return text;
  };

  if (!res.body?.getReader) {
    return fallback();
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let assembled = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';
    for (const block of parts) {
      const line = block
        .split('\n')
        .map((l) => l.trim())
        .find((l) => l.startsWith('data:'));
      if (!line) continue;
      try {
        const payload = JSON.parse(line.slice(5).trim()) as {
          delta?: string;
          replace?: string;
          done?: boolean;
          error?: string;
        };
        if (payload.error) throw new Error(payload.error);
        if (payload.replace != null) {
          assembled = payload.replace;
          onReplace?.(assembled);
        } else if (payload.delta) {
          assembled += payload.delta;
          onDelta(payload.delta);
        }
      } catch (err) {
        if (err instanceof SyntaxError) continue;
        throw err;
      }
    }
  }

  if (!assembled.trim()) {
    return fallback();
  }
  return assembled;
}
