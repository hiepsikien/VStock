import {
  MIN_CROP_SIZE,
  type CropRect,
  type StudioAccess,
  type StudioAnalysisNote,
  type StudioAnalyzeDraft,
  type StudioError,
  type StudioExample,
  type StudioPublishedSpec,
  type StudioUpload,
} from './protocol';

export type { CropRect } from './protocol';

/**
 * Pure helpers for the sentence Studio. Nothing here talks to the network.
 *
 * The editor edits **one spec mapping** (the object inside Workstream A's
 * `{ schema_version: 1, runtime: "code", specs: [...] }` wrapper), which is the
 * body `POST /studio/sentence/validate` expects. The wrapper is added by the
 * compile/publish path later, not by this screen.
 */

export type PatternId =
  | 'castillo'
  | 'sonatina'
  | 'fandanguillo'
  | 'danza'
  | 'galop'
  | 'villa_pattern'
  | 'preludio'
  | 'brouwer_etude';

export type Composer = 'Torroba' | 'Sor' | 'Villa' | 'Barrios' | 'Brouwer';

export type PatternOption = {
  id: PatternId;
  label: string;
  composer: Composer;
  meters: string[];
};

export const ANY_METER = '*';

/**
 * Display metadata only. The palette of patterns and meters comes from
 * `GET /sentence/examples`; this table supplies labels/composers and backs the
 * embedded fallback samples when that endpoint is unavailable.
 *
 * Villa (`villa_pattern`) and Barrios (`preludio`) are preview-only candidates,
 * so they have labels here but no embedded sample.
 */
export const PATTERNS: PatternOption[] = [
  { id: 'castillo', label: 'Castillo', composer: 'Torroba', meters: ['3/4', '4/4'] },
  { id: 'sonatina', label: 'Sonatina', composer: 'Torroba', meters: [ANY_METER] },
  { id: 'fandanguillo', label: 'Fandanguillo', composer: 'Torroba', meters: [ANY_METER] },
  { id: 'danza', label: 'Danza', composer: 'Torroba', meters: ['3/4', '6/8'] },
  { id: 'galop', label: 'Galop', composer: 'Sor', meters: [ANY_METER] },
  {
    id: 'villa_pattern',
    label: 'Villa arpeggio',
    composer: 'Villa',
    meters: ['4/4'],
  },
  {
    id: 'preludio',
    label: 'Barrios cathedral',
    composer: 'Barrios',
    meters: ['4/4'],
  },
  {
    id: 'brouwer_etude',
    label: 'Brouwer etude',
    composer: 'Brouwer',
    meters: ['4/4'],
  },
];

export function patternOption(pattern: string): PatternOption | undefined {
  return PATTERNS.find((item) => item.id === pattern);
}

export function patternLabel(pattern: string): string {
  return patternOption(pattern)?.label ?? pattern;
}

export function meterLabel(meter: string): string {
  return meter === ANY_METER ? 'any meter' : meter;
}

export type StudioSample = {
  /** Stable key, also used as the picker value. `pattern:meter`. */
  key: string;
  /** Requested pattern id. Candidate ids are not part of the shipped registry. */
  pattern: string;
  meter: string;
  title: string;
  spec: Record<string, unknown>;
  fixture: Record<string, unknown>;
  /** Server-side example/spec id, when the sample came from the API. */
  id?: string;
  source?: 'api' | 'fallback';
};

/**
 * A full, valid SentenceSpec per pattern/meter pair, copied from the registry
 * in `backend/app/sonify/guitar_torroba.py` / `guitar_sor.py`.
 *
 * Fields are spelled out (including defaults) so the JSON doubles as
 * documentation of the wire shape. Keep these in sync with `SentenceSpec`,
 * `Select`, `Span`, and `Slot` in `backend/app/sonify/sentence_specs.py`.
 */
