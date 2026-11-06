import {
  buildAnalyzeBody,
  buildAudioBody,
  buildAudioHashBody,
  buildJobBody,
  buildPreviewBody,
  buildTextureValidateBody,
  buildValidateBody,
  cropField,
  DEFAULT_JOB_RETRY_SEC,
  DEFAULT_STUDIO_VISIBILITY,
  emptyStudioQuota,
  normalizeAccessResponse,
  normalizeAnalyzeResponse,
  normalizeDeleteUploadResponse,
  normalizeAudioResponse,
  normalizeErrors,
  normalizeExamplesResponse,
  normalizeJobAcceptedResponse,
  normalizeJobPollResponse,
  normalizePreviewResponse,
  normalizePublishResponse,
  normalizePublishedSpecResponse,
  normalizeRollbackResponse,
  normalizeSpecsResponse,
  normalizeTextureValidateResponse,
  normalizeUploadResponse,
  normalizeValidateResponse,
  normalizeVisibility,
  nextJobPollDelayMs,
  parseRetryAfter,
  publishVisibilityQuery,
  resolveAudioUrl,
  studioSessionError,
} from './protocol';
import {
  DEFAULT_SAMPLE,
  DEFAULT_PUBLISHED_FILTER,
  PATTERNS,
  SAMPLES,
  STUDIO_FLOW_LABEL,
  STUDIO_LOCAL_NOTICE,
  STUDIO_VISION_ENABLED,
  accessDetail,
  accessReasonLabel,
  accessStatusLabel,
  accessSummary,
  audioStatusLabel,
  byteSizeLabel,
  checkSpecShape,
  checkSpecText,
  clampCropRect,
  confidenceBand,
  confidenceLabel,
  containRect,
  copyValue,
  cropForUpload,
  cropHandleAt,
  cropRectBetween,
  cropSizeLabel,
  defaultSampleForPattern,
  describeRequestFailure,
  draftJson,
  draftNoteRows,
  draftToTextureSpec,
  draftVoice,
  durationLabel,
  examplesStatusLabel,
  examplesToSamples,
  filterPublishedSpecs,
  exampleLabel,
  findSample,
  findSampleById,
  samplesForPatternMeter,
  fixtureForSpec,
  fixtureText,
  imageSizeError,
  jobStatusLabel,
  jsonErrorLocation,
  measureLines,
  meterLabel,
  metersForPattern,
  moveCropRect,
  nextPublishedList,
  nextPublishedSort,
  normalizeCropRect,
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
  publishedCountLabel,
  publishedFilterEmptyLabel,
  publishedFilterPatterns,
  publishedFilterSummary,
  publishedSortLabel,
  publishedSpecLineage,
  publishedSpecMeta,
  publishedSpecTitle,
  publishedVisibility,
  publishSuccessLabel,
  resizeCropRect,
  rollbackLabel,
  sampleText,
  scientificPitchToMidi,
  shortId,
  studioBusyHint,
  studioNextStep,
  studioVisionEnabled,
  textStats,
  textureDraftJson,
  textureDraftSummary,
  uploadMetaLabel,
  valueLines,
  visibilityHint,
  visibilityLabel,
  type StudioSample,
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
import {
  applyOffsetPreview,
  mergeVelocityEdits,
  normalizeVelocityContour,
  noteKey,
  pinnedLabel,
  ruleContourStatus,
  velocityContourIsEmpty,
  velocityLaneColumns,
  velocityLaneDiff,
  velocityLaneExtent,
  velocityLaneLabel,
  velocityLaneRows,
  velocitySlotContours,
  velocitySlotLabel,
  type MicroVelocity,
} from './velocity';
import {
  barLayouts,
  buildMusicXmlPassageBody,
  buildRoleLanes,
  clampZoom,
  defaultPassageRange,
  fullySelectedBars,
  isSupportedMeter,
  keySignatureLabel,
  meterChangeLabel,
  meterGroupTicks,
  meterGroups,
  meterQuarterBeats,
  meterTicks,
  musicXmlGrid,
  normalizeMusicXmlImport,
  normalizeMusicXmlPassage,
  passageRangeLabel,
  playheadTickAt,
  rangeTicks,
  resizeSelectionTicks,
  selectionFromTicks,
  snapTick,
  validatePassageRange,
  zoomLabel,
  type MusicXmlImport,
  type MusicXmlRoleLane,
} from './musicxml';
import {
  GENERIC_PATTERN_IDS,
  VILLA_COMPOSER,
  VILLA_RENDERER,
  appendPatternSentence,
  composerOptions,
  buildPatternDraftExport,
  buildSentenceDraftBody,
  createPatternDraft,
  existingTemplateOptions,
  genericPatternOptions,
  newPatternId,
  normalizeSentenceDraftResponse,
  patternDraftJson,
  patternDraftLabel,
  removePatternSentence,
  sentenceDraftKey,
  slugifyPatternId,
  villaMeterSupported,
  villaTemplateOptions,
  type PatternDraft,
  type PatternDraftSentence,
} from './sentenceDraft';
import { saveVelocityContourToSpec } from './velocitySpec';

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

// The vision flag is build-time only: `studioVisionEnabled` is the pure parser
// (only `1` / `true` turn it on) and the exported constant is whatever
// `EXPO_PUBLIC_STUDIO_VISION` inlined when the module loaded.
equal(studioVisionEnabled('1'), true);
equal(studioVisionEnabled('true'), true);
equal(studioVisionEnabled('0'), false);
equal(studioVisionEnabled('false'), false);
equal(studioVisionEnabled('TRUE'), false);
equal(studioVisionEnabled(' true '), false);
equal(studioVisionEnabled(''), false);
equal(studioVisionEnabled(undefined), false);
equal(studioVisionEnabled(null), false);
equal(
  STUDIO_VISION_ENABLED,
  studioVisionEnabled(process.env.EXPO_PUBLIC_STUDIO_VISION),
);

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

const duplicateExamples = examplesToSamples([
  villaExample,
  {
    ...villaExample,
    id: 'suite_mazurka_arpeggio_aaba',
    pattern: 'villa_pattern',
    meter: '3/4',
    payload: { ...villaExample.payload, id: 'suite_mazurka_arpeggio_aaba', meter: '3/4' },
  },
]);
equal(samplesForPatternMeter('villa_pattern', '4/4', duplicateExamples).length, 1);
equal(samplesForPatternMeter('villa_pattern', '3/4', duplicateExamples).length, 1);
equal(findSampleById('suite_mazurka_arpeggio_aaba', duplicateExamples)?.meter, '3/4');
equal(findSampleById('missing', duplicateExamples), undefined);
equal(exampleLabel(duplicateExamples[0]!), 'villa_arpeggio_aba');
equal(exampleLabel({ ...duplicateExamples[0]!, id: undefined }), 'Villa arpeggio · 4/4');

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
  visibility: 'private' as const,
};
equal(publishedSpecTitle(published), 'Villa arpeggio · 4/4');
equal(publishedSpecMeta(published), 'v3 · 2026-11-05 09:41');
equal(shortId(published.id), '0123456789…');
equal(shortId('short'), 'short');
equal(durationLabel(1.24), '1.2s');
equal(durationLabel(61), '1:01');
equal(durationLabel(0), '—');
equal(durationLabel(Number.NaN), '—');

// Visibility, copy formatting, and status copy are pure and locale-free.
equal(visibilityLabel('public'), 'Public');
equal(visibilityLabel('private'), 'Private');
equal(
  visibilityHint('public'),
  'Every Studio session can list and load this version.',
);
equal(
  visibilityHint('private'),
  'Only this Studio session can list and load this version.',
);
equal(publishedVisibility(published), 'private');
equal(publishedVisibility({ visibility: 'public' }), 'public');
equal(publishedVisibility({}), 'private');
equal(publishedCountLabel(0), 'No versions yet');
equal(publishedCountLabel(1), '1 version');
equal(publishedCountLabel(3), '3 versions');

// Published-list filter/sort helpers default to the unchanged server list.
const publicVersion = {
  ...published,
  id: 'fedcba9876543210fedcba9876543210',
  pattern: 'galop',
  meter: '*',
  version: 4,
  createdAt: '2026-11-06T10:00:00+00:00',
  visibility: 'public' as const,
};
const olderVersion = {
  ...published,
  id: 'aaaabbbbccccddddeeeeffff00001111',
  version: 1,
  createdAt: '2026-11-04T10:00:00+00:00',
};
const filterItems = [published, publicVersion, olderVersion];
deepEqual(publishedFilterPatterns(filterItems), ['villa_pattern', 'galop']);
deepEqual(filterPublishedSpecs(filterItems, DEFAULT_PUBLISHED_FILTER), filterItems);
deepEqual(
  filterPublishedSpecs(filterItems, {
    ...DEFAULT_PUBLISHED_FILTER,
    visibility: 'public',
  }),
  [publicVersion],
);
deepEqual(
  filterPublishedSpecs(filterItems, {
    ...DEFAULT_PUBLISHED_FILTER,
    pattern: 'villa_pattern',
  }).map((item) => item.id),
  [published.id, olderVersion.id],
);
deepEqual(
  filterPublishedSpecs(filterItems, {
    ...DEFAULT_PUBLISHED_FILTER,
    sort: 'newest',
  }).map((item) => item.id),
  [publicVersion.id, published.id, olderVersion.id],
);
deepEqual(
  filterPublishedSpecs(filterItems, {
    ...DEFAULT_PUBLISHED_FILTER,
    sort: 'oldest',
  }).map((item) => item.id),
  [olderVersion.id, published.id, publicVersion.id],
);
equal(publishedSortLabel('listed'), 'Server order');
equal(publishedSortLabel('newest'), 'Newest first');
equal(publishedSortLabel('oldest'), 'Oldest first');
equal(nextPublishedSort('listed'), 'newest');
equal(nextPublishedSort('newest'), 'oldest');
equal(nextPublishedSort('oldest'), 'listed');
equal(publishedFilterSummary(3, 3, DEFAULT_PUBLISHED_FILTER), '3 versions');
equal(
  publishedFilterSummary(3, 1, {
    ...DEFAULT_PUBLISHED_FILTER,
    visibility: 'public',
  }),
  '1 of 3 versions · Public',
);
equal(
  publishedFilterSummary(3, 3, {
    ...DEFAULT_PUBLISHED_FILTER,
    sort: 'newest',
  }),
  '3 of 3 versions · Newest first',
);
equal(
  publishedFilterSummary(3, 2, {
    visibility: 'private',
    pattern: 'villa_pattern',
    sort: 'oldest',
  }),
  '2 of 3 versions · Private · Villa arpeggio · Oldest first',
);
equal(publishedFilterEmptyLabel(0, DEFAULT_PUBLISHED_FILTER), 'No versions yet. Publish a spec to start its history; rows load the stored payload back into the editor.');
equal(
  publishedFilterEmptyLabel(3, {
    ...DEFAULT_PUBLISHED_FILTER,
    visibility: 'public',
    pattern: 'villa_pattern',
  }),
  'No Public · Villa arpeggio versions match this filter. Clear it to see all 3 versions.',
);

// Orientation and busy copy stay local-only and explicit about locked controls.
equal(STUDIO_FLOW_LABEL, 'Example → Spec → Preview → WAV → Publish');
equal(STUDIO_LOCAL_NOTICE.title, 'Local Studio · dev-only');
equal(
  STUDIO_LOCAL_NOTICE.text,
  'Requests go to the Studio API on this machine. Feature flags default off, there is no sign-in or shared library, and each browser keeps a local Studio session id. Published rows are dev rows.',
);
equal(
  studioNextStep('preview'),
  'Next: pick an example in 1 · Example, edit 2 · Spec JSON, then press Preview. Step 4 shows the plan, row, matrix, notes, and render hash.',
);
equal(
  studioNextStep('audio'),
  'Next: run a successful Preview, then press Play preview in step 4 to render and hear the short WAV.',
);
equal(
  studioNextStep('publish'),
  'Next: edit 2 · Spec JSON, press Preview to check it, then Publish in step 2. Step 5 lists the versions this session published.',
);
equal(
  studioBusyHint('validate'),
  'Validating — editor actions are disabled until the request finishes.',
);
equal(
  studioBusyHint('preview'),
  'Rendering preview — editor actions are disabled until it finishes.',
);
equal(
  studioBusyHint('publish'),
  'Publishing — editor actions are disabled until the request finishes.',
);
equal(studioBusyHint(null), null);

