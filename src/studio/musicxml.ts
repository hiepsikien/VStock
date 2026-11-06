/**
 * Pure MusicXML import/passage model for Studio.
 *
 * This module knows nothing about React or the network. It turns the
 * `POST /v1/studio/import/musicxml` and `.../passage` payloads into a
 * rhythm-first role-lane matrix:
 *
 *   Lead = voice 1 (one cell per onset; more than one tone is a chord)
 *   Bass = the lowest sounding non-lead MIDI at each onset
 *   Mid  = every remaining non-lead note at that onset
 *
 * The matrix is deliberately pitch-blind: a cell carries its bar, tick span,
 * bead duration, chord count, tie and source voice, and every gap is filled by
 * an explicit rest cell. A note that crosses a barline is clipped to the bar
 * end; the UI never invents a tie.
 *
 * Meter layout is per-bar. `summary.measureMeters` is indexed from bar 1; when
 * it is missing, `summary.meter` (then `4/4`) is used for every bar. The
 * parallel backend work may also send `summary.meterChanges`, which is applied
 * as a fallback source of bar meters.
 *
 * Contract seam:
 *
 *   POST /v1/studio/import/musicxml              multipart `file`
 *     -> 201 { ok, importId, filename, summary, notes, warnings }
 *   GET  /v1/studio/import/musicxml/{importId}   -> same
 *   POST /v1/studio/import/musicxml/{id}/passage
 *     body { barStart, beatStart, barEnd, beatEnd, voices? }
 *     -> { ok, passageId, meter, beatsPerBar, bpm, spec, notes,
 *          audioUrl, durationSec, warnings, errors }
 *
 * Importer notes are 0-based bars; passage notes are 0-based relative to
 * `barStart`. Bars in a passage *request* are 1-based and inclusive. Beats are
 * quarter-note offsets inside their bar; `beatEnd` is exclusive and an omitted
 * `beatEnd` means the end of `barEnd`.
 */

import {
  isRecord,
  normalizeErrors,
  resolveAudioUrl,
  type StudioError,
} from './protocol';

/** One quarter note. The Studio velocity lane already uses this grid. */
export const TICKS_PER_QUARTER = 24;

/** Layout-only fallback when neither measureMeters nor meter is usable. */
export const DEFAULT_METER = '4/4';

/** Meters the passage preview can synthesize (1/4 and 2/4 are per-bar aware). */
const SUPPORTED_METERS = new Set(['1/4', '2/4', '3/4', '4/4', '6/8']);

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function finite(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function integer(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) ? value : null;
}

function booleanFlag(value: unknown): boolean {
  return value === true || value === 'true' || value === 1;
}

function nonNegative(value: unknown, fallback = 0): number {
  const number = finite(value);
  return number == null || number < 0 ? fallback : number;
}

function warningList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    const single = text(value);
    return single ? [single] : [];
  }
  return value
    .map((item) =>
      isRecord(item) ? text(item.message) ?? text(item.msg) : text(item),
    )
    .filter((item): item is string => item !== null);
}

/* ------------------------------------------------------------------------- *
 * Meter
 * ------------------------------------------------------------------------- */

export type MeterParts = {
  numerator: number;
  denominator: number;
};

/** Parse `"6/8"` / `" 6 / 8 "`; null for anything that is not two integers. */
export function parseMeter(value: unknown): MeterParts | null {
  const raw = text(value);
  if (!raw) return null;
  const match = /^(\d+)\s*\/\s*(\d+)$/.exec(raw);
  if (!match) return null;
  const numerator = Number(match[1]);
  const denominator = Number(match[2]);
  if (!Number.isInteger(numerator) || !Number.isInteger(denominator)) return null;
  if (numerator <= 0 || denominator <= 0) return null;
  return { numerator, denominator };
}

/** Canonical `"6/8"` spelling, or null when the value is not a meter. */
export function normalizeMeterText(value: unknown): string | null {
  const parsed = parseMeter(value);
  return parsed ? `${parsed.numerator}/${parsed.denominator}` : null;
}

/** Quarter notes in one bar: `6/8` -> 3, `4/4` -> 4. */
export function meterQuarterBeats(meter: unknown): number {
  const parsed = parseMeter(meter);
  if (!parsed) return 0;
  return (parsed.numerator * 4) / parsed.denominator;
}

/** Tick length of one bar: `1/4` -> 24, `6/8` -> 72. */
export function meterTicks(meter: unknown): number {
  return meterQuarterBeats(meter) * TICKS_PER_QUARTER;
}

/** Meters accepted by the current passage synth contract. */
export function isSupportedMeter(meter: unknown): boolean {
  const normalized = normalizeMeterText(meter);
  return normalized != null && SUPPORTED_METERS.has(normalized);
}

/**
 * Conventional pulse groups.
 *
 * Compound/duple bars are counted in eighths, simple bars in quarters:
 * `6/8` -> `[3, 3]`, `4/4` -> `[4, 4]`, `3/4` -> `[3]`, `2/4` -> `[2]`,
 * `1/4` -> `[1]`. `meterGroupTicks()` scales these proportions onto the real
 * bar length, so a consumer never has to know which unit was used.
 */
export function meterGroups(meter: unknown): number[] {
  const parsed = parseMeter(meter);
  if (!parsed) return [];
  const { numerator, denominator } = parsed;
  if (denominator === 8 && numerator === 6) return [3, 3];
  if (denominator === 4 && numerator === 4) return [4, 4];
  return [numerator];
}

/**
 * Group spans in ticks. The proportions from `meterGroups()` are scaled onto
 * `meterTicks(meter)`, so `6/8` is `[36, 36]` and `4/4` is `[48, 48]`.
 */
