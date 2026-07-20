import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { useFocusEffect } from '@react-navigation/native';
import * as Haptics from 'expo-haptics';
import type { RootStackParamList } from '../navigation/types';
import * as WebBrowser from 'expo-web-browser';
import type { ChartRange, Stock } from '../types';
import type { NewsItem } from '../types/news';
import { fetchHistory, fetchStockDetail, loadSymbolNews } from '../api/client';
import { AlertSheet } from '../components/AlertSheet';
import { NewsRow } from '../components/NewsRow';
import { NewsRowSkeleton } from '../components/Skeleton';
import {
  formatChange,
  formatPercent,
  formatPrice,
  formatVolume,
  getFallbackStock,
} from '../data/stocks';
import { PriceChart } from '../components/PriceChart';
import { colors, spacing, typography } from '../theme';
import { isMarketOpen, marketSessionLabel, REFRESH } from '../utils/marketSession';
import { upsertPriceAlert } from '../storage/alerts';
import { addRecentSymbol } from '../storage/recent';

type Props = NativeStackScreenProps<RootStackParamList, 'Detail'>;

export function StockDetailScreen({ navigation, route }: Props) {
  const insets = useSafeAreaInsets();
  const symbol = route.params.symbol.toUpperCase();
  const [stock, setStock] = useState<Stock | null>(getFallbackStock(symbol) ?? null);
  const [range, setRange] = useState<ChartRange>('1D');
  const [rangePrices, setRangePrices] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(true);
  const [live, setLive] = useState(isMarketOpen());
  const [alertOpen, setAlertOpen] = useState(false);

  const rangeRef = useRef(range);
  rangeRef.current = range;

  const applyDetail = useCallback((detail: Stock) => {
    setStock(detail);
    if (rangeRef.current === '1D') {
      const day = detail.history['1D']?.length ? detail.history['1D'] : detail.sparkline;
      setRangePrices(day);
    }
  }, []);

  const loadDetail = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        const detail = await fetchStockDetail(symbol);
        applyDetail(detail);
      } catch {
        if (!silent) {
          const fallback = getFallbackStock(symbol);
          if (fallback) {
            setStock(fallback);
            setRangePrices(fallback.history['1D']);
          }
        }
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [applyDetail, symbol],
  );

  useEffect(() => {
    void loadDetail(false);
  }, [loadDetail]);

  useEffect(() => {
    let cancelled = false;
    setNewsLoading(true);

    void loadSymbolNews(symbol, 8, {
      onData: (items, fromCache) => {
        if (cancelled) return;
        setNews(items);
        setNewsLoading(false);
      },
    });

    return () => {
      cancelled = true;
    };
  }, [symbol]);

  const openArticle = useCallback(async (item: NewsItem) => {
    if (item.url) {
      await WebBrowser.openBrowserAsync(item.url, {
        presentationStyle: WebBrowser.WebBrowserPresentationStyle.PAGE_SHEET,
        controlsColor: colors.accent,
      });
    }
  }, []);

  useEffect(() => {
    const id = setInterval(() => setLive(isMarketOpen()), 60_000);
    return () => clearInterval(id);
  }, []);

  useFocusEffect(
    useCallback(() => {
      void addRecentSymbol(symbol);
    }, [symbol]),
  );

  useFocusEffect(
    useCallback(() => {
      const quoteTimer = setInterval(() => {
        if (isMarketOpen()) void loadDetail(true);
      }, REFRESH.quotePollMs);

      const chartTimer = setInterval(() => {
        if (!isMarketOpen() || rangeRef.current !== '1D') return;
        void (async () => {
          try {
            const prices = await fetchHistory(symbol, '1D');
            setRangePrices(prices);
            setStock((prev) =>
              prev
                ? {
                    ...prev,
                    sparkline: prices,
                    history: { ...prev.history, '1D': prices },
                  }
                : prev,
            );
          } catch {
            /* keep stale chart */
          }
        })();
      }, REFRESH.chart1dPollMs);

      return () => {
        clearInterval(quoteTimer);
        clearInterval(chartTimer);
      };
    }, [loadDetail, symbol]),
  );

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
        <Pressable
          onPress={() => {
            void Haptics.selectionAsync();
            setAlertOpen(true);
          }}
          hitSlop={8}
        >
          <Text style={styles.alertBtn}>Cảnh báo</Text>
        </Pressable>
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
            <Text style={styles.sessionMeta}>
              {stock.exchange}
              {live ? ' · live' : ` · ${marketSessionLabel()}`}
            </Text>
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

          <View style={styles.newsSection}>
            <Text style={styles.newsHeading}>Tin tức</Text>
            {newsLoading ? (
              <View style={styles.newsCard}>
                {[1, 2, 3].map((i) => (
                  <NewsRowSkeleton key={i} />
                ))}
              </View>
            ) : news.length === 0 ? (
              <Text style={styles.newsEmpty}>Chưa có tin cho mã này</Text>
            ) : (
              <View style={styles.newsCard}>
                {news.map((item, index) => (
                  <NewsRow
                    key={item.id}
                    item={item}
                    compact
                    isLast={index === news.length - 1}
                    onPress={(n) => void openArticle(n)}
                  />
                ))}
              </View>
            )}
          </View>
        </ScrollView>
      )}

      <AlertSheet
        visible={alertOpen}
        symbol={stock.symbol}
        currentPrice={stock.price}
        onClose={() => setAlertOpen(false)}
        onSave={(condition, price) => {
          void upsertPriceAlert({
            symbol: stock.symbol,
            condition,
            price,
            enabled: true,
          });
        }}
      />
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
  alertBtn: {
    color: colors.accent,
    fontSize: 16,
    fontWeight: '600',
  },
  sessionMeta: {
    color: colors.textSecondary,
    fontSize: 13,
    marginTop: 4,
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
  newsSection: {
    marginTop: spacing.xxl,
    marginHorizontal: spacing.lg,
  },
  newsHeading: {
    ...typography.title,
    fontSize: 20,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  newsCard: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    overflow: 'hidden',
  },
  newsSpinner: {
    marginVertical: spacing.lg,
  },
  newsEmpty: {
    color: colors.textSecondary,
    fontSize: 15,
    paddingVertical: spacing.md,
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
