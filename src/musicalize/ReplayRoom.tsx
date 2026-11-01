import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  absoluteApiUrl,
  DEFAULT_SYMBOLS,
  fetchMarketSymbols,
  fetchRecap,
  fetchSessionMinutes,
  fetchSessions,
  fetchSpan,
  type RecapEnsemble,
  type RecapManifest,
  type RecapVariant,
  type SessionMinutes,
  type SessionSummary,
  type SpanMovement,
} from '../api/client';
import {
  chartFocus,
  englishDate,
  englishKey,
  lerpFocus,
  movementOffsets,
  pieceCopy,
  pieceKey,
  type ChartFocus,
  type PieceProgram,
} from '../sonify/program';
import { Controls } from './Controls';
import { clockText, GENRES, type ListenSpan } from './labels';
import { RoomFrame } from './RoomFrame';
import { ReplayPlayer, type SeekCommand } from './ReplayPlayer';
import { TopBar } from './TopBar';
import { useKeyboard } from './useKeyboard';
import { useQuotes } from './useQuotes';
import {
  dailyMapClock,
  dailyStageSeek,
  movementFrameSettled,
  placeOnWork,
  replayAction,
  scrubberSeek,
  spanMapClock,
  spanStageSeek,
  workDuration,
  workSecondsAt,
  clamp01,
} from './seek';
import { Stage } from './Stage';
import { SymbolColumn, type SymbolChoice } from './SymbolColumn';
import { ambientDailyCandleIndexAt, spanCandleIndexAt } from '../utils/recapCursor';

type Props = {
  wide: boolean;
  onMode: (mode: 'replay' | 'live') => void;
};

function failureText(error: unknown, span: ListenSpan): string {
  const text = error instanceof Error ? error.message : '';
  if (text.includes('API 404')) {
    return span === '1D' ? 'Phiên này chưa có nến 1 phút.' : 'Chưa đủ dữ liệu cho bản này.';
  }
  if (text.includes('API 503')) return 'Máy chủ chưa soạn được nhạc.';
  return span === '1D' ? 'Không tải được phiên.' : 'Máy chủ chưa soạn được nhạc.';
}

function isAbort(error: unknown): boolean {
  return error instanceof Error && (error.name === 'AbortError' || /aborted/i.test(error.message));
}

function joinedVolumes(parts: { prices: number[]; volumes?: number[] }[]): number[] | null {
  if (parts.some((item) => !item.volumes || item.volumes.length !== item.prices.length)) return null;
  const volumes = parts.flatMap((item) => item.volumes ?? []);
  return volumes.length ? volumes : null;
}

