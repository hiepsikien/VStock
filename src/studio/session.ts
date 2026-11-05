/**
 * Stable `X-Studio-Session` id for the Studio.
 *
 * This is a namespace, not auth (docs §10.2): the backend hashes it into an
 * `owner_id` so uploads/specs are not global and per-session quota can be
 * counted. One id per install/browser, kept in AsyncStorage.
 *
 * The pure helpers and `loadStudioSession` live here without importing
 * AsyncStorage, so `studio.test.ts` can exercise them with an in-memory store.
 * `sessionStorage.ts` wires AsyncStorage to this module for the app.
 */

export const STUDIO_SESSION_HEADER = 'X-Studio-Session';
export const STUDIO_SESSION_KEY = 'vstock.studio.session.v1';

/** The subset of AsyncStorage this module needs. */
export type StudioSessionStore = {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
};

/** Header-safe session tokens: base64url-ish, dots, colons, dashes. */
const SESSION_PATTERN = /^[A-Za-z0-9._:-]{8,128}$/;

function randomUuid(): string | null {
  const crypto = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (!crypto?.randomUUID) return null;
  try {
    const id = crypto.randomUUID();
    return typeof id === 'string' && id.trim() ? id.trim() : null;
  } catch {
    return null;
  }
}

function randomHex(length: number): string {
  let out = '';
  while (out.length < length) {
    out += Math.random().toString(16).slice(2);
  }
  return out.slice(0, length);
}

/**
 * `st_` + 32 hex chars (a UUID without dashes when the runtime has one).
 * A fresh value per call; persistence is the caller's job.
 */
export function newStudioSession(): string {
  const uuid = randomUuid();
  if (uuid) return `st_${uuid.replace(/-/g, '').toLowerCase()}`;
  return `st_${randomHex(32)}`;
}

/** Accept only tokens that are safe to put in a header. */
export function normalizeStudioSession(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return SESSION_PATTERN.test(trimmed) ? trimmed : null;
}

/**
 * Load the stored session or mint one. A broken/absent store still yields a
 * usable id for this app run; the write failure is swallowed like the other
 * AsyncStorage helpers in the app.
 */
export async function loadStudioSession(store: StudioSessionStore): Promise<string> {
  let stored: string | null = null;
  try {
    stored = normalizeStudioSession(await store.getItem(STUDIO_SESSION_KEY));
  } catch {
    stored = null;
  }
  if (stored) return stored;

  const created = newStudioSession();
  try {
    await store.setItem(STUDIO_SESSION_KEY, created);
  } catch {
    // A full/unavailable store must not block the upload panel.
  }
  return created;
}

/** `{}` for a missing/invalid id so a header is never sent empty. */
export function sessionHeader(id: string | null | undefined): Record<string, string> {
  const valid = normalizeStudioSession(id);
  return valid ? { [STUDIO_SESSION_HEADER]: valid } : {};
}

/** Compact indicator text, e.g. `st_1a2b3c4d…`. */
export function sessionLabel(id: string | null | undefined, keep = 10): string {
  const valid = normalizeStudioSession(id);
  if (!valid) return 'no session';
  return valid.length <= keep ? valid : `${valid.slice(0, keep)}…`;
}
