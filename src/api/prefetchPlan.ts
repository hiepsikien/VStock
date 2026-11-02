export type PrefetchResponsePlan = 'range' | 'discard' | 'reject';

/**
 * How to read a prefetch response. A 206 is a one-byte range answer. Any other
 * 2xx means the server ignored Range: the export still ran, but the body is the
 * whole movement, so drop it instead of downloading it twice. The rest failed.
 */
export function prefetchResponsePlan(status: number): PrefetchResponsePlan {
  if (status === 206) return 'range';
  if (status >= 200 && status < 300) return 'discard';
  return 'reject';
}
