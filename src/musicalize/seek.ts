import { ambientDailyCandleIndexAt, spanCandleIndexAt } from '../utils/recapCursor';
import type { ListenSpan } from './labels';

export function clamp01(ratio: number): number {
  if (!Number.isFinite(ratio)) return 0;
  return Math.min(1, Math.max(0, ratio));
}

/**
 * Clock shared by the 1D playhead and a stage drag.
 * MuseScore leaves a release after the last note, so the file is longer than
 * the written piece. The chart follows `mapDurationSec`. The file length is
 * only a fallback when the map is missing.
 */
export function dailyMapClock(
  mapDurationSec: number,
  fileDurationSec: number,
  mediaDurationSec = 0,
): number {
  const file = fileDurationSec > 0 ? fileDurationSec : Math.max(0, mediaDurationSec);
  if (mapDurationSec > 0) return mapDurationSec;
  return file;
}

/**
 * Stage drag on a 1D session. `ratio` runs across the visible price candles,
 * and the target sits in the body of the 34-bar frame, not the intro or outro.
 * Pass `dailyMapClock`, the same duration `ambientDailyCandleIndexAt` uses.
 */
export function dailyStageSeek(durationSec: number, ratio: number): number {
  const r = clamp01(ratio);
  const introEnd = (durationSec * 2) / 34;
  const outroStart = (durationSec * 32) / 34;
  return introEnd + r * (outroStart - introEnd);
}

/**
 * Stage drag on the movement that fills the frame.
 * A week passes warmup and cooldown as 0, so the ratio covers the whole file.
 */
export function spanStageSeek(
  durationSec: number,
  warmupSec: number,
  cooldownSec: number,
  ratio: number,
): number {
  const r = clamp01(ratio);
  return warmupSec + r * (durationSec - warmupSec - cooldownSec);
}

/** Scrubber drag lands on a file second. The playhead then maps that second to a candle. */
export function scrubberSeek(durationSec: number, ratio: number): number {
  return clamp01(ratio) * Math.max(0, durationSec);
}

export function dailyCandleForSecond(elapsedSec: number, count: number, durationSec: number): number {
  return ambientDailyCandleIndexAt(elapsedSec, count, durationSec);
}

export function spanCandleForSecond(
  elapsedSec: number,
  count: number,
  durationSec: number,
  warmupSec: number,
  cooldownSec: number,
): number {
  return spanCandleIndexAt(elapsedSec, count, durationSec, warmupSec, cooldownSec);
}

export type WorkMovement = {
  durationSec: number;
  restAfterSec: number;
};

export type WorkSegment =
  | { kind: 'audio'; index: number; start: number; end: number; durationSec: number }
  | { kind: 'rest'; afterIndex: number; start: number; end: number };

/** The work bar includes the rest between movements and stops at the last note. */
export function workSegments(movements: WorkMovement[]): WorkSegment[] {
  const segments: WorkSegment[] = [];
  let cursor = 0;
  movements.forEach((movement, index) => {
    const duration = Math.max(0, movement.durationSec);
    segments.push({
      kind: 'audio',
      index,
      start: cursor,
      end: cursor + duration,
      durationSec: duration,
    });
    cursor += duration;
    const between = index < movements.length - 1 ? Math.max(0, movement.restAfterSec) : 0;
    if (between > 0) {
      segments.push({
        kind: 'rest',
        afterIndex: index,
        start: cursor,
        end: cursor + between,
      });
      cursor += between;
    }
  });
  return segments;
}

export function workDuration(movements: WorkMovement[]): number {
  const segments = workSegments(movements);
  if (!segments.length) return 0;
  return segments[segments.length - 1].end;
}

export type WorkPlace =
  | { kind: 'audio'; index: number; offset: number }
  | { kind: 'rest'; afterIndex: number; offset: number };

