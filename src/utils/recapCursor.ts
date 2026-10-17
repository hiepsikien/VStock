/** Same fraction as `candle_index_at` in backend/app/sonify/playback.py. */
export function candleIndexAt(elapsedSec: number, count: number, durationSec: number): number {
  if (count <= 1) return 0;
  if (durationSec <= 0 || elapsedSec <= 0) return 0;
  if (elapsedSec >= durationSec) return count - 1;
  return Math.min(count - 1, Math.floor((elapsedSec / durationSec) * count));
}
