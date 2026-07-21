import React, { useMemo } from 'react';
import {
  LayoutAnimation,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  UIManager,
  useWindowDimensions,
  View,
} from 'react-native';
import type { ChartRange } from '../types';
import { colors, spacing, typography } from '../theme';
import { Sparkline } from './Sparkline';

if (
  Platform.OS === 'android' &&
  UIManager.setLayoutAnimationEnabledExperimental
) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const RANGES: ChartRange[] = ['1D', '1W', '1M', '3M', '1Y', '5Y'];
const CHART_HEIGHT = 248;

type Props = {
  prices: number[];
  positive: boolean;
  range: ChartRange;
  onRangeChange: (range: ChartRange) => void;
};

export function PriceChart({ prices, positive, range, onRangeChange }: Props) {
  const { width: screenWidth } = useWindowDimensions();
  // Edge-to-edge feel — only small side inset for sparkline padding.
  const chartWidth = Math.max(300, screenWidth - 8);

  const stats = useMemo(() => {
    if (!prices.length) return { min: 0, max: 0 };
    return { min: Math.min(...prices), max: Math.max(...prices) };
  }, [prices]);

  return (
    <View style={styles.wrap}>
      <View style={styles.chartArea}>
        {prices.length > 1 ? (
          <Sparkline
            data={prices}
            width={chartWidth}
            height={CHART_HEIGHT}
            positive={positive}
            strokeWidth={2.25}
            showFill
          />
        ) : (
          <Text style={styles.emptyChart}>Chưa có dữ liệu chart</Text>
        )}
      </View>

      {prices.length > 1 ? (
        <View style={styles.axis} pointerEvents="none">
          <Text style={styles.axisText}>{stats.max.toFixed(2)}</Text>
          <Text style={styles.axisText}>{stats.min.toFixed(2)}</Text>
        </View>
      ) : null}

      <View style={styles.segmentTrack}>
        {RANGES.map((item) => {
          const active = item === range;
          return (
            <Pressable
              key={item}
              onPress={() => {
                LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
                onRangeChange(item);
              }}
              style={[styles.segment, active && styles.segmentActive]}
              hitSlop={4}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
            >
              <Text style={[styles.segmentText, active && styles.segmentTextActive]}>
                {item}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginTop: spacing.sm,
    position: 'relative',
  },
  chartArea: {
    alignItems: 'center',
    justifyContent: 'center',
    height: CHART_HEIGHT + 12,
  },
  emptyChart: {
    color: colors.textTertiary,
    fontSize: 14,
  },
  axis: {
    position: 'absolute',
    right: spacing.lg,
    top: 10,
    bottom: 58,
    justifyContent: 'space-between',
    alignItems: 'flex-end',
  },
  axisText: {
    ...typography.caption,
    color: colors.textTertiary,
    fontVariant: ['tabular-nums'],
  },
  segmentTrack: {
    flexDirection: 'row',
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    padding: 2,
    borderRadius: 9,
    backgroundColor: 'rgba(255,255,255,0.06)',
  },
  segment: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 7,
    borderRadius: 7,
  },
  segmentActive: {
    backgroundColor: 'rgba(255,255,255,0.14)',
  },
  segmentText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  segmentTextActive: {
    color: colors.text,
  },
});
