import {
  buildAudioBody,
  buildAudioHashBody,
  buildPreviewBody,
  buildValidateBody,
  normalizeAudioResponse,
  normalizeErrors,
  normalizeExamplesResponse,
  normalizePreviewResponse,
  normalizePublishResponse,
  normalizePublishedSpecResponse,
  normalizeSpecsResponse,
  normalizeValidateResponse,
  resolveAudioUrl,
} from './protocol';
import {
  DEFAULT_SAMPLE,
  PATTERNS,
  SAMPLES,
  checkSpecShape,
  checkSpecText,
  defaultSampleForPattern,
  describeRequestFailure,
  durationLabel,
  examplesToSamples,
  findSample,
  fixtureForSpec,
  fixtureText,
  jsonErrorLocation,
  meterLabel,
  metersForPattern,
  normalizeErrorPath,
  notesLines,
  parseJsonObject,
  patternCatalogHint,
  patternIds,
  planLines,
  prefixErrorPaths,
  publishedAtLabel,
  publishedSpecMeta,
  publishedSpecTitle,
  sampleText,
  shortId,
  textStats,
  valueLines,
} from './spec';

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

function paths(value: Array<{ path: string }>): string[] {
  return value.map((item) => item.path);
}

// Every template must be a real SentenceSpec shape and survive the local
// pre-flight unchanged. This is the guard against a typo in SAMPLES shipping a
// broken "valid" example.
equal(SAMPLES.length, 7);
for (const sample of SAMPLES) {
  equal(sample.spec.pattern, sample.pattern);
  equal(sample.spec.meter, sample.meter);
  equal(sample.key, `${sample.pattern}:${sample.meter}`);

  const parsed = parseJsonObject(sampleText(sample), 'Spec');
  if (!parsed.ok) {
    throw new Error(`${sample.key}: sample is not JSON: ${parsed.errors[0]?.message}`);
  }
  deepEqual(checkSpecShape(parsed.value), []);

  const fixture = parseJsonObject(fixtureText(sample), 'Fixture');
  if (!fixture.ok) {
    throw new Error(`${sample.key}: fixture is not JSON: ${fixture.errors[0]?.message}`);
  }
}

deepEqual(
  PATTERNS.map((item) => item.id),
  [
    'castillo',
    'sonatina',
    'fandanguillo',
    'danza',
    'galop',
    'villa_pattern',
    'preludio',
    'brouwer_etude',
  ],
);
equal(PATTERNS.filter((item) => item.composer === 'Torroba').length, 4);
equal(PATTERNS.filter((item) => item.composer === 'Sor').length, 1);
equal(PATTERNS.filter((item) => item.composer === 'Brouwer').length, 1);
equal(PATTERNS.filter((item) => item.composer === 'Villa').length, 1);
equal(PATTERNS.filter((item) => item.composer === 'Barrios').length, 1);
equal(patternIds(SAMPLES).length, 5);
deepEqual(metersForPattern(SAMPLES, 'danza'), ['3/4', '6/8']);
deepEqual(metersForPattern(SAMPLES, 'missing'), []);
equal(patternCatalogHint(SAMPLES), 'Torroba: Castillo, Sonatina, Fandanguillo, Danza · Sor: Galop');

equal(findSample('castillo', '3/4')?.spec.id, 'castillo_34_walk');
equal(findSample('danza', '6/8')?.spec.id, 'danza_68_open');
equal(findSample('galop', '*')?.spec.id, 'galop_cycle');
equal(defaultSampleForPattern('castillo').key, 'castillo:3/4');
equal(defaultSampleForPattern('galop').key, 'galop:*');
equal(defaultSampleForPattern('unknown').key, DEFAULT_SAMPLE.key);
equal(meterLabel('*'), 'any meter');
equal(meterLabel('3/4'), '3/4');

// The picker can be handed the API palette instead of the embedded table.
equal(findSample('castillo', '3/4', [SAMPLES[2]])?.key, undefined);
equal(defaultSampleForPattern('preludio', SAMPLES).key, DEFAULT_SAMPLE.key);

// Fixtures derived from a spec match the values the server defaults to.
deepEqual(fixtureForSpec(DEFAULT_SAMPLE.spec), {
  length: 9,
  n: 0,
  closes: false,
  rise: 0,
});
deepEqual(fixtureForSpec(findSample('galop', '*')!.spec), {
  run_length: 8,
  closes: false,
  rise: 0,
});
deepEqual(fixtureForSpec({ select: {}, span: {} }), { closes: false });

