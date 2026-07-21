import React, { memo, useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import type { Stock } from '../types';
import { formatChange, formatPercent, formatPrice } from '../data/stocks';
import { colors, spacing, typography } from '../theme';
import { Sparkline } from './Sparkline';

type Props = {
  stock: Stock;
  onPress: (stock: Stock) => void;
  onLongPress?: (stock: Stock) => void;
  editing?: boolean;
  onRemove?: (stock: Stock) => void;
  pinned?: boolean;
  isLast?: boolean;
};

const FLASH_MS = 280;
const RIGHT_COL_WIDTH = 112;

function StockRowInner({
  stock,
  onPress,
  onLongPress,
  editing = false,
  onRemove,
  pinned = false,
  isLast = false,
}: Props) {
  const isUp = stock.changePercent >= 0;
  const tint = isUp ? colors.positive : colors.negative;

  const prevPrice = useRef(stock.price);
  const flashOpacity = useRef(new Animated.Value(0)).current;
  const [flashUp, setFlashUp] = useState(true);
  const [flashKey, setFlashKey] = useState(0);

  useEffect(() => {
    if (prevPrice.current === stock.price) return;
    const up = stock.price > prevPrice.current;
    prevPrice.current = stock.price;
    setFlashUp(up);
    setFlashKey((k) => k + 1);
  }, [stock.price]);

  useEffect(() => {
    if (flashKey === 0) return;
    flashOpacity.stopAnimation();
    flashOpacity.setValue(0.4);
    Animated.timing(flashOpacity, {
      toValue: 0,
      duration: FLASH_MS,
      useNativeDriver: true,
    }).start();
  }, [flashKey, flashOpacity]);

  return (
    <Pressable
      onPress={() => {
        if (editing) return;
        void Haptics.selectionAsync();
        onPress(stock);
      }}
      onLongPress={
        !editing && onLongPress
          ? () => {
              onLongPress(stock);
            }
          : undefined
      }
      delayLongPress={350}
      style={({ pressed }) => [
        styles.row,
        !isLast && styles.rowBorder,
        pressed && !editing && styles.pressed,
      ]}
      accessibilityRole="button"
      accessibilityLabel={`${stock.symbol}, ${formatPrice(stock.price, stock.currency)}, ${formatPercent(stock.changePercent)}`}
    >
      {editing ? (
        <Pressable
          onPress={() => {
            void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
            onRemove?.(stock);
          }}
          style={styles.removeBtn}
          hitSlop={8}
        >
          <Text style={styles.removeIcon}>−</Text>
        </Pressable>
      ) : null}

      <View style={[styles.main, editing && styles.mainEditing]}>
        <View style={styles.left}>
          <View style={styles.symbolRow}>
            {pinned ? <View style={styles.pinDot} /> : null}
            <Text style={styles.symbol}>{stock.symbol}</Text>
            <View style={styles.exchangePill}>
              <Text style={styles.exchangeText}>{stock.exchange}</Text>
            </View>
          </View>
          <Text style={styles.name} numberOfLines={1}>
            {stock.name}
          </Text>
        </View>

        {!editing ? (
          <View style={styles.chart}>
            <Sparkline
              data={stock.sparkline}
              positive={isUp}
              width={72}
              height={32}
            />
          </View>
        ) : null}

        <View style={styles.right}>
          <View style={styles.priceWrap}>
            <Animated.View
              pointerEvents="none"
              style={[
                styles.priceFlash,
                {
                  opacity: flashOpacity,
                  backgroundColor: flashUp ? colors.positive : colors.negative,
                },
              ]}
            />
            <Text style={styles.price}>{formatPrice(stock.price, stock.currency)}</Text>
          </View>
          <View style={[styles.changeRow, { backgroundColor: `${tint}22` }]}>
            <Text style={[styles.changeAbs, { color: tint }]}>
              {formatChange(stock.change)}
            </Text>
            <Text style={[styles.changePct, { color: tint }]}>
              {formatPercent(stock.changePercent)}
            </Text>
          </View>
        </View>
      </View>
    </Pressable>
  );
}

export const StockRow = memo(StockRowInner, (prev, next) =>
  prev.stock === next.stock &&
  prev.editing === next.editing &&
  prev.pinned === next.pinned &&
  prev.isLast === next.isLast &&
  prev.onPress === next.onPress &&
  prev.onRemove === next.onRemove &&
  prev.onLongPress === next.onLongPress,
);

const styles = StyleSheet.create({
  row: {
    paddingHorizontal: spacing.lg,
    paddingVertical: 12,
    minHeight: 68,
  },
  rowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  pressed: {
    opacity: 0.85,
  },
  removeBtn: {
    position: 'absolute',
    left: spacing.lg,
    top: '50%',
    marginTop: -14,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.negative,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 2,
  },
  removeIcon: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '600',
    lineHeight: 24,
    marginTop: -1,
  },
  main: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  mainEditing: {
    paddingLeft: 36,
  },
  left: {
    flex: 1,
    paddingRight: spacing.sm,
    minWidth: 0,
  },
  symbolRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  pinDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.positive,
  },
  symbol: {
    ...typography.symbol,
    color: colors.text,
  },
  exchangePill: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 4,
    paddingHorizontal: 5,
    paddingVertical: 1,
  },
  exchangeText: {
    fontSize: 9,
    fontWeight: '700',
    color: colors.textTertiary,
    letterSpacing: 0.4,
  },
  name: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 3,
  },
  chart: {
    width: 76,
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 4,
  },
  right: {
    width: RIGHT_COL_WIDTH,
    alignItems: 'flex-end',
  },
  priceWrap: {
    alignSelf: 'stretch',
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 5,
    paddingHorizontal: 2,
    paddingVertical: 1,
  },
  priceFlash: {
    ...StyleSheet.absoluteFillObject,
  },
  price: {
    ...typography.price,
    color: colors.text,
    textAlign: 'right',
    width: '100%',
  },
  changeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 4,
    minWidth: RIGHT_COL_WIDTH - 4,
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 3,
  },
  changeAbs: {
    fontSize: 12,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
    textAlign: 'right',
    minWidth: 48,
  },
  changePct: {
    fontSize: 12,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
    textAlign: 'right',
    minWidth: 52,
  },
});