// Rule contours explain why the lane and Save to spec stay read-only.
{
  const rule: MicroVelocity = {
    kind: 'rule',
    ruleId: 'galop1',
    ruleVersion: 1,
    params: {},
  };
  equal(ruleContourStatus(null, false), null);
  equal(ruleContourStatus({ kind: 'offsets', notes: [] }, false), null);
  deepEqual(ruleContourStatus(rule, true), {
    blocked: true,
    label: 'Rule contour needs a flatten table',
    detail:
      'Some notes have no per-rule flatten entry, so their offsets stay empty and Save to spec is blocked. The lane is read-only until the rule or a flatten table supplies every offset.',
  });
  deepEqual(ruleContourStatus(rule, false), {
    blocked: false,
    label: 'Rule contour is read-only',
    detail:
      'Offsets resolve through the flatten table, but the rule carrier stays code-owned. Editing and Save to spec remain disabled.',
  });
}
equal(copyValue('  0123456789abcdef  '), '0123456789abcdef');
equal(copyValue('   '), null);
equal(copyValue(null), null);
equal(copyValue(undefined), null);
equal(
  publishSuccessLabel('public', 3, published.id),
  'Published v3 · Public · 0123456789…',
);
equal(
  publishSuccessLabel('private', null, 'short'),
  'Published a new version · Private · short',
);
equal(audioStatusLabel('idle'), 'No audio rendered for this preview yet.');
equal(audioStatusLabel('loading'), 'Synthesizing the cached preview WAV…');
equal(audioStatusLabel('ready', 1.24, true), '1.2s WAV · playing');
equal(audioStatusLabel('ready', 61, false), '1:01 WAV · ready');
equal(audioStatusLabel('error'), 'Audio preview failed.');
equal(jobStatusLabel('queued'), 'Queued for the Studio worker…');
equal(jobStatusLabel('running'), 'Rendering preview on the Studio worker…');
deepEqual(examplesStatusLabel({ loading: true, source: 'fallback', count: 7, note: null }), {
  tone: 'loading',
  text: 'Loading examples from the API…',
});
deepEqual(examplesStatusLabel({ loading: false, source: 'api', count: 1, note: null }), {
  tone: 'ok',
  text: '1 example loaded from the API.',
});
deepEqual(examplesStatusLabel({ loading: false, source: 'api', count: 4, note: null }), {
  tone: 'ok',
  text: '4 examples loaded from the API.',
});
deepEqual(examplesStatusLabel({ loading: false, source: 'fallback', count: 0, note: null }), {
  tone: 'error',
  text: 'No examples available. Paste a spec into the editor to continue.',
});
deepEqual(
  examplesStatusLabel({
    loading: false,
    source: 'fallback',
    count: 7,
    note: 'Examples API unavailable — using embedded samples.',
  }),
  { tone: 'warn', text: 'Examples API unavailable — using embedded samples.' },
);

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
equal(preview.microVelocity, null);

// The phase-2 contour field passes through unchanged; the lane normaliser
// handles the documented shape.
const contourPreview = normalizePreviewResponse({
  ok: true,
  notes: [],
  microVelocity: { kind: 'offsets', notes: [] },
});
deepEqual(contourPreview.microVelocity, { kind: 'offsets', notes: [] });

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
    visibility: 'private',
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
    visibility: 'private',
    errors: [{ path: 'spec.slots[0]', message: 'bad' }],
  },
);

// Publish visibility is explicit on the wire and fails closed to private.
equal(DEFAULT_STUDIO_VISIBILITY, 'private');
equal(normalizeVisibility(undefined), 'private');
equal(normalizeVisibility('PUBLIC'), 'public');
equal(normalizeVisibility('public'), 'public');
equal(normalizeVisibility('team'), 'private');
equal(normalizeVisibility('team', 'public'), 'public');
equal(publishVisibilityQuery('private'), '?visibility=private');
equal(publishVisibilityQuery('public'), '?visibility=public');
deepEqual(
  normalizePublishResponse({
    ok: true,
    id: 'pub',
    pattern: 'galop',
    meter: '*',
    version: 1,
    visibility: 'public',
  }),
  {
    ok: true,
    id: 'pub',
    pattern: 'galop',
    meter: '*',
    version: 1,
    visibility: 'public',
    errors: [],
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
    visibility: 'private',
  },
]);
deepEqual(normalizeSpecsResponse([published]), [published]);
deepEqual(normalizeSpecsResponse({ ok: true }), []);
equal(
  normalizeSpecsResponse({
    specs: [{ ...published, visibility: 'public' }],
  })[0]?.visibility,
  'public',
);
equal(
  normalizeSpecsResponse({
    specs: [{ ...published, visibility: 'everyone' }],
  })[0]?.visibility,
  'private',
);

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
    visibility: 'private',
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
  visibility: 'private',
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
    visibility: 'private',
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
    visibility: 'private',
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
equal(
  accessDetail(access),
  '20 uploads/day · 100 analyses/day · 50 publishes/day · max 20 MB · 1 preview slot',
);
deepEqual(accessStatusLabel('loading'), {
  tone: 'loading',
  text: 'Checking session and Studio access…',
});
deepEqual(accessStatusLabel('ready', access), {
  tone: 'ok',
  text: 'Open beta · 20 uploads/day · 100 analyses/day · 50 publishes/day · max 20 MB · 1 preview slot',
});
deepEqual(accessStatusLabel('error', undefined, 'offline'), {
  tone: 'warn',
  text: 'Access check failed · offline. Uploads stay enabled; the server enforces quota.',
});
deepEqual(
  accessStatusLabel('ready', normalizeAccessResponse({ enabled: false, reason: 'disabled' })),
  {
    tone: 'warn',
    text: 'Studio disabled · Disabled · the sentence editor still works.',
  },
);
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
equal(normalizeAnalyzeResponse({}).ok, false);
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
deepEqual(buildAnalyzeBody('up_1', undefined, { x: 10, y: 20, w: 100, h: 50 }), {
  uploadId: 'up_1',
  crop: { x: 10, y: 20, w: 100, h: 50 },
});
deepEqual(
  buildAnalyzeBody(
    'up_1',
    { composer: 'Villa' },
    { x: 10, y: 20, w: 100, h: 50 },
  ),
  {
    uploadId: 'up_1',
    crop: { x: 10, y: 20, w: 100, h: 50 },
    metadata: { composer: 'Villa' },
  },
);
// Absent / empty / too-small / non-finite crops are omitted entirely.
deepEqual(buildAnalyzeBody('up_1', undefined, null), { uploadId: 'up_1' });
deepEqual(buildAnalyzeBody('up_1', undefined, { x: 0, y: 0, w: 0, h: 0 }), {
  uploadId: 'up_1',
});
deepEqual(buildAnalyzeBody('up_1', undefined, { x: 0, y: 0, w: 8, h: 80 }), {
  uploadId: 'up_1',
});
deepEqual(
  buildAnalyzeBody('up_1', undefined, {
    x: Number.NaN,
    y: 0,
    w: 100,
    h: 80,
  }),
  { uploadId: 'up_1' },
);

// Crop geometry: clamp, round, min-size, drag/move/resize, and serialization.
deepEqual(clampCropRect({ x: -10, y: -5, w: 200, h: 120 }, { width: 100, height: 100 }), {
  x: 0,
  y: 0,
  w: 100,
  h: 100,
});
deepEqual(clampCropRect({ x: 90, y: 90, w: 50, h: 50 }, { width: 100, height: 100 }), {
  x: 50,
  y: 50,
  w: 50,
  h: 50,
});
deepEqual(
  normalizeCropRect({ x: 10.4, y: 20.6, w: 100.2, h: 50.7 }, { width: 200, height: 200 }),
  { x: 10, y: 21, w: 100, h: 51 },
);
equal(
  normalizeCropRect({ x: 0, y: 0, w: 8, h: 200 }, { width: 200, height: 200 }),
  null,
);
equal(
  normalizeCropRect({ x: 0, y: 0, w: 16, h: 16 }, { width: 200, height: 200 })?.w,
  16,
);
equal(
  normalizeCropRect({ x: 0, y: 0, w: 100, h: 100 }, { width: 0, height: 0 }),
  null,
);
deepEqual(
  cropRectBetween({ x: 50, y: 60 }, { x: 10, y: 20 }, { width: 100, height: 100 }),
  { x: 10, y: 20, w: 40, h: 40 },
);
deepEqual(
  cropRectBetween({ x: 10, y: 20 }, { x: 50, y: 60 }, { width: 100, height: 100 }),
  { x: 10, y: 20, w: 40, h: 40 },
);
deepEqual(
  moveCropRect({ x: 10, y: 10, w: 40, h: 40 }, 100, -5, { width: 80, height: 80 }),
  { x: 40, y: 5, w: 40, h: 40 },
);
deepEqual(
  resizeCropRect({ x: 10, y: 10, w: 40, h: 40 }, 'se', 20, 10, {
    width: 100,
    height: 100,
  }),
  { x: 10, y: 10, w: 60, h: 50 },
);
deepEqual(
  resizeCropRect({ x: 10, y: 10, w: 40, h: 40 }, 'nw', -20, -10, {
    width: 100,
    height: 100,
  }),
  { x: 0, y: 0, w: 50, h: 50 },
);
equal(cropHandleAt({ x: 10, y: 10, w: 50, h: 40 }, { x: 11, y: 11 }, 8), 'nw');
equal(cropHandleAt({ x: 10, y: 10, w: 50, h: 40 }, { x: 59, y: 12 }, 8), 'ne');
equal(cropHandleAt({ x: 10, y: 10, w: 50, h: 40 }, { x: 30, y: 30 }, 8), 'inside');
equal(cropHandleAt({ x: 10, y: 10, w: 50, h: 40 }, { x: 100, y: 100 }, 8), null);
equal(cropSizeLabel({ x: 0, y: 0, w: 900, h: 420 }), '900 × 420 px');
deepEqual(cropField({ x: 1.4, y: 2.6, w: 100.2, h: 50.5 }), {
  x: 1,
  y: 3,
  w: 100,
  h: 51,
});
equal(cropField({ x: 0, y: 0, w: 4, h: 4 }), null);
equal(cropField(null), null);

const cropRect = { x: 10, y: 20, w: 100, h: 50 };
deepEqual(cropForUpload({ uploadId: 'up_1', rect: cropRect }, 'up_1'), cropRect);
equal(cropForUpload({ uploadId: 'up_1', rect: cropRect }, 'up_2'), null);
equal(cropForUpload(null, 'up_1'), null);
equal(cropForUpload({ uploadId: 'up_1', rect: cropRect }, null), null);

deepEqual(containRect({ width: 1000, height: 500 }, { width: 300, height: 300 }), {
  left: 0,
  top: 75,
  width: 300,
  height: 150,
});
deepEqual(containRect({ width: 0, height: 0 }, { width: 300, height: 300 }), {
  left: 0,
  top: 0,
  width: 0,
  height: 0,
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

// ---------------------------------------------------------------------------
// Phase 1 back half: Gemini draft -> TextureSpec draft.
// ---------------------------------------------------------------------------

equal(scientificPitchToMidi('E3'), 52);
equal(scientificPitchToMidi('E4'), 64);
equal(scientificPitchToMidi('C4'), 60);
equal(scientificPitchToMidi('F#4'), 66);
equal(scientificPitchToMidi('Bb2'), 46);
equal(scientificPitchToMidi('not-a-pitch'), null);
equal(scientificPitchToMidi('C10'), null);

equal(draftVoice('upper'), 1);
equal(draftVoice('middle'), 2);
equal(draftVoice('lower'), 3);
equal(draftVoice('bass'), 3);
equal(draftVoice('4'), 4);
equal(draftVoice('5'), 1);
equal(draftVoice('constructor'), 1);
equal(draftVoice(null), 1);

const textureSource = normalizeAnalyzeResponse({
  ok: true,
  measures: [{ index: 1, meter: '3/4', key: 'A minor' }],
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
      articulation: ['accent'],
    },
    {
      bar: 4,
      beat: 2.5,
      duration_beats: 0.5,
      voice_hint: 'lower',
      written_pitch: 'A4',
      confidence: 0.5,
      conflict: true,
      review: 'edited',
    },
    {
      measure: 1,
      beat: 1.5,
      duration_beats: 1.5,
      voice_hint: '4',
      sounding_pitch: 'F#3',
    },
    {
      measure: 1,
      beat: 0,
      duration_beats: 1,
      written_pitch: 'not-a-pitch',
    },
    { measure: 1, duration_beats: 1, written_pitch: 'E4' },
    { beat: 0, duration_beats: 1, written_pitch: 'E4' },
  ],
  warnings: ['low contrast'],
});
// Draft normalization assigns pending when a note has no explicit review.
equal(textureSource.notes[2]?.review, 'pending');

