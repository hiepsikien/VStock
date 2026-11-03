export type PrefetchOutcome = 'ready' | 'retry' | 'fatal';

/**
 * How to read a prefetch response. A 206 is a one-byte range answer. Any other
 * 2xx means the server ignored Range: the export still ran, so the file is
 * written and the body can be dropped. 400/404/422 mean the URL cannot work;
 * everything else is worth another attempt.
 */
export function prefetchOutcome(status: number): PrefetchOutcome {
  if (status >= 200 && status < 300) return 'ready';
  if (status === 400 || status === 404 || status === 422) return 'fatal';
  return 'retry';
}
