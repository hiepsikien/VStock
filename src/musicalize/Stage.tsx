import React, { useState } from 'react';
import { StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { Sparkline, volumeStripFor } from '../components/Sparkline';
import type { PieceProgram } from '../sonify/program';
import { palette, WIDE_BREAKPOINT } from './palette';
import { clamp01 } from './seek';
import { type } from './type';

const VOLUME_COLOR = 'rgba(62, 224, 224, 0.22)';

type Props = {
  prices: number[];
  volumes?: number[] | null;
  cursorIndex?: number | null;
  cursorLabel?: string | null;
  dimUnplayed?: boolean;
  focusStart?: number;
  focusEnd?: number;
  program?: PieceProgram | null;
  identity?: string | null;
  badge?: string | null;
  meta?: string | null;
  banner?: string | null;
  seekable?: boolean;
  onSeekRatio?: (ratio: number) => void;
};

export function Stage({
  prices,
  volumes = null,
  cursorIndex = null,
  cursorLabel = null,
  dimUnplayed = false,
  focusStart,
  focusEnd,
  program = null,
  identity = null,
  badge = null,
  meta = null,
  banner = null,
  seekable = false,
  onSeekRatio,
}: Props) {
  const { width } = useWindowDimensions();
  const displayStyle = width >= WIDE_BREAKPOINT ? type.display : type.displayNarrow;
  const [plot, setPlot] = useState({ width: 0, height: 0 });
  const chartWidth = Math.max(1, plot.width);
  const plotHeight = Math.max(1, plot.height);
  const volumeSeries = volumes && volumes.length > 0 && volumes.length === prices.length ? volumes : null;
  const visible = visibleBounds(prices, focusStart, focusEnd);
  const labelLeft =
    cursorIndex == null || prices.length < 2
      ? 8
      : Math.max(
          8,
          Math.min(
            Math.max(8, chartWidth - 96),
            ((cursorIndex - visible.start) / Math.max(visible.end - visible.start, 1e-6)) * chartWidth - 22,
          ),
        );
  const showCursor =
    cursorLabel != null &&
    cursorIndex != null &&
    cursorIndex >= visible.start - 0.01 &&
    cursorIndex <= visible.end + 0.01;
  const ticks = tickLabels(prices, visible);

  const seekAt = (locationX: number) => {
    if (!seekable || !onSeekRatio || chartWidth <= 0) return;
    onSeekRatio(clamp01(locationX / chartWidth));
  };

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        {program ? (
          <>
            <Text style={[displayStyle, styles.title]} numberOfLines={2}>
              {program.title}
            </Text>
            {program.movement ? (
              <Text style={[type.sans, styles.movement]} numberOfLines={2}>
                {program.movement}
              </Text>
            ) : null}
            {program.phase !== 'playing' && program.instruments ? (
              <Text style={[type.sans, styles.instruments]} numberOfLines={1}>
                {program.instruments}
              </Text>
            ) : null}
            {badge || meta ? (
              <View style={styles.metaRow}>
                {badge ? (
                  <View style={styles.badge}>
                    <Text style={[type.monoSmall, styles.badgeText]}>{badge}</Text>
                  </View>
                ) : null}
                {meta ? (
                  <Text style={[type.meta, styles.meta]} numberOfLines={1}>
                    {meta}
                  </Text>
                ) : null}
              </View>
            ) : null}
          </>
        ) : identity ? (
          <Text style={[displayStyle, styles.title]} numberOfLines={2}>
            {identity}
          </Text>
        ) : null}
      </View>

      <View style={styles.chartArea}>
        <View
          style={styles.chartFrame}
          onLayout={(event) => {
            const next = event.nativeEvent.layout;
            setPlot((current) =>
              current.width === next.width && current.height === next.height
                ? current
                : { width: next.width, height: next.height },
            );
          }}
          onStartShouldSetResponder={() => seekable}
          onMoveShouldSetResponder={() => seekable}
          onResponderTerminationRequest={() => false}
          onResponderGrant={(event) => seekAt(event.nativeEvent.locationX)}
          onResponderMove={(event) => seekAt(event.nativeEvent.locationX)}
        >
          {prices.length > 1 && plot.width > 0 && plot.height > 0 ? (
            <View pointerEvents="none">
              <Sparkline
                data={prices}
                width={plot.width}
                height={plot.height}
                positive
                strokeWidth={2.5}
                showFill
                flatFill={palette.dataFill}
                strokeColor={palette.data}
                playheadColor={palette.playhead}
                cursorIndex={cursorIndex}
                dimUnplayed={dimUnplayed}
                focusStart={focusStart}
                focusEnd={focusEnd}
                volumes={volumeSeries}
                volumeColor={VOLUME_COLOR}
                grid
              />
            </View>
          ) : prices.length <= 1 ? (
            <View style={styles.emptyFrame} pointerEvents="none">
              <Text style={[type.section, styles.empty]}>{banner ? '' : 'Chọn một mã để nghe'}</Text>
            </View>
          ) : null}
          {showCursor ? (
            <View pointerEvents="none" style={[styles.cursorLabel, { left: labelLeft }]}>
              <Text style={[type.monoSmall, styles.cursorLabelText]}>{cursorLabel}</Text>
            </View>
          ) : null}
          {prices.length > 1 ? (
            <View
              style={[styles.axis, volumeSeries ? { bottom: volumeStripFor(plotHeight, true) + 8 } : null]}
              pointerEvents="none"
            >
              {ticks.map((value, index) => (
                <Text key={`${value}-${index}`} style={[type.monoSmall, styles.axisText]}>
                  {value.toFixed(2)}
                </Text>
              ))}
            </View>
          ) : null}
          {banner ? (
            <View pointerEvents="none" style={styles.banner}>
              <Text style={[type.sans, styles.bannerText]}>{banner}</Text>
            </View>
          ) : null}
        </View>
      </View>
    </View>
  );
}

