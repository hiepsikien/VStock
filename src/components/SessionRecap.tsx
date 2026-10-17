import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useAudioPlayer, useAudioPlayerStatus, setAudioModeAsync } from 'expo-audio';
import * as Haptics from 'expo-haptics';
import Svg, { Rect } from 'react-native-svg';
import {
  absoluteApiUrl,
  fetchRecap,
  fetchSessionMinutes,
  fetchSessions,
  type RecapManifest,
  type RecapVariant,
  type SessionMinutes,
  type SessionSummary,
} from '../api/client';
import { formatPercent } from '../data/stocks';
import { colors, spacing, typography } from '../theme';
import { candleIndexAt } from '../utils/recapCursor';
import { isMarketOpen, REFRESH } from '../utils/marketSession';

const VARIANTS: { id: RecapVariant; label: string }[] = [
  { id: 'symphony', label: 'Giao hưởng' },
  { id: 'jazz', label: 'Jazz' },
  { id: 'minimalist', label: 'Tối giản' },
];

export type RecapView = {
  prices: number[];
  changePercent: number;
  cursorIndex: number | null;
  cursorLabel: string | null;
};

type Props = {
  symbol: string;
  children: (view: RecapView) => React.ReactNode;
};

const EMPTY_VIEW: RecapView = {
  prices: [],
  changePercent: 0,
  cursorIndex: null,
  cursorLabel: null,
};

function vnToday(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
}

function chipParts(iso: string): { weekday: string; day: string } {
  const [year, month, day] = iso.split('-').map(Number);
  const when = new Date(year, (month || 1) - 1, day || 1);
  const weekday = new Intl.DateTimeFormat('vi-VN', { weekday: 'short' })
    .format(when)
    .replace('.', '');
  return { weekday, day: `${day}/${month}` };
}

function recapErrorMessage(error: unknown): string {
  const text = error instanceof Error ? error.message : '';
  if (text.includes('API 404')) return 'Phiên này chưa có nến 1 phút.';
  if (text.includes('API 503')) return 'Máy chủ chưa soạn được nhạc.';
  return 'Không tải được phiên.';
}

