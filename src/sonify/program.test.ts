import {
  chartFocus,
  englishDate,
  englishKey,
  instrumentLine,
  movementPulse,
  pieceCopy,
  pieceKey,
  playingLines,
  type MovementInput,
  type PieceInput,
} from './program';

function equal<T>(actual: T, expected: T) {
  if (actual !== expected) {
    throw new Error(`expected ${String(expected)}, got ${String(actual)}`);
  }
}

function deepEqual(actual: unknown, expected: unknown) {
  const left = JSON.stringify(actual);
  const right = JSON.stringify(expected);
  if (left !== right) throw new Error(`expected ${right}, got ${left}`);
}

function movement(partial: Partial<MovementInput> = {}): MovementInput {
  return {
    character: 'calm',
    keyLabel: 'Mi♭',
    prices: [10, 10.2, 10.1],
    label: 'I',
    ...partial,
  };
}

function piece(partial: Partial<PieceInput> & Pick<PieceInput, 'variant' | 'span'>): PieceInput {
  return {
    ensemble: 'classic',
    symbol: 'VIC',
    date: '2026-01-20',
    keyLabel: 'Mi♭',
    movements: [movement()],
    ...partial,
  };
}

equal(englishDate('2026-01-20'), '20/1');
equal(englishKey('Mi♭'), 'E-flat');
equal(englishKey('Mi♭ thứ'), 'E-flat minor');
equal(englishKey('Si♭'), 'B-flat');
equal(englishKey('Đô'), 'C');
equal(englishKey('Rê thứ'), 'D minor');
equal(englishKey('La'), 'A');

const day = pieceCopy(piece({ variant: 'symphony', span: '1D' }));
equal(day.title, 'Bagatelle VIC 20/1 in E-flat');
equal(day.instruments, 'Flute, Violin, Cello, Piano, Bass');
equal(day.movement, null);

equal(
  pieceCopy(piece({ variant: 'symphony', span: '1D', ensemble: 'wood' })).instruments,
  'Piccolo, Oboe, Clarinet, Harp, Contrabassoon',
);
equal(
  pieceCopy(piece({ variant: 'symphony', span: '1D', keyLabel: 'Mi♭ thứ' })).title,
  'Bagatelle VIC 20/1 in E-flat minor',
);

equal(pieceCopy(piece({ variant: 'symphony', span: '1W' })).title, 'Fantasia VIC 1W in E-flat');
equal(pieceCopy(piece({ variant: 'jazz', span: '1D' })).title, 'Jazz VIC 20/1 in E-flat');
equal(pieceCopy(piece({ variant: 'minimalist', span: '1D' })).title, 'Etude VIC 20/1 in E-flat');
equal(pieceCopy(piece({ variant: 'ambient', span: '1D' })).title, 'Prelude VIC 20/1 in E-flat');

const month = [
  movement({ label: 'I' }),
  movement({ label: 'II', character: 'calm' }),
  movement({ label: 'III', character: 'rally' }),
  movement({ label: 'IV', character: 'rally' }),
];
equal(
  pieceCopy(piece({ variant: 'symphony', span: '1M', movements: month }), 2).movement,
  'Minuet (3/4, 120 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'symphony', span: '1M', movements: month }), 0).title,
  'Divertimento VIC 1M in E-flat',
);
equal(
  pieceCopy(piece({ variant: 'symphony', span: '1M', movements: month }), 1).movement,
  'Siciliana (6/8, 72 BPM)',
);

const quarter = [movement({ label: 'I' }), movement({ label: 'II' }), movement({ label: 'III' })];
equal(
  pieceCopy(piece({ variant: 'symphony', span: '3M', movements: quarter }), 2).movement,
  'Finale (4/4, 108 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'symphony', span: '3M', movements: quarter })).title,
  'Quintet VIC 3M in E-flat',
);

const year = [1, 2, 3, 12].map((item) => movement({ label: `${String(item).padStart(2, '0')}/26` }));
equal(
  pieceCopy(piece({ variant: 'symphony', span: '1Y', movements: year }), 2).movement,
  'Minuet (3/4, 108 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'symphony', span: '1Y', movements: year }), 3).movement,
  'Finale (4/4, 96 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'symphony', span: '1Y', movements: year })).title,
  'Serenade VIC 1Y in E-flat',
);

equal(
  pieceCopy(piece({ variant: 'jazz', span: '1M', movements: month }), 2).movement,
  'Waltz (3/4, 120 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'jazz', span: '1M', movements: month }), 1).movement,
  'Ballad (12/8, 72 BPM)',
);

equal(
  pieceCopy(piece({ variant: 'minimalist', span: '1M', movements: month }), 0).movement,
  '(5/4, 96 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'minimalist', span: '1M', movements: month }), 3).movement,
  'Finale (4/4, 96 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'ambient', span: '1M', movements: month }), 2).movement,
  'Minuet (3/4, 120 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'ambient', span: '3M', movements: quarter }), 2).movement,
  'Finale (4/4, 108 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'minimalist', span: '3M', movements: quarter }), 2).movement,
  '(7/8, 108 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'jazz', span: '1M', movements: month })).title,
  'Set VIC 1M in E-flat',
);
equal(
  pieceCopy(piece({ variant: 'jazz', span: '1W' })).title,
  'Jazz VIC 1W in E-flat',
);
equal(
  pieceCopy(piece({ variant: 'minimalist', span: '3M', movements: quarter })).title,
  'Cycle VIC 3M in E-flat',
);
equal(
  pieceCopy(piece({ variant: 'ambient', span: '1Y', movements: year })).title,
  'Nocturne VIC 1Y in E-flat',
);
equal(
  pieceCopy(piece({ variant: 'ambient', span: '1W' })).title,
  'Prelude VIC 1W in E-flat',
);
equal(
  pieceKey('Mi♭', ['Mi♭ thứ', 'Mi♭']),
  'Mi♭',
);
equal(
  pieceKey('', ['Mi♭ thứ', 'Mi♭']),
  'Mi♭',
);
equal(
  pieceKey(undefined, ['Mi♭ thứ', 'Rê thứ']),
  'Mi♭ thứ',
);

