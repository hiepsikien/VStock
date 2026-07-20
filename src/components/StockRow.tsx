import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import type { Stock } from '../types';
import { formatPercent, formatPrice } from '../data/stocks';
import { colors, spacing, typography } from '../theme';
import { Sparkline } from './Sparkline';

type Props = {
  stock: Stock;
  onPress: (stock: Stock) => void;
};

export function StockRow({ stock, onPress }: Props) {
  const isUp = stock.changePercent >= 0;

  return (
    <Pressable
      onPress={() => {
        void Haptics.selectionAsync();
        onPress(stock);
      }}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
      accessibilityRole="button"
      accessibilityLabel={`${stock.symbol}, ${formatPrice(stock.price, stock.currency)}, ${formatPercent(stock.changePercent)}`}
    >
      <View style={styles.left}>
        <Text style={styles.symbol}>{stock.symbol}</Text>
        <Text style={styles.name} numberOfLines={1}>
          {stock.name}
        </Text>
      </View>

      <View style={styles.chart}>
        <Sparkline data={stock.sparkline} positive={isUp} width={76} height={34} />
      </View>

      <View style={styles.right}>
        <Text style={styles.price}>
          {formatPrice(stock.price, stock.currency)}
        </Text>
        <View style={[styles.badge, { backgroundColor: isUp ? colors.positive : colors.negative }]}>
          <Text style={styles.badgeText}>{formatPercent(stock.changePercent)}</Text>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: 14,
    minHeight: 64,
  },
  pressed: {
    backgroundColor: colors.surface,
  },
  left: {
    flex: 1.15,
    paddingRight: spacing.sm,
  },
  symbol: {
    ...typography.symbol,
    color: colors.text,
  },
  name: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  chart: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  right: {
    width: 92,
    alignItems: 'flex-end',
  },
  price: {
    ...typography.price,
    color: colors.text,
    marginBottom: 6,
  },
  badge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    minWidth: 72,
    alignItems: 'center',
  },
  badgeText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
});
