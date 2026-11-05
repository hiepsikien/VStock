/**
 * Pure micro-velocity lane model for Studio (docs §6.9).
 *
 * This module knows nothing about React or the network. It takes the preview
 * `notes[]` shape (`bar`, `beat`, `duration`, `midi`, `voice`, `velocity`,
 * `accent`, `staccato`, ties/slurs) and an optional authored contour, then
 * produces display rows, extents and labels.
 *
 * Contract seam while the backend contour API is not built:
 *
 *   `MicroVelocity` is the documented `{ kind: "offsets" | "rule", ... }`
 *   carrier. A preview response can expose it as `microVelocity` (preferred)
 *   or `velocityContour`; `normalizeVelocityContour()` accepts either value.
 *   A note may also carry `velocityOffset` / `pinned` / `pinnedLayer` for
 *   hand-authored specs.
 *
 * Coordinate notes:
 *   - Contour `bar`/`eighth` are relative to the figure/slot that owns them.
 *     `options.barOffset` shifts the start bar and `options.barSpan` wraps a
 *     tiled figure. With neither, contour bars match preview bars 0-based.
 *   - Preview `beat` is in quarter notes; `eighth` is `round(beat * 2)`.
 *   - The thumb lane is voice 3 / finger `p`. A voice-3 note is also treated
 *     as thumb when the contour's `thumb[]` names that bar/eighth.
 *   - Rule contours are never invented here. Every unmatched row gets
 *     `needsRule: true` unless the caller supplies a simple offset table.
 */

export type VelocityFinger = 'p' | 'a' | 'm' | 'i';

export const VELOCITY_FINGERS: readonly VelocityFinger[] = ['p', 'a', 'm', 'i'];

/** One authored micro-velocity coordinate (docs §6.9). */
export type VelocityCoordinate = {
  /** 0-based, relative to the figure/slot. */
  bar: number;
  /** 0-based eighth-note index inside the bar. */
  eighth: number;
  /** 1–4. */
  voice: number;
  /** Optional for tremolo/fingerstyle; absent means the whole voice. */
  finger?: VelocityFinger | null;
};

/**
 * One contour entry. An unpinned entry stores a delta in `offset`; a pinned
 * attack (absolute writer: snap/stab/fan/tremolo trim) stores `velocity`.
 */
export type VelocityOffset = VelocityCoordinate & {
  /** Delta on the figure-written level. Not an absolute velocity. */
  offset?: number;
  /** True when an absolute layer owns this attack. */
  pinned?: boolean;
  /** Final absolute velocity for a pinned attack. */
  velocity?: number;
  /** Absolute-writer name for the pinned label (`snap`, `stab`, …). */
  layer?: string | null;
};

export type VelocityOffsetsContour = {
  kind: 'offsets';
  notes: VelocityOffset[];
  /** Empty/absent means every thumb attack keeps offset 0. */
  thumb?: VelocityOffset[];
};

export type VelocityRuleContour = {
  kind: 'rule';
  ruleId: string;
  ruleVersion: number;
  /** The documented minimum per rule, e.g. `{ step, floor, peakQuarter }`. */
  params: Record<string, unknown>;
  notes?: VelocityOffset[];
  thumb?: VelocityOffset[];
};

/** Authored contour carrier for a figure, slot, pattern or sentence. */
export type MicroVelocity = VelocityOffsetsContour | VelocityRuleContour;

/** One preview note after normalisation. */
export type VelocityLaneNote = {
  bar: number;
  beat: number;
  eighth: number;
  duration: number | null;
  midi: number | null;
  voice: number;
  velocity: number | null;
  accent: boolean;
  staccato: boolean;
  tieStart: boolean;
  tieStop: boolean;
  slurStart: boolean;
  slurStop: boolean;
  staff: number | null;
  finger: VelocityFinger | null;
  /** Optional note-level authored delta (`AuthoredEvent.velocityOffset`). */
  velocityOffset: number | null;
  pinned: boolean;
  pinnedLayer: string | null;
};

export type VelocityLaneId = 'thumb' | 'voice1' | 'voice2' | 'voice3' | 'voice4';

