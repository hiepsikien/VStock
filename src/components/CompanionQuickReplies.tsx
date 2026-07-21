import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { colors, spacing } from '../theme';

type Props = {
  suggestions: string[];
  accent: string;
  disabled?: boolean;
  onSelect: (text: string) => void;
};

export function CompanionQuickReplies({
  suggestions,
  accent,
  disabled,
  onSelect,
}: Props) {
  if (!suggestions.length) return null;

  return (
    <View style={styles.wrap}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.row}
        keyboardShouldPersistTaps="handled"
      >
        {suggestions.map((label) => (
          <Pressable
            key={label}
            disabled={disabled}
            onPress={() => {
              void Haptics.selectionAsync();
              onSelect(label);
            }}
            style={[
              styles.chip,
              { borderColor: `${accent}66` },
              disabled && styles.chipDisabled,
            ]}
          >
            <Text style={[styles.chipText, { color: accent }]} numberOfLines={1}>
              {label}
            </Text>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingBottom: 8,
  },
  row: {
    paddingHorizontal: spacing.lg,
    gap: 8,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    backgroundColor: colors.surface,
    maxWidth: 220,
  },
  chipDisabled: { opacity: 0.4 },
  chipText: {
    fontSize: 13,
    fontWeight: '600',
  },
});
