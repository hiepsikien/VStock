import React, { useId, useState } from 'react';
import { View } from 'react-native';
import Svg, {
  Circle,
  Defs,
  Line,
  LinearGradient,
  Path,
  Stop,
} from 'react-native-svg';
import { palette } from './palette';

type Props = {
  levels: [number, number, number];
  height?: number;
};

/**
 * A parameter-derived low/mid/high preview. It is not an analyser: the
 * caller labels it as an estimate so nobody mistakes it for measured audio.
 */
export function TuningSpectrum({ levels, height = 76 }: Props) {
  const [width, setWidth] = useState(300);
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const padding = 9;
  const xs = [width * 0.12, width * 0.5, width * 0.88];
  const points = levels.map((level, index) => ({
    x: xs[index],
    y: padding + (1 - Math.max(0, Math.min(1, level))) * (height - padding * 2),
  }));
  const [first, mid, last] = points;
  const line = [
    `M${first.x.toFixed(2)},${first.y.toFixed(2)}`,
    `C${((first.x + mid.x) / 2).toFixed(2)},${first.y.toFixed(2)}`,
    `${((first.x + mid.x) / 2).toFixed(2)},${mid.y.toFixed(2)}`,
    `${mid.x.toFixed(2)},${mid.y.toFixed(2)}`,
    `C${((mid.x + last.x) / 2).toFixed(2)},${mid.y.toFixed(2)}`,
    `${((mid.x + last.x) / 2).toFixed(2)},${last.y.toFixed(2)}`,
    `${last.x.toFixed(2)},${last.y.toFixed(2)}`,
  ].join(' ');
  const area = `${line} L${last.x.toFixed(2)},${height} L${first.x.toFixed(2)},${height} Z`;

  return (
    <View
      style={{ width: '100%', height }}
      onLayout={(event) => setWidth(Math.max(80, event.nativeEvent.layout.width))}
      pointerEvents="none"
    >
      <Svg width={width} height={height}>
        <Defs>
          <LinearGradient id={`spectrum-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0%" stopColor={palette.sound} stopOpacity={0.3} />
            <Stop offset="100%" stopColor={palette.sound} stopOpacity={0.02} />
          </LinearGradient>
        </Defs>
        <Line
          x1={0}
          y1={height - 1}
          x2={width}
          y2={height - 1}
          stroke={palette.hairlineStrong}
          strokeWidth={1}
        />
        {points.map((point) => (
          <Line
            key={`guide-${point.x}`}
            x1={point.x}
            y1={padding}
            x2={point.x}
            y2={height - padding}
            stroke={palette.hairline}
            strokeWidth={1}
            strokeDasharray={[2, 4]}
          />
        ))}
        <Path d={area} fill={`url(#spectrum-${uid})`} />
        <Path d={line} fill="none" stroke={palette.sound} strokeWidth={1.8} />
        {points.map((point, index) => (
          <Circle
            key={`dot-${index}`}
            cx={point.x}
            cy={point.y}
            r={2.6}
            fill={palette.sound}
          />
        ))}
      </Svg>
    </View>
  );
}