// API examples replace the hand-copied SAMPLES and carry their own fixture.
const villaExample = {
  id: 'villa_arpeggio_aba',
  pattern: 'villa_pattern',
  meter: '4/4',
  payload: {
    id: 'villa_arpeggio_aba',
    pattern: 'villa_pattern',
    meter: '4/4',
    select: { length_min: 3, length_max: null, n_parity: 'any', rise_min: 0 },
    span: { tile: 3, remainder: 'same_figure', cycle: false, exact: false },
    slots: [{ start: 0, bars: 1, figure: 1 }],
  },
};
const villaSamples = examplesToSamples([villaExample]);
equal(villaSamples.length, 1);
equal(villaSamples[0]?.key, 'villa_pattern:4/4');
equal(villaSamples[0]?.title, 'Villa arpeggio · 4/4');
equal(villaSamples[0]?.source, 'api');
equal(villaSamples[0]?.id, 'villa_arpeggio_aba');
deepEqual(villaSamples[0]?.fixture, {
  length: 3,
  closes: false,
  rise: 0,
});
deepEqual(patternIds(villaSamples), ['villa_pattern']);
deepEqual(metersForPattern(villaSamples, 'villa_pattern'), ['4/4']);

// Publish/list formatting is deterministic and locale-free.
equal(publishedAtLabel('2026-11-05T09:41:02.123+00:00'), '2026-11-05 09:41');
equal(publishedAtLabel(''), '—');
equal(publishedAtLabel('not-a-date'), 'not-a-date');
const published = {
  id: '0123456789abcdef0123456789abcdef',
  pattern: 'villa_pattern',
  meter: '4/4',
  version: 3,
  status: 'published',
  createdAt: '2026-11-05T09:41:02+00:00',
};
equal(publishedSpecTitle(published), 'Villa arpeggio · 4/4');
equal(publishedSpecMeta(published), 'v3 · 2026-11-05 09:41');
equal(shortId(published.id), '0123456789…');
equal(shortId('short'), 'short');
equal(durationLabel(1.24), '1.2s');
equal(durationLabel(61), '1:01');
equal(durationLabel(0), '—');
equal(durationLabel(Number.NaN), '—');

// Editor counters.
deepEqual(textStats(''), { lines: 1, chars: 0 });
deepEqual(textStats('a\nbc'), { lines: 2, chars: 4 });

// JSON parsing: empty, array, scalar, and malformed inputs all get a path.
const empty = parseJsonObject('   ', 'Spec');
if (empty.ok) throw new Error('empty JSON should fail');
deepEqual(empty.errors, [{ path: '$', message: 'Spec is empty.' }]);

const array = parseJsonObject('[1]', 'Spec');
if (array.ok) throw new Error('an array is not one spec mapping');
equal(array.errors[0]?.path, '$');
if (!array.errors[0]?.message.includes('JSON object')) {
  throw new Error(array.errors[0]?.message);
}

const scalar = parseJsonObject('"x"', 'Spec');
if (scalar.ok) throw new Error('a scalar is not one spec mapping');

const malformed = parseJsonObject('{"a":}', 'Spec');
if (malformed.ok) throw new Error('malformed JSON should fail');
equal(malformed.errors[0]?.path, '$');
if (!malformed.errors[0]?.message.includes('Invalid JSON')) {
  throw new Error(malformed.errors[0]?.message);
}

deepEqual(jsonErrorLocation('Unexpected token } in JSON at position 6', '{"a":\n}'), {
  line: 2,
  column: 1,
});
deepEqual(jsonErrorLocation('bad (line 4 column 7)', ''), { line: 4, column: 7 });
equal(jsonErrorLocation('bad', ''), null);

// Shape checks point at the missing/changed field.
deepEqual(paths(checkSpecShape({})), [
  'id',
  'pattern',
  'meter',
  'select',
  'span',
  'slots',
]);

const valid = DEFAULT_SAMPLE.spec;
deepEqual(paths(checkSpecShape({ ...valid, slots: [] })), ['slots']);

const bothRealizers = checkSpecShape({
  ...valid,
  slots: [{ start: 0, bars: 1, figure: 8, cell: 'galop1' }],
});
deepEqual(paths(bothRealizers), ['slots[0]']);

const procedureOnly = checkSpecShape({
  ...valid,
  slots: [{ start: 0, bars: 1, procedure: 'bach_imitation' }],
});
deepEqual(procedureOnly, []);

const figureAndProcedure = checkSpecShape({
  ...valid,
  slots: [{ start: 0, bars: 1, figure: 8, procedure: 'bach_imitation' }],
});
deepEqual(paths(figureAndProcedure), ['slots[0]']);

const neitherRealizer = checkSpecShape({
  ...valid,
  slots: [{ start: 0, bars: 1, figure: null, cell: null }],
});
deepEqual(paths(neitherRealizer), ['slots[0]']);

