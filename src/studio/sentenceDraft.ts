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
 *     -> { ok, mode, rhythmTemplate?, spec, fixture, preview: {
 *          renderHash?, audioUrl, durationSec, notes }, warnings,
 *          productionReady, errors? }
 *
 * `rhythmTemplate: true` marks a `new` draft whose spec is the selected
 * passage itself (a TextureSpec, not a SentenceSpec); its audio follows the
 * source rhythm. Existing-pattern drafts keep the template/SentenceSpec path.
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
export const VILLA_DRAFT_METERS: readonly string[] = ['2/4', '3/4', '4/4'];

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
  /**
   * True when `spec` is a passage-sourced TextureSpec (new-pattern rhythm
   * preview), not a SentenceSpec built from a template.
   */
  rhythmTemplate: boolean;
  spec: Record<string, unknown> | null;
  fixture: Record<string, unknown>;
  preview: SentenceDraftPreview | null;
  warnings: string[];
  productionReady: boolean;
  errors: StudioError[];
};

/**
 * Source line for the result box: `source rhythm` for a passage-sourced new
 * draft, or `template auto` / the chosen template for the existing path.
 */
export function sentenceDraftSourceLabel(
  templateId: string,
  rhythmTemplate: boolean,
): string {
  if (rhythmTemplate) return 'source rhythm';
  const template = text(templateId);
  return template ? `template ${template}` : 'template auto';
}

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
    rhythmTemplate:
      value.rhythmTemplate === true || value.rhythm_template === true,
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

/* ------------------------------------------------------------------------- *
 * Figure pool (Phase 4)
 * ------------------------------------------------------------------------- */

/**
 * The five Studio role tags. `key` is the body figure; short/long are the two
 * scripts of the same intro/outro role, not separate patterns.
 */
export type FigureTag =
  | 'key'
  | 'contrast'
  | 'close'
  | 'intro.short'
  | 'intro.long'
  | 'outro.short'
  | 'outro.long';

/** Missing a tag uses `key.body` when the body sentence is not derivable. */
export type FigureMissingTag = FigureTag | 'key.body';

export const FIGURE_TAGS: readonly FigureTag[] = [
  'key',
  'intro.short',
  'intro.long',
  'outro.short',
  'outro.long',
  'contrast',
  'close',
];

export const REQUIRED_FIGURE_TAGS: readonly FigureTag[] = [
  'key',
  'intro.short',
  'intro.long',
  'outro.short',
  'outro.long',
];

export const KEY_BODY_MISSING = 'key.body' as const;

/** Short scripts are 2 bars, long scripts are 4; body tags allow 1–4. */
const FIGURE_TAG_BARS: Partial<Record<FigureTag, number>> = {
  'intro.short': 2,
  'intro.long': 4,
  'outro.short': 2,
  'outro.long': 4,
};
const FIGURE_TAG_BAR_LIMITS: Partial<Record<FigureTag, readonly [number, number]>> = {
  contrast: [1, 4],
  close: [1, 4],
};

export type PatternDraftFigure = {
  /** Local stable id. */
  id: string;
  /** Maps 1:1 to `TEXTURE_CELLS[(pattern, meter)]`; defaults to `id`. */
  cellId: string;
  spec: Record<string, unknown>;
  bars: number;
  tags: FigureTag[];
  previewMode?: 'source' | 'aaba';
};

export type PatternDraft = PatternDraftMeta & {
  sentences: PatternDraftSentence[];
  /** Source of cells/tags. Absent on an old `{sentences}` draft. */
  figures?: PatternDraftFigure[];
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
    figures: [],
  };
}

export function isFigureTag(value: unknown): value is FigureTag {
  return typeof value === 'string' && (FIGURE_TAGS as readonly string[]).includes(value);
}

/** Bars required by a tagged script, or `null` for the flexible `key` tag. */
export function figureTagBars(tag: FigureTag): number | null {
  return FIGURE_TAG_BARS[tag] ?? null;
}

/** Human-readable reason a tag does not fit `bars`, or `null` when it does. */
export function figureTagError(tag: FigureTag, bars: number): string | null {
  if (!Number.isFinite(bars) || bars < 1) return 'bars must be >= 1';
  const limits = FIGURE_TAG_BAR_LIMITS[tag];
  if (limits) {
    const [low, high] = limits;
    if (bars < low || bars > high) {
      return `${tag} needs ${low}-${high} bars, got ${bars}`;
    }
    return null;
  }
  const expected = figureTagBars(tag);
  if (expected != null && bars !== expected) {
    return `${tag} needs ${expected} bars, got ${bars}`;
  }
  return null;
}

