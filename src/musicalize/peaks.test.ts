import { workWaveform } from './peaks';
import { workDuration } from './seek';

function deepEqual(actual: unknown, expected: unknown, label = '') {
  const left = JSON.stringify(actual);
  const right = JSON.stringify(expected);
  if (left !== right) throw new Error(`${label} expected ${right}, got ${left}`);
}

const movements = [
  { durationSec: 10, restAfterSec: 2, peaks: [1, 1] },
  { durationSec: 10, restAfterSec: 0, peaks: [0, 0] },
];

const wave = workWaveform(movements, null, 11);
if (!wave) throw new Error('waveform missing');
deepEqual(wave.length, 11, 'bucket count');
// The 2s rest sits between the two audio segments and stays silent.
deepEqual(wave[5], 0, 'rest bucket');
if (wave[0] !== 1 || wave[9] !== 0) throw new Error('segment peaks not mapped');
deepEqual(workDuration(movements), 22, 'work duration includes rest');

const partial = workWaveform(
  [
    { durationSec: 10, restAfterSec: 0, peaks: [] },
    { durationSec: 10, restAfterSec: 0, peaks: [0.5] },
  ],
  null,
  4,
);
deepEqual(partial, [0, 0, 0.5, 0.5], 'unrendered movement leaves a gap');

if (workWaveform([{ durationSec: 10, restAfterSec: 0 }], null, 4) !== null) {
  throw new Error('no peaks should return null, not a flat waveform');
}

const scaled = workWaveform(
  [
    { durationSec: 10, restAfterSec: 0, peaks: [1], peakLevel: 0.2 },
    { durationSec: 10, restAfterSec: 0, peaks: [1], peakLevel: 0.4 },
  ],
  null,
  2,
);
deepEqual(scaled, [0.5, 1], 'quiet movement scales against the loudest');

console.log('musicalize peaks tests passed');
