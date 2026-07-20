import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import type { MarketSymbol } from '../api/client';
import { colors, spacing, typography } from '../theme';

type Props = {
  item: MarketSymbol;
  added: boolean;
  onOpen: () => void;
  onToggle: () => void;
};

export function SearchResultRow({ item, added, onOpen, onToggle }: Props) {
  return (
    <Pressable
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
      onPress={onOpen}
    >
      <View style={styles.left}>
        <View style={styles.symbolRow}>
          <Text style={styles.symbol}>{item.symbol}</Text>
          <View style={styles.exchangePill}>
            <Text style={styles.exchangeText}>{item.exchange}</Text>
          </View>
        </View>
        <Text style={styles.name} numberOfLines={1}>
          {item.name}
        </Text>
      </View>
      <Pressable
        onPress={() => {
          void Haptics.selectionAsync();
          onToggle();
        }}
        style={[styles.addBtn, added && styles.addedBtn]}
        hitSlop={8}
      >
        <Text style={[styles.addBtnText, added && styles.addedBtnText]}>
          {added ? '✓' : '+'}
        </Text>
      </Pressable>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: 12,
    minHeight: 58,
  },
  pressed: {
    backgroundColor: colors.surface,
  },
  left: {
    flex: 1,
    paddingRight: spacing.md,
  },
  symbolRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  symbol: {
    ...typography.symbol,
    color: colors.text,
  },
  exchangePill: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  exchangeText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    letterSpacing: 0.3,
  },
  name: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 3,
  },
  addBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addedBtn: {
    backgroundColor: colors.surfaceElevated,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.positive,
  },
  addBtnText: {
    color: colors.text,
    fontSize: 20,
    fontWeight: '600',
    lineHeight: 22,
  },
  addedBtnText: {
    color: colors.positive,
    fontSize: 18,
  },
});
