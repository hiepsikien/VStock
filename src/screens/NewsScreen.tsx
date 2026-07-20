import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as WebBrowser from 'expo-web-browser';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import * as Haptics from 'expo-haptics';
import type { RootStackParamList } from '../navigation/types';
import { loadMarketNews } from '../api/client';
import { NewsFilterChips } from '../components/NewsFilterChips';
import { NewsRow } from '../components/NewsRow';
import { NewsRowSkeleton } from '../components/Skeleton';
import type { NewsFilter, NewsItem } from '../types/news';
import { filterNewsItems } from '../types/news';
import { colors, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'News'>;

export function NewsScreen({ navigation }: Props) {
  const insets = useSafeAreaInsets();
  const [items, setItems] = useState<NewsItem[]>([]);
  const [filter, setFilter] = useState<NewsFilter>('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const filtered = useMemo(() => filterNewsItems(items, filter), [items, filter]);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else if (items.length === 0) setLoading(true);

    await loadMarketNews(40, {
      refresh: isRefresh,
      onData: (data, fromCache) => {
        setItems(data);
        if (fromCache) setLoading(false);
      },
    });

    setLoading(false);
    setRefreshing(false);
  }, [items.length]);

  useEffect(() => {
    void load();
  }, [load]);

  const openArticle = useCallback(async (item: NewsItem) => {
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
          <Text style={styles.backLabel}>Theo dõi</Text>
        </Pressable>
      </View>

      <View style={styles.header}>
        <Text style={styles.title}>Tin tức</Text>
        <Text style={styles.subtitle}>Chứng khoán · kinh tế Việt Nam</Text>
      </View>

      <View style={styles.filtersWrap}>
        <NewsFilterChips value={filter} onChange={setFilter} />
      </View>

      <ScrollView
        style={styles.list}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[
          styles.listContent,
          { paddingBottom: insets.bottom + 24 },
        ]}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => void load(true)}
            tintColor={colors.positive}
          />
        }
      >
        {loading && !refreshing ? (
          <View style={styles.card}>
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <NewsRowSkeleton key={i} />
            ))}
          </View>
        ) : filtered.length === 0 ? (
          <Text style={styles.empty}>
            {items.length === 0 ? 'Chưa tải được tin tức' : 'Không có tin trong nhóm này'}
          </Text>
        ) : (
          <View style={styles.card}>
            {filtered.map((item, index) => (
              <NewsRow
                key={item.id}
                item={item}
                onPress={(n) => void openArticle(n)}
                isLast={index === filtered.length - 1}
              />
            ))}
          </View>
        )}
      </ScrollView>
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
  header: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
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
  filtersWrap: {
    backgroundColor: colors.background,
    zIndex: 2,
    marginBottom: spacing.sm,
  },
  list: {
    flex: 1,
  },
  listContent: {
    flexGrow: 1,
    paddingTop: spacing.xs,
  },
  card: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.xs,
    backgroundColor: colors.surface,
    borderRadius: 14,
    overflow: 'hidden',
  },
  empty: {
    textAlign: 'center',
    color: colors.textSecondary,
    marginTop: 48,
    fontSize: 15,
    paddingHorizontal: spacing.lg,
  },
});
