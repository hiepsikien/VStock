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
        <Skeleton width={100} height={16} />
        <Skeleton width={108} height={22} borderRadius={6} style={{ marginTop: 6 }} />
      </View>
    </View>
  );
}

export function SummarySkeleton() {
  return (
    <View style={styles.summaryWrap}>
      <View style={styles.indexStrip}>
        <Skeleton width={168} height={36} borderRadius={10} />
        <Skeleton width={150} height={36} borderRadius={10} />
      </View>
      <View style={styles.health}>
        <View style={styles.healthTop}>
          <Skeleton width={140} height={12} />
          <Skeleton width={48} height={12} />
        </View>
        <Skeleton height={4} borderRadius={2} style={{ width: '100%' }} />
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
    width: 112,
    alignItems: 'flex-end',
  },
  summaryWrap: {
    marginBottom: spacing.sm,
  },
  indexStrip: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
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
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  newsRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    paddingVertical: 14,
    gap: spacing.md,
  },
});
