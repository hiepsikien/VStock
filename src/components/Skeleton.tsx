import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View, type ViewStyle } from 'react-native';
import { colors, spacing } from '../theme';

type Props = {
  style?: ViewStyle;
  width?: number | `${number}%`;
  height?: number;
  borderRadius?: number;
};

export function Skeleton({ style, width, height = 14, borderRadius = 6 }: Props) {
  const opacity = useRef(new Animated.Value(0.35)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.75, duration: 700, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.35, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);

  return (
    <Animated.View
      style={[
        styles.base,
        { height, borderRadius, opacity, width },
        style,
      ]}
    />
  );
}

export function StockRowSkeleton() {
  return (
    <View style={styles.stockRow}>
      <View style={styles.stockLeft}>
        <Skeleton width={56} height={16} />
        <Skeleton width={120} height={12} style={{ marginTop: 8 }} />
      </View>
      <Skeleton width={72} height={32} borderRadius={4} />
      <View style={styles.stockRight}>
        <Skeleton width={64} height={16} />
        <Skeleton width={72} height={22} borderRadius={6} style={{ marginTop: 6 }} />
      </View>
    </View>
  );
}

export function SummarySkeleton() {
  return (
    <View style={styles.summaryCard}>
      <View style={styles.summaryTop}>
        <Skeleton width={100} height={14} />
        <Skeleton width={72} height={14} />
      </View>
      <View style={styles.summaryStats}>
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} width={40} height={28} borderRadius={4} />
        ))}
      </View>
      <Skeleton height={4} borderRadius={2} style={{ marginTop: spacing.md, width: '100%' }} />
      <View style={styles.indexRow}>
        <Skeleton width="46%" height={52} borderRadius={10} />
        <Skeleton width="46%" height={52} borderRadius={10} />
      </View>
    </View>
  );
}

export function NewsRowSkeleton() {
  return (
    <View style={styles.newsRow}>
      <View style={{ flex: 1 }}>
        <Skeleton width={80} height={10} />
        <Skeleton width="95%" height={16} style={{ marginTop: 8 }} />
        <Skeleton width="70%" height={14} style={{ marginTop: 6 }} />
      </View>
      <Skeleton width={72} height={72} borderRadius={8} />
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    backgroundColor: colors.surfaceElevated,
  },
  stockRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: 14,
    gap: spacing.md,
  },
  stockLeft: {
    flex: 1,
  },
  stockRight: {
    alignItems: 'flex-end',
  },
  summaryCard: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    padding: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: 14,
  },
  summaryTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  summaryStats: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  indexRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.md,
  },
  newsRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    paddingVertical: 14,
    gap: spacing.md,
  },
});
