import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { fetchWatchlist } from '../api/client';
import { FALLBACK_WATCHLIST } from '../data/stocks';
import type { Stock } from '../types';
import { StockRow } from '../components/StockRow';
import { colors, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Watchlist'>;

export function WatchlistScreen({ navigation }: Props) {
  const insets = useSafeAreaInsets();
  const [query, setQuery] = useState('');
  const [stocks, setStocks] = useState<Stock[]>(FALLBACK_WATCHLIST);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usingFallback, setUsingFallback] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const data = await fetchWatchlist();
      setStocks(data);
      setError(null);
      setUsingFallback(false);
    } catch (err) {
      setUsingFallback(true);
      setStocks(FALLBACK_WATCHLIST);
      setError(err instanceof Error ? err.message : 'Không tải được dữ liệu');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const data = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return stocks;
    return stocks.filter(
      (s) =>
        s.symbol.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q),
    );
  }, [query, stocks]);

  const onPress = useCallback(
    (stock: Stock) => {
      navigation.navigate('Detail', { symbol: stock.symbol });
    },
    [navigation],
  );

  const gainers = stocks.filter((s) => s.changePercent >= 0).length;

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <StatusBar style="light" />

      <View style={styles.header}>
        <Text style={styles.title}>VStock</Text>
        <Text style={styles.subtitle}>
          {stocks.length} mã · {gainers} tăng
          {usingFallback ? ' · offline' : ' · HOSE/HNX'}
        </Text>
        {error && usingFallback ? (
          <Text style={styles.errorHint}>Đang dùng dữ liệu mẫu</Text>
        ) : null}
      </View>

      <View style={styles.searchWrap}>
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Tìm mã chứng khoán"
          placeholderTextColor={colors.textTertiary}
          style={styles.search}
          autoCorrect={false}
          autoCapitalize="characters"
          clearButtonMode="while-editing"
        />
      </View>

      {loading && !refreshing ? (
        <View style={styles.loading}>
          <ActivityIndicator color={colors.positive} />
        </View>
      ) : (
        <FlatList
          data={data}
          keyExtractor={(item) => item.symbol}
          renderItem={({ item }) => <StockRow stock={item} onPress={onPress} />}
          ItemSeparatorComponent={() => <View style={styles.separator} />}
          contentContainerStyle={{ paddingBottom: insets.bottom + 24 }}
          showsVerticalScrollIndicator={false}
          keyboardDismissMode="on-drag"
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => void load(true)}
              tintColor={colors.positive}
            />
          }
          ListEmptyComponent={
            <Text style={styles.empty}>Không tìm thấy mã phù hợp</Text>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
  },
  title: {
    ...typography.largeTitle,
    color: colors.text,
  },
  subtitle: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 4,
  },
  errorHint: {
    ...typography.caption,
    color: colors.textTertiary,
    marginTop: 4,
  },
  searchWrap: {
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  search: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 11,
    color: colors.text,
    fontSize: 16,
  },
  separator: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.separator,
    marginLeft: spacing.lg,
  },
  empty: {
    textAlign: 'center',
    color: colors.textSecondary,
    marginTop: 48,
    fontSize: 15,
  },
  loading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