export type VelocityLaneRow = {
  /** Unique per note (coordinate + midi + ordinal). */
  key: string;
  lane: VelocityLaneId;
  note: VelocityLaneNote;
  bar: number;
  beat: number;
  eighth: number;
  voice: number;
  finger: VelocityFinger | null;
  thumb: boolean;
  /** Delta to display for this row. Defaults to 0. */
  offset: number;
  /** True when the contour or the note supplied an authored value. */
  authored: boolean;
  pinned: boolean;
  pinnedLayer: string | null;
  /** Absolute velocity for pinned attacks; otherwise the realized velocity. */
  velocity: number | null;
  /** Display-only velocity after the offset; never written back. */
  previewVelocity: number | null;
  /** Rule contour with no flatten table entry for this coordinate. */
  needsRule: boolean;
};

export type VelocityLaneOptions = {
  /** Only include this voice's non-thumb rows; null/undefined means all. */
  voice?: number | null;
  /** Include the thumb lane (default true). */
  includeThumb?: boolean;
  /** Include voice 4 when the notes use it (default true). */
  includeVoice4?: boolean;
  /** Preview bar where the figure/slot starts. Default 0. */
  barOffset?: number;
  /** Figure length in bars; contour bars wrap modulo this. */
  barSpan?: number;
  /**
   * Simple flatten table for a rule contour, keyed by `noteKey(...)` or
   * `bar:eighth:voice`. Missing coordinates stay `needsRule`.
   */
  ruleOffsets?: Readonly<Record<string, number>>;
};

export type VelocityLaneExtent = {
  minOffset: number;
  maxOffset: number;
  minVelocity: number;
  maxVelocity: number;
  maxAbsOffset: number;
  barStart: number;
  barEnd: number;
  barCount: number;
  hasPinned: boolean;
  needsRule: boolean;
};

export type VelocityPreviewNote = VelocityLaneNote & {
  key: string;
  lane: VelocityLaneId;
  authoredOffset: number;
  pinnedLayer: string | null;
  previewVelocity: number | null;
};

