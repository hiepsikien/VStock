import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { colors, spacing, typography } from '../theme';

type Props = {
  message: string;
  onReply: () => void;
  onDismiss: () => void;
};

export function CompanionNudge({ message, onReply, onDismiss }: Props) {
  return (
    <View style={styles.wrap} accessibilityRole="summary">
      <Text style={styles.title}>Companion</Text>
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
          style={styles.btnPrimary}
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
    borderColor: 'rgba(10,132,255,0.45)',
  },
  title: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.accent,
    letterSpacing: 0.4,
    marginBottom: 6,
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
    backgroundColor: colors.accent,
  },
  btnPrimaryText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '600',
  },
});
