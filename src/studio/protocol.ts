/**
 * Wire types and normalisers for the Studio sentence endpoints.
 *
 * Kept free of `react-native` / `expo-constants` imports so the pure helpers
 * can run in the `tsx` test process. `api.ts` adds the fetch layer.
 *
 * Contract owned by workstream B:
 *
 *   POST {prefix}/validate  body = one sentence spec mapping
 *        -> { ok, errors: [{ path, message }] }
 *   POST {prefix}/preview   body = { spec, fixture }
 *        -> { ok, errors, plan, row, notes, renderHash, matrix }
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

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
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
