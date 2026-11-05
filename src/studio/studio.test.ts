import {
  buildAnalyzeBody,
  buildAudioBody,
  buildAudioHashBody,
  buildPreviewBody,
  buildValidateBody,
  emptyStudioQuota,
  normalizeAccessResponse,
  normalizeAnalyzeResponse,
  normalizeDeleteUploadResponse,
  normalizeAudioResponse,
  normalizeErrors,
  normalizeExamplesResponse,
  normalizePreviewResponse,
  normalizePublishResponse,
  normalizePublishedSpecResponse,
  normalizeRollbackResponse,
  normalizeSpecsResponse,
  normalizeUploadResponse,
  normalizeValidateResponse,
  parseRetryAfter,
  resolveAudioUrl,
  studioSessionError,
} from './protocol';
import {
  DEFAULT_SAMPLE,
  PATTERNS,
  SAMPLES,
  accessReasonLabel,
  accessSummary,
  byteSizeLabel,
  checkSpecShape,
  checkSpecText,
  confidenceBand,
  confidenceLabel,
  defaultSampleForPattern,
  describeRequestFailure,
  draftJson,
  draftNoteRows,
  durationLabel,
  examplesToSamples,
  findSample,
  fixtureForSpec,
  fixtureText,
  imageSizeError,
  jsonErrorLocation,
  measureLines,
  meterLabel,
  metersForPattern,
  nextPublishedList,
  normalizeErrorPath,
  noteBarLabel,
  noteBeatLabel,
  notePitchLabel,
  notePositionLabel,
  noteVoiceLabel,
  notesLines,
  parseJsonObject,
  patternCatalogHint,
  patternIds,
  planLines,
  prefixErrorPaths,
  publishedAtLabel,
  publishedSpecLineage,
  publishedSpecMeta,
  publishedSpecTitle,
  rollbackLabel,
  sampleText,
  shortId,
  textStats,
  uploadMetaLabel,
  valueLines,
} from './spec';
import {
  STUDIO_SESSION_HEADER,
  STUDIO_SESSION_KEY,
  loadStudioSession,
  newStudioSession,
  normalizeStudioSession,
  sessionHeader,
  sessionLabel,
} from './session';

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

// Vision/session errors use `detail:{code,message}`; do not show raw JSON.
deepEqual(
  normalizeErrors({
    detail: { code: 'studio_disabled', message: 'Studio is disabled' },
  }),
  [{ path: 'studio_disabled', message: 'Studio is disabled' }],
);

// FastAPI can answer with a bare string `detail`; surface it with the `$` path.
deepEqual(normalizeErrors({ detail: 'published spec not found' }), [
  { path: '$', message: 'published spec not found' },
]);

// Rollback responses use the publish summary plus `rollbackOf`.
deepEqual(
  normalizeRollbackResponse({
    ok: true,
    id: 'new',
    pattern: 'villa_pattern',
    meter: '4/4',
    version: 4,
    rollbackOf: 'old',
  }),
  {
    ok: true,
    id: 'new',
    pattern: 'villa_pattern',
    meter: '4/4',
    version: 4,
    rollbackOf: 'old',
    errors: [],
  },
);
deepEqual(normalizeRollbackResponse({ ok: true, id: 'new', version: 4 }, 'old'), {
  ok: true,
  id: 'new',
  pattern: null,
  meter: null,
  version: 4,
  rollbackOf: 'old',
  errors: [],
});
deepEqual(
  normalizeRollbackResponse({ ok: true, id: 'new', rollback_of: 'old' }, 'ignored'),
  {
    ok: true,
    id: 'new',
    pattern: null,
    meter: null,
    version: null,
    rollbackOf: 'old',
    errors: [],
  },
);
deepEqual(
  normalizeRollbackResponse(
    { errors: [{ path: 'spec', message: 'bad' }] },
    'old',
  ),
  {
    ok: false,
    id: null,
    pattern: null,
    meter: null,
    version: null,
    rollbackOf: 'old',
    errors: [{ path: 'spec', message: 'bad' }],
  },
);
let rollbackThrew = false;
try {
  normalizeRollbackResponse(null);
} catch {
  rollbackThrew = true;
}
equal(rollbackThrew, true);

