import type { StudioError } from './protocol';

/**
 * Pure helpers for the sentence Studio. Nothing here talks to the network.
 *
 * The editor edits **one spec mapping** (the object inside Workstream A's
 * `{ schema_version: 1, runtime: "code", specs: [...] }` wrapper), which is the
 * body `POST /studio/sentence/validate` expects. The wrapper is added by the
 * compile/publish path later, not by this screen.
 */

export type PatternId = 'castillo' | 'sonatina' | 'fandanguillo' | 'danza' | 'galop';

export type PatternOption = {
  id: PatternId;
  label: string;
  composer: 'Torroba' | 'Sor';
  meters: string[];
};

export const ANY_METER = '*';

/** Canonical meter key `*` is the backend's wildcard (SentenceSpec.meter). */
export const PATTERNS: PatternOption[] = [
  { id: 'castillo', label: 'Castillo', composer: 'Torroba', meters: ['3/4', '4/4'] },
  { id: 'sonatina', label: 'Sonatina', composer: 'Torroba', meters: [ANY_METER] },
  { id: 'fandanguillo', label: 'Fandanguillo', composer: 'Torroba', meters: [ANY_METER] },
  { id: 'danza', label: 'Danza', composer: 'Torroba', meters: ['3/4', '6/8'] },
  { id: 'galop', label: 'Galop', composer: 'Sor', meters: [ANY_METER] },
];

export function patternOption(pattern: string): PatternOption | undefined {
  return PATTERNS.find((item) => item.id === pattern);
}

export function meterLabel(meter: string): string {
  return meter === ANY_METER ? 'any meter' : meter;
}

export type StudioSample = {
  /** Stable key, also used as the picker value. `pattern:meter`. */
  key: string;
  pattern: PatternId;
  meter: string;
  title: string;
  spec: Record<string, unknown>;
  fixture: Record<string, unknown>;
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

export function samplesForPattern(pattern: string): StudioSample[] {
  return SAMPLES.filter((sample) => sample.pattern === pattern);
}

export function defaultSampleForPattern(pattern: string): StudioSample {
  return samplesForPattern(pattern)[0] ?? DEFAULT_SAMPLE;
}

export function findSample(pattern: string, meter: string): StudioSample | undefined {
  return SAMPLES.find((sample) => sample.pattern === pattern && sample.meter === meter);
}

export function sampleText(sample: StudioSample): string {
  return JSON.stringify(sample.spec, null, 2);
}

export function fixtureText(sample: StudioSample): string {
  return JSON.stringify(sample.fixture, null, 2);
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
      if (hasFigure === hasCell) {
        errors.push({
          path: `slots[${index}]`,
          message: 'needs exactly one of figure (number) or cell (non-empty string)',
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

