import {
  AHEAD_CAP,
  COMMIT_SEC,
  commitReason,
  lookaheadDepth,
  markMovementReady,
  maxRenderRatio,
  playerHasStarted,
  queueTargets,
  retryDelay,
  shouldAbortOnIndexChange,
  shouldAbortTarget,
} from './composeQueue';

// Commitment: needs an audible chapter, then dwell, ratio, or an explicit seek.
if (commitReason({ audible: false, heardSec: 60, movementSec: 200, seeked: true }) !== null) {
  throw new Error('an inaudible chapter cannot commit');
}
if (commitReason({ audible: true, heardSec: 0, movementSec: 200, seeked: false }) !== null) {
  throw new Error('a paused chapter at zero seconds has not committed');
}
if (commitReason({ audible: true, heardSec: COMMIT_SEC, movementSec: 600, seeked: false }) !== 'dwell') {
  throw new Error('dwell must commit at the threshold');
}
if (commitReason({ audible: true, heardSec: 12, movementSec: 100, seeked: false }) !== 'ratio') {
  throw new Error('8% of a short chapter must commit');
}
if (commitReason({ audible: true, heardSec: 2, movementSec: 0, seeked: false }) !== null) {
  throw new Error('a zero-length chapter must not divide by zero');
}
if (commitReason({ audible: true, heardSec: 1, movementSec: 600, seeked: true }) !== 'seek') {
  throw new Error('a seek commits immediately');
}

// Depth: one by default, two only with a measured ratio and a raised cap.
if (lookaheadDepth({ ratio: 0, paused: false, committed: true }) !== 1) {
  throw new Error('an unmeasured render keeps depth at one');
}
if (lookaheadDepth({ ratio: 0.8, paused: false, committed: false, max: 3 }) !== 1) {
  throw new Error('an uncommitted listener keeps depth at one');
}
if (lookaheadDepth({ ratio: 0.8, paused: false, committed: true }) !== AHEAD_CAP) {
  throw new Error('today the cap keeps depth at one even for a slow render');
}
if (lookaheadDepth({ ratio: 0.8, paused: false, committed: true, max: 2 }) !== 2) {
  throw new Error('a slow render may use depth two once the cap is raised');
}
if (lookaheadDepth({ ratio: 0.8, paused: true, committed: true, max: 3 }) !== 3) {
  throw new Error('a paused room may prepare one more chapter');
}
if (lookaheadDepth({ ratio: 0.8, paused: true, committed: true, max: 9 }) !== 3) {
  throw new Error('depth must never pass the hard ceiling');
}
if (lookaheadDepth({ ratio: Number.NaN, paused: false, committed: true }) !== 1) {
  throw new Error('a missing ratio is treated as zero');
}

const urls = ['u0', 'u1', 'u2', 'u3', 'u4'];
const cooldown = new Map<number, { url: string; until: number }>();
cooldown.set(3, { url: 'u3', until: 2_000 });

// The player owns the heard chapter, ready and done chapters are skipped, and a
// cooldown only applies to the URL it was recorded for.
const targets = queueTargets({
  currentIndex: 0,
  count: 5,
  urls,
  ready: [true, false, true, false, false],
  depth: 1,
  done: new Set(['u4']),
  cooldownUntil: cooldown,
  now: 1_000,
});
if (targets.join(',') !== '1') {
  throw new Error(`queue targets were ${targets.join(',')}`);
}

// A ready next chapter must not slide the window forward into chapter 3.
const windowed = queueTargets({
  currentIndex: 0,
  count: 5,
  urls,
  ready: [true, true, false, false, false],
  depth: 1,
  done: new Set(),
  cooldownUntil: new Map(),
  now: 0,
});
if (windowed.length !== 0) {
  throw new Error(`depth one must only look at chapter 1, got ${windowed.join(',')}`);
}

const afterCooldown = queueTargets({
  currentIndex: 2,
  count: 5,
  urls,
  ready: [true, true, true, false, false],
  depth: 1,
  done: new Set(),
  cooldownUntil: cooldown,
  now: 2_001,
});
if (afterCooldown.join(',') !== '3') {
  throw new Error(`an expired cooldown must retry, got ${afterCooldown.join(',')}`);
}

const capped = queueTargets({
  currentIndex: 0,
  count: 5,
  urls,
  ready: [true, false, false, false, false],
  depth: 9,
  done: new Set(),
  cooldownUntil: new Map(),
  now: 0,
});
if (capped.length !== 3) {
  throw new Error(`depth must cap at three, got ${capped.length}`);
}

