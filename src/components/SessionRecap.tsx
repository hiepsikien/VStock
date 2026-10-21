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
import { ambientDailyCandleIndexAt, candleIndexAt, playheadHoldsPoll } from '../utils/recapCursor';
import { isMarketOpen, REFRESH } from '../utils/marketSession';

const VARIANTS: { id: RecapVariant; label: string }[] = [
  { id: 'symphony', label: 'Giao hưởng' },
  { id: 'jazz', label: 'Jazz' },
  { id: 'minimalist', label: 'Tối giản' },
  { id: 'ambient', label: 'Ambient' },
];

export type RecapStatus = 'idle' | 'loading' | 'ready' | 'error';

export type RecapView = {
  status: RecapStatus;
  prices: number[];
  changePercent: number;
  cursorIndex: number | null;
  cursorLabel: string | null;
  dimUnplayed: boolean;
};

type Props = {
  symbol: string;
  children: (view: RecapView) => React.ReactNode;
};

const EMPTY_VIEW: RecapView = {
  status: 'idle',
  prices: [],
  changePercent: 0,
  cursorIndex: null,
  cursorLabel: null,
  dimUnplayed: false,
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

function isAbort(error: unknown): boolean {
  return error instanceof Error && (error.name === 'AbortError' || /aborted/i.test(error.message));
}

const GREW_DURING_COMPOSE = 'Phiên vừa thêm nến trong lúc soạn. Bấm Nghe lại.';

function pieceMatches(
  manifest: RecapManifest | null,
  series: SessionMinutes | null,
  variant: RecapVariant,
  selected: string | null,
): manifest is RecapManifest {
  return (
    manifest != null &&
    series != null &&
    selected != null &&
    manifest.date === series.date &&
    series.date === selected &&
    manifest.variant === variant &&
    manifest.barCount === series.prices.length
  );
}

export function SessionRecap({ symbol, children }: Props) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [variant, setVariant] = useState<RecapVariant>('symphony');
  const [series, setSeries] = useState<SessionMinutes | null>(null);
  const [manifest, setManifest] = useState<RecapManifest | null>(null);
  const [composing, setComposing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [listenError, setListenError] = useState<string | null>(null);
  const [autoplay, setAutoplay] = useState(false);
  const [cursor, setCursor] = useState<{ index: number; label: string } | null>(null);
  const [playbackActive, setPlaybackActive] = useState(false);
  const cursorActive = useRef(false);
  const recapAbort = useRef<AbortController | null>(null);
  const variantChanged = useRef(false);
  const seriesRef = useRef<SessionMinutes | null>(null);
  const manifestRef = useRef<RecapManifest | null>(null);
  const selectedRef = useRef<string | null>(null);
  const variantRef = useRef<RecapVariant>('symphony');
  const seriesEpoch = useRef(0);
  seriesRef.current = series;
  manifestRef.current = manifest;
  selectedRef.current = selected;
  variantRef.current = variant;

  const abortRecap = useCallback(() => {
    recapAbort.current?.abort();
    recapAbort.current = null;
  }, []);

  const onCursor = useCallback((index: number | null, label: string | null, holdPoll = false) => {
    const active = holdPoll && index != null;
    cursorActive.current = active;
    setPlaybackActive(active);
    setCursor(index == null || label == null ? null : { index, label });
  }, []);

  const clearPlayhead = useCallback(() => {
    cursorActive.current = false;
    setPlaybackActive(false);
    setCursor(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    abortRecap();
    setSessions([]);
    setSelected(null);
    setSeries(null);
    setManifest(null);
    clearPlayhead();
    setLoadError(null);
    setListenError(null);
    setComposing(false);
    setAutoplay(false);
    void (async () => {
      try {
        const rows = await fetchSessions(symbol);
        if (cancelled) return;
        setSessions(rows);
        setSelected(rows.length ? rows[rows.length - 1].date : null);
      } catch (err) {
        if (!cancelled) setLoadError(recapErrorMessage(err));
      }
    })();
    return () => {
      cancelled = true;
      abortRecap();
    };
  }, [abortRecap, clearPlayhead, symbol]);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    let cancelled = false;
    abortRecap();
    setSeries(null);
    setManifest(null);
    clearPlayhead();
    setLoadError(null);
    setListenError(null);
    setComposing(false);
    setAutoplay(false);
    void (async () => {
      try {
        const detail = await fetchSessionMinutes(symbol, selected, controller.signal);
        if (cancelled) return;
        setSeries(detail);
      } catch (err) {
        if (cancelled || isAbort(err)) return;
        setSeries(null);
        setLoadError(recapErrorMessage(err));
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
      abortRecap();
    };
  }, [abortRecap, clearPlayhead, selected, symbol]);

  useEffect(() => {
    if (!variantChanged.current) {
      variantChanged.current = true;
      return;
    }
    abortRecap();
    setManifest(null);
    clearPlayhead();
    setListenError(null);
    setComposing(false);
    setAutoplay(false);
  }, [abortRecap, clearPlayhead, variant]);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    let inflight: AbortController | null = null;
    const timer = setInterval(() => {
      if (cursorActive.current || !isMarketOpen() || selected !== vnToday()) return;
      inflight?.abort();
      const controller = new AbortController();
      inflight = controller;
      const epoch = seriesEpoch.current;
      void (async () => {
        try {
          const detail = await fetchSessionMinutes(symbol, selected, controller.signal);
          if (cancelled || cursorActive.current || detail.date !== selected) return;
          if (seriesEpoch.current !== epoch) return;
          setSeries(detail);
          if (pieceMatches(manifestRef.current, detail, variantRef.current, selected)) return;
          clearPlayhead();
          setManifest(null);
        } catch (err) {
          if (cancelled || isAbort(err)) return;
          /* keep the session on screen */
        }
      })();
    }, REFRESH.chart1dPollMs);
    return () => {
      cancelled = true;
      inflight?.abort();
      clearInterval(timer);
    };
  }, [clearPlayhead, selected, symbol]);

  const listen = useCallback(() => {
    const day = selectedRef.current;
    const current = seriesRef.current;
    const chosen = variantRef.current;
    if (!day || !current || current.date !== day) return;
    abortRecap();
    const controller = new AbortController();
    recapAbort.current = controller;
    setComposing(true);
    setListenError(null);
    setManifest(null);
    setAutoplay(false);
    const stillHere = () =>
      !controller.signal.aborted &&
      selectedRef.current === day &&
      variantRef.current === chosen;
    const composeOnce = async () => {
      const recap = await fetchRecap(symbol, day, chosen, controller.signal);
      if (!stillHere()) return null;
      const detail = await fetchSessionMinutes(symbol, day, controller.signal);
      if (!stillHere()) return null;
      return { recap, detail };
    };
    void (async () => {
      try {
        // The chart is up to five minutes old. The server composes whatever
        // candles it has when Nghe is pressed, so reload that snapshot and
        // play it. If the session grew during export, compose that pass once.
        let pass = await composeOnce();
        if (!pass || !stillHere()) return;
        const samePiece = (recap: RecapManifest, detail: SessionMinutes) =>
          recap.date === detail.date &&
          recap.variant === chosen &&
          recap.barCount === detail.prices.length;
        if (!samePiece(pass.recap, pass.detail)) {
          pass = await composeOnce();
          if (!pass || !stillHere()) return;
        }
        if (!samePiece(pass.recap, pass.detail)) {
          seriesEpoch.current += 1;
          setSeries(pass.detail);
          setListenError(GREW_DURING_COMPOSE);
          return;
        }
        seriesEpoch.current += 1;
        setSeries(pass.detail);
        setManifest(pass.recap);
        setAutoplay(true);
      } catch (err) {
        if (controller.signal.aborted || isAbort(err)) return;
        if (selectedRef.current === day && variantRef.current === chosen) {
          setListenError(recapErrorMessage(err));
        }
      } finally {
        if (recapAbort.current === controller) {
          recapAbort.current = null;
          setComposing(false);
        }
      }
    })();
  }, [abortRecap, symbol]);

  const ready = series != null && series.date === selected;
  const playingPiece = pieceMatches(manifest, series, variant, selected);
  const dimUnplayed =
    composing || (playingPiece && (playbackActive || (autoplay && cursor == null)));
  const view: RecapView = loadError
    ? { ...EMPTY_VIEW, status: 'error' }
    : ready && series
      ? {
          status: 'ready',
          prices: series.prices,
          changePercent: series.changePercent,
          cursorIndex: cursor?.index ?? null,
          cursorLabel: cursor?.label ?? null,
          dimUnplayed,
        }
      : selected
        ? { ...EMPTY_VIEW, status: 'loading' }
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

      {loadError ? <Text style={[styles.error, styles.errorInset]}>{loadError}</Text> : null}

      {children(view)}

      {ready && series ? (
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

          {playingPiece && manifest ? (
            <RecapPlayer
              key={manifest.audioUrl}
              manifest={manifest}
              times={series.times}
              autoplay={autoplay}
              onCursor={onCursor}
            />
          ) : composing ? (
            <View style={styles.preparing}>
              <ActivityIndicator color={colors.accent} />
              <Text style={styles.preparingText}>Đang soạn nhạc…</Text>
            </View>
          ) : (
            <Pressable
              onPress={() => {
                void Haptics.selectionAsync();
                listen();
              }}
              style={styles.play}
              accessibilityRole="button"
              accessibilityLabel="Nghe"
            >
              <Text style={styles.playText}>Nghe</Text>
            </Pressable>
          )}

          {listenError ? <Text style={styles.error}>{listenError}</Text> : null}
        </View>
      ) : null}
    </View>
  );
}

