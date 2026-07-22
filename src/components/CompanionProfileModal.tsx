import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import type { CompanionCharacter } from '../companion/characters';
import { getCharacterExpertise } from '../companion/characters';
import {
  formatActivityTime,
  type CompanionActivity,
} from '../companion/activityStore';
import { colors, spacing } from '../theme';
import { CompanionAvatar } from './CompanionAvatar';

type Props = {
  character: CompanionCharacter;
  visible: boolean;
  onClose: () => void;
  /** Clears chat history + bonding memory, then closes. */
  onResetSession?: () => Promise<void> | void;
  /** How Vy addresses the user */
  nickname?: string;
  onSaveNickname?: (nickname: string) => void | Promise<void>;
  /** Important actions Vy did for the user */
  activities?: CompanionActivity[];
};

export function CompanionProfileModal({
  character,
  visible,
  onClose,
  onResetSession,
  nickname = '',
  onSaveNickname,
  activities = [],
}: Props) {
  const insets = useSafeAreaInsets();
  const { profile } = character;
  const meta = `${profile.gender} · ${profile.age} · ${profile.birthplace}`;
  const [resetting, setResetting] = useState(false);
  const [nickDraft, setNickDraft] = useState(nickname);
  const [savingNick, setSavingNick] = useState(false);
  const expertise = getCharacterExpertise(character.id);

  useEffect(() => {
    if (visible) setNickDraft(nickname);
  }, [nickname, visible]);

  const saveNickname = async () => {
    if (!onSaveNickname || savingNick) return;
    setSavingNick(true);
    try {
      await onSaveNickname(nickDraft.trim());
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } finally {
      setSavingNick(false);
    }
  };

  const confirmReset = () => {
    if (!onResetSession || resetting) return;
    Alert.alert(
      'Bắt đầu lại với Vy?',
      'Xóa toàn bộ hội thoại, ký ức gắn kết và lịch sử hoạt động. Không hoàn tác được.',
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

          <ScrollView
            bounces={false}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
            style={styles.scroll}
            contentContainerStyle={styles.scrollContent}
          >
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

            {onSaveNickname ? (
              <View style={styles.nicknameBox}>
                <Text style={styles.nicknameLabel}>Vy gọi mình là</Text>
                <View style={styles.nicknameRow}>
                  <TextInput
                    value={nickDraft}
                    onChangeText={setNickDraft}
                    placeholder="vd. Andy, Anh, Lan…"
                    placeholderTextColor={colors.textTertiary}
                    maxLength={24}
                    style={styles.nicknameInput}
                    returnKeyType="done"
                    onSubmitEditing={() => void saveNickname()}
                  />
                  <Pressable
                    onPress={() => void saveNickname()}
                    disabled={savingNick}
                    style={[
                      styles.nicknameSave,
                      { backgroundColor: character.accent },
                    ]}
                  >
                    {savingNick ? (
                      <ActivityIndicator color="#0B1220" size="small" />
                    ) : (
                      <Text style={styles.nicknameSaveText}>Lưu</Text>
                    )}
                  </Pressable>
                </View>
                <Text style={styles.nicknameHint}>
                  Để trống thì gọi &quot;bạn&quot;. Hoặc nói trong chat: gọi tôi
                  là Andy.
                </Text>
              </View>
            ) : null}

            <View style={styles.activityBox}>
              <Text style={styles.activityTitle}>Hoạt động với Vy</Text>
              {activities.length === 0 ? (
                <Text style={styles.activityEmpty}>
                  Chưa có hành động nào. Khi Vy thêm/xóa mã hoặc đổi cách gọi
                  bạn, sẽ hiện ở đây.
                </Text>
              ) : (
                activities.slice(0, 20).map((item, index) => (
                  <View
                    key={item.id}
                    style={[
                      styles.activityRow,
                      index === 0 && styles.activityRowFirst,
                    ]}
                  >
                    <Text style={styles.activityLabel}>{item.label}</Text>
                    <Text style={styles.activityTime}>
                      {formatActivityTime(item.ts)}
                    </Text>
                  </View>
                ))
              )}
            </View>

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
          </ScrollView>
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
    maxHeight: '88%',
  },
  scroll: {
    flexGrow: 0,
  },
  scrollContent: {
    paddingBottom: 4,
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
  nicknameBox: {
    marginBottom: spacing.md,
    padding: spacing.md,
    borderRadius: 12,
    backgroundColor: colors.surface,
  },
  nicknameLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    marginBottom: 8,
    letterSpacing: 0.3,
  },
  nicknameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  nicknameInput: {
    flex: 1,
    minHeight: 40,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: colors.surfaceElevated,
    color: colors.text,
    fontSize: 15,
  },
  nicknameSave: {
    minWidth: 52,
    minHeight: 40,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 12,
  },
  nicknameSaveText: {
    color: '#0B1220',
    fontSize: 14,
    fontWeight: '700',
  },
  nicknameHint: {
    marginTop: 6,
    fontSize: 12,
    color: colors.textTertiary,
  },
  activityBox: {
    marginBottom: spacing.md,
    padding: spacing.md,
    borderRadius: 12,
    backgroundColor: colors.surface,
  },
  activityTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    marginBottom: 8,
    letterSpacing: 0.3,
  },
  activityEmpty: {
    fontSize: 13,
    lineHeight: 18,
    color: colors.textTertiary,
  },
  activityRow: {
    paddingVertical: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    gap: 2,
  },
  activityRowFirst: {
    borderTopWidth: 0,
    paddingTop: 0,
  },
  activityLabel: {
    fontSize: 14,
    lineHeight: 20,
    color: colors.text,
  },
  activityTime: {
    fontSize: 12,
    color: colors.textTertiary,
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
