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
 *   GET  {prefix}/specs     -> { ok, specs: [{ id, pattern, meter, version, status, createdAt }] }
 *   GET  {prefix}/specs/{id} -> summary + { payload }
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

export type StudioPublishedSpec = {
  id: string;
  pattern: string;
  meter: string;
  version: number;
  status: string;
  createdAt: string;
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
  const raw = item.path ?? item.loc ?? '$';
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
  const list = Array.isArray(body.errors)
    ? body.errors
    : Array.isArray(body.detail)
      ? body.detail
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

function normalizePublishedSpec(value: unknown): StudioPublishedSpec | null {
  if (!isRecord(value)) return null;
  const id = text(value.id);
  const pattern = text(value.pattern);
  const meter = text(value.meter);
  if (!id || !pattern || !meter) return null;
  return {
    id,
    pattern,
    meter,
    version: positiveInteger(value.version) ?? 0,
    status: text(value.status) ?? '',
    createdAt: text(value.createdAt) ?? text(value.created_at) ?? '',
  };
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
