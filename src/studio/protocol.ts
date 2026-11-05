/**
 * Wire types and normalisers for the Studio sentence endpoints.
 *
 * Kept free of `react-native` / `expo-constants` imports so the pure helpers
 * can run in the `tsx` test process. `api.ts` adds the fetch layer.
 *
 * Contract owned by workstream B:
 *
 *   GET  {prefix}/examples  { ok, examples: [{ pattern, meter, id, payload }] }
 *   POST {prefix}/validate  body = one sentence spec mapping
 *        -> { ok, errors: [{ path, message }] }
 *   POST {prefix}/preview   body = { spec, fixture }
 *        -> { ok, errors, plan, row, notes, renderHash, matrix }
 *   POST {prefix}/audio     body = { spec, fixture } | { renderHash }
 *        -> { ok, errors, audioUrl, durationSec, renderHash }
 *   POST {prefix}/publish   body = one sentence spec mapping
 *        -> { ok, id, pattern, meter, version, errors }
 *   POST {prefix}/specs/{id}/rollback
 *        -> { ok, id, pattern, meter, version, rollbackOf, errors }
 *   GET  {prefix}/specs     -> { ok, specs: [{ id, pattern, meter, version, status, createdAt, rollbackOf? }] }
 *   GET  {prefix}/specs/{id} -> summary + { payload }
 *
 * TextureSpec draft validation lives beside it:
 *
 *   POST /v1/studio/texture/validate  body = { spec }
 *        -> { ok, errors: [{ path, message }] }
 *
 * `rollbackOf` is optional on summaries (and absent for ordinary publishes):
 * it names the published version a rollback row was copied from.
 */

export type StudioError = {
  path: string;
  message: string;
};

export type StudioValidateResponse = {
  ok: boolean;
  errors: StudioError[];
};

export type StudioPreviewResponse = StudioValidateResponse & {
  plan: unknown;
  row: unknown;
  notes: unknown;
  renderHash: string | null;
  matrix: unknown;
};

/** One authoring example served by `GET /sentence/examples`. */
export type StudioExample = {
  id: string;
  pattern: string;
  meter: string;
  payload: Record<string, unknown>;
};

export type StudioExamplesResponse = {
  ok: boolean;
  examples: StudioExample[];
};

export type StudioAudioResponse = {
  ok: boolean;
  errors: StudioError[];
  audioUrl: string | null;
  durationSec: number;
  renderHash: string | null;
};

export type StudioPublishResponse = {
  ok: boolean;
  id: string | null;
  pattern: string | null;
  meter: string | null;
  version: number | null;
  errors: StudioError[];
};

export type StudioRollbackResponse = {
  ok: boolean;
  id: string | null;
  pattern: string | null;
  meter: string | null;
  version: number | null;
  rollbackOf: string | null;
  errors: StudioError[];
};

export type StudioPublishedSpec = {
  id: string;
  pattern: string;
  meter: string;
  version: number;
  status: string;
  createdAt: string;
  /** Present only on rows created by a rollback; names the source version. */
  rollbackOf?: string;
};

export type StudioPublishedSpecDetail = StudioPublishedSpec & {
  payload: Record<string, unknown>;
};

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function positiveInteger(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value > 0
    ? value
    : null;
}

function nonNegativeNumber(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
    ? value
    : 0;
}

export function buildValidateBody(spec: Record<string, unknown>): Record<string, unknown> {
  return spec;
}

/** `POST /texture/validate` wraps the spec so the route can grow options later. */
export function buildTextureValidateBody(
  spec: Record<string, unknown>,
): { spec: Record<string, unknown> } {
  return { spec };
}

/**
 * The texture route returns the same `{ ok, errors }` contract as the sentence
 * validator; keep one normalizer so path/message handling cannot drift.
 */
export function normalizeTextureValidateResponse(
  body: unknown,
): StudioValidateResponse {
  return normalizeValidateResponse(body);
}

