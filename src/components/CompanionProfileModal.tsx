import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import type { CompanionCharacter } from '../companion/characters';
import { getCharacterExpertise } from '../companion/characters';
import { colors, spacing } from '../theme';
import { CompanionAvatar } from './CompanionAvatar';

type Props = {
  character: CompanionCharacter;
  visible: boolean;
  onClose: () => void;
  /** Clears chat history + bonding memory, then closes. */
  onResetSession?: () => Promise<void> | void;
};

export function CompanionProfileModal({
  character,
  visible,
  onClose,
  onResetSession,
}: Props) {
  const insets = useSafeAreaInsets();
  const { profile } = character;
  const meta = `${profile.gender} · ${profile.age} · ${profile.birthplace}`;
  const [resetting, setResetting] = useState(false);
  const expertise = getCharacterExpertise(character.id);

  const confirmReset = () => {
    if (!onResetSession || resetting) return;
    Alert.alert(
      'Bắt đầu lại với Vy?',
      'Xóa toàn bộ hội thoại và ký ức gắn kết. Không hoàn tác được.',
      [
        { text: 'Hủy', style: 'cancel' },
        {
          text: 'Xóa hết',
          style: 'destructive',
          onPress: () => {
            void (async () => {
              setResetting(true);
              try {
                await onResetSession();
                void Haptics.notificationAsync(
                  Haptics.NotificationFeedbackType.Success,
                );
                onClose();
              } finally {
                setResetting(false);
              }
            })();
          },
        },
      ],
    );
  };

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

          {expertise.length ? (
            <View style={styles.expertiseBox}>
              <Text style={styles.expertiseTitle}>Chuyên môn</Text>
              {expertise.map((line) => (
                <Text key={line} style={styles.expertiseItem}>
                  · {line}
                </Text>
              ))}
            </View>
          ) : null}

          {onResetSession ? (
            <Pressable
              onPress={confirmReset}
              disabled={resetting}
              style={styles.resetBtn}
            >
              {resetting ? (
                <ActivityIndicator color={colors.negative} />
              ) : (
                <Text style={styles.resetBtnText}>Xóa chat & bắt đầu lại</Text>
              )}
            </Pressable>
          ) : null}

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
  expertiseBox: {
    marginBottom: spacing.md,
    padding: spacing.md,
    borderRadius: 12,
    backgroundColor: colors.surface,
  },
  expertiseTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    marginBottom: 6,
    letterSpacing: 0.3,
  },
  expertiseItem: {
    fontSize: 13,
    lineHeight: 20,
    color: colors.text,
  },
  resetBtn: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 40,
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: 'rgba(255,69,58,0.45)',
    backgroundColor: 'rgba(255,69,58,0.08)',
    marginBottom: spacing.sm,
  },
  resetBtnText: {
    color: colors.negative,
    fontSize: 15,
    fontWeight: '600',
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