const texture = draftToTextureSpec(textureSource);
equal(texture.eventCount, 3);
equal(texture.skipped, 3);
equal(texture.meter, '3/4');
equal(texture.warnings.length, 4);
equal(texture.warnings[0], 'low contrast');
equal(texture.warnings[1], 'Note 4 skipped: cannot parse pitch not-a-pitch.');
equal(texture.warnings[2], 'Note 5 skipped: missing beat.');
equal(texture.warnings[3], 'Note 6 skipped: missing measure/bar.');
equal(textureDraftSummary(texture), '3 events · 3/4 · 3 skipped · 4 warnings');

deepEqual(texture.spec, {
  id: 'gemini_draft',
  composer: 'unknown',
  kind: 'pattern',
  level: 'texture',
  parent: null,
  runtime: 'code',
  status: 'draft',
  meter_variants: [
    {
      meter: {
        id: '3/4',
        beats: 3,
        beat_type: 4,
        eighths_per_bar: 6,
        strong_eighths: [0],
        subbar_breaks: [4],
        extra_weights: [[4, 0.8]],
      },
      materializer: 'grid',
      transform: 'none',
      unsupported: false,
      reason: null,
      sentences: [],
    },
  ],
  authored: {
    events: [
      {
        bar: 0,
        beat: 0,
        duration_beats: 1.5,
        voice: 1,
        pitch: { kind: 'literal_midi', value: 52 },
        staff: 1,
        tie: 'none',
        slur: 'none',
        accent: true,
        tenuto: false,
        staccato: false,
        conflict: false,
        review: 'pending',
        string: 1,
        fret: 0,
        written_pitch: 'E4',
        sounding_pitch: 'E3',
        confidence: 0.91,
      },
      {
        bar: 4,
        beat: 2.5,
        duration_beats: 0.5,
        voice: 3,
        pitch: { kind: 'literal_midi', value: 69 },
        staff: 1,
        tie: 'none',
        slur: 'none',
        accent: false,
        tenuto: false,
        staccato: false,
        conflict: true,
        review: 'edited',
        written_pitch: 'A4',
        confidence: 0.5,
      },
      {
        bar: 0,
        beat: 1.5,
        duration_beats: 1.5,
        voice: 4,
        pitch: { kind: 'literal_midi', value: 54 },
        staff: 1,
        tie: 'none',
        slur: 'none',
        accent: false,
        tenuto: false,
        staccato: false,
        conflict: false,
        review: 'pending',
        sounding_pitch: 'F#3',
      },
    ],
  },
});

// Options only change the identity/materializer, never the placement rules.
const texture44 = draftToTextureSpec(
  normalizeAnalyzeResponse({
    ok: true,
    measures: [{ index: 1, meter: '4/4' }],
    notes: [{ measure: 1, beat: 0, duration_beats: 1, written_pitch: 'E4' }],
  }),
  { id: 'page_1', composer: 'villa', materializer: 'grid_4_4' },
);
equal(texture44.spec.id, 'page_1');
equal(texture44.spec.composer, 'villa');
deepEqual(
  (texture44.spec.meter_variants as Array<Record<string, unknown>>)[0]?.meter,
  {
    id: '4/4',
    beats: 4,
    beat_type: 4,
    eighths_per_bar: 8,
    strong_eighths: [0, 4],
    subbar_breaks: [4],
    extra_weights: [],
  },
);
equal(
  (texture44.spec.meter_variants as Array<Record<string, unknown>>)[0]?.materializer,
  'grid_4_4',
);

// 6/8 is the third supported meter; 5/4 produces a partial spec plus warning.
const texture68 = draftToTextureSpec(
  normalizeAnalyzeResponse({
    ok: true,
    measures: [{ index: 1, meter: '6/8' }],
    notes: [{ measure: 1, beat: 0, duration_beats: 1, sounding_pitch: 'E3' }],
  }),
);
equal(texture68.meter, '6/8');
deepEqual(
  (texture68.spec.meter_variants as Array<Record<string, unknown>>)[0]?.meter,
  {
    id: '6/8',
    beats: 6,
    beat_type: 8,
    eighths_per_bar: 6,
    strong_eighths: [0, 3],
    subbar_breaks: [3],
    extra_weights: [],
  },
);

const unsupportedMeter = draftToTextureSpec(
  normalizeAnalyzeResponse({
    ok: true,
    measures: [{ index: 1, meter: '5/4' }],
    notes: [{ measure: 1, beat: 0, duration_beats: 1, sounding_pitch: 'E3' }],
  }),
);
equal(unsupportedMeter.meter, null);
deepEqual(unsupportedMeter.spec.meter_variants, []);
equal(unsupportedMeter.eventCount, 1);
equal(
  unsupportedMeter.warnings.some((warning) =>
    warning.includes('Unsupported meter "5/4"'),
  ),
  true,
);
equal(textureDraftSummary(unsupportedMeter), '1 event · no meter · 1 warning');

const emptyDraft = draftToTextureSpec(
  normalizeAnalyzeResponse({
    ok: true,
    measures: [{ index: 1, meter: '4/4' }],
  }),
);
equal(emptyDraft.eventCount, 0);
equal(
  emptyDraft.warnings.some((warning) => warning.includes('Draft has no notes')),
  true,
);
equal(textureDraftSummary(emptyDraft), '0 events · 4/4 · 1 warning');

const noMeasureDraft = draftToTextureSpec(
  normalizeAnalyzeResponse({
    ok: true,
    notes: [{ bar: 2, beat: 0, duration_beats: 1, sounding_pitch: 'E3' }],
  }),
);
equal(noMeasureDraft.meter, null);
equal(
  noMeasureDraft.warnings.some((warning) =>
    warning.includes('No meter on the first measure'),
  ),
  true,
);
equal((noMeasureDraft.spec.authored as { events: unknown[] }).events.length, 1);

// A fallback bar is opt-in; without it a note with no measure/bar is skipped.
const fallbackBar = draftToTextureSpec(
  normalizeAnalyzeResponse({
    ok: true,
    measures: [{ index: 1, meter: '4/4' }],
    notes: [{ beat: 0, duration_beats: 1, sounding_pitch: 'E3' }],
  }),
  { fallbackBar: 7 },
);
equal(
  ((fallbackBar.spec.authored as { events: Array<{ bar: number }> }).events[0]).bar,
  7,
);

// Fret without a string is dropped instead of shipping an invalid event.
const droppedFret = draftToTextureSpec(
  normalizeAnalyzeResponse({
    ok: true,
    measures: [{ index: 1, meter: '4/4' }],
    notes: [{ measure: 1, beat: 0, duration_beats: 1, sounding_pitch: 'E3', fret: 3 }],
  }),
);
const droppedFretEvent = (
  droppedFret.spec.authored as { events: Array<Record<string, unknown>> }
).events[0]!;
equal('fret' in droppedFretEvent, false);
equal(
  droppedFret.warnings.some((warning) => warning.includes('fret without string')),
  true,
);

const invalidReview = draftToTextureSpec({
  ...textureSource,
  review: 'approved',
  notes: [{ ...textureSource.notes[0]!, review: 'approved' }],
});
equal(
  (invalidReview.spec.authored as { events: Array<{ review: string }> }).events[0]?.review,
  'pending',
);

const textureJson = JSON.parse(textureDraftJson(texture)) as {
  authored: { events: Array<Record<string, unknown>> };
};
equal(textureJson.authored.events.length, 3);
equal(textureJson.authored.events[0]?.duration_beats, 1.5);

// Texture validate body wraps the spec; the response normalizer accepts the
// documented shape, FastAPI's string detail, and an ok flag without errors.
deepEqual(buildTextureValidateBody({ id: 'page_1' }), { spec: { id: 'page_1' } });
deepEqual(
  normalizeTextureValidateResponse({
    ok: false,
    errors: [{ path: 'authored.events[0].review', message: 'unknown value' }],
  }),
  {
    ok: false,
    errors: [{ path: 'authored.events[0].review', message: 'unknown value' }],
  },
);
deepEqual(normalizeTextureValidateResponse({ ok: true }), { ok: true, errors: [] });
deepEqual(normalizeTextureValidateResponse({ detail: 'invalid spec' }), {
  ok: false,
  errors: [{ path: '$', message: 'invalid spec' }],
});

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

// Phase 1 job queue: 202 accepted, 409 pending with Retry-After, 200 done.
deepEqual(buildJobBody('validate', DEFAULT_SAMPLE.spec), {
  kind: 'validate',
  spec: DEFAULT_SAMPLE.spec,
});
deepEqual(buildJobBody('preview', DEFAULT_SAMPLE.spec, { length: 4 }), {
  kind: 'preview',
  spec: DEFAULT_SAMPLE.spec,
  fixture: { length: 4 },
});

deepEqual(
  normalizeJobAcceptedResponse({ ok: true, jobId: 'job_abc', status: 'queued' }),
  { jobId: 'job_abc', status: 'queued' },
);
deepEqual(
  normalizeJobAcceptedResponse({ job_id: 'job_snake', status: 'running' }),
  { jobId: 'job_snake', status: 'running' },
);
let acceptedThrew = false;
try {
  normalizeJobAcceptedResponse({ ok: true });
} catch {
  acceptedThrew = true;
}
equal(acceptedThrew, true);

deepEqual(
  normalizeJobPollResponse({ ok: false, jobId: 'job_abc', status: 'running' }, 409, 2),
  { kind: 'pending', jobId: 'job_abc', status: 'running', retryAfterSec: 2 },
);
deepEqual(
  normalizeJobPollResponse({ ok: false, jobId: 'job_abc', status: 'queued' }, 409),
  {
    kind: 'pending',
    jobId: 'job_abc',
    status: 'queued',
    retryAfterSec: DEFAULT_JOB_RETRY_SEC,
  },
);

const doneJob = normalizeJobPollResponse(
  {
    ok: true,
    jobId: 'job_abc',
    status: 'ok',
    result: {
      ok: true,
      errors: [],
      plan: [{ start: 0 }],
      row: ['x'],
      notes: [],
      renderHash: 'sha256:abc',
      matrix: [],
    },
  },
  200,
);
if (!doneJob || doneJob.kind !== 'done' || !doneJob.result) {
  throw new Error('expected a completed job result');
}
equal(doneJob.result.renderHash, 'sha256:abc');
deepEqual(doneJob.result.plan, [{ start: 0 }]);
deepEqual(doneJob.errors, []);

deepEqual(
  normalizeJobPollResponse(
    {
      ok: false,
      jobId: 'job_abc',
      status: 'error',
      errors: [{ path: 'preview', message: 'boom' }],
    },
    200,
  ),
  {
    kind: 'done',
    jobId: 'job_abc',
    status: 'error',
    result: null,
    errors: [{ path: 'preview', message: 'boom' }],
  },
);
equal(normalizeJobPollResponse({}, 200), null);
equal(
  normalizeJobPollResponse({ ok: true, jobId: 'job_abc', status: 'weird' }, 200),
  null,
);

// Backoff starts at 300 ms, doubles to a 5 s cap, and honours Retry-After.
equal(nextJobPollDelayMs(0), 300);
equal(nextJobPollDelayMs(1), 600);
equal(nextJobPollDelayMs(2), 1200);
equal(nextJobPollDelayMs(4), 4800);
equal(nextJobPollDelayMs(99), 4800);
equal(nextJobPollDelayMs(0, 2), 2000);
equal(nextJobPollDelayMs(3, 99), 5000);

// ---------------------------------------------------------------------------
// Micro-velocity lane (docs §6.9): pure rows, pinned writers, rule seam.

const laneNotes = [
  { bar: 0, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 },
  { bar: 0, beat: 1, duration: 0.5, midi: 65, voice: 1, velocity: 72 },
  {
    bar: 0,
    beat: 1,
    duration: 0.5,
    midi: 67,
    voice: 1,
    velocity: 72,
    finger: 'a',
  },
  { bar: 0, beat: 0.5, duration: 0.5, midi: 60, voice: 2, velocity: 60 },
  { bar: 0, beat: 0, duration: 1, midi: 48, voice: 3, velocity: 58 },
  { bar: 1, beat: 0, duration: 1, midi: 55, voice: 4, velocity: 61 },
];

function laneRow(rows: ReturnType<typeof velocityLaneRows>, midi: number) {
  const row = rows.find((item) => item.note.midi === midi);
  if (!row) throw new Error(`missing lane row for midi ${midi}`);
  return row;
}

// No contour: every offset is 0, every row is read-only and keeps realized
// velocity. Lane 4 exists because these notes use it.
const defaultRows = velocityLaneRows(laneNotes);
equal(defaultRows.length, 6);
equal(defaultRows.every((row) => row.offset === 0), true);
equal(defaultRows.every((row) => row.authored === false), true);
equal(defaultRows.every((row) => row.pinned === false), true);
equal(laneRow(defaultRows, 64).previewVelocity, 70);
equal(laneRow(defaultRows, 64).lane, 'voice1');
equal(laneRow(defaultRows, 55).lane, 'voice4');
equal(velocityLaneRows(laneNotes, null, { includeVoice4: false }).length, 5);