export function buildPreviewBody(
  spec: Record<string, unknown>,
  fixture: Record<string, unknown>,
): { spec: Record<string, unknown>; fixture: Record<string, unknown> } {
  return { spec, fixture };
}

export function buildAudioBody(
  spec: Record<string, unknown>,
  fixture: Record<string, unknown> = {},
): { spec: Record<string, unknown>; fixture: Record<string, unknown> } {
  return { spec, fixture };
}

export function buildAudioHashBody(renderHash: string): { renderHash: string } {
  return { renderHash };
}

function errorMessage(item: unknown): string {
  if (typeof item === 'string') return item;
  if (!isRecord(item)) return String(item);
  if (typeof item.message === 'string') return item.message;
  if (typeof item.msg === 'string') return item.msg;
  return 'Unknown validation error';
}

function errorPath(item: unknown): string {
  if (!isRecord(item)) return '$';
  const raw = item.path ?? item.loc ?? item.code ?? '$';
  if (Array.isArray(raw)) {
    const parts = raw.filter((part) => part !== 'body' && part != null).map(String);
    return parts.length ? parts.join('.') : '$';
  }
  return typeof raw === 'string' && raw.trim() ? raw : '$';
}

/**
 * Normalise the documented `{ok, errors}` shape. FastAPI's default `detail`
 * shape is accepted too, so a proxy/schema failure still shows a useful path
 * instead of a raw string.
 */
export function normalizeErrors(body: unknown): StudioError[] {
  if (!isRecord(body)) return [];
  const detail = body.detail;
  const list = Array.isArray(body.errors)
    ? body.errors
    : Array.isArray(detail)
      ? detail
      : typeof detail === 'string' && detail.trim()
        ? [detail]
        : isRecord(detail)
          ? [detail]
          : [];
  return list.map((item) => ({ path: errorPath(item), message: errorMessage(item) }));
}

export function normalizeValidateResponse(body: unknown): StudioValidateResponse {
  if (!isRecord(body)) {
    throw new Error('Studio API returned a non-object response.');
  }
  const errors = normalizeErrors(body);
  return {
    ok: typeof body.ok === 'boolean' ? body.ok : errors.length === 0,
    errors,
  };
}

export function normalizePreviewResponse(body: unknown): StudioPreviewResponse {
  const base = normalizeValidateResponse(body);
  if (!isRecord(body)) {
    throw new Error('Studio API returned a non-object response.');
  }
  const hash =
    typeof body.renderHash === 'string'
      ? body.renderHash
      : typeof body.render_hash === 'string'
        ? body.render_hash
        : null;
  return {
    ...base,
    plan: body.plan ?? null,
    row: body.row ?? null,
    notes: body.notes ?? null,
    renderHash: hash,
    matrix: body.matrix ?? null,
  };
}

/** Parse the examples list, dropping entries that cannot load into the editor. */
export function normalizeExamplesResponse(body: unknown): StudioExamplesResponse {
  if (!isRecord(body)) {
    throw new Error('Studio examples API returned a non-object response.');
  }
  const raw = Array.isArray(body.examples)
    ? body.examples
    : Array.isArray(body.specs)
      ? body.specs
      : [];
  const examples: StudioExample[] = [];
  for (const item of raw) {
    if (!isRecord(item)) continue;
    const payload = isRecord(item.payload)
      ? item.payload
      : isRecord(item.spec)
        ? item.spec
        : null;
    if (!payload) continue;
    const pattern = text(item.pattern) ?? text(payload.pattern);
    const meter = text(item.meter) ?? text(payload.meter);
    if (!pattern || !meter) continue;
    const id = text(item.id) ?? text(payload.id) ?? `${pattern}:${meter}`;
    examples.push({ id, pattern, meter, payload });
  }
  return {
    ok: typeof body.ok === 'boolean' ? body.ok : true,
    examples,
  };
}

