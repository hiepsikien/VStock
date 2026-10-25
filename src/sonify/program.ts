import type { RecapEnsemble, RecapVariant } from '../api/client';

/** Centered title stays up for this long, then docks. The chart matches it. */
export const TITLE_HOLD_SEC = 2;

export type SpanId = '1D' | '1W' | '1M' | '3M' | '1Y';
export type Mode = 'major' | 'minor';

export type Pulse = { bpm: number; beats: number; beatType: number };

export type MovementInput = {
  character: string | null;
  keyLabel: string;
  prices: number[];
  label: string;
  bpm?: number;
  beats?: number;
  beatType?: number;
  /** Dance or tempo the server composed. Empty means the client has no dance name. */
  name?: string | null;
};

export type PieceInput = {
  variant: RecapVariant;
  ensemble: RecapEnsemble;
  symbol: string;
  /** Session day, or the last day of a longer span. `YYYY-MM-DD`. */
  date: string;
  /** Home key, in the server's Vietnamese spelling. */
  keyLabel: string;
  span: SpanId;
  movements: MovementInput[];
};

export type PieceCopy = {
  title: string;
  instruments: string;
  movement: string | null;
};

export type PieceProgram = PieceCopy & { docked: boolean };

/** The docked title hides the time label only where the drawn glyphs overlap it. */
export function titleCoversCursor(
  docked: boolean,
  titleWidth: number,
  labelLeft: number,
  labelWidth: number,
  dockLeft: number,
): boolean {
  if (!docked || titleWidth <= 0 || labelWidth <= 0) return false;
  return labelLeft < dockLeft + titleWidth && labelLeft + labelWidth > dockLeft;
}

export type ChartFocus = { start: number; end: number };

const GUITAR_BPM: Record<string, number> = {
  bach: 96,
  classic: 88,
  villa: 100,
  barrios: 120,
  brouwer: 108,
};

const METER_44 = { beats: 4, beatType: 4 };
const METER_34 = { beats: 3, beatType: 4 };
const METER_68 = { beats: 6, beatType: 8 };
const METER_128 = { beats: 12, beatType: 8 };
const METER_64 = { beats: 6, beatType: 4 };
const METER_54 = { beats: 5, beatType: 4 };
const METER_78 = { beats: 7, beatType: 8 };

const INSTRUMENTS: Record<RecapVariant, Partial<Record<RecapEnsemble, string>>> = {
  symphony: {
    classic: 'Flute, Violin, Cello, Piano, Bass',
    wood: 'Piccolo, Oboe, Clarinet, Harp, Contrabassoon',
    brass: 'Glockenspiel, Trumpet, Trombone, Horn, Tuba',
  },
  jazz: {
    classic: 'Vibraphone, Alto Sax, Tenor Sax, Rhodes, Bass',
    soul: 'Guitar, Trumpet, Trombone, Wurlitzer, Bass',
    organ: 'Guitar, Soprano Sax, Baritone Sax, Organ, Bass',
  },
  minimalist: {
    classic: 'Bell, Arpeggio, Pad, Pulse, Sub-Bass',
    mallet: 'Crotales, Marimba, Choir, Harpsichord, Bass',
    guitar: 'Flute, Steel Guitar, Cello, Piano, Bass',
  },
  ambient: {
    classic: 'Celesta, Alto Flute, Bass Flute, Horn, Bass',
    breath: 'Chimes, English Horn, Bass Clarinet, Trombone, Contrabassoon',
    choir: 'Bells, Clarinet, Tenor, Viola, Bass',
  },
  guitar: {},
};

const TONIC: Record<string, string> = {
  Đô: 'C',
  Rê: 'D',
  'Mi♭': 'E-flat',
  'Si♭': 'B-flat',
  La: 'A',
};

export function modeOf(keyLabel: string): Mode {
  return keyLabel.includes('thứ') ? 'minor' : 'major';
}

