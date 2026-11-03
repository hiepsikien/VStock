/**
 * Small pure transitions for the two-slot A/B player. Keeping them here gives
 * the mobile player a testable seam without pulling in a React renderer.
 */

export type PlayerSlot = {
  url: string | null;
  startSec: number;
  play: boolean;
  gain: number;
};

export function loadedSlot(url: string, startSec: number, wantPlay: boolean): PlayerSlot {
  return { url, startSec, play: wantPlay, gain: wantPlay ? 1 : 0 };
}

/** Play after a paused load/scrub. The old player kept a silent gain of 0. */
export function resumedSlot(slot: PlayerSlot): PlayerSlot {
  return { ...slot, play: true, gain: 1 };
}

/** A crossfade target is only audible when the room still wants playback. */
export function completedSlot(slot: PlayerSlot, play: boolean): PlayerSlot {
  return { ...slot, play, gain: play ? 1 : 0 };
}

/** `audible` is a UI/DFI gate, not a mute flag. */
export function shouldAnnounceAudible(ready: boolean, wantPlay: boolean): boolean {
  return ready && wantPlay;
}
