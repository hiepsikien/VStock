import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { setAudioModeAsync, useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import * as Haptics from 'expo-haptics';
import {
  absoluteApiUrl,
  ENSEMBLE_ROWS,
  fetchSpan,
  type RecapEnsemble,
  type RecapVariant,
  type SpanMovement,
  type SpanRange,
} from '../api/client';
import { colors, spacing, typography } from '../theme';
import {
  chartFocus,
  lerpFocus,
  movementOffsets,
  pieceCopy,
  pieceKey,
  type ChartFocus,
  type PieceProgram,
} from '../sonify/program';
import { spanCandleIndexAt } from '../utils/recapCursor';
import { MixToggles } from './MixToggles';
import type { RecapView } from './SessionRecap';

const VARIANTS: { id: RecapVariant; label: string }[] = [
  { id: 'symphony', label: 'Giao hưởng' },
  { id: 'jazz', label: 'Jazz' },
  { id: 'minimalist', label: 'Tối giản' },
  { id: 'ambient', label: 'Ambient' },
  { id: 'guitar', label: 'Guitar' },
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
  program: null,
  focus: null,
};

export function SpanRecap({ symbol, range, children }: Props) {
  const [variant, setVariant] = useState<RecapVariant>('symphony');
  const [ensemble, setEnsemble] = useState<RecapEnsemble>('classic');
  const [humanize, setHumanize] = useState(true);
  const [colorOn, setColorOn] = useState(true);
  const [movements, setMovements] = useState<SpanMovement[] | null>(null);
  const [index, setIndex] = useState(0);
  const [playEpoch, setPlayEpoch] = useState(0);
  const [composing, setComposing] = useState(false);
  const [resting, setResting] = useState(false);
  const [finished, setFinished] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [audible, setAudible] = useState(false);
  const [asOf, setAsOf] = useState('');
  const [homeKey, setHomeKey] = useState('');
  const [focus, setFocus] = useState<ChartFocus | null>(null);
  const focusRef = useRef<ChartFocus | null>(null);
  const zoomFrame = useRef(0);
  const restTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const request = useRef<AbortController | null>(null);
  const namesRequest = useRef<AbortController | null>(null);

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
    namesRequest.current?.abort();
    namesRequest.current = null;
    clearRest();
    setMovements(null);
    setIndex(0);
    setFinished(false);
    setCursor(null);
    setElapsed(0);
    setAudible(false);
    setAsOf('');
    setHomeKey('');
    setFocus(null);
    focusRef.current = null;
    setError(null);
    setComposing(false);
  }, [clearRest]);

  useEffect(() => {
    reset();
  }, [colorOn, ensemble, humanize, range, symbol, variant, reset]);

  useEffect(() => () => clearRest(), [clearRest]);

  const listen = useCallback(() => {
    reset();
    const controller = new AbortController();
    request.current = controller;
    setComposing(true);
    void (async () => {
      try {
        const manifest = await fetchSpan(symbol, range, variant, ensemble, controller.signal, {
          humanize,
          color: colorOn,
        });
        if (controller.signal.aborted) return;
        if (!manifest.movements.length) {
          setError('Chưa đủ phiên để soạn bản này.');
          return;
        }
        setMovements(manifest.movements);
        setAsOf(manifest.asOf ?? '');
        setHomeKey(manifest.keyLabel ?? '');
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
  }, [colorOn, ensemble, humanize, range, reset, symbol, variant]);

  const current = movements?.[index] ?? null;
  const playing = current != null && !finished;
  const lengths = movements?.map((item) => item.prices.length) ?? [];
  const offsets = movementOffsets(lengths);
  const total = lengths.reduce((sum, length) => sum + length, 0);
  const multi = (movements?.length ?? 0) > 1;
  const shown = movements != null && current != null && (playing || resting || finished);
  const targetFocus = shown
    ? chartFocus({
        total,
        offsets,
        lengths,
        index,
        elapsed,
        resting: resting || finished,
        audible,
        multi,
      })
    : null;

  const placeCursor = useCallback((elapsed: number, holdAtEnd: boolean) => {
    if (!current) return;
    const count = Math.max(1, current.prices.length);
    const at = holdAtEnd
      ? count - 1
      : spanCandleIndexAt(
          elapsed,
          count,
          current.durationSec,
          current.warmupSec,
          current.cooldownSec,
        );
    setCursor(at);
    setElapsed(elapsed);
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
      setAudible(false);
      setCursor(0);
      setElapsed(0);
      setIndex(next);
      return;
    }
    setResting(true);
    restTimer.current = setTimeout(() => {
      restTimer.current = null;
      setResting(false);
      setAudible(false);
      setCursor(0);
      setElapsed(0);
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

  const refreshNames = useCallback((): Promise<void> => {
    if (variant !== 'guitar') return Promise.resolve();
    // A file already on disk reported its dance on the manifest. An empty name
    // there stays empty; only a render that just finished can add one.
    if (current?.name?.trim() || current?.ready) return Promise.resolve();
    if (!namesRequest.current || namesRequest.current.signal.aborted) {
      namesRequest.current = new AbortController();
    }
    const signal = namesRequest.current.signal;
    return (async () => {
      try {
        const manifest = await fetchSpan(symbol, range, variant, ensemble, signal, {
          humanize,
          color: colorOn,
        });
        if (signal.aborted) return;
        setMovements((existing) => {
          if (!existing) return existing;
          let changed = false;
          const next = existing.map((item, itemIndex) => {
            const incoming = manifest.movements[itemIndex]?.name?.trim() ?? '';
            if (!incoming || item.name?.trim()) return item;
            changed = true;
            return { ...item, name: incoming };
          });
          return changed ? next : existing;
        });
      } catch {
        // A missing dance stays blank. The title does not invent one.
      }
    })();
  }, [colorOn, current?.name, current?.ready, ensemble, humanize, range, symbol, variant]);

  const markAudible = useCallback(() => setAudible(true), []);

  const replay = useCallback(() => {
    clearRest();
    setFinished(false);
    setIndex(0);
    setCursor(null);
    setElapsed(0);
    setAudible(false);
    setError(null);
    setPlayEpoch((epoch) => epoch + 1);
  }, [clearRest]);

  const focusStart = targetFocus?.start ?? null;
  const focusEnd = targetFocus?.end ?? null;
  useEffect(() => {
    cancelAnimationFrame(zoomFrame.current);
    if (focusStart == null || focusEnd == null) {
      focusRef.current = null;
      setFocus(null);
      return;
    }
    const target = { start: focusStart, end: focusEnd };
    const from = focusRef.current ?? target;
    if (from.start === target.start && from.end === target.end) {
      focusRef.current = target;
      setFocus(target);
      return;
    }
    const started = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - started) / 900);
      const next = lerpFocus(from, target, t);
      focusRef.current = next;
      setFocus(next);
      if (t < 1) zoomFrame.current = requestAnimationFrame(step);
    };
    zoomFrame.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(zoomFrame.current);
  }, [focusEnd, focusStart]);

  const length = Math.max(1, lengths[index] ?? 1);
  const globalCursor =
    shown && cursor != null ? (offsets[index] ?? 0) + Math.min(cursor, length - 1) : null;
  const prices = useMemo(
    () => (shown && movements ? movements.flatMap((item) => item.prices) : []),
    [movements, shown],
  );
  const program: PieceProgram | null =
    shown && movements && current && !finished
      ? {
          ...pieceCopy(
            {
              variant,
              ensemble,
              symbol,
              date: asOf,
              keyLabel: pieceKey(
                homeKey,
                movements.map((item) => item.keyLabel),
              ),
              span: range,
              movements: movements.map((item) => ({
                character: item.character ?? null,
                keyLabel: item.keyLabel,
                prices: item.prices,
                label: item.label,
                bpm: item.bpm,
                beats: item.beats,
                beatType: item.beatType,
                name: item.name,
              })),
            },
            index,
          ),
          phase: audible ? 'playing' : 'intro',
        }
      : null;

  const view: RecapView = {
    ...EMPTY_VIEW,
    prices,
    cursorIndex: globalCursor,
    cursorLabel: shown && current ? current.label : null,
    dimUnplayed: shown && !finished,
    program,
    focus: shown ? (focus ?? targetFocus) : null,
  };

  return (
    <View>
      {children(view)}
      <View style={styles.player}>
        <Text style={styles.caption}>{RANGE_LABEL[range]} · một chương mỗi lần</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.variantRow}
        >
          {VARIANTS.map((item) => {
            const active = item.id === variant;
            return (
              <Pressable
                key={item.id}
                onPress={() => {
                  void Haptics.selectionAsync();
                  setVariant(item.id);
                  setEnsemble('classic');
                }}
                style={[styles.variant, active && styles.variantActive]}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
              >
                <Text
                  style={[styles.variantText, active && styles.variantTextActive]}
                  numberOfLines={1}
                >
                  {item.label}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
        <View style={[styles.variantRow, styles.ensembleRow]}>
          {ENSEMBLE_ROWS[variant].map((item) => {
            const active = item.id === ensemble;
            return (
              <Pressable
                key={item.id}
                onPress={() => {
                  void Haptics.selectionAsync();
                  setEnsemble(item.id);
                }}
                style={[styles.variant, active && styles.variantActive]}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
              >
                <Text style={[styles.variantText, active && styles.variantTextActive]} numberOfLines={1}>
                  {item.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <MixToggles
          humanize={humanize}
          colorOn={colorOn}
          onHumanize={setHumanize}
          onColor={setColorOn}
        />
        {playing && current ? (
          <MovementPlayer
            key={`${current.audioUrl}#${playEpoch}`}
            movement={current}
            onTime={onTime}
            onEnded={onEnded}
            onError={failPlayback}
            onLoaded={refreshNames}
            onAudible={markAudible}
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

function movementCaption(movement: SpanMovement, currentTime: number): string {
  const sessions = movement.sessionCharacters ?? [];
  if (sessions.length > 1) {
    const bar = Math.floor(currentTime / ((8 * 30) / 90));
    const index = Math.min(sessions.length - 1, Math.max(0, Math.floor(bar / 32)));
    return ` · Phiên ${index + 1} · ${sessions[index]}`;
  }
  return movement.characterLabel ? ` · ${movement.characterLabel}` : '';
}

function MovementPlayer({
  movement,
  onTime,
  onEnded,
  onError,
  onLoaded,
  onAudible,
}: {
  movement: SpanMovement;
  onTime: (elapsed: number) => void;
  onEnded: () => void;
  onError: (message: string) => void;
  onLoaded?: () => void | Promise<void>;
  onAudible?: () => void;
}) {
  const player = useAudioPlayer(absoluteApiUrl(movement.audioUrl), {
    updateInterval: 80,
    downloadFirst: true,
  });
  const status = useAudioPlayerStatus(player);
  const started = useRef(false);
  const finished = useRef(false);
  const onLoadedRef = useRef(onLoaded);
  const onAudibleRef = useRef(onAudible);
  onLoadedRef.current = onLoaded;
  onAudibleRef.current = onAudible;

  useEffect(() => {
    if (status.error) onError('Máy chủ chưa soạn được nhạc.');
  }, [onError, status.error]);

  useEffect(() => {
    if (started.current || !status.isLoaded || status.error) return;
    let cancelled = false;
    void (async () => {
      await setAudioModeAsync({ playsInSilentMode: true });
      if (cancelled || started.current) return;
      const hadName = Boolean(movement.name?.trim());
      await onLoadedRef.current?.();
      if (cancelled || started.current) return;
      // Let the card paint the movement name before playback replaces it.
      if (!hadName) {
        await new Promise<void>((resolve) => {
          requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
        });
      }
      if (cancelled || started.current) return;
      started.current = true;
      onAudibleRef.current?.();
      player.play();
    })();
    return () => {
      cancelled = true;
    };
  }, [movement.name, player, status.error, status.isLoaded]);

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
        <Text style={styles.preparingText}>
          Đang soạn {movement.label} · {movement.keyLabel}
          {movement.characterLabel ? ` · ${movement.characterLabel}` : ''}…
        </Text>
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
        {movementCaption(movement, status.currentTime)}
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
  ensembleRow: {
    marginTop: spacing.sm,
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
