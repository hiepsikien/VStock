import React, { useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Rect } from 'react-native-svg';
import { palette } from './palette';
import { clamp01 } from './seek';
import { type } from './type';

type DragProps = {
  progress: number;
  onRatio: (ratio: number) => void;
};

function useRatioDrag(onRatio: (ratio: number) => void) {
  const width = useRef(0);
  const seek = (locationX: number) => {
    if (width.current <= 0) return;
    onRatio(clamp01(locationX / width.current));
  };
  return {
    onLayout: (widthPx: number) => {
      width.current = widthPx;
    },
    seek,
  };
}

type Props = DragProps & {
  label: string;
  /** Audio peaks for a single-session file. The work bar has none. */
  peaks?: number[] | null;
};

const BARS = 36;
const HIT = 44;

/**
 * One timeline for both the session file and the whole work. Stronger ratio
 * placement lives in `ReplayRoom`, which owns the movement map.
 */
export function Timeline({ label, progress, peaks = null, onRatio }: Props) {
  const [width, setWidth] = useState(0);
  const drag = useRatioDrag(onRatio);
  const played = clamp01(progress);
  const bars = peaks && peaks.length ? peaks : null;

  return (
    <View style={styles.block}>
      <View style={styles.captionRow}>
        <Text style={[type.section, styles.caption]}>{label}</Text>
      </View>
      <View
        style={styles.hit}
        onLayout={(event) => {
          const next = event.nativeEvent.layout.width;
          drag.onLayout(next);
          setWidth((current) => (current === next ? current : next));
        }}
        onStartShouldSetResponder={() => true}
        onMoveShouldSetResponder={() => true}
        onResponderTerminationRequest={() => false}
        onResponderGrant={(event) => drag.seek(event.nativeEvent.locationX)}
        onResponderMove={(event) => drag.seek(event.nativeEvent.locationX)}
        accessibilityRole="adjustable"
        accessibilityLabel={label}
        accessibilityValue={{ min: 0, max: 100, now: Math.round(played * 100) }}
      >
        {bars ? (
          <View pointerEvents="none" style={styles.bars}>
            <Svg width={Math.max(width, 1)} height={BARS}>
              {bars.map((peak, index) => {
                const slot = Math.max(width, 1) / bars.length;
                const height = Math.max(2, Math.min(1, peak) * (BARS - 4));
                const passed = (index + 0.5) / bars.length <= played;
                return (
                  <Rect
                    key={index}
                    x={index * slot + slot * 0.15}
                    y={(BARS - height) / 2}
                    width={Math.max(1, slot * 0.7)}
                    height={height}
                    fill={passed ? palette.sound : palette.track}
                  />
                );
              })}
            </Svg>
          </View>
        ) : null}
        <View pointerEvents="none" style={styles.track}>
          <View style={[styles.fill, { width: `${played * 100}%` }]} />
        </View>
        <View pointerEvents="none" style={[styles.knob, { left: `${played * 100}%` }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  block: {
    marginTop: 4,
  },
  captionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  caption: {
    color: palette.textFaint,
  },
  hit: {
    height: HIT,
    justifyContent: 'center',
  },
  bars: {
    ...StyleSheet.absoluteFill,
    alignItems: 'center',
    justifyContent: 'center',
  },
  track: {
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.track,
    overflow: 'hidden',
  },
  fill: {
    height: 4,
    backgroundColor: palette.sound,
  },
  knob: {
    position: 'absolute',
    width: 10,
    height: 10,
    marginLeft: -5,
    borderRadius: 5,
    backgroundColor: palette.playhead,
  },
});