export function normalizeAudioResponse(body: unknown): StudioAudioResponse {
  if (!isRecord(body)) {
    throw new Error('Studio audio API returned a non-object response.');
  }
  const errors = normalizeErrors(body);
  const audioUrl = text(body.audioUrl) ?? text(body.audio_url);
  const hash = text(body.renderHash) ?? text(body.render_hash);
  return {
    ok: typeof body.ok === 'boolean' ? body.ok : Boolean(audioUrl) && !errors.length,
    errors,
    audioUrl,
    durationSec: nonNegativeNumber(body.durationSec ?? body.duration_sec),
    renderHash: hash,
  };
}

export function normalizePublishResponse(body: unknown): StudioPublishResponse {
  if (!isRecord(body)) {
    throw new Error('Studio publish API returned a non-object response.');
  }
  const errors = normalizeErrors(body);
  const id = text(body.id);
  return {
    ok: typeof body.ok === 'boolean' ? body.ok : Boolean(id) && !errors.length,
    id,
    pattern: text(body.pattern),
    meter: text(body.meter),
    version: positiveInteger(body.version),
    errors,
  };
}

/**
 * Normalise a rollback response. `rollbackOf` should point at the version that
 * was rolled back; when the server omits it (or uses snake_case), the caller's
 * source id is the fallback, so lineage still renders.
 */
export function normalizeRollbackResponse(
  body: unknown,
  sourceId?: string | null,
): StudioRollbackResponse {
  if (!isRecord(body)) {
    throw new Error('Studio rollback API returned a non-object response.');
  }
  const errors = normalizeErrors(body);
  const id = text(body.id);
  return {
    ok: typeof body.ok === 'boolean' ? body.ok : Boolean(id) && !errors.length,
    id,
    pattern: text(body.pattern),
    meter: text(body.meter),
    version: positiveInteger(body.version),
    rollbackOf:
      text(body.rollbackOf) ?? text(body.rollback_of) ?? text(sourceId),
    errors,
  };
}

function normalizePublishedSpec(value: unknown): StudioPublishedSpec | null {
  if (!isRecord(value)) return null;
  const id = text(value.id);
  const pattern = text(value.pattern);
  const meter = text(value.meter);
  if (!id || !pattern || !meter) return null;
  const spec: StudioPublishedSpec = {
    id,
    pattern,
    meter,
    version: positiveInteger(value.version) ?? 0,
    status: text(value.status) ?? '',
    createdAt: text(value.createdAt) ?? text(value.created_at) ?? '',
  };
  const rollbackOf = text(value.rollbackOf) ?? text(value.rollback_of);
  if (rollbackOf) spec.rollbackOf = rollbackOf;
  return spec;
}

/** Accept the documented `{ ok, specs }` wrapper and a bare array (older proxies). */
export function normalizeSpecsResponse(body: unknown): StudioPublishedSpec[] {
  if (Array.isArray(body)) {
    return body
      .map(normalizePublishedSpec)
      .filter((item): item is StudioPublishedSpec => item !== null);
  }
  if (!isRecord(body)) {
    throw new Error('Studio specs API returned a non-object response.');
  }
  const raw = Array.isArray(body.specs) ? body.specs : [];
  return raw
    .map(normalizePublishedSpec)
    .filter((item): item is StudioPublishedSpec => item !== null);
}

export function normalizePublishedSpecResponse(
  body: unknown,
): StudioPublishedSpecDetail {
  if (!isRecord(body)) {
    throw new Error('Studio spec API returned a non-object response.');
  }
  const summary = normalizePublishedSpec(body);
  if (!summary) {
    throw new Error('Studio spec response is missing id, pattern, or meter.');
  }
  return {
    ...summary,
    payload: isRecord(body.payload) ? body.payload : {},
  };
}

/**
 * Turn the server's relative `/v1/studio/.../audio/key.wav` into a browser URL.
 * Absolute URLs pass through so a CDN can replace the local audio route later.
 */
