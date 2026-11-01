import { Platform, type TextStyle } from 'react-native';

/**
 * Type roles for Musicalize.
 *
 * Display is serif: Georgia first because it was drawn for screens (large
 * x-height, low stroke contrast) and carries the full Vietnamese range —
 * checked against the local font files for `ạ ế đ ư ơ ộ ỹ ấ`. Palatino follows,
 * then Times New Roman for older Linux/Windows stacks.
 *
 * Mono is for symbols, clocks and numerals only. Menlo on macOS is missing
 * `ế` and `ấ`, so never set Vietnamese copy in the `mono` role; use `section`
 * or `sans` for that.
 */
const serifStack =
  Platform.select({
    web: "Georgia, 'Palatino Linotype', Palatino, 'Times New Roman', 'Noto Serif', serif",
    ios: 'Georgia',
    android: 'serif',
  }) ?? 'serif';

const sansStack =
  Platform.select({
    web: "-apple-system, 'SF Pro Text', 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif",
    ios: 'System',
    android: 'sans-serif',
  }) ?? 'sans-serif';

const monoStack =
  Platform.select({
    web: "ui-monospace, 'SF Mono', Menlo, 'Cascadia Mono', Consolas, monospace",
    ios: 'Menlo',
    android: 'monospace',
  }) ?? 'monospace';

export const font = {
  display: serifStack,
  sans: sansStack,
  wordmark: sansStack,
  section: sansStack,
  meta: monoStack,
  mono: monoStack,
} as const;

export const type = {
  display: {
    fontFamily: font.display,
    fontSize: 34,
    lineHeight: 38,
    fontWeight: '600',
    letterSpacing: -0.6,
    color: '#F4F1EA',
  },
  displayNarrow: {
    fontFamily: font.display,
    fontSize: 26,
    lineHeight: 30,
    fontWeight: '600',
    letterSpacing: -0.4,
    color: '#F4F1EA',
  },
  sans: {
    fontFamily: font.sans,
    fontSize: 14,
    lineHeight: 20,
    fontWeight: '500',
  },
  wordmark: {
    fontFamily: font.wordmark,
    fontSize: 13,
    lineHeight: 16,
    fontWeight: '700',
    letterSpacing: 3,
    textTransform: 'uppercase',
  },
  section: {
    fontFamily: font.section,
    fontSize: 11,
    lineHeight: 14,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  meta: {
    fontFamily: font.meta,
    fontSize: 12,
    lineHeight: 16,
    fontWeight: '500',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
  },
  mono: {
    fontFamily: font.mono,
    fontSize: 13,
    lineHeight: 16,
    fontWeight: '500',
    fontVariant: ['tabular-nums'],
  },
  monoSmall: {
    fontFamily: font.mono,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '500',
    fontVariant: ['tabular-nums'],
  },
} satisfies Record<string, TextStyle>;
