import React, { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { PieceTitle } from '../components/PieceTitle';
import { Sparkline } from '../components/Sparkline';
import { playingLines, type PieceProgram } from '../sonify/program';
import { palette } from './palette';
import { clamp01 } from './seek';

const CHART_HEIGHT = 248;

type Props = {
  prices: number[];
  cursorIndex?: number | null;
  cursorLabel?: string | null;
  dimUnplayed?: boolean;
  focusStart?: number;
  focusEnd?: number;
  program?: PieceProgram | null;
  wave?: number[] | null;
  identity?: string | null;
  banner?: string | null;
  seekable?: boolean;
  onSeekRatio?: (ratio: number) => void;
};

export function Stage({
  prices,
  cursorIndex = null,
  cursorLabel = null,
  dimUnplayed = false,
  focusStart,
  focusEnd,
  program = null,
  wave = null,
  identity = null,
  banner = null,
  seekable = false,
  onSeekRatio,
}: Props) {
  const [width, setWidth] = useState(0);
  const chartWidth = Math.max(1, width);
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
              wave={wave}
              waveColor={palette.sound}
              cursorIndex={cursorIndex}
              dimUnplayed={dimUnplayed}
              focusStart={focusStart}
              focusEnd={focusEnd}
            />
          </View>
        ) : (
          <Text style={styles.empty}>{banner ? '' : 'Sân khấu'}</Text>
        )}
        {program && program.phase !== 'playing' ? (
          <PieceTitle
            title={program.title}
            instruments={program.instruments}
            movement={program.movement}
            titleColor={palette.text}
            lineColor={palette.textMuted}
          />
        ) : null}
        {!program && identity ? (
          <View pointerEvents="none" style={styles.identity}>
            <Text style={styles.identityText} numberOfLines={2}>
              {identity}
            </Text>
          </View>
        ) : null}
        {program?.phase === 'playing' ? (
          <View pointerEvents="none" style={styles.nowPlaying}>
            {playingLines(program.title, program.movement).map((line, lineIndex) => (
              <Text key={`${lineIndex}-${line}`} style={styles.nowPlayingText} numberOfLines={1}>
                {line}
              </Text>
            ))}
          </View>
        ) : null}
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
      </View>
      {prices.length > 1 ? (
        <View style={styles.axis} pointerEvents="none">
          <Text style={styles.axisText}>{visible.max.toFixed(2)}</Text>
          <Text style={styles.axisText}>{visible.min.toFixed(2)}</Text>
        </View>
      ) : null}
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
  chartArea: {
    flex: 1,
    minHeight: CHART_HEIGHT,
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
  nowPlaying: {
    position: 'absolute',
    left: 10,
    right: 72,
    bottom: 8,
  },
  nowPlayingText: {
    color: palette.text,
    fontSize: 13,
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
