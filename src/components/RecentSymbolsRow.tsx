import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { formatPercent } from '../data/stocks';
import { colors, spacing } from '../theme';

type RecentItem = {
  symbol: string;
  name?: string;
  changePercent?: number;
};

type Props = {
  items: RecentItem[];
  onPress: (symbol: string) => void;
};

export function RecentSymbolsRow({ items, onPress }: Props) {
  if (!items.length) return null;

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>Xem gần đây</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
        {items.map((item) => {
          const up = (item.changePercent ?? 0) >= 0;
          const tint = up ? colors.positive : colors.negative;
          return (
            <Pressable
              key={item.symbol}
              onPress={() => {
                void Haptics.selectionAsync();
                onPress(item.symbol);
              }}
              style={styles.chip}
            >
              <Text style={styles.symbol}>{item.symbol}</Text>
              {item.changePercent != null ? (
                <Text style={[styles.change, { color: tint }]}>
                  {formatPercent(item.changePercent)}
                </Text>
              ) : null}
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginBottom: spacing.sm,
  },
  title: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.xs,
  },
  row: {
    paddingHorizontal: spacing.lg,
    gap: 8,
  },
  chip: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    minWidth: 72,
  },
  symbol: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.text,
  },
  change: {
    fontSize: 12,
    fontWeight: '600',
    marginTop: 2,
    fontVariant: ['tabular-nums'],
  },
});
