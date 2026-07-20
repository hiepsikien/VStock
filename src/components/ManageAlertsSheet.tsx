import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { useKeyboardBottomInset } from '../hooks/useKeyboardBottomInset';
import type { PriceAlert } from '../storage/alerts';
import { colors, spacing, typography } from '../theme';

type Props = {
  visible: boolean;
  alerts: PriceAlert[];
  onClose: () => void;
  onSave: (id: string, price: number) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
};

export function ManageAlertsSheet({ visible, alerts, onClose, onSave, onDelete }: Props) {
  const keyboardInset = useKeyboardBottomInset();
  const scrollRef = useRef<ScrollView>(null);
  const rowOffsets = useRef<Record<string, number>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!visible) return;
    setDrafts(
      Object.fromEntries(alerts.map((alert) => [alert.id, String(alert.price)])),
    );
    setBusyId(null);
  }, [alerts, visible]);

  const ordered = useMemo(
    () =>
      [...alerts].sort((a, b) =>
        `${a.symbol}_${a.condition}`.localeCompare(`${b.symbol}_${b.condition}`),
      ),
    [alerts],
  );

  const scrollToRow = (id: string) => {
    const y = rowOffsets.current[id];
    if (y == null) return;
    scrollRef.current?.scrollTo({ y: Math.max(0, y - spacing.md), animated: true });
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.container}>
        <Pressable style={styles.backdrop} onPress={onClose} />
        <View style={[styles.sheet, keyboardInset > 0 && { marginBottom: keyboardInset }]}>
          <View style={styles.header}>
            <Text style={styles.title}>Quản lý cảnh báo</Text>
            <Pressable
              onPress={() => {
                void Haptics.selectionAsync();
                onClose();
              }}
            >
              <Text style={styles.close}>Xong</Text>
            </Pressable>
          </View>

          {ordered.length === 0 ? (
            <Text style={styles.empty}>Chưa có cảnh báo nào.</Text>
          ) : (
            <ScrollView
              ref={scrollRef}
              keyboardShouldPersistTaps="handled"
              keyboardDismissMode="interactive"
              contentContainerStyle={styles.list}
            >
              {ordered.map((alert) => {
                const text = drafts[alert.id] ?? String(alert.price);
                const parsed = Number.parseFloat(text.replace(',', '.'));
                const valid = Number.isFinite(parsed) && parsed > 0;
                const unchanged = valid && parsed === alert.price;
                const saving = busyId === `save:${alert.id}`;
                const deleting = busyId === `delete:${alert.id}`;

                return (
                  <View
                    key={alert.id}
                    style={styles.row}
                    onLayout={(event) => {
                      rowOffsets.current[alert.id] = event.nativeEvent.layout.y;
                    }}
                  >
                    <View style={styles.rowHeader}>
                      <Text style={styles.symbol}>
                        {alert.symbol} {alert.condition === 'above' ? '≥' : '≤'}
                      </Text>
                      <Text style={styles.status}>{alert.enabled ? 'Đang bật' : 'Tắt'}</Text>
                    </View>

                    <TextInput
                      value={text}
                      onFocus={() => scrollToRow(alert.id)}
                      onChangeText={(value) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [alert.id]: value,
                        }))
                      }
                      keyboardType="decimal-pad"
                      placeholder="Giá cảnh báo"
                      placeholderTextColor={colors.textTertiary}
                      style={styles.input}
                    />

                    <View style={styles.actions}>
                      <Pressable
                        disabled={!valid || unchanged || saving || deleting}
                        onPress={() => {
                          if (!valid) return;
                          void Haptics.selectionAsync();
                          setBusyId(`save:${alert.id}`);
                          void onSave(alert.id, parsed).finally(() => setBusyId(null));
                        }}
                        style={[
                          styles.actionBtn,
                          (!valid || unchanged || saving || deleting) && styles.actionBtnDisabled,
                        ]}
                      >
                        <Text style={styles.actionText}>{saving ? 'Đang lưu…' : 'Lưu'}</Text>
                      </Pressable>
                      <Pressable
                        disabled={saving || deleting}
                        onPress={() => {
                          void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
                          setBusyId(`delete:${alert.id}`);
                          void onDelete(alert.id).finally(() => setBusyId(null));
                        }}
                        style={[styles.deleteBtn, (saving || deleting) && styles.actionBtnDisabled]}
                      >
                        <Text style={styles.deleteText}>{deleting ? 'Đang xoá…' : 'Xoá'}</Text>
                      </Pressable>
                    </View>
                  </View>
                );
              })}
            </ScrollView>
          )}
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
    justifyContent: 'space-between',
    alignItems: 'center',
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
  empty: {
    color: colors.textSecondary,
    fontSize: 15,
    paddingVertical: spacing.md,
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
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  symbol: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '600',
  },
  status: {
    color: colors.textTertiary,
    fontSize: 12,
    fontWeight: '600',
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    color: colors.text,
    fontSize: 16,
    fontVariant: ['tabular-nums'],
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
