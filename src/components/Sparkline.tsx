import React, { useEffect, useId, useMemo, useRef } from 'react';
import { Animated, View } from 'react-native';
import Svg, {
  Circle,
  ClipPath,
  Defs,
  G,
  Line,
  LinearGradient,
  Path,
  Rect,
  Stop,
} from 'react-native-svg';
import { colors } from '../theme';

const UNPLAYED_OPACITY = 0.28;

export const VOLUME_STRIP = 30;

export function volumeStripFor(
  plotHeight: number,
  enabled: boolean,
  maxStrip: number = VOLUME_STRIP,
): number {
  if (!enabled || plotHeight <= 0) return 0;
  return Math.min(maxStrip, Math.max(0, plotHeight - 24));
}

/** One filled outline for the visible window. The baseline is the bottom of the plot. */
function volumeOutline(
  volumes: number[],
  width: number,
  height: number,
  strip: number,
  focusStart?: number,
  focusEnd?: number,
): string {
  if (volumes.length < 1 || width <= 0 || height <= 0 || strip <= 0) return '';
  const start = focusStart ?? 0;
  const end = focusEnd ?? volumes.length - 1;
  const span = Math.max(end - start, 1e-6);
  const i0 = Math.max(0, Math.floor(start));
  const i1 = Math.min(volumes.length - 1, Math.ceil(end));
  let peak = 0;
  for (let index = i0; index <= i1; index += 1) {
    const value = volumes[index] ?? 0;
    if (value > peak) peak = value;
  }
  if (peak <= 0) return '';
  const yAt = (value: number) => height - (Math.max(0, value) / peak) * strip;
  const samples: { x: number; y: number }[] = [];
  const slot = width / span;
  if (slot >= 1.6) {
    for (let index = i0; index <= i1; index += 1) {
      samples.push({ x: ((index - start) / span) * width, y: yAt(volumes[index] ?? 0) });
    }
  } else {
    const columns = Math.max(1, Math.ceil(width));
    const bins = new Array<number>(columns).fill(0);
    const seen = new Array<boolean>(columns).fill(false);
    for (let index = i0; index <= i1; index += 1) {
      const x = ((index - start) / span) * width;
      const bin = Math.min(columns - 1, Math.max(0, Math.floor(x)));
      const value = Math.max(0, volumes[index] ?? 0);
      if (!seen[bin] || value > bins[bin]) bins[bin] = value;
      seen[bin] = true;
    }
    for (let bin = 0; bin < columns; bin += 1) {
      if (!seen[bin]) continue;
      samples.push({ x: bin, y: yAt(bins[bin]) });
    }
  }
  if (samples.length === 0) return '';
  const first = samples[0];
  const last = samples[samples.length - 1];
  let path = `M${first.x.toFixed(2)},${height.toFixed(2)}`;
  for (const sample of samples) {
    path += `L${sample.x.toFixed(2)},${sample.y.toFixed(2)}`;
  }
  path += `L${last.x.toFixed(2)},${height.toFixed(2)}Z`;
  return path;
}

function WaveBars({
  peaks,
  width,
  height,
  color,
}: {
  peaks: number[];
  width: number;
  height: number;
  color: string;
}) {
  if (peaks.length < 2 || width <= 0 || height <= 0) return null;
  return (
    <>
      {peaks.map((peak, index) => {
        const slot = width / peaks.length;
        const bar = Math.max(2, Math.min(1, Math.max(0, peak)) * height * 0.72);
        return (
          <Rect
            key={index}
            x={index * slot + slot * 0.18}
            y={(height - bar) / 2}
            width={Math.max(1, slot * 0.64)}
            height={bar}
            fill={color}
            opacity={0.8}
          />
        );
      })}
    </>
  );
}

type Props = {
  data: number[];
  width?: number;
  height?: number;
  positive?: boolean;
  strokeWidth?: number;
  showFill?: boolean;
  /** Candle the recap playhead is on, in the same index space as `data`. */
  cursorIndex?: number | null;
  /** Dim the unplayed portion of the chart while preparing or playing audio. */
  dimUnplayed?: boolean;
  /** Inclusive index window. Omit both to draw the whole series. */
  focusStart?: number;
  focusEnd?: number;
  /** Overrides the green/red stroke. Omit to keep the terminal palette. */
  strokeColor?: string;
  /** Flat fill. Omit to keep the theme gradient when `showFill` is set. */
  flatFill?: string;
  /** Fade a flat fill from the line into the baseline instead of painting it solid. */
  fillFade?: boolean;
  /** Clip the fill to the played side of the playhead. Off by default. */
  playedFillOnly?: boolean;
  /** Playhead stroke and dot. Omit to keep the terminal accent. */
  playheadColor?: string;
  /** Breathe the playhead dot while the piece is audible. Off by default. */
  pulseCursor?: boolean;
  /** Peak amplitudes in 0..1, drawn across the same frame as the price line. */
  wave?: number[] | null;
  waveColor?: string;
  /** Traded volume, one value per price, drawn as a strip under the line. */
  volumes?: number[] | null;
  volumeColor?: string;
  /** Cap on the volume strip. The studio asks for 36, the terminal keeps 30. */
  volumeStripMax?: number;
  /** Colour for the volume already played. Omit to keep the terminal's one-colour strip. */
  volumePlayedColor?: string;
  /** Hairline on the price baseline, at the top edge of the volume strip. */
  baselineColor?: string;
  /** Quiet horizontal rules behind the line. Off by default: the terminal keeps its face. */
  grid?: boolean;
  /** Soft halo under the stroke. Off by default. */
  glow?: boolean;
  gridColor?: string;
};