function RecapPlayer({
  manifest,
  times,
  autoplay,
  onCursor,
}: {
  manifest: RecapManifest;
  times: string[];
  autoplay: boolean;
  onCursor: (index: number | null, label: string | null, holdPoll?: boolean) => void;
}) {
  const player = useAudioPlayer(absoluteApiUrl(manifest.audioUrl), {
    updateInterval: 80,
    downloadFirst: true,
  });
  const status = useAudioPlayerStatus(player);
  const [waveWidth, setWaveWidth] = useState(0);
  const started = useRef(false);
  const hasHeard = useRef(false);
  const ended = useRef(false);
  const seekingTarget = useRef<number | null>(null);
  const ignoreDidJustFinish = useRef(false);

  useEffect(() => {
    if (!autoplay || started.current || !status.isLoaded) return;
    let cancelled = false;
    void (async () => {
      await setAudioModeAsync({ playsInSilentMode: true });
      if (cancelled || started.current) return;
      started.current = true;
      player.play();
    })();
    return () => {
      cancelled = true;
    };
  }, [autoplay, player, status.isLoaded]);

  useEffect(() => {
    return () => onCursor(null, null);
  }, [onCursor]);

  useEffect(() => {
    const fileDuration = status.duration > 0 ? status.duration : manifest.durationSec;
    const mapDuration =
      manifest.mapDurationSec > 0 ? manifest.mapDurationSec : fileDuration;
    if (status.playing) {
      seekingTarget.current = null;
      ignoreDidJustFinish.current = false;
    } else if (
      seekingTarget.current != null &&
      Math.abs(status.currentTime - seekingTarget.current) <= 0.5
    ) {
      seekingTarget.current = null;
    }
    const effectiveTime =
      seekingTarget.current != null ? seekingTarget.current : status.currentTime;
    const effectiveDidJustFinish =
      status.didJustFinish && !ignoreDidJustFinish.current;
    if (status.playing || effectiveTime > 0.05) {
      hasHeard.current = true;
    }
    const heard = hasHeard.current;
    if (!heard || times.length < 1) {
      ended.current = false;
      onCursor(null, null);
      return;
    }
    const index =
      manifest.variant === 'ambient'
        ? ambientDailyCandleIndexAt(effectiveTime, times.length, mapDuration)
        : candleIndexAt(effectiveTime, times.length, mapDuration);
    const stillRunning = playheadHoldsPoll({
      playing: status.playing,
      currentTime: effectiveTime,
      mapDurationSec: mapDuration,
      fileDurationSec: fileDuration,
      didJustFinish: effectiveDidJustFinish,
      started: hasHeard.current,
    });
    if (!stillRunning) ended.current = true;
    if (status.playing && stillRunning) ended.current = false;
    onCursor(index, times[index] ?? null, stillRunning && !ended.current);
  }, [
    manifest.durationSec,
    manifest.mapDurationSec,
    manifest.variant,
    onCursor,
    status.currentTime,
    status.didJustFinish,
    status.duration,
    status.playing,
    times,
  ]);

  const duration = status.duration > 0 ? status.duration : manifest.durationSec;
  const progress = duration > 0 ? Math.min(1, Math.max(0, status.currentTime / duration)) : 0;
  const peaks = manifest.peaks.length ? manifest.peaks : [0.2];

  const toggle = () => {
    void Haptics.selectionAsync();
    if (!status.isLoaded) return;
    if (status.playing) player.pause();
    else player.play();
  };

  const seek = (locationX: number) => {
    if (waveWidth <= 0 || duration <= 0) return;
    const ratio = Math.min(1, Math.max(0, locationX / waveWidth));
    const targetSec = ratio * duration;
    const mapDuration =
      manifest.mapDurationSec > 0 ? manifest.mapDurationSec : duration;
    hasHeard.current = true;
    seekingTarget.current = targetSec;
    ignoreDidJustFinish.current = true;
    if (times.length > 0) {
      const index =
        manifest.variant === 'ambient'
          ? ambientDailyCandleIndexAt(targetSec, times.length, mapDuration)
          : candleIndexAt(targetSec, times.length, mapDuration);
      const holds = playheadHoldsPoll({
        playing: status.playing,
        currentTime: targetSec,
        mapDurationSec: mapDuration,
        fileDurationSec: duration,
        didJustFinish: false,
        started: true,
      });
      ended.current = !holds;
      onCursor(index, times[index] ?? null, holds);
    }
    void player.seekTo(targetSec);
  };

  return (
    <View>
      <Pressable
        onPress={toggle}
        style={styles.play}
        accessibilityRole="button"
        accessibilityLabel={status.playing ? 'Tạm dừng' : 'Nghe'}
      >
        <Text style={styles.playText}>
          {!status.isLoaded ? 'Đang tải…' : status.playing ? 'Tạm dừng' : 'Nghe'}
        </Text>
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
  errorInset: {
    marginHorizontal: spacing.lg,
  },
  waveHit: {
    marginTop: spacing.md,
    height: 46,
  },
});
