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
import { formatChange, formatPercent } from '../data/stocks';
import { colors, spacing, typography } from '../theme';
import {
  formatIndexPrice,
  isCommodityStrip,
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

const AUTO_SCROLL_MS = 3200;
const PILL_WIDTH = 168;
const PILL_GAP = 8;

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
  const [userPaused, setUserPaused] = useState(false);

  useEffect(() => {
    if (indices.length <= 1) return;

    const id = setInterval(() => {
      if (pausedRef.current || userPaused) return;
      const next = (indexRef.current + 1) % indices.length;
      indexRef.current = next;
      scrollRef.current?.scrollTo({
        x: next * (PILL_WIDTH + PILL_GAP),
        animated: true,
      });
    }, AUTO_SCROLL_MS);

    return () => clearInterval(id);
  }, [indices.length, userPaused]);

  const onScrollEnd = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const x = event.nativeEvent.contentOffset.x;
    indexRef.current = Math.round(x / (PILL_WIDTH + PILL_GAP));
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
          snapToInterval={PILL_WIDTH + PILL_GAP}
          decelerationRate="fast"
          onScrollBeginDrag={() => {
            pausedRef.current = true;
            setUserPaused(true);
          }}
          onScrollEndDrag={() => {
            pausedRef.current = false;
            // Resume auto-scroll shortly after user finishes dragging.
            setTimeout(() => setUserPaused(false), 5000);
          }}
          onMomentumScrollEnd={onScrollEnd}
        >
          {indices.map((idx) => {
            const up = idx.changePercent >= 0;
            const tint = up ? colors.positive : colors.negative;
            const tappable = isIndexLikeDetail(idx.symbol) && !!onIndexPress;
            return (
              <Pressable
                key={idx.symbol}
                style={({ pressed }) => [
                  styles.indexPill,
                  { width: PILL_WIDTH },
                  pressed && tappable && styles.indexPillPressed,
                ]}
                onPress={() => {
                  if (!tappable) return;
                  void Haptics.selectionAsync();
                  onIndexPress?.(idx.symbol);
                }}
                disabled={!tappable}
                accessibilityRole={tappable ? 'button' : 'text'}
                accessibilityLabel={`${idx.name}, ${formatIndexPrice(idx.price, idx.currency)}, ${formatPercent(idx.changePercent)}`}
              >
                <View style={styles.indexPillTop}>
                  <Text style={styles.indexName} numberOfLines={1}>
                    {idx.name}
                  </Text>
                  <View style={[styles.pctBadge, { backgroundColor: `${tint}22` }]}>
                    <Text style={[styles.pctBadgeText, { color: tint }]}>
                      {formatPercent(idx.changePercent)}
                    </Text>
                  </View>
                </View>
                <View style={styles.indexPillBottom}>
                  <Text style={styles.indexPrice} numberOfLines={1}>
                    {formatIndexPrice(idx.price, idx.currency)}
                  </Text>
                  <Text style={[styles.indexChange, { color: tint }]} numberOfLines={1}>
                    {formatChange(idx.change)}
                  </Text>
                </View>
                {isCommodityStrip(idx.symbol) ? (
                  <Text style={styles.indexUnit}>
                    {idx.symbol === 'XAU' ? 'USD/oz' : 'USD/bbl'}
                  </Text>
                ) : null}
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}

      <View style={styles.card}>
        <View style={styles.topRow}>
          <View style={styles.liveWrap}>
            <View style={[styles.dot, live && styles.dotLive]} />
            <Text style={styles.liveText}>
              {offline ? 'Offline' : live ? 'Live · 30s' : sessionLabel}
            </Text>
          </View>
          <Text style={[styles.avg, { color: avgColor }]}>
            TB {avgChange >= 0 ? '+' : ''}
            {avgChange.toFixed(2)}%
          </Text>
        </View>

        <View style={styles.statsRow}>
          <Stat label="Tăng" value={gainers} color={colors.positive} />
          <Stat label="Giảm" value={losers} color={colors.negative} />
          <Stat label="Đi ngang" value={flat} color={colors.textSecondary} />
          <Stat label="Tổng" value={total} color={colors.text} />
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

function Stat({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <View style={styles.stat}>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginBottom: spacing.md,
  },
  indexScroll: {
    marginBottom: spacing.sm,
  },
  indexStrip: {
    paddingHorizontal: spacing.lg,
    gap: PILL_GAP,
  },
  indexPill: {
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 14,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separator,
  },
  indexPillPressed: {
    opacity: 0.85,
    backgroundColor: colors.surfaceElevated,
  },
  indexPillTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  indexName: {
    flex: 1,
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
    letterSpacing: 0.2,
  },
  pctBadge: {
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 8,
  },
  pctBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
  indexPillBottom: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginTop: 6,
    gap: 8,
  },
  indexPrice: {
    flexShrink: 1,
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    fontVariant: ['tabular-nums'],
  },
  indexChange: {
    fontSize: 13,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  indexUnit: {
    marginTop: 4,
    fontSize: 10,
    fontWeight: '500',
    color: colors.textTertiary,
  },
  card: {
    marginHorizontal: spacing.lg,
    padding: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: 14,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  liveWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  dot: {
    width: 8,
    height: 8,
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
  },
  avg: {
    fontSize: 14,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  stat: {
    alignItems: 'center',
    minWidth: 56,
  },
  statValue: {
    fontSize: 20,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  statLabel: {
    ...typography.caption,
    color: colors.textTertiary,
    marginTop: 2,
  },
  bar: {
    flexDirection: 'row',
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
    marginTop: spacing.md,
    backgroundColor: colors.surfaceElevated,
  },
  barSegment: {
    height: '100%',
  },
});