// A finger-`p` voice-3 note is the thumb lane even with no contour.
const defaultThumbRow = velocityLaneRows([
  { bar: 0, beat: 0, duration: 1, midi: 43, voice: 3, velocity: 55, finger: 'p' },
])[0];
equal(defaultThumbRow?.lane, 'thumb');
equal(defaultThumbRow?.offset, 0);
equal(defaultThumbRow?.previewVelocity, 55);

const offsetsContour: MicroVelocity = {
  kind: 'offsets',
  notes: [
    { bar: 0, beat: 0, voice: 1, offset: -6 },
    { bar: 0, beat: 1, voice: 1, finger: 'a', offset: 3 },
  ],
  thumb: [{ bar: 0, beat: 0, voice: 3, finger: 'p', offset: -4 }],
};

const offsetRows = velocityLaneRows(laneNotes, offsetsContour);
equal(laneRow(offsetRows, 64).offset, -6);
equal(laneRow(offsetRows, 64).authored, true);
equal(laneRow(offsetRows, 64).previewVelocity, 64);
// A fingerless note does not borrow a finger-specific offset.
equal(laneRow(offsetRows, 65).offset, 0);
equal(laneRow(offsetRows, 65).previewVelocity, 72);
// A finger-specific note matches exactly.
equal(laneRow(offsetRows, 67).offset, 3);
equal(laneRow(offsetRows, 67).previewVelocity, 75);
// Voice 3 + the thumb coordinate is its own lane, even without a note finger.
equal(laneRow(offsetRows, 48).lane, 'thumb');
equal(laneRow(offsetRows, 48).offset, -4);
equal(laneRow(offsetRows, 48).previewVelocity, 54);
equal(velocityLaneRows(laneNotes, offsetsContour, { includeThumb: false }).length, 5);
equal(velocityLaneRows(laneNotes, offsetsContour, { voice: 2 }).length, 2);
equal(
  velocityLaneRows(laneNotes, offsetsContour, { voice: 2 }).every(
    (row) => row.thumb || row.voice === 2,
  ),
  true,
);

// Sixteenths at 0/0.25/0.5/0.75 and a triplet at 1/3 all match by beat.
// The contour's 0.3333334 rounds to the same 6-decimal key as the note's 1/3.
const gridNotes = [
  { bar: 0, beat: 0, duration: 0.25, midi: 60, voice: 1, velocity: 70 },
  { bar: 0, beat: 0.25, duration: 0.25, midi: 61, voice: 1, velocity: 70 },
  { bar: 0, beat: 1 / 3, duration: 0.25, midi: 62, voice: 1, velocity: 70 },
  { bar: 0, beat: 0.5, duration: 0.25, midi: 63, voice: 1, velocity: 70 },
  { bar: 0, beat: 0.75, duration: 0.25, midi: 64, voice: 1, velocity: 70 },
];
const gridContour: MicroVelocity = {
  kind: 'offsets',
  notes: [
    { bar: 0, beat: 0, voice: 1, offset: -4 },
    { bar: 0, beat: 0.25, voice: 1, offset: -3 },
    { bar: 0, beat: 0.3333334, voice: 1, offset: 5 },
    { bar: 0, beat: 0.5, voice: 1, offset: -2 },
    { bar: 0, beat: 0.75, voice: 1, offset: -1 },
  ],
};
const gridRows = velocityLaneRows(gridNotes, gridContour);
equal(laneRow(gridRows, 60).offset, -4);
equal(laneRow(gridRows, 61).offset, -3);
equal(laneRow(gridRows, 62).offset, 5);
equal(laneRow(gridRows, 63).offset, -2);
equal(laneRow(gridRows, 64).offset, -1);
equal(noteKey(0, 1 / 3, 1), noteKey(0, 0.3333334, 1));

// Pinned attacks keep the absolute writer's velocity and never apply an offset.
const pinnedNote = [
  {
    bar: 0,
    beat: 0,
    duration: 1,
    midi: 64,
    voice: 1,
    velocity: 70,
    pinned: true,
    pinnedLayer: 'snap',
    velocityOffset: -9,
  },
];
const pinnedRows = velocityLaneRows(pinnedNote, {
  kind: 'offsets',
  notes: [{ bar: 0, beat: 0, voice: 1, offset: -6, pinned: true, velocity: 84, layer: 'snap' }],
});
equal(pinnedRows[0]?.pinned, true);
equal(pinnedRows[0]?.offset, -6);
equal(pinnedRows[0]?.previewVelocity, 84);
equal(pinnedRows[0]?.pinnedLayer, 'snap');
equal(pinnedLabel(pinnedRows[0] ?? {}), 'snap · v84');
equal(pinnedLabel({ velocity: 60 }), 'pinned · v60');
equal(pinnedLabel({ layer: 'trim', velocity: 52 }), 'trim · v52');
equal(pinnedLabel({}), 'pinned');

const pinnedPreview = applyOffsetPreview(pinnedNote, {
  kind: 'offsets',
  notes: [{ bar: 0, beat: 0, voice: 1, pinned: true, velocity: 84, layer: 'snap' }],
});
equal(pinnedPreview[0]?.pinned, true);
equal(pinnedPreview[0]?.velocity, 84);
equal(pinnedPreview[0]?.previewVelocity, 84);

// Rule contours are not flattened unless a table is supplied. Unmatched rows
// carry needsRule instead of a guessed value.
const ruleContour: MicroVelocity = {
  kind: 'rule',
  ruleId: 'galop1',
  ruleVersion: 1,
  params: { step: 2, floor: 40, peakQuarter: 3 },
  notes: [],
};
const ruleNotes = [
  { bar: 0, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 },
  { bar: 0, beat: 1, duration: 1, midi: 65, voice: 1, velocity: 70 },
];
const ruleRows = velocityLaneRows(ruleNotes, ruleContour);
equal(ruleRows.every((row) => row.needsRule), true);
equal(ruleRows.every((row) => row.offset === 0 && row.authored === false), true);
equal(velocityLaneExtent(ruleRows).needsRule, true);

const flattened = velocityLaneRows(ruleNotes, ruleContour, {
  ruleOffsets: { [noteKey(0, 0, 1)]: 4 },
});
equal(laneRow(flattened, 64).offset, 4);
equal(laneRow(flattened, 64).needsRule, false);
equal(laneRow(flattened, 64).authored, true);
equal(laneRow(flattened, 65).needsRule, true);

// Figure/slot-relative contour bars can wrap over a tiled preview.
const wrapped = velocityLaneRows(
  [{ bar: 8, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 }],
  { kind: 'offsets', notes: [{ bar: 0, beat: 0, voice: 1, offset: -6 }] },
  { barSpan: 8 },
);
equal(wrapped[0]?.bar, 8);
equal(wrapped[0]?.offset, -6);

// The same figure can start later; barOffset shifts the contour coordinate.
const shifted = velocityLaneRows(
  [{ bar: 4, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 }],
  { kind: 'offsets', notes: [{ bar: 0, beat: 0, voice: 1, offset: -6 }] },
  { barOffset: 4 },
);
equal(shifted[0]?.offset, -6);

// A slot at preview bar 2 maps contour bar 0/1 to absolute bars 2/3, and a
// whole-tile repeat wraps back onto the slot's coordinates.
const lateSlotNotes = [
  { bar: 2, beat: 0, duration: 1, midi: 60, voice: 1, velocity: 70 },
  { bar: 3, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 },
  { bar: 6, beat: 0, duration: 1, midi: 67, voice: 1, velocity: 70 },
];
const slotOriginContour: MicroVelocity = {
  kind: 'offsets',
  notes: [
    { bar: 0, beat: 0, voice: 1, offset: -6 },
    { bar: 1, beat: 0, voice: 1, offset: 3 },
  ],
};
const lateSlotRows = velocityLaneRows(lateSlotNotes, slotOriginContour, {
  slot: { start: 2, bars: 2, tile: 4, exact: false },
});
equal(lateSlotRows[0]?.bar, 2);
equal(lateSlotRows[0]?.contourBar, 0);
equal(lateSlotRows[0]?.offset, -6);
equal(lateSlotRows[1]?.contourBar, 1);
equal(lateSlotRows[1]?.offset, 3);
equal(lateSlotRows[2]?.contourBar, 0);
equal(lateSlotRows[2]?.offset, -6);

// A preview bar before the slot origin can never wrap forward into the slot.
const beforeSlot = velocityLaneRows(
  [{ bar: 1, beat: 0, duration: 1, midi: 59, voice: 1, velocity: 70 }],
  slotOriginContour,
  { slot: { start: 2, bars: 2, tile: 4, exact: false } },
);
equal(beforeSlot[0]?.contourBar, -1);
equal(beforeSlot[0]?.offset, 0);
equal(beforeSlot[0]?.authored, false);

// A non-repeating (exact) slot never wraps: bars after its last bar stay
// outside the contour, even when they would alias under a slot-bars modulo.
const exactSlotRows = velocityLaneRows(
  [
    { bar: 2, beat: 0, duration: 1, midi: 60, voice: 1, velocity: 70 },
    { bar: 3, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 },
    { bar: 4, beat: 0, duration: 1, midi: 67, voice: 1, velocity: 70 },
    { bar: 5, beat: 0, duration: 1, midi: 69, voice: 1, velocity: 70 },
  ],
  slotOriginContour,
  { slot: { start: 2, bars: 2, tile: 4, exact: true } },
);
equal(exactSlotRows[0]?.contourBar, 0);
equal(exactSlotRows[0]?.offset, -6);
equal(exactSlotRows[1]?.contourBar, 1);
equal(exactSlotRows[1]?.offset, 3);
equal(exactSlotRows[2]?.contourBar, -1);
equal(exactSlotRows[2]?.offset, 0);
equal(exactSlotRows[2]?.authored, false);
equal(exactSlotRows[3]?.contourBar, -1);
equal(exactSlotRows[3]?.offset, 0);

// A repeating tile starting at 0 wraps once per tile, inside the slot span.
const repeatedFromZeroRows = velocityLaneRows(
  [
    { bar: 0, beat: 0, duration: 1, midi: 60, voice: 1, velocity: 70 },
    { bar: 1, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 },
    { bar: 2, beat: 0, duration: 1, midi: 67, voice: 1, velocity: 70 },
    { bar: 3, beat: 0, duration: 1, midi: 69, voice: 1, velocity: 70 },
  ],
  slotOriginContour,
  { slot: { start: 0, bars: 2, tile: 2, exact: false } },
);
equal(repeatedFromZeroRows[0]?.contourBar, 0);
equal(repeatedFromZeroRows[0]?.offset, -6);
equal(repeatedFromZeroRows[1]?.contourBar, 1);
equal(repeatedFromZeroRows[1]?.offset, 3);
equal(repeatedFromZeroRows[2]?.contourBar, 0);
equal(repeatedFromZeroRows[2]?.offset, -6);
equal(repeatedFromZeroRows[3]?.contourBar, 1);
equal(repeatedFromZeroRows[3]?.offset, 3);

// In a repeating tile, bars between the slot end and the next occurrence stay
// outside it rather than borrowing a contour bar.
const gapRows = velocityLaneRows(
  [{ bar: 3, beat: 0, duration: 1, midi: 60, voice: 1, velocity: 70 }],
  slotOriginContour,
  { slot: { start: 0, bars: 2, tile: 4, exact: false } },
);
equal(gapRows[0]?.contourBar, -1);
equal(gapRows[0]?.offset, 0);

// The shared grid keeps every lane on the same absolute bar/beat columns.
const gridColumns = velocityLaneColumns(
  velocityLaneRows(
    [
      { bar: 0, beat: 1, duration: 1, midi: 67, voice: 1, velocity: 70 },
      { bar: 0, beat: 0, duration: 1, midi: 60, voice: 2, velocity: 70 },
      { bar: 1, beat: 0, duration: 1, midi: 62, voice: 1, velocity: 70 },
    ],
    null,
  ),
);
deepEqual(
  gridColumns.map((column) => `${column.bar}:${column.beat}`),
  ['0:0', '0:1', '1:0'],
);

// Display-only preview copies notes; the source objects are untouched.
const sourceNotes = [
  { bar: 0, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 },
  { bar: 0, beat: 0, duration: 0.5, midi: 48, voice: 3, velocity: 58 },
];
const before = JSON.stringify(sourceNotes);
const previewNotes = applyOffsetPreview(sourceNotes, offsetsContour);
equal(JSON.stringify(sourceNotes), before);
if (previewNotes[0] === (sourceNotes[0] as unknown)) {
  throw new Error('applyOffsetPreview must not return the source note object');
}
equal(previewNotes[0]?.previewVelocity, 64);
equal(previewNotes[0]?.authoredOffset, -6);
equal(previewNotes[1]?.lane, 'thumb');
equal(previewNotes[1]?.previewVelocity, 54);

