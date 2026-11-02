export type PrefetchResponsePlan = 'range' | 'discard' | 'reject';

/**
 * How to read a prefetch response. A 206 is a one-byte range answer. A 200
 * means the server ignored Range: the export still ran, but the body is the
 * whole movement, so drop it instead of downloading it twice. Anything else is
 * a failed render.
 */
export function prefetchResponsePlan(
  status: number,
  ok: boolean,
): PrefetchResponsePlan {
  if (status === 206) return 'range';
  if (ok) return 'discard';
  return 'reject';
}
