import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
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
  loadMarketIndices,
  loadWatchlist,
  loadMarketNews,
  searchMarketSymbols,
  type MarketSymbol,
} from '../api/client';
import { useMarketPolling } from '../hooks/useMarketPolling';
import { usePriceAlerts } from '../hooks/usePriceAlerts';
import { FALLBACK_WATCHLIST } from '../data/stocks';
import { formatCacheAge } from '../storage/cacheUtils';
import {
  addWatchlistSymbol,
  createWatchlist,
  deleteWatchlist,
  getActiveWatchlist,
  loadWatchlistsState,
  renameWatchlist,
  removeWatchlistSymbol,
  setActiveWatchlist,
  togglePinSymbol,
  type WatchlistsState,
} from '../storage/watchlist';
import {
  loadPriceAlerts,
  removePriceAlert,
  upsertPriceAlert,
  type PriceAlert,
} from '../storage/alerts';
import { syncPriceAlertBackgroundTask } from '../tasks/priceAlertBackgroundTask';
import type { Stock } from '../types';
import type { NewsItem } from '../types/news';
import { AlertSheet } from '../components/AlertSheet';
import { ApiStatusBanner } from '../components/ApiStatusBanner';
import { ManageAlertsSheet } from '../components/ManageAlertsSheet';
import { NewsRow } from '../components/NewsRow';
import { NewsRowSkeleton, StockRowSkeleton, SummarySkeleton } from '../components/Skeleton';
import { ManageWatchlistsSheet } from '../components/ManageWatchlistsSheet';
import { SearchResultRow } from '../components/SearchResultRow';
import { SortChips } from '../components/SortChips';
import { StockRow } from '../components/StockRow';
import { SwipeableStockRow } from '../components/SwipeableStockRow';
import { WatchlistMenuSheet } from '../components/WatchlistMenuSheet';
import { WatchlistPicker } from '../components/WatchlistPicker';
import { WatchlistSummary, type IndexQuote } from '../components/WatchlistSummary';
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
  const [watchlistsState, setWatchlistsState] = useState<WatchlistsState | null>(null);
  const [symbolList, setSymbolList] = useState<string[]>(DEFAULT_SYMBOLS);
  const [pinnedSymbols, setPinnedSymbols] = useState<string[]>([]);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [indices, setIndices] = useState<IndexQuote[]>([]);
  const [searchHits, setSearchHits] = useState<MarketSymbol[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [usingFallback, setUsingFallback] = useState(false);
  const [usingOfflineCache, setUsingOfflineCache] = useState(false);
  const [cacheFetchedAt, setCacheFetchedAt] = useState<number | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [live, setLive] = useState(isMarketOpen());
  const [sort, setSort] = useState<WatchlistSort>('change');
  const [editing, setEditing] = useState(false);
  const [addMode, setAddMode] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [newsPreview, setNewsPreview] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [alertStock, setAlertStock] = useState<Stock | null>(null);
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);
  const [menuVisible, setMenuVisible] = useState(false);
  const [manageVisible, setManageVisible] = useState(false);
  const [manageAlertsVisible, setManageAlertsVisible] = useState(false);
  const searchSeq = useRef(0);
  const searchRef = useRef<TextInput>(null);
  const symbolListRef = useRef(symbolList);
  symbolListRef.current = symbolList;

  const applyWatchlistState = useCallback((state: WatchlistsState) => {
    setWatchlistsState(state);
    const active = getActiveWatchlist(state);
    setSymbolList(active.symbols);
    setPinnedSymbols(active.pinnedSymbols);
    symbolListRef.current = active.symbols;
  }, []);

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

  const reloadAlerts = useCallback(async () => {
    const all = await loadPriceAlerts();
    setAlerts(all);
    void syncPriceAlertBackgroundTask();
  }, []);

  const loadIndices = useCallback(async (refresh = false) => {
    await loadMarketIndices({
      refresh,
      onData: (rows) => {
        setIndices(rows);
      },
    });
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

      if (symbols.length === 0) {
        setStocks([]);
        setUsingFallback(false);
        setUsingOfflineCache(false);
        setCacheFetchedAt(null);
        setApiError(null);
        if (!silent) setLoading(false);
        setRefreshing(false);
        return;
      }

      try {
        await loadWatchlist(symbols, {
          refresh: isRefresh,
          onData: (data, fromCache, fetchedAt) => {
            setStocks(data);
            if (fromCache) {
              setUsingOfflineCache(true);
              setCacheFetchedAt(fetchedAt ?? null);
              if (!silent) setApiError(null);
            } else {
              setUsingOfflineCache(false);
              setCacheFetchedAt(null);
              setUsingFallback(false);
              setApiError(null);
            }
            if (!silent && data.length > 0) setLoading(false);
          },
        });
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Không kết nối được máy chủ';
        if (!silent) setApiError(message);
        if (!silent) {
          const fallback = FALLBACK_WATCHLIST.filter((s) =>
            symbols.includes(s.symbol),
          );
          if (fallback.length) {
            setStocks(fallback);
            setUsingFallback(true);
            setUsingOfflineCache(false);
          }
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
    void loadIndices();
  }, [loadQuotes, loadIndices]);

  useEffect(() => {
    const id = setInterval(() => setLive(isMarketOpen()), 60_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    (async () => {
      const state = await loadWatchlistsState();
      applyWatchlistState(state);
      const active = getActiveWatchlist(state);
      await loadQuotes(active.symbols);
      void loadNewsPreview();
      void loadIndices();
      void reloadAlerts();
    })();
  }, [applyWatchlistState, loadQuotes, loadNewsPreview, loadIndices, reloadAlerts]);

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
  const pinnedSet = useMemo(() => new Set(pinnedSymbols), [pinnedSymbols]);

  useMarketPolling(
    silentRefresh,
    REFRESH.quotePollMs,
    !inSearchMode && !loading && !editing,
    false,
  );

  usePriceAlerts(stocks, !inSearchMode && !loading);

  const watchlistSet = useMemo(() => new Set(symbolList), [symbolList]);
  const stats = useMemo(() => watchlistStats(stocks), [stocks]);

  const sections = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = stocks;
    if (q && !addMode) {
      list = stocks.filter(
        (s) =>
          s.symbol.toLowerCase().includes(q) ||
          s.name.toLowerCase().includes(q),
      );
    }
    return buildWatchlistSections(list, sort, pinnedSymbols);
  }, [addMode, query, stocks, sort, pinnedSymbols]);

  const activeList = watchlistsState ? getActiveWatchlist(watchlistsState) : null;

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
    void loadIndices();
  }, [loadQuotes, loadNewsPreview, loadIndices, symbolList]);

  const onToggleSymbol = useCallback(
    async (hit: MarketSymbol) => {
      void Haptics.selectionAsync();
      const sym = hit.symbol.toUpperCase();
      const next = watchlistSet.has(sym)
        ? await removeWatchlistSymbol(sym)
        : await addWatchlistSymbol(sym);
      applyWatchlistState(next);
      await loadQuotes(getActiveWatchlist(next).symbols);
    },
    [applyWatchlistState, loadQuotes, watchlistSet],
  );

  const onRemove = useCallback(
    async (stock: Stock) => {
      const next = await removeWatchlistSymbol(stock.symbol);
      applyWatchlistState(next);
      await loadQuotes(getActiveWatchlist(next).symbols);
      if (getActiveWatchlist(next).symbols.length === 0) setEditing(false);
    },
    [applyWatchlistState, loadQuotes],
  );

  const onPin = useCallback(
    async (stock: Stock) => {
      const next = await togglePinSymbol(stock.symbol);
      applyWatchlistState(next);
    },
    [applyWatchlistState],
  );

  const onSaveAlert = useCallback(async (condition: 'above' | 'below', price: number) => {
    if (!alertStock) return;
    await upsertPriceAlert({
      symbol: alertStock.symbol,
      condition,
      price,
      enabled: true,
    });
    await reloadAlerts();
  }, [alertStock, reloadAlerts]);

  const onUpdateAlertValue = useCallback(async (id: string, price: number) => {
    const current = alerts.find((a) => a.id === id);
    if (!current) return;
    await upsertPriceAlert({
      id: current.id,
      symbol: current.symbol,
      condition: current.condition,
      price,
      enabled: current.enabled,
    });
    await reloadAlerts();
  }, [alerts, reloadAlerts]);

  const onDeleteAlert = useCallback(async (id: string) => {
    await removePriceAlert(id);
    await reloadAlerts();
  }, [reloadAlerts]);

  const onSelectWatchlist = useCallback(
    async (id: string) => {
      const next = await setActiveWatchlist(id);
      applyWatchlistState(next);
      await loadQuotes(getActiveWatchlist(next).symbols);
    },
    [applyWatchlistState, loadQuotes],
  );

  const onCreateWatchlist = useCallback(async () => {
    const count = watchlistsState?.lists.length ?? 1;
    const next = await createWatchlist(`Danh sách ${count + 1}`);
    applyWatchlistState(next);
    await loadQuotes(getActiveWatchlist(next).symbols);
  }, [applyWatchlistState, loadQuotes, watchlistsState?.lists.length]);

  const onRenameWatchlist = useCallback(async (id: string, name: string) => {
    const next = await renameWatchlist(id, name);
    applyWatchlistState(next);
  }, [applyWatchlistState]);

  const onDeleteWatchlist = useCallback(async (id: string) => {
    const next = await deleteWatchlist(id);
    applyWatchlistState(next);
    await loadQuotes(getActiveWatchlist(next).symbols);
  }, [applyWatchlistState, loadQuotes]);

  const listHeader = (
    <>
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text style={styles.title}>{activeList?.name ?? 'Theo dõi'}</Text>
          <Text style={styles.subtitle}>HOSE · HNX</Text>
        </View>
        {!inSearchMode ? (
          <View style={styles.headerActions}>
            <Pressable
              onPress={() => {
                void Haptics.selectionAsync();
                setFilterOpen(true);
                setTimeout(() => searchRef.current?.focus(), 50);
              }}
              hitSlop={8}
              style={styles.headerIconBtn}
              accessibilityRole="button"
              accessibilityLabel="Tìm trong danh sách"
            >
              <Text style={styles.searchHeaderIcon}>⌕</Text>
            </Pressable>
            <Pressable
              onPress={() => {
                void Haptics.selectionAsync();
                setMenuVisible(true);
              }}
              hitSlop={8}
              style={styles.menuBtn}
            >
              <Text style={styles.menuDots}>⋯</Text>
            </Pressable>
          </View>
        ) : null}
      </View>

      {!inSearchMode && watchlistsState ? (
        <WatchlistPicker
          lists={watchlistsState.lists}
          activeId={watchlistsState.activeId}
          onSelect={(id) => void onSelectWatchlist(id)}
          onCreate={() => void onCreateWatchlist()}
        />
      ) : null}

      {!inSearchMode && (usingFallback || usingOfflineCache || apiError) ? (
        <ApiStatusBanner
          message={
            usingFallback
              ? 'Không kết nối được máy chủ — đang hiển thị dữ liệu mẫu'
              : usingOfflineCache
                ? `Dữ liệu đã lưu · cập nhật ${formatCacheAge(cacheFetchedAt ?? Date.now())}`
                : (apiError ?? 'Không kết nối được máy chủ')
          }
          onRetry={() => void loadQuotes(symbolList, { refresh: true })}
        />
      ) : null}

      {!inSearchMode ? (
        loading && !refreshing ? (
          <SummarySkeleton />
        ) : (
          <WatchlistSummary
            total={stats.total}
            gainers={stats.gainers}
            losers={stats.losers}
            flat={stats.flat}
            avgChange={stats.avgChange}
            live={live}
            sessionLabel={marketSessionLabel()}
            offline={usingFallback || usingOfflineCache}
            indices={indices}
            onIndexPress={(symbol) => navigation.navigate('Detail', { symbol })}
          />
        )
      ) : null}

      {inSearchMode || filterOpen ? (
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
          <Pressable
            onPress={() => {
              if (addMode) {
                setAddMode(false);
              } else {
                setFilterOpen(false);
              }
              setQuery('');
              searchRef.current?.blur();
            }}
            hitSlop={8}
          >
            <Text style={styles.cancelBtn}>Huỷ</Text>
          </Pressable>
        </View>
      ) : null}

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
        <View style={styles.newsCard}>
          {[1, 2, 3].map((i) => (
            <NewsRowSkeleton key={i} />
          ))}
        </View>
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

  const renderStockRow = (item: Stock, isFirst: boolean, isLast: boolean) => {
    const wrapStyle = [
      styles.groupedRow,
      isFirst && styles.groupTop,
      isLast && styles.groupBottom,
    ];

    if (editing) {
      return (
        <View style={wrapStyle}>
          <StockRow
            stock={item}
            onPress={onPressStock}
            editing
            onRemove={() => void onRemove(item)}
            pinned={pinnedSet.has(item.symbol)}
            isLast={isLast}
          />
        </View>
      );
    }

    return (
      <View style={[wrapStyle, { padding: 0, overflow: 'hidden' }]}>
        <SwipeableStockRow
          stock={item}
          pinned={pinnedSet.has(item.symbol)}
          onPress={onPressStock}
          onPin={() => void onPin(item)}
          onAlert={() => setAlertStock(item)}
          onRemove={() => void onRemove(item)}
          isLast={isLast}
        />
      </View>
    );
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <StatusBar style="light" />

      {loading && !refreshing && !inSearchMode ? (
        <SectionList
          sections={[{ key: 'sk', title: '', data: [] as Stock[] }]}
          ListHeaderComponent={listHeader}
          ListFooterComponent={
            <>
              <View style={styles.skeletonCard}>
                {[1, 2, 3, 4, 5].map((i) => (
                  <StockRowSkeleton key={i} />
                ))}
              </View>
              {newsFooter}
            </>
          }
          renderItem={() => null}
          renderSectionHeader={() => null}
          contentContainerStyle={{ paddingBottom: insets.bottom + 24 }}
        />
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
                Chạm nút + để thêm mã từ toàn thị trường HOSE / HNX
              </Text>
            </View>
          }
          renderSectionHeader={({ section: { title, data } }) =>
            data.length > 0 ? (
              <Text style={styles.sectionTitleList}>{title}</Text>
            ) : null
          }
          renderItem={({ item, index, section }) =>
            renderStockRow(item, index === 0, index === section.data.length - 1)
          }
          SectionSeparatorComponent={() => <View style={styles.sectionGap} />}
        />
      )}

      {!inSearchMode && !loading ? (
        <Pressable
          style={[styles.fab, { bottom: insets.bottom + 16 }]}
          onPress={() => {
            void Haptics.selectionAsync();
            setFilterOpen(false);
            setAddMode(true);
            setQuery('');
            setTimeout(() => searchRef.current?.focus(), 50);
          }}
        >
          <Text style={styles.fabText}>+</Text>
        </Pressable>
      ) : null}

      <AlertSheet
        visible={alertStock != null}
        symbol={alertStock?.symbol ?? ''}
        currentPrice={alertStock?.price ?? 0}
        onClose={() => setAlertStock(null)}
        onSave={(condition, price) => void onSaveAlert(condition, price)}
      />

      <WatchlistMenuSheet
        visible={menuVisible}
        onClose={() => setMenuVisible(false)}
        onManageWatchlists={() => {
          setMenuVisible(false);
          setManageVisible(true);
        }}
        onManageAlerts={() => {
          setMenuVisible(false);
          setManageAlertsVisible(true);
        }}
        onSystemHealth={() => {
          setMenuVisible(false);
          navigation.navigate('Health');
        }}
      />

      <ManageWatchlistsSheet
        visible={manageVisible}
        lists={watchlistsState?.lists ?? []}
        activeId={watchlistsState?.activeId ?? ''}
        onClose={() => setManageVisible(false)}
        onRename={onRenameWatchlist}
        onDelete={onDeleteWatchlist}
      />

      <ManageAlertsSheet
        visible={manageAlertsVisible}
        alerts={alerts}
        onClose={() => setManageAlertsVisible(false)}
        onSave={onUpdateAlertValue}
        onDelete={onDeleteAlert}
      />
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
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  headerIconBtn: {
    paddingHorizontal: spacing.sm,
    paddingTop: spacing.xs,
  },
  searchHeaderIcon: {
    color: colors.accent,
    fontSize: 22,
    lineHeight: 28,
    fontWeight: '500',
  },
  menuBtn: {
    paddingHorizontal: spacing.sm,
    paddingTop: spacing.xs,
  },
  menuDots: {
    color: colors.accent,
    fontSize: 30,
    lineHeight: 30,
    fontWeight: '600',
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
  skeletonCard: {
    marginHorizontal: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: 14,
    overflow: 'hidden',
    marginTop: spacing.sm,
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