const diff = velocityLaneDiff(
  [
    { bar: 0, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 },
    { bar: 0, beat: 0.5, duration: 0.5, midi: 65, voice: 1, velocity: 70 },
  ],
  {
    kind: 'offsets',
    notes: [
      { bar: 0, beat: 0, voice: 1, offset: -5 },
      { bar: 0, beat: 0.5, voice: 1, pinned: true, velocity: 90, layer: 'stab' },
    ],
  },
);
equal(diff.total, 2);
equal(diff.offsetRows, 1);
equal(diff.pinnedRows, 1);
equal(diff.needsRule, 0);
equal(diff.maxAbsOffset, 5);
equal(diff.velocityDelta, -5);

// Extent covers both offset directions, pinned absolute velocity and bars.
const extentRows = velocityLaneRows(
  [
    { bar: 0, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 },
    { bar: 0, beat: 0.5, duration: 0.5, midi: 60, voice: 3, velocity: 60, pinned: true },
    { bar: 1, beat: 0, duration: 1, midi: 65, voice: 1, velocity: 70 },
  ],
  {
    kind: 'offsets',
    notes: [
      { bar: 0, beat: 0, voice: 1, offset: -6 },
      { bar: 1, beat: 0, voice: 1, offset: 3 },
      { bar: 0, beat: 0.5, voice: 3, pinned: true, velocity: 90, layer: 'stab' },
    ],
  },
);
const extent = velocityLaneExtent(extentRows);
equal(extent.minOffset, -6);
equal(extent.maxOffset, 3);
equal(extent.minVelocity, 90);
equal(extent.maxVelocity, 90);
equal(extent.maxAbsOffset, 6);
equal(extent.barStart, 0);
equal(extent.barEnd, 1);
equal(extent.barCount, 2);
equal(extent.hasPinned, true);
equal(extent.needsRule, false);

equal(
  velocityLaneLabel({ bar: 1, beat: 1, voice: 1, finger: 'a' }),
  'bar 2 · beat 1 · voice 1 · finger a',
);
equal(velocityLaneLabel({ bar: 0, beat: 0, voice: 3, thumb: true }), 'bar 1 · beat 0 · voice 3 · thumb');

const normalizedContour = normalizeVelocityContour({
  kind: 'offsets',
  notes: [{ bar: 0, beat: 0, voice: 1, offset: -3 }],
  thumb: [],
});
if (!normalizedContour || normalizedContour.kind !== 'offsets') {
  throw new Error('expected an offsets contour');
}
equal(normalizedContour.notes.length, 1);
equal(normalizedContour.thumb?.length, 0);
equal(normalizeVelocityContour({ kind: 'mystery' }), null);
equal(normalizeVelocityContour(null), null);

// The API serves `microVelocity` as `[{ slot, start, bars, contour }]`. A slot
// wrapper must never be read as an offset entry.
const slotContour = normalizeVelocityContour([
  {
    slot: 0,
    contour: {
      kind: 'offsets',
      notes: [{ bar: 0, beat: 0.25, voice: 1, offset: -3 }],
    },
  },
  {
    slot: 1,
    contour: {
      kind: 'offsets',
      notes: [{ bar: 0, beat: 0.5, voice: 1, offset: -7 }],
    },
  },
]);
if (!slotContour || slotContour.kind !== 'offsets') {
  throw new Error('expected the first slot contour to normalise');
}
equal(slotContour.notes.length, 1);
equal(slotContour.notes[0]?.offset, -3);
equal(slotContour.notes[0]?.beat, 0.25);

// Compatibility path: a bare offsets array still normalises.
const plainOffsets = normalizeVelocityContour([
  { bar: 0, beat: 0.5, voice: 1, offset: -2 },
]);
if (!plainOffsets || plainOffsets.kind !== 'offsets') {
  throw new Error('expected a plain offsets array to normalise');
}
equal(plainOffsets.notes.length, 1);
equal(plainOffsets.notes[0]?.offset, -2);

// Multi-slot selection follows wire order and keeps a null contour visible so
// the selector can show an unauthored slot instead of flattening slots.
const selectedSlots = velocitySlotContours([
  {
    slot: 0,
    start: 0,
    bars: 2,
    contour: { kind: 'offsets', notes: [{ bar: 0, beat: 0, voice: 1, offset: -3 }] },
  },
  { slot: 2, start: 3, bars: 2, contour: null },
  {
    slot: 1,
    start: 1,
    bars: 2,
    contour: { kind: 'offsets', notes: [{ bar: 0, beat: 0.5, voice: 1, offset: -7 }] },
  },
]);
deepEqual(
  selectedSlots.map((item) => item.slot),
  [0, 2, 1],
);
equal(selectedSlots[1]?.contour, null);
equal(selectedSlots[1]?.start, 3);
equal(selectedSlots[1]?.bars, 2);
if (
  !selectedSlots[2]?.contour ||
  selectedSlots[2].contour.kind !== 'offsets'
) {
  throw new Error('expected slot 1 offsets');
}
equal(selectedSlots[2].contour.notes[0]?.offset, -7);
equal(selectedSlots[2].start, 1);
equal(velocitySlotLabel(2), 'Slot 2');
equal(velocitySlotLabel(1, selectedSlots[2]), 'Slot 1 · bars 2–3');
equal(velocitySlotLabel(3, { start: 4, bars: 1 }), 'Slot 3 · bar 5');
equal(velocitySlotLabel(0, { start: 2, bars: 0 }), 'Slot 0 · from bar 3');

// The wire carries tile/exact/cycle so the lane can distinguish an exact
// slot from a repeating tile. Legacy entries default to no tile and no repeat.
const windowedSlots = velocitySlotContours([
  {
    slot: 0,
    start: 0,
    bars: 2,
    tile: 4,
    exact: false,
    cycle: false,
    contour: { kind: 'offsets', notes: [{ bar: 0, beat: 0, voice: 1, offset: -3 }] },
  },
  {
    slot: 1,
    start: 3,
    bars: 2,
    tile: null,
    exact: true,
    cycle: false,
    contour: { kind: 'offsets', notes: [{ bar: 0, beat: 0, voice: 1, offset: -7 }] },
  },
]);
equal(windowedSlots[0]?.tile, 4);
equal(windowedSlots[0]?.exact, false);
equal(windowedSlots[0]?.cycle, false);
equal(windowedSlots[1]?.tile, null);
equal(windowedSlots[1]?.exact, true);

// Multi-slot mapping uses each selected slot's own window. The same preview
// bars map to different contour bars, and bars outside the active slot miss.
const multiSlotNotes = [0, 1, 2, 3, 4].map((bar) => ({
  bar,
  beat: 0,
  duration: 1,
  midi: 60 + bar,
  voice: 1,
  velocity: 70,
}));
const slotZeroRows = velocityLaneRows(
  multiSlotNotes,
  windowedSlots[0]?.contour ?? null,
  { slot: windowedSlots[0] },
);
const slotOneRows = velocityLaneRows(
  multiSlotNotes,
  windowedSlots[1]?.contour ?? null,
  { slot: windowedSlots[1] },
);
equal(slotZeroRows[0]?.contourBar, 0);
equal(slotZeroRows[0]?.offset, -3);
equal(slotZeroRows[1]?.contourBar, 1);
equal(slotZeroRows[1]?.offset, 0);
// Bars 2–3 are the gap after slot 0 inside the tile; they stay outside.
equal(slotZeroRows[2]?.contourBar, -1);
equal(slotZeroRows[3]?.contourBar, -1);
// Slot 0 repeats every 4 bars, so bar 4 is its next occurrence.
equal(slotZeroRows[4]?.contourBar, 0);
equal(slotZeroRows[4]?.offset, -3);

equal(slotOneRows[2]?.contourBar, -1);
equal(slotOneRows[2]?.offset, 0);
equal(slotOneRows[3]?.contourBar, 0);
equal(slotOneRows[3]?.offset, -7);
equal(slotOneRows[4]?.contourBar, 1);
equal(slotOneRows[4]?.offset, 0);

// Older preview payloads omit `start`/`bars`; they stay at origin 0.
const legacySlots = velocitySlotContours([
  {
    slot: 0,
    contour: { kind: 'offsets', notes: [{ bar: 0, beat: 0, voice: 1, offset: -3 }] },
  },
]);
equal(legacySlots[0]?.start, 0);
equal(legacySlots[0]?.bars, 0);
equal(legacySlots[0]?.tile, null);
equal(legacySlots[0]?.exact, false);
equal(legacySlots[0]?.cycle, false);

// The single-slot path is unchanged: a bare contour maps to slot 0.
const singleSlot = velocitySlotContours(normalizedContour);
equal(singleSlot.length, 1);
equal(singleSlot[0]?.slot, 0);
deepEqual(singleSlot[0]?.contour, normalizedContour);

// The legacy single-slot normaliser still takes the first *authored* contour.
const lateContour = normalizeVelocityContour([
  { slot: 0, contour: null },
  {
    slot: 1,
    contour: { kind: 'offsets', notes: [{ bar: 0, beat: 0, voice: 1, offset: -5 }] },
  },
]);
if (!lateContour || lateContour.kind !== 'offsets') {
  throw new Error('expected the first authored slot to win');
}
equal(lateContour.notes[0]?.offset, -5);

// Lane edits merge into the contour: replace an authored entry, append a new
// one, and never mutate the original contour.
const editContour: MicroVelocity = {
  kind: 'offsets',
  notes: [{ bar: 0, beat: 0, voice: 1, offset: -6 }],
};
const editRows = velocityLaneRows(
  [
    { bar: 0, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 },
    { bar: 0, beat: 1, duration: 1, midi: 65, voice: 1, velocity: 70 },
  ],
  editContour,
);
const firstEditRow = editRows[0];
const secondEditRow = editRows[1];
if (!firstEditRow || !secondEditRow) throw new Error('expected two lane rows');
const mergedContour = mergeVelocityEdits(editContour, editRows, {
  [firstEditRow.key]: -2,
  [secondEditRow.key]: 5,
});
if (mergedContour.kind !== 'offsets') throw new Error('expected offsets');
equal(mergedContour.notes.length, 2);
equal(mergedContour.notes[0]?.offset, -2);
equal(mergedContour.notes[1]?.bar, 0);
equal(mergedContour.notes[1]?.beat, 1);
equal(mergedContour.notes[1]?.offset, 5);
if (editContour.kind !== 'offsets') throw new Error('expected offsets');
equal(editContour.notes[0]?.offset, -6);

// Save stays slot-relative: a row at preview bar 2 still writes contour bar 0.
const shiftedEditRows = velocityLaneRows(
  [
    { bar: 2, beat: 0, duration: 1, midi: 60, voice: 1, velocity: 70 },
    { bar: 3, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 },
  ],
  { kind: 'offsets', notes: [] },
  { slot: { start: 2, bars: 2, tile: 4, exact: false } },
);
const shiftedFirst = shiftedEditRows[0];
const shiftedSecond = shiftedEditRows[1];
if (!shiftedFirst || !shiftedSecond) throw new Error('expected shifted rows');
const shiftedMerge = mergeVelocityEdits({ kind: 'offsets', notes: [] }, shiftedEditRows, {
  [shiftedFirst.key]: -5,
  [shiftedSecond.key]: 4,
});
if (shiftedMerge.kind !== 'offsets') throw new Error('expected offsets');
equal(shiftedMerge.notes[0]?.bar, 0);
equal(shiftedMerge.notes[0]?.offset, -5);
equal(shiftedMerge.notes[1]?.bar, 1);
equal(shiftedMerge.notes[1]?.offset, 4);

// Edits on a bar before the slot origin are dropped, never saved as negative.
const beforeSlotEdit = mergeVelocityEdits(
  { kind: 'offsets', notes: [] },
  beforeSlot,
  { [beforeSlot[0]?.key ?? '']: -5 },
);
if (beforeSlotEdit.kind !== 'offsets') throw new Error('expected offsets');
equal(beforeSlotEdit.notes.length, 0);

// Edits on a bar after a non-repeating slot end are dropped too: the row has
// no slot-relative coordinate, so Save cannot smuggle it into the contour.
const afterEndEdit = mergeVelocityEdits(
  { kind: 'offsets', notes: [] },
  exactSlotRows,
  {
    [exactSlotRows[2]?.key ?? '']: -5,
    [exactSlotRows[3]?.key ?? '']: 7,
  },
);
if (afterEndEdit.kind !== 'offsets') throw new Error('expected offsets');
equal(afterEndEdit.notes.length, 0);

