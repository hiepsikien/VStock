import React, { useRef } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Swipeable } from 'react-native-gesture-handler';
import * as Haptics from 'expo-haptics';
import type { Stock } from '../types';
import { StockRow } from './StockRow';
import { colors, spacing } from '../theme';

type Props = {
  stock: Stock;
  pinned?: boolean;
  onPress: (stock: Stock) => void;
  onPin: (stock: Stock) => void;
  onAlert: (stock: Stock) => void;
  onRemove: (stock: Stock) => void;
  isLast?: boolean;
  disabled?: boolean;
};

export function SwipeableStockRow({
  stock,
  pinned = false,
  onPress,
  onPin,
  onAlert,
  onRemove,
  isLast,
  disabled,
}: Props) {
  const ref = useRef<Swipeable>(null);

  const renderLeft = () => (
    <Pressable
      style={[styles.action, styles.pinAction]}
      onPress={() => {
        void Haptics.selectionAsync();
        ref.current?.close();
        onPin(stock);
      }}
    >
      <Text style={styles.actionText}>{pinned ? 'Bỏ ghim' : 'Ghim'}</Text>
    </Pressable>
  );

  const renderRight = () => (
    <View style={styles.rightActions}>
      <Pressable
        style={[styles.action, styles.alertAction]}
        onPress={() => {
          void Haptics.selectionAsync();
          ref.current?.close();
          onAlert(stock);
        }}
      >
        <Text style={styles.actionText}>Cảnh báo</Text>
      </Pressable>
      <Pressable
        style={[styles.action, styles.deleteAction]}
        onPress={() => {
          void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
          ref.current?.close();
          onRemove(stock);
        }}
      >
        <Text style={styles.actionText}>Xóa</Text>
      </Pressable>
    </View>
  );

  if (disabled) {
    return (
      <StockRow
        stock={stock}
        pinned={pinned}
        onPress={onPress}
        isLast={isLast}
      />
    );
  }

  return (
    <Swipeable
      ref={ref}
      renderLeftActions={renderLeft}
      renderRightActions={renderRight}
      overshootLeft={false}
      overshootRight={false}
      friction={2}
    >
      <View style={styles.rowWrap}>
        <StockRow
          stock={stock}
          pinned={pinned}
          onPress={onPress}
          isLast={isLast}
        />
      </View>
    </Swipeable>
  );
}

const styles = StyleSheet.create({
  rowWrap: {
    backgroundColor: colors.surface,
  },
  action: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    minWidth: 80,
  },
  pinAction: {
    backgroundColor: colors.accent,
  },
  alertAction: {
    backgroundColor: '#5856D6',
  },
  deleteAction: {
    backgroundColor: colors.negative,
  },
  rightActions: {
    flexDirection: 'row',
  },
  actionText: {
    color: colors.text,
    fontWeight: '700',
    fontSize: 13,
  },
});
