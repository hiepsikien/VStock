import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import type { WatchlistSort } from '../utils/watchlistSort';
import { colors, spacing } from '../theme';

const OPTIONS: { key: WatchlistSort; label: string }[] = [
  { key: 'change', label: '% Thay đổi' },
  { key: 'symbol', label: 'Mã' },
];

type Props = {
  value: WatchlistSort;
  onChange: (sort: WatchlistSort) => void;
  editing: boolean;
  onToggleEdit: () => void;
};

export function SortChips({ value, onChange, editing, onToggleEdit }: Props) {
  return (
    <View style={styles.row}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chips}
      >
        {OPTIONS.map((opt) => {
          const active = value === opt.key;
          return (
            <Pressable
              key={opt.key}
              onPress={() => {
                void Haptics.selectionAsync();
                onChange(opt.key);
              }}
              style={[styles.chip, active && styles.chipActive]}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>
                {opt.label}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
      <Pressable
        onPress={() => {
          void Haptics.selectionAsync();
          onToggleEdit();
        }}
        style={[styles.editBtn, editing && styles.editBtnActive]}
      >
        <Text style={[styles.editText, editing && styles.editTextActive]}>
          {editing ? 'Xong' : 'Sửa'}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingLeft: spacing.lg,
    marginBottom: spacing.sm,
  },
  chips: {
    gap: 8,
    paddingRight: spacing.sm,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 16,
    backgroundColor: colors.surface,
  },
  chipActive: {
    backgroundColor: colors.surfaceElevated,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.positive,
  },
  chipText: {
    fontSize: 13,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  chipTextActive: {
    color: colors.positive,
    fontWeight: '600',
  },
  editBtn: {
    paddingHorizontal: spacing.lg,
    paddingVertical: 8,
  },
  editBtnActive: {},
  editText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.accent,
  },
  editTextActive: {
    color: colors.positive,
  },
});
