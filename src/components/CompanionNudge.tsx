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
  /** Mood check-in chips — tap sends seed message into chat */
  quickReplies?: string[];
  onQuickReply?: (text: string) => void;
};

export function CompanionNudge({
  message,
  onReply,
  onDismiss,
  quickReplies,
  onQuickReply,
}: Props) {
  const character = getCompanionCharacter();
  const hasChips = Boolean(quickReplies?.length && onQuickReply);

  return (
    <View
      style={[styles.wrap, { borderColor: `${character.accent}73` }]}
      accessibilityRole="summary"
    >
      <View style={styles.header}>
        <CompanionAvatar character={character} size={28} />
        <Text style={[styles.title, { color: character.accent }]}>
          {character.name}
        </Text>
      </View>
      <Text style={styles.body}>{message}</Text>
      {hasChips ? (
        <View style={styles.chips}>
          {quickReplies!.map((chip) => (
            <Pressable
              key={chip}
              onPress={() => {
                void Haptics.selectionAsync();
                onQuickReply!(chip);
              }}
              style={[styles.chip, { borderColor: `${character.accent}55` }]}
            >
              <Text style={[styles.chipText, { color: character.accent }]}>
                {chip}
              </Text>
            </Pressable>
          ))}
        </View>
      ) : null}
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
        {!hasChips ? (
          <Pressable
            onPress={() => {
              void Haptics.selectionAsync();
              onReply();
            }}
            style={[styles.btnPrimary, { backgroundColor: character.accent }]}
          >
            <Text style={styles.btnPrimaryText}>Trả lời</Text>
          </Pressable>
        ) : null}
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
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: spacing.sm,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    backgroundColor: colors.surface,
  },
  chipText: {
    fontSize: 13,
    fontWeight: '600',
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