export function resolveAudioUrl(baseUrl: string, value: unknown): string | null {
  const raw = text(value);
  if (!raw) return null;
  if (/^(https?:|blob:|data:)/i.test(raw)) return raw;
  const base = baseUrl.trim().replace(/\/+$/, '');
  const path = raw.startsWith('/') ? raw : `/${raw}`;
  return base ? `${base}${path}` : path;
}

/* ------------------------------------------------------------------------- *
 * Phase 1 front half: access, upload, analyze.
 *
 * Contract (parallel backend workstream, docs §10.2.1 / §11.3):
 *
 *   GET  {prefix}/access   -> { enabled, reason, seats?, quota }
 *   POST {prefix}/uploads  multipart `file` -> { ok, id, sha256, filename,
 *                            mime, url, token, width?, height? }
 *   POST {prefix}/analyze  { uploadId, crop?, metadata? }
 *                          -> { ok, measures, notes, warnings, cached,
 *                               partial?, skippedChecks? }
 *
 * Media URLs may be relative; callers resolve them against the API base.
 * ------------------------------------------------------------------------- */

export type StudioQuota = {
  uploadsPerDay: number;
  analysesPerDay: number;
  specsPerDay: number;
  maxImageMb: number;
  previewsConcurrent: number;
};

export type StudioAccess = {
  ok: boolean;
  enabled: boolean;
  /** `open_beta` | `entitled` | `disabled`; unknown values pass through. */
  reason: string;
  seats: number | null;
  quota: StudioQuota;
  errors: StudioError[];
};

export type StudioUpload = {
  ok: boolean;
  id: string | null;
  sha256: string | null;
  filename: string | null;
  mime: string | null;
  url: string | null;
  token: string | null;
  width: number | null;
  height: number | null;
  errors: StudioError[];
};

export type StudioAnalysisMeasure = {
  index: number | null;
  meter: string | null;
  key: string | null;
};

/** One draft note; names mirror the Gemini contract in docs §9.2. */
export type StudioAnalysisNote = {
  measure: number | null;
  bar: number | null;
  beat: number | null;
  durationBeats: number | null;
  voiceHint: string | null;
  writtenPitch: string | null;
  soundingPitch: string | null;
  string: number | null;
  fret: number | null;
  confidence: number | null;
  conflict: boolean;
  review: string | null;
  tie: string | null;
  articulation: string[];
};

export type StudioAnalyzeDraft = {
  ok: boolean;
  measures: StudioAnalysisMeasure[];
  notes: StudioAnalysisNote[];
  warnings: string[];
  cached: boolean;
  partial: boolean;
  /** Top-level Gemini review state; per-note values are the durable copy. */
  review: string | null;
  /** Checks skipped because the draft has no render context (`pitch`, …). */
  skippedChecks: string[];
  errors: StudioError[];
};

const EMPTY_QUOTA: StudioQuota = {
  uploadsPerDay: 0,
  analysesPerDay: 0,
  specsPerDay: 0,
  maxImageMb: 0,
  previewsConcurrent: 0,
};

