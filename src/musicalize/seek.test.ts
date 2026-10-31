import { ambientDailyCandleIndexAt, spanCandleIndexAt } from '../utils/recapCursor';
import { whenFor } from './liveSynth';
import { liveListRows, pickLiveRow } from './liveRows';
import {
  dailyCandleForSecond,
  dailyMapClock,
  dailyStageSeek,
  movementFrameSettled,
  placeOnWork,
  replayAction,
  scrubberSeek,
  shouldArmFinish,
  shouldResumePlay,
  sonifySocketUrl,
  spanCandleForSecond,
  spanMapClock,
  spanStageSeek,
  workDuration,
  workSecondsAt,
  workSegments,
} from './seek';

function equal<T>(actual: T, expected: T, label = '') {
  if (actual !== expected) {
    throw new Error(`${label} expected ${String(expected)}, got ${String(actual)}`);
  }
}

function deepEqual(actual: unknown, expected: unknown, label = '') {
  const left = JSON.stringify(actual);
  const right = JSON.stringify(expected);
  if (left !== right) throw new Error(`${label} expected ${right}, got ${left}`);
}

const duration = 340;
equal(dailyStageSeek(duration, 0), 20, 'daily r=0');
equal(dailyStageSeek(duration, 1), 320, 'daily r=1');
equal(dailyStageSeek(duration, 0.25), 95, 'daily r=0.25');
equal(dailyStageSeek(duration, -2), 20, 'daily clamp low');
equal(dailyStageSeek(duration, 4), 320, 'daily clamp high');

const count = 120;
equal(dailyCandleForSecond(dailyStageSeek(duration, 0), count, duration), 0, 'stage start candle');
equal(
  dailyCandleForSecond(dailyStageSeek(duration, 1), count, duration),
  count - 1,
  'stage end candle',
);
equal(ambientDailyCandleIndexAt(scrubberSeek(duration, 0.03), count, duration), 0, 'scrubber sticks in intro');
if (dailyCandleForSecond(dailyStageSeek(duration, 0.03), count, duration) <= 0) {
  throw new Error('stage ratio inside the body must leave the first candle');
}
const mid = dailyStageSeek(duration, 0.5);
equal(mid, 170, 'daily midpoint second');
const midCandle = dailyCandleForSecond(mid, count, duration);
if (midCandle < 40 || midCandle > 80) {
  throw new Error(`mid candle ${midCandle} is not near the middle of ${count}`);
}

const fileTail = 374;
const written = 340;
const tailCandles = 200;
equal(dailyMapClock(written, fileTail, 380), written, 'stage clock is the written map');
equal(dailyMapClock(0, fileTail, 380), fileTail, 'missing map falls back to the file');
equal(dailyMapClock(0, 0, 380), 380, 'missing file falls back to the element');
const onMap = dailyCandleForSecond(dailyStageSeek(dailyMapClock(written, fileTail), 0.5), tailCandles, written);
const onFile = dailyCandleForSecond(dailyStageSeek(fileTail, 0.5), tailCandles, written);
equal(onMap, 100, 'map clock lands on the candle under the finger');
if (onFile === onMap) {
  throw new Error('seeking with the file length must miss the playhead clock when a tail is present');
}

equal(movementFrameSettled({ start: 10, end: 24 }, 10, 15), true, 'settled movement');
equal(movementFrameSettled({ start: 0, end: 40 }, 10, 15), false, 'zoom still open');
equal(movementFrameSettled(null, 0, 15), false, 'no focus yet');

equal(spanMapClock(260, 263), 260, 'span chart follows the written map');
equal(spanMapClock(0, 263), 263, 'span map falls back to the file');
equal(spanCandleForSecond(130, 20, spanMapClock(260, 263), 0, 0), 10, 'span midpoint candle');
equal(spanCandleForSecond(263, 20, spanMapClock(260, 263), 0, 0), 19, 'span tail rests on the last candle');
equal(spanStageSeek(spanMapClock(260, 263), 0, 0, 1), 260, 'span stage ends on the map');