// Lineage is optional, so ordinary rows stay unchanged.
const rollbackRow = {
  ...published,
  id: 'new',
  version: 4,
  rollbackOf: '0123456789abcdef',
};
equal(publishedSpecLineage(rollbackRow), 'rollback of 0123456789…');
equal(publishedSpecLineage(published), null);
equal(
  publishedSpecMeta(rollbackRow),
  'v4 · 2026-11-05 09:41 · rollback of 0123456789…',
);
equal(rollbackLabel(4, rollbackRow.rollbackOf), 'v4 · rollback of 0123456789…');
equal(rollbackLabel(null, 'abc'), 'rollback of abc');
equal(rollbackLabel(4, ''), null);
equal(rollbackLabel(4, undefined), null);
deepEqual(
  normalizeSpecsResponse({ specs: [{ ...published, rollbackOf: 'old' }] }),
  [{ ...published, rollbackOf: 'old' }],
);
deepEqual(
  normalizeSpecsResponse({ specs: [{ ...published, rollback_of: 'old' }] }),
  [{ ...published, rollbackOf: 'old' }],
);
deepEqual(normalizePublishedSpecResponse({ ...rollbackRow, payload: {} }), {
  ...rollbackRow,
  payload: {},
});

// Refresh transitions keep rows visible while loading and after an error.
const listState = { loading: false, items: [published], error: 'stale' };
deepEqual(nextPublishedList(listState, { kind: 'start' }), {
  loading: true,
  items: [published],
  error: null,
});
deepEqual(nextPublishedList(listState, { kind: 'success', items: [] }), {
  loading: false,
  items: [],
  error: null,
});
deepEqual(nextPublishedList(listState, { kind: 'failure', message: 'down' }), {
  loading: false,
  items: [published],
  error: 'down',
});

// ---------------------------------------------------------------------------
// Phase 1 front half: access, upload, analyze, session.
// ---------------------------------------------------------------------------

// Access: documented shape, snake_case quota aliases, and the disabled gate.
const access = normalizeAccessResponse({
  enabled: true,
  reason: 'open_beta',
  quota: {
    uploadsPerDay: 20,
    analysesPerDay: 100,
    specsPerDay: 50,
    maxImageMb: 20,
    previewsConcurrent: 1,
  },
});
deepEqual(access, {
  ok: true,
  enabled: true,
  reason: 'open_beta',
  seats: null,
  quota: {
    uploadsPerDay: 20,
    analysesPerDay: 100,
    specsPerDay: 50,
    maxImageMb: 20,
    previewsConcurrent: 1,
  },
  errors: [],
});
equal(accessSummary(access), 'Open beta · 20 uploads/day · max 20 MB');
equal(accessReasonLabel('open_beta'), 'Open beta');
equal(accessReasonLabel('entitled'), 'Entitled');
equal(accessReasonLabel('disabled'), 'Disabled');
equal(accessReasonLabel('new_value'), 'new_value');

deepEqual(
  normalizeAccessResponse({
    enabled: false,
    reason: 'disabled',
    seats: 3,
    quota: { uploads_per_day: 5, max_image_mb: 8, previews_concurrent: 2 },
  }),
  {
    ok: false,
    enabled: false,
    reason: 'disabled',
    seats: 3,
    quota: {
      uploadsPerDay: 5,
      analysesPerDay: 0,
      specsPerDay: 0,
      maxImageMb: 8,
      previewsConcurrent: 2,
    },
    errors: [],
  },
);
equal(accessSummary(normalizeAccessResponse({ enabled: false, reason: 'disabled' })), 'Studio disabled · Disabled');

// `enabled` may be omitted; `reason` then decides. An empty/broken body is
// treated as disabled rather than guessing open.
equal(normalizeAccessResponse({ reason: 'open_beta' }).enabled, true);
equal(normalizeAccessResponse({ reason: 'disabled' }).enabled, false);
equal(normalizeAccessResponse({}).enabled, false);
equal(normalizeAccessResponse({}).reason, 'unknown');
deepEqual(emptyStudioQuota(), {
  uploadsPerDay: 0,
  analysesPerDay: 0,
  specsPerDay: 0,
  maxImageMb: 0,
  previewsConcurrent: 0,
});
const accessFailure = normalizeAccessResponse({ detail: 'studio access unavailable' });
equal(accessFailure.enabled, false);
deepEqual(accessFailure.errors, [
  { path: '$', message: 'studio access unavailable' },
]);
let accessThrew = false;
try {
  normalizeAccessResponse(null);
} catch {
  accessThrew = true;
}
equal(accessThrew, true);

