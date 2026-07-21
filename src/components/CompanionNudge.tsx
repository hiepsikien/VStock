import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { getCompanionCharacter } from '../companion/characters';
import { CompanionAvatar } from './CompanionAvatar';
import { colors, spacing, typography } from '../theme';

type Props = {
  message: string;
  onReply: () => void;
  onDismiss: () => void;
};

export function CompanionNudge({ message, onReply, onDismiss }: Props) {
  const character = getCompanionCharacter();
  return (
    <View style={[styles.wrap, { borderColor: `${character.accent}73` }]} accessibilityRole="summary">
      <View style={styles.header}>
        <CompanionAvatar character={character} size={28} />
        <Text style={[styles.title, { color: character.accent }]}>{character.name}</Text>
      </View>
      <Text style={styles.body}>{message}</Text>
      <View style={styles.actions}>
        <Pressable
          onPress={() => {
            void Haptics.selectionAsync();
            onDismiss();
          }}
          hitSlop={8}
          style={styles.btnGhost}
        >
          <Text style={styles.btnGhostText}>Bỏ qua</Text>
        </Pressable>
        <Pressable
          onPress={() => {
            void Haptics.selectionAsync();
            onReply();
          }}
          style={[styles.btnPrimary, { backgroundColor: character.accent }]}
        >
          <Text style={styles.btnPrimaryText}>Trả lời</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    padding: spacing.md,
    borderRadius: 14,
    backgroundColor: 'rgba(28,28,30,0.92)',
    borderWidth: StyleSheet.hairlineWidth,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  title: {
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  body: {
    ...typography.body,
    color: colors.text,
    lineHeight: 20,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
    marginTop: spacing.md,
  },
  btnGhost: {
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  btnGhostText: {
    color: colors.textSecondary,
    fontSize: 15,
    fontWeight: '500',
  },
  btnPrimary: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 10,
  },
  btnPrimaryText: {
    color: '#0B1220',
    fontSize: 15,
    fontWeight: '700',
  },
});