export function ReplayRoom({ wide, onMode }: Props) {
  const [symbols, setSymbols] = useState<SymbolChoice[]>(
    DEFAULT_SYMBOLS.map((symbol) => ({ symbol, name: symbol })),
  );
  const [filter, setFilter] = useState('');
  const [symbol, setSymbol] = useState('VNM');
  const [span, setSpan] = useState<ListenSpan>('1D');
  const [variant, setVariant] = useState<RecapVariant>('symphony');
  const [ensemble, setEnsemble] = useState<RecapEnsemble>('classic');
  const [humanize, setHumanize] = useState(true);
  const [colorOn, setColorOn] = useState(true);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [date, setDate] = useState<string | null>(null);
  const [series, setSeries] = useState<SessionMinutes | null>(null);
  const [manifest, setManifest] = useState<RecapManifest | null>(null);
  const [movements, setMovements] = useState<SpanMovement[] | null>(null);
  const [spanLine, setSpanLine] = useState<{ key: string; prices: number[]; volumes?: number[] } | null>(null);
  const [asOf, setAsOf] = useState('');
  const [homeKey, setHomeKey] = useState('');
  const [index, setIndex] = useState(0);
  const [movementTime, setMovementTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [finished, setFinished] = useState(false);
  const [resting, setResting] = useState(false);
  const [restOffset, setRestOffset] = useState(0);
  const [audible, setAudible] = useState(false);
  const [composing, setComposing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parked, setParked] = useState(false);
  const [mediaDuration, setMediaDuration] = useState(0);
  const [playEpoch, setPlayEpoch] = useState(0);
  const [startSec, setStartSec] = useState(0);
  const [seek, setSeek] = useState<SeekCommand | null>(null);
  const [focus, setFocus] = useState<ChartFocus | null>(null);
  const [focusSignal, setFocusSignal] = useState(0);

  const request = useRef<AbortController | null>(null);
  const restTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const seekSeq = useRef(0);
  const focusRef = useRef<ChartFocus | null>(null);
  const zoomFrame = useRef(0);
  const movementsRef = useRef<SpanMovement[] | null>(null);
  const indexRef = useRef(0);
  const playingRef = useRef(false);
  movementsRef.current = movements;
  indexRef.current = index;
  playingRef.current = playing;

  const clearRest = useCallback(() => {
    if (restTimer.current) {
      clearInterval(restTimer.current);
      restTimer.current = null;
    }
  }, []);

  const clearPlayback = useCallback(() => {
    request.current?.abort();
    request.current = null;
    clearRest();
    setManifest(null);
    setMovements(null);
    setAsOf('');
    setHomeKey('');
    setIndex(0);
    setMovementTime(0);
    setPlaying(false);
    setFinished(false);
    setResting(false);
    setRestOffset(0);
    setAudible(false);
    setParked(false);
    setComposing(false);
    setError(null);
    setMediaDuration(0);
    setStartSec(0);
    setSeek(null);
    setFocus(null);
    focusRef.current = null;
  }, [clearRest]);

  useEffect(() => {
    return () => {
      request.current?.abort();
      clearRest();
    };
  }, [clearRest]);

  const signature = `${symbol}|${span}|${date ?? ''}|${variant}|${ensemble}|${humanize ? 1 : 0}|${colorOn ? 1 : 0}`;
  const signatureRef = useRef(signature);
  useEffect(() => {
    if (signatureRef.current === signature) return;
    signatureRef.current = signature;
    clearPlayback();
  }, [clearPlayback, signature]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const rows = await fetchMarketSymbols();
        if (cancelled || !rows.length) return;
        setSymbols(rows.map((item) => ({ symbol: item.symbol, name: item.name, exchange: item.exchange })));
        setSymbol((current) => {
          if (rows.some((item) => item.symbol === current)) return current;
          return rows.find((item) => item.symbol === 'VNM')?.symbol ?? rows[0].symbol;
        });
      } catch {
        if (!cancelled) setError('Không tải được danh sách mã.');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const quoteSymbols = useMemo(() => {
    const query = filter.trim().toUpperCase();
    const shown = query
      ? symbols.filter(
          (item) => item.symbol.includes(query) || item.name.toUpperCase().includes(query),
        )
      : symbols;
    return shown.map((item) => item.symbol);
  }, [filter, symbols]);
  const quotes = useQuotes(quoteSymbols);

  useEffect(() => {
    if (span !== '1D') return;
    let cancelled = false;
    void (async () => {
      try {
        const rows = await fetchSessions(symbol);
        if (cancelled) return;
        setSessions(rows);
        setDate((current) => {
          if (current && rows.some((row) => row.date === current)) return current;
          return rows.length ? rows[rows.length - 1].date : null;
        });
      } catch (err) {
        if (!cancelled) setError(failureText(err, '1D'));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [span, symbol]);

  useEffect(() => {
    if (span !== '1D' || !date) {
      setSeries(null);
      return;
    }
    setSeries(null);
    const controller = new AbortController();
    let cancelled = false;
    void (async () => {
      try {
        const detail = await fetchSessionMinutes(symbol, date, controller.signal);
        if (!cancelled) setSeries(detail);
      } catch (err) {
        if (cancelled || isAbort(err)) return;
        setSeries(null);
        setError(failureText(err, '1D'));
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [date, span, symbol]);

  const spanKey = `${symbol}|${span}|${variant}|${ensemble}|${humanize ? 1 : 0}|${colorOn ? 1 : 0}`;
  useEffect(() => {
    if (span === '1D') return;
    const controller = new AbortController();
    let cancelled = false;
    const key = spanKey;
    void (async () => {
      try {
        const plan = await fetchSpan(symbol, span, variant, ensemble, controller.signal, {
          humanize,
          color: colorOn,
        });
        if (cancelled) return;
        const prices = plan.movements.flatMap((item) => item.prices);
        const volumes = joinedVolumes(plan.movements);
        setSpanLine(prices.length > 1 ? { key, prices, ...(volumes ? { volumes } : {}) } : null);
      } catch (err) {
        if (cancelled || isAbort(err)) return;
        setSpanLine(null);
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [colorOn, ensemble, humanize, span, spanKey, symbol, variant]);

  const seekTarget = useRef<number | null>(null);

  const issueSeek = useCallback((seconds: number) => {
    seekTarget.current = seconds;
    const id = ++seekSeq.current;
    setSeek({ id, seconds });
  }, []);

  const beginRest = useCallback(
    (afterIndex: number, restSec: number, already: number) => {
      clearRest();
      const total = Math.max(0, restSec);
      const startOffset = Math.min(total, Math.max(0, already));
      setResting(true);
      setRestOffset(startOffset);
      setIndex(afterIndex);
      const endsAt = Date.now() + (total - startOffset) * 1000;
      restTimer.current = setInterval(() => {
        const remainMs = endsAt - Date.now();
        if (remainMs <= 0) {
          clearRest();
          setResting(false);
          setRestOffset(0);
          setAudible(false);
          setMovementTime(0);
          setStartSec(0);
          setSeek(null);
          setIndex(afterIndex + 1);
          setPlayEpoch((epoch) => epoch + 1);
          return;
        }
        setRestOffset(total - remainMs / 1000);
      }, 200);
    },
    [clearRest],
  );

  const onTime = useCallback((seconds: number) => {
    if (seekTarget.current != null && Math.abs(seconds - seekTarget.current) > 0.6) return;
    seekTarget.current = null;
    setMovementTime(seconds);
    // Playback must not clear `parked`. The next Nghe lại, after the press
    // that returned to this movement, still goes to the start of the work.
  }, []);

  const onEnded = useCallback(() => {
    if (span === '1D') {
      setPlaying(false);
      setFinished(true);
      const end = mediaDuration > 0 ? mediaDuration : manifest?.durationSec ?? 0;
      if (end > 0) setMovementTime(end);
      return;
    }
    const currentMovements = movementsRef.current;
    const currentIndex = indexRef.current;
    const movement = currentMovements?.[currentIndex];
    if (!movement || !currentMovements) return;
    const next = currentIndex + 1;
    const end = mediaDuration > 0 ? mediaDuration : movement.durationSec;
    setMovementTime(end);
    if (next >= currentMovements.length) {
      setPlaying(false);
      setFinished(true);
      return;
    }
    if (movement.restAfterSec <= 0) {
      setAudible(false);
      setMovementTime(0);
      setStartSec(0);
      setSeek(null);
      setIndex(next);
      setPlayEpoch((epoch) => epoch + 1);
      return;
    }
    beginRest(currentIndex, movement.restAfterSec, 0);
  }, [beginRest, manifest, mediaDuration, span]);

  const listen = useCallback(() => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setComposing(true);
    setError(null);
    setFinished(false);
    setParked(false);
    const chosenSymbol = symbol;
    const chosenSpan = span;
    const chosenVariant = variant;
    const chosenEnsemble = ensemble;
    const shaped = humanize;
    const tinted = colorOn;
    const chosenDate = date;
    void (async () => {
      try {
        if (chosenSpan === '1D') {
          if (!chosenDate) return;
          const recap = await fetchRecap(chosenSymbol, chosenDate, chosenVariant, chosenEnsemble, controller.signal, {
            humanize: shaped,
            color: tinted,
          });
          if (controller.signal.aborted) return;
          const detail = await fetchSessionMinutes(chosenSymbol, chosenDate, controller.signal);
          if (controller.signal.aborted) return;
          if (recap.barCount !== detail.prices.length) {
            const again = await fetchRecap(chosenSymbol, chosenDate, chosenVariant, chosenEnsemble, controller.signal, {
              humanize: shaped,
              color: tinted,
            });
            const fresh = await fetchSessionMinutes(chosenSymbol, chosenDate, controller.signal);
            if (controller.signal.aborted) return;
            if (again.barCount !== fresh.prices.length) {
              setSeries(fresh);
              setError('Phiên vừa thêm nến trong lúc soạn. Bấm Nghe lại.');
              return;
            }
            setSeries(fresh);
            setManifest(again);
          } else {
            setSeries(detail);
            setManifest(recap);
          }
          setMovements(null);
          setIndex(0);
          setMovementTime(0);
          setStartSec(0);
          setSeek(null);
          setAudible(false);
          setPlaying(true);
          setPlayEpoch((epoch) => epoch + 1);
          return;
        }
        const plan = await fetchSpan(
          chosenSymbol,
          chosenSpan,
          chosenVariant,
          chosenEnsemble,
          controller.signal,
          { humanize: shaped, color: tinted },
        );
        if (controller.signal.aborted) return;
        if (!plan.movements.length) {
          setError('Chưa đủ phiên để soạn bản này.');
          return;
        }
        setManifest(null);
        setMovements(plan.movements);
        setAsOf(plan.asOf ?? '');
        setHomeKey(plan.keyLabel ?? '');
        setIndex(0);
        setMovementTime(0);
        setStartSec(0);
        setSeek(null);
        setResting(false);
        setAudible(false);
        setPlaying(true);
        setPlayEpoch((epoch) => epoch + 1);
      } catch (err) {
        if (controller.signal.aborted || isAbort(err)) return;
        setError(failureText(err, chosenSpan));
      } finally {
        if (request.current === controller) {
          request.current = null;
          setComposing(false);
        }
      }
    })();
  }, [colorOn, date, ensemble, humanize, span, symbol, variant]);

  const jumpToMovement = useCallback(
    (nextIndex: number, seconds: number, autoplay: boolean) => {
      const current = movementsRef.current?.[nextIndex];
      const written = current?.durationSec ?? seconds;
      const file = nextIndex === indexRef.current && mediaDuration > 0 ? mediaDuration : 0;
      const duration = Math.max(written, file);
      const target = Math.min(Math.max(0, seconds), Math.max(0, duration));
      clearRest();
      setResting(false);
      setFinished(false);
      setParked(false);
      setMovementTime(target);
      setPlaying(autoplay);
      if (nextIndex !== indexRef.current) {
        setAudible(false);
        setIndex(nextIndex);
        setStartSec(target);
        setSeek(null);
        setPlayEpoch((epoch) => epoch + 1);
        return;
      }
      setStartSec(target);
      issueSeek(target);
    },
    [clearRest, issueSeek, mediaDuration],
  );

  const onPlay = useCallback(() => {
    if (composing || finished) return;
    if (resting && movements) {
      const movement = movements[index];
      if (!movement) return;
      setPlaying(true);
      beginRest(index, movement.restAfterSec, restOffset);
      return;
    }
    const loaded = span === '1D' ? manifest != null : movements != null;
    if (loaded) {
      setPlaying(true);
      return;
    }
    listen();
  }, [beginRest, composing, finished, index, listen, manifest, movements, restOffset, resting, span]);

  const onPause = useCallback(() => {
    if (composing) {
      request.current?.abort();
      request.current = null;
      setComposing(false);
      return;
    }
    setPlaying(false);
    if (resting) clearRest();
  }, [clearRest, composing]);

  const onReplay = useCallback(() => {
    const count = span === '1D' ? 1 : (movements?.length ?? 0);
    if (span !== '1D' && !movements) {
      listen();
      return;
    }
    if (span === '1D' && !manifest) {
      listen();
      return;
    }
    const action = replayAction({
      span,
      movementCount: Math.max(1, count),
      movementIndex: index,
      movementTimeSec: movementTime,
      finished,
      parkedOnMovement: parked,
    });
    clearRest();
    setResting(false);
    setFinished(false);
    setPlaying(true);
    if (action.kind === 'movement-start') {
      setParked(true);
      jumpToMovement(action.index, 0, true);
      setParked(true);
      return;
    }
    setParked(false);
    if (span === '1D') {
      setMovementTime(0);
      setStartSec(0);
      issueSeek(0);
      return;
    }
    jumpToMovement(0, 0, true);
  }, [
    clearRest,
    finished,
    index,
    issueSeek,
    jumpToMovement,
    listen,
    manifest,
    movementTime,
    movements,
    parked,
    span,
  ]);

  const onStageRatio = useCallback(
    (ratio: number) => {
      if (span === '1D') {
        if (!manifest) return;
        const clock = dailyMapClock(manifest.mapDurationSec, manifest.durationSec, mediaDuration);
        if (clock <= 0) return;
        const target = dailyStageSeek(clock, ratio);
        if (finished) setPlaying(true);
        setFinished(false);
        setParked(false);
        setMovementTime(target);
        issueSeek(target);
        return;
      }
      if (!movements || resting) return;
      const movement = movements[index];
      if (!movement) return;
      const frameStart = movements
        .slice(0, index)
        .reduce((sum, item) => sum + item.prices.length, 0);
      if (
        movements.length > 1 &&
        (finished || !audible || !movementFrameSettled(focusRef.current, frameStart, movement.prices.length))
      ) {
        return;
      }
      const map = spanMapClock(movement.mapDurationSec ?? 0, movement.durationSec);
      const target = spanStageSeek(map, movement.warmupSec, movement.cooldownSec, ratio);
      setParked(false);
      jumpToMovement(index, target, playingRef.current || finished);
    },
    [audible, finished, index, issueSeek, jumpToMovement, manifest, mediaDuration, movements, resting, span],
  );

  const onFileScrub = useCallback(
    (ratio: number) => {
      if (!manifest) return;
      const clock = mediaDuration > 0 ? mediaDuration : manifest.durationSec;
      const target = scrubberSeek(clock, ratio);
      if (finished) setPlaying(true);
      setFinished(false);
      setParked(false);
      setMovementTime(target);
      issueSeek(target);
    },
    [finished, issueSeek, manifest, mediaDuration],
  );

  const onWorkScrub = useCallback(
    (ratio: number) => {
      if (!movements) return;
      const total = workDuration(movements);
      const place = placeOnWork(movements, scrubberSeek(total, ratio));
      const resume = playingRef.current || finished;
      if (place.kind === 'rest') {
        setPlaying(resume);
        setFinished(false);
        setParked(false);
        setAudible(false);
        const movement = movements[place.afterIndex];
        setMovementTime(movement?.durationSec ?? 0);
        beginRest(place.afterIndex, movement?.restAfterSec ?? 0, place.offset);
        if (!resume) clearRest();
        return;
      }
      jumpToMovement(place.index, place.offset, resume);
    },
    [beginRest, clearRest, finished, jumpToMovement, movements],
  );

  const heardName = movements?.[index]?.name?.trim() ?? '';
  const heardReady = Boolean(movements?.[index]?.ready);
  useEffect(() => {
    if (variant !== 'guitar' || span === '1D' || !audible || heardName || heardReady) return;
    let stopped = false;
    let pending = false;
    const pull = async () => {
      if (stopped || pending) return;
      pending = true;
      try {
        const plan = await fetchSpan(symbol, span, variant, ensemble, undefined, {
          humanize,
          color: colorOn,
        });
        if (stopped) return;
        setMovements((existing) => {
          if (!existing) return existing;
          let changed = false;
          const next = existing.map((item, itemIndex) => {
            const incoming = plan.movements[itemIndex];
            if (!incoming) return item;
            const name = incoming.name?.trim() ?? '';
            if (item.name?.trim()) {
              if (item.ready === incoming.ready) return item;
              changed = true;
              return { ...item, ready: incoming.ready };
            }
            if (!name && item.ready === incoming.ready) return item;
            changed = true;
            return { ...item, ready: incoming.ready, ...(name ? { name } : {}) };
          });
          return changed ? next : existing;
        });
      } catch {
        // The score may still be writing. The next tick asks again.
      } finally {
        pending = false;
      }
    };
    void pull();
    const timer = setInterval(() => void pull(), 1500);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [audible, colorOn, ensemble, heardName, heardReady, humanize, span, symbol, variant]);

  const lengths = movements?.map((item) => item.prices.length) ?? [];
  const offsets = movementOffsets(lengths);
  const totalCandles = lengths.reduce((sum, length) => sum + length, 0);
  const multi = (movements?.length ?? 0) > 1;
  const current = movements?.[index] ?? null;
  const targetFocus =
    movements && totalCandles > 1
      ? chartFocus({
          total: totalCandles,
          offsets,
          lengths,
          index,
          elapsed: movementTime,
          resting: resting || finished,
          audible,
          multi,
        })
      : null;
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

  const prices = useMemo(() => {
    if (span !== '1D' && movements) return movements.flatMap((item) => item.prices);
    if (span !== '1D' && spanLine?.key === spanKey && spanLine.prices.length > 1) return spanLine.prices;
    return series?.prices ?? [];
  }, [movements, series, span, spanKey, spanLine]);

  const volumes = useMemo(() => {
    if (span !== '1D' && movements) return joinedVolumes(movements);
    if (span !== '1D' && spanLine?.key === spanKey && spanLine.prices.length > 1) {
      return joinedVolumes([spanLine]);
    }
    return series ? joinedVolumes([series]) : null;
  }, [movements, series, span, spanKey, spanLine]);

  const cursor = useMemo(() => {
    if (span === '1D') {
      if (!manifest || !series || series.prices.length < 1) return { index: null as number | null, label: null as string | null };
      if (!audible && movementTime <= 0 && !finished) return { index: null, label: null };
      const map = dailyMapClock(manifest.mapDurationSec, manifest.durationSec, mediaDuration);
      const at = finished
        ? series.prices.length - 1
        : ambientDailyCandleIndexAt(movementTime, series.prices.length, map);
      return { index: at, label: series.times[at] ?? null };
    }
    if (!current || !movements) return { index: null, label: null };
    const count = Math.max(1, current.prices.length);
    const at = resting || finished
      ? count - 1
      : spanCandleIndexAt(
          movementTime,
          count,
          spanMapClock(current.mapDurationSec ?? 0, current.durationSec),
          current.warmupSec,
          current.cooldownSec,
        );
    const global = (offsets[index] ?? 0) + Math.min(at, count - 1);
    return { index: audible || resting || finished || movementTime > 0 ? global : null, label: current.label };
  }, [
    audible,
    current,
    finished,
    index,
    manifest,
    mediaDuration,
    movementTime,
    movements,
    offsets,
    resting,
    series,
    span,
  ]);

  const program: PieceProgram | null = useMemo(() => {
    if (span === '1D') {
      if (!manifest || !series) return null;
      return {
        ...pieceCopy({
          variant,
          ensemble,
          symbol,
          date: manifest.date,
          keyLabel: manifest.keyLabel ?? '',
          span: '1D',
          movements: [
            {
              character: manifest.character ?? null,
              keyLabel: manifest.keyLabel ?? '',
              prices: series.prices,
              label: '',
              name: manifest.movementName,
            },
          ],
        }),
        phase: audible || movementTime > 0.05 || finished ? 'playing' : 'intro',
      };
    }
    if (!movements || !current) return null;
    return {
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
          span,
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
      phase: audible || finished ? 'playing' : 'intro',
    };
  }, [
    asOf,
    audible,
    current,
    ensemble,
    finished,
    homeKey,
    index,
    manifest,
    movementTime,
    movements,
    series,
    span,
    symbol,
    variant,
  ]);

  const audioUrl =
    span === '1D'
      ? manifest
        ? absoluteApiUrl(manifest.audioUrl)
        : null
      : current && !resting && !finished
        ? absoluteApiUrl(current.audioUrl)
        : null;

  useEffect(() => {
    setMediaDuration(0);
  }, [audioUrl]);

  const stageSeekable =
    span === '1D'
      ? manifest != null
      : movements != null &&
        !resting &&
        (movements.length <= 1 ||
          (!finished &&
            audible &&
            current != null &&
            movementFrameSettled(focus, offsets[index] ?? 0, current.prices.length)));

  const fileClock = manifest ? (mediaDuration > 0 ? mediaDuration : manifest.durationSec) : 0;
  const workClock = movements ? workDuration(movements) : 0;
  const workTime = movements
    ? workSecondsAt(movements, index, movementTime, resting, restOffset)
    : 0;

  const chapterCount = span === '1D' ? 1 : (movements?.length ?? 0);
  const chapterIndex = span === '1D' ? 0 : index;
  const chapterLabel =
    span === '1D'
      ? manifest?.movementName?.trim() || null
      : current?.name?.trim() || (movements ? `Chương ${index + 1}` : null);

  const timeline =
    span === '1D'
      ? manifest
        ? {
            label: 'Phiên',
            progress: fileClock > 0 ? Math.min(1, movementTime / fileClock) : 0,
            time: movementTime,
            duration: fileClock,
            peaks: manifest.peaks.length ? manifest.peaks : [0.2],
          }
        : null
      : movements
        ? {
            label: 'Tác phẩm',
            progress: workClock > 0 ? Math.min(1, workTime / workClock) : 0,
            time: workTime,
            duration: workClock,
          }
        : null;

  const durationClock = span === '1D' ? fileClock : workClock;
  const keyName = span === '1D' ? (manifest?.keyLabel ?? '') : (current?.keyLabel ?? homeKey);
  const stageMeta = [
    symbol,
    span === '1D' ? (date ? englishDate(date) || date : null) : span,
    keyName ? englishKey(keyName) : null,
    current?.bpm ? `${current.bpm} BPM` : null,
    durationClock > 0 ? clockText(durationClock, durationClock) : null,
  ]
    .filter(Boolean)
    .join(' · ');

  const seekBy = useCallback(
    (delta: number) => {
      if (span === '1D') {
        if (!manifest || fileClock <= 0) return;
        onFileScrub(clamp01((movementTime + delta) / fileClock));
        return;
      }
      if (!movements || workClock <= 0) return;
      onWorkScrub(clamp01((workTime + delta) / workClock));
    },
    [fileClock, manifest, movementTime, movements, onFileScrub, onWorkScrub, span, workClock, workTime],
  );

  const jumpChapter = useCallback(
    (delta: number) => {
      if (span === '1D' || !movements || movements.length < 2) return;
      const next = Math.min(movements.length - 1, Math.max(0, index + delta));
      if (next === index) return;
      jumpToMovement(next, 0, playingRef.current);
    },
    [index, jumpToMovement, movements, span],
  );

  const toggle = useCallback(() => {
    if (playing) onPause();
    else onPlay();
  }, [onPause, onPlay, playing]);

  const pickGenre = useCallback((slot: number) => {
    const next = GENRES[slot];
    if (!next) return;
    setVariant(next.id);
    setEnsemble('classic');
  }, []);

  useKeyboard({
    onToggle: toggle,
    onReplay,
    onSeekBy: seekBy,
    onChapter: jumpChapter,
    onGenre: pickGenre,
    onFocusSearch: () => setFocusSignal((signal) => signal + 1),
    onEscape: () => {
      const doc = (
        globalThis as { document?: { activeElement?: { blur?: () => void } } }
      ).document;
      doc?.activeElement?.blur?.();
    },
  });

  const identity =
    span === '1D'
      ? `${symbol}${date ? ` · ${englishDate(date) || date}` : ''}`
      : `${symbol} · ${span}`;

  return (
    <>
    <RoomFrame
      wide={wide}
      topBar={
        <TopBar
          mode="replay"
          onMode={onMode}
          onSearch={() => setFocusSignal((signal) => signal + 1)}
        />
      }
      chooser={
        <SymbolColumn
          mode="replay"
          symbols={symbols}
          filter={filter}
          onFilter={setFilter}
          selectedSymbol={symbol}
          span={span}
          selectedDate={date}
          sessions={sessions}
          onSymbol={setSymbol}
          onSpan={setSpan}
          onDate={setDate}
          quotes={quotes}
          focusSignal={focusSignal}
        />
      }
      stage={
        <Stage
          prices={prices}
          volumes={volumes}
          cursorIndex={cursor.index}
          cursorLabel={cursor.label}
          dimUnplayed={Boolean(manifest || movements) && !finished && (playing || audible || composing)}
          focusStart={focus?.start}
          focusEnd={focus?.end}
          program={program}
          identity={program ? null : identity}
          badge={program ? symbol : null}
          meta={program ? stageMeta : null}
          banner={error}
          seekable={stageSeekable}
          onSeekRatio={onStageRatio}
        />
      }
      controls={
        <Controls
          mode="replay"
          variant={variant}
          ensemble={ensemble}
          humanize={humanize}
          colorOn={colorOn}
          playing={playing}
          finished={finished}
          composing={composing}
          timeline={timeline}
          chapterLabel={chapterLabel}
          chapterIndex={chapterIndex}
          chapterCount={chapterCount}
          onVariant={(next) => {
            setVariant(next);
            setEnsemble('classic');
          }}
          onEnsemble={setEnsemble}
          onHumanize={setHumanize}
          onColor={setColorOn}
          onPlay={onPlay}
          onPause={onPause}
          onReplay={onReplay}
          onTimeline={span === '1D' ? onFileScrub : onWorkScrub}
          status={composing ? 'Đang soạn…' : resting ? 'Nghỉ giữa chương' : null}
        />
      }
    >
    </RoomFrame>
    {audioUrl ? (
      <ReplayPlayer
        key={`${audioUrl}#${playEpoch}`}
        url={audioUrl}
        startSec={startSec}
        wantPlay={playing && !resting && !finished}
        seek={seek}
        onTime={onTime}
        onEnded={onEnded}
        onAudible={() => setAudible(true)}
        onError={setError}
        onDuration={setMediaDuration}
      />
    ) : null}
    </>
  );
}