export const SAMPLES: StudioSample[] = [
  {
    key: 'castillo:3/4',
    pattern: 'castillo',
    meter: '3/4',
    title: 'Castillo 3/4 · walk',
    spec: {
      id: 'castillo_34_walk',
      pattern: 'castillo',
      meter: '3/4',
      select: {
        length_min: 2,
        length_max: null,
        n_parity: 'even',
        n_mod: null,
        closes: null,
        rise_min: 0,
      },
      span: {
        tile: 9,
        remainder: 'same_figure',
        truncate_to_length: true,
        cycle: false,
        exact: false,
      },
      slots: [{ start: 0, bars: 9, figure: 13, cell: null, anchor: 'start' }],
    },
    fixture: { length: 8, n: 2, closes: false, rise: 1 },
  },
  {
    key: 'castillo:4/4',
    pattern: 'castillo',
    meter: '4/4',
    title: 'Castillo 4/4 · short',
    spec: {
      id: 'castillo_44_short',
      pattern: 'castillo',
      meter: '4/4',
      select: {
        length_min: 2,
        length_max: 3,
        n_parity: 'any',
        n_mod: null,
        closes: null,
        rise_min: 0,
      },
      span: {
        tile: null,
        remainder: 'exact',
        truncate_to_length: true,
        cycle: false,
        exact: true,
      },
      slots: [{ start: 0, bars: 2, figure: 8, cell: null, anchor: 'start' }],
    },
    fixture: { length: 3, n: 2, closes: false, rise: 1 },
  },
  {
    key: 'sonatina:*',
    pattern: 'sonatina',
    meter: ANY_METER,
    title: 'Sonatina · open, 7+ bars',
    spec: {
      id: 'son_open_l7plus',
      pattern: 'sonatina',
      meter: ANY_METER,
      select: {
        length_min: 7,
        length_max: null,
        n_parity: 'any',
        n_mod: null,
        closes: 'open',
        rise_min: 0,
      },
      span: {
        tile: null,
        remainder: 'exact',
        truncate_to_length: true,
        cycle: false,
        exact: true,
      },
      slots: [
        { start: 0, bars: 2, figure: 4, cell: null, anchor: 'start' },
        { start: 3, bars: 1, figure: 1, cell: null, anchor: 'start' },
        { start: 5, bars: 2, figure: 2, cell: null, anchor: 'start' },
      ],
    },
    fixture: { length: 8, n: 2, closes: false, rise: 1 },
  },
  {
    key: 'fandanguillo:*',
    pattern: 'fandanguillo',
    meter: ANY_METER,
    title: 'Fandanguillo · even open turn',
    spec: {
      id: 'fan_even_open',
      pattern: 'fandanguillo',
      meter: ANY_METER,
      select: {
        length_min: 4,
        length_max: null,
        n_parity: 'even',
        n_mod: null,
        closes: 'open',
        rise_min: 1,
      },
      span: {
        tile: null,
        remainder: 'exact',
        truncate_to_length: true,
        cycle: false,
        exact: true,
      },
      slots: [{ start: 0, bars: 4, figure: 5, cell: null, anchor: 'start' }],
    },
    fixture: { length: 6, n: 2, closes: false, rise: 2 },
  },
  {
    key: 'danza:3/4',
    pattern: 'danza',
    meter: '3/4',
    title: 'Danza 3/4 · open',
    spec: {
      id: 'danza_34_open',
      pattern: 'danza',
      meter: '3/4',
      select: {
        length_min: 4,
        length_max: null,
        n_parity: 'any',
        n_mod: null,
        closes: 'open',
        rise_min: 0,
      },
      span: {
        tile: null,
        remainder: 'exact',
        truncate_to_length: true,
        cycle: false,
        exact: true,
      },
      slots: [{ start: 0, bars: 4, figure: 6, cell: null, anchor: 'start' }],
    },
    fixture: { length: 5, n: 2, closes: false, rise: 1 },
  },
  {
    key: 'danza:6/8',
    pattern: 'danza',
    meter: '6/8',
    title: 'Danza 6/8 · open',
    spec: {
      id: 'danza_68_open',
      pattern: 'danza',
      meter: '6/8',
      select: {
        length_min: 4,
        length_max: null,
        n_parity: 'any',
        n_mod: null,
        closes: 'open',
        rise_min: 0,
      },
      span: {
        tile: null,
        remainder: 'exact',
        truncate_to_length: true,
        cycle: false,
        exact: true,
      },
      slots: [{ start: 0, bars: 4, figure: 6, cell: null, anchor: 'start' }],
    },
    fixture: { length: 5, n: 2, closes: false, rise: 1 },
  },
  {
    key: 'galop:*',
    pattern: 'galop',
    meter: ANY_METER,
    title: 'Galop · run cycle',
    spec: {
      id: 'galop_cycle',
      pattern: 'galop',
      meter: ANY_METER,
      select: {
        length_min: 1,
        length_max: null,
        n_parity: 'any',
        n_mod: null,
        closes: null,
        rise_min: 0,
      },
      span: {
        tile: 8,
        remainder: 'truncate_cycle',
        truncate_to_length: true,
        cycle: true,
        exact: false,
      },
      slots: [
        { start: 0, bars: 4, figure: null, cell: 'galop1', anchor: 'start' },
        { start: 4, bars: 4, figure: null, cell: 'galop2', anchor: 'start' },
      ],
    },
    fixture: { run_length: 10 },
  },
];

export const DEFAULT_SAMPLE = SAMPLES[0];

export function samplesForPattern(
  pattern: string,
  samples: readonly StudioSample[] = SAMPLES,
): StudioSample[] {
  return samples.filter((sample) => sample.pattern === pattern);
}

export function defaultSampleForPattern(
  pattern: string,
  samples: readonly StudioSample[] = SAMPLES,
): StudioSample {
  return samplesForPattern(pattern, samples)[0] ?? samples[0] ?? DEFAULT_SAMPLE;
}

export function findSample(
  pattern: string,
  meter: string,
  samples: readonly StudioSample[] = SAMPLES,
): StudioSample | undefined {
  return samples.find(
    (sample) => sample.pattern === pattern && sample.meter === meter,
  );
}