export type VelocityLaneDiff = {
  total: number;
  offsetRows: number;
  pinnedRows: number;
  needsRule: number;
  changedRows: number;
  maxAbsOffset: number;
  velocityDelta: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function finite(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function nonNegativeInteger(value: unknown): number | null {
  const number = finite(value);
  return number == null || number < 0 ? null : Math.trunc(number);
}

function integer(value: unknown, fallback = 0): number {
  return nonNegativeInteger(value) ?? fallback;
}

function clampVelocity(value: number): number {
  return Math.max(0, Math.min(127, Math.round(value)));
}

function fingerValue(value: unknown): VelocityFinger | null {
  return typeof value === 'string' && (VELOCITY_FINGERS as readonly string[]).includes(value)
    ? (value as VelocityFinger)
    : null;
}

function stringValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/** Default 0; thumb also defaults to 0, as required by §6.9. */
export function noteOffset(value: unknown): number {
  return finite(value) ?? 0;
}

/** Stable contour coordinate key; a missing finger matches the whole voice. */
export function noteKey(
  bar: number,
  eighth: number,
  voice: number,
  finger?: VelocityFinger | null,
): string {
  return `${Math.trunc(bar)}:${Math.trunc(eighth)}:${Math.trunc(voice)}:${finger ?? '*'}`;
}

function voiceKey(bar: number, eighth: number, voice: number): string {
  return `${Math.trunc(bar)}:${Math.trunc(eighth)}:${Math.trunc(voice)}`;
}

function thumbPositionKey(bar: number, eighth: number): string {
  return `${Math.trunc(bar)}:${Math.trunc(eighth)}`;
}

/** Normalise one preview note; unknown/extra fields are ignored. */
export function normalizeVelocityNote(value: unknown): VelocityLaneNote | null {
  if (!isRecord(value)) return null;
  if (typeof value.bar !== 'number' || typeof value.voice !== 'number') return null;

  const beat = finite(value.beat) ?? 0;
  const voice = Math.trunc(value.voice);
  if (voice < 1 || voice > 4) return null;

  return {
    bar: Math.trunc(value.bar),
    beat,
    eighth: Math.max(0, Math.round(beat * 2)),
    duration: finite(value.duration),
    midi: finite(value.midi),
    voice,
    velocity: finite(value.velocity),
    accent: value.accent === true,
    staccato: value.staccato === true,
    tieStart: value.tieStart === true,
    tieStop: value.tieStop === true,
    slurStart: value.slurStart === true,
    slurStop: value.slurStop === true,
    staff: finite(value.staff),
    finger: fingerValue(value.finger),
    velocityOffset: finite(value.velocityOffset),
    pinned: value.pinned === true,
    pinnedLayer: stringValue(value.pinnedLayer ?? value.layer),
  };
}

function normalizeOffset(value: unknown): VelocityOffset | null {
  if (!isRecord(value)) return null;
  if (typeof value.voice !== 'number') return null;
  const voice = Math.trunc(value.voice);
  if (voice < 1 || voice > 4) return null;
  const offset = finite(value.offset);
  const velocity = finite(value.velocity);
  return {
    bar: integer(value.bar),
    eighth: integer(value.eighth),
    voice,
    finger: fingerValue(value.finger),
    ...(offset == null ? {} : { offset }),
    ...(value.pinned === true ? { pinned: true } : {}),
    ...(velocity == null ? {} : { velocity }),
    ...(stringValue(value.layer) ? { layer: stringValue(value.layer) } : {}),
  };
}

function normalizeOffsets(value: unknown): VelocityOffset[] {
  if (!Array.isArray(value)) return [];
  return value
    .map(normalizeOffset)
    .filter((entry): entry is VelocityOffset => entry !== null);
}

/** Accept the documented contour, an array, or null. */
export function normalizeVelocityContour(value: unknown): MicroVelocity | null {
  if (Array.isArray(value)) {
    return { kind: 'offsets', notes: normalizeOffsets(value) };
  }
  if (!isRecord(value)) return null;

  const kind = value.kind;
  if (kind === 'rule') {
    const ruleId = stringValue(value.ruleId);
    if (!ruleId) return null;
    return {
      kind: 'rule',
      ruleId,
      ruleVersion: integer(value.ruleVersion ?? value.version),
      params: isRecord(value.params) ? { ...value.params } : {},
      notes: normalizeOffsets(value.notes),
      thumb: normalizeOffsets(value.thumb),
    };
  }
  if (kind === 'offsets' || kind === 'microVelocity' || Array.isArray(value.notes)) {
    return {
      kind: 'offsets',
      notes: normalizeOffsets(value.notes),
      thumb: normalizeOffsets(value.thumb),
    };
  }
  return null;
}

export function velocityContourKind(
  contour: MicroVelocity | null | undefined,
): 'none' | 'offsets' | 'rule' {
  return contour ? contour.kind : 'none';
}

type Lookup = {
  /** Exact `bar:eighth:voice:finger` entries. */
  exact: Map<string, VelocityOffset>;
  /** Fingerless `bar:eighth:voice:*` entries. */
  voice: Map<string, VelocityOffset>;
  /** Thumb positions from `thumb[]`, even when the entry itself is fingerless. */
  thumb: VelocityOffset[];
  thumbExact: Map<string, VelocityOffset>;
  thumbVoice: Map<string, VelocityOffset>;
  thumbPositions: Set<string>;
  rule: boolean;
  ruleOffsets: Readonly<Record<string, number>> | null;
  hasContour: boolean;
};

function entryFor(
  exact: Map<string, VelocityOffset>,
  byVoice: Map<string, VelocityOffset>,
  bar: number,
  eighth: number,
  voice: number,
  finger: VelocityFinger | null,
): VelocityOffset | undefined {
  if (finger) {
    const exactHit = exact.get(noteKey(bar, eighth, voice, finger));
    if (exactHit) return exactHit;
  }
  return byVoice.get(noteKey(bar, eighth, voice, null));
}

function buildLookup(contour: MicroVelocity | null | undefined): Lookup {
  const exact = new Map<string, VelocityOffset>();
  const byVoice = new Map<string, VelocityOffset>();
  const thumbExact = new Map<string, VelocityOffset>();
  const thumbVoice = new Map<string, VelocityOffset>();
  const thumbPositions = new Set<string>();
  const lookup: Lookup = {
    exact,
    voice: byVoice,
    thumb: [],
    thumbExact,
    thumbVoice,
    thumbPositions,
    rule: contour?.kind === 'rule',
    ruleOffsets: null,
    hasContour: contour != null,
  };
  if (!contour) return lookup;

  for (const entry of contour.notes ?? []) {
    const key = noteKey(entry.bar, entry.eighth, entry.voice, entry.finger ?? null);
    if (entry.finger) exact.set(key, entry);
    else byVoice.set(key, entry);
  }
  for (const entry of contour.thumb ?? []) {
    lookup.thumb.push(entry);
    const key = noteKey(entry.bar, entry.eighth, entry.voice, entry.finger ?? null);
    if (entry.finger) thumbExact.set(key, entry);
    else thumbVoice.set(key, entry);
    thumbPositions.add(thumbPositionKey(entry.bar, entry.eighth));
  }
  return lookup;
}

function ruleOffsetFor(
  table: Readonly<Record<string, number>> | null,
  bar: number,
  eighth: number,
  voice: number,
  finger: VelocityFinger | null,
): number | null {
  if (!table) return null;
  const candidates = [
    noteKey(bar, eighth, voice, finger),
    noteKey(bar, eighth, voice, null),
    voiceKey(bar, eighth, voice),
  ];
  for (const candidate of candidates) {
    const value = finite(table[candidate]);
    if (value != null) return value;
  }
  return null;
}

function relativeBar(
  bar: number,
  barOffset: number,
  barSpan: number | undefined,
): number {
  const relative = bar - barOffset;
  if (barSpan && barSpan > 0) {
    const wrapped = relative % barSpan;
    return wrapped < 0 ? wrapped + barSpan : wrapped;
  }
  return relative;
}

/**
 * One row per preview note, with default offset 0.
 *
 * Rows are sorted by bar, eighth, voice, midi. Never mutates `notes`.
 */
export function velocityLaneRows(
  notes: readonly unknown[],
  contour?: MicroVelocity | null,
  options: VelocityLaneOptions = {},
): VelocityLaneRow[] {
  const lookup = buildLookup(contour);
  const barOffset = options.barOffset ?? 0;
  const includeThumb = options.includeThumb !== false;
  const includeVoice4 = options.includeVoice4 !== false;
  const voiceFilter = options.voice ?? null;

  const normalized = notes
    .map(normalizeVelocityNote)
    .filter((note): note is VelocityLaneNote => note !== null);

  normalized.sort((left, right) => {
    if (left.bar !== right.bar) return left.bar - right.bar;
    if (left.beat !== right.beat) return left.beat - right.beat;
    if (left.voice !== right.voice) return left.voice - right.voice;
    if (left.midi !== right.midi) return (left.midi ?? -1) - (right.midi ?? -1);
    return (left.duration ?? 0) - (right.duration ?? 0);
  });

  const rows: VelocityLaneRow[] = [];
  normalized.forEach((note, index) => {
    const bar = relativeBar(note.bar, barOffset, options.barSpan);
    const position = thumbPositionKey(bar, note.eighth);
    const thumb =
      note.voice === 3 &&
      (note.finger === 'p' || lookup.thumbPositions.has(position));
    const lane: VelocityLaneId = thumb ? 'thumb' : (`voice${note.voice}` as VelocityLaneId);

    if (voiceFilter != null && !thumb && note.voice !== voiceFilter) return;
    if (!includeThumb && thumb) return;
    if (!includeVoice4 && note.voice === 4) return;

    let offset = 0;
    let authored = false;
    let pinned = note.pinned;
    let pinnedLayer = note.pinnedLayer;
    let velocity = note.velocity;
    let needsRule = false;

    if (lookup.rule) {
      const rule = ruleOffsetFor(
        options.ruleOffsets ?? null,
        bar,
        note.eighth,
        note.voice,
        note.finger,
      );
      if (rule == null) {
        needsRule = true;
        offset = 0;
      } else {
        offset = rule;
        authored = true;
      }
    } else {
      // A preview note rarely carries `finger`; the thumb classification tells
      // us the matched contour entry must be the `p` one when it is fingered.
      const lookupFinger = thumb ? (note.finger ?? 'p') : note.finger;
      const entry = thumb
        ? entryFor(lookup.thumbExact, lookup.thumbVoice, bar, note.eighth, note.voice, lookupFinger)
        : entryFor(lookup.exact, lookup.voice, bar, note.eighth, note.voice, lookupFinger);
      if (entry) {
        authored = true;
        offset = noteOffset(entry.offset);
        if (entry.pinned === true) pinned = true;
        if (entry.velocity != null) velocity = entry.velocity;
        if (stringValue(entry.layer)) pinnedLayer = stringValue(entry.layer);
      } else if (note.velocityOffset != null) {
        // Note-level authored delta is the fallback for hand-authored specs.
        authored = true;
        offset = note.velocityOffset;
      }
    }

    if (pinned && !authored) {
      // Pinned note-level attacks are authored even without an offset entry.
      authored = true;
    }
    if (pinned && velocity == null) {
      // The absolute writer's velocity is unknown; do not invent one.
      velocity = null;
    }

    const previewVelocity = pinned
      ? velocity
      : velocity == null
        ? null
        : clampVelocity(velocity + offset);

    rows.push({
      key: `${noteKey(note.bar, note.eighth, note.voice, note.finger)}:${note.midi ?? '-'}:${index}`,
      lane,
      note,
      bar: note.bar,
      beat: note.beat,
      eighth: note.eighth,
      voice: note.voice,
      finger: note.finger,
      thumb,
      offset,
      authored,
      pinned,
      pinnedLayer,
      velocity,
      previewVelocity,
      needsRule,
    });
  });

  return rows;
}

export function velocityLaneExtent(rows: readonly VelocityLaneRow[]): VelocityLaneExtent {
  const offsets = rows.filter((row) => !row.pinned).map((row) => row.offset);
  const velocities = rows
    .filter((row) => row.pinned && row.velocity != null)
    .map((row) => row.velocity as number);
  const minOffset = Math.min(0, ...offsets);
  const maxOffset = Math.max(0, ...offsets);
  const minVelocity = velocities.length ? Math.min(...velocities) : 0;
  const maxVelocity = velocities.length ? Math.max(...velocities) : 0;
  const bars = rows.map((row) => row.bar);

  return {
    minOffset,
    maxOffset,
    minVelocity,
    maxVelocity,
    maxAbsOffset: Math.max(Math.abs(minOffset), Math.abs(maxOffset)),
    barStart: bars.length ? Math.min(...bars) : 0,
    barEnd: bars.length ? Math.max(...bars) : 0,
    barCount: bars.length ? Math.max(...bars) - Math.min(...bars) + 1 : 0,
    hasPinned: rows.some((row) => row.pinned),
    needsRule: rows.some((row) => row.needsRule),
  };
}

/** Display label; bars are 1-based for musicians, contour data stays 0-based. */
export function velocityLaneLabel(input: {
  bar: number;
  eighth: number;
  voice: number;
  finger?: VelocityFinger | null;
  thumb?: boolean;
}): string {
  const parts = [`bar ${input.bar + 1}`, `eighth ${input.eighth}`, `voice ${input.voice}`];
  if (input.finger) parts.push(`finger ${input.finger}`);
  if (input.thumb) parts.push('thumb');
  return parts.join(' · ');
}

/** Pinned label: absolute-writer name plus the stored absolute velocity. */
export function pinnedLabel(input: {
  pinned?: boolean;
  layer?: string | null;
  pinnedLayer?: string | null;
  velocity?: number | null;
}): string {
  const layer = stringValue(input.layer ?? input.pinnedLayer);
  const velocity = finite(input.velocity);
  if (layer && velocity != null) return `${layer} · v${Math.round(velocity)}`;
  if (layer) return layer;
  if (velocity != null) return `pinned · v${Math.round(velocity)}`;
  return 'pinned';
}

/**
 * Display-only preview. Returns fresh note copies; `notes` is never mutated.
 * Pinned attacks keep their absolute velocity and ignore the offset.
 */
export function applyOffsetPreview(
  notes: readonly unknown[],
  contour?: MicroVelocity | null,
  options: VelocityLaneOptions = {},
): VelocityPreviewNote[] {
  return velocityLaneRows(notes, contour, options).map((row) => ({
    ...row.note,
    key: row.key,
    lane: row.lane,
    velocity: row.pinned ? row.velocity : row.note.velocity,
    velocityOffset: row.offset,
    pinned: row.pinned,
    authoredOffset: row.offset,
    pinnedLayer: row.pinnedLayer,
    previewVelocity: row.previewVelocity,
  }));
}

/** Cheap summary of what the contour changes; all offsets display-only. */
export function velocityLaneDiff(
  notes: readonly unknown[],
  contour?: MicroVelocity | null,
  options: VelocityLaneOptions = {},
): VelocityLaneDiff {
  const rows = velocityLaneRows(notes, contour, options);
  return {
    total: rows.length,
    offsetRows: rows.filter((row) => !row.pinned && row.offset !== 0).length,
    pinnedRows: rows.filter((row) => row.pinned).length,
    needsRule: rows.filter((row) => row.needsRule).length,
    changedRows: rows.filter(
      (row) => row.pinned || row.offset !== 0 || row.needsRule,
    ).length,
    maxAbsOffset: rows.reduce(
      (max, row) => (row.pinned ? max : Math.max(max, Math.abs(row.offset))),
      0,
    ),
    velocityDelta: rows.reduce((sum, row) => {
      if (row.pinned || row.velocity == null || row.previewVelocity == null) return sum;
      return sum + (row.previewVelocity - row.velocity);
    }, 0),
  };
}