// Repeating tile edits still save slot-relative bars.
const repeatedEdit = mergeVelocityEdits(
  { kind: 'offsets', notes: [] },
  repeatedFromZeroRows,
  { [repeatedFromZeroRows[2]?.key ?? '']: -5 },
);
if (repeatedEdit.kind !== 'offsets') throw new Error('expected offsets');
equal(repeatedEdit.notes[0]?.bar, 0);
equal(repeatedEdit.notes[0]?.offset, -5);

// Pinned attacks are locked: an edit can never replace their absolute layer.
const pinnedEdge: MicroVelocity = {
  kind: 'offsets',
  notes: [
    { bar: 0, beat: 0, voice: 1, pinned: true, velocity: 84, layer: 'snap' },
    { bar: 0, beat: 1, voice: 1, offset: -4 },
  ],
};
const pinnedEdgeRows = velocityLaneRows(
  [
    { bar: 0, beat: 0, duration: 1, midi: 64, voice: 1, velocity: 70 },
    { bar: 0, beat: 1, duration: 1, midi: 65, voice: 1, velocity: 70 },
  ],
  pinnedEdge,
);
const lockedPinnedRow = pinnedEdgeRows.find((row) => row.pinned);
const lockedOffsetRow = pinnedEdgeRows.find((row) => !row.pinned);
if (!lockedPinnedRow || !lockedOffsetRow) throw new Error('expected pinned + offset rows');
const lockedContour = mergeVelocityEdits(pinnedEdge, pinnedEdgeRows, {
  [lockedPinnedRow.key]: 99,
  [lockedOffsetRow.key]: -1,
});
if (lockedContour.kind !== 'offsets') throw new Error('expected offsets');
const lockedPinned = lockedContour.notes.find((entry) => entry.pinned === true);
equal(lockedPinned?.velocity, 84);
equal(lockedPinned?.offset, undefined);
equal(lockedPinned?.layer, 'snap');
equal(lockedContour.notes.find((entry) => entry.beat === 1)?.offset, -1);

// Empty means no notes and no thumb; a rule carrier is never empty.
equal(velocityContourIsEmpty(null), true);
equal(velocityContourIsEmpty({ kind: 'offsets', notes: [], thumb: [] }), true);
equal(
  velocityContourIsEmpty({
    kind: 'offsets',
    notes: [{ bar: 0, beat: 0, voice: 1, offset: -1 }],
  }),
  false,
);
equal(velocityContourIsEmpty(ruleContour), false);

// Save writes exactly one slot and preserves every other slot field.
const saveBase = {
  ...DEFAULT_SAMPLE.spec,
  id: 'velocity_save',
  slots: [
    { start: 0, bars: 2, figure: 8, cell: null, anchor: 'start' },
    {
      start: 2,
      bars: 2,
      figure: 13,
      cell: null,
      anchor: 'start',
      microVelocity: {
        kind: 'rule',
        ruleId: 'old_rule',
        ruleVersion: 1,
        params: { step: 2 },
        notes: [],
      },
    },
  ],
};
const saveText = JSON.stringify(saveBase, null, 2);
const savedContour: MicroVelocity = {
  kind: 'offsets',
  notes: [
    { bar: 0, beat: 0, voice: 1, finger: 'a', offset: -6 },
    { bar: 0, beat: 2, voice: 1, pinned: true, velocity: 90, layer: 'snap' },
  ],
  thumb: [{ bar: 0, beat: 0, voice: 3, finger: 'p', offset: -4 }],
};
const savedResult = saveVelocityContourToSpec({
  specText: saveText,
  slot: 1,
  contour: savedContour,
});
if (!savedResult.ok) {
  throw new Error(`save failed: ${savedResult.errors[0]?.message}`);
}
equal(savedResult.omitted, false);
const savedSpec = JSON.parse(savedResult.text) as Record<string, unknown>;
const savedSlots = savedSpec.slots as Array<Record<string, unknown>>;
deepEqual(savedSlots[0], saveBase.slots[0]);
equal(savedSlots[1]?.start, 2);
equal(savedSlots[1]?.figure, 13);
deepEqual(savedSlots[1]?.microVelocity, savedContour);
equal(savedSpec.id, 'velocity_save');

// Saving the same contour twice is byte-identical (spec round-trip).
const savedAgain = saveVelocityContourToSpec({
  specText: savedResult.text,
  slot: 1,
  contour: savedContour,
});
if (!savedAgain.ok) {
  throw new Error(`second save failed: ${savedAgain.errors[0]?.message}`);
}
equal(savedAgain.text, savedResult.text);

// An empty contour omits the field and still preserves the slot.
const omittedResult = saveVelocityContourToSpec({
  specText: savedResult.text,
  slot: 1,
  contour: null,
});
if (!omittedResult.ok) throw new Error('null contour should save by omission');
equal(omittedResult.omitted, true);
const omittedSpec = JSON.parse(omittedResult.text) as Record<string, unknown>;
const omittedSlots = omittedSpec.slots as Array<Record<string, unknown>>;
equal('microVelocity' in (omittedSlots[1] ?? {}), false);
equal(omittedSlots[1]?.start, 2);

const emptyContour = saveVelocityContourToSpec({
  specText: savedResult.text,
  slot: 1,
  contour: { kind: 'offsets', notes: [], thumb: [] },
});
if (!emptyContour.ok) throw new Error('empty contour should save by omission');
equal(emptyContour.omitted, true);
const emptySpec = JSON.parse(emptyContour.text) as Record<string, unknown>;
equal(
  'microVelocity' in ((emptySpec.slots as Array<Record<string, unknown>>)[1] ?? {}),
  false,
);

// Parse/slot failures are inert and keep the normal pre-flight path shape.
const invalidSpec = saveVelocityContourToSpec({
  specText: '{"slots":',
  slot: 0,
  contour: null,
});
if (invalidSpec.ok) throw new Error('invalid JSON must not save');
equal(invalidSpec.errors[0]?.path, '$');

const missingSlot = saveVelocityContourToSpec({
  specText: saveText,
  slot: 9,
  contour: null,
});
if (missingSlot.ok) throw new Error('missing slot must not save');
equal(missingSlot.errors[0]?.path, 'slots[9]');

// A rule that still needs flattening is blocked; a fully flattened rule can
// round-trip unchanged. Edited rule rows are blocked because the carrier stays
// a rule.
const blockedRule = saveVelocityContourToSpec({
  specText: saveText,
  slot: 1,
  contour: ruleContour,
  needsRule: true,
});
if (blockedRule.ok) throw new Error('unflattened rule must not save');
equal(blockedRule.errors[0]?.path, 'slots[1].microVelocity');
equal(blockedRule.errors[0]?.message.includes('flatten'), true);

const blockedRuleEdits = saveVelocityContourToSpec({
  specText: saveText,
  slot: 1,
  contour: ruleContour,
  needsRule: false,
  hasEdits: true,
});
if (blockedRuleEdits.ok) throw new Error('edited rule must not save');
equal(blockedRuleEdits.errors[0]?.path, 'slots[1].microVelocity');

const flattenedRuleSave = saveVelocityContourToSpec({
  specText: saveText,
  slot: 1,
  contour: ruleContour,
  needsRule: false,
});
if (!flattenedRuleSave.ok) {
  throw new Error(`flattened rule should save: ${flattenedRuleSave.errors[0]?.message}`);
}
const flattenedRuleSpec = JSON.parse(flattenedRuleSave.text) as Record<string, unknown>;
const flattenedRuleSlot = (
  flattenedRuleSpec.slots as Array<Record<string, unknown>>
)[1];
const flattenedRuleContour = flattenedRuleSlot?.microVelocity as Record<string, unknown>;
equal(flattenedRuleContour.kind, 'rule');
equal(flattenedRuleContour.ruleId, 'galop1');
equal(flattenedRuleContour.ruleVersion, 1);

/* ------------------------------------------------------------------------- *
 * MusicXML: meter, layout, role lanes, selection, normalizers.
 * ------------------------------------------------------------------------- */

function musicXmlImport(
  summary: Record<string, unknown>,
  notes: unknown[],
): MusicXmlImport {
  return normalizeMusicXmlImport({
    ok: true,
    importId: 'mxi_test',
    filename: 'score.musicxml',
    summary,
    notes,
  });
}

function roleLane(lanes: readonly MusicXmlRoleLane[], role: MusicXmlRoleLane['role']) {
  const lane = lanes.find((item) => item.role === role);
  if (!lane) throw new Error(`missing ${role} lane`);
  return lane;
}

function assertLanesContiguous(
  lanes: readonly MusicXmlRoleLane[],
  bars: ReturnType<typeof barLayouts>,
) {
  for (const lane of lanes) {
    for (const bar of bars) {
      const cells = lane.cells.filter((cell) => cell.bar === bar.bar);
      if (cells.length === 0) {
        throw new Error(`${lane.role} bar ${bar.bar}: no cells`);
      }
      let cursor = 0;
      for (const cell of cells) {
        if (cell.startTick !== cursor) {
          throw new Error(
            `${lane.role} bar ${bar.bar}: expected tick ${cursor}, got ${cell.startTick}`,
          );
        }
        if (cell.ticks <= 0) {
          throw new Error(`${lane.role} bar ${bar.bar}: non-positive cell`);
        }
        cursor += cell.ticks;
      }
      if (cursor !== bar.ticks) {
        throw new Error(
          `${lane.role} bar ${bar.bar}: cells end at ${cursor}, bar is ${bar.ticks}`,
        );
      }
    }
  }
}

equal(meterQuarterBeats('3/4'), 3);
equal(meterQuarterBeats('6/8'), 3);
equal(meterQuarterBeats('1/4'), 1);
equal(meterTicks('1/4'), 24);
equal(meterTicks('2/4'), 48);
equal(meterTicks('3/4'), 72);
equal(meterTicks('4/4'), 96);
equal(meterTicks('6/8'), 72);
equal(isSupportedMeter('6/8'), true);
equal(isSupportedMeter('2/4'), true);
equal(isSupportedMeter('5/8'), false);
deepEqual(meterGroups('6/8'), [3, 3]);
deepEqual(meterGroups('4/4'), [4, 4]);
deepEqual(meterGroups('3/4'), [3]);
deepEqual(meterGroups('2/4'), [2]);
deepEqual(meterGroups('1/4'), [1]);
deepEqual(meterGroupTicks('6/8'), [36, 36]);
deepEqual(meterGroupTicks('4/4'), [48, 48]);
deepEqual(meterGroupTicks('3/4'), [72]);

const roleImport = musicXmlImport(
  {
    title: 'Roles',
    meter: '4/4',
    measureCount: 1,
    measureMeters: ['4/4'],
    keyFifths: 0,
    tempo: 96,
  },
  [
    { bar: 0, beat: 0, duration: 1, voice: 1, midi: 72 },
    { bar: 0, beat: 0, duration: 1, voice: 1, midi: 76, chord: true },
    { bar: 0, beat: 0, duration: 1, voice: 1, midi: null, rest: true },
    { bar: 0, beat: 0, duration: 1, voice: 2, midi: 60 },
    { bar: 0, beat: 0, duration: 1, voice: 2, midi: 64 },
    { bar: 0, beat: 0, duration: 1, voice: 3, midi: 48 },
    { bar: 0, beat: 2, duration: 1, voice: 1, midi: 67 },
  ],
);
const roleBars = barLayouts(roleImport.summary);
const roleLanes = buildRoleLanes(roleImport.notes, roleBars);
const leadLane = roleLane(roleLanes, 'lead');
const midLane = roleLane(roleLanes, 'mid');
const bassLane = roleLane(roleLanes, 'bass');
deepEqual(
  leadLane.cells.map((cell) => ({
    start: cell.startTick,
    ticks: cell.ticks,
    rest: cell.rest,
    count: cell.count,
  })),
  [
    { start: 0, ticks: 24, rest: false, count: 2 },
    { start: 24, ticks: 24, rest: true, count: 0 },
    { start: 48, ticks: 24, rest: false, count: 1 },
    { start: 72, ticks: 24, rest: true, count: 0 },
  ],
);
deepEqual(
  midLane.cells.map((cell) => ({
    start: cell.startTick,
    ticks: cell.ticks,
    rest: cell.rest,
    count: cell.count,
  })),
  [
    { start: 0, ticks: 24, rest: false, count: 2 },
    { start: 24, ticks: 72, rest: true, count: 0 },
  ],
);
deepEqual(
  bassLane.cells.map((cell) => ({
    start: cell.startTick,
    ticks: cell.ticks,
    rest: cell.rest,
    count: cell.count,
  })),
  [
    { start: 0, ticks: 24, rest: false, count: 1 },
    { start: 24, ticks: 72, rest: true, count: 0 },
  ],
);
equal(bassLane.cells[0]?.voice, 3);
assertLanesContiguous(roleLanes, roleBars);

