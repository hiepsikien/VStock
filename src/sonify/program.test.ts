import {
  chartFocus,
  englishDate,
  englishKey,
  instrumentLine,
  movementPulse,
  pieceCopy,
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

equal(pieceCopy(piece({ variant: 'symphony', span: '1W' })).title, 'Fantasia VIC 20/1 in E-flat');
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
  'Movement 3: Minuet (120 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'symphony', span: '1M', movements: month }), 0).title,
  'Divertimento VIC 20/1 in E-flat',
);
equal(
  pieceCopy(piece({ variant: 'symphony', span: '1M', movements: month }), 1).movement,
  'Movement 2: Siciliana (72 BPM)',
);

const quarter = [movement({ label: 'I' }), movement({ label: 'II' }), movement({ label: 'III' })];
equal(
  pieceCopy(piece({ variant: 'symphony', span: '3M', movements: quarter }), 2).movement,
  'Movement 3: Finale (108 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'symphony', span: '3M', movements: quarter })).title,
  'Quintet VIC 20/1 in E-flat',
);

const year = [1, 2, 3, 12].map((item) => movement({ label: `${String(item).padStart(2, '0')}/26` }));
equal(
  pieceCopy(piece({ variant: 'symphony', span: '1Y', movements: year }), 2).movement,
  'Movement 3: Minuet (108 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'symphony', span: '1Y', movements: year }), 3).movement,
  'Movement 4: Finale (96 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'symphony', span: '1Y', movements: year })).title,
  'Serenade VIC 20/1 in E-flat',
);

equal(
  pieceCopy(piece({ variant: 'jazz', span: '1M', movements: month }), 2).movement,
  'Movement 3: Waltz (120 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'jazz', span: '1M', movements: month }), 1).movement,
  'Movement 2: Ballad (72 BPM)',
);

equal(
  pieceCopy(piece({ variant: 'minimalist', span: '1M', movements: month }), 0).movement,
  'Movement 1 (5/4, 96 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'minimalist', span: '1M', movements: month }), 3).movement,
  'Movement 4: Finale (96 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'ambient', span: '1M', movements: month }), 2).movement,
  'Movement 3: Minuet (120 BPM)',
);
equal(
  pieceCopy(piece({ variant: 'ambient', span: '3M', movements: quarter }), 2).movement,
  'Movement 3: Finale (108 BPM)',
);

equal(instrumentLine('guitar', 'bach'), 'Guitar (Solo)');
equal(
  pieceCopy(piece({ variant: 'guitar', ensemble: 'bach', span: '1D', movements: [movement({ character: 'calm' })] })).title,
  'Gavotte VIC 20/1 in E-flat',
);
equal(
  pieceCopy(piece({ variant: 'guitar', ensemble: 'bach', span: '1D', movements: [movement({ character: 'volatile' })] })).title,
  'Fugue VIC 20/1 in E-flat',
);
equal(
  pieceCopy(piece({ variant: 'guitar', ensemble: 'bach', span: '1D', movements: [movement({ character: 'selloff' })] })).title,
  'Chaconne VIC 20/1 in E-flat',
);
equal(
  pieceCopy(piece({ variant: 'guitar', ensemble: 'bach', span: '1D', movements: [movement({ character: 'rally' })] })).title,
  'Bourree VIC 20/1 in E-flat',
);

const wide = movement({ character: 'rally', prices: [100, 102], keyLabel: 'Mi♭' });
equal(
  pieceCopy(piece({ variant: 'guitar', ensemble: 'classic', span: '1D', movements: [wide] })).title,
  'Galop VIC 20/1 in E-flat',
);
equal(
  pieceCopy(
    piece({
      variant: 'guitar',
      ensemble: 'classic',
      span: '1D',
      keyLabel: 'Mi♭ thứ',
      movements: [movement({ character: 'rally', prices: [100, 102] })],
    }),
  ).title,
  'Etude VIC 20/1 in E-flat minor',
);

const guitarMonth = pieceCopy(
  piece({ variant: 'guitar', ensemble: 'bach', span: '1M', movements: month }),
  1,
);
equal(guitarMonth.title, 'Suite VIC 20/1 in E-flat');
equal(guitarMonth.movement, 'Movement 2: Sarabande (72 BPM)');
equal(
  pieceCopy(piece({ variant: 'guitar', ensemble: 'bach', span: '1M', movements: month }), 2).movement,
  'Movement 3: Gigue (120 BPM)',
);

deepEqual(movementPulse('guitar', 'bach', '1M', 2, null), { bpm: 120, beats: 6, beatType: 8 });
deepEqual(movementPulse('symphony', 'classic', '1D', 0, null), { bpm: 90, beats: 4, beatType: 4 });

const lengths = [4, 3];
const focus = chartFocus({
  total: 7,
  offsets: [0, 4],
  lengths,
  index: 0,
  elapsed: 0.4,
  resting: false,
  multi: true,
});
deepEqual(focus, { start: 0, end: 6 });
deepEqual(
  chartFocus({ total: 7, offsets: [0, 4], lengths, index: 0, elapsed: 3, resting: false, multi: true }),
  { start: 0, end: 3 },
);
deepEqual(
  chartFocus({ total: 7, offsets: [0, 4], lengths, index: 1, elapsed: 0.2, resting: false, multi: true }),
  { start: 4, end: 6 },
);
deepEqual(
  chartFocus({ total: 7, offsets: [0, 4], lengths, index: 1, elapsed: 1, resting: true, multi: true }),
  { start: 0, end: 6 },
);

console.log('program tests passed');