/** Pattern ids in first-seen order, so the picker follows the API ordering. */
export function patternIds(samples: readonly StudioSample[]): string[] {
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const sample of samples) {
    if (seen.has(sample.pattern)) continue;
    seen.add(sample.pattern);
    ids.push(sample.pattern);
  }
  return ids;
}

/** Meters offered for one pattern, in first-seen order. */
export function metersForPattern(
  samples: readonly StudioSample[],
  pattern: string,
): string[] {
  const seen = new Set<string>();
  const meters: string[] = [];
  for (const sample of samples) {
    if (sample.pattern !== pattern || seen.has(sample.meter)) continue;
    seen.add(sample.meter);
    meters.push(sample.meter);
  }
  return meters;
}

/** One-line composer summary built from whatever the API returned. */
export function patternCatalogHint(samples: readonly StudioSample[]): string {
  const groups = new Map<string, string[]>();
  for (const pattern of patternIds(samples)) {
    const option = patternOption(pattern);
    const composer = option?.composer ?? 'Other';
    const labels = groups.get(composer) ?? [];
    labels.push(option?.label ?? pattern);
    groups.set(composer, labels);
  }
  return [...groups]
    .map(([composer, labels]) => `${composer}: ${labels.join(', ')}`)
    .join(' · ');
}

/** Build the fixture the server would otherwise default from the spec. */
export function fixtureForSpec(spec: Record<string, unknown>): Record<string, unknown> {
  if (!isRecord(spec)) return {};
  const select = isRecord(spec.select) ? spec.select : {};
  const span = isRecord(spec.span) ? spec.span : {};

  const parity = select.n_parity;
  const nMod = Array.isArray(select.n_mod) ? select.n_mod[1] : null;
  const n =
    typeof nMod === 'number'
      ? nMod
      : parity === 'odd'
        ? 1
        : parity === 'even'
          ? 0
          : null;

  const length =
    typeof span.tile === 'number' && span.tile > 0
      ? span.tile
      : typeof select.length_min === 'number' && select.length_min > 0
        ? select.length_min
        : null;

  const fixture: Record<string, unknown> = {};
  const key = span.cycle === true ? 'run_length' : 'length';
  if (length != null) fixture[key] = length;
  if (n != null) fixture.n = n;
  fixture.closes = select.closes === 'close';
  if (typeof select.rise_min === 'number') fixture.rise = select.rise_min;
  return fixture;
}

export function sampleText(sample: StudioSample): string {
  return JSON.stringify(sample.spec, null, 2);
}

export function fixtureText(sample: StudioSample): string {
  return JSON.stringify(sample.fixture, null, 2);
}

export function fixtureTextForSpec(spec: Record<string, unknown>): string {
  return JSON.stringify(fixtureForSpec(spec), null, 2);
}

/** Convert one examples-API entry into the picker's sample shape. */
export function exampleToSample(example: StudioExample): StudioSample {
  const spec = example.payload;
  return {
    key: `${example.pattern}:${example.meter}`,
    pattern: example.pattern,
    meter: example.meter,
    id: example.id,
    title: `${patternLabel(example.pattern)} · ${meterLabel(example.meter)}`,
    spec,
    fixture: fixtureForSpec(spec),
    source: 'api',
  };
}

export function examplesToSamples(examples: readonly StudioExample[]): StudioSample[] {
  return examples.map(exampleToSample);
}

/** `2026-11-05T09:41:02.123+00:00` -> `2026-11-05 09:41`. */
export function publishedAtLabel(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return '—';
  const match = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/.exec(trimmed);
  if (match) return `${match[1]} ${match[2]}`;
  const parsed = new Date(trimmed);
  if (!Number.isNaN(parsed.getTime())) {
    const iso = parsed.toISOString();
    return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
  }
  return trimmed;
}

export function publishedSpecTitle(spec: StudioPublishedSpec): string {
  return `${patternLabel(spec.pattern)} · ${meterLabel(spec.meter)}`;
}

/**
 * Compact lineage for a history row, e.g. `rollback of 0123456789…`.
 * Null for ordinary publishes, so the row stays unchanged.
 */
export function publishedSpecLineage(spec: StudioPublishedSpec): string | null {
  const source = spec.rollbackOf?.trim();
  return source ? `rollback of ${shortId(source)}` : null;
}

/** `v4 · rollback of 0123456789…`; version is omitted when the server omits it. */
export function rollbackLabel(
  version: number | null | undefined,
  rollbackOf: string | null | undefined,
): string | null {
  const source = rollbackOf?.trim();
  if (!source) return null;
  const prefix =
    typeof version === 'number' && Number.isInteger(version) && version > 0
      ? `v${version} · `
      : '';
  return `${prefix}rollback of ${shortId(source)}`;
}

