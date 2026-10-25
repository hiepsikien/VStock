import React, { useId, useMemo } from 'react';
import { View } from 'react-native';
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
}: Props) {
  const { line, fill, cursor } = useMemo(() => {
    if (data.length < 2) {
      return { line: '', fill: '', cursor: null as { x: number; y: number } | null };
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
    const usableH = height - padY * 2;

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

    const fillPath = `${linePath} L${width},${height} L0,${height} Z`;
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

    return { line: linePath, fill: fillPath, cursor };
  }, [cursorIndex, data, focusEnd, focusStart, width, height]);

  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const stroke = positive ? colors.positive : colors.negative;
  const gradId = `sparkGrad-${uid}`;
  const playedClipId = `sparkPlayed-${uid}`;
  const unplayedClipId = `sparkUnplayed-${uid}`;
  const splitX = cursor ? Math.min(width, Math.max(0, cursor.x)) : 0;

  return (
    <View style={{ width, height, overflow: 'hidden' }}>
      <Svg width={width} height={height}>
        <Defs>
          {showFill && (
            <LinearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <Stop
                offset="0%"
                stopColor={stroke}
                stopOpacity={0.28}
              />
              <Stop offset="100%" stopColor={stroke} stopOpacity={0} />
            </LinearGradient>
          )}
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

        {dimUnplayed && cursor ? (
          <>
            <G clipPath={`url(#${unplayedClipId})`} opacity={UNPLAYED_OPACITY}>
              {showFill && fill ? (
                <Path d={fill} fill={`url(#${gradId})`} />
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
              {showFill && fill ? (
                <Path d={fill} fill={`url(#${gradId})`} />
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
            {showFill && fill ? (
              <Path d={fill} fill={`url(#${gradId})`} />
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
              stroke={colors.accent}
              strokeWidth={1.5}
            />
            <Circle cx={cursor.x} cy={cursor.y} r={4.5} fill={colors.accent} />
          </>
        ) : null}
      </Svg>
    </View>
  );
}
