import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  loadStudioSession,
  newStudioSession,
  sessionHeader,
  type StudioSessionStore,
} from './session';

/**
 * App-side wiring for the Studio session. AsyncStorage is imported only here so
 * the pure helpers in `session.ts` stay testable in node.
 */

let cached: Promise<string> | null = null;

/** One id per install/browser, shared by every Studio request. */
export function studioSessionId(): Promise<string> {
  if (!cached) {
    cached = loadStudioSession(AsyncStorage as StudioSessionStore).catch(() =>
      newStudioSession(),
    );
  }
  return cached;
}

/** Headers for a Studio request; empty only if the id is somehow invalid. */
export async function studioSessionHeaders(): Promise<Record<string, string>> {
  return sessionHeader(await studioSessionId());
}
