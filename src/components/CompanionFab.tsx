import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { colors, spacing } from '../theme';

type Props = {
  onPress: () => void;
  badge?: boolean;
  bottom?: number;
};

/** Floating Companion entry — left side to avoid watchlist + FAB. */
export function CompanionFab({ onPress, badge, bottom = 24 }: Props) {
  return (
    <Pressable
      onPress={() => {
        void Haptics.selectionAsync();
        onPress();
      }}
      style={[styles.fab, { bottom }]}
      accessibilityRole="button"
      accessibilityLabel="Mở Companion"
    >
      <Text style={styles.glyph}>◎</Text>
      {badge ? <View style={styles.badge} /> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  fab: {
    position: 'absolute',
    left: spacing.lg,
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.surfaceElevated,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
    zIndex: 20,
  },
  glyph: {
    color: colors.accent,
    fontSize: 22,
    fontWeight: '600',
  },
  badge: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 9,
    height: 9,
    borderRadius: 5,
    backgroundColor: colors.positive,
  },
});
