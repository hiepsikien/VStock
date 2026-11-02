export type VolumeScale = 'linear' | 'sqrt' | 'log';

/**
 * Nearest-rank cap over positive values. `floor` is deliberate: for any window
 * with at least two positive bars, P99.9 then excludes the single largest bar
 * instead of silently becoming the maximum.
 */
export function volumeCap(values: number[], percentile: number): number {
  const sorted = values.filter((value) => value > 0).sort((a, b) => a - b);
  if (!sorted.length) return 0;
  const rank = Math.min(
    sorted.length - 1,
    Math.max(0, Math.floor(percentile * (sorted.length - 1))),
  );
  return sorted[rank] ?? 0;
}

export function volumeRatio(
  value: number,
  ceiling: number,
  scale: VolumeScale,
): number {
  if (!(ceiling > 0)) return 0;
  const safe = Math.min(Math.max(0, value), ceiling);
  if (scale === 'log') return Math.log1p(safe) / Math.log1p(ceiling);
  if (scale === 'sqrt') return Math.sqrt(safe / ceiling);
  return safe / ceiling;
}