export function englishKey(keyLabel: string): string {
  const minor = modeOf(keyLabel) === 'minor';
  const tonic = keyLabel.replace('thứ', '').trim();
  const name = TONIC[tonic] ?? (tonic || 'C');
  return minor ? `${name} minor` : name;
}

/**
 * Work key. A span sends the ticker's home key, minor only when every movement is minor.
 * Without that field, a selloff opening must not pull the whole piece into minor.
 */
export function pieceKey(home: string | null | undefined, movementKeys: string[]): string {
  const given = home?.trim() ?? '';
  if (given) return given;
  const labels = movementKeys.map((label) => label.trim()).filter((label) => label.length > 0);
  if (!labels.length) return '';
  if (labels.every((label) => label.includes('thứ'))) return labels[0];
  return labels[0].replace(/thứ/g, '').replace(/\s+/g, ' ').trim();
}

/** `2026-01-20` → `20/1`. Anything else yields an empty string. */
export function englishDate(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return '';
  return `${Number(match[3])}/${Number(match[2])}`;
}

/** Year labels are `03/26`. Other spans use roman or weekday text. */
export function movementMonth(label: string): number | null {
  const match = /^(\d{1,2})\/\d{2}$/.exec(label.trim());
  if (!match) return null;
  const month = Number(match[1]);
  return month >= 1 && month <= 12 ? month : null;
}

export function movementOffsets(lengths: number[]): number[] {
  const offsets: number[] = [];
  let cursor = 0;
  for (const length of lengths) {
    offsets.push(cursor);
    cursor += length;
  }
  return offsets;
}

export function fullFocus(total: number): ChartFocus {
  return { start: 0, end: Math.max(total - 1, 0) };
}

export function movementFocus(offsets: number[], lengths: number[], index: number): ChartFocus {
  const start = offsets[index] ?? 0;
  const length = lengths[index] ?? 1;
  return { start, end: start + Math.max(length - 1, 0) };
}

export function chartFocus(input: {
  total: number;
  offsets: number[];
  lengths: number[];
  index: number;
  elapsed: number;
  resting: boolean;
  multi: boolean;
}): ChartFocus {
  const full = fullFocus(input.total);
  if (!input.multi || input.resting) return full;
  if (input.index === 0 && input.elapsed < TITLE_HOLD_SEC) return full;
  return movementFocus(input.offsets, input.lengths, input.index);
}

export function easeInOut(t: number): number {
  const clamped = Math.min(1, Math.max(0, t));
  return clamped < 0.5 ? 2 * clamped * clamped : 1 - ((-2 * clamped + 2) ** 2) / 2;
}

export function lerpFocus(from: ChartFocus, to: ChartFocus, t: number): ChartFocus {
  const eased = easeInOut(t);
  return {
    start: from.start + (to.start - from.start) * eased,
    end: from.end + (to.end - from.end) * eased,
  };
}

function pulse(bpm: number, meter: { beats: number; beatType: number }): Pulse {
  return { bpm, beats: meter.beats, beatType: meter.beatType };
}

function swapGuitarMeter(meter: { beats: number; beatType: number }): { beats: number; beatType: number } {
  if (meter.beats === 6 && meter.beatType === 8) return METER_34;
  if (meter.beats === 3 && meter.beatType === 4) return METER_68;
  return meter;
}

function monthPulse(variant: RecapVariant, index: number): Pulse {
  if (variant === 'minimalist') {
    return [pulse(96, METER_54), pulse(72, METER_44), pulse(120, METER_78), pulse(96, METER_44)][index] ?? pulse(96, METER_44);
  }
  if (variant === 'jazz') {
    return [pulse(96, METER_44), pulse(72, METER_128), pulse(120, METER_34), pulse(96, METER_44)][index] ?? pulse(96, METER_44);
  }
  if (variant === 'ambient') {
    return [pulse(96, METER_44), pulse(72, METER_64), pulse(120, METER_34), pulse(96, METER_44)][index] ?? pulse(96, METER_44);
  }
  return [pulse(96, METER_44), pulse(72, METER_68), pulse(120, METER_34), pulse(96, METER_44)][index] ?? pulse(96, METER_44);
}

