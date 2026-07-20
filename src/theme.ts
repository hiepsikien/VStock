export const colors = {
  background: '#000000',
  surface: '#1C1C1E',
  surfaceElevated: '#2C2C2E',
  separator: '#38383A',
  text: '#FFFFFF',
  textSecondary: '#8E8E93',
  textTertiary: '#636366',
  positive: '#30D158',
  negative: '#FF453A',
  accent: '#0A84FF',
  chartFill: 'rgba(48, 209, 88, 0.12)',
  chartFillNeg: 'rgba(255, 69, 58, 0.12)',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 28,
} as const;

export const typography = {
  largeTitle: {
    fontSize: 34,
    fontWeight: '700' as const,
    letterSpacing: 0.4,
  },
  title: {
    fontSize: 22,
    fontWeight: '600' as const,
  },
  symbol: {
    fontSize: 17,
    fontWeight: '600' as const,
  },
  body: {
    fontSize: 15,
    fontWeight: '400' as const,
  },
  caption: {
    fontSize: 13,
    fontWeight: '400' as const,
  },
  price: {
    fontSize: 17,
    fontWeight: '500' as const,
    fontVariant: ['tabular-nums' as const],
  },
  heroPrice: {
    fontSize: 40,
    fontWeight: '300' as const,
    fontVariant: ['tabular-nums' as const],
  },
};