function normalizeFigureTags(tags: readonly unknown[] | undefined): FigureTag[] {
  const seen = new Set<FigureTag>();
  for (const tag of tags ?? []) {
    if (isFigureTag(tag)) seen.add(tag);
  }
  return FIGURE_TAGS.filter((tag) => seen.has(tag));
}

export type CreatePatternFigureInput = {
  id: string;
  cellId?: string;
  spec: Record<string, unknown>;
  bars: number;
  tags?: readonly FigureTag[];
  previewMode?: 'source' | 'aaba';
};

export function createPatternFigure(input: CreatePatternFigureInput): PatternDraftFigure {
  const id = text(input.id) ?? '';
  const bars = Math.trunc(finite(input.bars) ?? 0);
  return {
    id,
    cellId: text(input.cellId) ?? id,
    spec: input.spec,
    bars,
    tags: normalizeFigureTags(input.tags),
    ...(input.previewMode ? { previewMode: input.previewMode } : {}),
  };
}

export function patternDraftFigures(draft: PatternDraft): PatternDraftFigure[] {
  return draft.figures ?? [];
}

function figuresOrList(
  value: PatternDraft | readonly PatternDraftFigure[],
): readonly PatternDraftFigure[] {
  return Array.isArray(value) ? value : patternDraftFigures(value as PatternDraft);
}

/** The bars a figure covers: max authored bar + 1, then source fallbacks. */
export function figureBarsFromTextureSpec(spec: Record<string, unknown>): number {
  const authored = isRecord(spec.authored) ? spec.authored : null;
  const events = authored && Array.isArray(authored.events) ? authored.events : [];
  let maxBar = -1;
  for (const event of events) {
    if (!isRecord(event)) continue;
    const bar = finite(event.bar);
    if (bar != null && bar >= 0) maxBar = Math.max(maxBar, Math.trunc(bar));
  }
  if (maxBar >= 0) return maxBar + 1;

  const source = isRecord(spec.source) ? spec.source : null;
  const bars = finite(source?.bars);
  if (bars != null && bars >= 1) return Math.trunc(bars);
  if (source && Array.isArray(source.passageBars) && source.passageBars.length === 2) {
    const start = finite(source.passageBars[0]);
    const end = finite(source.passageBars[1]);
    if (start != null && end != null && end >= start) {
      return Math.max(1, Math.trunc(end - start + 1));
    }
  }
  return 0;
}

/** Build a figure from a `TextureSpec` response; `null` when it has no bars. */
export function patternFigureFromTextureSpec(
  spec: Record<string, unknown>,
  options: {
    id?: string;
    cellId?: string;
    tags?: readonly FigureTag[];
    previewMode?: 'source' | 'aaba';
  } = {},
): PatternDraftFigure | null {
  const bars = figureBarsFromTextureSpec(spec);
  if (bars < 1) return null;
  const id = text(options.id) ?? text(spec.id) ?? 'figure';
  return createPatternFigure({
    id,
    cellId: options.cellId,
    spec,
    bars,
    tags: options.tags,
    previewMode: options.previewMode,
  });
}

export function appendPatternFigure(
  draft: PatternDraft,
  figure: PatternDraftFigure,
): PatternDraftAppendResult {
  const figures = patternDraftFigures(draft);
  if (figures.some((item) => item.id === figure.id)) {
    return {
      ok: false,
      error: `Figure ${figure.id} is already in this pattern draft.`,
      draft,
    };
  }
  if (
    figure.cellId &&
    figures.some((item) => item.cellId === figure.cellId)
  ) {
    return {
      ok: false,
      error: `Cell ${figure.cellId} is already used by another figure.`,
      draft,
    };
  }
  return { ok: true, draft: { ...draft, figures: [...figures, figure] } };
}

export function removePatternFigure(draft: PatternDraft, figureId: string): PatternDraft {
  const figures = patternDraftFigures(draft);
  if (!figures.some((figure) => figure.id === figureId)) return draft;
  return {
    ...draft,
    figures: figures.filter((figure) => figure.id !== figureId),
  };
}

/**
 * Give `tag` to one figure, taking it away from any other figure. A tag stays
 * on at most one figure (MVP); moving it never duplicates the figure.
 */