equal(spanStageSeek(90, 0, 0, 0), 0, 'week r=0');
equal(spanStageSeek(90, 0, 0, 1), 90, 'week r=1');
equal(spanStageSeek(90, 0, 0, 0.5), 45, 'week r=0.5');
equal(spanCandleForSecond(spanStageSeek(90, 0, 0, 0), 10, 90, 0, 0), 0, 'week start candle');
equal(spanCandleForSecond(spanStageSeek(90, 0, 0, 1), 10, 90, 0, 0), 9, 'week end candle');

const spanDuration = 100;
const warmup = 10;
const cooldown = 10;
equal(spanStageSeek(spanDuration, warmup, cooldown, 0), 10, 'span body start');
equal(spanStageSeek(spanDuration, warmup, cooldown, 1), 90, 'span body end');
equal(spanStageSeek(spanDuration, warmup, cooldown, 0.5), 50, 'span body mid');
equal(
  spanCandleIndexAt(spanStageSeek(spanDuration, warmup, cooldown, 0), 40, spanDuration, warmup, cooldown),
  0,
  'span stage r=0 candle',
);
equal(
  spanCandleIndexAt(spanStageSeek(spanDuration, warmup, cooldown, 1), 40, spanDuration, warmup, cooldown),
  39,
  'span stage r=1 candle',
);
equal(scrubberSeek(spanDuration, 0), 0, 'scrubber start is the file start');
equal(
  spanCandleIndexAt(scrubberSeek(spanDuration, 0.05), 40, spanDuration, warmup, cooldown),
  0,
  'linear scrubber stays in warmup',
);

const movements = [
  { durationSec: 10, restAfterSec: 6 },
  { durationSec: 8, restAfterSec: 5 },
];
deepEqual(
  workSegments(movements),
  [
    { kind: 'audio', index: 0, start: 0, end: 10, durationSec: 10 },
    { kind: 'rest', afterIndex: 0, start: 10, end: 16 },
    { kind: 'audio', index: 1, start: 16, end: 24, durationSec: 8 },
  ],
  'work segments',
);
equal(workDuration(movements), 24, 'last rest is not part of the work');
deepEqual(placeOnWork(movements, 3), { kind: 'audio', index: 0, offset: 3 }, 'inside first');
deepEqual(placeOnWork(movements, 10), { kind: 'rest', afterIndex: 0, offset: 0 }, 'rest boundary');
deepEqual(placeOnWork(movements, 12), { kind: 'rest', afterIndex: 0, offset: 2 }, 'inside rest');
deepEqual(placeOnWork(movements, 16), { kind: 'audio', index: 1, offset: 0 }, 'next movement');
deepEqual(placeOnWork(movements, 24), { kind: 'audio', index: 1, offset: 8 }, 'work end');
deepEqual(placeOnWork(movements, scrubberSeek(24, 0.5)), { kind: 'rest', afterIndex: 0, offset: 2 }, 'work scrub midpoint');
equal(workSecondsAt(movements, 1, 2, false), 18, 'playing offset');
equal(workSecondsAt(movements, 0, 10, true, 2), 12, 'rest offset');

const week = [{ durationSec: 40, restAfterSec: 0 }];
deepEqual(workSegments(week), [{ kind: 'audio', index: 0, start: 0, end: 40, durationSec: 40 }], 'single movement');
equal(spanStageSeek(40, 0, 0, 1), scrubberSeek(40, 1), 'week stage covers the file');

deepEqual(
  replayAction({
    span: '1D',
    movementCount: 1,
    movementIndex: 0,
    movementTimeSec: 40,
    finished: false,
    parkedOnMovement: false,
  }),
  { kind: 'file-start' },
  '1D replay',
);
deepEqual(
  replayAction({
    span: '1W',
    movementCount: 1,
    movementIndex: 0,
    movementTimeSec: 12,
    finished: true,
    parkedOnMovement: false,
  }),
  { kind: 'file-start' },
  'single movement replay',
);
deepEqual(
  replayAction({
    span: '1M',
    movementCount: 4,
    movementIndex: 2,
    movementTimeSec: 15,
    finished: false,
    parkedOnMovement: false,
  }),
  { kind: 'movement-start', index: 2 },
  'first replay stays in the movement',
);
deepEqual(
  replayAction({
    span: '1M',
    movementCount: 4,
    movementIndex: 2,
    movementTimeSec: 0,
    finished: false,
    parkedOnMovement: true,
  }),
  { kind: 'work-start' },
  'second replay returns to the work',
);
deepEqual(
  replayAction({
    span: '1M',
    movementCount: 4,
    movementIndex: 2,
    movementTimeSec: 40,
    finished: false,
    parkedOnMovement: true,
  }),
  { kind: 'work-start' },
  'second replay still returns home after playback continues',
);
deepEqual(
  replayAction({
    span: '1Y',
    movementCount: 12,
    movementIndex: 6,
    movementTimeSec: 40,
    finished: true,
    parkedOnMovement: false,
  }),
  { kind: 'work-start' },
  'finished work',
);

