export type PeaksRefreshState = {
  pending: boolean;
  again: boolean;
};

/** Start a refresh, or remember that one more is needed after it returns. */
export function requestPeaksRefresh(state: PeaksRefreshState): boolean {
  if (state.pending) {
    state.again = true;
    return false;
  }
  state.pending = true;
  return true;
}

/** Mark the request finished and report whether another refresh is queued. */
export function finishPeaksRefresh(state: PeaksRefreshState): boolean {
  state.pending = false;
  if (!state.again) return false;
  state.again = false;
  return true;
}

export const PEAKS_POLL_BUDGET = 8;

/** Delay before the next fallback refresh; backs off once quick retries fail. */
export function peaksPollDelay(attempt: number): number {
  if (attempt <= 0) return 2000;
  if (attempt <= 2) return 3000;
  return 6000;
}

export type PeaksPollKeyInput = {
  symbol: string;
  span: string;
  variant: string;
  ensemble: string;
  index: number;
  playing: boolean;
};

/** One retry budget per identity, chapter, and pause state. */
export function peaksPollKey(input: PeaksPollKeyInput): string {
  return [
    input.symbol,
    input.span,
    input.variant,
    input.ensemble,
    input.index,
    input.playing ? 'play' : 'idle',
  ].join('|');
}
