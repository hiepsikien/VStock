/**
 * Pure sentence-draft model for the MusicXML panel (Sprint C).
 *
 * The backend builds the draft spec; this module only:
 *   - turns the 4-step form state into the documented request body,
 *   - normalizes the tolerant `sentence-draft` response,
 *   - keeps a local `PatternDraft` (pattern + sentences + fixtures) and
 *   - shapes the export bundle.
 *
 * It never writes into the SentenceSpec editor and never publishes.
 *
 * Contract (parallel backend work):
 *
 *   POST /v1/studio/import/musicxml/{importId}/sentence-draft
 *     body { barStart, beatStart, barEnd, beatEnd, mode, pattern?,
 *            templateId?, newPattern?, voices? }
 *     -> { ok, mode, spec, fixture, preview: { renderHash, audioUrl,
 *          durationSec, notes }, warnings, productionReady, errors? }
 *
 * Errors arrive as HTTP 200 `{ ok: false, errors: [{ path, message }] }`.
 */

import {
  isRecord,
  normalizeErrors,
  resolveAudioUrl,
  type StudioError,
} from './protocol';
import {
  ANY_METER,
  PATTERNS,
  SAMPLES,
  exampleLabel,
  patternOption,
  type StudioSample,
} from './spec';

export type SentenceDraftMode = 'existing' | 'new';

/** Patterns that can receive another sentence in `existing` mode. */
export const GENERIC_PATTERN_IDS = [
  'castillo',
  'sonatina',
  'fandanguillo',
  'danza',
  'galop',
] as const;

export type GenericPatternId = (typeof GENERIC_PATTERN_IDS)[number];

/** MVP: `new` mode reuses the Villa renderer/figure family. */
export const VILLA_RENDERER = 'villa';
export const VILLA_RENDERER_LABEL = 'Villa';
export const VILLA_COMPOSER = 'Villa-Lobos';
export const VILLA_DRAFT_METERS: readonly string[] = ['3/4', '4/4'];

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function finite(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function nonNegative(value: unknown): number {
  const number = finite(value);
  return number == null || number < 0 ? 0 : number;
}

function warningList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    const single = text(value);
    return single ? [single] : [];
  }
  return value
    .map((item) =>
      isRecord(item) ? text(item.message) ?? text(item.msg) : text(item),
    )
    .filter((item): item is string => item !== null);
}

/* ------------------------------------------------------------------------- *
 * Pattern ids / labels
 * ------------------------------------------------------------------------- */

/**
 * `Mazurka-Choro` -> `mazurka_choro`, `Café 3/4` -> `cafe_3_4`.
 * Lowercase ASCII words joined by single underscores; never empty for a name
 * that has at least one alphanumeric character.
 */
