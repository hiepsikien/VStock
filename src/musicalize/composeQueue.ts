/** Pure decisions for composing the next chapters of a long-form piece. */

/** Heard seconds before the room treats the listener as staying for the work. */
export const COMMIT_SEC = 20;
/** Or this fraction of the current chapter, whichever comes first. */
export const COMMIT_RATIO = 0.08;
/** Hard ceiling on chapters prepared ahead. */
export const MAX_AHEAD_HARD = 3;
/**
 * Chapters prepared ahead today. Stays at 1 until measurements show a render
 * ratio above 0.7 and the server can prioritise playback over prefetch.
 */
export const AHEAD_CAP = 1;

export type CommitReason = 'seek' | 'dwell' | 'ratio' | null;

/**
 * Whether the listener has committed to hearing the work out.
 *
 * `audible` means the chapter has been heard at least once, not that it is
 * playing now: the room does not clear it on pause. `heardSec` is the
 * movement clock, so a pause stops it from growing.
 */
export function commitReason(input: {
  audible: boolean;
  heardSec: number;
  movementSec: number;
  seeked: boolean;
}): CommitReason {
  if (!input.audible) return null;
  if (input.seeked) return 'seek';
  if (input.heardSec >= COMMIT_SEC) return 'dwell';
  if (input.movementSec > 0 && input.heardSec / input.movementSec >= COMMIT_RATIO) {
    return 'ratio';
  }
  return null;
}

/**
 * Chapters to keep prepared ahead. The render ratio comes from the server and
 * excludes queue wait, so a busy server cannot raise the depth on its own.
 *
 * Production keeps `AHEAD_CAP` at 1, so this returns 1 until P2 raises the cap
 * after adding server-side playback priority. The ratio and paused branches are
 * covered by tests so the P2 switch is a one-line change.
 */
export function lookaheadDepth(input: {
  ratio: number;
  paused: boolean;
  committed: boolean;
  max?: number;
}): number {
  if (!input.committed) return 1;
  const ratio = Number.isFinite(input.ratio) && input.ratio > 0 ? input.ratio : 0;
  const base = ratio > 0.7 ? 2 : 1;
  const wanted = input.paused ? base + 1 : base;
  const cap = Math.max(1, Math.min(input.max ?? AHEAD_CAP, MAX_AHEAD_HARD));
  return Math.min(cap, wanted);
}

/**
 * Chapters that still need a file inside a fixed window after the heard
 * chapter. The player owns the current chapter; this list never contains it.
 * The window is `currentIndex + 1 … currentIndex + depth`, so a finished
 * chapter does not slide the queue forward and render the whole work.
 */
export function queueTargets(input: {
  currentIndex: number;
  count: number;
  urls: string[];
  ready: boolean[];
  depth: number;
  done: ReadonlySet<string>;
  cooldownUntil: ReadonlyMap<number, { url: string; until: number }>;
  now: number;
}): number[] {
  const out: number[] = [];
  const ahead = Math.max(0, Math.min(input.depth, MAX_AHEAD_HARD));
  const last = Math.min(input.count - 1, input.currentIndex + ahead);
  for (let index = input.currentIndex + 1; index <= last; index += 1) {
    const url = input.urls[index];
    if (!url || input.ready[index] || input.done.has(url)) continue;
    const cooldown = input.cooldownUntil.get(index);
    if (cooldown && cooldown.url === url && cooldown.until > input.now) continue;
    out.push(index);
  }
  return out;
}

/** A render for a chapter the listener has already passed is wasted work. */
export function shouldAbortTarget(target: number | null, currentIndex: number): boolean {
  return target != null && target < currentIndex;
}

/**
 * Whether a background render must be dropped when the heard chapter changes.
 * Keep a render for the chapter being entered, and keep future renders only
 * while that chapter already has a file (otherwise the player needs the single
 * export slot first).
 */
export function shouldAbortOnIndexChange(input: {
  flightIndex: number | null;
  currentIndex: number;
  currentReady: boolean;
  depth: number;
}): boolean {
  if (input.flightIndex == null) return false;
  if (shouldAbortTarget(input.flightIndex, input.currentIndex)) return true;
  const last = input.currentIndex + Math.max(1, Math.min(input.depth, MAX_AHEAD_HARD));
  if (input.flightIndex > last) return true;
  return !input.currentReady && input.flightIndex !== input.currentIndex;
}

/**
 * The player has asked for the heard chapter, so the pump may look ahead.
 * `mediaIndex` must match: on a chapter change the old duration is still set
 * for one render and must not unlock the next chapter's prefetch.
 */
export function playerHasStarted(input: {
  ready: boolean;
  audible: boolean;
  resting: boolean;
  mediaIndex: number;
  currentIndex: number;
  mediaDurationSec: number;
}): boolean {
  if (input.ready || input.audible || input.resting) return true;
  return input.mediaIndex === input.currentIndex && input.mediaDurationSec > 0;
}

/** Backoff before retrying a failed render, in milliseconds. 0 means cool down. */
export function retryDelay(attempt: number): number {
  if (attempt <= 1) return 2000;
  if (attempt === 2) return 5000;
  if (attempt === 3) return 10000;
  return 0;
}

/**
 * Mark one chapter ready only when the URL still matches. A re-plan can change
 * the fingerprint, and a stale ready would hide an unrendered file.
 */
export function markMovementReady<M extends { audioUrl: string; ready: boolean; renderSec?: number }>(
  movements: M[],
  index: number,
  url: string,
  renderSec: number,
): M[] {
  const current = movements[index];
  if (!current || current.audioUrl !== url) return movements;
  const known = Number.isFinite(renderSec) && renderSec > 0;
  if (current.ready && (!known || current.renderSec === renderSec)) return movements;
  const next = movements.slice();
  next[index] = { ...current, ready: true, ...(known ? { renderSec } : {}) };
  return next;
}

/** Largest measured render ratio in a plan. Zero means no measurement yet. */
export function maxRenderRatio(movements: Array<{ renderRatio?: number }>): number {
  let found = 0;
  for (const movement of movements) {
    const value = movement.renderRatio;
    if (typeof value === 'number' && Number.isFinite(value) && value > found) found = value;
  }
  return found;
}
