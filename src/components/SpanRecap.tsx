import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { setAudioModeAsync, useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import * as Haptics from 'expo-haptics';
import {
  absoluteApiUrl,
  fetchSpan,
  type RecapVariant,
  type SpanMovement,
  type SpanRange,
} from '../api/client';
import { colors, spacing, typography } from '../theme';
import { candleIndexAt, listenWindow } from '../utils/recapCursor';
import type { RecapView } from './SessionRecap';

const VARIANTS: { id: RecapVariant; label: string }[] = [
  { id: 'symphony', label: 'Giao hưởng' },
  { id: 'jazz', label: 'Jazz' },
  { id: 'minimalist', label: 'Tối giản' },
  { id: 'ambient', label: 'Ambient' },
];

const RANGE_LABEL: Record<SpanRange, string> = {
  '1W': 'Tuần',
  '1M': 'Tháng',
  '3M': 'Quý',
  '1Y': 'Năm',
};

type Props = {
  symbol: string;
  range: SpanRange;
  children: (view: RecapView) => React.ReactNode;
};

const EMPTY_VIEW: RecapView = {
  status: 'ready',
  prices: [],
  changePercent: 0,
  cursorIndex: null,
  cursorLabel: null,
  dimUnplayed: false,
};

export function SpanRecap({ symbol, range, children }: Props) {
  const [variant, setVariant] = useState<RecapVariant>('symphony');
  const [movements, setMovements] = useState<SpanMovement[] | null>(null);
  const [index, setIndex] = useState(0);
  const [playEpoch, setPlayEpoch] = useState(0);
  const [composing, setComposing] = useState(false);
  const [resting, setResting] = useState(false);
  const [finished, setFinished] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState<number | null>(null);
  const restTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const request = useRef<AbortController | null>(null);

  const clearRest = useCallback(() => {
    if (restTimer.current) {
      clearTimeout(restTimer.current);
      restTimer.current = null;
    }
    setResting(false);
  }, []);

  const reset = useCallback(() => {
    request.current?.abort();
    request.current = null;
    clearRest();
    setMovements(null);
    setIndex(0);
    setFinished(false);
    setCursor(null);
    setError(null);
    setComposing(false);
  }, [clearRest]);

  useEffect(() => {
    reset();
  }, [range, symbol, variant, reset]);

  useEffect(() => () => clearRest(), [clearRest]);

  const listen = useCallback(() => {
    reset();
    const controller = new AbortController();
    request.current = controller;
    setComposing(true);
    void (async () => {
      try {
        const manifest = await fetchSpan(symbol, range, variant, controller.signal);
        if (controller.signal.aborted) return;
        if (!manifest.movements.length) {
          setError('Chưa đủ phiên để soạn bản này.');
          return;
        }
        setMovements(manifest.movements);
        setIndex(0);
        setPlayEpoch((epoch) => epoch + 1);
      } catch (err) {
        if (controller.signal.aborted) return;
        const text = err instanceof Error ? err.message : '';
        setError(text.includes('API 404') ? 'Chưa đủ dữ liệu cho bản này.' : 'Máy chủ chưa soạn được nhạc.');
      } finally {
        if (request.current === controller) {
          request.current = null;
          setComposing(false);
        }
      }
    })();
  }, [range, reset, symbol, variant]);

  const current = movements?.[index] ?? null;
  const upcoming = movements && index + 1 < movements.length ? movements[index + 1] : null;
  const playing = current != null && !finished;
  const chartWindow = current ? listenWindow(current.prices, upcoming?.prices ?? null) : null;

  const placeCursor = useCallback((elapsed: number, holdAtEnd: boolean) => {
    if (!current) return;
    const count = Math.max(1, current.prices.length);
    const at = holdAtEnd ? count - 1 : candleIndexAt(elapsed, count, current.durationSec);
    setCursor(at);
  }, [current]);

  const onTime = useCallback(
    (elapsed: number) => {
      placeCursor(elapsed, false);
    },
    [placeCursor],
  );

  const onEnded = useCallback(() => {
    if (!current || !movements) return;
    placeCursor(current.durationSec, true);
    const next = index + 1;
    if (next >= movements.length) {
      setFinished(true);
      return;
    }
    const wait = current.restAfterSec * 1000;
    if (wait <= 0) {
      setIndex(next);
      return;
    }
    setResting(true);
    restTimer.current = setTimeout(() => {
      restTimer.current = null;
      setResting(false);
      setIndex(next);
    }, wait);
  }, [current, index, movements, placeCursor]);

  const failPlayback = useCallback(
    (message: string) => {
      clearRest();
      setMovements(null);
      setCursor(null);
      setFinished(false);
      setError(message);
    },
    [clearRest],
  );

  const replay = useCallback(() => {
    clearRest();
    setFinished(false);
    setIndex(0);
    setCursor(null);
    setError(null);
    setPlayEpoch((epoch) => epoch + 1);
  }, [clearRest]);

  const view: RecapView = {
    ...EMPTY_VIEW,
    prices: chartWindow?.prices ?? [],
    cursorIndex: cursor,
    cursorLabel: current ? current.label : null,
    dimUnplayed: Boolean(chartWindow) && !finished && (composing || current != null),
  };

  return (
    <View>
      {children(view)}
      <View style={styles.player}>
        <Text style={styles.caption}>{RANGE_LABEL[range]} · một chương mỗi lần</Text>
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
                <Text style={[styles.variantText, active && styles.variantTextActive]}>{item.label}</Text>
              </Pressable>
            );
          })}
        </View>
        {playing && current ? (
          <MovementPlayer
            key={`${current.audioUrl}#${playEpoch}`}
            movement={current}
            onTime={onTime}
            onEnded={onEnded}
            onError={failPlayback}
          />
        ) : finished ? (
          <Pressable
            onPress={() => {
              void Haptics.selectionAsync();
              replay();
            }}
            style={styles.play}
            accessibilityRole="button"
            accessibilityLabel="Nghe lại"
          >
            <Text style={styles.playText}>Nghe lại</Text>
          </Pressable>
        ) : composing ? (
          <View style={styles.preparing}>
            <ActivityIndicator color={colors.accent} />
            <Text style={styles.preparingText}>Đang xếp chương…</Text>
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
        {resting ? <Text style={styles.rest}>Nghỉ giữa chương</Text> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
      </View>
    </View>
  );
}

function MovementPlayer({
  movement,
  onTime,
  onEnded,
  onError,
}: {
  movement: SpanMovement;
  onTime: (elapsed: number) => void;
  onEnded: () => void;
  onError: (message: string) => void;
}) {
  const player = useAudioPlayer(absoluteApiUrl(movement.audioUrl), {
    updateInterval: 80,
    downloadFirst: true,
  });
  const status = useAudioPlayerStatus(player);
  const started = useRef(false);
  const finished = useRef(false);

  useEffect(() => {
    if (status.error) onError('Máy chủ chưa soạn được nhạc.');
  }, [onError, status.error]);

  useEffect(() => {
    if (started.current || !status.isLoaded || status.error) return;
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
  }, [player, status.error, status.isLoaded]);

  useEffect(() => {
    if (!status.isLoaded) return;
    const duration = movement.durationSec > 0 ? movement.durationSec : status.duration;
    onTime(Math.min(status.currentTime, duration));
    if (status.didJustFinish && !finished.current) {
      finished.current = true;
      onEnded();
    }
  }, [movement.durationSec, onEnded, onTime, status.currentTime, status.didJustFinish, status.duration, status.isLoaded]);

  if (!status.isLoaded) {
    return (
      <View style={styles.preparing}>
        <ActivityIndicator color={colors.accent} />
        <Text style={styles.preparingText}>Đang soạn {movement.label} · {movement.keyLabel}…</Text>
      </View>
    );
  }

  return (
    <Pressable
      onPress={() => {
        void Haptics.selectionAsync();
        if (status.playing) player.pause();
        else player.play();
      }}
      style={styles.play}
      accessibilityRole="button"
    >
      <Text style={styles.playText}>
        {status.playing ? 'Tạm dừng' : 'Tiếp tục'} · {movement.label} · {movement.keyLabel}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  player: {
    marginTop: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  caption: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  variantRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  variant: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: colors.surface,
  },
  variantActive: {
    backgroundColor: colors.accent,
  },
  variantText: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  variantTextActive: {
    color: colors.text,
    fontWeight: '600',
  },
  play: {
    marginTop: spacing.md,
    alignItems: 'center',
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
  rest: {
    ...typography.caption,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
  error: {
    ...typography.caption,
    color: colors.negative,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
});
