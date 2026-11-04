import {
  completedSlot,
  loadedSlot,
  resumedSlot,
  shouldAnnounceAudible,
} from './playerState';

function ok(value: unknown, message: string): asserts value {
  if (!value) throw new Error(message);
}

const paused = loadedSlot('https://example.test/a.m4a', 12, false);
ok(paused.play === false && paused.gain === 0, 'paused load must stay silent');

const resumed = resumedSlot(paused);
ok(resumed.play === true && resumed.gain === 1, 'resume must restore full gain');

const crossed = completedSlot(paused, true);
ok(crossed.play === true && crossed.gain === 1, 'finished crossfade is audible');

const pausedCross = completedSlot(paused, false);
ok(pausedCross.play === false && pausedCross.gain === 0, 'paused crossfade stays silent');

ok(shouldAnnounceAudible(true, true), 'ready + playing must mark audible');
ok(!shouldAnnounceAudible(true, false), 'ready but paused is not audible');
ok(!shouldAnnounceAudible(false, true), 'playing before ready is not audible');

console.log('musicalize player state tests passed');