function quarterPulse(variant: RecapVariant, index: number): Pulse {
  if (variant === 'minimalist') {
    return [pulse(96, METER_54), pulse(60, METER_44), pulse(108, METER_78)][index] ?? pulse(96, METER_44);
  }
  if (variant === 'jazz') {
    return [pulse(96, METER_44), pulse(60, METER_128), pulse(108, METER_44)][index] ?? pulse(96, METER_44);
  }
  if (variant === 'ambient') {
    return [pulse(96, METER_44), pulse(60, METER_64), pulse(108, METER_44)][index] ?? pulse(96, METER_44);
  }
  return [pulse(96, METER_44), pulse(60, METER_68), pulse(108, METER_44)][index] ?? pulse(96, METER_44);
}

function yearPulse(variant: RecapVariant, month: number): Pulse {
  if (month === 12) return pulse(96, METER_44);
  const slot = (month - 1) % 3;
  if (variant === 'minimalist') {
    if (slot === 0) return pulse(100, METER_54);
    if (slot === 1) return pulse(66, METER_44);
    return pulse(108, METER_78);
  }
  if (slot === 0) return pulse(100, METER_44);
  if (slot === 1) {
    if (variant === 'jazz') return pulse(66, METER_128);
    if (variant === 'ambient') return pulse(66, METER_64);
    return pulse(66, METER_68);
  }
  return pulse(108, METER_34);
}

/** Meter and tempo of one movement when the server has not sent them. */
export function movementPulse(
  variant: RecapVariant,
  ensemble: RecapEnsemble,
  span: SpanId,
  index: number,
  month: number | null,
): Pulse {
  if (variant === 'guitar' && span !== '1D' && span !== '1W') {
    const base = movementPulse('symphony', 'classic', span, index, month);
    const meter = swapGuitarMeter(base);
    return { bpm: base.bpm, beats: meter.beats, beatType: meter.beatType };
  }
  if (span === '1W') return pulse(90, METER_44);
  if (span === '1D') {
    if (variant === 'jazz') return pulse(82, METER_44);
    if (variant === 'minimalist') return pulse(118, METER_44);
    if (variant === 'ambient') return pulse(60, METER_44);
    if (variant === 'guitar') return pulse(GUITAR_BPM[ensemble] ?? 96, METER_44);
    return pulse(90, METER_44);
  }
  if (span === '1M') return monthPulse(variant, index);
  if (span === '3M') return quarterPulse(variant, index);
  return yearPulse(variant, month ?? Math.min(12, index + 1));
}

function meterLabel(pulseValue: Pulse): string {
  return `${pulseValue.beats}/${pulseValue.beatType}`;
}

function isCommonTime(pulseValue: Pulse): boolean {
  return pulseValue.beats === 4 && pulseValue.beatType === 4;
}

