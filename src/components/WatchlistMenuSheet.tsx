import React from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { colors, spacing, typography } from '../theme';

type Props = {
  visible: boolean;
  onClose: () => void;
  onManageWatchlists: () => void;
  onManageAlerts: () => void;
};

export function WatchlistMenuSheet({
  visible,
  onClose,
  onManageWatchlists,
  onManageAlerts,
}: Props) {
  const press = (action: () => void) => {
    void Haptics.selectionAsync();
    action();
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} />
      <View style={styles.sheet}>
        <Text style={styles.title}>Tuỳ chọn</Text>

        <Pressable style={styles.item} onPress={() => press(onManageWatchlists)}>
          <Text style={styles.itemText}>Quản lý danh sách</Text>
        </Pressable>
        <Pressable style={styles.item} onPress={() => press(onManageAlerts)}>
          <Text style={styles.itemText}>Quản lý cảnh báo</Text>
        </Pressable>
        <Pressable style={[styles.item, styles.cancel]} onPress={() => press(onClose)}>
          <Text style={styles.cancelText}>Huỷ</Text>
        </Pressable>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
    gap: spacing.sm,
  },
  title: {
    ...typography.title,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  item: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 12,
    paddingHorizontal: spacing.md,
    paddingVertical: 14,
  },
  itemText: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '600',
  },
  cancel: {
    marginTop: spacing.sm,
  },
  cancelText: {
    color: colors.accent,
    fontSize: 16,
    fontWeight: '600',
    textAlign: 'center',
  },
});
