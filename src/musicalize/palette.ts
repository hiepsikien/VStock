/** Studio palette for Musicalize. The stock terminal keeps `src/theme.ts`. */
export const palette = {
  background: '#08090C',
  panel: '#0F1319',
  surface: '#171C24',
  surfaceActive: '#1E242E',
  hairline: 'rgba(244, 241, 234, 0.08)',
  hairlineStrong: 'rgba(244, 241, 234, 0.16)',
  text: '#F4F1EA',
  textMuted: '#9AA3AD',
  textFaint: '#5C6572',
  data: '#3EE0E0',
  dataFill: 'rgba(62, 224, 224, 0.14)',
  sound: '#E040A0',
  soundSoft: 'rgba(224, 64, 160, 0.16)',
  playhead: '#F5B942',
  track: '#2A313A',
} as const;

export const WIDE_BREAKPOINT = 960;
export const COLUMN_WIDTH = 312;
export const TOPBAR_HEIGHT = 56;
export const DOCK_HEIGHT = 232;
export const TOUCH_TARGET = 44;