export function setFigureTag(
  draft: PatternDraft,
  figureId: string,
  tag: FigureTag,
): PatternDraftAppendResult {
  const figures = patternDraftFigures(draft);
  const target = figures.find((figure) => figure.id === figureId);
  if (!target) {
    return { ok: false, error: `Figure ${figureId} is not in this draft.`, draft };
  }
  const error = figureTagError(tag, target.bars);
  if (error) {
    return { ok: false, error: `${target.id}: ${error}`, draft };
  }
  return {
    ok: true,
    draft: {
      ...draft,
      figures: figures.map((figure) => {
        const tags = figure.tags.filter((item) => item !== tag);
        if (figure.id === figureId) tags.push(tag);
        return { ...figure, tags: normalizeFigureTags(tags) };
      }),
    },
  };
}

export function removeFigureTag(
  draft: PatternDraft,
  figureId: string,
  tag: FigureTag,
): PatternDraft {
  const figures = patternDraftFigures(draft);
  return {
    ...draft,
    figures: figures.map((figure) =>
      figure.id === figureId
        ? { ...figure, tags: figure.tags.filter((item) => item !== tag) }
        : figure,
    ),
  };
}

function figureTagValid(figure: PatternDraftFigure, tag: FigureTag): boolean {
  return figureTagError(tag, figure.bars) === null;
}

function validFigureOwners(
  figures: readonly PatternDraftFigure[],
): Map<FigureTag, PatternDraftFigure[]> {
  const owners = new Map<FigureTag, PatternDraftFigure[]>();
  for (const figure of figures) {
    for (const tag of figure.tags) {
      if (!isFigureTag(tag) || !figureTagValid(figure, tag)) continue;
      const list = owners.get(tag) ?? [];
      list.push(figure);
      owners.set(tag, list);
    }
  }
  return owners;
}

/** SentenceSpecs in the draft that already use the key figure's cell. */
function bodySentenceProblems(
  draft: PatternDraft,
  key: PatternDraftFigure,
): string[] {
  const problems: string[] = [];
  for (const sentence of draft.sentences) {
    const spec = sentence.spec;
    if (!isRecord(spec) || !Array.isArray(spec.slots)) continue;
    const usesCell = spec.slots.some(
      (slot) => isRecord(slot) && text(slot.cell) === key.cellId,
    );
    if (!usesCell) continue;
    const span = isRecord(spec.span) ? spec.span : null;
    const tile = span ? finite(span.tile) : null;
    for (const slot of spec.slots) {
      if (!isRecord(slot) || text(slot.cell) !== key.cellId) continue;
      const bars = finite(slot.bars);
      if (bars != null && Math.trunc(bars) !== key.bars) {
        problems.push(
          `${text(spec.id) ?? 'sentence'}: key cell slot has ${Math.trunc(
            bars,
          )} bars, figure has ${key.bars}`,
        );
      }
    }
    if (tile != null && tile < key.bars) {
      problems.push(
        `${text(spec.id) ?? 'sentence'}: tile ${Math.trunc(
          tile,
        )} is shorter than the key figure (${key.bars} bars)`,
      );
    }
  }
  return problems;
}

/**
 * Required tags that no valid figure owns, in display order. A missing or
 * ambiguous key reports `key.body`; duplicate tags are incomplete (MVP).
 */
export function missingFigureTags(
  value: PatternDraft | readonly PatternDraftFigure[],
): FigureMissingTag[] {
  const figures = figuresOrList(value);
  const owners = validFigureOwners(figures);
  const draft = Array.isArray(value) ? null : (value as PatternDraft);
  const missing: FigureMissingTag[] = [];
  for (const tag of REQUIRED_FIGURE_TAGS) {
    const unique = (owners.get(tag)?.length ?? 0) === 1;
    if (tag === 'key') {
      if (!unique) {
        missing.push(KEY_BODY_MISSING);
        continue;
      }
      if (draft && bodySentenceProblems(draft, owners.get(tag)![0]).length > 0) {
        missing.push(KEY_BODY_MISSING);
      }
    } else if (!unique) {
      missing.push(tag);
    }
  }
  return missing;
}

/** The one key figure, when it is uniquely and validly tagged. */
export function patternDraftKeyFigure(
  draft: PatternDraft,
): PatternDraftFigure | null {
  const owners = validFigureOwners(patternDraftFigures(draft)).get('key') ?? [];
  return owners.length === 1 ? owners[0] : null;
}

/** Optional back-compat projection; never read as the source of truth. */
export function patternDraftKeyFigures(draft: PatternDraft): PatternDraftFigure[] {
  return patternDraftFigures(draft).filter((figure) => figure.tags.includes('key'));
}