export function meterGroupTicks(meter: unknown): number[] {
  const groups = meterGroups(meter);
  const total = meterTicks(meter);
  if (!groups.length || total <= 0) return [];
  const sum = groups.reduce((acc, value) => acc + value, 0);
  if (sum <= 0) return [];
  const unit = total / sum;
  return groups.map((value) => value * unit);
}

/** Round a tick value to a stable beat label (6 decimals, like velocity.ts). */
export function ticksToBeats(ticks: number): number {
  return Math.round((ticks / TICKS_PER_QUARTER) * 1_000_000) / 1_000_000;
}

/* ------------------------------------------------------------------------- *
 * Imported notes / summary / response normalizers
 * ------------------------------------------------------------------------- */

export type MusicXmlImportedNote = {
  /** 0-based measure index, as returned by the importer. */
  bar: number;
  /** Quarter-note offset inside the bar. */
  beat: number;
  /** Quarter-note duration. */
  duration: number;
  voice: number;
  midi: number | null;
  writtenMidi: number | null;
  staff: number | null;
  /** `start` | `stop` | `continue` | `none`, or null when absent. */
  tie: string | null;
  /** `start` | `stop` | `continue` | `none`, or null when absent. */
  slur: string | null;
  rest: boolean;
  chord: boolean;
  accent: boolean;
  tenuto: boolean;
  staccato: boolean;
  writtenPitch: string | null;
  soundingPitch: string | null;
};

export type MusicXmlMeterChange = {
  /** 1-based bar where the new meter starts. */
  bar: number;
  meter: string;
};

export type MusicXmlImportSummary = {
  title: string;
  meter: string;
  meterSupported: boolean;
  measureCount: number;
  keyFifths: number;
  keyMode: string | null;
  tempo: number | null;
  noteCount: number;
  voices: number[];
  sourceHash: string;
  /** Index 0 is bar 1; null when the server did not send the field. */
  measureMeters: string[] | null;
  meterChanges: MusicXmlMeterChange[];
  warnings: string[];
};

export type MusicXmlImport = {
  ok: boolean;
  importId: string;
  filename: string;
  summary: MusicXmlImportSummary;
  notes: MusicXmlImportedNote[];
  warnings: string[];
  errors: StudioError[];
};

export type MusicXmlSynthNote = {
  /** 0-based, relative to the requested barStart. */
  bar: number;
  beat: number;
  duration: number;
  midi: number;
  voice: number;
  velocity: number | null;
  accent: boolean;
  staccato: boolean;
};

export type MusicXmlPassage = {
  ok: boolean;
  passageId: string;
  meter: string;
  beatsPerBar: number;
  /** Preview synth tempo; 96 when the backend does not send one. */
  bpm: number;
  spec: Record<string, unknown> | null;
  notes: MusicXmlSynthNote[];
  /** Resolved against the API base when one was supplied to the normalizer. */
  audioUrl: string | null;
  durationSec: number;
  warnings: string[];
  errors: StudioError[];
};

function tieName(value: Record<string, unknown>): string | null {
  const named = text(value.tie);
  if (named) return named.toLowerCase();
  const start = booleanFlag(value.tie_start ?? value.tieStart);
  const stop = booleanFlag(value.tie_stop ?? value.tieStop);
  if (start && stop) return 'continue';
  if (start) return 'start';
  if (stop) return 'stop';
  return null;
}

function slurName(value: Record<string, unknown>): string | null {
  const named = text(value.slur);
  if (named) return named.toLowerCase();
  const start = booleanFlag(value.slur_start ?? value.slurStart);
  const stop = booleanFlag(value.slur_stop ?? value.slurStop);
  if (start && stop) return 'continue';
  if (start) return 'start';
  if (stop) return 'stop';
  return null;
}

function midiValue(value: unknown): number | null {
  const number = finite(value);
  if (number == null) return null;
  const rounded = Math.round(number);
  return rounded >= 0 && rounded <= 127 ? rounded : null;
}

export function normalizeMusicXmlNote(value: unknown): MusicXmlImportedNote | null {
  if (!isRecord(value)) return null;
  const bar = integer(value.bar);
  if (bar == null) return null;
  const beat = nonNegative(value.beat);
  const duration = nonNegative(value.duration);
  const voice = Math.max(1, Math.trunc(finite(value.voice) ?? 1));
  const midi = midiValue(value.midi);
  const writtenMidi = midiValue(value.written_midi ?? value.writtenMidi);
  const writtenPitch =
    text(value.written_pitch) ?? text(value.writtenPitch) ?? null;
  const soundingPitch =
    text(value.sounding_pitch) ?? text(value.soundingPitch) ?? null;
  const rest =
    booleanFlag(value.rest) ||
    (midi == null && writtenMidi == null && writtenPitch == null);
  const staff = finite(value.staff);

  return {
    bar: Math.max(0, bar),
    beat,
    duration,
    voice,
    midi,
    writtenMidi,
    staff: staff == null ? null : Math.trunc(staff),
    tie: tieName(value),
    slur: slurName(value),
    rest,
    chord: booleanFlag(value.chord),
    accent: booleanFlag(value.accent),
    tenuto: booleanFlag(value.tenuto),
    staccato: booleanFlag(value.staccato),
    writtenPitch,
    soundingPitch,
  };
}

function normalizeMeterChanges(value: unknown): MusicXmlMeterChange[] {
  if (!Array.isArray(value)) return [];
  const changes: MusicXmlMeterChange[] = [];
  const seen = new Set<number>();
  for (const item of value) {
    if (!isRecord(item)) continue;
    const meter = normalizeMeterText(item.meter ?? item.value);
    const bar = integer(item.bar ?? item.measure ?? item.index);
    if (!meter || bar == null || bar < 1 || seen.has(bar)) continue;
    seen.add(bar);
    changes.push({ bar, meter });
  }
  return changes.sort((left, right) => left.bar - right.bar);
}

