import {
  PEAKS_POLL_BUDGET,
  finishPeaksRefresh,
  peaksPollDelay,
  peaksPollKey,
  requestPeaksRefresh,
  type PeaksRefreshState,
} from './peaksPrefetch';

// Coalescing: a second request while one is in flight only queues a retry.
const state: PeaksRefreshState = { pending: false, again: false };
if (!requestPeaksRefresh(state)) throw new Error('the first refresh must start');
if (requestPeaksRefresh(state)) throw new Error('a refresh was started twice');
if (!state.again) throw new Error('the queued refresh was not remembered');
if (!finishPeaksRefresh(state)) throw new Error('the queued refresh was lost');
if (state.again || state.pending) throw new Error('the refresh state was not cleared');
if (finishPeaksRefresh(state)) throw new Error('an idle state queued a refresh');

// Identity changed while a refresh was in flight: the room swaps in a fresh
// state, so the old request's finish cannot queue anything for the new work.
const inFlight: PeaksRefreshState = { pending: true, again: true };
const afterReset: PeaksRefreshState = { pending: false, again: false };
if (finishPeaksRefresh(afterReset)) {
  throw new Error('a replaced refresh state must not queue another request');
}
if (!requestPeaksRefresh(afterReset)) {
  throw new Error('the new identity must start a clean refresh');
}
// The orphaned state keeps its own flag; the component drops it with the ref.
if (!finishPeaksRefresh(inFlight)) {
  throw new Error('the orphaned refresh lost its queued flag');
}

// The fallback delays grow and stay bounded, and the budget is finite.
if (!(peaksPollDelay(0) > 0)) throw new Error('the first retry needs a delay');
if (!(peaksPollDelay(4) >= peaksPollDelay(0))) {
  throw new Error('the retry delay must not shrink');
}
if (!(PEAKS_POLL_BUDGET > 0 && Number.isFinite(PEAKS_POLL_BUDGET))) {
  throw new Error('the poll budget must be a positive number');
}

const poll = {
  symbol: 'AAM',
  span: '3M',
  variant: 'guitar',
  ensemble: 'torroba',
  index: 1,
  playing: true,
};
const key = peaksPollKey(poll);
if (peaksPollKey(poll) !== key) throw new Error('the peaks poll key is not stable');
if (peaksPollKey({ ...poll, index: 2 }) === key) {
  throw new Error('a new chapter must reset the retry budget');
}
if (peaksPollKey({ ...poll, playing: false }) === key) {
  throw new Error('pausing must reset the retry budget');
}

console.log('musicalize peaks prefetch tests passed');
