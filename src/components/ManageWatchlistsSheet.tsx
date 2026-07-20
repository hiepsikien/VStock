import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { useKeyboardBottomInset } from '../hooks/useKeyboardBottomInset';
import type { Watchlist } from '../storage/watchlist';
import { colors, spacing, typography } from '../theme';

type Props = {
  visible: boolean;
  lists: Watchlist[];
  activeId: string;
  onClose: () => void;
  onRename: (id: string, name: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
};

export function ManageWatchlistsSheet({
  visible,
  lists,
  activeId,
  onClose,
  onRename,
  onDelete,
}: Props) {
  const keyboardInset = useKeyboardBottomInset();
  const scrollRef = useRef<ScrollView>(null);
  const rowOffsets = useRef<Record<string, number>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!visible) return;
    setDrafts(
      Object.fromEntries(lists.map((list) => [list.id, list.name])),
    );
    setBusyId(null);
  }, [lists, visible]);

  const canDelete = useMemo(() => lists.length > 1, [lists.length]);

  const scrollToRow = (id: string) => {
    const y = rowOffsets.current[id];
    if (y == null) return;
    scrollRef.current?.scrollTo({ y: Math.max(0, y - spacing.md), animated: true });
  };

  const requestDelete = (list: Watchlist) => {
    void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);

    const performDelete = () => {
      setBusyId(`delete:${list.id}`);
      void onDelete(list.id).finally(() => setBusyId(null));
    };

    if (list.symbols.length === 0) {
      performDelete();
      return;
    }

    Alert.alert(
      'Xoá danh sách?',
      `"${list.name}" có ${list.symbols.length} mã. Thao tác này không thể hoàn tác.`,
      [
        { text: 'Huỷ', style: 'cancel' },
        { text: 'Xoá', style: 'destructive', onPress: performDelete },
      ],
    );
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.container}>
        <Pressable style={styles.backdrop} onPress={onClose} />
        <View style={[styles.sheet, keyboardInset > 0 && { marginBottom: keyboardInset }]}>
          <View style={styles.header}>
            <Text style={styles.title}>Quản lý danh sách</Text>
            <Pressable
              onPress={() => {
                void Haptics.selectionAsync();
                onClose();
              }}
            >
              <Text style={styles.close}>Xong</Text>
            </Pressable>
          </View>

          <ScrollView
            ref={scrollRef}
            keyboardShouldPersistTaps="handled"
            keyboardDismissMode="interactive"
            contentContainerStyle={styles.list}
          >
            {lists.map((list) => {
              const draft = drafts[list.id] ?? list.name;
              const trimmed = draft.trim();
              const unchanged = trimmed === list.name;
              const saving = busyId === `rename:${list.id}`;
              const deleting = busyId === `delete:${list.id}`;
              return (
                <View
                  key={list.id}
                  style={styles.row}
                  onLayout={(event) => {
                    rowOffsets.current[list.id] = event.nativeEvent.layout.y;
                  }}
                >
                  <View style={styles.rowHeader}>
                    <Text style={styles.badge}>
                      {list.id === activeId ? 'Đang dùng' : 'Danh sách'}
                    </Text>
                    <Text style={styles.count}>{list.symbols.length} mã</Text>
                  </View>

                  <TextInput
                    value={draft}
                    onFocus={() => scrollToRow(list.id)}
                    onChangeText={(value) =>
                      setDrafts((prev) => ({
                        ...prev,
                        [list.id]: value,
                      }))
                    }
                    style={styles.input}
                    placeholder="Tên danh sách"
                    placeholderTextColor={colors.textTertiary}
                  />

                  <View style={styles.actions}>
                    <Pressable
                      disabled={saving || deleting || unchanged || trimmed.length === 0}
                      onPress={() => {
                        void Haptics.selectionAsync();
                        setBusyId(`rename:${list.id}`);
                        void onRename(list.id, trimmed).finally(() => setBusyId(null));
                      }}
                      style={[
                        styles.actionBtn,
                        (saving || deleting || unchanged || trimmed.length === 0) &&
                          styles.actionBtnDisabled,
                      ]}
                    >
                      <Text style={styles.actionText}>{saving ? 'Đang lưu…' : 'Lưu tên'}</Text>
                    </Pressable>

                    <Pressable
                      disabled={!canDelete || saving || deleting}
                      onPress={() => requestDelete(list)}
                      style={[
                        styles.deleteBtn,
                        (!canDelete || saving || deleting) && styles.actionBtnDisabled,
                      ]}
                    >
                      <Text style={styles.deleteText}>{deleting ? 'Đang xoá…' : 'Xoá'}</Text>
                    </Pressable>
                  </View>
                </View>
              );
            })}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xxl,
    maxHeight: '78%',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  title: {
    ...typography.title,
    color: colors.text,
  },
  close: {
    color: colors.accent,
    fontSize: 16,
    fontWeight: '600',
  },
  list: {
    gap: spacing.sm,
    paddingBottom: spacing.md,
  },
  row: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 12,
    padding: spacing.md,
    gap: spacing.sm,
  },
  rowHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  badge: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  count: {
    fontSize: 12,
    color: colors.textTertiary,
    fontWeight: '600',
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    color: colors.text,
    fontSize: 16,
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  actionBtn: {
    flex: 1,
    borderRadius: 10,
    backgroundColor: colors.accent,
    paddingVertical: 10,
    alignItems: 'center',
  },
  actionBtnDisabled: {
    opacity: 0.45,
  },
  actionText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
  deleteBtn: {
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.negative,
    paddingHorizontal: spacing.md,
    justifyContent: 'center',
  },
  deleteText: {
    color: colors.negative,
    fontSize: 14,
    fontWeight: '600',
  },
});
