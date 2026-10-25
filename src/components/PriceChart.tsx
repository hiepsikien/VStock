import React, { useCallback, useMemo, useState } from 'react';
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
import { titleCoversCursor, type PieceProgram } from '../sonify/program';
import { PieceTitle, TITLE_DOCK_LEFT } from './PieceTitle';
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
  cursorIndex?: number | null;
  cursorLabel?: string | null;
  dimUnplayed?: boolean;
  /** Inclusive index window into `prices`. Omit to show the whole series. */
  focusStart?: number;
  focusEnd?: number;
  program?: PieceProgram | null;
};

export function PriceChart({
  prices,
  positive,
  range,
  onRangeChange,
  cursorIndex = null,
  cursorLabel = null,
  dimUnplayed = false,
  focusStart,
  focusEnd,
  program = null,
}: Props) {
  const { width: screenWidth } = useWindowDimensions();
  // Edge-to-edge feel — only small side inset for sparkline padding.
  const chartWidth = Math.max(300, screenWidth - 8);

  const visible = useMemo(() => {
    if (prices.length < 2) return { start: 0, end: 0, values: prices };
    const start = focusStart ?? 0;
    const end = focusEnd ?? prices.length - 1;
    const i0 = Math.max(0, Math.floor(start));
    const i1 = Math.min(prices.length - 1, Math.ceil(end));
    return { start, end, values: prices.slice(i0, i1 + 1) };
  }, [focusEnd, focusStart, prices]);

  const stats = useMemo(() => {
    if (!visible.values.length) return { min: 0, max: 0 };
    return { min: Math.min(...visible.values), max: Math.max(...visible.values) };
  }, [visible.values]);

  const labelLeft = useMemo(() => {
    if (cursorIndex == null || prices.length < 2) return 8;
    const span = Math.max(visible.end - visible.start, 1e-6);
    const x = ((cursorIndex - visible.start) / span) * chartWidth;
    return Math.min(chartWidth - 58, Math.max(8, x - 22));
  }, [chartWidth, cursorIndex, prices.length, visible.end, visible.start]);
  const [titleWidth, setTitleWidth] = useState(0);
  const [labelWidth, setLabelWidth] = useState(0);
  const onDockWidth = useCallback((width: number) => {
    setTitleWidth((current) => (current === width ? current : width));
  }, []);
  const cursorUnderTitle = titleCoversCursor(
    !!program?.docked,
    titleWidth,
    labelLeft,
    labelWidth,
    TITLE_DOCK_LEFT,
  );

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
            cursorIndex={cursorIndex}
            dimUnplayed={dimUnplayed}
            focusStart={focusStart}
            focusEnd={focusEnd}
          />
        ) : (
          <Text style={styles.emptyChart}>Chưa có dữ liệu chart</Text>
        )}
        {program ? (
          <PieceTitle
            title={program.title}
            instruments={program.instruments}
            movement={program.movement}
            docked={program.docked}
            onDockWidth={onDockWidth}
          />
        ) : null}
        {cursorLabel &&
        cursorIndex != null &&
        cursorIndex >= visible.start - 0.01 &&
        cursorIndex <= visible.end + 0.01 ? (
          <View
            pointerEvents="none"
            accessibilityElementsHidden={cursorUnderTitle}
            importantForAccessibility={cursorUnderTitle ? 'no-hide-descendants' : 'auto'}
            onLayout={(event) => {
              const width = event.nativeEvent.layout.width;
              setLabelWidth((current) => (current === width ? current : width));
            }}
            style={[styles.cursorLabel, { left: labelLeft, opacity: cursorUnderTitle ? 0 : 1 }]}
          >
            <Text style={styles.cursorLabelText}>{cursorLabel}</Text>
          </View>
        ) : null}
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
    position: 'relative',
  },
  cursorLabel: {
    position: 'absolute',
    top: 6,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    backgroundColor: 'rgba(10,132,255,0.9)',
  },
  cursorLabelText: {
    ...typography.caption,
    color: colors.text,
    fontVariant: ['tabular-nums'],
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