function tickLabels(prices: number[], visible: { min: number; max: number }): number[] {
  if (prices.length < 2) return [];
  const range = visible.max - visible.min;
  if (!Number.isFinite(range) || range <= 0) return [visible.max];
  return [visible.max, visible.max - range / 3, visible.min + range / 3, visible.min];
}

function visibleBounds(prices: number[], focusStart?: number, focusEnd?: number) {
  if (prices.length < 2) return { start: 0, end: 0, min: 0, max: 0 };
  const start = focusStart ?? 0;
  const end = focusEnd ?? prices.length - 1;
  const i0 = Math.max(0, Math.floor(start));
  const i1 = Math.min(prices.length - 1, Math.ceil(end));
  let min = prices[i0];
  let max = prices[i0];
  for (let index = i0; index <= i1; index += 1) {
    const value = prices[index];
    if (value < min) min = value;
    if (value > max) max = value;
  }
  return { start, end, min, max };
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    minHeight: 0,
  },
  header: {
    flexShrink: 0,
    paddingHorizontal: 24,
    paddingTop: 8,
    paddingBottom: 12,
  },
  title: {
    color: palette.text,
  },
  movement: {
    color: palette.textMuted,
    fontSize: 15,
    lineHeight: 21,
    marginTop: 2,
  },
  instruments: {
    color: palette.textFaint,
    fontSize: 13,
    marginTop: 2,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 8,
  },
  badge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
  },
  badgeText: {
    color: palette.textMuted,
  },
  meta: {
    color: palette.textFaint,
    flexShrink: 1,
  },
  chartArea: {
    flex: 1,
    minHeight: 0,
  },
  chartFrame: {
    flex: 1,
    minHeight: 0,
    width: '100%',
    position: 'relative',
  },
  emptyFrame: {
    ...StyleSheet.absoluteFill,
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 24,
    marginBottom: 16,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
  },
  empty: {
    color: palette.textFaint,
  },
  cursorLabel: {
    position: 'absolute',
    top: 6,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    backgroundColor: palette.playhead,
  },
  cursorLabelText: {
    color: palette.background,
  },
  banner: {
    position: 'absolute',
    left: 16,
    right: 16,
    bottom: 36,
    alignItems: 'center',
  },
  bannerText: {
    color: palette.text,
    fontWeight: '600',
    textAlign: 'center',
  },
  axis: {
    position: 'absolute',
    right: 12,
    top: 32,
    bottom: 12,
    justifyContent: 'space-between',
    alignItems: 'flex-end',
  },
  axisText: {
    color: palette.textFaint,
    fontSize: 11,
  },
});
