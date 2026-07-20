import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as WebBrowser from 'expo-web-browser';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { BottomTabScreenProps } from '@react-navigation/bottom-tabs';
import type { CompositeScreenProps } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { MainTabParamList, RootStackParamList } from '../navigation/types';
import { fetchMarketNews } from '../api/client';
import { NewsRow } from '../components/NewsRow';
import type { NewsItem } from '../types/news';
import { colors, spacing, typography } from '../theme';

type Props = CompositeScreenProps<
  BottomTabScreenProps<MainTabParamList, 'News'>,
  NativeStackScreenProps<RootStackParamList>
>;

export function NewsScreen({ navigation }: Props) {
  const insets = useSafeAreaInsets();
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await fetchMarketNews(30);
      setItems(data);
    } catch {
      if (!isRefresh) setItems([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

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

      <View style={styles.header}>
        <Text style={styles.title}>Tin tức</Text>
        <Text style={styles.subtitle}>Chứng khoán · kinh tế Việt Nam</Text>
      </View>

      {loading && !refreshing ? (
        <ActivityIndicator style={styles.loading} color={colors.positive} />
      ) : (
        <ScrollView
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
          {items.length === 0 ? (
            <Text style={styles.empty}>Chưa tải được tin tức</Text>
          ) : (
            <View style={styles.card}>
              {items.map((item, index) => (
                <NewsRow
                  key={item.id}
                  item={item}
                  onPress={(n) => void openArticle(n)}
                  isLast={index === items.length - 1}
                />
              ))}
            </View>
          )}
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
  listContent: {
    flexGrow: 1,
  },
  card: {
    marginHorizontal: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: 14,
    overflow: 'hidden',
  },
  loading: {
    marginTop: 48,
  },
  empty: {
    textAlign: 'center',
    color: colors.textSecondary,
    marginTop: 48,
    fontSize: 15,
  },
});