equal(instrumentLine('guitar', 'bach'), 'Guitar (Solo)');
equal(
  pieceCopy(
    piece({
      variant: 'guitar',
      ensemble: 'barrios',
      span: '1D',
      movements: [movement({ character: 'volatile', name: 'Tremolo' })],
    }),
  ).title,
  'Tremolo VIC 20/1 in E-flat',
);
equal(
  pieceCopy(
    piece({
      variant: 'guitar',
      ensemble: 'barrios',
      span: '1D',
      movements: [movement({ character: 'volatile' })],
    }),
  ).title,
  'VIC 20/1 in E-flat',
);
equal(
  pieceCopy(
    piece({
      variant: 'guitar',
      ensemble: 'villa',
      span: '1D',
      movements: [movement({ character: 'calm', name: 'Chord Melody' })],
    }),
  ).title,
  'Chord Melody VIC 20/1 in E-flat',
);
equal(
  pieceCopy(
    piece({
      variant: 'guitar',
      ensemble: 'bach',
      span: '1D',
      movements: [movement({ character: 'selloff', name: 'Sarabande' })],
    }),
  ).title,
  'Sarabande VIC 20/1 in E-flat',
);

const guitarMonth = pieceCopy(
  piece({
    variant: 'guitar',
    ensemble: 'bach',
    span: '1M',
    movements: month.map((item, itemIndex) =>
      itemIndex === 1 ? { ...item, name: 'Sarabande' } : itemIndex === 2 ? { ...item, name: 'Gigue' } : item,
    ),
  }),
  1,
);
equal(guitarMonth.title, 'Suite VIC 1M in E-flat');
equal(guitarMonth.instruments, 'Guitar (Solo)');
equal(guitarMonth.movement, 'Sarabande (3/4, 72 BPM)');
const guitarBeforeName = pieceCopy(
  piece({ variant: 'guitar', ensemble: 'bach', span: '1M', movements: month }),
  0,
);
equal(guitarBeforeName.title, 'Suite VIC 1M in E-flat');
equal(guitarBeforeName.instruments, 'Guitar (Solo)');
equal(guitarBeforeName.movement, null);
equal(
  pieceCopy(
    piece({
      variant: 'guitar',
      ensemble: 'bach',
      span: '1M',
      movements: month.map((item, itemIndex) => (itemIndex === 2 ? { ...item, name: 'Gigue' } : item)),
    }),
    2,
  ).movement,
  'Gigue (6/8, 120 BPM)',
);
equal(
  pieceCopy(
    piece({
      variant: 'minimalist',
      span: '3M',
      movements: quarter.map((item, itemIndex) => (itemIndex === 2 ? { ...item, name: 'Finale', beats: 7, beatType: 8, bpm: 108 } : item)),
    }),
    2,
  ).movement,
  '(7/8, 108 BPM)',
);

deepEqual(movementPulse('guitar', 'bach', '1M', 2, null), { bpm: 120, beats: 6, beatType: 8 });
deepEqual(movementPulse('symphony', 'classic', '1D', 0, null), { bpm: 90, beats: 4, beatType: 4 });

const lengths = [4, 3];
const waiting = { total: 7, offsets: [0, 4], lengths, elapsed: 0.4, resting: false, audible: false, multi: true };
deepEqual(chartFocus({ ...waiting, index: 0 }), { start: 0, end: 6 });
deepEqual(chartFocus({ ...waiting, index: 1 }), { start: 0, end: 6 });
deepEqual(
  chartFocus({ total: 7, offsets: [0, 4], lengths, index: 0, elapsed: 3, resting: false, audible: true, multi: true }),
  { start: 0, end: 3 },
);
deepEqual(
  chartFocus({ total: 7, offsets: [0, 4], lengths, index: 1, elapsed: 0.2, resting: false, audible: true, multi: true }),
  { start: 4, end: 6 },
);
deepEqual(
  chartFocus({ total: 7, offsets: [0, 4], lengths, index: 1, elapsed: 1, resting: true, audible: true, multi: true }),
  { start: 0, end: 6 },
);

deepEqual(playingLines('Suite VIC 1M in E-flat', 'Sarabande (3/4, 72 BPM)'), [
  'Suite VIC 1M in E-flat',
  'Sarabande (3/4, 72 BPM)',
]);
deepEqual(playingLines('Bagatelle VIC 20/1 in E-flat', null), ['Bagatelle VIC 20/1 in E-flat']);
equal(
  pieceCopy(
    piece({
      variant: 'guitar',
      ensemble: 'bach',
      span: '1M',
      movements: month.map((item, itemIndex) =>
        itemIndex === 1 ? { ...item, name: 'Prelude — Sarabande — Prelude' } : item,
      ),
    }),
    1,
  ).movement,
  'Prelude — Sarabande — Prelude (3/4, 72 BPM)',
);
equal(
  pieceCopy(
    piece({
      variant: 'guitar',
      ensemble: 'bach',
      span: '1M',
      movements: month.map((item, itemIndex) =>
        itemIndex === 3 ? { ...item, name: 'Prelude — Sarabande — Prelude' } : item,
      ),
    }),
    3,
  ).movement,
  'Finale: Prelude — Sarabande — Prelude (4/4, 96 BPM)',
);

console.log('program tests passed');
