import type { RecapVariant } from '../api/client';

export const GENRES: { id: RecapVariant; label: string }[] = [
  { id: 'symphony', label: 'Giao hưởng' },
  { id: 'jazz', label: 'Jazz' },
  { id: 'minimalist', label: 'Tối giản' },
  { id: 'ambient', label: 'Ambient' },
  { id: 'guitar', label: 'Guitar' },
];

/** Live socket variants. Guitar is a composed file, not a stream. */
export const STREAM_GENRES = GENRES.filter(
  (item): item is { id: 'symphony' | 'jazz' | 'minimalist' | 'ambient'; label: string } =>
    item.id !== 'guitar',
);

export type StreamVariant = (typeof STREAM_GENRES)[number]['id'];

export const LISTEN_SPANS = ['1D', '1W', '1M', '3M', '1Y'] as const;
export type ListenSpan = (typeof LISTEN_SPANS)[number];

export function formatClock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
  const whole = Math.floor(seconds);
  const minutes = Math.floor(whole / 60);
  const remain = whole % 60;
  return `${minutes}:${remain.toString().padStart(2, '0')}`;
}

/**
 * A clock reading clamped to its own duration. Playback can report a second
 * past the file end, which used to print `4:23 / 4:20`.
 */
export function clockText(seconds: number, duration: number): string {
  const safeDuration = Number.isFinite(duration) && duration > 0 ? duration : null;
  const upper = safeDuration ?? (Number.isFinite(seconds) ? Math.max(0, seconds) : 0);
  const safe = Math.min(Math.max(0, Number.isFinite(seconds) ? seconds : 0), upper);
  return formatClock(safe);
}

export function chipDate(iso: string): { weekday: string; day: string } {
  const [year, month, day] = iso.split('-').map(Number);
  const when = new Date(year, (month || 1) - 1, day || 1);
  const weekday = new Intl.DateTimeFormat('vi-VN', { weekday: 'short' })
    .format(when)
    .replace('.', '');
  return { weekday, day: `${day}/${month}` };
}

/**
 * Search folding for the command palette. Vietnamese labels must match a
 * query typed without diacritics: "giao huong" finds "Giao hưởng".
 */
export function foldText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .trim();
}

export type Delta = { glyph: string; text: string; positive: boolean };

/** Monochrome day change: the arrow carries the direction, the sparkline the slope. */
export function formatDelta(changePercent: number | null | undefined): Delta | null {
  if (changePercent == null || !Number.isFinite(changePercent)) return null;
  if (Math.abs(changePercent) < 0.005) {
    return { glyph: '·', text: '0.00%', positive: true };
  }
  return {
    glyph: changePercent > 0 ? '▲' : '▼',
    text: `${Math.abs(changePercent).toFixed(2)}%`,
    positive: changePercent > 0,
  };
}
