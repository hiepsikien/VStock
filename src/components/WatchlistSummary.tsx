import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { formatChange, formatPercent } from '../data/stocks';
import { colors, spacing, typography } from '../theme';

export type IndexQuote = {
  symbol: string;
  name: string;
  exchange: string;
  price: number;
  change: number;
  changePercent: number;
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

  return (
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

      {indices.length > 0 ? (
        <View style={styles.indicesRow}>
          {indices.map((idx) => {
            const up = idx.changePercent >= 0;
            const tint = up ? colors.positive : colors.negative;
            return (
              <Pressable
                key={idx.symbol}
                style={styles.indexCard}
                onPress={() => {
                  if (!onIndexPress) return;
                  void Haptics.selectionAsync();
                  onIndexPress(idx.symbol);
                }}
                disabled={!onIndexPress}
              >
                <Text style={styles.indexName}>{idx.name}</Text>
                <Text style={styles.indexPrice}>{idx.price.toFixed(2)}</Text>
                <Text style={[styles.indexChange, { color: tint }]}>
                  {formatChange(idx.change)} ({formatPercent(idx.changePercent)})
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}
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
  card: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
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
  indicesRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  indexCard: {
    flex: 1,
    backgroundColor: colors.surfaceElevated,
    borderRadius: 10,
    padding: spacing.sm,
  },
  indexName: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
  },
  indexPrice: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginTop: 4,
    fontVariant: ['tabular-nums'],
  },
  indexChange: {
    fontSize: 12,
    fontWeight: '600',
    marginTop: 2,
    fontVariant: ['tabular-nums'],
  },
});
