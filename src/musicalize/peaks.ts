import { workSegments } from './seek';

type WaveMovement = {
  durationSec: number;
  restAfterSec: number;
  peaks?: number[] | null;
  peakLevel?: number | null;
};

export type WavePeaks = {
  peaks: number[] | null;
  level: number;
};

export const WORK_WAVEFORM_BUCKETS = 96;

/**
 * Audio peaks for the whole work, in work-clock order. Each movement's file is
 * sampled into its audio segment; rests stay silent. Movements whose file has
 * not been written yet contribute nothing, so the bar fills in as they render.
 *
 * Each file's envelope is normalized to its own loudest bucket. `peakLevel`
 * scales it back to the work's loudest movement so a quiet movement does not
 * look as loud as a loud one.
 */
export function workWaveform(
  movements: WaveMovement[],
  overrides?: Array<Partial<WavePeaks> | null | undefined> | null,
  buckets = WORK_WAVEFORM_BUCKETS,
): number[] | null {
  if (!movements.length || buckets < 1) return null;
  const segments = workSegments(movements);
  const total = segments.length ? segments[segments.length - 1].end : 0;
  if (!(total > 0)) return null;

  const resolved = movements.map((movement, index) => {
    const override = overrides?.[index];
    const peaks =
      override?.peaks && override.peaks.length
        ? override.peaks
        : movement.peaks && movement.peaks.length
          ? movement.peaks
          : null;
    if (!peaks) return null;
    return {
      peaks,
      level: override?.level ?? movement.peakLevel ?? 0,
    };
  });
  const loudest = resolved.reduce(
    (max, item) => (item && item.level > max ? item.level : max),
    0,
  );

  const bars = new Array<number>(buckets).fill(0);
  let any = false;
  for (let bucket = 0; bucket < buckets; bucket += 1) {
    const at = ((bucket + 0.5) / buckets) * total;
    const segment =
      segments.find((item) => at >= item.start && at < item.end) ??
      segments[segments.length - 1];
    if (!segment || segment.kind !== 'audio' || segment.durationSec <= 0) continue;
    const source = resolved[segment.index];
    if (!source) continue;
    const ratio = (at - segment.start) / segment.durationSec;
    const index = Math.min(
      source.peaks.length - 1,
      Math.max(0, Math.floor(ratio * source.peaks.length)),
    );
    const raw = Number(source.peaks[index]);
    if (!Number.isFinite(raw)) continue;
    const levelScale =
      loudest > 0 && source.level > 0 ? source.level / loudest : 1;
    bars[bucket] = Math.min(1, Math.max(0, raw * levelScale));
    any = true;
  }
  return any ? bars : null;
}
