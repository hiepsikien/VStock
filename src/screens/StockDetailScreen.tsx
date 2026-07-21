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
import { fetchHistory, loadHistory, loadStockDetail, loadSymbolNews } from '../api/client';
import { AlertSheet } from '../components/AlertSheet';
import { ApiStatusBanner } from '../components/ApiStatusBanner';
import { NewsRow } from '../components/NewsRow';
import { NewsRowSkeleton } from '../components/Skeleton';
import {
  formatChange,
  formatPercent,
  formatPrice,
  formatVolume,
  formatMarketCapLabel,
  getFallbackStock,
} from '../data/stocks';
import { PriceChart } from '../components/PriceChart';
import { colors, spacing, typography } from '../theme';
import { isMarketOpen, marketSessionLabel, REFRESH } from '../utils/marketSession';
import { upsertPriceAlert } from '../storage/alerts';
import { syncPriceAlertBackgroundTask } from '../tasks/priceAlertBackgroundTask';
import { addRecentSymbol } from '../storage/recent';
import { formatCacheAge } from '../storage/cacheUtils';
import { isCommodityStrip, isIndexLikeDetail } from '../utils/marketIndices';

type Props = NativeStackScreenProps<RootStackParamList, 'Detail'>;

export function StockDetailScreen({ navigation, route }: Props) {
  const insets = useSafeAreaInsets();
  const symbol = route.params.symbol.toUpperCase();
  const [stock, setStock] = useState<Stock | null>(null);
  const [range, setRange] = useState<ChartRange>('1D');
  const [rangePrices, setRangePrices] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [usingOfflineCache, setUsingOfflineCache] = useState(false);
  const [cacheFetchedAt, setCacheFetchedAt] = useState<number | null>(null);
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
        await loadStockDetail(symbol, {
          onData: (detail, fromCache, fetchedAt) => {
            applyDetail(detail);
            if (fromCache) {
              setUsingOfflineCache(true);
              setCacheFetchedAt(fetchedAt ?? null);
            } else {
              setUsingOfflineCache(false);
              setCacheFetchedAt(null);
            }
            if (!silent) setLoading(false);
          },
        });
      } catch {
        if (!silent) {
          const fallback = getFallbackStock(symbol);
          if (fallback) {
            setStock(fallback);
            setRangePrices(fallback.history['1D']);
            setUsingOfflineCache(false);
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
      onData: (items) => {
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
      if (isIndexLikeDetail(symbol)) return;
      void addRecentSymbol(symbol);
    }, [symbol]),
  );

  useFocusEffect(
    useCallback(() => {
      const alwaysPoll = isCommodityStrip(symbol);
      const quoteTimer = setInterval(() => {
        if (alwaysPoll || isMarketOpen()) void loadDetail(true);
      }, REFRESH.quotePollMs);

      const chartTimer = setInterval(() => {
        if ((!alwaysPoll && !isMarketOpen()) || rangeRef.current !== '1D') return;
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
        await loadHistory(symbol, next, {
          onData: (prices, fromCache, fetchedAt) => {
            setRangePrices(prices);
            setStock((prev) =>
              prev
                ? { ...prev, history: { ...prev.history, [next]: prices } }
                : prev,
            );
            if (fromCache) {
              setUsingOfflineCache(true);
              setCacheFetchedAt(fetchedAt ?? null);
            }
          },
        });
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
  const isIndexLike = isIndexLikeDetail(symbol);
  const isCommodity = isCommodityStrip(symbol);
  const isUsd = (stock?.currency ?? '') === 'USD';
  const sessionLive = isCommodity || live;

  const formatStatValue = useCallback(
    (value: number) => {
      if (isUsd) return formatPrice(value, 'USD');
      if (isIndexLike) return formatPrice(value, '');
      return formatPrice(value, stock?.currency ?? '₫');
    },
    [isIndexLike, isUsd, stock?.currency],
  );

  const stats = useMemo(() => {
    if (!stock) return [] as { label: string; value: string }[];
    if (isIndexLike) {
      const priorClose = stock.priorClose ?? stock.price - stock.change;
      return [
        { label: 'Mở', value: formatStatValue(stock.open) },
        { label: 'Cao', value: formatStatValue(stock.high) },
        { label: 'Thấp', value: formatStatValue(stock.low) },
        { label: 'Đóng', value: formatStatValue(priorClose) },
      ];
    }
    return [
      { label: 'Mở', value: formatStatValue(stock.open) },
      { label: 'Cao', value: formatStatValue(stock.high) },
      { label: 'Thấp', value: formatStatValue(stock.low) },
      { label: 'KL', value: formatVolume(stock.volume) },
      { label: 'P/E', value: stock.pe != null ? stock.pe.toFixed(1) : '—' },
      { label: 'Vốn hóa', value: formatMarketCapLabel(stock.marketCap) },
    ];
  }, [stock, isIndexLike, formatStatValue]);

  // Apple Stocks compact strip: 2 columns, fill top→bottom (3 rows for equities).
  const statColumns = useMemo(() => {
    if (!stats.length) return [] as { label: string; value: string }[][];
    const columnCount = 2;
    const rowsPerCol = Math.ceil(stats.length / columnCount);
    const cols: { label: string; value: string }[][] = [];
    for (let c = 0; c < columnCount; c += 1) {
      const start = c * rowsPerCol;
      const slice = stats.slice(start, start + rowsPerCol);
      if (slice.length) cols.push(slice);
    }
    return cols;
  }, [stats]);

  if (loading && !stock) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <StatusBar style="light" />
        <View style={styles.loading}>
          <ActivityIndicator color={colors.positive} />
        </View>
      </View>
    );
  }

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
        {!isIndexLike ? (
          <Pressable
            onPress={() => {
              void Haptics.selectionAsync();
              setAlertOpen(true);
            }}
            hitSlop={8}
          >
            <Text style={styles.alertBtn}>Cảnh báo</Text>
          </Pressable>
        ) : (
          <View style={styles.navSpacer} />
        )}
      </View>

      {usingOfflineCache ? (
        <ApiStatusBanner
          message={`Dữ liệu đã lưu · cập nhật ${formatCacheAge(cacheFetchedAt ?? Date.now())}`}
          onRetry={() => void loadDetail(true)}
        />
      ) : null}

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
              {sessionLive ? ' · live' : ` · ${marketSessionLabel()}`}
            </Text>
            <Text style={styles.price}>
              {isUsd
                ? formatPrice(stock.price, 'USD')
                : `${formatPrice(stock.price, stock.currency)}${isIndexLike ? '' : ' ₫'}`}
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

          {statColumns.length > 0 ? (
            <View style={styles.stats}>
              {statColumns.map((col, colIndex) => (
                <View
                  key={`col-${colIndex}`}
                  style={[
                    styles.statColumn,
                    colIndex < statColumns.length - 1 && styles.statColumnDivider,
                  ]}
                >
                  {col.map((item) => (
                    <View key={item.label} style={styles.statRow}>
                      <Text style={styles.statLabel} numberOfLines={1}>
                        {item.label}
                      </Text>
                      <Text style={styles.statValue} numberOfLines={1}>
                        {item.value}
                      </Text>
                    </View>
                  ))}
                </View>
              ))}
            </View>
          ) : null}

          <View style={styles.newsSection}>
            <Text style={styles.newsHeading}>
              {isIndexLike ? 'Tin liên quan' : 'Tin tức'}
            </Text>
            {newsLoading ? (
              <View style={styles.newsCard}>
                {[1, 2, 3].map((i) => (
                  <NewsRowSkeleton key={i} />
                ))}
              </View>
            ) : news.length === 0 ? (
              <Text style={styles.newsEmpty}>
                {isIndexLike
                  ? 'Chưa có tin liên quan'
                  : 'Chưa có tin cho mã này'}
              </Text>
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

      {!isIndexLike ? (
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
            }).then(() => syncPriceAlertBackgroundTask());
          }}
        />
      ) : null}
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
  navSpacer: {
    width: 72,
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
    marginTop: spacing.lg,
    marginHorizontal: spacing.lg,
    paddingTop: spacing.md,
    flexDirection: 'row',
    alignItems: 'flex-start',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(255,255,255,0.12)',
  },
  statColumn: {
    flex: 1,
    gap: 11,
    paddingHorizontal: 12,
  },
  statColumnDivider: {
    borderRightWidth: StyleSheet.hairlineWidth,
    borderRightColor: 'rgba(255,255,255,0.12)',
  },
  statRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    gap: 8,
    minHeight: 18,
  },
  statLabel: {
    flexShrink: 1,
    color: colors.textSecondary,
    fontSize: 13,
  },
  statValue: {
    flexGrow: 0,
    flexShrink: 1,
    maxWidth: '62%',
    color: colors.text,
    fontSize: 13,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
    textAlign: 'right',
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