const restImport = musicXmlImport(
  { meter: '4/4', measureCount: 2, measureMeters: ['4/4', '4/4'] },
  [{ bar: 0, beat: 1, duration: 1, voice: 1, midi: 72 }],
);
const restBars = barLayouts(restImport.summary);
const restLanes = buildRoleLanes(restImport.notes, restBars);
assertLanesContiguous(restLanes, restBars);
const restLead = roleLane(restLanes, 'lead');
deepEqual(
  restLead.cells.filter((cell) => cell.bar === 1).map((cell) => ({
    start: cell.startTick,
    ticks: cell.ticks,
    rest: cell.rest,
  })),
  [
    { start: 0, ticks: 24, rest: true },
    { start: 24, ticks: 24, rest: false },
    { start: 48, ticks: 48, rest: true },
  ],
);
deepEqual(
  roleLane(restLanes, 'mid')
    .cells.filter((cell) => cell.bar === 2)
    .map((cell) => ({ start: cell.startTick, ticks: cell.ticks, rest: cell.rest })),
  [{ start: 0, ticks: 96, rest: true }],
);
deepEqual(
  roleLane(restLanes, 'bass')
    .cells.filter((cell) => cell.bar === 1)
    .map((cell) => ({ start: cell.startTick, ticks: cell.ticks, rest: cell.rest })),
  [{ start: 0, ticks: 96, rest: true }],
);

const crossingImport = musicXmlImport(
  { meter: '4/4', measureCount: 1, measureMeters: ['4/4'] },
  [{ bar: 0, beat: 3, duration: 4, voice: 1, midi: 72 }],
);
const crossingLead = roleLane(
  buildRoleLanes(crossingImport.notes, barLayouts(crossingImport.summary)),
  'lead',
);
const crossingCell = crossingLead.cells.find((cell) => !cell.rest);
if (!crossingCell) throw new Error('crossing note cell missing');
equal(crossingCell.startTick, 72);
equal(crossingCell.ticks, 24);
equal(crossingCell.tie, null);

const sixEightBars = barLayouts({
  meter: '6/8',
  measureCount: 1,
  measureMeters: null,
  meterChanges: [],
});
equal(sixEightBars[0]?.ticks, 72);
const sixEightGrid = musicXmlGrid(sixEightBars);
deepEqual(sixEightGrid.bars[0]?.beatTicks, [0, 36]);
equal(sixEightGrid.bars[0]?.meterStart, true);
equal(sixEightGrid.totalTicks, 72);

// Scottish pickup: bar 1 is 1/4, the body is 2/4; the default skips the
// one-bar opening run, caps at four bars, and selects whole bars (beats).
const scottishImport = musicXmlImport(
  {
    meter: '1/4',
    measureCount: 6,
    measureMeters: ['1/4', '2/4', '2/4', '2/4', '2/4', '2/4'],
  },
  [],
);
const scottishBars = barLayouts(scottishImport.summary);
deepEqual(defaultPassageRange(scottishBars), {
  barStart: 2,
  beatStart: 0,
  barEnd: 5,
  beatEnd: 2,
});
equal(meterChangeLabel(scottishBars), '1/4 → 2/4 at bar 2');
equal(
  passageRangeLabel(scottishBars, {
    barStart: 2,
    beatStart: 0,
    barEnd: 4,
    beatEnd: 1,
  }),
  'bar 2 · beat 1.0 → bar 4 · beat 1.0',
);

const shortRunBars = barLayouts({
  meter: '3/4',
  measureCount: 4,
  measureMeters: ['3/4', '3/4', '4/4', '4/4'],
  meterChanges: [
    { bar: 3, meter: '4/4' },
  ],
});
// A two-bar run must not drag the next meter into the default window.
deepEqual(defaultPassageRange(shortRunBars), {
  barStart: 1,
  beatStart: 0,
  barEnd: 2,
  beatEnd: 3,
});
equal(
  validatePassageRange(shortRunBars, defaultPassageRange(shortRunBars)).ok,
  true,
);

const mixedBars = barLayouts({
  meter: '1/4',
  measureCount: 2,
  measureMeters: ['1/4', '2/4'],
  meterChanges: [],
});
const mixedRange = validatePassageRange(mixedBars, {
  barStart: 1,
  beatStart: 0,
  barEnd: 2,
  beatEnd: 2,
});
equal(mixedRange.ok, false);
equal(mixedRange.mixedMeter, true);
if (mixedRange.errors.length === 0) throw new Error('mixed range needs an error');
equal(
  passageRangeLabel(mixedBars, {
    barStart: 1,
    beatStart: 0,
    barEnd: 2,
    beatEnd: 2,
  }),
  'bar 1 · beat 1.0 → bar 2 · beat 2.0',
);
equal(
  validatePassageRange(mixedBars, {
    barStart: 2,
    beatStart: 0,
    barEnd: 2,
    beatEnd: 2,
  }).ok,
  true,
);
equal(
  validatePassageRange(mixedBars, {
    barStart: 2,
    beatStart: 0,
    barEnd: 1,
    beatEnd: 1,
  }).ok,
  false,
);
equal(
  validatePassageRange(mixedBars, {
    barStart: 0,
    beatStart: 0,
    barEnd: 1,
    beatEnd: 1,
  }).ok,
  false,
);
equal(
  validatePassageRange(mixedBars, {
    barStart: 1,
    beatStart: 0,
    barEnd: 3,
    beatEnd: 1,
  }).ok,
  false,
);
deepEqual(defaultPassageRange(mixedBars), {
  barStart: 1,
  beatStart: 0,
  barEnd: 1,
  beatEnd: 1,
});

/* Beat-aware selection: snap, absolute ticks, round-trip, end-exclusive. */
equal(snapTick(-5), 0);
equal(snapTick(0), 0);
equal(snapTick(11.9), 0);
equal(snapTick(12), 24);
equal(snapTick(13), 24);
equal(snapTick(35.9), 24);
equal(snapTick(36), 48);

const fourFourBars = barLayouts({
  meter: '4/4',
  measureCount: 2,
  measureMeters: ['4/4', '4/4'],
});
const fourFourGrid = musicXmlGrid(fourFourBars);
deepEqual(
  rangeTicks(fourFourGrid, {
    barStart: 1,
    beatStart: 1,
    barEnd: 2,
    beatEnd: 2,
  }),
  { startTick: 24, endTick: 144 },
);
deepEqual(
  selectionFromTicks(fourFourGrid, 24, 144),
  { barStart: 1, beatStart: 1, barEnd: 2, beatEnd: 2 },
);
deepEqual(
  rangeTicks(
    fourFourGrid,
    selectionFromTicks(fourFourGrid, 24, 144),
  ),
  { startTick: 24, endTick: 144 },
);
// End-exclusive: a window ending on the barline belongs to the previous bar.
deepEqual(
  selectionFromTicks(fourFourGrid, 0, 96),
  { barStart: 1, beatStart: 0, barEnd: 1, beatEnd: 4 },
);
deepEqual(
  selectionFromTicks(fourFourGrid, 96, 120),
  { barStart: 2, beatStart: 0, barEnd: 2, beatEnd: 1 },
);
deepEqual(
  selectionFromTicks(fourFourGrid, 0, 0),
  { barStart: 1, beatStart: 0, barEnd: 1, beatEnd: 1 },
);

const oneFourGrid = musicXmlGrid(
  barLayouts({ meter: '1/4', measureCount: 3, measureMeters: null }),
);
deepEqual(
  rangeTicks(oneFourGrid, {
    barStart: 1,
    beatStart: 0,
    barEnd: 2,
    beatEnd: 1,
  }),
  { startTick: 0, endTick: 48 },
);
deepEqual(
  selectionFromTicks(oneFourGrid, 24, 48),
  { barStart: 2, beatStart: 0, barEnd: 2, beatEnd: 1 },
);
const twoFourGrid = musicXmlGrid(
  barLayouts({ meter: '2/4', measureCount: 2, measureMeters: ['2/4', '2/4'] }),
);
deepEqual(
  selectionFromTicks(twoFourGrid, 0, 48),
  { barStart: 1, beatStart: 0, barEnd: 1, beatEnd: 2 },
);
deepEqual(
  selectionFromTicks(twoFourGrid, 48, 96),
  { barStart: 2, beatStart: 0, barEnd: 2, beatEnd: 2 },
);

deepEqual(
  resizeSelectionTicks(fourFourGrid, { startTick: 0, endTick: 96 }, 'start', 24),
  { startTick: 24, endTick: 96 },
);
deepEqual(
  resizeSelectionTicks(fourFourGrid, { startTick: 0, endTick: 96 }, 'start', 200),
  { startTick: 72, endTick: 96 },
);
deepEqual(
  resizeSelectionTicks(fourFourGrid, { startTick: 24, endTick: 96 }, 'end', 120),
  { startTick: 24, endTick: 120 },
);
deepEqual(
  resizeSelectionTicks(fourFourGrid, { startTick: 24, endTick: 96 }, 'end', 9999),
  { startTick: 24, endTick: 192 },
);
deepEqual([...fullySelectedBars(fourFourGrid.bars, 0, 96)], [1]);
deepEqual([...fullySelectedBars(fourFourGrid.bars, 0, 120)], [1]);
deepEqual([...fullySelectedBars(fourFourGrid.bars, 0, 192)], [1, 2]);
deepEqual([...fullySelectedBars(fourFourGrid.bars, 24, 192)], [2]);
deepEqual([...fullySelectedBars(fourFourGrid.bars, 24, 144)], []);

const beatStartNegative = validatePassageRange(fourFourBars, {
  barStart: 1,
  beatStart: -1,
  barEnd: 1,
  beatEnd: 2,
});
equal(beatStartNegative.ok, false);
const beatPastBar = validatePassageRange(fourFourBars, {
  barStart: 1,
  beatStart: 0,
  barEnd: 1,
  beatEnd: 5,
});
equal(beatPastBar.ok, false);
const emptyBeatRange = validatePassageRange(fourFourBars, {
  barStart: 1,
  beatStart: 2,
  barEnd: 1,
  beatEnd: 2,
});
equal(emptyBeatRange.ok, false);
const reversedBeatRange = validatePassageRange(fourFourBars, {
  barStart: 1,
  beatStart: 3,
  barEnd: 1,
  beatEnd: 2,
});
equal(reversedBeatRange.ok, false);
equal(
  validatePassageRange(fourFourBars, {
    barStart: 1,
    beatStart: 0,
    barEnd: 1,
    beatEnd: 4,
  }).ok,
  true,
);

/* Playhead + zoom helpers. */
equal(playheadTickAt(1, 96, 0), 38.4);
equal(playheadTickAt(0.5, 96, 24), 43.2);
equal(playheadTickAt(1, 0, 0), 38.4);
equal(playheadTickAt(-1, 96, 24), 24);
const playheadRaw = playheadTickAt(10, 96, 24);
equal(Math.min(96, Math.max(24, playheadRaw)), 96);
equal(clampZoom(0.1), 0.5);
equal(clampZoom(5), 3);
equal(clampZoom(1.13), 1.25);
equal(clampZoom(Number.NaN), 1);
equal(zoomLabel(0.5), '50%');
equal(zoomLabel(1), '100%');
equal(zoomLabel(3), '300%');

/* Passage request body keeps legacy callers and sends finite beats. */
deepEqual(buildMusicXmlPassageBody({ barStart: 1, barEnd: 2 }), {
  barStart: 1,
  barEnd: 2,
});
deepEqual(
  buildMusicXmlPassageBody({
    barStart: 2,
    beatStart: 1,
    barEnd: 4,
    beatEnd: 2,
    voices: [2, 1, 2],
  }),
  {
    barStart: 2,
    barEnd: 4,
    beatStart: 1,
    beatEnd: 2,
    voices: [1, 2],
  },
);
deepEqual(
  buildMusicXmlPassageBody({
    barStart: 1,
    beatStart: Number.NaN,
    barEnd: 1,
    beatEnd: Number.POSITIVE_INFINITY,
  }),
  { barStart: 1, barEnd: 1 },
);

const missingMeters = musicXmlImport(
  {
    title: 'No meter list',
    meter: '3/4',
    measureCount: 2,
    keyFifths: -2,
    keyMode: 'minor',
    tempo: 88,
    noteCount: 1,
    voices: [1],
  },
  [
    {
      bar: 1,
      beat: 0,
      duration: 1,
      voice: 1,
      midi: 60,
      written_midi: 59,
      written_pitch: 'B3',
      sounding_pitch: 'C4',
    },
  ],
);
equal(missingMeters.summary.measureMeters, null);
deepEqual(
  barLayouts(missingMeters.summary).map((bar) => bar.meter),
  ['3/4', '3/4'],
);
equal(missingMeters.notes[0]?.writtenMidi, 59);
equal(missingMeters.notes[0]?.writtenPitch, 'B3');
equal(missingMeters.notes[0]?.soundingPitch, 'C4');
if (!keySignatureLabel(missingMeters.summary).includes('2b')) {
  throw new Error('flat key label should include 2b');
}