const badSlot = checkSpecShape({
  ...valid,
  slots: [{ start: 0, bars: 0, figure: 8 }],
});
deepEqual(paths(badSlot), ['slots[0].bars']);

const checked = checkSpecText(sampleText(DEFAULT_SAMPLE));
if (!checked.ok) throw new Error('default sample should pass pre-flight');
equal(checked.spec.id, 'castillo_34_walk');

// Error paths are rendered as JSON paths.
equal(normalizeErrorPath(''), '$');
equal(normalizeErrorPath('$'), '$');
equal(normalizeErrorPath('select.length_min'), '$.select.length_min');
equal(normalizeErrorPath('[0].bars'), '$[0].bars');
equal(normalizeErrorPath('$.slots[1]'), '$.slots[1]');

deepEqual(
  prefixErrorPaths(
    [
      { path: '$', message: 'invalid' },
      { path: '$.length', message: 'must be a number' },
    ],
    'fixture',
  ),
  [
    { path: 'fixture', message: 'invalid' },
    { path: 'fixture.length', message: 'must be a number' },
  ],
);

// Plan formatter handles tuple spans, object spans, cells, and unknown blobs.
deepEqual(planLines([]), []);
deepEqual(planLines([
  [13, [0, 1, 2]],
  [8, [3, 4]],
]), ['figure 13 · bars 0–2', 'figure 8 · bars 3–4']);
deepEqual(planLines([{ cell: 'galop1', bars: [0, 1, 2, 3] }]), [
  'cell galop1 · bars 0–3',
]);
deepEqual(planLines([{ figure: 7, bars: [1, 2] }]), ['figure 7 · bars 1–2']);
equal(planLines({ spans: [] })[0] ?? '', '{');

// Notes: compact one-line rows, event object unwrapping, and caps.
deepEqual(notesLines([{ bar: 0, beat: 1, pitch: 'A4', voice: 1 }]), [
  'bar 0 · beat 1 · A4 · v1',
]);
deepEqual(notesLines({ events: [{ midi: 69, string: 1, fret: 5 }] }), ['MIDI 69 · s1f5']);
deepEqual(notesLines([]), []);
deepEqual(notesLines(null), []);
equal(notesLines(Array.from({ length: 30 }, (_, index) => ({ bar: index })))[24], '… 6 more notes');

deepEqual(valueLines(null), []);
deepEqual(valueLines({ a: 1 }), ['{', '  "a": 1', '}']);
deepEqual(valueLines({ a: 1 }, 2), ['{', '  "a": 1', '… 1 more lines']);

equal(describeRequestFailure(new Error('boom')), 'boom');
equal(describeRequestFailure('plain'), 'plain');
equal(describeRequestFailure(null), 'Unknown Studio API error.');

// Protocol normalisation, including FastAPI's `detail` fallback.
deepEqual(
  normalizeErrors({ errors: [{ path: 'select.length_min', message: 'must be >= 1' }] }),
  [{ path: 'select.length_min', message: 'must be >= 1' }],
);
deepEqual(
  normalizeErrors({
    detail: [{ loc: ['body', 'slots', 0, 'bars'], msg: 'must be >= 1' }],
  }),
  [{ path: 'slots.0.bars', message: 'must be >= 1' }],
);

deepEqual(normalizeValidateResponse({ ok: false }), { ok: false, errors: [] });
deepEqual(
  normalizeValidateResponse({ errors: [{ path: 'meter', message: 'unknown' }] }),
  { ok: false, errors: [{ path: 'meter', message: 'unknown' }] },
);

deepEqual(buildValidateBody({ id: 'x' }), { id: 'x' });
deepEqual(buildPreviewBody({ id: 'x' }, { length: 8 }), {
  spec: { id: 'x' },
  fixture: { length: 8 },
});

const preview = normalizePreviewResponse({
  ok: true,
  render_hash: 'abc123',
  plan: [[13, [0, 1]]],
});
equal(preview.ok, true);
equal(preview.renderHash, 'abc123');
deepEqual(preview.plan, [[13, [0, 1]]]);
equal(preview.row, null);
equal(preview.notes, null);
equal(preview.matrix, null);

