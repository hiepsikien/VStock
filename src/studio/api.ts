import { getApiBaseUrl } from '../api/client';
import {
  buildPreviewBody,
  buildValidateBody,
  normalizeErrors,
  normalizePreviewResponse,
  normalizeValidateResponse,
  type StudioPreviewResponse,
  type StudioValidateResponse,
} from './protocol';

export type {
  StudioError,
  StudioPreviewResponse,
  StudioValidateResponse,
} from './protocol';

/**
 * Studio sentence endpoints.
 *
 *   POST {prefix}/validate  body = one sentence spec mapping
 *   POST {prefix}/preview   body = { spec, fixture }
 *
 * `plan` / `row` / `notes` / `matrix` are deliberately `unknown`: the UI formats
 * them defensively so the backend can keep them structured (spans, a selection
 * matrix, a note list) without this screen freezing the payload shape.
 *
 * If the deployed prefix differs, change it in one place:
 * `EXPO_PUBLIC_STUDIO_SENTENCE_PREFIX` or `DEFAULT_SENTENCE_PREFIX`.
 */
export const DEFAULT_SENTENCE_PREFIX = '/v1/studio/sentence';

export const STUDIO_SENTENCE_PREFIX = (
  process.env.EXPO_PUBLIC_STUDIO_SENTENCE_PREFIX ?? DEFAULT_SENTENCE_PREFIX
).replace(/\/+$/, '');

export function studioSentenceUrl(action: 'validate' | 'preview'): string {
  return `${getApiBaseUrl()}${STUDIO_SENTENCE_PREFIX}/${action}`;
}

function truncate(text: string, limit = 240): string {
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}

async function postStudio(
  action: 'validate' | 'preview',
  body: unknown,
  signal?: AbortSignal,
): Promise<unknown> {
  const res = await fetch(studioSentenceUrl(action), {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  const text = await res.text();
  let parsed: unknown = null;
  if (text.trim()) {
    try {
      parsed = JSON.parse(text);
    } catch {
      throw new Error(`Studio API ${res.status}: response is not JSON.`);
    }
  }

  if (!res.ok) {
    const errors = normalizeErrors(parsed);
    if (errors.length) return { ok: false, errors };
    throw new Error(
      `Studio API ${res.status}: ${truncate(text) || res.statusText || 'request failed'}`,
    );
  }

  return parsed;
}

/** Validate one spec mapping. Returns contract errors instead of throwing. */
export async function validateSentenceSpec(
  spec: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<StudioValidateResponse> {
  const body = await postStudio('validate', buildValidateBody(spec), signal);
  return normalizeValidateResponse(body);
}

/** Preview one spec with a fixture. Audio is not part of this workstream. */
export async function previewSentenceSpec(
  spec: Record<string, unknown>,
  fixture: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<StudioPreviewResponse> {
  const body = await postStudio('preview', buildPreviewBody(spec, fixture), signal);
  return normalizePreviewResponse(body);
}
