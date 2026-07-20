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

type Props = {
  prices: number[];
  positive: boolean;
  range: ChartRange;
  onRangeChange: (range: ChartRange) => void;
};

export function PriceChart({ prices, positive, range, onRangeChange }: Props) {
  const { width: screenWidth } = useWindowDimensions();
  const chartWidth = Math.max(280, screenWidth - 40);

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
            height={180}
            positive={positive}
            strokeWidth={2}
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

      <View style={styles.ranges}>
        {RANGES.map((item) => {
          const active = item === range;
          return (
            <Pressable
              key={item}
              onPress={() => {
                LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
                onRangeChange(item);
              }}
              style={[styles.rangeBtn, active && styles.rangeBtnActive]}
              hitSlop={6}
            >
              <Text style={[styles.rangeText, active && styles.rangeTextActive]}>
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
    marginTop: spacing.md,
    position: 'relative',
  },
  chartArea: {
    alignItems: 'center',
    justifyContent: 'center',
    height: 190,
  },
  emptyChart: {
    color: colors.textTertiary,
    fontSize: 14,
  },
  axis: {
    position: 'absolute',
    right: spacing.lg,
    top: 8,
    bottom: 52,
    justifyContent: 'space-between',
    alignItems: 'flex-end',
  },
  axisText: {
    ...typography.caption,
    color: colors.textTertiary,
    fontVariant: ['tabular-nums'],
  },
  ranges: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    marginTop: spacing.md,
  },
  rangeBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  rangeBtnActive: {
    backgroundColor: colors.surfaceElevated,
  },
  rangeText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  rangeTextActive: {
    color: colors.positive,
  },
});