function optionalInteger(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
    ? value
    : null;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/** Accept 0..1, and defensively divide a 0..100 percentage. */
function confidenceValue(value: unknown): number | null {
  const number = finiteNumber(value);
  if (number == null || number < 0) return null;
  if (number <= 1) return number;
  if (number <= 100) return number / 100;
  return null;
}

function booleanFlag(value: unknown): boolean {
  return value === true || value === 'true' || value === 1;
}

/** `reason` is a free string so a new backend value still renders. */
export function normalizeAccessResponse(body: unknown): StudioAccess {
  if (!isRecord(body)) {
    throw new Error('Studio access API returned a non-object response.');
  }
  const errors = normalizeErrors(body);
  const quotaRaw = isRecord(body.quota) ? body.quota : {};
  const reason = text(body.reason) ?? 'unknown';
  const enabled =
    typeof body.enabled === 'boolean'
      ? body.enabled
      : body.ok === false || errors.length > 0
        ? false
        : reason !== 'disabled' && reason !== 'unknown';
  return {
    ok: typeof body.ok === 'boolean' ? body.ok : enabled,
    enabled,
    reason,
    seats: optionalInteger(body.seats),
    quota: {
      uploadsPerDay: nonNegativeNumber(quotaRaw.uploadsPerDay ?? quotaRaw.uploads_per_day),
      analysesPerDay: nonNegativeNumber(
        quotaRaw.analysesPerDay ?? quotaRaw.analyses_per_day,
      ),
      specsPerDay: nonNegativeNumber(quotaRaw.specsPerDay ?? quotaRaw.specs_per_day),
      maxImageMb: nonNegativeNumber(quotaRaw.maxImageMb ?? quotaRaw.max_image_mb),
      previewsConcurrent: nonNegativeNumber(
        quotaRaw.previewsConcurrent ?? quotaRaw.previews_concurrent,
      ),
    },
    errors,
  };
}

/** Empty quota for the loading/failure states so the UI has one shape. */
export function emptyStudioQuota(): StudioQuota {
  return { ...EMPTY_QUOTA };
}

export type StudioDeleteUpload = {
  ok: boolean;
  id: string | null;
  errors: StudioError[];
};

export function normalizeDeleteUploadResponse(body: unknown): StudioDeleteUpload {
  if (!isRecord(body)) {
    throw new Error('Studio delete-upload API returned a non-object response.');
  }
  const errors = normalizeErrors(body);
  const id = text(body.id) ?? text(body.uploadId) ?? text(body.upload_id);
  return {
    ok: typeof body.ok === 'boolean' ? body.ok : Boolean(id) && errors.length === 0,
    id,
    errors,
  };
}

export function normalizeUploadResponse(body: unknown): StudioUpload {
  if (!isRecord(body)) {
    throw new Error('Studio upload API returned a non-object response.');
  }
  const errors = normalizeErrors(body);
  const id = text(body.id) ?? text(body.uploadId) ?? text(body.upload_id);
  return {
    ok: typeof body.ok === 'boolean' ? body.ok : Boolean(id) && errors.length === 0,
    id,
    sha256: text(body.sha256) ?? text(body.sha),
    filename: text(body.filename) ?? text(body.name),
    mime: text(body.mime) ?? text(body.mimeType) ?? text(body.mime_type),
    url: text(body.url),
    token: text(body.token),
    width: optionalInteger(body.width),
    height: optionalInteger(body.height),
    errors,
  };
}

function measureValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function normalizeMeasure(value: unknown): StudioAnalysisMeasure | null {
  if (!isRecord(value)) return null;
  const index = optionalInteger(value.index);
  const meter = text(value.meter);
  const key = text(value.key);
  if (index == null && !meter && !key) return null;
  return { index, meter, key };
}

function articulationList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => text(item)).filter((item): item is string => item !== null);
}

function normalizeNote(value: unknown): StudioAnalysisNote | null {
  if (!isRecord(value)) return null;
  const measure = measureValue(value.measure);
  const bar = measureValue(value.bar);
  const writtenPitch = text(value.writtenPitch) ?? text(value.written_pitch);
  const soundingPitch = text(value.soundingPitch) ?? text(value.sounding_pitch);
  if (measure == null && bar == null && !writtenPitch && !soundingPitch) {
    return null;
  }
  return {
    measure,
    bar,
    beat: measureValue(value.beat),
    durationBeats:
      finiteNumber(value.durationBeats) ?? finiteNumber(value.duration_beats),
    voiceHint: text(value.voiceHint) ?? text(value.voice_hint) ?? text(value.voice),
    writtenPitch,
    soundingPitch,
    string: optionalInteger(value.string),
    fret: optionalInteger(value.fret),
    confidence: confidenceValue(value.confidence),
    conflict: booleanFlag(value.conflict),
    // Gemini drafts are pending; a note copied without an explicit state must
    // not fall back to `edited` in AuthoredEvent later.
    review: text(value.review) ?? 'pending',
    tie: text(value.tie),
    articulation: articulationList(value.articulation),
  };
}