equal(
  sonifySocketUrl('http://localhost:8000', { variant: 'jazz', source: 'live', symbol: 'ETHUSDT' }),
  'ws://localhost:8000/v1/sonify/ws?variant=jazz&source=live&symbol=ETHUSDT',
  'ws url',
);
equal(
  sonifySocketUrl('https://vstock-api.antunai.com/', {
    variant: 'ambient',
    source: 'history',
    symbol: 'BTCUSDT',
  }),
  'wss://vstock-api.antunai.com/v1/sonify/ws?variant=ambient&source=history&symbol=BTCUSDT',
  'wss url',
);

equal(whenFor(10, 0, 0.25, false), 10, 'straight when');
equal(whenFor(10, 4, 0.25, false), 11, 'straight bar');
if (whenFor(0, 2, 0.25, true) <= whenFor(0, 1, 0.25, true)) {
  throw new Error('swing should keep later sixteenths later');
}

const rows = liveListRows([
  { symbol: 'ETHUSDT', base: 'ETH' },
  { symbol: 'BTCUSDT', base: 'BTC' },
]);
equal(rows[2]?.key, 'history:BTCUSDT', 'history tape sits under BTC');
equal(rows[2]?.source, 'history', 'history row is still a stream');
equal(rows.filter((row) => row.source === 'history').length, 1, 'one history tape');
equal(liveListRows([{ symbol: 'ETHUSDT', base: 'ETH' }]).at(-1)?.symbol, 'BTCUSDT', 'history tape without BTC in the top list');

const withoutBtc = liveListRows([{ symbol: 'ETHUSDT', base: 'ETH' }]);
equal(pickLiveRow(withoutBtc, 'live:BTCUSDT')?.key, 'live:ETHUSDT', 'missing highlight falls to the first row');
equal(pickLiveRow(withoutBtc, 'live:BTCUSDT')?.source, 'live', 'fallback keeps the live source');
equal(pickLiveRow(withoutBtc, 'history:BTCUSDT')?.key, 'history:BTCUSDT', 'history highlight survives without BTC live');

equal(
  shouldResumePlay({ wantPlay: true, playing: false, didJustFinish: true, ended: false }),
  false,
  'do not restart on the finish tick',
);
equal(
  shouldResumePlay({ wantPlay: true, playing: false, didJustFinish: false, ended: true }),
  false,
  'do not restart after onEnded',
);
equal(
  shouldResumePlay({ wantPlay: true, playing: false, didJustFinish: false, ended: false }),
  true,
  'resume after a seek or Nghe',
);
equal(
  shouldResumePlay({ wantPlay: false, playing: false, didJustFinish: false, ended: false }),
  false,
  'paused stays paused',
);

equal(
  shouldArmFinish({ didJustFinish: false, currentTime: 12, durationSec: 100 }),
  true,
  'mid-file seek re-arms when finish clears',
);
equal(
  shouldArmFinish({ didJustFinish: true, currentTime: 12, durationSec: 100 }),
  false,
  'spurious finish mid-file stays disarmed',
);
equal(
  shouldArmFinish({ didJustFinish: true, currentTime: 99.8, durationSec: 100 }),
  true,
  'seek to the end re-arms so onEnded can run',
);
equal(
  shouldArmFinish({ didJustFinish: true, currentTime: 100, durationSec: 100 }),
  true,
  'exact end re-arms',
);

console.log('musicalize seek tests passed');
