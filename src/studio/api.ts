import { getApiBaseUrl } from '../api/client';
import {
  buildAnalyzeBody,
  buildAudioBody,
  buildAudioHashBody,
  buildJobBody,
  buildPreviewBody,
  buildTextureValidateBody,
  buildValidateBody,
  normalizeAccessResponse,
  normalizeAnalyzeResponse,
  normalizeAudioResponse,
  normalizeErrors,
  normalizeDeleteUploadResponse,
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
  parseRetryAfter,
  studioSessionError,
  type CropRect,
  type StudioAccess,
  type StudioAnalyzeDraft,
  type StudioDeleteUpload,
  type StudioAudioResponse,
  type StudioExamplesResponse,
  type StudioJobAccepted,
  type StudioJobKind,
  type StudioJobPoll,
  type StudioPreviewResponse,
  type StudioPublishResponse,
  type StudioPublishedSpec,
  type StudioPublishedSpecDetail,
  type StudioRollbackResponse,
  type StudioUpload,
  type StudioValidateResponse,
} from './protocol';
import { studioSessionHeaders } from './sessionStorage';

export type {
  CropRect,
  StudioAccess,
  StudioAnalysisMeasure,
  StudioAnalysisNote,
  StudioAnalyzeDraft,
  StudioAudioResponse,
  StudioError,
  StudioExample,
  StudioExamplesResponse,
  StudioJobAccepted,
  StudioJobDone,
  StudioJobKind,
  StudioJobPending,
  StudioJobPoll,
  StudioJobStatus,
  StudioPreviewResponse,
  StudioPublishResponse,
  StudioPublishedSpec,
  StudioPublishedSpecDetail,
  StudioQuota,
  StudioRollbackResponse,
  StudioUpload,
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
 *   POST {prefix}/specs/{id}/rollback -> { ok, id, pattern, meter, version, rollbackOf }
 *   GET  {prefix}/specs             -> { ok, specs: [...] }
 *   GET  {prefix}/specs/{id}        -> summary + { payload }
 *
 *   POST /v1/studio/texture/validate body = { spec } -> { ok, errors }
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

export const STUDIO_TEXTURE_PREFIX = (
  process.env.EXPO_PUBLIC_STUDIO_TEXTURE_PREFIX ?? '/v1/studio/texture'
).replace(/\/+$/, '');

export function studioTextureValidateUrl(): string {
  return `${getApiBaseUrl()}${STUDIO_TEXTURE_PREFIX}/validate`;
}

/** Roll back to a published version by creating a new version from its payload. */
export function studioSentenceRollbackUrl(id: string): string {
  return `${studioSentenceSpecUrl(id)}/rollback`;
}

/**
 * Pollable validate/preview jobs (Phase 1). Separate prefix from the sentence
 * contract: `POST /v1/studio/jobs`, `GET /v1/studio/jobs/{id}`.
 */
export const DEFAULT_STUDIO_JOBS_PREFIX = '/v1/studio/jobs';

export const STUDIO_JOBS_PREFIX = (
  process.env.EXPO_PUBLIC_STUDIO_JOBS_PREFIX ?? DEFAULT_STUDIO_JOBS_PREFIX
).replace(/\/+$/, '');

export function studioJobsUrl(): string {
  return `${getApiBaseUrl()}${STUDIO_JOBS_PREFIX}`;
}

export function studioJobUrl(id: string): string {
  return `${studioJobsUrl()}/${encodeURIComponent(id)}`;
}

/**
 * Phase 1 Studio endpoints (parallel backend workstream). `/access` gates the
 * upload/analyze panel; the other two live under the same prefix as the table
 * in docs §11.3. Override the prefix in one place with
 * `EXPO_PUBLIC_MUSICALIZE_STUDIO_PREFIX`.
 */
export const DEFAULT_MUSICALIZE_STUDIO_PREFIX = '/v1/musicalize/studio';

export const MUSICALIZE_STUDIO_PREFIX = (
  process.env.EXPO_PUBLIC_MUSICALIZE_STUDIO_PREFIX ??
  DEFAULT_MUSICALIZE_STUDIO_PREFIX
).replace(/\/+$/, '');

export function studioAccessUrl(): string {
  return `${getApiBaseUrl()}${MUSICALIZE_STUDIO_PREFIX}/access`;
}

export function studioUploadsUrl(): string {
  return `${getApiBaseUrl()}${MUSICALIZE_STUDIO_PREFIX}/uploads`;
}

export function studioUploadItemUrl(id: string): string {
  return `${studioUploadsUrl()}/${encodeURIComponent(id)}`;
}

export function studioAnalyzeUrl(): string {
  return `${getApiBaseUrl()}${MUSICALIZE_STUDIO_PREFIX}/analyze`;
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
    const sessionMessage = studioSessionError(
      res.status,
      parseRetryAfter(res.headers.get('retry-after')),
    );
    if (sessionMessage) throw new Error(sessionMessage);
    throw new Error(
      `Studio API ${res.status}: ${truncate(text) || res.statusText || 'request failed'}`,
    );
  }

  return parsed;
}