// Examples: documented payload, a `spec` alias, and invalid rows are dropped.
deepEqual(
  normalizeExamplesResponse({
    ok: true,
    examples: [
      {
        id: 'villa_arpeggio_aba',
        pattern: 'villa_pattern',
        meter: '4/4',
        payload: { id: 'villa_arpeggio_aba' },
      },
      { pattern: 'preludio', meter: '4/4', spec: { id: 'barrios' } },
      { pattern: '', meter: '4/4', payload: {} },
      { pattern: 'broken', meter: '4/4' },
      'nope',
    ],
  }),
  {
    ok: true,
    examples: [
      {
        id: 'villa_arpeggio_aba',
        pattern: 'villa_pattern',
        meter: '4/4',
        payload: { id: 'villa_arpeggio_aba' },
      },
      {
        id: 'barrios',
        pattern: 'preludio',
        meter: '4/4',
        payload: { id: 'barrios' },
      },
    ],
  },
);
deepEqual(normalizeExamplesResponse({ examples: [] }), { ok: true, examples: [] });
let examplesThrew = false;
try {
  normalizeExamplesResponse(null);
} catch {
  examplesThrew = true;
}
equal(examplesThrew, true);

// Audio body allows spec+fixture or a cached render hash.
deepEqual(buildAudioBody({ id: 'x' }, { length: 8 }), {
  spec: { id: 'x' },
  fixture: { length: 8 },
});
deepEqual(buildAudioBody({ id: 'x' }), { spec: { id: 'x' }, fixture: {} });
deepEqual(buildAudioHashBody('sha256:abc'), { renderHash: 'sha256:abc' });

deepEqual(
  normalizeAudioResponse({
    ok: true,
    audio_url: '/v1/studio/sentence/audio/key.wav',
    duration_sec: 1.25,
    render_hash: 'sha256:abc',
  }),
  {
    ok: true,
    errors: [],
    audioUrl: '/v1/studio/sentence/audio/key.wav',
    durationSec: 1.25,
    renderHash: 'sha256:abc',
  },
);
deepEqual(
  normalizeAudioResponse({
    ok: false,
    errors: [{ path: 'audio', message: 'busy' }],
    durationSec: -1,
  }),
  {
    ok: false,
    errors: [{ path: 'audio', message: 'busy' }],
    audioUrl: null,
    durationSec: 0,
    renderHash: null,
  },
);

// Audio URLs: relative routes join the API base; absolute/CDN URLs pass through.
equal(
  resolveAudioUrl('http://localhost:8000', '/v1/studio/sentence/audio/key.wav'),
  'http://localhost:8000/v1/studio/sentence/audio/key.wav',
);
equal(
  resolveAudioUrl('http://localhost:8000/', 'v1/studio/sentence/audio/key.wav'),
  'http://localhost:8000/v1/studio/sentence/audio/key.wav',
);
equal(
  resolveAudioUrl('http://localhost:8000', 'https://cdn.example/key.wav'),
  'https://cdn.example/key.wav',
);
equal(resolveAudioUrl('http://localhost:8000', ''), null);
equal(resolveAudioUrl('', '/v1/key.wav'), '/v1/key.wav');
equal(resolveAudioUrl('http://localhost:8000', 'blob:http://localhost/123'), 'blob:http://localhost/123');

// Publish normalisation.
deepEqual(
  normalizePublishResponse({
    ok: true,
    id: 'abc',
    pattern: 'villa_pattern',
    meter: '4/4',
    version: 2,
  }),
  {
    ok: true,
    id: 'abc',
    pattern: 'villa_pattern',
    meter: '4/4',
    version: 2,
    errors: [],
  },
);
deepEqual(
  normalizePublishResponse({
    errors: [{ path: 'spec.slots[0]', message: 'bad' }],
  }),
  {
    ok: false,
    id: null,
    pattern: null,
    meter: null,
    version: null,
    errors: [{ path: 'spec.slots[0]', message: 'bad' }],
  },
);

// Spec list accepts `{ok, specs}` and a bare array; detail adds the payload.
const specs = normalizeSpecsResponse({
  ok: true,
  specs: [
    published,
    { id: 'y', pattern: 'preludio', meter: '4/4', version: 1, created_at: '2026-11-04T00:00:00Z' },
    { id: 'bad' },
  ],
});
deepEqual(specs, [
  published,
  {
    id: 'y',
    pattern: 'preludio',
    meter: '4/4',
    version: 1,
    status: '',
    createdAt: '2026-11-04T00:00:00Z',
  },
]);
deepEqual(normalizeSpecsResponse([published]), [published]);
deepEqual(normalizeSpecsResponse({ ok: true }), []);

deepEqual(
  normalizePublishedSpecResponse({ ...published, payload: { id: 'villa' } }),
  { ...published, payload: { id: 'villa' } },
);
deepEqual(
  normalizePublishedSpecResponse({ ...published }),
  { ...published, payload: {} },
);
let detailThrew = false;
try {
  normalizePublishedSpecResponse({ id: 'only-id' });
} catch {
  detailThrew = true;
}
equal(detailThrew, true);

console.log('studio tests passed');