function warningList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    const single = text(value);
    return single ? [single] : [];
  }
  return value
    .map((item) => (isRecord(item) ? text(item.message) ?? text(item.msg) : text(item)))
    .filter((item): item is string => item !== null);
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => text(item)).filter((item): item is string => item !== null);
}

export function normalizeAnalyzeResponse(body: unknown): StudioAnalyzeDraft {
  if (!isRecord(body)) {
    throw new Error('Studio analyze API returned a non-object response.');
  }
  // The vision endpoint wraps the transcription in `draft`; older/mocked
  // responses may still put the fields at the top level.
  const draft = isRecord(body.draft) ? body.draft : body;
  const errors = normalizeErrors(body);
  const backendError = isRecord(body.error) ? body.error : null;
  if (backendError && errors.length === 0) {
    const code = text(backendError.code) ?? 'analyze_failed';
    errors.push({ path: code, message: text(backendError.message) ?? code });
  }
  const measures = Array.isArray(draft.measures)
    ? draft.measures
        .map(normalizeMeasure)
        .filter((item): item is StudioAnalysisMeasure => item !== null)
    : [];
  const notes = Array.isArray(draft.notes)
    ? draft.notes
        .map(normalizeNote)
        .filter((item): item is StudioAnalysisNote => item !== null)
    : [];
  return {
    ok:
      typeof body.ok === 'boolean'
        ? body.ok
        : errors.length === 0 &&
          (measures.length > 0 ||
            notes.length > 0 ||
            Boolean(text(draft.review))),
    measures,
    notes,
    warnings: warningList(draft.warnings),
    review: text(draft.review) ?? text(body.review),
    cached:
      booleanFlag(body.cached) ||
      booleanFlag(body.cacheHit) ||
      booleanFlag(draft.cacheHit) ||
      booleanFlag(body.cache_hit) ||
      booleanFlag(draft.cached),
    partial: booleanFlag(body.partial) || booleanFlag(draft.partial),
    skippedChecks: stringList(
      draft.skippedChecks ??
        draft.skipped_checks ??
        body.skippedChecks ??
        body.skipped_checks,
    ),
    errors,
  };
}

/** Body for `POST /analyze`; metadata/crop are omitted when empty. */
export function buildAnalyzeBody(
  uploadId: string,
  metadata?: Record<string, unknown>,
  crop?: Record<string, unknown>,
): Record<string, unknown> {
  const body: Record<string, unknown> = { uploadId };
  if (crop && Object.keys(crop).length) body.crop = crop;
  if (metadata && Object.keys(metadata).length) body.metadata = metadata;
  return body;
}

/** `Retry-After` is seconds in this API; ignore HTTP-date values. */
export function parseRetryAfter(value: string | null | undefined): number | null {
  if (typeof value !== 'string') return null;
  const seconds = Number(value.trim());
  return Number.isFinite(seconds) && seconds >= 0 ? Math.round(seconds) : null;
}

/**
 * Friendly copy for a Studio session/quota rejection, or null for unrelated
 * statuses (which keep the generic `Studio API <status>` error).
 */
export function studioSessionError(
  status: number,
  retryAfterSec?: number | null,
): string | null {
  if (status === 401 || status === 403 || status === 428) {
    return 'Studio session was rejected. Reload the page to start a new session.';
  }
  if (status === 429) {
    const retry =
      typeof retryAfterSec === 'number' && retryAfterSec > 0
        ? ` Try again in ${retryAfterSec}s.`
        : ' Try again later.';
    return `Studio quota reached.${retry}`;
  }
  return null;
}