function normalizeMeasureMeters(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  return value.map((item) => {
    if (isRecord(item)) {
      return (
        normalizeMeterText(item.meter ?? item.value) ??
        normalizeMeterText(item)
      );
    }
    return normalizeMeterText(item);
  }).map((item) => item ?? '');
}

function voiceList(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  const voices = new Set<number>();
  for (const item of value) {
    const voice = finite(item);
    if (voice == null) continue;
    const rounded = Math.trunc(voice);
    if (rounded >= 1 && rounded <= 4) voices.add(rounded);
  }
  return [...voices].sort((left, right) => left - right);
}

export function normalizeMusicXmlSummary(
  value: unknown,
  fallbackTitle = '',
): MusicXmlImportSummary {
  const raw = isRecord(value) ? value : {};
  const meter = normalizeMeterText(raw.meter) ?? '';
  const measureMeters = normalizeMeasureMeters(
    raw.measureMeters ?? raw.measure_meters,
  );
  const meterChanges = normalizeMeterChanges(
    raw.meterChanges ?? raw.meter_changes,
  );
  const declaredMeasures = nonNegative(
    integer(raw.measureCount ?? raw.measure_count) ?? 0,
  );
  // A per-bar list is more authoritative than a stale count.
  const measureCount = Math.max(
    Math.trunc(declaredMeasures),
    measureMeters?.length ?? 0,
    meterChanges.reduce((max, change) => Math.max(max, change.bar), 0),
  );
  const keyFifths = Math.trunc(
    finite(raw.keyFifths ?? raw.key_fifths) ?? 0,
  );
  const tempo = finite(raw.tempo ?? raw.bpm);
  const meterSupported =
    typeof raw.meterSupported === 'boolean'
      ? raw.meterSupported
      : typeof raw.meter_supported === 'boolean'
        ? raw.meter_supported
        : isSupportedMeter(meter);
  const keyMode = text(raw.keyMode ?? raw.key_mode);

  return {
    title: text(raw.title) ?? fallbackTitle,
    meter,
    meterSupported,
    measureCount,
    keyFifths,
    keyMode: keyMode ? keyMode.toLowerCase() : null,
    tempo: tempo != null && tempo > 0 ? tempo : null,
    noteCount: Math.trunc(nonNegative(raw.noteCount ?? raw.note_count)),
    voices: voiceList(raw.voices),
    sourceHash: text(raw.sourceHash ?? raw.source_hash) ?? '',
    measureMeters,
    meterChanges,
    warnings: warningList(raw.warnings),
  };
}

/** Tolerant import normalizer: snake_case and a missing summary both survive. */
export function normalizeMusicXmlImport(value: unknown): MusicXmlImport {
  if (!isRecord(value)) {
    throw new Error('MusicXML import API returned a non-object response.');
  }
  const summaryRaw = isRecord(value.summary) ? value.summary : value;
  const filename = text(value.filename) ?? text(summaryRaw.filename) ?? '';
  const summary = normalizeMusicXmlSummary(summaryRaw, filename);
  const notes = Array.isArray(value.notes)
    ? value.notes
        .map(normalizeMusicXmlNote)
        .filter((note): note is MusicXmlImportedNote => note !== null)
    : [];
  const sounding = notes.filter((note) => !note.rest && note.midi != null);
  const voices = new Set(summary.voices);
  for (const note of sounding) voices.add(note.voice);
  summary.voices = [...voices].sort((left, right) => left - right);
  if (summary.noteCount === 0) summary.noteCount = sounding.length;
  if (summary.measureCount === 0 && notes.length) {
    summary.measureCount =
      notes.reduce((max, note) => Math.max(max, note.bar), 0) + 1;
  }

  const importId = text(value.importId ?? value.import_id) ?? '';
  const errors = normalizeErrors(value);
  return {
    ok: typeof value.ok === 'boolean' ? value.ok : Boolean(importId),
    importId,
    filename,
    summary,
    notes,
    warnings: warningList(value.warnings),
    errors,
  };
}

function normalizeSynthNote(value: unknown): MusicXmlSynthNote | null {
  if (!isRecord(value)) return null;
  const bar = integer(value.bar);
  const midi = midiValue(value.midi);
  if (bar == null || midi == null) return null;
  return {
    bar: Math.max(0, bar),
    beat: nonNegative(value.beat),
    duration: nonNegative(value.duration),
    midi,
    voice: Math.max(1, Math.trunc(finite(value.voice) ?? 1)),
    velocity: finite(value.velocity),
    accent: booleanFlag(value.accent),
    staccato: booleanFlag(value.staccato),
  };
}

/**
 * Tolerant passage normalizer. The current backend omits `meter`/`beatsPerBar`
 * on some responses; those stay empty/zero and the panel falls back to the
 * selected bar layout. Audio URLs stay relative unless `baseUrl` is supplied.
 */
export function normalizeMusicXmlPassage(
  value: unknown,
  baseUrl?: string | null,
): MusicXmlPassage {
  if (!isRecord(value)) {
    throw new Error('MusicXML passage API returned a non-object response.');
  }
  const meter = normalizeMeterText(value.meter ?? value.passageMeter) ?? '';
  const beats = finite(value.beatsPerBar ?? value.beats_per_bar);
  const bpmValue = finite(value.bpm ?? value.tempo);
  const audio = text(value.audioUrl ?? value.audio_url);
  const notes = Array.isArray(value.notes)
    ? value.notes
        .map(normalizeSynthNote)
        .filter((note): note is MusicXmlSynthNote => note !== null)
    : [];
  const errors = normalizeErrors(value);
  const audioUrl = audio
    ? resolveAudioUrl(baseUrl ?? '', audio)
    : null;

  return {
    ok:
      typeof value.ok === 'boolean'
        ? value.ok
        : (audioUrl != null || isRecord(value.spec)) && errors.length === 0,
    passageId: text(value.passageId ?? value.passage_id) ?? '',
    meter,
    beatsPerBar:
      beats != null && beats > 0
        ? beats
        : meter
          ? meterQuarterBeats(meter)
          : 0,
    bpm: bpmValue != null && bpmValue > 0 ? bpmValue : 96,
    spec: isRecord(value.spec) ? value.spec : null,
    notes,
    audioUrl,
    durationSec: nonNegative(value.durationSec ?? value.duration_sec),
    warnings: warningList(value.warnings),
    errors,
  };
}