export function placeOnWork(movements: WorkMovement[], seconds: number): WorkPlace {
  const segments = workSegments(movements);
  if (!segments.length) return { kind: 'audio', index: 0, offset: 0 };
  const total = segments[segments.length - 1].end;
  const t = Number.isFinite(seconds) ? seconds : 0;
  if (t <= 0) return { kind: 'audio', index: 0, offset: 0 };
  if (t >= total) {
    const lastAudio = [...segments].reverse().find((segment) => segment.kind === 'audio');
    if (lastAudio && lastAudio.kind === 'audio') {
      return { kind: 'audio', index: lastAudio.index, offset: lastAudio.durationSec };
    }
    return { kind: 'audio', index: 0, offset: 0 };
  }
  for (let index = 0; index < segments.length; index += 1) {
    const segment = segments[index];
    const last = index === segments.length - 1;
    const inside = t >= segment.start && (t < segment.end || (last && t === segment.end));
    if (!inside) continue;
    if (segment.kind === 'audio') {
      return { kind: 'audio', index: segment.index, offset: t - segment.start };
    }
    return { kind: 'rest', afterIndex: segment.afterIndex, offset: t - segment.start };
  }
  return { kind: 'audio', index: 0, offset: 0 };
}

export function workSecondsAt(
  movements: WorkMovement[],
  index: number,
  offsetSec: number,
  resting: boolean,
  restOffsetSec = 0,
): number {
  const segments = workSegments(movements);
  const audio = segments.find(
    (segment): segment is Extract<WorkSegment, { kind: 'audio' }> =>
      segment.kind === 'audio' && segment.index === index,
  );
  if (!audio) return 0;
  if (resting) {
    const rest = segments.find(
      (segment): segment is Extract<WorkSegment, { kind: 'rest' }> =>
        segment.kind === 'rest' && segment.afterIndex === index,
    );
    if (!rest) return audio.end;
    return Math.min(rest.end, rest.start + Math.max(0, restOffsetSec));
  }
  return audio.start + Math.min(audio.durationSec, Math.max(0, offsetSec));
}

/** The zoom has landed on this movement, so a stage ratio matches its candles. */
export function movementFrameSettled(
  focus: { start: number; end: number } | null,
  movementStart: number,
  movementLength: number,
): boolean {
  if (!focus || movementLength < 1) return false;
  const end = movementStart + Math.max(movementLength - 1, 0);
  return Math.abs(focus.start - movementStart) < 0.05 && Math.abs(focus.end - end) < 0.05;
}

const MOVEMENT_START_SEC = 0.2;

export type ReplayAction =
  | { kind: 'file-start' }
  | { kind: 'movement-start'; index: number }
  | { kind: 'work-start' };

/**
 * 1D, and a single-movement span, return to the start of the file.
 * A multi-movement piece returns to the current movement first.
 * The next press, or a finished work, returns to the start of the work.
 */
export function replayAction(input: {
  span: ListenSpan;
  movementCount: number;
  movementIndex: number;
  movementTimeSec: number;
  finished: boolean;
  /** Set after a press that already parked on the current movement. */
  parkedOnMovement: boolean;
}): ReplayAction {
  const multi = input.span !== '1D' && input.movementCount > 1;
  if (!multi) return { kind: 'file-start' };
  if (input.finished || input.parkedOnMovement || input.movementTimeSec <= MOVEMENT_START_SEC) {
    return { kind: 'work-start' };
  }
  return { kind: 'movement-start', index: input.movementIndex };
}

/** WebSocket on the API host. The server rejects a page whose Origin is a different host. */
export function sonifySocketUrl(
  apiBase: string,
  query: { variant: string; source: 'live' | 'history'; symbol: string },
): string {
  const base = new URL(apiBase);
  const protocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = new URL('/v1/sonify/ws', `${protocol}//${base.host}`);
  url.searchParams.set('variant', query.variant);
  url.searchParams.set('source', query.source);
  url.searchParams.set('symbol', query.symbol);
  return url.toString();
}