// Upload: documented shape, aliases, and FastAPI's string detail.
deepEqual(
  normalizeUploadResponse({
    ok: true,
    id: 'up_1',
    sha256: 'abcdef0123456789abcdef0123456789',
    filename: 'score.png',
    mime: 'image/png',
    url: '/v1/musicalize/studio/uploads/up_1',
    token: 'tok',
    width: 900,
    height: 420,
  }),
  {
    ok: true,
    id: 'up_1',
    sha256: 'abcdef0123456789abcdef0123456789',
    filename: 'score.png',
    mime: 'image/png',
    url: '/v1/musicalize/studio/uploads/up_1',
    token: 'tok',
    width: 900,
    height: 420,
    errors: [],
  },
);
deepEqual(
  normalizeUploadResponse({
    upload_id: 'up_2',
    sha: 'sha2',
    name: 'page.jpg',
    mime_type: 'image/jpeg',
  }),
  {
    ok: true,
    id: 'up_2',
    sha256: 'sha2',
    filename: 'page.jpg',
    mime: 'image/jpeg',
    url: null,
    token: null,
    width: null,
    height: null,
    errors: [],
  },
);
const uploadFailure = normalizeUploadResponse({ detail: 'file too large' });
equal(uploadFailure.ok, false);
equal(uploadFailure.id, null);
deepEqual(uploadFailure.errors, [{ path: '$', message: 'file too large' }]);
equal(uploadMetaLabel(normalizeUploadResponse({ id: 'up', width: 10, height: 20, sha256: '0123456789abcdef' })), 'up · 10×20 · sha 0123456789…');
equal(uploadMetaLabel(normalizeUploadResponse({})), '');

deepEqual(normalizeDeleteUploadResponse({ ok: true, id: 'up_1', deleted: true }), {
  ok: true,
  id: 'up_1',
  errors: [],
});
deepEqual(
  normalizeDeleteUploadResponse({
    ok: false,
    errors: [{ path: 'upload', message: 'missing' }],
  }),
  { ok: false, id: null, errors: [{ path: 'upload', message: 'missing' }] },
);

deepEqual(byteSizeLabel(512), '512 B');
deepEqual(byteSizeLabel(2048), '2 KB');
deepEqual(byteSizeLabel(1.5 * 1024 * 1024), '1.5 MB');
deepEqual(byteSizeLabel(0), '—');
equal(imageSizeError(512 * 1024, 1), null);
equal(imageSizeError(2 * 1024 * 1024, 0), null);
equal(imageSizeError(2 * 1024 * 1024, 1), 'Ảnh 2.0 MB vượt giới hạn 1 MB.');

// Analyze: notes accept camelCase and snake_case; bar falls back to measure.
const draft = normalizeAnalyzeResponse({
  ok: true,
  measures: [{ index: 1, meter: '3/4', key: 'A minor' }, { meter: '' }],
  notes: [
    {
      measure: 1,
      beat: 0,
      duration_beats: 1.5,
      voice_hint: 'upper',
      written_pitch: 'E4',
      sounding_pitch: 'E3',
      string: 1,
      fret: 0,
      confidence: 0.91,
      conflict: false,
      review: 'pending',
    },
    { bar: 4, beat: 2.5, writtenPitch: 'A4', confidence: 91, conflict: true },
    { garbage: true },
  ],
  warnings: ['low contrast'],
  cached: true,
  partial: true,
  skipped_checks: ['pitch', 'playable'],
});
equal(draft.ok, true);
equal(draft.measures.length, 1);
equal(draft.measures[0]?.meter, '3/4');
equal(draft.notes.length, 2);
deepEqual(draft.notes[0], {
  measure: 1,
  bar: null,
  beat: 0,
  durationBeats: 1.5,
  voiceHint: 'upper',
  writtenPitch: 'E4',
  soundingPitch: 'E3',
  string: 1,
  fret: 0,
  confidence: 0.91,
  conflict: false,
  review: 'pending',
  tie: null,
  articulation: [],
});
equal(draft.notes[1]?.bar, 4);
equal(draft.notes[1]?.confidence, 0.91);
equal(draft.notes[1]?.conflict, true);
deepEqual(draft.warnings, ['low contrast']);
equal(draft.cached, true);
equal(draft.partial, true);
deepEqual(draft.skippedChecks, ['pitch', 'playable']);

