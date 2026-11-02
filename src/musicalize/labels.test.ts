import { clockText, foldText, formatClock, formatDelta, pafiBandLabel, pafiPillText } from './labels';

function equal<T>(actual: T, expected: T, label = '') {
  if (actual !== expected) {
    throw new Error(`${label} expected ${String(expected)}, got ${String(actual)}`);
  }
}

equal(formatClock(0), '0:00', 'zero');
equal(formatClock(59.9), '0:59', 'floor under a minute');
equal(formatClock(260), '4:20', 'minutes');
equal(formatClock(-3), '0:00', 'negative clamps');
equal(formatClock(Number.NaN), '0:00', 'nan clamps');

equal(clockText(263, 260), '4:20', 'clock above duration clamps');
equal(clockText(-1, 100), '0:00', 'clock below zero clamps');
equal(clockText(42, 260), '0:42', 'clock inside duration passes through');
equal(clockText(60, 0), '1:00', 'zero duration falls back to the reading');
equal(clockText(300, Number.NaN), '5:00', 'nan duration falls back to the reading');

const up = formatDelta(1.234);
equal(up?.glyph, '▲', 'up glyph');
equal(up?.text, '1.23%', 'up text');
equal(up?.positive, true, 'up sign');

const down = formatDelta(-0.4);
equal(down?.glyph, '▼', 'down glyph');
equal(down?.text, '0.40%', 'down text');
equal(down?.positive, false, 'down sign');

equal(formatDelta(0)?.glyph, '·', 'flat glyph');
equal(formatDelta(null), null, 'missing quote stays empty');
equal(formatDelta(Number.NaN), null, 'nan quote stays empty');

equal(foldText('Giao hưởng'), 'giao huong', 'fold removes tone marks');
equal(foldText('ĐỒNG'), 'dong', 'fold handles đ and case');
equal(foldText('  Tối giản  '), 'toi gian', 'fold trims and removes marks');
equal(foldText('Jazz'), 'jazz', 'fold keeps ascii');

equal(pafiBandLabel('fair'), 'Vừa', 'server fair maps to Vietnamese');
equal(pafiBandLabel('very-clear'), 'Rất rõ', 'clear band');
equal(pafiBandLabel(null), 'Chưa đủ mẫu', 'missing band is not a zero');
equal(pafiPillText(78.4, 'high'), 'PA 78', 'pill rounds');
equal(pafiPillText(78.4, 'low'), 'PA ~78', 'low confidence keeps the tilde');
equal(pafiPillText(null), 'PA —', 'missing score');
equal(pafiPillText(Number.NaN), 'PA —', 'nan score');

console.log('musicalize label tests passed');