export function slugifyPatternId(name: string): string {
  return name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

/**
 * New-pattern id for the MVP: a `villa_` namespace prefix plus the slug.
 * Typing `villa_valsa_choro` does not double the prefix.
 */
export function newPatternId(name: string): string {
  const slug = slugifyPatternId(name);
  if (!slug) return '';
  return slug.startsWith(`${VILLA_RENDERER}_`) ? slug : `${VILLA_RENDERER}_${slug}`;
}

/** `Mazurka-Choro` stays as typed; an empty name falls back to the id. */
export function newPatternLabel(name: string, id: string): string {
  return text(name) ?? text(id) ?? '';
}

/** Reject suite gates and the preview-only pattern families. */
export function isGenericPatternId(value: unknown): value is GenericPatternId {
  const id = text(value);
  if (!id) return false;
  return (GENERIC_PATTERN_IDS as readonly string[]).includes(id);
}

export function isSuitePatternId(value: unknown): boolean {
  const id = text(value);
  return id != null && id.startsWith('suite_');
}

export function isVillaPatternId(value: unknown): boolean {
  const id = text(value);
  if (!id) return false;
  return id === 'villa_pattern' || id.startsWith('suite_');
}

/** Villa previews only know 3/4 and 4/4 today. */
export function villaMeterSupported(meter: unknown): boolean {
  const value = text(meter);
  return value != null && VILLA_DRAFT_METERS.includes(value);
}

export type SentencePatternOption = {
  id: string;
  label: string;
  composer: string;
};

/** Composer choices for a new pattern; never free text unless "New composer". */
export function composerOptions(): string[] {
  const seen = new Set<string>(['Villa-Lobos']);
  for (const pattern of PATTERNS) {
    if (pattern.composer === 'Villa') seen.add('Villa-Lobos');
    else if (pattern.composer) seen.add(pattern.composer);
  }
  return [...seen];
}

/** Generic production patterns only; `suite_*`/Villa/Barrios/Brouwer never appear. */
export function genericPatternOptions(
  samples: readonly StudioSample[] = SAMPLES,
): SentencePatternOption[] {
  const present = new Set<string>();
  for (const sample of samples) {
    if (isGenericPatternId(sample.pattern)) present.add(sample.pattern);
  }
  return GENERIC_PATTERN_IDS.filter((id) => present.has(id)).map((id) => {
    const meta = patternOption(id);
    return {
      id,
      label: meta?.label ?? id,
      composer: meta?.composer ?? '',
    };
  });
}

export type SentenceTemplateOption = {
  /** Value sent as `templateId`; empty string means "auto". */
  id: string;
  label: string;
  meter: string;
};

function templateId(sample: StudioSample): string {
  return sample.id ?? text(sample.spec.id) ?? sample.key;
}

function templateOption(sample: StudioSample): SentenceTemplateOption {
  return {
    id: templateId(sample),
    label: exampleLabel(sample),
    meter: sample.meter,
  };
}

/** Examples for one generic pattern at the passage meter. */
export function existingTemplateOptions(
  samples: readonly StudioSample[],
  pattern: string,
  meter: string,
): SentenceTemplateOption[] {
  const wanted = text(meter);
  if (!wanted) return [];
  return samples
    .filter(
      (sample) =>
        sample.pattern === pattern &&
        (sample.meter === wanted || sample.meter === ANY_METER),
    )
    .map(templateOption);
}

/** Villa example templates at the passage meter; empty outside 3/4 and 4/4. */
export function villaTemplateOptions(
  samples: readonly StudioSample[],
  meter: string,
): SentenceTemplateOption[] {
  const wanted = text(meter);
  if (!wanted || !villaMeterSupported(wanted)) return [];
  return samples
    .filter(
      (sample) => isVillaPatternId(sample.id ?? sample.pattern) && sample.meter === wanted,
    )
    .map(templateOption);
}

/* ------------------------------------------------------------------------- *
 * Request body
 * ------------------------------------------------------------------------- */

export type SentenceDraftNewPattern = {
  id: string;
  label: string;
  composer: string;
  renderer: string;
  meter: string;
  templateId?: string;
};

export type MusicXmlSentenceDraftRequest = {
  barStart: number;
  beatStart?: number;
  barEnd: number;
  beatEnd?: number;
  mode: SentenceDraftMode;
  pattern?: string;
  templateId?: string;
  newPattern?: SentenceDraftNewPattern;
  voices?: number[];
};

/** Pure request body builder; omits empty/unknown fields rather than guessing. */
export function buildSentenceDraftBody(
  request: MusicXmlSentenceDraftRequest,
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    barStart: Math.trunc(request.barStart),
    barEnd: Math.trunc(request.barEnd),
    mode: request.mode === 'new' ? 'new' : 'existing',
  };
  if (typeof request.beatStart === 'number' && Number.isFinite(request.beatStart)) {
    body.beatStart = request.beatStart;
  }
  if (typeof request.beatEnd === 'number' && Number.isFinite(request.beatEnd)) {
    body.beatEnd = request.beatEnd;
  }
  if (request.voices && request.voices.length) {
    body.voices = [...new Set(request.voices.map((voice) => Math.trunc(voice)))].sort(
      (left, right) => left - right,
    );
  }

  if (request.mode === 'new') {
    const pattern = request.newPattern;
    if (pattern) {
      const newPattern: Record<string, unknown> = {
        id: pattern.id,
        label: pattern.label,
        composer: pattern.composer,
        renderer: pattern.renderer,
        meter: pattern.meter,
      };
      const template = text(pattern.templateId);
      if (template) newPattern.templateId = template;
      body.newPattern = newPattern;
    }
    return body;
  }

  const pattern = text(request.pattern);
  if (pattern) body.pattern = pattern;
  const template = text(request.templateId);
  if (template) body.templateId = template;
  return body;
}

/* ------------------------------------------------------------------------- *
 * Response
 * ------------------------------------------------------------------------- */

export type SentenceDraftPreview = {
  renderHash: string | null;
  /** Resolved against the API base when one was supplied. */
  audioUrl: string | null;
  durationSec: number;
  notes: number;
};

export type SentenceDraftResponse = {
  ok: boolean;
  mode: SentenceDraftMode;
  spec: Record<string, unknown> | null;
  fixture: Record<string, unknown>;
  preview: SentenceDraftPreview | null;
  warnings: string[];
  productionReady: boolean;
  errors: StudioError[];
};

function previewNotes(value: unknown): number {
  if (Array.isArray(value)) return value.length;
  const number = finite(value);
  return number == null || number < 0 ? 0 : Math.trunc(number);
}

