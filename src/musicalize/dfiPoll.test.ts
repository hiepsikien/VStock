import { dfiPollKey } from './dfiPoll';

const base = {
  symbol: 'AAM',
  span: '3M',
  variant: 'guitar',
  ensemble: 'torroba',
  index: 0,
  ready: true,
  name: 'Olite — Castillo — Olite',
  audible: true,
};

const key = dfiPollKey(base);
if (dfiPollKey(base) !== key) throw new Error('the poll key is not stable');

const paused = dfiPollKey({ ...base, audible: false });
if (paused === key) throw new Error('pausing must change the poll key');
if (dfiPollKey({ ...base, audible: false }) !== paused) {
  throw new Error('the idle poll key is not stable');
}

if (dfiPollKey({ ...base, ready: false }) === key) {
  throw new Error('audio readiness must change the poll key');
}
if (dfiPollKey({ ...base, name: '' }) === key) {
  throw new Error('a missing movement name must change the poll key');
}

// Pause then play returns to the same identity, but the component sees a
// different key on the way back, which resets the retry budget.
if (dfiPollKey({ ...base, audible: false }) === key) {
  throw new Error('pause and play must not share a budget');
}

console.log('dfiPoll tests passed');
