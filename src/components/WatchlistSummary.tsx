import React, { useEffect, useRef, useState } from 'react';
import {
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import * as Haptics from 'expo-haptics';
import { formatPercent } from '../data/stocks';
import { colors, spacing, typography } from '../theme';
import {
  formatIndexPrice,
  isIndexLikeDetail,
} from '../utils/marketIndices';

export type IndexQuote = {
  symbol: string;
  name: string;
  exchange: string;
  price: number;
  change: number;
  changePercent: number;
  currency?: string;
};

type Props = {
  total: number;
  gainers: number;
  losers: number;
  flat: number;
  avgChange: number;
  live: boolean;
  sessionLabel: string;
  offline?: boolean;
  indices?: IndexQuote[];
  onIndexPress?: (symbol: string) => void;
};

const AUTO_SCROLL_MS = 2800;
const CHIP_GAP = 8;
const STRIP_PAD = spacing.lg;

function tickerLabel(idx: IndexQuote): string {
  switch (idx.symbol.toUpperCase()) {
    case 'VNINDEX':
      return 'VNINDEX';
    case 'HNX':
      return 'HNX';
    case 'XAU':
      return 'Vàng';
    case 'WTI':
      return 'Dầu';
    default:
      return idx.name;
  }
}

export function WatchlistSummary({
  total,
  gainers,
  losers,
  flat,
  avgChange,
  live,
  sessionLabel,
  offline,
  indices = [],
  onIndexPress,
}: Props) {
  const upRatio = total > 0 ? gainers / total : 0;
  const downRatio = total > 0 ? losers / total : 0;
  const flatRatio = total > 0 ? flat / total : 0;
  const avgColor = avgChange >= 0 ? colors.positive : colors.negative;

  const scrollRef = useRef<ScrollView>(null);
  const indexRef = useRef(0);
  const pausedRef = useRef(false);
  const chipWidths = useRef<number[]>([]);
  const [snapOffsets, setSnapOffsets] = useState<number[]>([]);
  const [userPaused, setUserPaused] = useState(false);

  const rebuildOffsets = (count: number) => {
    const widths = chipWidths.current;
    if (widths.length < count || widths.some((w) => !w)) return;
    const offsets: number[] = [];
    let x = 0;
    for (let i = 0; i < count; i += 1) {
      offsets.push(x);
      x += widths[i] + CHIP_GAP;
    }
    setSnapOffsets(offsets);
  };

  useEffect(() => {
    chipWidths.current = new Array(indices.length).fill(0);
    setSnapOffsets([]);
    indexRef.current = 0;
  }, [indices.length]);

  useEffect(() => {
    if (indices.length <= 1 || snapOffsets.length < indices.length) return;

    const id = setInterval(() => {
      if (pausedRef.current || userPaused) return;
      const next = (indexRef.current + 1) % indices.length;
      indexRef.current = next;
      scrollRef.current?.scrollTo({
        x: snapOffsets[next] ?? 0,
        animated: true,
      });
    }, AUTO_SCROLL_MS);

    return () => clearInterval(id);
  }, [indices.length, snapOffsets, userPaused]);

  const onScrollEnd = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const x = event.nativeEvent.contentOffset.x;
    if (!snapOffsets.length) return;
    let nearest = 0;
    let best = Number.POSITIVE_INFINITY;
    snapOffsets.forEach((offset, i) => {
      const d = Math.abs(offset - x);
      if (d < best) {
        best = d;
        nearest = i;
      }
    });
    indexRef.current = nearest;
  };

  return (
    <View style={styles.wrap}>
      {indices.length > 0 ? (
        <ScrollView
          ref={scrollRef}
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.indexStrip}
          style={styles.indexScroll}
          snapToOffsets={snapOffsets.length ? snapOffsets : undefined}
          decelerationRate="fast"
          onScrollBeginDrag={() => {
            pausedRef.current = true;
            setUserPaused(true);
          }}
          onScrollEndDrag={() => {
            pausedRef.current = false;
            setTimeout(() => setUserPaused(false), 5000);
          }}
          onMomentumScrollEnd={onScrollEnd}
        >
          {indices.map((idx, i) => {
            const up = idx.changePercent >= 0;
            const tint = up ? colors.positive : colors.negative;
            const tappable = isIndexLikeDetail(idx.symbol) && !!onIndexPress;
            const label = tickerLabel(idx);
            return (
              <Pressable
                key={idx.symbol}
                style={({ pressed }) => [
                  styles.indexChip,
                  pressed && tappable && styles.indexChipPressed,
                ]}
                onLayout={(e) => {
                  const w = e.nativeEvent.layout.width;
                  if (chipWidths.current[i] === w) return;
                  chipWidths.current[i] = w;
                  rebuildOffsets(indices.length);
                }}
                onPress={() => {
                  if (!tappable) return;
                  void Haptics.selectionAsync();
                  onIndexPress?.(idx.symbol);
                }}
                disabled={!tappable}
                accessibilityRole={tappable ? 'button' : 'text'}
                accessibilityLabel={`${label}, ${formatIndexPrice(idx.price, idx.currency)}, ${formatPercent(idx.changePercent)}`}
              >
                <Text style={styles.indexName}>{label}</Text>
                <Text style={styles.indexPrice}>
                  {formatIndexPrice(idx.price, idx.currency)}
                </Text>
                <Text style={[styles.indexPct, { color: tint }]}>
                  {formatPercent(idx.changePercent)}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}

      <View style={styles.health}>
        <View style={styles.healthTop}>
          <View style={styles.liveWrap}>
            <View style={[styles.dot, live && styles.dotLive]} />
            <Text style={styles.liveText} numberOfLines={1}>
              {offline ? 'Offline' : live ? 'Live · 30s' : sessionLabel}
            </Text>
            <Text style={styles.dotSep}>·</Text>
            <Text style={[styles.avg, { color: avgColor }]} numberOfLines={1}>
              TB {avgChange >= 0 ? '+' : ''}
              {avgChange.toFixed(2)}%
            </Text>
          </View>
          <View style={styles.microStats}>
            <Text style={[styles.microStat, { color: colors.positive }]}>
              {gainers}↑
            </Text>
            <Text style={[styles.microStat, { color: colors.negative }]}>
              {losers}↓
            </Text>
          </View>
        </View>

        <View style={styles.bar}>
          {upRatio > 0 ? (
            <View style={[styles.barSegment, { flex: upRatio, backgroundColor: colors.positive }]} />
          ) : null}
          {flatRatio > 0 ? (
            <View
              style={[styles.barSegment, { flex: flatRatio, backgroundColor: colors.textTertiary }]}
            />
          ) : null}
          {downRatio > 0 ? (
            <View
              style={[styles.barSegment, { flex: downRatio, backgroundColor: colors.negative }]}
            />
          ) : null}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginBottom: spacing.sm,
  },
  indexScroll: {
    marginBottom: spacing.sm,
  },
  indexStrip: {
    paddingHorizontal: STRIP_PAD,
    gap: CHIP_GAP,
    alignItems: 'center',
  },
  indexChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    height: 36,
    paddingHorizontal: 12,
    borderRadius: 10,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separator,
  },
  indexChipPressed: {
    opacity: 0.85,
    backgroundColor: colors.surfaceElevated,
  },
  indexName: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  indexPrice: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.text,
    fontVariant: ['tabular-nums'],
  },
  indexPct: {
    fontSize: 12,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
  health: {
    marginHorizontal: spacing.lg,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: colors.surface,
    borderRadius: 12,
  },
  healthTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
    marginBottom: 8,
  },
  liveWrap: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    minWidth: 0,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: colors.textTertiary,
  },
  dotLive: {
    backgroundColor: colors.positive,
  },
  liveText: {
    ...typography.caption,
    color: colors.textSecondary,
    fontWeight: '500',
    flexShrink: 1,
  },
  dotSep: {
    color: colors.textTertiary,
    fontSize: 12,
  },
  avg: {
    fontSize: 13,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
    flexShrink: 0,
  },
  microStats: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  microStat: {
    fontSize: 13,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
  bar: {
    flexDirection: 'row',
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
    backgroundColor: colors.surfaceElevated,
  },
  barSegment: {
    height: '100%',
  },
});