export function SessionRecap({ symbol, children }: Props) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [variant, setVariant] = useState<RecapVariant>('symphony');
  const [series, setSeries] = useState<SessionMinutes | null>(null);
  const [manifest, setManifest] = useState<RecapManifest | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState<{ index: number; label: string } | null>(null);
  const cursorActive = useRef(false);

  const onCursor = useCallback((index: number | null, label: string | null) => {
    cursorActive.current = index != null;
    setCursor(index == null || label == null ? null : { index, label });
  }, []);

  useEffect(() => {
    let cancelled = false;
    setSessions([]);
    setSelected(null);
    setSeries(null);
    setManifest(null);
    setCursor(null);
    setError(null);
    void (async () => {
      try {
        const rows = await fetchSessions(symbol);
        if (cancelled) return;
        setSessions(rows);
        setSelected(rows.length ? rows[rows.length - 1].date : null);
      } catch (err) {
        if (!cancelled) setError(recapErrorMessage(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    setPreparing(true);
    setError(null);
    setCursor(null);
    setManifest(null);
    void (async () => {
      try {
        const detail = await fetchSessionMinutes(symbol, selected);
        if (cancelled) return;
        setSeries(detail);
        const recap = await fetchRecap(symbol, selected, variant);
        if (cancelled) return;
        setManifest(recap);
      } catch (err) {
        if (!cancelled) {
          setManifest(null);
          setError(recapErrorMessage(err));
        }
      } finally {
        if (!cancelled) setPreparing(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selected, symbol, variant]);

  useEffect(() => {
    if (!selected) return;
    const timer = setInterval(() => {
      if (cursorActive.current || !isMarketOpen() || selected !== vnToday()) return;
      void (async () => {
        try {
          const detail = await fetchSessionMinutes(symbol, selected);
          if (cursorActive.current) return;
          setSeries(detail);
          if (detail.prices.length !== manifest?.barCount) {
            const recap = await fetchRecap(symbol, selected, variant);
            if (!cursorActive.current) setManifest(recap);
          }
        } catch {
          /* keep the session on screen */
        }
      })();
    }, REFRESH.chart1dPollMs);
    return () => clearInterval(timer);
  }, [manifest?.barCount, selected, symbol, variant]);

  const view: RecapView = series
    ? {
        prices: series.prices,
        changePercent: series.changePercent,
        cursorIndex: cursor?.index ?? null,
        cursorLabel: cursor?.label ?? null,
      }
    : EMPTY_VIEW;

  return (
    <View>
      {sessions.length > 0 ? (
        <View style={styles.daysBlock}>
          <Text style={styles.daysCaption}>7 phiên gần nhất · nến 1 phút</Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.daysRow}
          >
            {sessions.map((session) => {
              const active = session.date === selected;
              const up = session.changePercent >= 0;
              const chip = chipParts(session.date);
              return (
                <Pressable
                  key={session.date}
                  onPress={() => {
                    void Haptics.selectionAsync();
                    setSelected(session.date);
                  }}
                  style={[styles.dayChip, active && styles.dayChipActive]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: active }}
                >
                  <Text style={[styles.dayWeek, active && styles.dayWeekActive]}>{chip.weekday}</Text>
                  <Text style={[styles.dayDate, active && styles.dayDateActive]}>{chip.day}</Text>
                  <Text style={[styles.dayChange, { color: up ? colors.positive : colors.negative }]}>
                    {formatPercent(session.changePercent)}
                  </Text>
                </Pressable>
              );
            })}
          </ScrollView>
        </View>
      ) : null}

      {children(view)}

      {selected ? (
        <View style={styles.player}>
          <View style={styles.variantRow}>
            {VARIANTS.map((item) => {
              const active = item.id === variant;
              return (
                <Pressable
                  key={item.id}
                  onPress={() => {
                    void Haptics.selectionAsync();
                    setVariant(item.id);
                  }}
                  style={[styles.variant, active && styles.variantActive]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: active }}
                >
                  <Text style={[styles.variantText, active && styles.variantTextActive]}>
                    {item.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {manifest && series ? (
            <RecapPlayer
              key={manifest.audioUrl}
              manifest={manifest}
              times={series.times}
              onCursor={onCursor}
            />
          ) : preparing ? (
            <View style={styles.preparing}>
              <ActivityIndicator color={colors.accent} />
              <Text style={styles.preparingText}>Đang soạn nhạc…</Text>
            </View>
          ) : null}

          {error ? <Text style={styles.error}>{error}</Text> : null}
        </View>
      ) : null}
    </View>
  );
}

function RecapPlayer({
  manifest,
  times,
  onCursor,
}: {
  manifest: RecapManifest;
  times: string[];
  onCursor: (index: number | null, label: string | null) => void;
}) {
  const player = useAudioPlayer(absoluteApiUrl(manifest.audioUrl), {
    updateInterval: 80,
    downloadFirst: true,
  });
  const status = useAudioPlayerStatus(player);
  const [waveWidth, setWaveWidth] = useState(0);

  useEffect(() => {
    void setAudioModeAsync({ playsInSilentMode: true });
  }, []);

  useEffect(() => {
    const fileDuration = status.duration > 0 ? status.duration : manifest.durationSec;
    const mapDuration =
      manifest.mapDurationSec > 0 ? manifest.mapDurationSec : fileDuration;
    const started = status.playing || status.currentTime > 0.05;
    if (!started || times.length < 1) {
      onCursor(null, null);
      return;
    }
    const index = candleIndexAt(status.currentTime, times.length, mapDuration);
    onCursor(index, times[index] ?? null);
  }, [
    manifest.durationSec,
    manifest.mapDurationSec,
    onCursor,
    status.currentTime,
    status.duration,
    status.playing,
    times,
  ]);

  const duration = status.duration > 0 ? status.duration : manifest.durationSec;
  const progress = duration > 0 ? Math.min(1, Math.max(0, status.currentTime / duration)) : 0;
  const peaks = manifest.peaks.length ? manifest.peaks : [0.2];

  const toggle = () => {
    void Haptics.selectionAsync();
    if (status.playing) player.pause();
    else player.play();
  };

  const seek = (locationX: number) => {
    if (waveWidth <= 0 || duration <= 0) return;
    const ratio = Math.min(1, Math.max(0, locationX / waveWidth));
    void player.seekTo(ratio * duration);
  };

  return (
    <View>
      <Pressable
        onPress={toggle}
        style={styles.play}
        accessibilityRole="button"
        accessibilityLabel={status.playing ? 'Tạm dừng' : 'Nghe'}
      >
        <Text style={styles.playText}>{status.playing ? 'Tạm dừng' : 'Nghe'}</Text>
      </Pressable>
      <Pressable
        onPress={(event) => seek(event.nativeEvent.locationX)}
        onLayout={(event) => setWaveWidth(event.nativeEvent.layout.width)}
        style={styles.waveHit}
        accessibilityRole="adjustable"
        accessibilityLabel="Sóng âm"
      >
        <Svg width={Math.max(waveWidth, 1)} height={46}>
          {peaks.map((peak, index) => {
            const slot = Math.max(waveWidth, 1) / peaks.length;
            const height = Math.max(2, Math.min(1, peak) * 40);
            const played = (index + 0.5) / peaks.length <= progress;
            return (
              <Rect
                key={index}
                x={index * slot + slot * 0.15}
                y={(46 - height) / 2}
                width={Math.max(1, slot * 0.7)}
                height={height}
                rx={1.5}
                fill={played ? colors.accent : 'rgba(255,255,255,0.28)'}
              />
            );
          })}
        </Svg>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  daysBlock: {
    marginTop: spacing.sm,
  },
  daysCaption: {
    ...typography.caption,
    color: colors.textTertiary,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  daysRow: {
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
  },
  dayChip: {
    minWidth: 72,
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.06)',
    alignItems: 'center',
  },
  dayChipActive: {
    backgroundColor: colors.surfaceElevated,
  },
  dayWeek: {
    ...typography.caption,
    color: colors.textTertiary,
  },
  dayWeekActive: {
    color: colors.textSecondary,
  },
  dayDate: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
    marginTop: 2,
  },
  dayDateActive: {
    color: colors.text,
  },
  dayChange: {
    fontSize: 12,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
    marginTop: 2,
  },
  player: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
  },
  variantRow: {
    flexDirection: 'row',
    padding: 2,
    borderRadius: 9,
    backgroundColor: 'rgba(255,255,255,0.06)',
  },
  variant: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 8,
    borderRadius: 7,
  },
  variantActive: {
    backgroundColor: 'rgba(255,255,255,0.14)',
  },
  variantText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  variantTextActive: {
    color: colors.text,
  },
  play: {
    marginTop: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: colors.accent,
  },
  playText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  preparing: {
    marginTop: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
  },
  preparingText: {
    ...typography.body,
    color: colors.textSecondary,
  },
  error: {
    ...typography.caption,
    color: colors.negative,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
  waveHit: {
    marginTop: spacing.md,
    height: 46,
  },
});
