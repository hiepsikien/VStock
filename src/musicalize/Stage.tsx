import React, { useEffect, useRef, useState } from 'react';
import { Animated, Easing, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { Sparkline, volumeStripFor } from '../components/Sparkline';
import type { PieceProgram } from '../sonify/program';
import { useChartEntrance, usePulse, useReducedMotion } from './motion';
import { palette, WIDE_BREAKPOINT } from './palette';
import { clamp01 } from './seek';
import { type } from './type';

/** The studio strip is 36px tall; the stock terminal keeps its 30. */
const VOLUME_STRIP_MAX = 36;
const VOLUME_COLOR = 'rgba(62, 224, 224, 0.22)';
const VOLUME_PLAYED = 'rgba(62, 224, 224, 0.42)';
const SHIMMER_WIDTH = 220;

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
  /** The server is writing the score: shimmer the chart and say so. */
  composing?: boolean;
  /** Between two movements: dim the chart and count the rest down. */
  resting?: boolean;
  restRemaining?: number;
  restTotal?: number;
  /** Live room: pulsing dot and `TRỰC TIẾP` in the chart corner. */
  live?: boolean;
  /** Audible: the playhead dot breathes. */
  playing?: boolean;
  /** Changing this string fades the chart in: symbol, span or genre. */
  chartKey?: string;
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
  composing = false,
  resting = false,
  restRemaining = 0,
  restTotal = 0,
  live = false,
  playing = false,
  chartKey = '',
}: Props) {
  const { width } = useWindowDimensions();
  const reduced = useReducedMotion();
  const displayStyle = width >= WIDE_BREAKPOINT ? type.display : type.displayNarrow;
  const [plot, setPlot] = useState({ width: 0, height: 0 });
  const chartWidth = Math.max(1, plot.width);
  const plotHeight = Math.max(1, plot.height);
  const volumeSeries = volumes && volumes.length > 0 && volumes.length === prices.length ? volumes : null;
  const volumeStrip = volumeSeries ? volumeStripFor(plotHeight, true, VOLUME_STRIP_MAX) : 0;
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
  const entrance = useChartEntrance(chartKey);
  const livePulse = usePulse(live, 1600, 0.25);

  const shimmer = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    shimmer.stopAnimation();
    if (!composing || reduced) {
      shimmer.setValue(0);
      return;
    }
    shimmer.setValue(0);
    const loop = Animated.loop(
      Animated.timing(shimmer, {
        toValue: 1,
        duration: 1200,
        easing: Easing.linear,
        useNativeDriver: false,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [composing, reduced, shimmer]);

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
          <Animated.View
            pointerEvents="none"
            style={[styles.chartLayer, entrance, resting && styles.chartResting]}
          >
            {prices.length > 1 && plot.width > 0 && plot.height > 0 ? (
              <Sparkline
                data={prices}
                width={plot.width}
                height={plot.height}
                positive
                strokeWidth={2.5}
                showFill
                fillFade
                playedFillOnly
                flatFill={palette.dataFill}
                strokeColor={palette.data}
                playheadColor={palette.playhead}
                cursorIndex={cursorIndex}
                dimUnplayed={dimUnplayed}
                focusStart={focusStart}
                focusEnd={focusEnd}
                volumes={volumeSeries}
                volumeColor={VOLUME_COLOR}
                volumePlayedColor={VOLUME_PLAYED}
                volumeStripMax={VOLUME_STRIP_MAX}
                baselineColor={palette.hairline}
                pulseCursor={playing && !reduced}
                grid
                glow
              />
            ) : prices.length <= 1 ? (
              <View style={styles.emptyFrame}>
                <Text style={[type.section, styles.empty]}>
                  {banner ? '' : 'Chọn một mã để nghe'}
                </Text>
              </View>
            ) : null}

            {showCursor ? (
              <View style={[styles.cursorLabel, { left: labelLeft }]}>
                <Text style={[type.monoSmall, styles.cursorLabelText]}>{cursorLabel}</Text>
              </View>
            ) : null}

            {prices.length > 1 ? (
              <View style={[styles.axis, volumeSeries ? { bottom: volumeStrip + 8 } : null]}>
                {ticks.map((value, index) => (
                  <Text key={`${value}-${index}`} style={[type.monoSmall, styles.axisText]}>
                    {value.toFixed(2)}
                  </Text>
                ))}
              </View>
            ) : null}

            {prices.length > 1 && volumeSeries ? (
              <Text style={[type.monoSmall, styles.volumeLabel, { bottom: volumeStrip - 14 }]}>
                KL
              </Text>
            ) : null}
          </Animated.View>

          {composing && !reduced ? (
            <Animated.View
              pointerEvents="none"
              style={[
                styles.shimmer,
                {
                  transform: [
                    {
                      translateX: shimmer.interpolate({
                        inputRange: [0, 1],
                        outputRange: [-SHIMMER_WIDTH, Math.max(SHIMMER_WIDTH, plot.width)],
                      }),
                    },
                  ],
                },
              ]}
            />
          ) : null}

          {composing ? (
            <View pointerEvents="none" style={styles.composingLabel}>
              <Text style={[type.section, styles.composingText]}>Đang soạn</Text>
            </View>
          ) : null}

          {resting ? (
            <View pointerEvents="none" style={styles.rest}>
              <RestArc remaining={restRemaining} total={restTotal} />
              <View style={styles.restRow}>
                <Text style={[type.section, styles.restLabel]}>Nghỉ</Text>
                <Text style={[type.mono, styles.restClock]}>
                  {clockForRest(restRemaining)}
                </Text>
              </View>
            </View>
          ) : null}

          {live ? (
            <View pointerEvents="none" style={styles.live}>
              <Animated.View style={[styles.liveDot, { opacity: livePulse }]} />
              <Text style={[type.section, styles.liveText]}>Trực tiếp</Text>
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

const ARC_SIZE = 24;
const ARC_RADIUS = 9.5;
const ARC_CIRCUMFERENCE = 2 * Math.PI * ARC_RADIUS;

/** The rest countdown: an amber ring that drains as the silence runs out. */
function RestArc({ remaining, total }: { remaining: number; total: number }) {
  const fraction = total > 0 ? clamp01(remaining / total) : 0;
  return (
    <Svg width={ARC_SIZE} height={ARC_SIZE}>
      <Circle
        cx={ARC_SIZE / 2}
        cy={ARC_SIZE / 2}
        r={ARC_RADIUS}
        fill="none"
        stroke={palette.hairlineStrong}
        strokeWidth={2}
      />
      {fraction > 0 ? (
        <Circle
          cx={ARC_SIZE / 2}
          cy={ARC_SIZE / 2}
          r={ARC_RADIUS}
          fill="none"
          stroke={palette.playhead}
          strokeWidth={2}
          strokeLinecap="round"
          strokeDasharray={`${ARC_CIRCUMFERENCE} ${ARC_CIRCUMFERENCE}`}
          strokeDashoffset={ARC_CIRCUMFERENCE * (1 - fraction)}
          rotation={-90}
          originX={ARC_SIZE / 2}
          originY={ARC_SIZE / 2}
        />
      ) : null}
    </Svg>
  );
}

function clockForRest(seconds: number): string {
  const safe = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  const whole = Math.ceil(safe);
  return `${Math.floor(whole / 60)}:${(whole % 60).toString().padStart(2, '0')}`;
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
  chartLayer: {
    ...StyleSheet.absoluteFill,
  },
  chartResting: {
    opacity: 0.4,
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
  shimmer: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: SHIMMER_WIDTH,
    backgroundColor: 'rgba(244, 241, 234, 0.05)',
  },
  composingLabel: {
    position: 'absolute',
    left: 4,
    bottom: 6,
  },
  composingText: {
    color: palette.textMuted,
  },
  rest: {
    ...StyleSheet.absoluteFill,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  restRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 6,
  },
  restLabel: {
    color: palette.playhead,
  },
  restClock: {
    color: palette.playhead,
  },
  live: {
    position: 'absolute',
    top: 4,
    right: 4,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: palette.sound,
  },
  liveText: {
    color: palette.text,
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
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairline,
    borderRadius: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    overflow: 'hidden',
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
  volumeLabel: {
    position: 'absolute',
    left: 4,
    color: palette.textFaint,
    fontSize: 10,
    lineHeight: 14,
  },
});