const noMeter = musicXmlImport({ measureCount: 1 }, []);
equal(noMeter.summary.meter, '');
const noMeterBars = barLayouts(noMeter.summary);
equal(noMeterBars[0]?.meter, '4/4');
equal(noMeterBars[0]?.ticks, 96);

const changedMeter = musicXmlImport(
  {
    meter: '4/4',
    measureCount: 3,
    meterChanges: [{ bar: 3, meter: '3/4' }],
  },
  [],
);
deepEqual(
  barLayouts(changedMeter.summary).map((bar) => bar.meter),
  ['4/4', '4/4', '3/4'],
);

const relativePassage = normalizeMusicXmlPassage(
  {
    ok: true,
    passageId: 'mxp_relative',
    audioUrl: '/v1/studio/sentence/audio/relative.wav',
    notes: [{ bar: 0, beat: 0, duration: 1, midi: 60, voice: 1 }],
    durationSec: 1.25,
  },
  'https://api.test',
);
equal(
  relativePassage.audioUrl,
  'https://api.test/v1/studio/sentence/audio/relative.wav',
);
equal(relativePassage.meter, '');
equal(relativePassage.beatsPerBar, 0);
equal(relativePassage.bpm, 96);
equal(relativePassage.notes.length, 1);
equal(relativePassage.durationSec, 1.25);

const sixEightPassage = normalizeMusicXmlPassage({
  ok: true,
  passageId: 'mxp_68',
  meter: '6/8',
  bpm: 120,
  audioUrl: 'https://cdn.test/audio/absolute.wav',
  notes: [],
});
equal(sixEightPassage.beatsPerBar, 3);
equal(sixEightPassage.bpm, 120);
equal(sixEightPassage.audioUrl, 'https://cdn.test/audio/absolute.wav');

equal(normalizeMusicXmlPassage({ bpm: 0 }).bpm, 96);
equal(normalizeMusicXmlPassage({ bpm: 'fast' }).bpm, 96);
equal(normalizeMusicXmlPassage({ bpm: 84.5 }).bpm, 84.5);

const failedPassage = normalizeMusicXmlPassage({
  ok: false,
  errors: [{ path: 'meter', message: 'meter 5/8 is not supported' }],
});
equal(failedPassage.ok, false);
equal(failedPassage.errors[0]?.path, 'meter');

/* ------------------------------------------------------------------------- *
 * Sprint C: sentence draft body, tolerant response, local pattern draft.
 * ------------------------------------------------------------------------- */

equal(slugifyPatternId('Mazurka-Choro'), 'mazurka_choro');
equal(slugifyPatternId('  Valsa  Choro! '), 'valsa_choro');
equal(slugifyPatternId('Café 3/4'), 'cafe_3_4');
equal(slugifyPatternId('---'), '');
equal(newPatternId('Mazurka-Choro'), 'villa_mazurka_choro');
equal(newPatternId('villa_valsa_choro'), 'villa_valsa_choro');
equal(newPatternId('  '), '');
equal(villaMeterSupported('2/4'), true);
equal(villaMeterSupported('3/4'), true);
equal(villaMeterSupported('4/4'), true);
equal(villaMeterSupported('6/8'), false);

deepEqual(
  [...GENERIC_PATTERN_IDS],
  ['castillo', 'sonatina', 'fandanguillo', 'danza', 'galop'],
);

const draftSamples: StudioSample[] = [
  ...SAMPLES,
  {
    key: 'villa_pattern:3/4',
    pattern: 'villa_pattern',
    meter: '3/4',
    title: 'Mazurka',
    id: 'suite_mazurka_arpeggio_aaba',
    spec: {},
    fixture: {},
  },
  {
    key: 'villa_pattern:4/4',
    pattern: 'villa_pattern',
    meter: '4/4',
    title: 'Schottish',
    id: 'suite_schottish_arpeggio_abab',
    spec: {},
    fixture: {},
  },
  {
    key: 'preludio:4/4',
    pattern: 'preludio',
    meter: '4/4',
    title: 'Barrios',
    id: 'barrios_cathedral',
    spec: {},
    fixture: {},
  },
];

const genericIds = genericPatternOptions(draftSamples).map((option) => option.id);
deepEqual(genericIds, ['castillo', 'sonatina', 'fandanguillo', 'danza', 'galop']);
if (genericIds.some((id) => id.startsWith('suite_'))) {
  throw new Error('suite_* must not appear in the existing pattern picker');
}
if (genericIds.includes('villa_pattern') || genericIds.includes('preludio')) {
  throw new Error('Villa/Barrios must not appear in the existing pattern picker');
}
deepEqual(
  existingTemplateOptions(draftSamples, 'castillo', '4/4').map((option) => option.id),
  ['castillo_44_short'],
);
deepEqual(
  villaTemplateOptions(draftSamples, '3/4').map((option) => option.id),
  ['suite_mazurka_arpeggio_aaba'],
);
const composers = composerOptions();
if (composers[0] !== 'Villa-Lobos') {
  throw new Error('Villa-Lobos should be the first composer option');
}
for (const expected of ['Torroba', 'Sor', 'Barrios', 'Brouwer']) {
  if (!composers.includes(expected)) {
    throw new Error(`missing composer option ${expected}`);
  }
}
if (new Set(composers).size !== composers.length) {
  throw new Error('composer options must be unique');
}
if (composers.includes('Villa')) {
  throw new Error('Villa must normalize to Villa-Lobos');
}

deepEqual(villaTemplateOptions(draftSamples, '6/8'), []);

deepEqual(
  buildSentenceDraftBody({
    barStart: 2,
    beatStart: 0,
    barEnd: 5,
    beatEnd: 2,
    mode: 'existing',
    pattern: 'castillo',
    templateId: 'castillo_34_walk',
    voices: [2, 1, 2],
  }),
  {
    barStart: 2,
    barEnd: 5,
    mode: 'existing',
    beatStart: 0,
    beatEnd: 2,
    voices: [1, 2],
    pattern: 'castillo',
    templateId: 'castillo_34_walk',
  },
);

deepEqual(
  buildSentenceDraftBody({
    barStart: 2,
    beatStart: 0,
    barEnd: 5,
    beatEnd: 2,
    mode: 'new',
    pattern: 'castillo',
    templateId: 'suite_mazurka_arpeggio_aaba',
    newPattern: {
      id: 'villa_mazurka_choro',
      label: 'Mazurka-Choro',
      composer: VILLA_COMPOSER,
      renderer: VILLA_RENDERER,
      meter: '3/4',
      templateId: 'suite_mazurka_arpeggio_aaba',
    },
  }),
  {
    barStart: 2,
    barEnd: 5,
    mode: 'new',
    beatStart: 0,
    beatEnd: 2,
    newPattern: {
      id: 'villa_mazurka_choro',
      label: 'Mazurka-Choro',
      composer: 'Villa-Lobos',
      renderer: 'villa',
      meter: '3/4',
      templateId: 'suite_mazurka_arpeggio_aaba',
    },
  },
);

const draftResponse = normalizeSentenceDraftResponse(
  {
    ok: true,
    mode: 'existing',
    spec: { id: 'musicxml_mxi_2_5', pattern: 'castillo', meter: '3/4' },
    fixture: { length: 4, n: 0, closes: false, rise: 0 },
    preview: {
      renderHash: 'sha256:abc',
      audioUrl: '/v1/studio/sentence/audio/abc.wav',
      durationSec: 1.5,
      notes: 24,
    },
    warnings: ['template tile 4 used; passage has 4 bars'],
    productionReady: false,
  },
  'https://api.test',
);
equal(draftResponse.ok, true);
equal(draftResponse.mode, 'existing');
equal(draftResponse.spec?.id, 'musicxml_mxi_2_5');
deepEqual(draftResponse.fixture, { length: 4, n: 0, closes: false, rise: 0 });
equal(
  draftResponse.preview?.audioUrl,
  'https://api.test/v1/studio/sentence/audio/abc.wav',
);
equal(draftResponse.preview?.renderHash, 'sha256:abc');
equal(draftResponse.preview?.durationSec, 1.5);
equal(draftResponse.preview?.notes, 24);
equal(draftResponse.warnings[0], 'template tile 4 used; passage has 4 bars');
equal(draftResponse.productionReady, false);

const snakeDraft = normalizeSentenceDraftResponse({
  ok: true,
  mode: 'new',
  spec: { id: 'musicxml_new', pattern: 'villa_mazurka_choro' },
  preview: {
    render_hash: 'sha256:def',
    audio_url: 'https://cdn.test/a.wav',
    duration_sec: 2,
    notes: [{}, {}, {}],
  },
  production_ready: true,
  warnings: 'single warning',
});
equal(snakeDraft.mode, 'new');
equal(snakeDraft.preview?.renderHash, 'sha256:def');
equal(snakeDraft.preview?.audioUrl, 'https://cdn.test/a.wav');
equal(snakeDraft.preview?.durationSec, 2);
equal(snakeDraft.preview?.notes, 3);
equal(snakeDraft.productionReady, true);
deepEqual(snakeDraft.warnings, ['single warning']);

const failedSentenceDraft = normalizeSentenceDraftResponse({
  ok: false,
  errors: [
    { path: 'pattern', message: 'suite_mazurka is a single-sentence suite gate' },
  ],
});
equal(failedSentenceDraft.ok, false);
equal(failedSentenceDraft.mode, 'existing');
equal(failedSentenceDraft.spec, null);
deepEqual(failedSentenceDraft.fixture, {});
equal(failedSentenceDraft.preview, null);
equal(failedSentenceDraft.productionReady, false);
equal(failedSentenceDraft.errors[0]?.path, 'pattern');
if (!failedSentenceDraft.errors[0]?.message.includes('single-sentence')) {
  throw new Error('sentence-draft errors should survive normalization');
}

const sentenceA: PatternDraftSentence = {
  spec: { id: 'musicxml_a', pattern: 'villa_mazurka_choro', meter: '3/4' },
  fixture: { length: 4, n: 0, closes: false, rise: 0 },
  rangeLabel: 'bar 2 · beat 1.0 → bar 5 · beat 3.0',
  audioUrl: 'https://api.test/a.wav',
  durationSec: 1.25,
  renderHash: 'sha256:a',
};
const sentenceB: PatternDraftSentence = {
  spec: { id: 'musicxml_b', pattern: 'villa_mazurka_choro', meter: '3/4' },
  fixture: { length: 4, n: 1, closes: false, rise: 0 },
  rangeLabel: 'bar 6 · beat 1.0 → bar 9 · beat 3.0',
};
const patternDraft: PatternDraft = createPatternDraft(
  {
    id: 'villa_mazurka_choro',
    label: 'Mazurka-Choro',
    composer: VILLA_COMPOSER,
    renderer: VILLA_RENDERER,
    meter: '3/4',
  },
  sentenceA,
);
equal(patternDraft.sentences.length, 1);
const appended = appendPatternSentence(patternDraft, sentenceB);
if (!appended.ok) throw new Error(appended.error);
equal(appended.draft.sentences.length, 2);
equal(appended.draft.sentences[1]?.spec.id, 'musicxml_b');

const duplicate = appendPatternSentence(appended.draft, sentenceA);
equal(duplicate.ok, false);
if (duplicate.ok) throw new Error('duplicate sentence should be rejected');
if (!duplicate.error.includes('already')) {
  throw new Error('duplicate sentence error should say it is already present');
}
equal(duplicate.draft.sentences.length, 2);

const removed = removePatternSentence(appended.draft, 0);
equal(removed.sentences.length, 1);
equal(removed.sentences[0]?.spec.id, 'musicxml_b');
equal(removePatternSentence(removed, 9).sentences.length, 1);
equal(patternDraftLabel(appended.draft), 'villa_mazurka_choro · 3/4 · 2 sentences');
equal(sentenceDraftKey(sentenceA), 'musicxml_a');

deepEqual(buildPatternDraftExport(appended.draft), {
  id: 'villa_mazurka_choro',
  label: 'Mazurka-Choro',
  composer: 'Villa-Lobos',
  renderer: 'villa',
  meter: '3/4',
  sentences: [
    { spec: sentenceA.spec, fixture: sentenceA.fixture },
    { spec: sentenceB.spec, fixture: sentenceB.fixture },
  ],
});
const exported = patternDraftJson(appended.draft);
if (exported.includes('rangeLabel') || exported.includes('renderHash')) {
  throw new Error('export bundle must contain only spec + fixture per sentence');
}

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
