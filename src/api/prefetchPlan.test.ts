import { prefetchResponsePlan } from './prefetchPlan';

// A range answer is the one-byte path and must be consumed.
if (prefetchResponsePlan(206, true) !== 'range') {
  throw new Error('206 must be read as a range response');
}

// A server without range support still wrote the file; never download it twice.
if (prefetchResponsePlan(200, true) !== 'discard') {
  throw new Error('200 must discard the duplicate body');
}
if (prefetchResponsePlan(204, true) !== 'discard') {
  throw new Error('another 2xx must still count as rendered');
}

// A failed render is not a prefetch.
if (prefetchResponsePlan(404, false) !== 'reject') {
  throw new Error('a 404 must not be treated as a render');
}
if (prefetchResponsePlan(503, false) !== 'reject') {
  throw new Error('a 503 must not be treated as a render');
}

console.log('api prefetch plan tests passed');
