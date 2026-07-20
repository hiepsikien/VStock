import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  SectionList,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as WebBrowser from 'expo-web-browser';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import * as Haptics from 'expo-haptics';
import type { RootStackParamList } from '../navigation/types';
import {
  DEFAULT_SYMBOLS,
  fetchWatchlist,
  loadMarketNews,
  searchMarketSymbols,
  type MarketSymbol,
} from '../api/client';
import { useMarketPolling } from '../hooks/useMarketPolling';
import { FALLBACK_WATCHLIST } from '../data/stocks';
import {
  addWatchlistSymbol,
  loadWatchlistSymbols,
  removeWatchlistSymbol,
} from '../storage/watchlist';
import type { Stock } from '../types';
import type { NewsItem } from '../types/news';
import { NewsRow } from '../components/NewsRow';
import { SearchResultRow } from '../components/SearchResultRow';
import { SortChips } from '../components/SortChips';
import { StockRow } from '../components/StockRow';
import { WatchlistSummary } from '../components/WatchlistSummary';
import { colors, spacing, typography } from '../theme';
import { isMarketOpen, marketSessionLabel, REFRESH } from '../utils/marketSession';
import {
  buildWatchlistSections,
  watchlistStats,
  type WatchlistSort,
} from '../utils/watchlistSort';

type Props = NativeStackScreenProps<RootStackParamList, 'Watchlist'>;

const NEWS_PREVIEW_COUNT = 5;

