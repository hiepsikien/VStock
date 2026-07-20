import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import type { Watchlist } from '../storage/watchlist';
import { colors, spacing } from '../theme';

type Props = {
  lists: Watchlist[];
  activeId: string;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onManage?: () => void;
};

export function WatchlistPicker({ lists, activeId, onSelect, onCreate }: Props) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}
    >
      {lists.map((list) => {
        const active = list.id === activeId;
        return (
          <Pressable
            key={list.id}
            onPress={() => {
              void Haptics.selectionAsync();
              onSelect(list.id);
            }}
            style={[styles.chip, active && styles.chipActive]}
          >
            <Text style={[styles.chipText, active && styles.chipTextActive]}>
              {list.name}
            </Text>
            <Text style={[styles.count, active && styles.countActive]}>
              {list.symbols.length}
            </Text>
          </Pressable>
        );
      })}
      <Pressable
        onPress={() => {
          void Haptics.selectionAsync();
          onCreate();
        }}
        style={styles.addChip}
      >
        <Text style={styles.addText}>+ Mới</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: {
    paddingHorizontal: spacing.lg,
    gap: 8,
    paddingBottom: spacing.sm,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 18,
    backgroundColor: colors.surface,
  },
  chipActive: {
    backgroundColor: colors.surfaceElevated,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.positive,
  },
  chipText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  chipTextActive: {
    color: colors.text,
  },
  count: {
    fontSize: 12,
    color: colors.textTertiary,
    fontWeight: '600',
  },
  countActive: {
    color: colors.textSecondary,
  },
  addChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 18,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separator,
  },
  addText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.accent,
  },
});
