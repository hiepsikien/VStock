import React, { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Sparkline, VOLUME_STRIP } from '../components/Sparkline';
import type { PieceProgram } from '../sonify/program';
import { palette } from './palette';
import { clamp01 } from './seek';

const CHART_HEIGHT = 248;
const VOLUME_COLOR = 'rgba(62, 224, 224, 0.45)';

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
  banner = null,
  seekable = false,
  onSeekRatio,
}: Props) {
  const [width, setWidth] = useState(0);
  const chartWidth = Math.max(1, width);
  const volumeSeries = volumes && volumes.length > 0 && volumes.length === prices.length ? volumes : null;
  const visible = visibleBounds(prices, focusStart, focusEnd);
  const labelLeft =
    cursorIndex == null || prices.length < 2
      ? 8
      : Math.min(
          chartWidth - 58,
          Math.max(8, ((cursorIndex - visible.start) / Math.max(visible.end - visible.start, 1e-6)) * chartWidth - 22),
        );
  const showCursor =
    cursorLabel != null &&
    cursorIndex != null &&
    cursorIndex >= visible.start - 0.01 &&
    cursorIndex <= visible.end + 0.01;

  const seekAt = (locationX: number) => {
    if (!seekable || !onSeekRatio || chartWidth <= 0) return;
    onSeekRatio(clamp01(locationX / chartWidth));
  };

  return (
    <View style={styles.wrap}>
      {program ? (
        <View pointerEvents="none" style={styles.program}>
          <Text style={styles.programTitle} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.6}>
            {program.title}
          </Text>
          {program.movement ? (
            <Text style={styles.programLine} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>
              {program.movement}
            </Text>
          ) : null}
          {program.phase !== 'playing' && program.instruments ? (
            <Text style={styles.programLine} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>
              {program.instruments}
            </Text>
          ) : null}
        </View>
      ) : prices.length > 1 && identity ? (
        <View pointerEvents="none" style={styles.program}>
          <Text style={styles.programTitle} numberOfLines={2}>
            {identity}
          </Text>
        </View>
      ) : null}
      <View
        style={styles.chartArea}
        onLayout={(event) => {
          const next = event.nativeEvent.layout.width;
          setWidth((current) => (current === next ? current : next));
        }}
        onStartShouldSetResponder={() => seekable}
        onMoveShouldSetResponder={() => seekable}
        onResponderTerminationRequest={() => false}
        onResponderGrant={(event) => seekAt(event.nativeEvent.locationX)}
        onResponderMove={(event) => seekAt(event.nativeEvent.locationX)}
      >
        <View style={styles.chartFrame}>
          {prices.length > 1 && width > 0 ? (
            <View pointerEvents="none">
              <Sparkline
                data={prices}
                width={chartWidth}
                height={CHART_HEIGHT}
                positive
                strokeWidth={2.25}
                showFill
                flatFill="rgba(62, 224, 224, 0.16)"
                strokeColor={palette.data}
                playheadColor={palette.playhead}
                cursorIndex={cursorIndex}
                dimUnplayed={dimUnplayed}
                focusStart={focusStart}
                focusEnd={focusEnd}
                volumes={volumeSeries}
                volumeColor={VOLUME_COLOR}
              />
            </View>
          ) : (
            <Text style={styles.empty}>{banner ? '' : 'Sân khấu'}</Text>
          )}
          {showCursor ? (
            <View pointerEvents="none" style={[styles.cursorLabel, { left: labelLeft }]}>
              <Text style={styles.cursorLabelText}>{cursorLabel}</Text>
            </View>
          ) : null}
          {banner ? (
            <View pointerEvents="none" style={styles.banner}>
              <Text style={styles.bannerText}>{banner}</Text>
            </View>
          ) : null}
          {prices.length > 1 ? (
            <View
              style={[styles.axis, volumeSeries ? { bottom: VOLUME_STRIP + 4 } : null]}
              pointerEvents="none"
            >
              <Text style={styles.axisText}>{visible.max.toFixed(2)}</Text>
              <Text style={styles.axisText}>{visible.min.toFixed(2)}</Text>
            </View>
          ) : null}
        </View>
        {!program && identity && prices.length <= 1 ? (
          <View pointerEvents="none" style={styles.identity}>
            <Text style={styles.identityText} numberOfLines={2}>
              {identity}
            </Text>
          </View>
        ) : null}
      </View>
    </View>
  );
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
    minHeight: CHART_HEIGHT + 28,
    position: 'relative',
  },
  program: {
    paddingHorizontal: 16,
    paddingTop: 2,
    paddingBottom: 8,
    alignItems: 'center',
  },
  programTitle: {
    color: palette.text,
    fontSize: 22,
    fontWeight: '600',
    textAlign: 'center',
    width: '100%',
  },
  programLine: {
    color: palette.textMuted,
    fontSize: 15,
    textAlign: 'center',
    marginTop: 2,
    width: '100%',
  },
  chartArea: {
    flex: 1,
    minHeight: CHART_HEIGHT,
    justifyContent: 'flex-start',
    position: 'relative',
  },
  chartFrame: {
    height: CHART_HEIGHT,
    width: '100%',
    position: 'relative',
    justifyContent: 'center',
  },
  empty: {
    color: palette.textMuted,
    fontSize: 15,
    textAlign: 'center',
  },
  identity: {
    position: 'absolute',
    left: 24,
    right: 24,
    top: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  identityText: {
    color: palette.text,
    fontSize: 22,
    fontWeight: '600',
    textAlign: 'center',
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
    fontSize: 13,
    fontVariant: ['tabular-nums'],
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
    fontSize: 15,
    fontWeight: '600',
    textAlign: 'center',
  },
  axis: {
    position: 'absolute',
    right: 12,
    top: 8,
    bottom: 8,
    justifyContent: 'space-between',
    alignItems: 'flex-end',
  },
  axisText: {
    color: palette.textMuted,
    fontSize: 13,
    fontVariant: ['tabular-nums'],
  },
});
