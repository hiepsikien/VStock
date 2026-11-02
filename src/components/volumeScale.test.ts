import { volumeCap, volumeRatio } from './volumeScale';

function equal(actual: number, expected: number, label = '') {
  if (Math.abs(actual - expected) > 1e-6) {
    throw new Error(`${label} expected ${expected}, got ${actual}`);
  }
}

// Small windows: floor keeps P99.9 below the maximum so the cap is not a
// no-op. The largest bar is still drawn at full height by the caller's clamp.
equal(volumeCap([1, 2, 3, 4], 0.999), 3, 'P99.9 caps below the max');
equal(volumeCap([1, 2, 3, 4], 0.98), 3, 'P98 on a small window');
equal(volumeCap([0, 0, 5], 0.5), 5, 'zeros do not win the percentile');
equal(volumeCap([0, 0], 0.98), 0, 'all zeros have no cap');

const sixty = Array.from({ length: 60 }, (_, index) => index + 1);
equal(volumeCap(sixty, 0.98), 58, 'P98 at n=60');
equal(volumeCap(sixty, 0.999), 59, 'P99.9 at n=60');

equal(volumeRatio(50, 100, 'linear'), 0.5, 'linear ratio');
equal(volumeRatio(50, 100, 'sqrt'), Math.sqrt(0.5), 'sqrt ratio');
equal(volumeRatio(100, 100, 'sqrt'), 1, 'cap reaches full height');
equal(volumeRatio(0, 100, 'sqrt'), 0, 'zero stays at the baseline');

console.log('volume scale tests passed');
