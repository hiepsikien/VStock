import React, { useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Rect } from 'react-native-svg';
import { palette } from './palette';
import { clamp01 } from './seek';
import { formatClock } from './labels';

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

export function PeakScrubber({
  peaks,
  progress,
  time,
  duration,
  onRatio,
}: DragProps & { peaks: number[]; time: number; duration: number }) {
  const [width, setWidth] = useState(0);
  const drag = useRatioDrag(onRatio);
  const bars = peaks.length ? peaks : [0.2];
  return (
    <View style={styles.block}>
      <View style={styles.captionRow}>
        <Text style={styles.caption}>Phiên</Text>
        <Text style={styles.clock}>
          {formatClock(time)} / {formatClock(duration)}
        </Text>
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
        accessibilityLabel="Thanh thời gian phiên"
      >
        <Svg width={Math.max(width, 1)} height={46}>
          {bars.map((peak, index) => {
            const slot = Math.max(width, 1) / bars.length;
            const height = Math.max(2, Math.min(1, peak) * 40);
            const played = (index + 0.5) / bars.length <= progress;
            return (
              <Rect
                key={index}
                x={index * slot + slot * 0.15}
                y={(46 - height) / 2}
                width={Math.max(1, slot * 0.7)}
                height={height}
                fill={played ? palette.sound : palette.track}
              />
            );
          })}
        </Svg>
      </View>
    </View>
  );
}

export function FlatScrubber({
  label,
  progress,
  time,
  duration,
  onRatio,
}: DragProps & { label: string; time: number; duration: number }) {
  const drag = useRatioDrag(onRatio);
  const played = Math.min(1, Math.max(0, progress));
  return (
    <View style={styles.block}>
      <View style={styles.captionRow}>
        <Text style={styles.caption}>{label}</Text>
        <Text style={styles.clock}>
          {formatClock(time)} / {formatClock(duration)}
        </Text>
      </View>
      <View
        style={styles.flatHit}
        onLayout={(event) => drag.onLayout(event.nativeEvent.layout.width)}
        onStartShouldSetResponder={() => true}
        onMoveShouldSetResponder={() => true}
        onResponderTerminationRequest={() => false}
        onResponderGrant={(event) => drag.seek(event.nativeEvent.locationX)}
        onResponderMove={(event) => drag.seek(event.nativeEvent.locationX)}
        accessibilityRole="adjustable"
        accessibilityLabel={label}
      >
        <View style={styles.flatTrack}>
          <View style={[styles.flatFill, { width: `${played * 100}%` }]} />
          <View style={[styles.knob, { left: `${played * 100}%` }]} />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  block: {
    marginTop: 12,
  },
  captionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  caption: {
    color: palette.textMuted,
    fontSize: 13,
  },
  clock: {
    color: palette.textMuted,
    fontSize: 13,
    fontVariant: ['tabular-nums'],
  },
  hit: {
    height: 46,
  },
  flatHit: {
    height: 28,
    justifyContent: 'center',
  },
  flatTrack: {
    height: 6,
    borderRadius: 3,
    backgroundColor: palette.track,
    justifyContent: 'center',
  },
  flatFill: {
    height: 6,
    borderRadius: 3,
    backgroundColor: palette.sound,
  },
  knob: {
    position: 'absolute',
    width: 12,
    height: 12,
    marginLeft: -6,
    borderRadius: 6,
    backgroundColor: palette.playhead,
  },
});