/* ------------------------------------------------------------------------- *
 * Per-bar layout and ruler
 * ------------------------------------------------------------------------- */

export type MusicXmlBarLayout = {
  /** 1-based bar number. */
  bar: number;
  meter: string;
  quarterBeats: number;
  ticks: number;
};

export type MusicXmlGridBar = MusicXmlBarLayout & {
  /** Absolute tick offset from the start of the score. */
  startTick: number;
  /** True on bar 1 and whenever the meter differs from the previous bar. */
  meterStart: boolean;
  /** Pulse group spans in ticks, scaled onto this bar. */
  groups: number[];
  /** Group starts relative to the bar, always beginning with 0. */
  beatTicks: number[];
};

export type MusicXmlGrid = {
  bars: MusicXmlGridBar[];
  totalTicks: number;
};

/**
 * Per-bar meters from `measureMeters` (index 0 = bar 1), falling back to
 * `meterChanges`, then `summary.meter`, then `4/4`. Missing entries inherit
 * the previous bar so a short list cannot produce a hole.
 */
export function barLayouts(
  summary: {
    meter?: string | null;
    measureCount?: number;
    measureMeters?: string[] | null;
    meterChanges?: readonly MusicXmlMeterChange[] | null;
  },
): MusicXmlBarLayout[] {
  const measureMeters = summary.measureMeters ?? null;
  const meterChanges = summary.meterChanges ?? [];
  const count = Math.max(
    0,
    Math.trunc(summary.measureCount ?? 0),
    measureMeters?.length ?? 0,
    meterChanges.reduce((max, change) => Math.max(max, change.bar), 0),
  );
  if (count === 0) return [];

  const meterAtChange = new Map<number, string>();
  for (const change of meterChanges) {
    meterAtChange.set(change.bar, change.meter);
  }
  const fallback = normalizeMeterText(summary.meter) ?? DEFAULT_METER;

  let previous = fallback;
  const layouts: MusicXmlBarLayout[] = [];
  for (let index = 0; index < count; index += 1) {
    const bar = index + 1;
    const explicit =
      normalizeMeterText(measureMeters?.[index]) ??
      meterAtChange.get(bar) ??
      previous;
    const meter = normalizeMeterText(explicit) ?? previous;
    previous = meter;
    const quarterBeats = meterQuarterBeats(meter) || 4;
    layouts.push({
      bar,
      meter,
      quarterBeats,
      ticks: quarterBeats * TICKS_PER_QUARTER,
    });
  }
  return layouts;
}

/** Deterministic ruler: absolute bar starts, meter starts, beat groups. */
export function musicXmlGrid(
  bars: readonly MusicXmlBarLayout[],
): MusicXmlGrid {
  let startTick = 0;
  let previousMeter: string | null = null;
  const gridBars = bars.map((bar) => {
    const groups = meterGroupTicks(bar.meter);
    const beatTicks: number[] = [];
    let cursor = 0;
    for (const group of groups) {
      beatTicks.push(cursor);
      cursor += group;
    }
    const row: MusicXmlGridBar = {
      ...bar,
      startTick,
      meterStart: previousMeter !== bar.meter,
      groups,
      beatTicks,
    };
    previousMeter = bar.meter;
    startTick += bar.ticks;
    return row;
  });
  return { bars: gridBars, totalTicks: startTick };
}

/** `1/4 → 2/4 at bar 2` for the summary card and matrix legend. */
export function meterChangeLabel(
  bars: readonly MusicXmlBarLayout[],
): string {
  if (bars.length === 0) return 'no meter';
  const parts: string[] = [];
  let previous: string | null = null;
  for (const bar of bars) {
    if (previous == null) {
      parts.push(bar.meter);
    } else if (bar.meter !== previous) {
      parts.push(`${bar.meter} at bar ${bar.bar}`);
    }
    previous = bar.meter;
  }
  return parts.join(' → ');
}

const MAJOR_KEYS = [
  'C',
  'G',
  'D',
  'A',
  'E',
  'B',
  'F#',
  'C#',
] as const;
const MINOR_KEYS = [
  'A',
  'E',
  'B',
  'F#',
  'C#',
  'G#',
  'D#',
  'A#',
] as const;

function keyName(fifths: number, mode: string | null): string | null {
  const minor = mode === 'minor';
  const table = minor ? MINOR_KEYS : MAJOR_KEYS;
  if (fifths >= 0) {
    const name = table[fifths];
    return name ? `${name} ${minor ? 'minor' : 'major'}` : null;
  }
  const flatTables: Record<string, readonly string[]> = {
    major: ['C', 'F', 'Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb'],
    minor: ['A', 'D', 'G', 'C', 'F', 'Bb', 'Eb', 'Ab'],
  };
  const name = flatTables[minor ? 'minor' : 'major'][-fifths];
  return name ? `${name} ${minor ? 'minor' : 'major'}` : null;
}

/** `D major · 2#` / `A minor · 0`; free of locale formatting. */
export function keySignatureLabel(summary: MusicXmlImportSummary): string {
  const fifths = Math.trunc(summary.keyFifths);
  const accidental =
    fifths === 0 ? '0' : fifths > 0 ? `${fifths}#` : `${-fifths}b`;
  const name = keyName(fifths, summary.keyMode);
  return name ? `${name} · ${accidental}` : `${fifths} fifths`;
}

