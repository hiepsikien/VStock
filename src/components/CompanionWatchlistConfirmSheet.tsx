import React from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import {
  actionLabel,
  type CompanionWatchlistAction,
} from '../companion/watchlistActions';
import { colors, spacing } from '../theme';

type Props = {
  visible: boolean;
  actions: CompanionWatchlistAction[];
  accent: string;
  onConfirm: (action: CompanionWatchlistAction) => void;
  onClose: () => void;
};

function actionDetail(action: CompanionWatchlistAction): string | null {
  if (action.type === 'create_watchlist') {
    const syms = action.symbols?.length
      ? action.symbols
      : action.symbol
        ? [action.symbol]
        : [];
    if (syms.length) return syms.join(' · ');
    return 'Danh sách trống, thêm mã sau';
  }
  if (action.type === 'add_symbol') {
    return action.watchlistName
      ? `Vào “${action.watchlistName}”`
      : 'Chọn danh sách ở bước tiếp theo';
  }
  if (action.type === 'suggest_add_symbol') {
    return 'Chọn danh sách ở bước tiếp theo';
  }
  return null;
}

export function CompanionWatchlistConfirmSheet({
  visible,
  actions,
  accent,
  onConfirm,
  onClose,
}: Props) {
  if (!actions.length) return null;

  const close = () => {
    void Haptics.selectionAsync();
    onClose();
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={close}
    >
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>Xác nhận thao tác</Text>
          <Text style={styles.subtitle}>
            Vy đề xuất thay đổi danh sách theo dõi của bạn:
          </Text>

          <View style={styles.actionList}>
            {actions.map((action, index) => {
              const detail = actionDetail(action);
              return (
                <Pressable
                  key={`${action.type}-${index}`}
                  onPress={() => {
                    void Haptics.notificationAsync(
                      Haptics.NotificationFeedbackType.Success,
                    );
                    onConfirm(action);
                  }}
                  style={[
                    styles.actionBtn,
                    {
                      backgroundColor: accent,
                      borderColor: `${accent}88`,
                    },
                  ]}
                >
                  <Text style={styles.actionLabel}>{actionLabel(action)}</Text>
                  {detail ? (
                    <Text style={styles.actionDetail}>{detail}</Text>
                  ) : null}
                </Pressable>
              );
            })}
          </View>

          <Pressable onPress={close} style={styles.cancelBtn} hitSlop={8}>
            <Text style={styles.cancelText}>Huỷ</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
  },
  card: {
    width: '100%',
    maxWidth: 360,
    backgroundColor: colors.surface,
    borderRadius: 20,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
    gap: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separator,
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 14,
    lineHeight: 20,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  actionList: {
    gap: 10,
    marginTop: 4,
  },
  actionBtn: {
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderWidth: StyleSheet.hairlineWidth,
  },
  actionLabel: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
    textAlign: 'center',
  },
  actionDetail: {
    color: 'rgba(255,255,255,0.85)',
    fontSize: 13,
    textAlign: 'center',
    marginTop: 4,
  },
  cancelBtn: {
    alignItems: 'center',
    paddingVertical: 10,
    marginTop: 4,
  },
  cancelText: {
    color: colors.textSecondary,
    fontSize: 16,
    fontWeight: '600',
  },
});
