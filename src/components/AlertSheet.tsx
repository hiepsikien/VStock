import React from 'react';
import { Alert, Modal, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { useKeyboardBottomInset } from '../hooks/useKeyboardBottomInset';
import type { AlertCondition } from '../storage/alerts';
import { alertDeliveryHint } from '../utils/priceAlertNotify';
import { isPriceAlreadyThroughAlert } from '../utils/priceAlertLogic';
import { colors, spacing, typography } from '../theme';

type Props = {
  visible: boolean;
  symbol: string;
  currentPrice: number;
  onClose: () => void;
  onSave: (condition: AlertCondition, price: number) => void;
};

export function AlertSheet({ visible, symbol, currentPrice, onClose, onSave }: Props) {
  const keyboardInset = useKeyboardBottomInset();
  const [condition, setCondition] = React.useState<AlertCondition>('above');
  const [priceText, setPriceText] = React.useState('');

  React.useEffect(() => {
    if (!visible) return;
    setCondition('above');
    setPriceText(currentPrice > 0 ? currentPrice.toFixed(2) : '');
    // Snapshot currentPrice when the sheet opens; don't overwrite in-progress edits on live ticks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, symbol]);

  const price = parseFloat(priceText.replace(',', '.'));
  const hasLivePrice = Number.isFinite(currentPrice) && currentPrice > 0;
  const valid = Number.isFinite(price) && price > 0 && hasLivePrice;
  const alreadyThrough = valid && isPriceAlreadyThroughAlert(condition, price, currentPrice);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.container}>
        <Pressable style={styles.backdrop} onPress={onClose} />
        <View style={[styles.sheet, keyboardInset > 0 && { marginBottom: keyboardInset }]}>
          <Text style={styles.title}>Cảnh báo giá · {symbol}</Text>
          <Text style={styles.subtitle}>
            {hasLivePrice ? `Giá hiện tại: ${currentPrice.toFixed(2)}` : 'Chưa có giá live để đặt cảnh báo'}
          </Text>
          <Text style={styles.hint}>{alertDeliveryHint()}</Text>

          <View style={styles.row}>
            {(['above', 'below'] as AlertCondition[]).map((c) => (
              <Pressable
                key={c}
                onPress={() => {
                  void Haptics.selectionAsync();
                  setCondition(c);
                }}
                style={[styles.chip, condition === c && styles.chipActive]}
              >
                <Text style={[styles.chipText, condition === c && styles.chipTextActive]}>
                  {c === 'above' ? 'Trên mức' : 'Dưới mức'}
                </Text>
              </Pressable>
            ))}
          </View>

          <TextInput
            value={priceText}
            onChangeText={setPriceText}
            keyboardType="decimal-pad"
            placeholder="Giá mục tiêu"
            placeholderTextColor={colors.textTertiary}
            style={styles.input}
          />

          {alreadyThrough ? (
            <Text style={styles.warn}>
              {currentPrice === price
                ? 'Giá đang đúng mức này. Cảnh báo sẽ báo khi giá cắt qua, không báo ngay.'
                : 'Giá hiện tại đã qua mức này. Cảnh báo sẽ chờ giá cắt lại từ phía còn lại.'}
            </Text>
          ) : null}

          <Pressable
            disabled={!valid}
            onPress={() => {
              if (!valid) return;
              void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
              onSave(condition, price);
              Alert.alert(
                'Đã lưu cảnh báo',
                `${symbol} · ${condition === 'above' ? '≥' : '≤'} ${price.toFixed(2)}`,
              );
              onClose();
            }}
            style={[styles.saveBtn, !valid && styles.saveBtnDisabled]}
          >
            <Text style={styles.saveText}>Lưu cảnh báo</Text>
          </Pressable>
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
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  title: {
    ...typography.title,
    color: colors.text,
  },
  subtitle: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 4,
  },
  hint: {
    fontSize: 12,
    color: colors.textTertiary,
    lineHeight: 17,
    marginTop: spacing.sm,
    marginBottom: spacing.lg,
  },
  warn: {
    fontSize: 12,
    color: colors.accent,
    lineHeight: 17,
    marginTop: -spacing.md,
    marginBottom: spacing.lg,
  },
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  chip: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: colors.surfaceElevated,
    alignItems: 'center',
  },
  chipActive: {
    borderWidth: 1,
    borderColor: colors.positive,
  },
  chipText: {
    color: colors.textSecondary,
    fontWeight: '600',
  },
  chipTextActive: {
    color: colors.positive,
  },
  input: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 10,
    paddingHorizontal: spacing.md,
    paddingVertical: 14,
    color: colors.text,
    fontSize: 18,
    fontVariant: ['tabular-nums'],
    marginBottom: spacing.lg,
  },
  saveBtn: {
    backgroundColor: colors.accent,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  saveBtnDisabled: {
    opacity: 0.45,
  },
  saveText: {
    color: colors.text,
    fontSize: 17,
    fontWeight: '600',
  },
});