/* ------------------------------------------------------------------------- *
 * Passage range
 * ------------------------------------------------------------------------- */

export type PassageRange = {
  /** 1-based and inclusive, matching the API request. */
  barStart: number;
  /** Quarter-note offset inside `barStart`; 0 is the first beat. */
  beatStart: number;
  /** 1-based and inclusive, matching the API request. */
  barEnd: number;
  /** Quarter-note offset inside `barEnd`; exclusive. */
  beatEnd: number;
};

export type PassageRangeValidation = {
  ok: boolean;
  errors: string[];
  mixedMeter: boolean;
  meters: string[];
};

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(max, Math.max(min, value));
}

function roundTick(value: number): number {
  return Math.round(value * 1_000_000) / 1_000_000;
}

/** Round to the nearest quarter note (24 ticks), never below zero. */
export function snapTick(tick: number): number {
  if (!Number.isFinite(tick) || tick <= 0) return 0;
  return Math.round(tick / TICKS_PER_QUARTER) * TICKS_PER_QUARTER;
}

/** Display a beat offset as a 1-based musical beat (`0` -> `1.0`). */
export function passageBeatLabel(beat: number): string {
  if (!Number.isFinite(beat)) return '—';
  const value = Math.round((beat + 1) * 1_000_000) / 1_000_000;
  const text = String(value);
  return text.includes('.') ? text : `${text}.0`;
}

/**
 * Display an exclusive end offset as the last included 1-based beat.
 * `2` (the end of a 2/4 bar) -> `2.0`, not `3.0`.
 */
export function passageEndBeatLabel(beatEnd: number): string {
  if (!Number.isFinite(beatEnd) || beatEnd <= 0) return '—';
  return passageBeatLabel(beatEnd - 1);
}

/**
 * First run of at least two bars in one meter, capped at four bars. A one-bar
 * opening run (e.g. a pickup 1/4 before the 2/4 body) is skipped so the
 * default lands on the stable body: Scottish -> bars 2..5, whole bars.
 */
export function defaultPassageRange(
  bars: readonly MusicXmlBarLayout[],
): PassageRange {
  if (bars.length === 0) {
    return { barStart: 1, beatStart: 0, barEnd: 1, beatEnd: 0 };
  }
  for (let index = 0; index < bars.length; index += 1) {
    if (index > 0 && bars[index].meter === bars[index - 1].meter) continue;
    let runEnd = index;
    while (
      runEnd + 1 < bars.length &&
      bars[runEnd + 1].meter === bars[index].meter
    ) {
      runEnd += 1;
    }
    // Never let the default window run past the end of this meter run into a
    // different meter; that range would be rejected by validation.
    const barEnd = Math.min(index + 4, runEnd + 1, bars.length);
    const range = {
      barStart: index + 1,
      beatStart: 0,
      barEnd,
      beatEnd: bars[barEnd - 1].quarterBeats,
    };
    if (runEnd - index + 1 >= 2) return range;
  }
  return {
    barStart: 1,
    beatStart: 0,
    barEnd: 1,
    beatEnd: bars[0].quarterBeats,
  };
}

/**
 * Absolute tick span for a range. Beats are clamped to their bar so a
 * half-typed number cannot paint outside the score.
 */
export function rangeTicks(
  grid: MusicXmlGrid,
  range: PassageRange,
): { startTick: number; endTick: number } {
  const bars = grid.bars;
  if (bars.length === 0) return { startTick: 0, endTick: 0 };
  const startIndex = clamp(Math.trunc(range.barStart) - 1, 0, bars.length - 1);
  const endIndex = clamp(Math.trunc(range.barEnd) - 1, 0, bars.length - 1);
  const startBar = bars[startIndex];
  const endBar = bars[endIndex];
  const startBeat = clamp(range.beatStart, 0, startBar.quarterBeats);
  const endBeat = clamp(range.beatEnd, 0, endBar.quarterBeats);
  return {
    startTick: roundTick(startBar.startTick + startBeat * TICKS_PER_QUARTER),
    endTick: roundTick(endBar.startTick + endBeat * TICKS_PER_QUARTER),
  };
}

function barContainingTick(
  grid: MusicXmlGrid,
  tick: number,
): MusicXmlGridBar {
  const bars = grid.bars;
  for (const bar of bars) {
    if (tick < bar.startTick + bar.ticks) return bar;
  }
  return bars[bars.length - 1];
}

/**
 * Normalize an absolute tick window into a bar/beat range. The window is
 * snapped to quarter notes and is always at least one quarter long, so the
 * inverse (`rangeTicks`) round-trips. `endTick` is exclusive: a window that
 * ends exactly at a barline is reported as the end of the previous bar.
 */
export function selectionFromTicks(
  grid: MusicXmlGrid,
  startTick: number,
  endTick: number,
): PassageRange {
  const bars = grid.bars;
  if (bars.length === 0) {
    return { barStart: 1, beatStart: 0, barEnd: 1, beatEnd: 0 };
  }
  const totalTicks = Math.max(TICKS_PER_QUARTER, grid.totalTicks);
  let start = clamp(snapTick(startTick), 0, totalTicks - TICKS_PER_QUARTER);
  let end = clamp(snapTick(endTick), start + TICKS_PER_QUARTER, totalTicks);
  if (start >= totalTicks) {
    start = Math.max(0, totalTicks - TICKS_PER_QUARTER);
    end = totalTicks;
  }
  start = Math.round(start);
  end = Math.round(end);
  const startBar = barContainingTick(grid, start);
  const endBar = barContainingTick(grid, Math.max(start, end - 1));
  return {
    barStart: startBar.bar,
    beatStart: roundTick((start - startBar.startTick) / TICKS_PER_QUARTER),
    barEnd: endBar.bar,
    beatEnd: roundTick((end - endBar.startTick) / TICKS_PER_QUARTER),
  };
}

