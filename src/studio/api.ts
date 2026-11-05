import { getApiBaseUrl } from '../api/client';
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
  type StudioAudioResponse,
  type StudioExamplesResponse,
  type StudioPreviewResponse,
  type StudioPublishResponse,
  type StudioPublishedSpec,
  type StudioPublishedSpecDetail,
  type StudioValidateResponse,
} from './protocol';

export type {
  StudioAudioResponse,
  StudioError,
  StudioExample,
  StudioExamplesResponse,
  StudioPreviewResponse,
  StudioPublishResponse,
  StudioPublishedSpec,
  StudioPublishedSpecDetail,
  StudioValidateResponse,
} from './protocol';

/**
 * Studio sentence endpoints.
 *
 *   GET  {prefix}/examples          -> { ok, examples: [{ pattern, meter, id, payload }] }
 *   POST {prefix}/validate          body = one sentence spec mapping
 *   POST {prefix}/preview           body = { spec, fixture }
 *   POST {prefix}/audio             body = { spec, fixture } | { renderHash }
 *   POST {prefix}/publish           body = one sentence spec mapping
 *   GET  {prefix}/specs             -> { ok, specs: [...] }
 *   GET  {prefix}/specs/{id}        -> summary + { payload }
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

export type StudioSentenceAction =
  | 'examples'
  | 'validate'
  | 'preview'
  | 'audio'
  | 'publish'
  | 'specs';

export function studioSentenceUrl(action: StudioSentenceAction): string {
  return `${getApiBaseUrl()}${STUDIO_SENTENCE_PREFIX}/${action}`;
}

export function studioSentenceSpecUrl(id: string): string {
  return `${studioSentenceUrl('specs')}/${encodeURIComponent(id)}`;
}

function truncate(text: string, limit = 240): string {
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}

async function readStudioResponse(res: Response, text: string): Promise<unknown> {
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

async function postStudio(
  action: 'validate' | 'preview' | 'audio' | 'publish',
  body: unknown,
  signal?: AbortSignal,
): Promise<unknown> {
  const res = await fetch(studioSentenceUrl(action), {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  return readStudioResponse(res, await res.text());
}

async function getStudio(
  url: string,
  signal?: AbortSignal,
): Promise<unknown> {
  // Published versions and examples must not come from a stale HTTP cache
  // right after a publish/refresh.
  const res = await fetch(url, { signal, cache: 'no-store' });
  return readStudioResponse(res, await res.text());
}

/** Validate one spec mapping. Returns contract errors instead of throwing. */
export async function validateSentenceSpec(
  spec: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<StudioValidateResponse> {
  const body = await postStudio('validate', buildValidateBody(spec), signal);
  return normalizeValidateResponse(body);
}

/** Preview one spec with a fixture. The render hash keys the audio cache. */
export async function previewSentenceSpec(
  spec: Record<string, unknown>,
  fixture: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<StudioPreviewResponse> {
  const body = await postStudio('preview', buildPreviewBody(spec, fixture), signal);
  return normalizePreviewResponse(body);
}

/** Load the authored examples palette. Falls back to embedded samples upstream. */
export async function fetchSentenceExamples(
  signal?: AbortSignal,
): Promise<StudioExamplesResponse> {
  return normalizeExamplesResponse(await getStudio(studioSentenceUrl('examples'), signal));
}

export type SentenceAudioInput =
  | { spec: Record<string, unknown>; fixture?: Record<string, unknown> }
  | { renderHash: string };

/** Synthesize (or reuse) the short preview WAV for a preview. */
export async function requestSentenceAudio(
  input: SentenceAudioInput,
  signal?: AbortSignal,
): Promise<StudioAudioResponse> {
  const body =
    'spec' in input
      ? buildAudioBody(input.spec, input.fixture)
      : buildAudioHashBody(input.renderHash);
  return normalizeAudioResponse(await postStudio('audio', body, signal));
}

/** Persist one spec, assigning the next version for its `(pattern, meter)`. */
export async function publishSentenceSpec(
  spec: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<StudioPublishResponse> {
  return normalizePublishResponse(await postStudio('publish', spec, signal));
}

/** Newest published versions first. */
export async function fetchPublishedSpecs(
  signal?: AbortSignal,
): Promise<StudioPublishedSpec[]> {
  return normalizeSpecsResponse(await getStudio(studioSentenceUrl('specs'), signal));
}

/** One published spec including its authored payload. */
export async function fetchPublishedSpec(
  id: string,
  signal?: AbortSignal,
): Promise<StudioPublishedSpecDetail> {
  return normalizePublishedSpecResponse(
    await getStudio(studioSentenceSpecUrl(id), signal),
  );
}