/** Session header on every Studio call (docs §11.3: all but `/access`). */
async function studioHeaders(
  extra: Record<string, string> = {},
): Promise<Record<string, string>> {
  return { ...(await studioSessionHeaders()), ...extra };
}

async function postStudioUrl(
  url: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<unknown> {
  const res = await fetch(url, {
    method: 'POST',
    headers: await studioHeaders({ 'content-type': 'application/json' }),
    body: JSON.stringify(body),
    signal,
  });
  return readStudioResponse(res, await res.text());
}

async function postStudio(
  action: 'validate' | 'preview' | 'audio' | 'publish',
  body: unknown,
  signal?: AbortSignal,
): Promise<unknown> {
  return postStudioUrl(studioSentenceUrl(action), body, signal);
}

async function getStudio(
  url: string,
  signal?: AbortSignal,
): Promise<unknown> {
  // Published versions and examples must not come from a stale HTTP cache
  // right after a publish/refresh.
  const res = await fetch(url, {
    headers: await studioHeaders(),
    signal,
    cache: 'no-store',
  });
  return readStudioResponse(res, await res.text());
}

/** Capability gate + per-session quota for the Studio. */
export async function fetchStudioAccess(
  signal?: AbortSignal,
): Promise<StudioAccess> {
  return normalizeAccessResponse(await getStudio(studioAccessUrl(), signal));
}

/** The browser's File/Blob; native pickers are out of scope in this pass. */
export type StudioUploadOptions = {
  /** Overrides `File.name` (useful when a canvas blob has no name). */
  filename?: string;
  signal?: AbortSignal;
};

function uploadFilename(file: Blob): string {
  if (typeof File !== 'undefined' && file instanceof File && file.name.trim()) {
    return file.name;
  }
  return 'spectrum.png';
}

/**
 * `POST /uploads` as multipart field `file` plus `X-Studio-Session`.
 * The browser sets the multipart boundary, so no `content-type` header here.
 */
export async function uploadStudioImage(
  file: Blob,
  options: StudioUploadOptions = {},
): Promise<StudioUpload> {
  if (typeof FormData === 'undefined') {
    throw new Error('Image upload needs a browser File/FormData runtime.');
  }
  const form = new FormData() as unknown as {
    append(name: string, value: Blob, filename?: string): void;
  };
  form.append('file', file, options.filename ?? uploadFilename(file));
  const res = await fetch(studioUploadsUrl(), {
    method: 'POST',
    headers: await studioSessionHeaders(),
    body: form as unknown as BodyInit,
    signal: options.signal,
  });
  return normalizeUploadResponse(await readStudioResponse(res, await res.text()));
}

/** `DELETE /uploads/{id}`; owner is the session header. */
export async function deleteStudioUpload(
  id: string,
  signal?: AbortSignal,
): Promise<StudioDeleteUpload> {
  const res = await fetch(studioUploadItemUrl(id), {
    method: 'DELETE',
    headers: await studioSessionHeaders(),
    signal,
  });
  return normalizeDeleteUploadResponse(
    await readStudioResponse(res, await res.text()),
  );
}

/**
 * `POST /analyze` for one uploaded image. The response is a TextureSpec note
 * draft; it is never loaded into the SentenceSpec editor automatically.
 */
export type StudioAnalyzeOptions = {
  metadata?: Record<string, unknown>;
  /** Source-image pixel rectangle; omit to analyze the whole image. */
  crop?: CropRect | null;
  signal?: AbortSignal;
};

export async function analyzeStudioImage(
  uploadId: string,
  options: StudioAnalyzeOptions = {},
): Promise<StudioAnalyzeDraft> {
  const body = await postStudioUrl(
    studioAnalyzeUrl(),
    buildAnalyzeBody(uploadId, options.metadata, options.crop),
    options.signal,
  );
  return normalizeAnalyzeResponse(body);
}

/** Validate one spec mapping. Returns contract errors instead of throwing. */
export async function validateSentenceSpec(
  spec: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<StudioValidateResponse> {
  const body = await postStudio('validate', buildValidateBody(spec), signal);
  return normalizeValidateResponse(body);
}

/**
 * Validate one TextureSpec draft mapping. No render, registry, or publish: the
 * backend runs the offline texture validator only.
 */
export async function validateTextureSpec(
  spec: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<StudioValidateResponse> {
  const body = await postStudioUrl(
    studioTextureValidateUrl(),
    buildTextureValidateBody(spec),
    signal,
  );
  return normalizeTextureValidateResponse(body);
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

/**
 * Enqueue one validate/preview job on the global Studio worker. The response is
 * a 202 with the job id; use `fetchStudioJob` to poll it.
 */
export async function submitStudioJob(
  kind: StudioJobKind,
  spec: Record<string, unknown>,
  fixture: Record<string, unknown> = {},
  signal?: AbortSignal,
): Promise<StudioJobAccepted> {
  const body = await postStudioUrl(
    studioJobsUrl(),
    buildJobBody(kind, spec, fixture),
    signal,
  );
  return normalizeJobAcceptedResponse(body);
}

/**
 * One poll of a Studio job. 409 stays a value (`kind: "pending"`) so callers
 * can back off; 404 and other failures throw.
 */
export async function fetchStudioJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<StudioJobPoll> {
  const res = await fetch(studioJobUrl(jobId), {
    headers: await studioHeaders(),
    signal,
    cache: 'no-store',
  });
  const raw = await res.text();
  let parsed: unknown = null;
  if (raw.trim()) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = null;
    }
  }

  if (res.status === 404) {
    throw new Error('Studio job was not found or has expired. Run the preview again.');
  }
  if (res.status !== 200 && res.status !== 409) {
    // Reuse the shared error path for 401/403/429/5xx so session/quota copy
    // stays consistent with the synchronous endpoints.
    await readStudioResponse(res, raw);
    throw new Error(`Studio API ${res.status}: unexpected job response.`);
  }

  const poll = normalizeJobPollResponse(
    parsed,
    res.status,
    parseRetryAfter(res.headers.get('retry-after')),
  );
  if (!poll) {
    throw new Error(`Studio API ${res.status}: unexpected job response.`);
  }
  return poll;
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

/**
 * Roll back to `id`: the backend copies that version's payload into a new
 * version and reports it via `rollbackOf`. The body is empty by contract.
 */
export async function rollbackSentenceSpec(
  id: string,
  signal?: AbortSignal,
): Promise<StudioRollbackResponse> {
  return normalizeRollbackResponse(
    await postStudioUrl(studioSentenceRollbackUrl(id), {}, signal),
    id,
  );
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