/**
 * Reversed/out-of-range/mixed-meter/unsupported-meter and beat-bound checks
 * for the panel. Beats are quarter-note offsets; `beatEnd` is exclusive.
 */
export type SelectionEdge = 'start' | 'end';

/** Resize one selection edge to a snapped tick, keeping one quarter minimum. */
export function resizeSelectionTicks(
  grid: MusicXmlGrid,
  selection: { startTick: number; endTick: number },
  edge: SelectionEdge,
  pointerTick: number,
): { startTick: number; endTick: number } {
  const total = Math.max(TICKS_PER_QUARTER, grid.totalTicks);
  const tick = Math.min(total, Math.max(0, snapTick(pointerTick)));
  if (edge === 'start') {
    const end = Math.min(total, Math.max(selection.endTick, TICKS_PER_QUARTER));
    return {
      startTick: Math.min(tick, end - TICKS_PER_QUARTER),
      endTick: end,
    };
  }
  const start = Math.max(0, Math.min(selection.startTick, total - TICKS_PER_QUARTER));
  return {
    startTick: start,
    endTick: Math.max(start + TICKS_PER_QUARTER, Math.min(total, tick)),
  };
}

/** Bars completely covered by a tick span; partial bars are not full highlights. */
export function fullySelectedBars(
  bars: readonly MusicXmlGridBar[],
  startTick: number,
  endTick: number,
): Set<number> {
  const selected = new Set<number>();
  for (const bar of bars) {
    if (bar.startTick >= startTick && bar.startTick + bar.ticks <= endTick) {
      selected.add(bar.bar);
    }
  }
  return selected;
}

export function validatePassageRange(
  bars: readonly MusicXmlBarLayout[],
  range: PassageRange,
): PassageRangeValidation {
  const { barStart, beatStart, barEnd, beatEnd } = range;
  const errors: string[] = [];
  if (bars.length === 0) {
    return {
      ok: false,
      errors: ['This import has no measures.'],
      mixedMeter: false,
      meters: [],
    };
  }
  if (!Number.isInteger(barStart)) {
    errors.push('Start bar must be a whole number.');
  } else if (barStart < 1 || barStart > bars.length) {
    errors.push(`Start bar must be between 1 and ${bars.length}.`);
  }
  if (!Number.isInteger(barEnd)) {
    errors.push('End bar must be a whole number.');
  } else if (barEnd < 1 || barEnd > bars.length) {
    errors.push(`End bar must be between 1 and ${bars.length}.`);
  }

  const startBar =
    Number.isInteger(barStart) && barStart >= 1 && barStart <= bars.length
      ? bars[barStart - 1]
      : null;
  const endBar =
    Number.isInteger(barEnd) && barEnd >= 1 && barEnd <= bars.length
      ? bars[barEnd - 1]
      : null;

  if (!Number.isFinite(beatStart)) {
    errors.push('Start beat must be a number.');
  } else if (startBar) {
    if (beatStart < 0) {
      errors.push('Start beat cannot be negative.');
    } else if (beatStart >= startBar.quarterBeats) {
      errors.push(
        `Start beat must be inside bar ${startBar.bar} (before ${passageBeatLabel(
          startBar.quarterBeats,
        )}).`,
      );
    }
  }
  if (!Number.isFinite(beatEnd)) {
    errors.push('End beat must be a number.');
  } else if (endBar) {
    if (beatEnd <= 0) {
      errors.push('End beat must be after the start of the bar.');
    } else if (beatEnd > endBar.quarterBeats) {
      errors.push(
        `End beat must be inside bar ${endBar.bar} (at or before ${passageEndBeatLabel(
          endBar.quarterBeats,
        )}).`,
      );
    }
  }

  if (
    Number.isInteger(barStart) &&
    Number.isInteger(barEnd) &&
    barStart >= 1 &&
    barEnd >= 1 &&
    barEnd < barStart
  ) {
    errors.push('End bar must be at or after the start bar.');
  } else if (
    startBar &&
    endBar &&
    startBar.bar === endBar.bar &&
    Number.isFinite(beatStart) &&
    Number.isFinite(beatEnd) &&
    beatEnd <= beatStart
  ) {
    errors.push('End beat must be after the start beat.');
  } else if (
    startBar &&
    endBar &&
    startBar.bar < endBar.bar &&
    Number.isFinite(beatStart) &&
    Number.isFinite(beatEnd) &&
    beatStart >= startBar.quarterBeats &&
    beatEnd <= 0
  ) {
    errors.push('The passage range is empty.');
  }

  const meters: string[] = [];
  if (
    Number.isInteger(barStart) &&
    Number.isInteger(barEnd) &&
    barStart >= 1 &&
    barEnd >= 1 &&
    barStart <= bars.length &&
    barEnd <= bars.length
  ) {
    const from = Math.min(barStart, barEnd);
    const to = Math.max(barStart, barEnd);
    for (let bar = from; bar <= to; bar += 1) {
      const meter = bars[bar - 1].meter;
      if (!meters.includes(meter)) meters.push(meter);
    }
  }
  if (meters.length > 1) {
    errors.push(
      `This range crosses a meter change (${meters.join(' → ')}); choose bars inside one meter.`,
    );
  } else if (meters.length === 1 && !isSupportedMeter(meters[0])) {
    errors.push(`Meter ${meters[0]} is not supported by the passage preview.`);
  }

  return {
    ok: errors.length === 0,
    errors,
    mixedMeter: meters.length > 1,
    meters,
  };
}

