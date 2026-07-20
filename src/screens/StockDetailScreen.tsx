import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import * as Haptics from 'expo-haptics';
import type { RootStackParamList } from '../navigation/types';
import type { ChartRange, Stock } from '../types';
import { fetchHistory, fetchStockDetail } from '../api/client';
import {
  formatChange,
  formatPercent,
  formatPrice,
  formatVolume,
  getFallbackStock,
} from '../data/stocks';
import { PriceChart } from '../components/PriceChart';
import { colors, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Detail'>;

export function StockDetailScreen({ navigation, route }: Props) {
  const insets = useSafeAreaInsets();
  const symbol = route.params.symbol.toUpperCase();
  const [stock, setStock] = useState<Stock | null>(getFallbackStock(symbol) ?? null);
  const [range, setRange] = useState<ChartRange>('1D');
  const [rangePrices, setRangePrices] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const detail = await fetchStockDetail(symbol);
        if (!cancelled) {
          setStock(detail);
          setRangePrices(detail.history['1D']?.length ? detail.history['1D'] : detail.sparkline);
        }
      } catch {
        const fallback = getFallbackStock(symbol);
        if (!cancelled && fallback) {
          setStock(fallback);
          setRangePrices(fallback.history['1D']);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  const onRangeChange = useCallback(
    async (next: ChartRange) => {
      setRange(next);
      if (!stock) return;

      const cached = stock.history[next];
      if (cached && cached.length > 0) {
        setRangePrices(cached);
        return;
      }

      setChartLoading(true);
      try {
        const prices = await fetchHistory(symbol, next);
        setRangePrices(prices);
        setStock((prev) =>
          prev
            ? { ...prev, history: { ...prev.history, [next]: prices } }
            : prev,
        );
      } catch {
        if (stock.history[next]?.length) {
          setRangePrices(stock.history[next]);
        }
      } finally {
        setChartLoading(false);
      }
    },
    [stock, symbol],
  );

  const isUp = (stock?.changePercent ?? 0) >= 0;

  const stats = useMemo(() => {
    if (!stock) return [];
    return [
      { label: 'Mở cửa', value: formatPrice(stock.open, stock.currency) },
      { label: 'Cao', value: formatPrice(stock.high, stock.currency) },
      { label: 'Thấp', value: formatPrice(stock.low, stock.currency) },
      { label: 'KL', value: formatVolume(stock.volume) },
      { label: 'Vốn hóa', value: stock.marketCap },
      { label: 'P/E', value: stock.pe != null ? stock.pe.toFixed(1) : '—' },
    ];
  }, [stock]);

  if (!stock) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <Text style={styles.missing}>Không tìm thấy mã</Text>
        <Pressable onPress={() => navigation.goBack()}>
          <Text style={styles.backLink}>Quay lại</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <StatusBar style="light" />

      <View style={styles.nav}>
        <Pressable
          onPress={() => {
            void Haptics.selectionAsync();
            navigation.goBack();
          }}
          hitSlop={12}
          style={styles.backBtn}
        >
          <Text style={styles.backChevron}>‹</Text>
          <Text style={styles.backLabel}>Watchlist</Text>
        </Pressable>
        <Text style={styles.exchange}>{stock.exchange}</Text>
      </View>

      {loading ? (
        <View style={styles.loading}>
          <ActivityIndicator color={colors.positive} />
        </View>
      ) : (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={{ paddingBottom: insets.bottom + 32 }}
        >
          <View style={styles.hero}>
            <Text style={styles.symbol}>{stock.symbol}</Text>
            <Text style={styles.name}>{stock.name}</Text>
            <Text style={styles.price}>
              {formatPrice(stock.price, stock.currency)} ₫
            </Text>
            <Text
              style={[
                styles.change,
                { color: isUp ? colors.positive : colors.negative },
              ]}
            >
              {formatChange(stock.change)} ({formatPercent(stock.changePercent)})
            </Text>
          </View>

          <View>
            <PriceChart
              prices={rangePrices.length ? rangePrices : stock.sparkline}
              positive={isUp}
              range={range}
              onRangeChange={(r) => void onRangeChange(r)}
            />
            {chartLoading ? (
              <ActivityIndicator
                style={styles.chartSpinner}
                color={colors.textSecondary}
              />
            ) : null}
          </View>

          <View style={styles.stats}>
            {stats.map((item, index) => (
              <View
                key={item.label}
                style={[
                  styles.statRow,
                  index === stats.length - 1 && styles.statRowLast,
                ]}
              >
                <Text style={styles.statLabel}>{item.label}</Text>
                <Text style={styles.statValue}>{item.value}</Text>
              </View>
            ))}
          </View>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  nav: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  backChevron: {
    color: colors.accent,
    fontSize: 32,
    lineHeight: 34,
    marginRight: 2,
    fontWeight: '300',
  },
  backLabel: {
    color: colors.accent,
    fontSize: 17,
  },
  exchange: {
    color: colors.textSecondary,
    fontSize: 13,
    fontWeight: '500',
  },
  hero: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
  },
  symbol: {
    ...typography.title,
    color: colors.text,
  },
  name: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: 2,
  },
  price: {
    ...typography.heroPrice,
    color: colors.text,
    marginTop: spacing.md,
  },
  change: {
    fontSize: 16,
    fontWeight: '500',
    marginTop: 4,
    fontVariant: ['tabular-nums'],
  },
  chartSpinner: {
    marginTop: -8,
    marginBottom: 8,
  },
  stats: {
    marginTop: spacing.xxl,
    marginHorizontal: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingHorizontal: spacing.lg,
  },
  statRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 13,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  statRowLast: {
    borderBottomWidth: 0,
  },
  statLabel: {
    color: colors.textSecondary,
    fontSize: 15,
  },
  statValue: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '500',
    fontVariant: ['tabular-nums'],
  },
  missing: {
    color: colors.text,
    textAlign: 'center',
    marginTop: 80,
    fontSize: 17,
  },
  backLink: {
    color: colors.accent,
    textAlign: 'center',
    marginTop: 12,
    fontSize: 17,
  },
  loading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
