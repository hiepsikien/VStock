import AsyncStorage from '@react-native-async-storage/async-storage';
import { getApiBaseUrl } from '../api/client';

export type TelemetryName = 'ab_toggle' | 'profile_save' | 'knob_change' | 'prefetch_fail';

type TelemetryEvent = {
  name: TelemetryName;
  at: number;
  payload: Record<string, unknown>;
};

const STORAGE_KEY = 'vstock.musicalize.events.v1';
const MAX_BUFFER = 50;
let inflight = false;

async function readBuffer(): Promise<TelemetryEvent[]> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed)
      ? parsed.filter(
          (item): item is TelemetryEvent =>
            Boolean(item) &&
            typeof item === 'object' &&
            typeof (item as TelemetryEvent).name === 'string' &&
            typeof (item as TelemetryEvent).at === 'number',
        )
      : [];
  } catch {
    return [];
  }
}

async function writeBuffer(events: TelemetryEvent[]): Promise<void> {
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(events.slice(-MAX_BUFFER)));
  } catch {
    // Telemetry must never break listening.
  }
}

async function flush(): Promise<void> {
  if (inflight) return;
  inflight = true;
  try {
    const events = await readBuffer();
    if (!events.length) return;
    const response = await fetch(`${getApiBaseUrl()}/v1/sonify/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events }),
    });
    if (response.ok) await writeBuffer([]);
  } catch {
    // Keep the buffer for the next attempt.
  } finally {
    inflight = false;
  }
}

/** Queue one event and try to flush. Offline keeps it for the next call. */
export async function trackEvent(
  name: TelemetryName,
  payload: Record<string, unknown> = {},
): Promise<void> {
  const events = await readBuffer();
  events.push({ name, at: Date.now() / 1000, payload });
  await writeBuffer(events);
  await flush();
}

export async function flushTelemetry(): Promise<void> {
  await flush();
}