/** `bar 2 · beat 1.0 → bar 4 · beat 2.0`; no locale formatting. */
export function passageRangeLabel(
  bars: readonly MusicXmlBarLayout[],
  range: PassageRange,
): string {
  const { barStart, beatStart, barEnd, beatEnd } = range;
  if (
    !Number.isFinite(barStart) ||
    !Number.isFinite(barEnd) ||
    !Number.isFinite(beatStart) ||
    !Number.isFinite(beatEnd)
  ) {
    return 'no range';
  }
  if (bars.length === 0) {
    return `bar ${barStart} · beat ${passageBeatLabel(beatStart)} → bar ${barEnd} · beat ${passageEndBeatLabel(beatEnd)}`;
  }
  return `bar ${barStart} · beat ${passageBeatLabel(beatStart)} → bar ${barEnd} · beat ${passageEndBeatLabel(beatEnd)}`;
}

/* ------------------------------------------------------------------------- *
 * Playhead + zoom
 * ------------------------------------------------------------------------- */

export const MIN_ZOOM = 0.5;
export const MAX_ZOOM = 3;
export const ZOOM_STEP = 0.25;

/** Clamp to 0.5–3.0 and round to the nearest 0.25 step. */
export function clampZoom(value: number): number {
  if (!Number.isFinite(value)) return 1;
  const stepped = Math.round(value / ZOOM_STEP) * ZOOM_STEP;
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round(stepped * 100) / 100));
}

/** `50%` / `100%` / `300%`; no locale formatting. */
export function zoomLabel(value: number): string {
  const zoom = clampZoom(value);
  return `${Math.round(zoom * 100)}%`;
}

/**
 * Playhead position in absolute score ticks. Seconds are wall-clock preview
 * time; `bpm` is the preview synth tempo (fallback 96 in the panel). The panel
 * clamps the result to the selection end.
 */
export function playheadTickAt(
  seconds: number,
  bpm: number,
  selectionStartTick: number,
): number {
  const start = Number.isFinite(selectionStartTick)
    ? Math.max(0, selectionStartTick)
    : 0;
  const tempo = Number.isFinite(bpm) && bpm > 0 ? bpm : 96;
  const elapsed = Number.isFinite(seconds) && seconds > 0 ? seconds : 0;
  return (
    start + Math.round(elapsed * (tempo / 60) * TICKS_PER_QUARTER * 1_000_000) / 1_000_000
  );
}

/* ------------------------------------------------------------------------- *
 * Passage API body
 * ------------------------------------------------------------------------- */

export type MusicXmlPassageBodyInput = {
  barStart: number;
  beatStart?: number;
  barEnd: number;
  beatEnd?: number;
  voices?: number[];
};

/**
 * Pure request body builder. Beat fields are omitted unless finite so older
 * callers keep sending `{ barStart, barEnd }`; an omitted `beatEnd` means the
 * end of `barEnd` on the backend.
 */
export function buildMusicXmlPassageBody(
  range: MusicXmlPassageBodyInput,
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    barStart: Math.trunc(range.barStart),
    barEnd: Math.trunc(range.barEnd),
  };
  if (typeof range.beatStart === 'number' && Number.isFinite(range.beatStart)) {
    body.beatStart = range.beatStart;
  }
  if (typeof range.beatEnd === 'number' && Number.isFinite(range.beatEnd)) {
    body.beatEnd = range.beatEnd;
  }
  if (range.voices && range.voices.length) {
    body.voices = [...new Set(range.voices.map((voice) => Math.trunc(voice)))].sort(
      (left, right) => left - right,
    );
  }
  return body;
}

/* ------------------------------------------------------------------------- *
 * Role lanes
 * ------------------------------------------------------------------------- */

export type MusicXmlRole = 'lead' | 'mid' | 'bass';

export const MUSIC_XML_ROLES: readonly MusicXmlRole[] = ['lead', 'mid', 'bass'];

export const MUSIC_XML_ROLE_LABELS: Record<MusicXmlRole, string> = {
  lead: 'Lead',
  mid: 'Mid',
  bass: 'Bass',
};

export type MusicXmlRoleCell = {
  /** 1-based bar number. */
  bar: number;
  /** Tick offset relative to the bar start. */
  startTick: number;
  /** Tick length, already clipped to the bar end. */
  ticks: number;
  rest: boolean;
  /** Sounding notes collapsed into this cell; 0 for a rest, >1 for a chord. */
  count: number;
  durationBeats: number;
  tie: string | null;
  voice: number | null;
};

export type MusicXmlRoleLane = {
  role: MusicXmlRole;
  label: string;
  cells: MusicXmlRoleCell[];
};

function noteTicks(note: MusicXmlImportedNote): number {
  return Math.max(1, Math.round(note.duration * TICKS_PER_QUARTER));
}

function noteTie(notes: readonly MusicXmlImportedNote[]): string | null {
  for (const note of notes) {
    if (note.tie && note.tie !== 'none') return note.tie;
  }
  return null;
}

function firstVoice(notes: readonly MusicXmlImportedNote[]): number {
  let voice = notes[0]?.voice ?? 1;
  for (const note of notes) voice = Math.min(voice, note.voice);
  return voice;
}

function cellFor(
  bar: number,
  startTick: number,
  notes: readonly MusicXmlImportedNote[],
): MusicXmlRoleCell {
  return {
    bar,
    startTick,
    ticks: Math.max(...notes.map(noteTicks)),
    rest: false,
    count: notes.length,
    durationBeats: ticksToBeats(Math.max(...notes.map(noteTicks))),
    tie: noteTie(notes),
    voice: firstVoice(notes),
  };
}

function restCell(bar: number, startTick: number, ticks: number): MusicXmlRoleCell {
  return {
    bar,
    startTick,
    ticks,
    rest: true,
    count: 0,
    durationBeats: ticksToBeats(ticks),
    tie: null,
    voice: null,
  };
}

function onsetKey(bar: number, tick: number): string {
  return `${bar}:${tick}`;
}

type Onset = {
  bar: number;
  tick: number;
  lead: MusicXmlImportedNote[];
  nonLead: MusicXmlImportedNote[];
};