// Aborting: only chapters behind the heard one. Never the chapter being entered.
if (!shouldAbortTarget(1, 3)) throw new Error('a passed chapter must abort');
if (shouldAbortTarget(3, 3)) throw new Error('the heard chapter must not abort');
if (shouldAbortTarget(4, 3)) throw new Error('a future chapter must not abort');
if (shouldAbortTarget(null, 3)) throw new Error('no in-flight render means no abort');

// Index changes: drop passed work, drop work outside the new window, and drop
// a future render when the chapter being entered still needs the export slot.
if (!shouldAbortOnIndexChange({ flightIndex: 1, currentIndex: 3, currentReady: true, depth: 1 })) {
  throw new Error('a passed render must abort on a jump forward');
}
if (shouldAbortOnIndexChange({ flightIndex: 3, currentIndex: 3, currentReady: false, depth: 1 })) {
  throw new Error('the render for the heard chapter must survive');
}
if (shouldAbortOnIndexChange({ flightIndex: 4, currentIndex: 3, currentReady: true, depth: 1 })) {
  throw new Error('a render inside the window survives when the heard chapter is ready');
}
if (!shouldAbortOnIndexChange({ flightIndex: 5, currentIndex: 3, currentReady: true, depth: 1 })) {
  throw new Error('a render outside the window must abort on a jump back');
}
if (!shouldAbortOnIndexChange({ flightIndex: 4, currentIndex: 3, currentReady: false, depth: 2 })) {
  throw new Error('an unready chapter must not wait behind a later render');
}
if (shouldAbortOnIndexChange({ flightIndex: null, currentIndex: 3, currentReady: false, depth: 1 })) {
  throw new Error('no in-flight render means no index-change abort');
}

// Player started: a duration from the previous chapter must not unlock the next.
if (
  playerHasStarted({
    ready: false,
    audible: false,
    resting: false,
    mediaIndex: 0,
    currentIndex: 1,
    mediaDurationSec: 200,
  })
) {
  throw new Error('a stale duration from the previous chapter must not count as started');
}
if (
  !playerHasStarted({
    ready: false,
    audible: false,
    resting: false,
    mediaIndex: 1,
    currentIndex: 1,
    mediaDurationSec: 200,
  })
) {
  throw new Error('a duration for this chapter means the player started');
}
if (
  !playerHasStarted({
    ready: true,
    audible: false,
    resting: false,
    mediaIndex: -1,
    currentIndex: 1,
    mediaDurationSec: 0,
  })
) {
  throw new Error('a ready chapter needs no player wait');
}
if (
  !playerHasStarted({
    ready: false,
    audible: true,
    resting: false,
    mediaIndex: -1,
    currentIndex: 1,
    mediaDurationSec: 0,
  })
) {
  throw new Error('audible means the player started');
}
if (
  !playerHasStarted({
    ready: false,
    audible: false,
    resting: true,
    mediaIndex: -1,
    currentIndex: 1,
    mediaDurationSec: 0,
  })
) {
  throw new Error('a rest unmounts the player, so the pump may look ahead');
}

if (retryDelay(1) !== 2000 || retryDelay(2) !== 5000 || retryDelay(3) !== 10000) {
  throw new Error('retry backoff must be 2s, 5s, 10s');
}
if (retryDelay(4) !== 0) throw new Error('the fourth failure must cool down');

const movements = [
  { audioUrl: 'a', ready: false, durationSec: 200, renderSec: 0 },
  { audioUrl: 'b', ready: false, durationSec: 200, renderSec: 0 },
];
const ready = markMovementReady(movements, 1, 'b', 30);
if (!ready[1].ready || ready[0].ready) {
  throw new Error('only the matching chapter may be marked ready');
}
if (ready[1].durationSec !== 200) {
  throw new Error('marking ready must not change the duration');
}
if (markMovementReady(movements, 1, 'stale-url', 30) !== movements) {
  throw new Error('a changed URL must leave the manifest untouched');
}
const readyNoTiming = markMovementReady(movements, 1, 'b', 0);
if (!readyNoTiming[1].ready || readyNoTiming[1].renderSec !== 0) {
  throw new Error('unknown render time stays zero');
}
if (markMovementReady(readyNoTiming, 1, 'b', 0) !== readyNoTiming) {
  throw new Error('marking an already-ready chapter must keep the reference');
}

if (maxRenderRatio([{ renderRatio: 0.2 }, { renderRatio: 0.5 }, {}]) !== 0.5) {
  throw new Error('the largest render ratio must win');
}
if (maxRenderRatio([]) !== 0) {
  throw new Error('an empty plan has no render ratio');
}

console.log('musicalize compose queue tests passed');