export function patternDraftComplete(draft: PatternDraft): boolean {
  return missingFigureTags(draft).length === 0;
}

/**
 * Tolerant loader for a saved/exported draft. An old `{sentences}` payload
 * becomes `figures: []` (and therefore incomplete); `keyFigures` is ignored.
 */
export function normalizePatternDraft(
  value: unknown,
  fallback?: Partial<PatternDraftMeta>,
): PatternDraft | null {
  if (!isRecord(value)) return null;
  const id = text(value.id) ?? text(fallback?.id);
  if (!id) return null;
  const sentences: PatternDraftSentence[] = [];
  if (Array.isArray(value.sentences)) {
    for (const item of value.sentences) {
      if (!isRecord(item) || !isRecord(item.spec)) continue;
      sentences.push({
        spec: item.spec,
        fixture: isRecord(item.fixture) ? item.fixture : {},
        ...(text(item.rangeLabel) ? { rangeLabel: text(item.rangeLabel)! } : {}),
        ...(typeof item.audioUrl === 'string' || item.audioUrl === null
          ? { audioUrl: item.audioUrl }
          : {}),
        ...(finite(item.durationSec) != null
          ? { durationSec: finite(item.durationSec)! }
          : {}),
        ...(typeof item.renderHash === 'string' || item.renderHash === null
          ? { renderHash: item.renderHash }
          : {}),
      });
    }
  }
  const figures: PatternDraftFigure[] = [];
  if (Array.isArray(value.figures)) {
    for (const item of value.figures) {
      if (!isRecord(item) || !isRecord(item.spec)) continue;
      const figureId = text(item.id);
      if (!figureId) continue;
      const bars = Math.trunc(finite(item.bars) ?? 0);
      const tags = normalizeFigureTags(
        Array.isArray(item.tags) ? (item.tags as unknown[]) : [],
      );
      const previewMode =
        item.previewMode === 'source' || item.previewMode === 'aaba'
          ? item.previewMode
          : undefined;
      figures.push(
        createPatternFigure({
          id: figureId,
          cellId: text(item.cellId) ?? figureId,
          spec: item.spec,
          bars,
          tags,
          previewMode,
        }),
      );
    }
  }
  return {
    id,
    label: text(value.label) ?? text(fallback?.label) ?? id,
    composer: text(value.composer) ?? text(fallback?.composer) ?? '',
    renderer: text(value.renderer) ?? text(fallback?.renderer) ?? '',
    meter: text(value.meter) ?? text(fallback?.meter) ?? '',
    sentences,
    figures,
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
  const missing = missingFigureTags(draft);
  return {
    id: draft.id,
    label: draft.label,
    composer: draft.composer,
    renderer: draft.renderer,
    meter: draft.meter,
    figures: patternDraftFigures(draft).map((figure) => ({
      id: figure.id,
      cellId: figure.cellId,
      spec: figure.spec,
      bars: figure.bars,
      tags: [...figure.tags],
      ...(figure.previewMode ? { previewMode: figure.previewMode } : {}),
    })),
    sentences: draft.sentences.map((sentence) => ({
      spec: sentence.spec,
      fixture: sentence.fixture,
    })),
    complete: missing.length === 0,
    missing,
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

/* ------------------------------------------------------------------------- *
 * Render Piece (Phase D)
 *
 * `POST /v1/studio/figure/render` takes the tagged figure pool, a plan id, a
 * resolved 1D bar series and a form. MusicXML comes back immediately; audio is
 * an async production job:
 *
 *   POST /v1/studio/figure/render                     -> RenderResponse
 *   POST /v1/studio/figure/render/{renderHash}/audio   -> 202 { jobId }
 *   GET  /v1/studio/figure/render/{renderHash}/audio/{jobId}
 *
 * The UI uses this module for the request body and response normalization; it
 * never publishes and never edits the SentenceSpec editor.
 * ------------------------------------------------------------------------- */

/** Plan ids implemented by `sentence_plan.py` today. */
export type FigureRenderPlanId = 'auto_aaba' | 'trio';

export type FigureRenderPlanOption = {
  id: FigureRenderPlanId;
  label: string;
  /** Role pattern, e.g. `A A B close`. */
  roles: string;
  hint: string;
};

/**
 * The picker is data, not hardcoded ABA branches. ABAB/through stay out until
 * the backend implements them (docs §5).
 */
export const FIGURE_RENDER_PLANS: readonly FigureRenderPlanOption[] = [
  {
    id: 'auto_aaba',
    label: 'AABA',
    roles: 'A A B close',
    hint: 'Key body, contrast, cadence close',
  },
  {
    id: 'trio',
    label: 'Trio',
    roles: 'A B A',
    hint: 'Key body, contrast, key return',
  },
];

export const FIGURE_RENDER_PLAN_IDS: readonly FigureRenderPlanId[] =
  FIGURE_RENDER_PLANS.map((option) => option.id);

/** Documented but not implemented yet; never rendered by this UI. */
export const FUTURE_FIGURE_RENDER_PLAN_IDS = ['abab', 'through'] as const;

export function isFigureRenderPlanId(value: unknown): value is FigureRenderPlanId {
  const id = text(value);
  return id != null && (FIGURE_RENDER_PLAN_IDS as readonly string[]).includes(id);
}

export type FigureRenderFormSpan = '1W' | '1M';

export const FIGURE_RENDER_FORM_SPANS: readonly FigureRenderFormSpan[] = ['1W', '1M'];

/** `1M` defaults to movement III (index 2), per the plan doc. */
export const DEFAULT_FIGURE_RENDER_MOVEMENT_INDEX = 2;

export type FigureRenderBar = {
  close: number;
  volume: number;
};

export type FigureRenderFigure = {
  id: string;
  cellId: string;
  bars: number;
  tags: string[];
  spec: Record<string, unknown>;
};

export type FigureRenderForm = {
  span: FigureRenderFormSpan;
  /** Only sent for `1M`; the backend defaults to movement index 2 too. */
  movementIndex?: number;
};

export type FigureRenderRequest = {
  pattern: string;
  meter: string;
  figures: FigureRenderFigure[];
  plan: { id: FigureRenderPlanId };
  series: { kind: 'bars'; bars: FigureRenderBar[] };
  form: FigureRenderForm;
  /** Optional; falls back to the draft label. */
  title?: string;
  options: { includeDoors: boolean };
};

export type FigureRenderOptions = {
  /** Defaults to the draft id. */
  pattern?: string;
  /** Defaults to the draft meter. */
  meter?: string;
  includeDoors?: boolean;
  /** Defaults to the draft label; an empty value omits the field. */
  title?: string | null;
  /** Defaults to `{ span: "1W" }`. */
  form?: FigureRenderFormSpan | FigureRenderForm;
};

export type FigureRenderBuildResult =
  | { ok: true; request: FigureRenderRequest }
  | { ok: false; error: string; missing: FigureMissingTag[] };

/** Backend limit (`_MAX_SERIES_BARS`); never truncate to fit. */
export const MAX_FIGURE_RENDER_SERIES_BARS = 4096;

function buildError(
  error: string,
  missing: FigureMissingTag[] = [],
): FigureRenderBuildResult {
  return { ok: false, error, missing };
}

function normalizeRenderBars(
  series: readonly FigureRenderBar[],
): { ok: true; bars: FigureRenderBar[] } | { ok: false; error: string } {
  if (!Array.isArray(series) || series.length === 0) {
    return { ok: false, error: 'The 1D series needs at least one bar.' };
  }
  if (series.length > MAX_FIGURE_RENDER_SERIES_BARS) {
    return {
      ok: false,
      error: `The 1D series has ${series.length} bars; the backend accepts at most ${MAX_FIGURE_RENDER_SERIES_BARS}.`,
    };
  }
  const bars: FigureRenderBar[] = [];
  for (let index = 0; index < series.length; index += 1) {
    const bar = series[index];
    if (!bar || !Number.isFinite(bar.close)) {
      return { ok: false, error: `series.bars[${index}].close must be a finite number.` };
    }
    if (!Number.isFinite(bar.volume) || bar.volume < 0) {
      return {
        ok: false,
        error: `series.bars[${index}].volume must be a finite number >= 0.`,
      };
    }
    bars.push({ close: bar.close, volume: bar.volume });
  }
  return { ok: true, bars };
}

/**
 * Build the Render Piece request body. Sends the whole series and lets the
 * backend answer 400 when it is shorter than the form (W9: no silent truncate
 * or repeat). Returns an error value instead of throwing when the pool is
 * missing a required tag.
 */
export function buildFigureRenderRequest(
  draft: PatternDraft,
  planId: FigureRenderPlanId,
  series: readonly FigureRenderBar[],
  options: FigureRenderOptions = {},
): FigureRenderBuildResult {
  const missing = missingFigureTags(draft);
  if (missing.length > 0) {
    return buildError(`missing figure tags: ${missing.join(', ')}`, missing);
  }
  if (!isFigureRenderPlanId(planId)) {
    return buildError(
      `unknown plan ${String(planId)}; expected ${FIGURE_RENDER_PLAN_IDS.join(', ')}`,
    );
  }

  const pattern = text(options.pattern) ?? text(draft.id);
  if (!pattern) return buildError('pattern must be a non-empty string');
  const meter = text(options.meter) ?? text(draft.meter);
  if (!meter) return buildError('meter must be a non-empty string');

  const normalized = normalizeRenderBars(series);
  if (!normalized.ok) return buildError(normalized.error);

  const rawForm = options.form ?? '1W';
  const span = typeof rawForm === 'string' ? rawForm : rawForm?.span;
  if (span !== '1W' && span !== '1M') {
    return buildError(`unknown form span ${String(span)}; expected 1W or 1M`);
  }
  const form: FigureRenderForm = { span };
  if (span === '1M') {
    const requested =
      typeof rawForm === 'object' && rawForm != null ? rawForm.movementIndex : undefined;
    const movementIndex =
      typeof requested === 'number' && Number.isInteger(requested)
        ? requested
        : DEFAULT_FIGURE_RENDER_MOVEMENT_INDEX;
    if (movementIndex < 0 || movementIndex > 3) {
      return buildError('form.movementIndex must be an integer in 0..3 for span 1M');
    }
    form.movementIndex = movementIndex;
  }

  const title = text(options.title) ?? text(draft.label);
  const request: FigureRenderRequest = {
    pattern,
    meter,
    figures: patternDraftFigures(draft).map((figure) => ({
      id: figure.id,
      cellId: figure.cellId,
      bars: figure.bars,
      tags: [...figure.tags],
      spec: figure.spec,
    })),
    plan: { id: planId },
    series: { kind: 'bars', bars: normalized.bars },
    form,
    options: { includeDoors: options.includeDoors ?? true },
    ...(title ? { title } : {}),
  };
  return { ok: true, request };
}

/** Stable JSON signature used to invalidate a rendered piece. */
export function figureRenderDraftKey(draft: PatternDraft): string {
  return JSON.stringify({
    id: draft.id,
    label: draft.label,
    meter: draft.meter,
    figures: patternDraftFigures(draft).map((figure) => ({
      id: figure.id,
      cellId: figure.cellId,
      bars: figure.bars,
      tags: figure.tags,
      spec: figure.spec,
    })),
  });
}

export type DemoSeriesRange = '1D' | '1W' | '1M';

export type DemoSeriesOption = {
  id: DemoSeriesRange;
  label: string;
  hint: string;
};

/**
 * Synthetic data ranges exposed by the MVP Render Piece UI. They are demo
 * data with progressively shorter waves, so `1W`/`1M` exercise more pitch
 * movement than `1D`. A symbol/date loader replaces them later.
 */
export const DEMO_SERIES_OPTIONS: readonly DemoSeriesOption[] = [
  {
    id: '1D',
    label: 'Demo 1D',
    hint: 'One session · 3 slow price cycles',
  },
  {
    id: '1W',
    label: 'Demo 1W',
    hint: 'One week · more intraday swings',
  },
  {
    id: '1M',
    label: 'Demo 1M',
    hint: 'One month · most movement',
  },
];

export const DEMO_SERIES_IDS: readonly DemoSeriesRange[] =
  DEMO_SERIES_OPTIONS.map((option) => option.id);

export function isDemoSeriesRange(value: unknown): value is DemoSeriesRange {
  return typeof value === 'string' && (DEMO_SERIES_IDS as readonly string[]).includes(value);
}

export const DEMO_SERIES_LABEL = 'Demo 1D series';

function demoClose(range: DemoSeriesRange, t: number): number {
  if (range === '1W') {
    return 100 + 14 * t + 20 * Math.sin(t * Math.PI * 10) + 7 * Math.sin(t * Math.PI * 30);
  }
  if (range === '1M') {
    return 100 + 10 * t + 16 * Math.sin(t * Math.PI * 18) + 6 * Math.sin(t * Math.PI * 54);
  }
  return 100 + 18 * t + 24 * Math.sin(t * Math.PI * 6);
}

function demoVolume(range: DemoSeriesRange, t: number): number {
  if (range === '1W') {
    return 220 + 80 * (0.5 + 0.5 * Math.sin(t * Math.PI * 4)) + 30 * Math.sin(t * Math.PI * 12);
  }
  if (range === '1M') {
    return 260 + 70 * (0.5 + 0.5 * Math.sin(t * Math.PI * 8)) + 25 * Math.sin(t * Math.PI * 24);
  }
  return 180 + 90 * (0.5 + 0.5 * Math.sin(t * Math.PI * 2));
}

/**
 * Deterministic synthetic series for a demo data range. A symbol/date picker
 * will replace it later; today it is clearly labeled demo data and never
 * touches the network or the repo.
 *
 * `1W` and `1M` deliberately use shorter waves plus a small harmonic so the
 * rendered melody changes pitch more often than the `1D` series.
 *
 * 64 bars is enough for `1W`; the UI requests more for `1M`.
 */
export function demoSeriesForRange(
  range: DemoSeriesRange = '1D',
  bars = 64,
): FigureRenderBar[] {
  const count =
    typeof bars === 'number' && Number.isFinite(bars) ? Math.max(1, Math.trunc(bars)) : 64;
  const series: FigureRenderBar[] = [];
  for (let index = 0; index < count; index += 1) {
    const t = count === 1 ? 0 : index / (count - 1);
    const close = demoClose(range, t);
    const volume = demoVolume(range, t);
    series.push({
      close: Math.round(close * 1000) / 1000,
      volume: Math.round(Math.max(0, volume)),
    });
  }
  return series;
}

/** Backwards-compatible alias for the default demo `1D` series. */
export function demoSeries(bars = 64): FigureRenderBar[] {
  return demoSeriesForRange('1D', bars);
}

/* ------------------------------------------------------------------------- *
 * Render Piece responses
 * ------------------------------------------------------------------------- */

export type FigureRenderAudioStatus = 'queued' | 'running' | 'ready' | 'failed';

export type FigureRenderAudioError = {
  path: string;
  code: string;
  message: string;
};

export type FigureRenderAudio = {
  status: FigureRenderAudioStatus;
  jobId: string | null;
  /** Resolved against the API base when one was supplied. */
  audioUrl: string | null;
  audioHash: string | null;
  durationSec: number;
  errors: FigureRenderAudioError[];
  retryAfterSec: number | null;
};

export type FigureRenderResponse = {
  ok: boolean;
  renderHash: string | null;
  musicxmlUrl: string | null;
  meter: string | null;
  bars: number;
  notes: number;
  plan: string | null;
  warnings: string[];
  errors: StudioError[];
  audio: FigureRenderAudio;
};

export type FigureAudioAccepted = {
  jobId: string;
  status: FigureRenderAudioStatus;
};

export type FigureAudioJob = FigureRenderAudio & {
  renderHash: string | null;
  durationSec: number;
};

function countValue(value: unknown): number {
  const number = finite(value);
  return number == null || number < 0 ? 0 : Math.trunc(number);
}

function retryAfterSeconds(value: unknown): number | null {
  const number = finite(value);
  return number == null || number < 0 ? null : Math.trunc(number);
}

function normalizeAudioStatus(
  value: unknown,
  fallback: FigureRenderAudioStatus,
): FigureRenderAudioStatus {
  const status = text(value)?.toLowerCase();
  switch (status) {
    case 'queued':
    case 'pending':
      return 'queued';
    case 'running':
    case 'rendering':
      return 'running';
    case 'ready':
    case 'ok':
    case 'done':
      return 'ready';
    case 'failed':
    case 'failure':
    case 'error':
    case 'unavailable':
      return 'failed';
    default:
      return fallback;
  }
}

function normalizeAudioErrors(value: unknown): FigureRenderAudioError[] {
  if (!Array.isArray(value)) {
    const single = text(value);
    return single
      ? [{ path: 'audio', code: 'audio_failed', message: single }]
      : [];
  }
  const errors: FigureRenderAudioError[] = [];
  for (const item of value) {
    if (isRecord(item)) {
      const code = text(item.code) ?? 'audio_failed';
      errors.push({
        path: text(item.path) ?? 'audio',
        code,
        message: text(item.message) ?? code,
      });
    } else {
      const message = text(item);
      if (message) errors.push({ path: 'audio', code: 'audio_failed', message });
    }
  }
  return errors;
}

/** Tolerant `audio` block normalizer for both render and job responses. */
export function normalizeFigureRenderAudio(
  value: unknown,
  baseUrl?: string | null,
): FigureRenderAudio {
  const raw = isRecord(value) ? value : {};
  const audioUrl = resolveAudioUrl(baseUrl ?? '', raw.audioUrl ?? raw.audio_url);
  const errors = normalizeAudioErrors(raw.errors);
  const fallback: FigureRenderAudioStatus = audioUrl
    ? 'ready'
    : errors.length > 0
      ? 'failed'
      : 'queued';
  return {
    status: normalizeAudioStatus(raw.status, fallback),
    jobId: text(raw.jobId) ?? text(raw.job_id),
    audioUrl,
    audioHash: text(raw.audioHash) ?? text(raw.audio_hash),
    durationSec: nonNegative(raw.durationSec ?? raw.duration_sec),
    errors,
    retryAfterSec: retryAfterSeconds(
      raw.retryAfter ?? raw.retryAfterSec ?? raw.retry_after,
    ),
  };
}

/** `POST /v1/studio/figure/render` normalizer. */
export function normalizeFigureRenderResponse(
  value: unknown,
  baseUrl?: string | null,
): FigureRenderResponse {
  if (!isRecord(value)) {
    throw new Error('Studio render API returned a non-object response.');
  }
  const errors = normalizeErrors(value);
  const renderHash = text(value.renderHash) ?? text(value.render_hash);
  return {
    ok:
      typeof value.ok === 'boolean'
        ? value.ok
        : Boolean(renderHash) && errors.length === 0,
    renderHash,
    musicxmlUrl: resolveAudioUrl(
      baseUrl ?? '',
      value.musicxmlUrl ?? value.musicxml_url,
    ),
    meter: text(value.meter),
    bars: countValue(value.bars),
    notes: countValue(value.notes),
    plan: text(value.plan),
    warnings: warningList(value.warnings),
    errors,
    audio: normalizeFigureRenderAudio(value.audio, baseUrl),
  };
}

/** `POST .../{renderHash}/audio` (202) normalizer. */
export function normalizeFigureAudioAccepted(value: unknown): FigureAudioAccepted {
  if (!isRecord(value)) {
    throw new Error('Studio render audio API returned a non-object response.');
  }
  const jobId = text(value.jobId) ?? text(value.job_id);
  if (!jobId) {
    // 429/400 answers arrive as `{ ok: false, errors }`; keep their path.
    const first = normalizeErrors(value)[0];
    if (first) {
      throw new Error(
        `${first.path && first.path !== '$' ? `${first.path}: ` : ''}${first.message}`,
      );
    }
    throw new Error('Studio render audio API did not return a job id.');
  }
  return {
    jobId,
    status: normalizeAudioStatus(value.status, 'queued'),
  };
}

/** `GET .../{renderHash}/audio/{jobId}` poll normalizer. */
export function normalizeFigureAudioJobResponse(
  value: unknown,
  baseUrl?: string | null,
): FigureAudioJob {
  if (!isRecord(value)) {
    throw new Error('Studio render audio job API returned a non-object response.');
  }
  const audio = normalizeFigureRenderAudio(value, baseUrl);
  const jobId = audio.jobId;
  if (!jobId) {
    throw new Error('Studio render audio job API did not return a job id.');
  }
  return {
    ...audio,
    jobId,
    renderHash: text(value.renderHash) ?? text(value.render_hash),
    durationSec: nonNegative(value.durationSec ?? value.duration_sec),
  };
}

/** Compact UI label for the render audio lifecycle. */
export function figureAudioStatusLabel(
  status: FigureRenderAudioStatus,
  durationSec = 0,
): string {
  switch (status) {
    case 'queued':
      return 'Audio queued';
    case 'running':
      return 'Rendering audio…';
    case 'ready':
      return durationSec > 0
        ? `Audio ready · ${durationSec.toFixed(2)} s`
        : 'Audio ready';
    case 'failed':
      return 'Audio failed';
  }
}

/** Relative render routes; `api.ts` prepends the API base. */
export const STUDIO_RENDER_PREFIX = '/v1/studio/figure';

function renderHashSegment(value: string): string {
  return encodeURIComponent(value.trim().replace(/^sha256:/i, ''));
}

export function figureRenderMusicXmlPath(renderHash: string): string {
  return `${STUDIO_RENDER_PREFIX}/render/${renderHashSegment(renderHash)}.musicxml`;
}

export function figureRenderWavPath(audioHash: string): string {
  return `${STUDIO_RENDER_PREFIX}/render/${renderHashSegment(audioHash)}.wav`;
}

export function figureRenderAudioPath(renderHash: string): string {
  return `${STUDIO_RENDER_PREFIX}/render/${renderHashSegment(renderHash)}/audio`;
}

export function figureRenderAudioJobPath(renderHash: string, jobId: string): string {
  return `${figureRenderAudioPath(renderHash)}/${encodeURIComponent(jobId.trim())}`;
}