function normalizeDraftPreview(
  value: unknown,
  baseUrl: string,
): SentenceDraftPreview | null {
  if (!isRecord(value)) return null;
  const audio = text(value.audioUrl ?? value.audio_url);
  return {
    renderHash: text(value.renderHash ?? value.render_hash),
    audioUrl: audio ? resolveAudioUrl(baseUrl, audio) : null,
    durationSec: nonNegative(value.durationSec ?? value.duration_sec),
    notes: previewNotes(value.notes ?? value.noteCount ?? value.note_count),
  };
}

/** Tolerant normalizer: snake_case, missing preview, and HTTP-200 errors survive. */
export function normalizeSentenceDraftResponse(
  value: unknown,
  baseUrl?: string | null,
): SentenceDraftResponse {
  if (!isRecord(value)) {
    throw new Error('Sentence draft API returned a non-object response.');
  }
  const errors = normalizeErrors(value);
  const spec = isRecord(value.spec) ? value.spec : null;
  const fixture = isRecord(value.fixture) ? value.fixture : {};
  const nestedPreview = isRecord(value.preview) ? value.preview : null;
  const preview = normalizeDraftPreview(nestedPreview ?? value, baseUrl ?? '');
  const hasPreview = nestedPreview
    ? true
    : value.audioUrl != null ||
      value.audio_url != null ||
      value.renderHash != null ||
      value.render_hash != null ||
      value.durationSec != null ||
      value.duration_sec != null ||
      value.notes != null;

  return {
    ok:
      typeof value.ok === 'boolean'
        ? value.ok
        : spec != null && errors.length === 0,
    mode: value.mode === 'new' ? 'new' : 'existing',
    spec,
    fixture,
    preview: hasPreview ? preview : null,
    warnings: warningList(value.warnings),
    productionReady:
      typeof value.productionReady === 'boolean'
        ? value.productionReady
        : value.production_ready === true,
    errors,
  };
}

/* ------------------------------------------------------------------------- *
 * Local pattern draft
 * ------------------------------------------------------------------------- */

export type PatternDraftSentence = {
  spec: Record<string, unknown>;
  fixture: Record<string, unknown>;
  /** `bar 2 · beat 1.0 → bar 5 · beat 2.0`, captured at preview time. */
  rangeLabel?: string;
  audioUrl?: string | null;
  durationSec?: number;
  renderHash?: string | null;
};

export type PatternDraftMeta = {
  id: string;
  label: string;
  composer: string;
  renderer: string;
  meter: string;
};

export type PatternDraft = PatternDraftMeta & {
  sentences: PatternDraftSentence[];
};

export type PatternDraftAppendResult =
  | { ok: true; draft: PatternDraft }
  | { ok: false; error: string; draft: PatternDraft };

export function createPatternDraft(
  meta: PatternDraftMeta,
  sentence?: PatternDraftSentence,
): PatternDraft {
  return {
    id: meta.id,
    label: meta.label,
    composer: meta.composer,
    renderer: meta.renderer,
    meter: meta.meter,
    sentences: sentence ? [sentence] : [],
  };
}

/** Stable local duplicate key: the spec id, or its JSON when no id is sent. */
export function sentenceDraftKey(sentence: PatternDraftSentence): string {
  const id = text(sentence.spec.id);
  if (id) return id;
  try {
    return JSON.stringify(sentence.spec);
  } catch {
    return '';
  }
}

export function appendPatternSentence(
  draft: PatternDraft,
  sentence: PatternDraftSentence,
): PatternDraftAppendResult {
  const key = sentenceDraftKey(sentence);
  if (key && draft.sentences.some((item) => sentenceDraftKey(item) === key)) {
    return {
      ok: false,
      error: `Sentence ${key} is already in this pattern draft.`,
      draft,
    };
  }
  return { ok: true, draft: { ...draft, sentences: [...draft.sentences, sentence] } };
}

export function removePatternSentence(draft: PatternDraft, index: number): PatternDraft {
  if (index < 0 || index >= draft.sentences.length) return draft;
  return {
    ...draft,
    sentences: draft.sentences.filter((_, itemIndex) => itemIndex !== index),
  };
}

/** Export payload documented in the sprint plan; no extra preview fields. */
export function buildPatternDraftExport(draft: PatternDraft): Record<string, unknown> {
  return {
    id: draft.id,
    label: draft.label,
    composer: draft.composer,
    renderer: draft.renderer,
    meter: draft.meter,
    sentences: draft.sentences.map((sentence) => ({
      spec: sentence.spec,
      fixture: sentence.fixture,
    })),
  };
}

export function patternDraftJson(draft: PatternDraft): string {
  return JSON.stringify(buildPatternDraftExport(draft), null, 2);
}

/** One-line draft header, e.g. `villa_mazurka_choro · 3/4 · 2 sentences`. */
export function patternDraftLabel(draft: PatternDraft): string {
  const count = draft.sentences.length;
  return `${draft.id} · ${draft.meter} · ${count} sentence${count === 1 ? '' : 's'}`;
}
