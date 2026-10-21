/** Same fraction as `candle_index_at` in backend/app/sonify/playback.py. */
export function candleIndexAt(elapsedSec: number, count: number, durationSec: number): number {
  if (count <= 1) return 0;
  if (durationSec <= 0 || elapsedSec <= 0) return 0;
  if (elapsedSec >= durationSec) return count - 1;
  return Math.min(count - 1, Math.floor((elapsedSec / durationSec) * count));
}

/** Chart index for one movement. A rest holds the playhead on the movement that just ended. */
export function spanChartIndex(input: {
  elapsedSec: number;
  durationSec: number;
  chartStart: number;
  chartEnd: number;
  priceCount: number;
  holdAtEnd: boolean;
}): number {
  const count = Math.max(1, input.priceCount);
  const fraction =
    input.holdAtEnd || input.durationSec <= 0 || input.elapsedSec >= input.durationSec
      ? 1
      : Math.max(0, input.elapsedSec) / input.durationSec;
  const ratio = input.chartStart + (input.chartEnd - input.chartStart) * fraction;
  return Math.min(count - 1, Math.max(0, Math.floor(ratio * count)));
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
