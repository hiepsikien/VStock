/** Same fraction as `candle_index_at` in backend/app/sonify/playback.py. */
export function candleIndexAt(elapsedSec: number, count: number, durationSec: number): number {
  if (count <= 1) return 0;
  if (durationSec <= 0 || elapsedSec <= 0) return 0;
  if (elapsedSec >= durationSec) return count - 1;
  return Math.min(count - 1, Math.floor((elapsedSec / durationSec) * count));
}

/** Same hold as `ambient_daily_candle_index`. Every 1D variant uses this 36-bar frame. */
export function ambientDailyCandleIndexAt(
  elapsedSec: number,
  count: number,
  durationSec: number,
): number {
  if (count <= 1) return 0;
  if (durationSec <= 0 || elapsedSec <= 0) return 0;
  const introEnd = (durationSec * 2) / 36;
  const outroStart = (durationSec * 32) / 36;
  if (elapsedSec < introEnd) return 0;
  if (elapsedSec >= outroStart) return count - 1;
  const span = outroStart - introEnd;
  if (span <= 0) return 0;
  const fraction = (elapsedSec - introEnd) / span;
  if (fraction >= 1) return count - 1;
  return Math.min(count - 1, Math.floor(fraction * count));
}

/** Visible listen chart: the whole current movement, then the opening of the next.

The split is about 70% current and 30% next, counted in the candles that
were sonified, so each impulse lines up with the note it produced.
*/
export function listenWindow(
  current: number[],
  next: number[] | null,
): { prices: number[]; playedCount: number } {
  if (!next || next.length === 0 || current.length < 2) {
    return { prices: current, playedCount: current.length };
  }
  const peek = Math.max(1, Math.round((current.length * 0.3) / 0.7));
  return {
    prices: current.concat(next.slice(0, peek)),
    playedCount: current.length,
  };
}

/** Keep the open-session poll parked only while this take can still resume.

The chart may keep the last candle on screen after the file ends. That resting
playhead must not block the next minute refresh.
*/
export function playheadHoldsPoll(input: {
  playing: boolean;
  currentTime: number;
  mapDurationSec: number;
  fileDurationSec: number;
  didJustFinish?: boolean;
  started?: boolean;
}): boolean {
  const heard = Boolean(input.started) || input.playing || input.currentTime > 0.05;
  if (!heard) return false;
  if (input.playing) return true;
  if (input.didJustFinish) return false;
  const fileEnd = input.fileDurationSec > 0 ? input.fileDurationSec : input.mapDurationSec;
  if (fileEnd > 0 && input.currentTime >= fileEnd - 0.4) return false;
  return true;
}
