import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import type { NewsFilter } from '../types/news';
import { colors, spacing } from '../theme';

const OPTIONS: { key: NewsFilter; label: string }[] = [
  { key: 'all', label: 'Tất cả' },
  { key: 'stock_news', label: 'Chứng khoán' },
  { key: 'macro_news', label: 'Kinh tế' },
  { key: 'company_news', label: 'Doanh nghiệp' },
  { key: 'commodity_news', label: 'Vàng · HH' },
  { key: 'real_estate_news', label: 'BĐS' },
  { key: 'disclosure', label: 'Công bố' },
];

type Props = {
  value: NewsFilter;
  onChange: (value: NewsFilter) => void;
};

export function NewsFilterChips({ value, onChange }: Props) {
  return (
    <View style={styles.wrap}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.row}
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
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    minHeight: 42,
  },
  row: {
    paddingHorizontal: spacing.lg,
    gap: 8,
    paddingTop: 2,
    paddingBottom: spacing.sm,
    alignItems: 'center',
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    minHeight: 34,
    borderRadius: 16,
    backgroundColor: colors.surface,
    justifyContent: 'center',
  },
  chipActive: {
    backgroundColor: colors.surfaceElevated,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.positive,
  },
  chipText: {
    fontSize: 13,
    lineHeight: 17,
    fontWeight: '500',
    color: colors.textSecondary,
    textAlignVertical: 'center',
  },
  chipTextActive: {
    color: colors.positive,
    fontWeight: '600',
  },
});
