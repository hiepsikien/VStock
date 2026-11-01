import React, { useEffect, useRef, useState } from 'react';
import { Platform, StyleSheet, Text, View } from 'react-native';
import Svg, { Rect } from 'react-native-svg';
import { clockText } from './labels';
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

/** One movement or rest on the merged work timeline, in work seconds. */
export type TimelinePart = {
  kind: 'audio' | 'rest';
  label: string;
  start: number;
  end: number;
};

type Props = DragProps & {
  label: string;
  duration?: number;
  /** Multi-movement work: audio and rest spans, in order. */
  parts?: TimelinePart[] | null;
  /** Audio peaks for a single-session file. The work bar has none. */
  peaks?: number[] | null;
};

const BARS = 36;
const HIT = 44;
const TIP_WIDTH = 188;

/**
 * One timeline for both the session file and the whole work. Stronger ratio
 * placement lives in `ReplayRoom`, which owns the movement map.
 */
export function Timeline({
  label,
  progress,
  duration = 0,
  peaks = null,
  parts = null,
  onRatio,
}: Props) {
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<{ x: number; ratio: number; box: number } | null>(null);
  const hitRef = useRef<React.ComponentRef<typeof View> | null>(null);
  const drag = useRatioDrag(onRatio);
  const played = clamp01(progress);
  const bars = peaks && peaks.length ? peaks : null;
  const chapters = parts && parts.length > 1 ? parts : null;
  const total = chapters ? chapters[chapters.length - 1].end : Math.max(0, duration);
  const at = hover && chapters ? hover.ratio * total : null;
  const hovered = chapters && at != null ? partAt(chapters, at) : null;
  const tipLeft = hover
    ? Math.max(0, Math.min(Math.max(0, hover.box - TIP_WIDTH), hover.x - TIP_WIDTH / 2))
    : 0;

  // Hover is web-only and the responder system swallows bubbled pointer moves,
  // so listen on the rail node itself.
  useEffect(() => {
    if (Platform.OS !== 'web' || !chapters) return;
    const node = hitRef.current as unknown as HTMLElement | null;
    if (!node?.addEventListener) return;
    const onMove = (event: PointerEvent) => {
      const rect = node.getBoundingClientRect();
      const x = event.clientX - rect.left;
      if (!Number.isFinite(x) || rect.width <= 0) return;
      setHover({ x, ratio: clamp01(x / rect.width), box: rect.width });
    };
    const onLeave = () => setHover(null);
    node.addEventListener('pointermove', onMove);
    node.addEventListener('pointerleave', onLeave);
    return () => {
      node.removeEventListener('pointermove', onMove);
      node.removeEventListener('pointerleave', onLeave);
    };
  }, [chapters]);

  const showHover = (locationX: number) => {
    if (!chapters || width <= 0) return;
    setHover({ x: locationX, ratio: clamp01(locationX / width), box: width });
  };

  return (
    <View style={styles.block}>
      <View style={styles.captionRow}>
        <Text style={[type.section, styles.caption]}>{label}</Text>
      </View>
      <View
        ref={hitRef}
        style={styles.hit}
        onLayout={(event) => {
          const next = event.nativeEvent.layout.width;
          drag.onLayout(next);
          setWidth((current) => (current === next ? current : next));
        }}
        onStartShouldSetResponder={() => true}
        onMoveShouldSetResponder={() => true}
        onResponderTerminationRequest={() => false}
        onResponderGrant={(event) => {
          drag.seek(event.nativeEvent.locationX);
          showHover(event.nativeEvent.locationX);
        }}
        onResponderMove={(event) => {
          drag.seek(event.nativeEvent.locationX);
          showHover(event.nativeEvent.locationX);
        }}
        onResponderRelease={() => setHover(null)}
        onResponderTerminate={() => setHover(null)}
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
          {chapters ? (
            <View style={styles.segments}>
              {chapters.map((part, index) => (
                <View
                  key={`${part.kind}-${index}`}
                  style={{
                    flex: Math.max(part.end - part.start, 1e-6),
                    backgroundColor: part.kind === 'rest' ? palette.hairline : palette.track,
                  }}
                />
              ))}
            </View>
          ) : null}
          <View style={[styles.fill, { width: `${played * 100}%` }]} />
        </View>
        {chapters
          ? chapters
              .filter((part) => part.kind === 'audio' && part.start > 0)
              .map((part, index) => (
                <View
                  key={`tick-${index}`}
                  pointerEvents="none"
                  style={[styles.tick, { left: `${(part.start / total) * 100}%` }]}
                />
              ))
          : null}
        <View pointerEvents="none" style={[styles.knob, { left: `${played * 100}%` }]} />
        {hovered && hover ? (
          <View pointerEvents="none" style={[styles.tip, { left: tipLeft }]}>
            <Text style={[type.sans, styles.tipLabel]} numberOfLines={1}>
              {hovered.label}
            </Text>
            <Text style={[type.monoSmall, styles.tipClock]}>
              {clockText(at ?? 0, total)}
            </Text>
          </View>
        ) : null}
      </View>
    </View>
  );
}

function partAt(parts: TimelinePart[], seconds: number): TimelinePart | null {
  if (!parts.length) return null;
  for (let index = 0; index < parts.length; index += 1) {
    const part = parts[index];
    const last = index === parts.length - 1;
    if (seconds >= part.start && (seconds < part.end || (last && seconds <= part.end))) {
      return part;
    }
  }
  return parts[parts.length - 1];
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
    position: 'relative',
  },
  segments: {
    ...StyleSheet.absoluteFill,
    flexDirection: 'row',
  },
  fill: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    backgroundColor: palette.sound,
  },
  tick: {
    position: 'absolute',
    top: HIT / 2 - 5,
    width: 1,
    height: 10,
    marginLeft: -0.5,
    backgroundColor: palette.hairlineStrong,
  },
  knob: {
    position: 'absolute',
    width: 10,
    height: 10,
    marginLeft: -5,
    borderRadius: 5,
    backgroundColor: palette.playhead,
  },
  tip: {
    position: 'absolute',
    bottom: HIT + 2,
    height: 24,
    maxWidth: TIP_WIDTH,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 8,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
    overflow: 'hidden',
  },
  tipLabel: {
    color: palette.text,
    fontSize: 12,
    lineHeight: 16,
    flexShrink: 1,
  },
  tipClock: {
    color: palette.textMuted,
  },
});