function clipNoteCell(
  cell: MusicXmlRoleCell,
  barTicks: number,
): MusicXmlRoleCell | null {
  const start = Math.max(0, Math.min(barTicks, cell.startTick));
  if (start >= barTicks) return null;
  const end = Math.max(start + 1, Math.min(barTicks, start + cell.ticks));
  if (end <= start) return null;
  const ticks = end - start;
  return {
    ...cell,
    startTick: start,
    ticks,
    durationBeats: ticksToBeats(ticks),
  };
}

/**
 * Fill a lane row with note cells and explicit rests. If a source note sustains
 * across a later onset in the same lane, the earlier cell is truncated at that
 * onset so both attacks stay visible; the last cell is clipped to the bar end.
 */
function fillLane(
  bar: number,
  barTicks: number,
  noteCells: readonly MusicXmlRoleCell[],
): MusicXmlRoleCell[] {
  const clipped = noteCells
    .map((cell) => clipNoteCell(cell, barTicks))
    .filter((cell): cell is MusicXmlRoleCell => cell !== null)
    .sort(
      (left, right) =>
        left.startTick - right.startTick ||
        (left.voice ?? 0) - (right.voice ?? 0),
    );

  const cells: MusicXmlRoleCell[] = [];
  let cursor = 0;
  for (const cell of clipped) {
    let start = cell.startTick;
    if (start >= barTicks) continue;

    // Preserve this onset by shortening the previous sustained note. A lane is
    // a single row, so overlapping source notes cannot both own the same ticks.
    if (start < cursor) {
      const previous = cells[cells.length - 1];
      if (previous && !previous.rest && start > previous.startTick) {
        const ticks = start - previous.startTick;
        previous.ticks = ticks;
        previous.durationBeats = ticksToBeats(ticks);
        cursor = start;
      } else {
        start = cursor;
      }
    }
    if (start >= barTicks) continue;
    if (start > cursor) cells.push(restCell(bar, cursor, start - cursor));

    const end = Math.max(start + 1, Math.min(barTicks, start + cell.ticks));
    const ticks = end - start;
    cells.push({ ...cell, startTick: start, ticks, durationBeats: ticksToBeats(ticks) });
    cursor = end;
  }
  if (cursor < barTicks) cells.push(restCell(bar, cursor, barTicks - cursor));
  if (cells.length === 0) cells.push(restCell(bar, 0, barTicks));
  return cells;
}

/**
 * Build Lead / Mid / Bass rows. Every bar and every lane is contiguous from
 * tick 0 to the bar end: a gap is a rest cell, never an omitted span.
 *
 * `notes` must be the normalized importer notes; `bars` supplies the per-bar
 * meter and length. Rest events are ignored for role assignment.
 */
export function buildRoleLanes(
  notes: readonly MusicXmlImportedNote[],
  bars: readonly MusicXmlBarLayout[],
): MusicXmlRoleLane[] {
  const onsets = new Map<string, Onset>();
  for (const note of notes) {
    if (note.rest || note.midi == null) continue;
    if (note.bar < 0 || note.bar >= bars.length) continue;
    const bar = note.bar + 1;
    const tick = Math.max(0, Math.round(note.beat * TICKS_PER_QUARTER));
    if (tick >= bars[note.bar].ticks) continue;
    const key = onsetKey(bar, tick);
    const existing = onsets.get(key);
    if (existing) {
      if (note.voice === 1) existing.lead.push(note);
      else existing.nonLead.push(note);
    } else {
      onsets.set(key, {
        bar,
        tick,
        lead: note.voice === 1 ? [note] : [],
        nonLead: note.voice === 1 ? [] : [note],
      });
    }
  }

  const noteCells: Record<MusicXmlRole, Map<number, MusicXmlRoleCell[]>> = {
    lead: new Map(),
    mid: new Map(),
    bass: new Map(),
  };
  const add = (role: MusicXmlRole, cell: MusicXmlRoleCell) => {
    const bucket = noteCells[role].get(cell.bar);
    if (bucket) bucket.push(cell);
    else noteCells[role].set(cell.bar, [cell]);
  };

  for (const onset of onsets.values()) {
    if (onset.lead.length) add('lead', cellFor(onset.bar, onset.tick, onset.lead));
    if (onset.nonLead.length) {
      const sorted = [...onset.nonLead].sort(
        (left, right) =>
          (left.midi ?? 127) - (right.midi ?? 127) ||
          left.voice - right.voice ||
          (left.writtenMidi ?? left.midi ?? 127) -
            (right.writtenMidi ?? right.midi ?? 127),
      );
      const bass = sorted[0];
      if (bass) add('bass', cellFor(onset.bar, onset.tick, [bass]));
      if (sorted.length > 1) {
        add('mid', cellFor(onset.bar, onset.tick, sorted.slice(1)));
      }
    }
  }

  return MUSIC_XML_ROLES.map((role) => {
    const cells: MusicXmlRoleCell[] = [];
    for (const bar of bars) {
      const barCells = (noteCells[role].get(bar.bar) ?? []).slice();
      cells.push(...fillLane(bar.bar, bar.ticks, barCells));
    }
    return { role, label: MUSIC_XML_ROLE_LABELS[role], cells };
  });
}

/* ------------------------------------------------------------------------- *
 * Small display helpers
 * ------------------------------------------------------------------------- */

/** `2.5` / `1` / `0.5`; no locale-dependent formatting. */
export function beatCountLabel(value: number): string {
  if (!Number.isFinite(value)) return '—';
  const rounded = Math.round(value * 1_000_000) / 1_000_000;
  return Number.isInteger(rounded) ? String(rounded) : String(rounded);
}

/** `96 BPM` or `—`. */
export function tempoLabel(tempo: number | null): string {
  return tempo != null && Number.isFinite(tempo) && tempo > 0
    ? `${Math.round(tempo)} BPM`
    : '—';
}