const wrappedDraft = normalizeAnalyzeResponse({
  ok: true,
  cacheHit: true,
  draft: {
    measures: [{ index: 2, meter: '4/4' }],
    notes: [{ measure: 2, beat: 1, written_pitch: 'B4', confidence: 0.88 }],
    warnings: ['cut-off system'],
    review: 'pending',
  },
});
equal(wrappedDraft.ok, true);
equal(wrappedDraft.cached, true);
equal(wrappedDraft.measures[0]?.meter, '4/4');
equal(wrappedDraft.notes[0]?.writtenPitch, 'B4');
deepEqual(wrappedDraft.warnings, ['cut-off system']);

const pendingByDefault = normalizeAnalyzeResponse({
  ok: true,
  draft: { notes: [{ measure: 1, written_pitch: 'E4' }] },
});
equal(pendingByDefault.notes[0]?.review, 'pending');
equal(JSON.parse(draftJson(pendingByDefault)).notes[0].review, 'pending');
equal(JSON.parse(draftJson(pendingByDefault)).review, 'pending');

const failedDraft = normalizeAnalyzeResponse({
  ok: false,
  uploadId: 'up_1',
  error: { code: 'gemini_unconfigured', message: 'Gemini is not configured' },
});
equal(failedDraft.ok, false);
equal(failedDraft.errors[0]?.path, 'gemini_unconfigured');
equal(failedDraft.errors[0]?.message, 'Gemini is not configured');

deepEqual(normalizeAnalyzeResponse({ warnings: [{ message: 'faint tab' }] }).warnings, [
  'faint tab',
]);
deepEqual(normalizeAnalyzeResponse({}).notes, []);
equal(normalizeAnalyzeResponse({}).ok, true);
let analyzeThrew = false;
try {
  normalizeAnalyzeResponse(null);
} catch {
  analyzeThrew = true;
}
equal(analyzeThrew, true);

deepEqual(buildAnalyzeBody('up_1'), { uploadId: 'up_1' });
deepEqual(buildAnalyzeBody('up_1', {}), { uploadId: 'up_1' });
deepEqual(buildAnalyzeBody('up_1', { composer: 'Villa' }), {
  uploadId: 'up_1',
  metadata: { composer: 'Villa' },
});
deepEqual(buildAnalyzeBody('up_1', undefined, { x: 1 }), {
  uploadId: 'up_1',
  crop: { x: 1 },
});

// Confidence buckets drive the table colour and the label.
equal(confidenceBand(0.91), 'high');
equal(confidenceBand(0.85), 'high');
equal(confidenceBand(0.6), 'medium');
equal(confidenceBand(0.59), 'low');
equal(confidenceBand(null), 'unknown');
equal(confidenceBand(Number.NaN), 'unknown');
equal(confidenceLabel(0.915), '92%');
equal(confidenceLabel(1.4), '100%');
equal(confidenceLabel(null), '—');

const draftNote = draft.notes[0]!;
equal(noteBarLabel(draftNote), '1');
equal(noteBeatLabel(draftNote), '0');
equal(noteBeatLabel(draft.notes[1]!), '2.50');
equal(noteVoiceLabel(draftNote), 'upper');
equal(noteVoiceLabel({ ...draftNote, voiceHint: null }), '—');
equal(notePitchLabel(draftNote), 'E4 (E3)');
equal(notePitchLabel({ ...draftNote, soundingPitch: 'E4' }), 'E4');
equal(notePositionLabel(draftNote), 's1f0');
equal(notePositionLabel({ ...draftNote, fret: null }), '');

const rows = draftNoteRows(draft.notes);
equal(rows.length, 2);
deepEqual(rows[0], {
  index: 0,
  bar: '1',
  beat: '0',
  voice: 'upper',
  pitch: 'E4 (E3)',
  position: 's1f0',
  confidence: '91%',
  band: 'high',
  conflict: false,
  review: 'pending',
});
equal(rows[1]?.bar, '4');
equal(rows[1]?.conflict, true);
equal(draftNoteRows(draft.notes, 1).length, 1);

