import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
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
import { fetchSourceHealth, getApiUrl, type SourceHealthResponse } from '../api/client';
import { colors, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Health'>;

function statusColor(status: string): string {
  if (status === 'ok') return colors.positive;
  if (status === 'degraded') return '#f5a623';
  return colors.negative;
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('vi-VN');
  } catch {
    return iso;
  }
}

export function HealthScreen({ navigation }: Props) {
  const insets = useSafeAreaInsets();
  const [data, setData] = useState<SourceHealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const health = await fetchSourceHealth();
      setData(health);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : 'Không tải được trạng thái hệ thống');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

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
        >
          <Text style={styles.back}>← Quay lại</Text>
        </Pressable>
        <Text style={styles.title}>Nguồn dữ liệu</Text>
        <View style={styles.navSpacer} />
      </View>

      {loading && !data ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.accent} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.content}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} tintColor={colors.accent} />
          }
        >
          {error ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorTitle}>Không kết nối được máy chủ</Text>
              <Text style={styles.errorText}>{error}</Text>
              <Text style={styles.hint}>API: {getApiUrl()}</Text>
            </View>
          ) : null}

          {data ? (
            <>
              <View style={styles.card}>
                <Text style={styles.cardTitle}>Tổng quan</Text>
                <Row label="Trạng thái" value={data.status.toUpperCase()} valueColor={statusColor(data.status)} />
                <Row label="Phiên" value={data.marketOpen ? 'Đang mở' : 'Đóng cửa'} />
                <Row label="Kiểm tra lúc" value={formatTime(data.checkedAt)} />
              </View>

              <View style={styles.card}>
                <Text style={styles.cardTitle}>Kho dữ liệu (SQLite)</Text>
                <Row label="Giá" value={`${data.store.quotesCount} mã`} />
                <Row label="Cập nhật giá" value={formatTime(data.store.quotesLatestAt)} />
                <Row label="Tin tức" value={`${data.store.newsCount} bài`} />
                <Row label="Chỉ số" value={`${data.store.indicesCount} mã`} />
                <Row label="Lịch sử" value={`${data.store.historyCount} dòng`} />
                <Row label="Mã CK" value={`${data.store.symbolsCount} mã`} />
                <Row label="Cơ bản" value={`${data.store.fundamentalsCount} mã`} />
              </View>

              <View style={styles.card}>
                <Text style={styles.cardTitle}>Providers</Text>
                {data.providers.map((provider) => (
                  <View key={`${provider.kind}:${provider.name}`} style={styles.providerRow}>
                    <Text style={styles.providerName}>
                      {provider.kind}/{provider.name}
                    </Text>
                    <Text style={[styles.providerStatus, { color: statusColor(provider.status) }]}>
                      {provider.status}
                      {provider.stale ? ' · stale' : ''}
                    </Text>
                    {provider.lastError ? (
                      <Text style={styles.providerError} numberOfLines={2}>
                        {provider.lastError}
                      </Text>
                    ) : null}
                  </View>
                ))}
              </View>

              {data.jobs.length > 0 ? (
                <View style={styles.card}>
                  <Text style={styles.cardTitle}>Jobs nền</Text>
                  {data.jobs.map((job) => (
                    <View key={job.name} style={styles.providerRow}>
                      <Text style={styles.providerName}>{job.name}</Text>
                      <Text style={styles.meta}>
                        {job.lastItemCount} items · {formatTime(job.lastSuccessAt)}
                      </Text>
                    </View>
                  ))}
                </View>
              ) : null}
            </>
          ) : null}
        </ScrollView>
      )}
    </View>
  );
}

function Row({
  label,
  value,
  valueColor = colors.text,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={[styles.rowValue, { color: valueColor }]}>{value}</Text>
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
    paddingBottom: spacing.sm,
  },
  back: {
    color: colors.accent,
    fontSize: 16,
    fontWeight: '600',
    minWidth: 90,
  },
  title: {
    ...typography.title,
    color: colors.text,
    flex: 1,
    textAlign: 'center',
  },
  navSpacer: {
    minWidth: 90,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: {
    padding: spacing.lg,
    gap: spacing.md,
    paddingBottom: spacing.xxl,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing.md,
    gap: 8,
  },
  cardTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 4,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  rowLabel: {
    color: colors.textSecondary,
    fontSize: 14,
  },
  rowValue: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
    flexShrink: 1,
    textAlign: 'right',
  },
  providerRow: {
    paddingVertical: 6,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  providerName: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
  providerStatus: {
    fontSize: 13,
    marginTop: 2,
  },
  providerError: {
    color: colors.textTertiary,
    fontSize: 12,
    marginTop: 2,
  },
  meta: {
    color: colors.textSecondary,
    fontSize: 12,
    marginTop: 2,
  },
  errorBox: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.negative,
  },
  errorTitle: {
    color: colors.negative,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 6,
  },
  errorText: {
    color: colors.textSecondary,
    fontSize: 14,
  },
  hint: {
    color: colors.textTertiary,
    fontSize: 12,
    marginTop: 8,
  },
});
