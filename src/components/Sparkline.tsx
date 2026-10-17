import React, { useMemo } from 'react';
import { View } from 'react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop } from 'react-native-svg';
import { colors } from '../theme';

type Props = {
  data: number[];
  width?: number;
  height?: number;
  positive?: boolean;
  strokeWidth?: number;
  showFill?: boolean;
  /** Candle the recap playhead is on. */
  cursorIndex?: number | null;
};

export function Sparkline({
  data,
  width = 72,
  height = 36,
  positive = true,
  strokeWidth = 1.5,
  showFill = false,
  cursorIndex = null,
}: Props) {
  const { line, fill, cursor } = useMemo(() => {
    if (data.length < 2) {
      return { line: '', fill: '', cursor: null as { x: number; y: number } | null };
    }

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const padY = 2;
    const usableH = height - padY * 2;

    const points = data.map((value, index) => {
      const x = (index / (data.length - 1)) * width;
      const y = padY + usableH - ((value - min) / range) * usableH;
      return { x, y };
    });

    const linePath = points
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
      .join(' ');

    const fillPath = `${linePath} L${width},${height} L0,${height} Z`;
    const cursor =
      cursorIndex == null
        ? null
        : points[Math.min(points.length - 1, Math.max(0, cursorIndex))] ?? null;

    return { line: linePath, fill: fillPath, cursor };
  }, [cursorIndex, data, width, height]);

  const stroke = positive ? colors.positive : colors.negative;
  const gradId = positive ? 'sparkPos' : 'sparkNeg';

  return (
    <View style={{ width, height }}>
      <Svg width={width} height={height}>
        {showFill && (
          <Defs>
            <LinearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <Stop
                offset="0%"
                stopColor={stroke}
                stopOpacity={0.28}
              />
              <Stop offset="100%" stopColor={stroke} stopOpacity={0} />
            </LinearGradient>
          </Defs>
        )}
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
        {cursor ? (
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