export function Sparkline({
  data,
  width = 72,
  height = 36,
  positive = true,
  strokeWidth = 1.5,
  showFill = false,
  cursorIndex = null,
  dimUnplayed = false,
  focusStart,
  focusEnd,
  strokeColor,
  flatFill,
  fillFade = false,
  playedFillOnly = false,
  playheadColor,
  pulseCursor = false,
  wave = null,
  waveColor = '#E040A0',
  volumes = null,
  volumeColor = 'rgba(62, 224, 224, 0.45)',
  volumeStripMax = VOLUME_STRIP,
  volumePlayedColor,
  baselineColor,
  grid = false,
  glow = false,
  gridColor = 'rgba(244, 241, 234, 0.05)',
}: Props) {
  const volumeStrip = volumeStripFor(
    height,
    Boolean(volumes && volumes.length > 0 && volumes.length === data.length),
    volumeStripMax,
  );
  const { line, fill, cursor, volume } = useMemo(() => {
    const outline =
      volumeStrip > 0 && volumes
        ? volumeOutline(volumes, width, height, volumeStrip, focusStart, focusEnd)
        : '';
    if (data.length < 2) {
      return { line: '', fill: '', cursor: null as { x: number; y: number } | null, volume: outline };
    }

    const start = focusStart ?? 0;
    const end = focusEnd ?? data.length - 1;
    const span = Math.max(end - start, 1e-6);
    const i0 = Math.max(0, Math.floor(start));
    const i1 = Math.min(data.length - 1, Math.ceil(end));
    let min = data[i0];
    let max = data[i0];
    for (let index = i0; index <= i1; index += 1) {
      const value = data[index];
      if (value < min) min = value;
      if (value > max) max = value;
    }
    const range = max - min || 1;
    const padY = 2;
    const usableH = Math.max(1, height - padY * 2 - volumeStrip);

    const points: { x: number; y: number }[] = [];
    for (let index = i0; index <= i1; index += 1) {
      const value = data[index];
      points.push({
        x: ((index - start) / span) * width,
        y: padY + usableH - ((value - min) / range) * usableH,
      });
    }

    const linePath = points
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
      .join(' ');

    const priceBottom = height - volumeStrip;
    const fillPath = `${linePath} L${width},${priceBottom} L0,${priceBottom} Z`;
    const cursor =
      cursorIndex == null
        ? null
        : {
            x: ((cursorIndex - start) / span) * width,
            y:
              padY +
              usableH -
              ((data[Math.min(data.length - 1, Math.max(0, cursorIndex))] - min) / range) * usableH,
          };

    return { line: linePath, fill: fillPath, cursor, volume: outline };
  }, [cursorIndex, data, focusEnd, focusStart, height, volumeStrip, volumes, width]);

  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const stroke = strokeColor ?? (positive ? colors.positive : colors.negative);
  const playhead = playheadColor ?? colors.accent;
  const gradId = `sparkGrad-${uid}`;
  const fadeId = `sparkFade-${uid}`;
  const playedClipId = `sparkPlayed-${uid}`;
  const unplayedClipId = `sparkUnplayed-${uid}`;
  const splitX = cursor ? Math.min(width, Math.max(0, cursor.x)) : 0;
  const fillPaint = flatFill ? (fillFade ? `url(#${fadeId})` : flatFill) : `url(#${gradId})`;
  const waveBars =
    wave && wave.length > 1 ? (
      <WaveBars peaks={wave} width={width} height={height} color={waveColor} />
    ) : null;
  // A two-tone volume strip needs its own layer outside the played/unplayed
  // price groups: the base stays quiet while only the played part brightens.
  const layeredVolume = Boolean(volumePlayedColor && volume && volumeStrip > 0);
  const volumeShape = volume && !layeredVolume ? <Path d={volume} fill={volumeColor} /> : null;

  const pulse = useRef(new Animated.Value(1)).current;
  const pulsing = pulseCursor && cursor != null;
  useEffect(() => {
    pulse.stopAnimation();
    if (!pulsing) {
      pulse.setValue(1);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 0.35,
          duration: 600,
          useNativeDriver: false,
        }),
        Animated.timing(pulse, {
          toValue: 1,
          duration: 600,
          useNativeDriver: false,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse, pulsing]);

  return (
    <View style={{ width, height, overflow: 'hidden' }}>
      <Svg width={width} height={height}>
        <Defs>
          {showFill && !flatFill ? (
            <LinearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <Stop
                offset="0%"
                stopColor={stroke}
                stopOpacity={0.28}
              />
              <Stop offset="100%" stopColor={stroke} stopOpacity={0} />
            </LinearGradient>
          ) : null}
          {showFill && flatFill && fillFade ? (
            <LinearGradient id={fadeId} x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0%" stopColor={flatFill} stopOpacity={1} />
              <Stop offset="100%" stopColor={flatFill} stopOpacity={0} />
            </LinearGradient>
          ) : null}
          {dimUnplayed && cursor && (
            <>
              <ClipPath id={playedClipId}>
                <Rect x={0} y={0} width={splitX} height={height} />
              </ClipPath>
              <ClipPath id={unplayedClipId}>
                <Rect
                  x={splitX}
                  y={0}
                  width={Math.max(0, width - splitX)}
                  height={height}
                />
              </ClipPath>
            </>
          )}
        </Defs>

        {grid ? (
          <G>
            {[0, 1 / 3, 2 / 3, 1].map((t) => (
              <Line
                key={t}
                x1={0}
                y1={(height - volumeStrip) * t}
                x2={width}
                y2={(height - volumeStrip) * t}
                stroke={gridColor}
                strokeWidth={1}
              />
            ))}
          </G>
        ) : null}

        {baselineColor && volumeStrip > 0 ? (
          <Line
            x1={0}
            y1={height - volumeStrip}
            x2={width}
            y2={height - volumeStrip}
            stroke={baselineColor}
            strokeWidth={1}
          />
        ) : null}

        {layeredVolume && volume ? (
          <>
            <Path d={volume} fill={volumeColor} />
            {dimUnplayed && cursor ? (
              <G clipPath={`url(#${playedClipId})`}>
                <Path d={volume} fill={volumePlayedColor} />
              </G>
            ) : null}
          </>
        ) : null}

        {dimUnplayed && cursor ? (
          <>
            <G clipPath={`url(#${unplayedClipId})`} opacity={UNPLAYED_OPACITY}>
              {volumeShape}
              {waveBars}
              {showFill && fill && !playedFillOnly ? (
                <Path d={fill} fill={fillPaint} />
              ) : null}
              {glow && line ? (
                <Path
                  d={line}
                  stroke={stroke}
                  strokeWidth={strokeWidth * 3}
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity={0.16}
                />
              ) : null}
              {line ? (
                <Path
                  d={line}
                  stroke={stroke}
                  strokeWidth={strokeWidth}
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ) : null}
            </G>
            <G clipPath={`url(#${playedClipId})`}>
              {volumeShape}
              {waveBars}
              {showFill && fill ? <Path d={fill} fill={fillPaint} /> : null}
              {glow && line ? (
                <Path
                  d={line}
                  stroke={stroke}
                  strokeWidth={strokeWidth * 3}
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity={0.16}
                />
              ) : null}
              {line ? (
                <Path
                  d={line}
                  stroke={stroke}
                  strokeWidth={strokeWidth}
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ) : null}
            </G>
          </>
        ) : (
          <G opacity={dimUnplayed ? UNPLAYED_OPACITY : 1}>
            {volumeShape}
            {waveBars}
            {showFill && fill ? <Path d={fill} fill={fillPaint} /> : null}
            {glow && line ? (
              <Path
                d={line}
                stroke={stroke}
                strokeWidth={strokeWidth * 3}
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={0.16}
              />
            ) : null}
            {line ? (
              <Path
                d={line}
                stroke={stroke}
                strokeWidth={strokeWidth}
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ) : null}
          </G>
        )}

        {cursor && cursor.x >= -2 && cursor.x <= width + 2 ? (
          <>
            <Line
              x1={cursor.x}
              y1={0}
              x2={cursor.x}
              y2={height}
              stroke={playhead}
              strokeWidth={1.5}
            />
            <Circle cx={cursor.x} cy={cursor.y} r={4.5} fill={playhead} />
          </>
        ) : null}
      </Svg>
      {pulsing && cursor ? (
        <Animated.View
          pointerEvents="none"
          style={{
            position: 'absolute',
            left: cursor.x - 4.5,
            top: cursor.y - 4.5,
            width: 9,
            height: 9,
            borderRadius: 5,
            backgroundColor: playhead,
            opacity: pulse,
            transform: [
              { scale: pulse.interpolate({ inputRange: [0.35, 1], outputRange: [1.7, 1] }) },
            ],
          }}
        />
      ) : null}
    </View>
  );
}
