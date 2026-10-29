import { ENSEMBLE_ROWS, type RecapEnsemble, type RecapVariant } from '../api/client';

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

export function ensembleChoices(variant: RecapVariant): { id: RecapEnsemble; label: string }[] {
  return ENSEMBLE_ROWS[variant];
}

export function formatClock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
  const whole = Math.floor(seconds);
  const minutes = Math.floor(whole / 60);
  const remain = whole % 60;
  return `${minutes}:${remain.toString().padStart(2, '0')}`;
}

export function chipDate(iso: string): { weekday: string; day: string } {
  const [year, month, day] = iso.split('-').map(Number);
  const when = new Date(year, (month || 1) - 1, day || 1);
  const weekday = new Intl.DateTimeFormat('vi-VN', { weekday: 'short' })
    .format(when)
    .replace('.', '');
  return { weekday, day: `${day}/${month}` };
}