export function WatchlistScreen({ navigation }: Props) {
  const insets = useSafeAreaInsets();
  const [query, setQuery] = useState('');
  const [symbolList, setSymbolList] = useState<string[]>(DEFAULT_SYMBOLS);
  const [stocks, setStocks] = useState<Stock[]>(FALLBACK_WATCHLIST);
  const [searchHits, setSearchHits] = useState<MarketSymbol[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [usingFallback, setUsingFallback] = useState(false);
  const [live, setLive] = useState(isMarketOpen());
  const [sort, setSort] = useState<WatchlistSort>('change');
  const [editing, setEditing] = useState(false);
  const [addMode, setAddMode] = useState(false);
  const [newsPreview, setNewsPreview] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const searchSeq = useRef(0);
  const searchRef = useRef<TextInput>(null);
  const symbolListRef = useRef(symbolList);
  symbolListRef.current = symbolList;

  const loadNewsPreview = useCallback(async (refresh = false) => {
    if (!refresh) setNewsLoading(true);
    await loadMarketNews(NEWS_PREVIEW_COUNT, {
      refresh,
      onData: (items, fromCache) => {
        setNewsPreview(items);
        if (fromCache) setNewsLoading(false);
      },
    });
    setNewsLoading(false);
  }, []);

  const loadQuotes = useCallback(
    async (
      symbols: string[],
      opts?: { refresh?: boolean; silent?: boolean },
    ) => {
      const isRefresh = opts?.refresh ?? false;
      const silent = opts?.silent ?? false;

      if (isRefresh) setRefreshing(true);
      else if (!silent) setLoading(true);

      try {
        const data = await fetchWatchlist(symbols);
        setStocks(data);
        setUsingFallback(false);
      } catch {
        if (!silent) {
          const fallback = FALLBACK_WATCHLIST.filter((s) =>
            symbols.includes(s.symbol),
          );
          setStocks(fallback.length ? fallback : FALLBACK_WATCHLIST);
          setUsingFallback(true);
        }
      } finally {
        if (!silent) setLoading(false);
        setRefreshing(false);
      }
    },
    [],
  );

  const silentRefresh = useCallback(() => {
    void loadQuotes(symbolListRef.current, { silent: true });
  }, [loadQuotes]);

  useEffect(() => {
    const id = setInterval(() => setLive(isMarketOpen()), 60_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    (async () => {
      const saved = await loadWatchlistSymbols();
      setSymbolList(saved);
      await loadQuotes(saved);
      void loadNewsPreview();
    })();
  }, [loadQuotes, loadNewsPreview]);

  useEffect(() => {
    if (!addMode) {
      setSearchHits([]);
      setSearching(false);
      return;
    }

    const q = query.trim();
    if (q.length < 1) {
      setSearchHits([]);
      setSearching(false);
      return;
    }

    const seq = ++searchSeq.current;
    setSearching(true);
    const timer = setTimeout(() => {
      void (async () => {
        try {
          const hits = await searchMarketSymbols(q, 40);
          if (searchSeq.current === seq) setSearchHits(hits);
        } catch {
          if (searchSeq.current === seq) setSearchHits([]);
        } finally {
          if (searchSeq.current === seq) setSearching(false);
        }
      })();
    }, 250);

    return () => clearTimeout(timer);
  }, [query, addMode]);

  const inSearchMode = addMode;

  useMarketPolling(
    silentRefresh,
    REFRESH.quotePollMs,
    !inSearchMode && !loading && !editing,
    false,
  );

  const watchlistSet = useMemo(() => new Set(symbolList), [symbolList]);
  const stats = useMemo(() => watchlistStats(stocks), [stocks]);

  const sections = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = stocks;
    if (q) {
      list = stocks.filter(
        (s) =>
          s.symbol.toLowerCase().includes(q) ||
          s.name.toLowerCase().includes(q),
      );
    }
    return buildWatchlistSections(list, sort);
  }, [query, stocks, sort]);

  const onPressStock = useCallback(
    (stock: Stock) => {
      navigation.navigate('Detail', { symbol: stock.symbol });
    },
    [navigation],
  );

  const openNewsArticle = useCallback(async (item: NewsItem) => {
    if (item.url) {
      await WebBrowser.openBrowserAsync(item.url, {
        presentationStyle: WebBrowser.WebBrowserPresentationStyle.PAGE_SHEET,
        controlsColor: colors.accent,
      });
      return;
    }
    if (item.symbols[0]) {
      navigation.navigate('Detail', { symbol: item.symbols[0] });
    }
  }, [navigation]);

  const onRefresh = useCallback(() => {
    void loadQuotes(symbolList, { refresh: true });
    void loadNewsPreview(true);
  }, [loadQuotes, loadNewsPreview, symbolList]);

  const onToggleSymbol = useCallback(
    async (hit: MarketSymbol) => {
      void Haptics.selectionAsync();
      const sym = hit.symbol.toUpperCase();
      const next = watchlistSet.has(sym)
        ? await removeWatchlistSymbol(sym)
        : await addWatchlistSymbol(sym);
      setSymbolList(next);
      await loadQuotes(next);
    },
    [watchlistSet, loadQuotes],
  );

  const onRemove = useCallback(
    async (stock: Stock) => {
      const next = await removeWatchlistSymbol(stock.symbol);
      setSymbolList(next);
      await loadQuotes(next);
      if (next.length === 0) setEditing(false);
    },
    [loadQuotes],
  );

  const listHeader = (
    <>
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text style={styles.title}>Theo dõi</Text>
          <Text style={styles.subtitle}>HOSE · HNX</Text>
        </View>
        {!inSearchMode ? (
          <Pressable
            onPress={() => {
              void Haptics.selectionAsync();
              navigation.navigate('News');
            }}
            hitSlop={8}
          >
            <Text style={styles.newsLink}>Tin tức</Text>
          </Pressable>
        ) : null}
      </View>

      {!inSearchMode ? (
        <WatchlistSummary
          total={stats.total}
          gainers={stats.gainers}
          losers={stats.losers}
          flat={stats.flat}
          avgChange={stats.avgChange}
          live={live}
          sessionLabel={marketSessionLabel()}
          offline={usingFallback}
        />
      ) : null}

      <View style={styles.searchWrap}>
        <Text style={styles.searchIcon}>⌕</Text>
        <TextInput
          ref={searchRef}
          value={query}
          onChangeText={setQuery}
          placeholder={
            addMode ? 'Thêm mã từ HOSE / HNX…' : 'Lọc danh sách theo dõi…'
          }
          placeholderTextColor={colors.textTertiary}
          style={styles.search}
          autoCorrect={false}
          autoCapitalize="characters"
          clearButtonMode="while-editing"
          onFocus={() => {
            if (editing) setEditing(false);
          }}
        />
        {addMode ? (
          <Pressable
            onPress={() => {
              setAddMode(false);
              setQuery('');
              searchRef.current?.blur();
            }}
            hitSlop={8}
          >
            <Text style={styles.cancelBtn}>Huỷ</Text>
          </Pressable>
        ) : null}
      </View>

      {!inSearchMode ? (
        <SortChips
          value={sort}
          onChange={setSort}
          editing={editing}
          onToggleEdit={() => setEditing((v) => !v)}
        />
      ) : (
        <Text style={styles.searchHint}>
          {searching ? 'Đang tìm…' : `${searchHits.length} kết quả · chạm + để thêm`}
        </Text>
      )}
    </>
  );

  const newsFooter = !inSearchMode ? (
    <View style={styles.newsSection}>
      <View style={styles.newsSectionHeader}>
        <Text style={styles.sectionTitle}>Tin tức</Text>
        <Pressable
          onPress={() => {
            void Haptics.selectionAsync();
            navigation.navigate('News');
          }}
          hitSlop={8}
        >
          <Text style={styles.seeAll}>Xem tất cả</Text>
        </Pressable>
      </View>
      {newsLoading && newsPreview.length === 0 ? (
        <ActivityIndicator
          style={styles.newsSpinner}
          color={colors.textSecondary}
        />
      ) : newsPreview.length === 0 ? (
        <Text style={styles.newsEmpty}>Chưa tải được tin tức</Text>
      ) : (
        <View style={styles.newsCard}>
          {newsPreview.map((item, index) => (
            <NewsRow
              key={item.id}
              item={item}
              compact
              isLast={index === newsPreview.length - 1}
              onPress={(n) => void openNewsArticle(n)}
            />
          ))}
        </View>
      )}
    </View>
  ) : null;

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <StatusBar style="light" />

      {loading && !refreshing && !inSearchMode ? (
        <View style={styles.loadingWrap}>
          {listHeader}
          <ActivityIndicator style={styles.loading} color={colors.positive} />
        </View>
      ) : inSearchMode ? (
        <SectionList
          sections={[{ key: 'search', title: '', data: searchHits }]}
          keyExtractor={(item) => item.symbol}
          keyboardDismissMode="on-drag"
          stickySectionHeadersEnabled={false}
          ListHeaderComponent={listHeader}
          contentContainerStyle={{ paddingBottom: insets.bottom + 24 }}
          ListEmptyComponent={
            !searching ? (
              <Text style={styles.empty}>Không tìm thấy mã phù hợp</Text>
            ) : null
          }
          renderItem={({ item }) => (
            <SearchResultRow
              item={item}
              added={watchlistSet.has(item.symbol)}
              onOpen={() => navigation.navigate('Detail', { symbol: item.symbol })}
              onToggle={() => void onToggleSymbol(item)}
            />
          )}
          renderSectionHeader={() => null}
        />
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(item) => item.symbol}
          stickySectionHeadersEnabled={false}
          keyboardDismissMode="on-drag"
          ListHeaderComponent={listHeader}
          contentContainerStyle={{ paddingBottom: insets.bottom + 24 }}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => void onRefresh()}
              tintColor={colors.positive}
            />
          }
          ListFooterComponent={newsFooter}
          ListEmptyComponent={
            <View style={styles.emptyBox}>
              <Text style={styles.emptyTitle}>Chưa có mã nào</Text>
              <Text style={styles.empty}>
                Gõ tên hoặc mã ở ô tìm kiếm để thêm từ toàn thị trường
              </Text>
            </View>
          }
          renderSectionHeader={({ section: { title, data } }) =>
            data.length > 0 ? (
              <Text style={styles.sectionTitleList}>{title}</Text>
            ) : null
          }
          renderItem={({ item, index, section }) => {
            const isFirst = index === 0;
            const isLast = index === section.data.length - 1;
            return (
              <View
                style={[
                  styles.groupedRow,
                  isFirst && styles.groupTop,
                  isLast && styles.groupBottom,
                ]}
              >
                <StockRow
                  stock={item}
                  onPress={onPressStock}
                  onLongPress={editing ? undefined : () => void onRemove(item)}
                  editing={editing}
                  onRemove={() => void onRemove(item)}
                  isLast={isLast}
                />
              </View>
            );
          }}
          SectionSeparatorComponent={() => <View style={styles.sectionGap} />}
        />
      )}

      {!inSearchMode && !loading && stocks.length > 0 ? (
        <Pressable
          style={[styles.fab, { bottom: insets.bottom + 16 }]}
          onPress={() => {
            void Haptics.selectionAsync();
            setAddMode(true);
            setQuery('');
            setTimeout(() => searchRef.current?.focus(), 50);
          }}
        >
          <Text style={styles.fabText}>+</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  headerText: {
    flex: 1,
  },
  newsLink: {
    color: colors.accent,
    fontSize: 17,
    fontWeight: '500',
    paddingTop: 10,
  },
  title: {
    ...typography.largeTitle,
    color: colors.text,
  },
  subtitle: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  searchWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingHorizontal: 12,
  },
  searchIcon: {
    fontSize: 18,
    color: colors.textTertiary,
    marginRight: 8,
  },
  search: {
    flex: 1,
    paddingVertical: 12,
    color: colors.text,
    fontSize: 16,
  },
  cancelBtn: {
    color: colors.accent,
    fontSize: 16,
    fontWeight: '500',
    paddingLeft: spacing.sm,
  },
  searchHint: {
    ...typography.caption,
    color: colors.textTertiary,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  newsSection: {
    marginTop: spacing.xxl,
    paddingBottom: spacing.lg,
  },
  newsSectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xs,
  },
  seeAll: {
    color: colors.accent,
    fontSize: 15,
    fontWeight: '500',
  },
  newsCard: {
    marginHorizontal: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: 14,
    overflow: 'hidden',
  },
  newsSpinner: {
    marginVertical: spacing.lg,
  },
  newsEmpty: {
    color: colors.textSecondary,
    fontSize: 15,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  sectionTitleList: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xs,
  },
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
  sectionGap: {
    height: spacing.sm,
  },
  emptyBox: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.xxl,
    padding: spacing.xl,
    backgroundColor: colors.surface,
    borderRadius: 14,
    alignItems: 'center',
  },
  emptyTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 8,
  },
  empty: {
    textAlign: 'center',
    color: colors.textSecondary,
    fontSize: 15,
    lineHeight: 22,
  },
  loadingWrap: {
    flex: 1,
  },
  loading: {
    marginTop: 48,
  },
  fab: {
    position: 'absolute',
    right: spacing.lg,
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
    elevation: 6,
  },
  fabText: {
    color: colors.text,
    fontSize: 28,
    fontWeight: '300',
    lineHeight: 30,
    marginTop: -2,
  },
});
