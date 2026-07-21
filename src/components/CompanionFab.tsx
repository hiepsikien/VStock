import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { getCompanionCharacter } from '../companion/characters';
import { CompanionAvatar } from './CompanionAvatar';
import { spacing } from '../theme';

type Props = {
  onPress: () => void;
  badge?: boolean;
  bottom?: number;
};

/** Floating Companion entry — left side to avoid watchlist + FAB. */
export function CompanionFab({ onPress, badge, bottom = 24 }: Props) {
  const character = getCompanionCharacter();
  return (
    <Pressable
      onPress={() => {
        void Haptics.selectionAsync();
        onPress();
      }}
      style={[styles.fab, { bottom, borderColor: character.accent }]}
      accessibilityRole="button"
      accessibilityLabel={`Mở chat với ${character.name}`}
    >
      <CompanionAvatar character={character} size={44} />
      {badge ? <View style={[styles.badge, { backgroundColor: character.accent }]} /> : null}
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
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
    elevation: 5,
    zIndex: 20,
  },
  badge: {
    position: 'absolute',
    top: 2,
    right: 2,
    width: 10,
    height: 10,
    borderRadius: 5,
    borderWidth: 1.5,
    borderColor: '#000',
  },
});