export function publishedSpecMeta(spec: StudioPublishedSpec): string {
  const base = `v${spec.version} · ${publishedAtLabel(spec.createdAt)}`;
  const lineage = publishedSpecLineage(spec);
  return lineage ? `${base} · ${lineage}` : base;
}

/** State of the published list while a refresh is in flight. */
export type PublishedListState = {
  loading: boolean;
  items: StudioPublishedSpec[];
  error: string | null;
};

export type PublishedListEvent =
  | { kind: 'start' }
  | { kind: 'success'; items: StudioPublishedSpec[] }
  | { kind: 'failure'; message: string };

/**
 * Refresh transitions keep the previous rows visible while loading and after a
 * failed reload, so a rollback/publish does not blank the history panel.
 */
export function nextPublishedList(
  state: PublishedListState,
  event: PublishedListEvent,
): PublishedListState {
  switch (event.kind) {
    case 'start':
      return { ...state, loading: true, error: null };
    case 'success':
      return { loading: false, items: event.items, error: null };
    case 'failure':
      return { loading: false, items: state.items, error: event.message };
  }
}

/** Keep a published row compact while still exposing the full id to a11y tools. */
export function shortId(id: string, keep = 10): string {
  return id.length <= keep ? id : `${id.slice(0, keep)}…`;
}

