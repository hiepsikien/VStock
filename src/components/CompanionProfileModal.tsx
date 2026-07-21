import React from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import type { CompanionCharacter } from '../companion/characters';
import { colors, spacing } from '../theme';
import { CompanionAvatar } from './CompanionAvatar';

type Props = {
  character: CompanionCharacter;
  visible: boolean;
  onClose: () => void;
};

export function CompanionProfileModal({ character, visible, onClose }: Props) {
  const insets = useSafeAreaInsets();
  const { profile } = character;
  const meta = `${profile.gender} · ${profile.age} · ${profile.birthplace}`;

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent
      onRequestClose={onClose}
    >
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable
          style={[styles.sheet, { paddingBottom: Math.max(insets.bottom, 16) }]}
          onPress={(e) => e.stopPropagation()}
        >
          <View style={styles.handle} />

          <View style={styles.header}>
            <CompanionAvatar character={character} size={56} />
            <View style={styles.headerText}>
              <View style={styles.nameRow}>
                <Text style={styles.name}>{character.name}</Text>
                <Text style={[styles.virtual, { color: character.accent }]}>
                  Nhân vật ảo
                </Text>
              </View>
              <Text style={styles.meta}>{meta}</Text>
              <Text style={styles.job}>{profile.occupation}</Text>
            </View>
          </View>

          <Text style={styles.bio}>{profile.bio}</Text>

          <Pressable
            onPress={() => {
              void Haptics.selectionAsync();
              onClose();
            }}
            hitSlop={8}
            style={styles.closeBtn}
          >
            <Text style={styles.closeBtnText}>Đóng</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.surfaceElevated,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
  },
  handle: {
    alignSelf: 'center',
    width: 32,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.separator,
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: spacing.md,
  },
  headerText: {
    flex: 1,
    gap: 2,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 8,
    flexWrap: 'wrap',
  },
  name: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
  },
  virtual: {
    fontSize: 12,
    fontWeight: '700',
  },
  meta: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  job: {
    fontSize: 13,
    color: colors.textTertiary,
    marginTop: 1,
  },
  bio: {
    fontSize: 14,
    lineHeight: 20,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  closeBtn: {
    alignSelf: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  closeBtnText: {
    color: colors.textSecondary,
    fontSize: 15,
    fontWeight: '600',
  },
});
