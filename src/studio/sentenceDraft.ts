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
];

export const KEY_BODY_MISSING = 'key.body' as const;

/** Short scripts are 2 bars, long scripts are 4; `key` allows any length >= 1. */
const FIGURE_TAG_BARS: Partial<Record<FigureTag, number>> = {
  'intro.short': 2,
  'intro.long': 4,
  'outro.short': 2,
  'outro.long': 4,
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
  for (const tag of FIGURE_TAGS) {
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
