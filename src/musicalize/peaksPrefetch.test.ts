import {
  PEAKS_POLL_BUDGET,
  finishPeaksRefresh,
  needsPrefetch,
  peaksPollDelay,
  peaksPollKey,
  prefetchKey,
  requestPeaksRefresh,
  stalePrefetchTargets,
  type PeaksRefreshState,
} from './peaksPrefetch';

// A chapter whose file is written already has its envelope from the plan.
if (needsPrefetch({ ready: true, peaks: [0.4, 0.7] })) {
  throw new Error('a ready movement with peaks needs no prefetch');
}
if (!needsPrefetch({ ready: true, peaks: [] })) {
  throw new Error('a ready movement without peaks still needs a render');
}
if (!needsPrefetch({ ready: false, peaks: [] })) {
  throw new Error('a missing file needs a render');
}
if (needsPrefetch(null) || needsPrefetch(undefined)) {
  throw new Error('a missing movement is not a prefetch target');
}

if (prefetchKey('AAM|3M', 2) !== 'AAM|3M|2') {
  throw new Error('prefetch keys must include the identity and index');
}
if (prefetchKey('AAM|3M', 2) === prefetchKey('AAM|1M', 2)) {
  throw new Error('a new span must not reuse prefetch keys');
}

// Keep the chapter being heard and the next one; drop skipped targets.
const stale = stalePrefetchTargets([0, 1, 2, 3], 2);
if (stale.join(',') !== '0,1') {
  throw new Error(`stale targets were ${stale.join(',')}`);
}
if (stalePrefetchTargets([1, 2], 0).join(',') !== '2') {
  // 1 is the next chapter at index 0, so only 2 is stale there.
  throw new Error('the next chapter must survive at index 0');
}

// Coalescing: a second request while one is in flight only queues a retry.
const state: PeaksRefreshState = { pending: false, again: false };
if (!requestPeaksRefresh(state)) throw new Error('the first refresh must start');
if (requestPeaksRefresh(state)) throw new Error('a refresh was started twice');
if (!state.again) throw new Error('the queued refresh was not remembered');
if (!finishPeaksRefresh(state)) throw new Error('the queued refresh was lost');
if (state.again || state.pending) throw new Error('the refresh state was not cleared');
if (finishPeaksRefresh(state)) throw new Error('an idle state queued a refresh');

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
