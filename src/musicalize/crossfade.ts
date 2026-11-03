/**
 * Musical position helpers for the A/B listening room.
 *
 * A/B must keep the listener at the same bar/beat, not at the same wall-clock
 * second. Tempo can differ between the two sides, so the player converts the
 * current position to musical coordinates before it asks for the other side.
 */

export type MovementTiming = {
  /** Written musical length. The file may add a release tail. */
  mapDurationSec?: number;
  /** File length, used when the plan has no written length. */
  durationSec: number;
  bpm?: number;
  /** Beats per bar. */
  beats?: number;
  /** Note value that gets one beat. */
  beatType?: number;
};

export type MusicalPosition = {
  /** Movement/chapter index. */
  index: number;
  bar: number;
  beat: number;
  /** Fraction of the beat, 0..1. */
  fraction: number;
  /** Fallback when the movement has no BPM/meter metadata. */
  ratio: number;
};

type Grid = {
  barSec: number;
  beatSec: number;
};

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

function musicalLength(timing: MovementTiming): number {
  const written = timing.mapDurationSec ?? 0;
  if (written > 0) return written;
  return Math.max(0, timing.durationSec);
}

function gridFor(timing: MovementTiming): Grid | null {
  const bpm = timing.bpm ?? 0;
  const beats = timing.beats ?? 0;
  const beatType = timing.beatType ?? 0;
  if (!(bpm > 0) || !(beats > 0) || !(beatType > 0)) return null;
  const quarterPerBar = beats * (4 / beatType);
  const beatSec = (60 / bpm) * (4 / beatType);
  return { barSec: quarterPerBar * (60 / bpm), beatSec };
}

/** Convert a wall-clock offset inside one movement to bar/beat/fraction. */
export function positionAt(seconds: number, timing: MovementTiming): Omit<MusicalPosition, 'index'> {
  const length = musicalLength(timing);
  const t = clamp(Number.isFinite(seconds) ? seconds : 0, 0, length);
  const grid = gridFor(timing);
  if (!grid || length <= 0) {
    return {
      bar: 0,
      beat: 0,
      fraction: length > 0 ? t / length : 0,
      ratio: length > 0 ? t / length : 0,
    };
  }
  const bar = Math.floor(t / grid.barSec);
  const within = t - bar * grid.barSec;
  const beatFloat = within / grid.beatSec;
  const beat = Math.floor(beatFloat);
  return {
    bar,
    beat,
    fraction: beatFloat - beat,
    ratio: length > 0 ? t / length : 0,
  };
}

/** Convert bar/beat/fraction back to a wall-clock offset for another side. */
export function secondsAt(position: Omit<MusicalPosition, 'index'>, timing: MovementTiming): number {
  const length = musicalLength(timing);
  if (length <= 0) return 0;
  const grid = gridFor(timing);
  if (!grid) return clamp(position.ratio, 0, 1) * length;
  const t =
    position.bar * grid.barSec +
    (Math.max(0, position.beat) + clamp(position.fraction, 0, 1)) * grid.beatSec;
  return clamp(t, 0, length);
}