/** 1.24 -> `1.2s`; 61 -> `1:01`; missing -> `—`. */
export function durationLabel(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '—';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const total = Math.round(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

/** Counters in the editor header. Kept pure so the test can assert them. */
export function textStats(text: string): { lines: number; chars: number } {
  return { lines: text.split('\n').length, chars: text.length };
}

export type JsonObjectResult =
  | { ok: true; value: Record<string, unknown> }
  | { ok: false; errors: StudioError[] };

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Extract a line/column from a V8 or Hermes JSON.parse message. */
export function jsonErrorLocation(
  message: string,
  text: string,
): { line: number; column: number } | null {
  const explicit = /line\s+(\d+)\s+column\s+(\d+)/i.exec(message);
  if (explicit) {
    return { line: Number(explicit[1]), column: Number(explicit[2]) };
  }
  const position = /position\s+(\d+)/i.exec(message);
  if (!position) return null;
  const index = Math.max(0, Math.min(Number(position[1]), text.length));
  const before = text.slice(0, index);
  const lastBreak = before.lastIndexOf('\n');
  return {
    line: before.split('\n').length,
    column: index - lastBreak,
  };
}

/** Parse any JSON object, with a path-shaped error for the UI. */
export function parseJsonObject(text: string, label = 'JSON'): JsonObjectResult {
  if (!text.trim()) {
    return { ok: false, errors: [{ path: '$', message: `${label} is empty.` }] };
  }
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch (error) {
    const raw = error instanceof Error ? error.message : String(error);
    const location = jsonErrorLocation(raw, text);
    const where = location ? `line ${location.line}, column ${location.column}` : 'an unknown position';
    return {
      ok: false,
      errors: [{ path: '$', message: `Invalid JSON at ${where}. ${raw}` }],
    };
  }
  if (!isRecord(value)) {
    return {
      ok: false,
      errors: [{ path: '$', message: `${label} must be a JSON object (one spec mapping).` }],
    };
  }
  return { ok: true, value };
}

/**
 * Cheap pre-flight checks so the editor can point at obvious mistakes before a
 * round trip. The server remains authoritative for sentence semantics (tile
 * fit, slot anchors, figure ids, selection coverage).
 */
export function checkSpecShape(spec: Record<string, unknown>): StudioError[] {
  const errors: StudioError[] = [];
  const requiredString = (key: string) => {
    const value = spec[key];
    if (typeof value !== 'string' || !value.trim()) {
      errors.push({ path: key, message: 'must be a non-empty string' });
    }
  };

  requiredString('id');
  requiredString('pattern');
  requiredString('meter');

  const select = spec.select;
  if (!isRecord(select)) {
    errors.push({ path: 'select', message: 'must be an object' });
  } else {
    if (typeof select.length_min !== 'number') {
      errors.push({ path: 'select.length_min', message: 'must be a number' });
    }
    if (select.length_max != null && typeof select.length_max !== 'number') {
      errors.push({ path: 'select.length_max', message: 'must be a number or null' });
    }
    if (
      select.n_parity != null &&
      !['any', 'even', 'odd'].includes(String(select.n_parity))
    ) {
      errors.push({ path: 'select.n_parity', message: "must be 'any', 'even', or 'odd'" });
    }
    if (select.closes != null && !['open', 'close'].includes(String(select.closes))) {
      errors.push({ path: 'select.closes', message: "must be 'open', 'close', or null" });
    }
    if (select.rise_min != null && typeof select.rise_min !== 'number') {
      errors.push({ path: 'select.rise_min', message: 'must be a number' });
    }
  }

  const span = spec.span;
  if (!isRecord(span)) {
    errors.push({ path: 'span', message: 'must be an object' });
  } else if (span.tile != null && typeof span.tile !== 'number') {
    errors.push({ path: 'span.tile', message: 'must be a number or null' });
  }

  const slots = spec.slots;
  if (!Array.isArray(slots) || slots.length === 0) {
    errors.push({ path: 'slots', message: 'must be a non-empty array' });
  } else {
    slots.forEach((slot, index) => {
      if (!isRecord(slot)) {
        errors.push({ path: `slots[${index}]`, message: 'must be an object' });
        return;
      }
      if (typeof slot.start !== 'number' || !Number.isFinite(slot.start)) {
        errors.push({ path: `slots[${index}].start`, message: 'must be a number' });
      }
      if (
        typeof slot.bars !== 'number' ||
        !Number.isInteger(slot.bars) ||
        slot.bars < 1
      ) {
        errors.push({ path: `slots[${index}].bars`, message: 'must be an integer >= 1' });
      }
      const hasFigure = typeof slot.figure === 'number';
      const hasCell = typeof slot.cell === 'string' && slot.cell.trim() !== '';
      const hasProcedure =
        typeof slot.procedure === 'string' && slot.procedure.trim() !== '';
      const realizers = Number(hasFigure) + Number(hasCell) + Number(hasProcedure);
      if (realizers !== 1) {
        errors.push({
          path: `slots[${index}]`,
          message:
            'needs exactly one of figure (number), cell (non-empty string), or procedure (non-empty string)',
        });
      }
      if (
        slot.anchor != null &&
        !['start', 'middle', 'end'].includes(String(slot.anchor))
      ) {
        errors.push({
          path: `slots[${index}].anchor`,
          message: "must be 'start', 'middle', or 'end'",
        });
      }
    });
  }

  return errors;
}

export type CheckedSpec =
  | { ok: true; spec: Record<string, unknown> }
  | { ok: false; errors: StudioError[] };

export function checkSpecText(text: string): CheckedSpec {
  const parsed = parseJsonObject(text, 'Spec');
  if (!parsed.ok) return parsed;
  const errors = checkSpecShape(parsed.value);
  if (errors.length) return { ok: false, errors };
  return { ok: true, spec: parsed.value };
}

/** `select.length_min` and `["body","select"]` both become `$.select.length_min`. */
export function normalizeErrorPath(path: string): string {
  const trimmed = path.trim();
  if (!trimmed) return '$';
  if (trimmed.startsWith('$')) return trimmed;
  if (trimmed.startsWith('[')) return `$${trimmed}`;
  return `$.${trimmed}`;
}

/** Keep fixture errors distinct from spec errors in the shared panel. */
export function prefixErrorPaths(errors: StudioError[], prefix: string): StudioError[] {
  return errors.map((error) => ({
    path: error.path === '$' ? prefix : `${prefix}.${error.path.replace(/^\$\.?/, '')}`,
    message: error.message,
  }));
}

export function describeRequestFailure(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === 'string' && error) return error;
  return 'Unknown Studio API error.';
}

function compactJson(value: unknown): string {
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

/** Pretty JSON split into lines, capped so one huge blob cannot fill the pane. */
export function valueLines(value: unknown, limit = 80): string[] {
  if (value == null) return [];
  let text: string;
  if (typeof value === 'string') {
    text = value;
  } else {
    try {
      text = JSON.stringify(value, null, 2);
    } catch {
      text = String(value);
    }
  }
  const lines = text.split('\n');
  if (lines.length <= limit) return lines;
  return [...lines.slice(0, limit), `… ${lines.length - limit} more lines`];
}

function rangeLabel(bars: unknown): string | null {
  if (!Array.isArray(bars) || bars.length === 0) return null;
  const first = bars[0];
  const last = bars[bars.length - 1];
  return `bars ${String(first)}–${String(last)}`;
}

function spanLine(span: unknown): string | null {
  if (typeof span === 'string') return span;
  if (Array.isArray(span) && span.length === 2) {
    const range = rangeLabel(span[1]);
    return range ? `figure ${String(span[0])} · ${range}` : null;
  }
  if (!isRecord(span)) return null;
  const figure = span.figure != null ? `figure ${String(span.figure)}` : null;
  const cell = span.cell != null ? `cell ${String(span.cell)}` : null;
  const range = rangeLabel(span.bars);
  const head = figure ?? cell;
  if (!head && !range) return null;
  return [head, range].filter(Boolean).join(' · ');
}

/**
 * The backend's plan shape is workstream B's contract. Handle the two likely
 * spellings (a list of `[figure, bars]` tuples or `{figure|cell, bars}` objects)
 * and fall back to pretty JSON for anything else.
 */
export function planLines(plan: unknown, limit = 48): string[] {
  if (plan == null) return [];
  if (Array.isArray(plan)) {
    if (plan.length === 0) return [];
    const lines = plan.map((span) => spanLine(span) ?? compactJson(span));
    if (lines.length <= limit) return lines;
    return [...lines.slice(0, limit), `… ${lines.length - limit} more spans`];
  }
  return valueLines(plan, limit);
}

const NOTE_KEYS = ['pitch', 'name', 'note', 'midi', 'bar', 'beat', 'duration', 'voice', 'string', 'fret'];

function noteLine(note: unknown): string {
  if (typeof note === 'string') return note;
  if (typeof note === 'number') return String(note);
  if (!isRecord(note)) return compactJson(note);

  const bar = note.bar != null ? `bar ${String(note.bar)}` : null;
  const beat = note.beat != null ? `beat ${String(note.beat)}` : null;
  const pitch =
    note.pitch != null
      ? String(note.pitch)
      : note.name != null
        ? String(note.name)
        : note.note != null
          ? String(note.note)
          : note.midi != null
            ? `MIDI ${String(note.midi)}`
            : null;
  const duration = note.duration != null ? `dur ${String(note.duration)}` : null;
  const voice = note.voice != null ? `v${String(note.voice)}` : null;
  const position =
    note.string != null && note.fret != null
      ? `s${String(note.string)}f${String(note.fret)}`
      : null;

  const known = [bar, beat, pitch, duration, voice, position].filter(Boolean);
  if (known.length) return known.join(' · ');

  const extras = NOTE_KEYS.filter((key) => note[key] != null);
  return extras.length ? extras.map((key) => `${key} ${compactJson(note[key])}`).join(' · ') : compactJson(note);
}

/** Compact, human-readable note rows for the preview panel. */
export function notesLines(notes: unknown, limit = 24): string[] {
  if (notes == null) return [];
  const value =
    isRecord(notes) && Array.isArray(notes.events) ? notes.events : notes;
  if (Array.isArray(value)) {
    if (value.length === 0) return [];
    const lines = value.map(noteLine);
    if (lines.length <= limit) return lines;
    return [...lines.slice(0, limit), `… ${lines.length - limit} more notes`];
  }
  if (typeof value === 'string') return value.split('\n');
  return valueLines(value, limit);
}

/* ------------------------------------------------------------------------- *
 * Phase 1 front half: access, upload, Gemini draft.
 * ------------------------------------------------------------------------- */

export type ConfidenceBand = 'high' | 'medium' | 'low' | 'unknown';

/** Confidence colour buckets used by the notes table. */
export function confidenceBand(value: number | null | undefined): ConfidenceBand {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'unknown';
  if (value >= 0.85) return 'high';
  if (value >= 0.6) return 'medium';
  return 'low';
}

/** `0.91` -> `91%`; missing -> `—`. */
export function confidenceLabel(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return '—';
  return `${Math.round(Math.min(1, value) * 100)}%`;
}

export function accessReasonLabel(reason: string): string {
  switch (reason) {
    case 'open_beta':
      return 'Open beta';
    case 'entitled':
      return 'Entitled';
    case 'disabled':
      return 'Disabled';
    case 'unknown':
      return 'Unknown';
    default:
      return reason || 'Unknown';
  }
}

/** One-line header indicator; quota is omitted when the server sends zeroes. */
export function accessSummary(access: StudioAccess): string {
  if (!access.enabled) {
    return `Studio disabled · ${accessReasonLabel(access.reason)}`;
  }
  const parts = [accessReasonLabel(access.reason)];
  if (access.quota.uploadsPerDay > 0) {
    parts.push(`${access.quota.uploadsPerDay} uploads/day`);
  }
  if (access.quota.maxImageMb > 0) {
    parts.push(`max ${access.quota.maxImageMb} MB`);
  }
  return parts.join(' · ');
}

/** `912` -> `912 B`, `2048` -> `2 KB`, `1.4 MB`. */
export function byteSizeLabel(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '—';
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Client-side guard before a multipart upload; null when the file fits. */
export function imageSizeError(bytes: number, maxImageMb: number): string | null {
  if (!Number.isFinite(maxImageMb) || maxImageMb <= 0) return null;
  const limit = maxImageMb * 1024 * 1024;
  if (!Number.isFinite(bytes) || bytes <= 0) return null;
  if (bytes <= limit) return null;
  return `Ảnh ${byteSizeLabel(bytes)} vượt giới hạn ${maxImageMb} MB.`;
}

/** `score.png · 900×420 · sha 1a2b3c4d5e…` */
export function uploadMetaLabel(upload: StudioUpload): string {
  const parts: string[] = [];
  const name = upload.filename ?? upload.id;
  if (name) parts.push(name);
  if (upload.width != null && upload.height != null) {
    parts.push(`${upload.width}×${upload.height}`);
  }
  if (upload.sha256) parts.push(`sha ${shortId(upload.sha256, 10)}`);
  return parts.join(' · ');
}

/* ------------------------------------------------------------------------- *
 * Web crop rectangle.
 *
 * The UI works in source-image pixels; the stage is CSS pixels. Convert only
 * at the pointer boundary so every clamp/serialize value matches what Gemini
 * receives. A crop is always tied to an upload id: a stale rectangle is never
 * sent with a different image.
 * ------------------------------------------------------------------------- */

export type CropPoint = { x: number; y: number };
export type CropBounds = { width: number; height: number };
export type CropHandle = 'nw' | 'ne' | 'sw' | 'se';
export type CropTarget = CropHandle | 'inside';

/** Committed crop tied to the upload it was drawn on. */
export type CropSelection = { uploadId: string; rect: CropRect };

/** Image content box inside a fixed-size stage (object-fit: contain). */
export type DisplayRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

function clampNumber(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function pixel(value: number, max: number): number {
  if (!Number.isFinite(value)) return 0;
  return clampNumber(Math.round(value), 0, max);
}

function boundsSize(bounds: CropBounds): CropBounds {
  return {
    width: Number.isFinite(bounds.width) ? Math.max(0, Math.round(bounds.width)) : 0,
    height: Number.isFinite(bounds.height) ? Math.max(0, Math.round(bounds.height)) : 0,
  };
}

/** Clamp a rectangle to `bounds` on the pixel grid. Size may be zero. */
export function clampCropRect(rect: CropRect, bounds: CropBounds): CropRect {
  const { width, height } = boundsSize(bounds);
  const w = pixel(rect.w, width);
  const h = pixel(rect.h, height);
  return {
    x: clampNumber(pixel(rect.x, width), 0, width - w),
    y: clampNumber(pixel(rect.y, height), 0, height - h),
    w,
    h,
  };
}

/**
 * Clamp, round, and enforce the minimum size. Returns null for a non-finite
 * rectangle, empty bounds, or a selection smaller than `MIN_CROP_SIZE`.
 */
export function normalizeCropRect(
  rect: CropRect,
  bounds: CropBounds,
  minSize: number = MIN_CROP_SIZE,
): CropRect | null {
  if (![rect.x, rect.y, rect.w, rect.h].every(Number.isFinite)) return null;
  const { width, height } = boundsSize(bounds);
  if (width <= 0 || height <= 0) return null;
  const clamped = clampCropRect(rect, bounds);
  const min = Number.isFinite(minSize) && minSize > 0 ? Math.round(minSize) : MIN_CROP_SIZE;
  if (clamped.w < min || clamped.h < min) return null;
  return clamped;
}

/** Rectangle between two drag points; corner may cross the anchor. */
export function cropRectBetween(
  anchor: CropPoint,
  point: CropPoint,
  bounds: CropBounds,
): CropRect {
  const { width, height } = boundsSize(bounds);
  const ax = pixel(anchor.x, width);
  const ay = pixel(anchor.y, height);
  const bx = pixel(point.x, width);
  const by = pixel(point.y, height);
  return clampCropRect(
    {
      x: Math.min(ax, bx),
      y: Math.min(ay, by),
      w: Math.abs(bx - ax),
      h: Math.abs(by - ay),
    },
    bounds,
  );
}

/** Translate a crop, keeping the rectangle fully inside the image. */
export function moveCropRect(
  rect: CropRect,
  dx: number,
  dy: number,
  bounds: CropBounds,
): CropRect {
  return clampCropRect(
    {
      ...rect,
      x: rect.x + (Number.isFinite(dx) ? dx : 0),
      y: rect.y + (Number.isFinite(dy) ? dy : 0),
    },
    bounds,
  );
}

/** Resize by one corner; dragging past the opposite edge flips the box. */
export function resizeCropRect(
  rect: CropRect,
  handle: CropHandle,
  dx: number,
  dy: number,
  bounds: CropBounds,
): CropRect {
  const left = rect.x;
  const top = rect.y;
  const right = rect.x + rect.w;
  const bottom = rect.y + rect.h;
  const west = handle === 'nw' || handle === 'sw';
  const north = handle === 'nw' || handle === 'ne';
  const moveX = Number.isFinite(dx) ? dx : 0;
  const moveY = Number.isFinite(dy) ? dy : 0;
  const anchorX = west ? right : left;
  const anchorY = north ? bottom : top;
  const movingX = (west ? left : right) + moveX;
  const movingY = (north ? top : bottom) + moveY;
  return cropRectBetween(
    { x: anchorX, y: anchorY },
    { x: movingX, y: movingY },
    bounds,
  );
}

/** Corner first, then interior. `tolerance` is in image pixels. */
export function cropHandleAt(
  rect: CropRect,
  point: CropPoint,
  tolerance = 10,
): CropTarget | null {
  const tol = Number.isFinite(tolerance) && tolerance >= 0 ? tolerance : 10;
  const near = (x: number, y: number) =>
    Math.abs(point.x - x) <= tol && Math.abs(point.y - y) <= tol;
  if (near(rect.x, rect.y)) return 'nw';
  if (near(rect.x + rect.w, rect.y)) return 'ne';
  if (near(rect.x, rect.y + rect.h)) return 'sw';
  if (near(rect.x + rect.w, rect.y + rect.h)) return 'se';
  if (
    point.x >= rect.x &&
    point.x <= rect.x + rect.w &&
    point.y >= rect.y &&
    point.y <= rect.y + rect.h
  ) {
    return 'inside';
  }
  return null;
}

/** `900 × 420 px` */
export function cropSizeLabel(rect: CropRect): string {
  return `${Math.round(rect.w)} × ${Math.round(rect.h)} px`;
}

/** The crop to send for `uploadId`; null when it belongs to another image. */
export function cropForUpload(
  crop: CropSelection | null | undefined,
  uploadId: string | null | undefined,
): CropRect | null {
  if (!crop || !uploadId || crop.uploadId !== uploadId) return null;
  return crop.rect;
}

/** Fit `image` inside `stage` with letterboxing, like `resizeMode="contain"`. */
export function containRect(image: CropBounds, stage: CropBounds): DisplayRect {
  if (
    !(image.width > 0) ||
    !(image.height > 0) ||
    !(stage.width > 0) ||
    !(stage.height > 0)
  ) {
    return { left: 0, top: 0, width: 0, height: 0 };
  }
  const scale = Math.min(stage.width / image.width, stage.height / image.height);
  const width = image.width * scale;
  const height = image.height * scale;
  return {
    left: (stage.width - width) / 2,
    top: (stage.height - height) / 2,
    width,
    height,
  };
}

export function noteBarLabel(note: StudioAnalysisNote): string {
  const value = note.bar ?? note.measure;
  return value == null ? '—' : String(value);
}

export function noteBeatLabel(note: StudioAnalysisNote): string {
  if (note.beat == null || !Number.isFinite(note.beat)) return '—';
  return Number.isInteger(note.beat) ? String(note.beat) : note.beat.toFixed(2);
}

export function noteVoiceLabel(note: StudioAnalysisNote): string {
  return note.voiceHint ?? '—';
}

/** Written pitch with the sounding pitch when they differ (guitar octave). */
export function notePitchLabel(note: StudioAnalysisNote): string {
  const written = note.writtenPitch;
  const sounding = note.soundingPitch;
  if (written && sounding && written !== sounding) return `${written} (${sounding})`;
  return written ?? sounding ?? '—';
}

/** `s1f5`; empty when the draft has no tab position. */
export function notePositionLabel(note: StudioAnalysisNote): string {
  if (note.string == null || note.fret == null) return '';
  return `s${note.string}f${note.fret}`;
}

export type DraftNoteRow = {
  index: number;
  bar: string;
  beat: string;
  voice: string;
  pitch: string;
  position: string;
  confidence: string;
  band: ConfidenceBand;
  conflict: boolean;
  review: string;
};

/** Rows for the compact draft table; capped so one huge page stays usable. */
export function draftNoteRows(
  notes: readonly StudioAnalysisNote[],
  limit = 40,
): DraftNoteRow[] {
  return notes.slice(0, limit).map((note, index) => ({
    index,
    bar: noteBarLabel(note),
    beat: noteBeatLabel(note),
    voice: noteVoiceLabel(note),
    pitch: notePitchLabel(note),
    position: notePositionLabel(note),
    confidence: confidenceLabel(note.confidence),
    band: confidenceBand(note.confidence),
    conflict: note.conflict,
    review: note.review ?? '—',
  }));
}

/** `m1 · 3/4 · A minor` rows for the draft header; capped like the note table. */
export function measureLines(
  measures: StudioAnalyzeDraft['measures'],
  limit = 12,
): string[] {
  const lines = measures.slice(0, limit).map((measure, index) => {
    const label =
      measure.index != null ? `m${measure.index}` : `m${index + 1}`;
    return [label, measure.meter, measure.key].filter(Boolean).join(' · ');
  });
  if (measures.length <= limit) return lines;
  return [...lines, `… ${measures.length - limit} more measures`];
}

/**
 * The draft is a TextureSpec note list, not a SentenceSpec, so it is copied as
 * JSON instead of replacing the editor contents.
 */
export function draftJson(draft: StudioAnalyzeDraft): string {
  const notes = draft.notes.map((note) => {
    const row: Record<string, unknown> = {};
    const put = (key: string, value: unknown) => {
      if (value !== null && value !== undefined && value !== '') row[key] = value;
    };
    put('measure', note.measure);
    put('bar', note.bar);
    put('beat', note.beat);
    put('duration_beats', note.durationBeats);
    put('voice_hint', note.voiceHint);
    put('written_pitch', note.writtenPitch);
    put('sounding_pitch', note.soundingPitch);
    put('string', note.string);
    put('fret', note.fret);
    put('confidence', note.confidence);
    if (note.conflict) row.conflict = true;
    put('review', note.review ?? 'pending');
    put('tie', note.tie);
    if (note.articulation.length) row.articulation = note.articulation;
    return row;
  });
  return JSON.stringify(
    {
      measures: draft.measures,
      notes,
      warnings: draft.warnings,
      review: draft.review ?? 'pending',
    },
    null,
    2,
  );
}

