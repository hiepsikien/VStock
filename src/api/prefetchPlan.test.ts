import { prefetchOutcome } from './prefetchPlan';

if (prefetchOutcome(206) !== 'ready') {
  throw new Error('a one-byte range answer means the file is written');
}
// A server that ignored Range still exported before answering.
if (prefetchOutcome(200) !== 'ready') {
  throw new Error('a full 200 response still means the file is written');
}
if (prefetchOutcome(204) !== 'ready') {
  throw new Error('an empty 2xx still means the export finished');
}
// These URLs cannot become valid by retrying.
if (prefetchOutcome(400) !== 'fatal') {
  throw new Error('a bad request must not be retried');
}
if (prefetchOutcome(404) !== 'fatal') {
  throw new Error('a missing movement must not be retried');
}
if (prefetchOutcome(422) !== 'fatal') {
  throw new Error('an invalid range must not be retried');
}
if (prefetchOutcome(429) !== 'retry') {
  throw new Error('a throttled prefetch must back off');
}
if (prefetchOutcome(500) !== 'retry') {
  throw new Error('a server error is retryable');
}
if (prefetchOutcome(503) !== 'retry') {
  throw new Error('a busy exporter is retryable');
}

console.log('api prefetch plan tests passed');