function classicalName(variant: RecapVariant, span: SpanId, index: number, month: number | null): string | null {
  if (variant === 'minimalist') {
    if (span === '1Y' && month === 12) return 'Finale';
    if (span === '1M' && index === 3) return 'Finale';
    return null;
  }
  if (span === '1Y') {
    const slotMonth = month ?? index + 1;
    if (slotMonth === 12) return 'Finale';
    const slot = (slotMonth - 1) % 3;
    if (variant === 'jazz') return ['Swing', 'Ballad', 'Waltz'][slot] ?? 'Swing';
    if (variant === 'ambient') return ['Allegretto', 'Adagio', 'Minuet'][slot] ?? 'Allegretto';
    return ['Allegretto', 'Siciliana', 'Minuet'][slot] ?? 'Allegretto';
  }
  if (span === '1M') {
    if (variant === 'jazz') return ['Swing', 'Ballad', 'Waltz', 'Finale'][index] ?? 'Finale';
    if (variant === 'ambient') return ['Allegretto', 'Adagio', 'Minuet', 'Finale'][index] ?? 'Finale';
    return ['Allegretto', 'Siciliana', 'Minuet', 'Finale'][index] ?? 'Finale';
  }
  if (span === '3M') {
    if (variant === 'jazz') return ['Swing', 'Ballad', 'Finale'][index] ?? 'Finale';
    if (variant === 'ambient') return ['Allegretto', 'Adagio', 'Finale'][index] ?? 'Finale';
    return ['Allegretto', 'Adagio', 'Finale'][index] ?? 'Finale';
  }
  return null;
}

function workForm(variant: RecapVariant, span: SpanId, dance: string | null, count: number): string | null {
  if (variant === 'guitar') return count > 1 ? 'Suite' : dance;
  if (variant === 'jazz') return span === '1D' || span === '1W' ? 'Jazz' : 'Set';
  if (variant === 'minimalist') return span === '1D' || span === '1W' ? 'Etude' : 'Cycle';
  if (variant === 'ambient') return span === '1D' || span === '1W' ? 'Prelude' : 'Nocturne';
  if (span === '1D') return 'Bagatelle';
  if (span === '1W') return 'Fantasia';
  if (span === '1M') return 'Divertimento';
  if (span === '3M') return 'Quintet';
  return 'Serenade';
}

function movementLine(index: number, name: string | null, pulseValue: Pulse): string {
  const number = index + 1;
  if (name === 'Finale' && isCommonTime(pulseValue)) return `Movement ${number}: Finale (${pulseValue.bpm} BPM)`;
  if (name && name !== 'Finale') return `Movement ${number}: ${name} (${pulseValue.bpm} BPM)`;
  return `Movement ${number} (${meterLabel(pulseValue)}, ${pulseValue.bpm} BPM)`;
}

export function instrumentLine(variant: RecapVariant, ensemble: RecapEnsemble): string {
  if (variant === 'guitar') return 'Guitar (Solo)';
  return INSTRUMENTS[variant][ensemble] ?? INSTRUMENTS[variant].classic ?? '';
}

export function pieceCopy(input: PieceInput, movementIndex = 0): PieceCopy {
  const count = Math.max(1, input.movements.length);
  const index = Math.min(count - 1, Math.max(0, movementIndex));
  const current = input.movements[index];
  const month = current ? movementMonth(current.label) : null;
  const pulseValue = current
    ? resolvePulse(current, input.variant, input.ensemble, input.span, index, month)
    : movementPulse(input.variant, input.ensemble, input.span, index, month);
  const supplied = current?.name?.trim() || null;
  const dance = input.variant === 'guitar' ? supplied : null;
  const form = workForm(input.variant, input.span, dance, count);
  const when = englishDate(input.date);
  const dated = when ? `${input.symbol} ${when}` : input.symbol;
  const movementName =
    supplied ?? (input.variant === 'guitar' ? null : classicalName(input.variant, input.span, index, month));
  const key = englishKey(input.keyLabel);
  return {
    title: form ? `${form} ${dated} in ${key}` : `${dated} in ${key}`,
    instruments: instrumentLine(input.variant, input.ensemble),
    movement: count > 1 ? movementLine(index, movementName, pulseValue) : null,
  };
}

function resolvePulse(
  movement: MovementInput,
  variant: RecapVariant,
  ensemble: RecapEnsemble,
  span: SpanId,
  index: number,
  month: number | null,
): Pulse {
  if (movement.bpm && movement.beats && movement.beatType) {
    return { bpm: movement.bpm, beats: movement.beats, beatType: movement.beatType };
  }
  return movementPulse(variant, ensemble, span, index, month);
}
