import { positionAt, positionForMovement, secondsAt } from './crossfade';

function ok(value: unknown, message: string): asserts value {
  if (!value) throw new Error(message);
}

const common = { durationSec: 32, mapDurationSec: 30, bpm: 120, beats: 4, beatType: 4 };

const at325 = positionAt(3.25, common);
ok(at325.bar === 1, `expected bar 1, got ${at325.bar}`);
ok(at325.beat === 2, `expected beat 2, got ${at325.beat}`);
ok(Math.abs(at325.fraction - 0.5) < 1e-9, `expected half beat, got ${at325.fraction}`);
ok(Math.abs(secondsAt(at325, common) - 3.25) < 1e-9, 'round trip should keep the second');

// The same bar/beat survives a tempo change, even though the second changes.
const slow = { ...common, bpm: 60 };
const fast = { ...common, bpm: 120 };
const slowAt = positionAt(secondsAt(at325, slow), slow);
const fastAt = positionAt(secondsAt(at325, fast), fast);
ok(slowAt.bar === fastAt.bar && slowAt.beat === fastAt.beat, 'bar/beat must be tempo-independent');
ok(Math.abs(slowAt.fraction - fastAt.fraction) < 1e-9, 'fraction must survive tempo change');

// Release tails never push the position past the written musical length.
const tail = positionAt(31.9, common);
ok(tail.ratio === 1, `expected clamped ratio, got ${tail.ratio}`);

// No BPM/meter metadata falls back to the written ratio.
const fallback = positionAt(7.5, { durationSec: 30 });
ok(fallback.bar === 0 && fallback.beat === 0, 'fallback has no bar grid');
ok(Math.abs(fallback.ratio - 0.25) < 1e-9, 'fallback uses the ratio');

const clamped = positionForMovement({ bar: 99, beat: 99, fraction: 0.9, ratio: 1 }, common);
ok(Math.abs(secondsAt(clamped, common) - 30) < 1e-9, 'position clamps to the movement length');

console.log('musicalize crossfade tests passed');
