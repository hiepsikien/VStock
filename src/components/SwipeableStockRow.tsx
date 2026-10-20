import React, { memo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { RectButton } from 'react-native-gesture-handler';
import Swipeable, {
  type SwipeableMethods,
} from 'react-native-gesture-handler/ReanimatedSwipeable';
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

function SwipeableStockRowInner({
  stock,
  pinned = false,
  onPress,
  onPin,
  onAlert,
  onRemove,
  isLast,
  disabled,
}: Props) {
  // RectButton (RNGH) — not RN Pressable — so taps compete correctly with the
  // ReanimatedSwipeable pan gesture (RN Pressable onPress can fail to fire).
  const renderLeft = (
    _progress: unknown,
    _translation: unknown,
    methods: SwipeableMethods,
  ) => (
    <RectButton
      style={[styles.action, styles.pinAction]}
      onPress={() => {
        void Haptics.selectionAsync();
        methods.close();
        onPin(stock);
      }}
    >
      <Text style={styles.actionText}>{pinned ? 'Bỏ ghim' : 'Ghim'}</Text>
    </RectButton>
  );

  const renderRight = (
    _progress: unknown,
    _translation: unknown,
    methods: SwipeableMethods,
  ) => (
    <View style={styles.rightActions}>
      <RectButton
        style={[styles.action, styles.alertAction]}
        onPress={() => {
          void Haptics.selectionAsync();
          methods.close();
          onAlert(stock);
        }}
      >
        <Text style={styles.actionText}>Cảnh báo</Text>
      </RectButton>
      <RectButton
        style={[styles.action, styles.deleteAction]}
        onPress={() => {
          void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
          methods.close();
          onRemove(stock);
        }}
      >
        <Text style={styles.actionText}>Xóa</Text>
      </RectButton>
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

export const SwipeableStockRow = memo(SwipeableStockRowInner, (prev, next) =>
  prev.stock === next.stock &&
  prev.pinned === next.pinned &&
  prev.isLast === next.isLast &&
  prev.disabled === next.disabled &&
  prev.onPress === next.onPress &&
  prev.onPin === next.onPin &&
  prev.onAlert === next.onAlert &&
  prev.onRemove === next.onRemove,
);

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