deepEqual(measureLines(draft.measures), ['m1 · 3/4 · A minor']);
equal(measureLines([]).length, 0);
equal(
  measureLines([{ index: null, meter: null, key: null }])[0],
  'm1',
);

const draftJsonText = draftJson(draft);
const draftJsonParsed = JSON.parse(draftJsonText) as {
  notes: Array<Record<string, unknown>>;
  measures: unknown[];
  warnings: string[];
};
equal(draftJsonParsed.notes.length, 2);
equal(draftJsonParsed.notes[0]?.written_pitch, 'E4');
equal(draftJsonParsed.notes[0]?.duration_beats, 1.5);
equal(draftJsonParsed.notes[1]?.bar, 4);
equal(draftJsonParsed.notes[1]?.conflict, true);
equal('sounding_pitch' in (draftJsonParsed.notes[1] ?? {}), false);
deepEqual(draftJsonParsed.warnings, ['low contrast']);

// Session errors map to friendly copy; other statuses keep the generic path.
equal(parseRetryAfter('12'), 12);
equal(parseRetryAfter('1.6'), 2);
equal(parseRetryAfter('later'), null);
equal(parseRetryAfter(null), null);
equal(studioSessionError(401, null)?.includes('Reload the page'), true);
equal(studioSessionError(403, null)?.includes('Reload the page'), true);
equal(studioSessionError(428, null)?.includes('Reload the page'), true);
equal(studioSessionError(429, 30), 'Studio quota reached. Try again in 30s.');
equal(studioSessionError(429, null), 'Studio quota reached. Try again later.');
equal(studioSessionError(500, 30), null);

// Session id shape, validation, and stable load through an injected store.
const shape = /^st_[a-z0-9]{16,}$/;
if (!shape.test(newStudioSession())) throw new Error('session shape is wrong');
const ids = new Set(Array.from({ length: 50 }, () => newStudioSession()));
equal(ids.size, 50);
equal(normalizeStudioSession('  st_abcdef123456  '), 'st_abcdef123456');
equal(normalizeStudioSession('short'), null);
equal(normalizeStudioSession('has space in it'), null);
equal(normalizeStudioSession(42), null);
deepEqual(sessionHeader('st_abcdef123456'), {
  [STUDIO_SESSION_HEADER]: 'st_abcdef123456',
});
deepEqual(sessionHeader(null), {});
deepEqual(sessionHeader('bad'), {});
equal(sessionLabel('st_abcdef123456'), 'st_abcdef1…');
equal(sessionLabel(null), 'no session');

type FakeStore = {
  value: string | null;
  writes: Array<{ key: string; value: string }>;
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
};

function fakeStore(initial: string | null, failRead = false, failWrite = false): FakeStore {
  const store: FakeStore = {
    value: initial,
    writes: [],
    async getItem(key: string) {
      if (failRead) throw new Error('read failed');
      equal(key, STUDIO_SESSION_KEY);
      return store.value;
    },
    async setItem(key: string, value: string) {
      if (failWrite) throw new Error('write failed');
      equal(key, STUDIO_SESSION_KEY);
      store.writes.push({ key, value });
      store.value = value;
    },
  };
  return store;
}

async function sessionPersistenceTests(): Promise<void> {
  const existing = 'st_existing123456';
  const reused = fakeStore(existing);
  equal(await loadStudioSession(reused), existing);
  equal(reused.writes.length, 0);

  const fresh = fakeStore(null);
  const created = await loadStudioSession(fresh);
  if (!shape.test(created)) throw new Error('created session shape is wrong');
  equal(fresh.writes.length, 1);
  equal(fresh.writes[0]?.value, created);
  equal(await loadStudioSession(fresh), created);

  const brokenRead = fakeStore(null, true);
  const fromBrokenRead = await loadStudioSession(brokenRead);
  if (!shape.test(fromBrokenRead)) throw new Error('broken-read session shape is wrong');

  const brokenWrite = fakeStore(null, false, true);
  const fromBrokenWrite = await loadStudioSession(brokenWrite);
  if (!shape.test(fromBrokenWrite)) throw new Error('broken-write session shape is wrong');
}

void sessionPersistenceTests()
  .then(() => {
    console.log('studio tests passed');
  })
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
