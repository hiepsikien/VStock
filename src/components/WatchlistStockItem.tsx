import React, { memo } from 'react';
import { StyleSheet, View } from 'react-native';
import type { Stock } from '../types';
import { colors, spacing } from '../theme';
import { StockRow } from './StockRow';
import { SwipeableStockRow } from './SwipeableStockRow';

type Props = {
  stock: Stock;
  isFirst: boolean;
  isLast: boolean;
  editing: boolean;
  pinned: boolean;
  onPress: (stock: Stock) => void;
  onRemove: (stock: Stock) => void;
  onPin: (stock: Stock) => void;
  onAlert: (stock: Stock) => void;
};

function WatchlistStockItemInner({
  stock,
  isFirst,
  isLast,
  editing,
  pinned,
  onPress,
  onRemove,
  onPin,
  onAlert,
}: Props) {
  const wrapStyle = [
    styles.groupedRow,
    isFirst && styles.groupTop,
    isLast && styles.groupBottom,
  ];

  if (editing) {
    return (
      <View style={wrapStyle}>
        <StockRow
          stock={stock}
          onPress={onPress}
          editing
          onRemove={onRemove}
          pinned={pinned}
          isLast={isLast}
        />
      </View>
    );
  }

  return (
    <View style={[wrapStyle, styles.swipeWrap]}>
      <SwipeableStockRow
        stock={stock}
        pinned={pinned}
        onPress={onPress}
        onPin={onPin}
        onAlert={onAlert}
        onRemove={onRemove}
        isLast={isLast}
      />
    </View>
  );
}

export const WatchlistStockItem = memo(WatchlistStockItemInner, (prev, next) =>
  prev.stock === next.stock &&
  prev.isFirst === next.isFirst &&
  prev.isLast === next.isLast &&
  prev.editing === next.editing &&
  prev.pinned === next.pinned &&
  prev.onPress === next.onPress &&
  prev.onRemove === next.onRemove &&
  prev.onPin === next.onPin &&
  prev.onAlert === next.onAlert,
);

const styles = StyleSheet.create({
  groupedRow: {
    marginHorizontal: spacing.lg,
    backgroundColor: colors.surface,
    overflow: 'hidden',
  },
  groupTop: {
    borderTopLeftRadius: 14,
    borderTopRightRadius: 14,
  },
  groupBottom: {
    borderBottomLeftRadius: 14,
    borderBottomRightRadius: 14,
  },
  swipeWrap: {
    padding: 0,
    overflow: 'hidden',
  },
});
