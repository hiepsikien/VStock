import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  absoluteApiUrl,
  DEFAULT_SYMBOLS,
  ENSEMBLE_ROWS,
  fetchMarketSymbols,
  fetchDfiPieces,
  fetchDfiSignatures,
  fetchRecap,
  fetchSessionMinutes,
  fetchSessions,
  fetchSpan,
  fetchSpanPeaks,
  prefetchSpanAudio,
  type DfiPiece,
  type DfiSignature,
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
import { DfiSheet } from './DfiSheet';
import { dfiPollKey } from './dfiPoll';
import { CommandPalette } from './CommandPalette';
import { clockText, GENRES, type ListenSpan } from './labels';
import { readLink, writeLink } from './link';
import {
  baseBpmFor,
  isDefaultParams,
  paramsKey,
  paramsLayers,
  type SonifyParams,
} from './params';
import { RoomFrame } from './RoomFrame';
import { ReplayPlayer, type SeekCommand } from './ReplayPlayer';
import { TopBar } from './TopBar';
import { useTuning } from './tuning';
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
  workSegments,
  workSecondsAt,
  clamp01,
} from './seek';
import { Stage } from './Stage';
import { SymbolColumn, type SymbolChoice } from './SymbolColumn';
import type { TimelinePart } from './Scrubber';
import { workWaveform, type WavePeaks } from './peaks';
import {
  PEAKS_POLL_BUDGET,
  finishPeaksRefresh,
  peaksPollDelay,
  peaksPollKey,
  requestPeaksRefresh,
  type PeaksRefreshState,
} from './peaksPrefetch';
import {
  commitReason,
  lookaheadDepth,
  markMovementReady,
  maxRenderRatio,
  playerHasStarted,
  queueTargets,
  retryDelay,
  shouldAbortOnIndexChange,
} from './composeQueue';
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

type QueueState = {
  generation: number;
  inFlight: { index: number; url: string; controller: AbortController } | null;
  attempts: Map<string, number>;
  cooldownUntil: Map<number, { url: string; until: number }>;
  done: Set<string>;
  renderRatio: number;
};

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Long enough to cover the one-slot queue, not just the export. */
function prefetchTimeoutMs(durationSec: number): number {
  return Math.max(15 * 60_000, (2 * Math.max(0, durationSec) + 300) * 1000);
}

function joinedVolumes(parts: { prices: number[]; volumes?: number[] }[]): number[] | null {
  if (parts.some((item) => !item.volumes || item.volumes.length !== item.prices.length)) return null;
  const volumes = parts.flatMap((item) => item.volumes ?? []);
  return volumes.length ? volumes : null;
}

const PINNED_INDICES: SymbolChoice[] = [
  {
    symbol: 'VNINDEX',
    name: 'VN-Index',
    exchange: 'HOSE',
    kind: 'index',
  },
  {
    symbol: 'HNX',
    name: 'HNX-Index',
    exchange: 'HNX',
    kind: 'index',
  },
];

export function ReplayRoom({ wide, onMode }: Props) {
  const [symbols, setSymbols] = useState<SymbolChoice[]>(
    DEFAULT_SYMBOLS.map((symbol) => ({ symbol, name: symbol })),
  );
  const [visibleSymbols, setVisibleSymbols] = useState<string[]>([]);
  const [filter, setFilter] = useState('');
  // The URL is the source of truth on the first render: a shared link opens
  // the same room. Native has no location and gets the defaults.
  const [boot] = useState(() => readLink());
  const [symbol, setSymbol] = useState(boot.symbol);
  const [span, setSpan] = useState<ListenSpan>(boot.span);
  const [variant, setVariant] = useState<RecapVariant>(boot.genre);
  const [ensemble, setEnsemble] = useState<RecapEnsemble>(() =>
    boot.ensemble && ENSEMBLE_ROWS[boot.genre].some((row) => row.id === boot.ensemble)
      ? boot.ensemble
      : 'classic',
  );
  const {
    heardParams,
    draftDirty,
    savedDirty,
    playNonce,
    requestPlay,
    autoSavedNotice,
    open: tuningOpen,
    setOpen: setTuningOpen,
  } = useTuning();
  const heardKey = paramsKey(heardParams);
  const heardLayers = paramsLayers(heardParams);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [date, setDate] = useState<string | null>(boot.date);
  const [series, setSeries] = useState<SessionMinutes | null>(null);
  const [manifest, setManifest] = useState<RecapManifest | null>(null);
  const [movements, setMovements] = useState<SpanMovement[] | null>(null);
  const [spanLine, setSpanLine] = useState<{ key: string; prices: number[]; volumes?: number[] } | null>(null);
  const [spanPeaks, setSpanPeaks] = useState<Array<WavePeaks | null> | null>(null);
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
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [muted, setMuted] = useState(false);
  const [dfiOpen, setDfiOpen] = useState(false);
  const [genrePieces, setGenrePieces] = useState<DfiPiece[] | null>(null);
  const [ensemblePieces, setEnsemblePieces] = useState<DfiPiece[] | null>(null);
  const [dfiSignatures, setDfiSignatures] = useState<DfiSignature[]>([]);
  const [genreLoading, setGenreLoading] = useState(false);
  const [ensembleLoading, setEnsembleLoading] = useState(false);

  const request = useRef<AbortController | null>(null);
  const peaksRequest = useRef<AbortController | null>(null);
  // A peaks refresh is cheap but re-plans the work. Let one answer land instead
  // of aborting it every time another movement finishes; ask once more after.
  const peaksState = useRef<PeaksRefreshState>({ pending: false, again: false });
  // Bumped whenever the timeline identity changes; a response from the old
  // identity must never merge into the new one.
  const peaksGen = useRef(0);
  const peaksPoll = useRef({ key: '', count: 0 });
  // One pump owns every background render. The player still owns the heard
  // chapter; this queue only looks at what comes after it.
  const [generation, setGeneration] = useState(0);
  const queue = useRef<QueueState>({
    generation: 0,
    inFlight: null,
    attempts: new Map(),
    cooldownUntil: new Map(),
    done: new Set(),
    renderRatio: 0,
  });
  // The index that produced the current `mediaDuration`. On a chapter change
  // the old duration is still set for one render.
  const mediaIndex = useRef(-1);
  const restTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const seekSeq = useRef(0);
  const dfiPoll = useRef({ key: '', count: 0 });
  const focusRef = useRef<ChartFocus | null>(null);
  const zoomFrame = useRef(0);
  const movementsRef = useRef<SpanMovement[] | null>(null);
  const indexRef = useRef(0);
  const playingRef = useRef(false);
  const committedRef = useRef(false);
  const finishedRef = useRef(false);
  // False until the player has asked for the heard chapter. Prevents the pump
  // from racing its own request for the next one.
  const playerStartedRef = useRef(false);
  movementsRef.current = movements;
  indexRef.current = index;
  playingRef.current = playing;
  finishedRef.current = finished;

  const clearRest = useCallback(() => {
    if (restTimer.current) {
      clearInterval(restTimer.current);
      restTimer.current = null;
    }
  }, []);

  /**
   * Forget the waveform and render state of the work being replaced. A new
   * identity and a re-plan of the same identity both land here so the paths
   * cannot drift. Bumping the generation aborts every background render and
   * restarts the pump.
   */
  const resetPeaksState = useCallback(() => {
    peaksRequest.current?.abort();
    peaksRequest.current = null;
    peaksState.current = { pending: false, again: false };
    peaksGen.current += 1;
    peaksPoll.current = { key: '', count: 0 };
    mediaIndex.current = -1;
    queue.current.generation += 1;
    queue.current.inFlight?.controller.abort();
    queue.current.inFlight = null;
    queue.current.attempts.clear();
    queue.current.cooldownUntil.clear();
    queue.current.done.clear();
    queue.current.renderRatio = 0;
    committedRef.current = false;
    playerStartedRef.current = false;
    setGeneration(queue.current.generation);
  }, []);

  const clearPlayback = useCallback(() => {
    request.current?.abort();
    request.current = null;
    resetPeaksState();
    clearRest();
    setManifest(null);
    setMovements(null);
    setSpanPeaks(null);
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
  }, [clearRest, resetPeaksState]);

  useEffect(() => {
    return () => {
      request.current?.abort();
      peaksRequest.current?.abort();
      queue.current.inFlight?.controller.abort();
      clearRest();
    };
  }, [clearRest]);

  const signature = `${symbol}|${span}|${date ?? ''}|${variant}|${ensemble}|${heardKey}`;
  const signatureRef = useRef(signature);
  useEffect(() => {
    if (signatureRef.current === signature) return;
    signatureRef.current = signature;
    clearPlayback();
  }, [clearPlayback, signature]);

  // Keep the address bar shareable. `replaceState` avoids a history entry for
  // every tuning change.
  useEffect(() => {
    writeLink({
      symbol,
      span,
      date,
      genre: variant,
      ensemble,
      params: heardParams,
    });
  }, [date, ensemble, heardParams, span, symbol, variant]);

  const dfiBucket = span === '1D' ? 'day' : 'span';

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const rows = await fetchDfiSignatures(dfiBucket, undefined, controller.signal);
        setDfiSignatures(rows);
      } catch (err) {
        if (!isAbort(err)) setDfiSignatures([]);
      }
    })();
    return () => controller.abort();
  }, [dfiBucket]);

  // The sheet's two comparison tables are composed on the server. Reset on
  // close so reopening on another symbol cannot flash the previous session's
  // rows, and keep the genre table independent of ensemble changes.
  useEffect(() => {
    if (dfiOpen) return;
    setGenrePieces(null);
    setEnsemblePieces(null);
    setGenreLoading(false);
    setEnsembleLoading(false);
  }, [dfiOpen]);

  useEffect(() => {
    if (!dfiOpen) return;
    if (dfiBucket === 'day' && !date) return;
    const controller = new AbortController();
    setGenrePieces(null);
    setGenreLoading(true);
    void (async () => {
      try {
        const result = await fetchDfiPieces(
          {
            symbol,
            bucket: dfiBucket,
            date: dfiBucket === 'day' ? date : null,
            range: dfiBucket === 'span' ? span : null,
            movement: dfiBucket === 'span' ? index : 0,
            variant: null,
            ensemble: null,
            params: heardParams,
          },
          controller.signal,
        );
        if (!controller.signal.aborted) setGenrePieces(result.pieces);
      } catch {
        if (!controller.signal.aborted) setGenrePieces(null);
      } finally {
        if (!controller.signal.aborted) setGenreLoading(false);
      }
    })();
    return () => controller.abort();
  }, [date, dfiBucket, dfiOpen, heardKey, index, span, symbol]);

  useEffect(() => {
    if (!dfiOpen) return;
    if (dfiBucket === 'day' && !date) return;
    const controller = new AbortController();
    setEnsemblePieces(null);
    setEnsembleLoading(true);
    void (async () => {
      try {
        const result = await fetchDfiPieces(
          {
            symbol,
            bucket: dfiBucket,
            date: dfiBucket === 'day' ? date : null,
            range: dfiBucket === 'span' ? span : null,
            movement: dfiBucket === 'span' ? index : 0,
            variant,
            ensemble: null,
            params: heardParams,
          },
          controller.signal,
        );
        if (!controller.signal.aborted) setEnsemblePieces(result.pieces);
      } catch {
        if (!controller.signal.aborted) setEnsemblePieces(null);
      } finally {
        if (!controller.signal.aborted) setEnsembleLoading(false);
      }
    })();
    return () => controller.abort();
  }, [date, dfiBucket, dfiOpen, heardKey, index, span, symbol, variant]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const rows = await fetchMarketSymbols();
        if (cancelled || !rows.length) return;
        const stocks: SymbolChoice[] = rows
          .filter((item) => !PINNED_INDICES.some((pinned) => pinned.symbol === item.symbol))
          .map((item) => ({
            symbol: item.symbol,
            name: item.name,
            exchange: item.exchange,
            ranges: item.ranges,
            kind: 'stock' as const,
          }));
        setSymbols([...PINNED_INDICES, ...stocks]);
        setSymbol((current) => {
          if (rows.some((item) => item.symbol === current) || PINNED_INDICES.some((item) => item.symbol === current)) {
            return current;
          }
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
    const fallback = symbols.slice(0, 16).map((item) => item.symbol);
    const visible = visibleSymbols.filter((item) =>
      symbols.some((symbolChoice) => symbolChoice.symbol === item),
    );
    return [...new Set([symbol, ...visible, ...fallback])].slice(0, 17);
  }, [symbol, symbols, visibleSymbols]);
  const quotes = useQuotes(quoteSymbols, span);

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

  const spanKey = `${symbol}|${span}|${variant}|${ensemble}|${heardKey}`;
  useEffect(() => {
    if (span === '1D') return;
    const controller = new AbortController();
    let cancelled = false;
    const key = spanKey;
    setSpanPeaks(null);
    void (async () => {
      try {
        const plan = await fetchSpan(symbol, span, variant, ensemble, controller.signal, heardParams);
        if (cancelled) return;
        const prices = plan.movements.flatMap((item) => item.prices);
        const volumes = joinedVolumes(plan.movements);
        setSpanLine(prices.length > 1 ? { key, prices, ...(volumes ? { volumes } : {}) } : null);
        setSpanPeaks(
          plan.movements.map((item) => ({
            peaks: item.peaks && item.peaks.length ? item.peaks : null,
            level: item.peakLevel ?? 0,
          })),
        );
      } catch (err) {
        if (cancelled || isAbort(err)) return;
        setSpanLine(null);
        setSpanPeaks(null);
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [ensemble, heardParams, span, spanKey, symbol, variant]);

  /**
   * A movement's waveform only exists after its audio file is written. Merge
   * whatever the plan can see now without touching durations, prices or
   * playback. Requests are coalesced: aborting a slow refresh and starting a
   * new one on every chapter change is what left the waveform a chapter behind.
   */
  const refreshSpanPeaks = useCallback(() => {
    if (span === '1D') return;
    if (!requestPeaksRefresh(peaksState.current)) return;
    const gen = peaksGen.current;
    const controller = new AbortController();
    peaksRequest.current = controller;
    void (async () => {
      try {
        const peaks = await fetchSpanPeaks(
          symbol,
          span,
          variant,
          ensemble,
          controller.signal,
          heardParams,
        );
        if (controller.signal.aborted || gen !== peaksGen.current) return;
        if (
          peaks.symbol !== symbol ||
          peaks.range !== span ||
          peaks.variant !== variant ||
          (peaks.ensemble != null && peaks.ensemble !== ensemble) ||
          (peaks.humanize != null && peaks.humanize !== heardLayers.humanize) ||
          (peaks.color != null && peaks.color !== heardLayers.color)
        ) {
          return;
        }
        let measured = 0;
        for (const item of peaks.movements) {
          if (typeof item.renderRatio === 'number' && item.renderRatio > measured) {
            measured = item.renderRatio;
          }
        }
        if (measured > 0) queue.current.renderRatio = measured;
        setSpanPeaks((prev) => {
          const next = [...(prev ?? [])];
          for (const item of peaks.movements) {
            const previous = next[item.index];
            next[item.index] = {
              peaks: item.peaks && item.peaks.length ? item.peaks : (previous?.peaks ?? null),
              level: item.peakLevel ?? previous?.level ?? 0,
            };
          }
          return next;
        });
        setMovements((existing) => {
          if (!existing) return existing;
          let changed = false;
          const next = existing.map((movement, itemIndex) => {
            const incoming = peaks.movements.find((item) => item.index === itemIndex);
            // A re-plan changes the fingerprint; a row for another URL must
            // never make this movement look rendered.
            if (!incoming || !incoming.audioUrl || incoming.audioUrl !== movement.audioUrl) {
              return movement;
            }
            const patch: Partial<SpanMovement> = {};
            if (incoming.ready === true && !movement.ready) {
              patch.ready = true;
              queue.current.done.add(movement.audioUrl);
            }
            if (incoming.durationSec != null && incoming.durationSec > 0 && incoming.durationSec !== movement.durationSec) {
              patch.durationSec = incoming.durationSec;
            }
            if (incoming.renderSec != null && incoming.renderSec > 0 && incoming.renderSec !== movement.renderSec) {
              patch.renderSec = incoming.renderSec;
            }
            if (incoming.renderRatio != null && incoming.renderRatio > 0 && incoming.renderRatio !== movement.renderRatio) {
              patch.renderRatio = incoming.renderRatio;
            }
            if (!Object.keys(patch).length) return movement;
            changed = true;
            return { ...movement, ...patch };
          });
          return changed ? next : existing;
        });
      } catch {
        // Peaks are additive. Keep whatever the timeline already has.
      } finally {
        // A newer identity owns the shared state now; leave its request alone.
        if (peaksRequest.current === controller) {
          peaksRequest.current = null;
          if (finishPeaksRefresh(peaksState.current) && !controller.signal.aborted) {
            refreshSpanPeaks();
          }
        }
      }
    })();
  }, [ensemble, heardLayers.color, heardLayers.humanize, heardParams, span, symbol, variant]);

  const hasMovements = movements != null;
  const currentMovement = movements?.[index] ?? null;

  /**
   * One pump for every background render. It never asks for the heard chapter:
   * the player owns that request. It keeps running while paused and through the
   * rest between chapters, and stops only when the identity or generation
   * changes.
   */
  useEffect(() => {
    if (span === '1D' || !hasMovements) return;
    const gen = generation;
    let stopped = false;

    void (async () => {
      while (!stopped && gen === queue.current.generation) {
        if (finishedRef.current) {
          await sleep(500);
          continue;
        }
        // Let the player ask for the heard chapter first. This is what stops a
        // prefetch from reaching the single export slot before the chapter the
        // listener is waiting for.
        if (!playerStartedRef.current) {
          await sleep(200);
          continue;
        }
        if (queue.current.inFlight) {
          await sleep(200);
          continue;
        }
        const list = movementsRef.current;
        if (!list) {
          await sleep(500);
          continue;
        }
        const depth = lookaheadDepth({
          ratio: queue.current.renderRatio,
          paused: !playingRef.current,
          committed: committedRef.current,
        });
        const targets = queueTargets({
          currentIndex: indexRef.current,
          count: list.length,
          urls: list.map((item) => item.audioUrl),
          ready: list.map((item) => item.ready),
          depth,
          done: queue.current.done,
          cooldownUntil: queue.current.cooldownUntil,
          now: Date.now(),
        });
        const next = targets[0];
        if (next == null) {
          await sleep(500);
          continue;
        }
        const target = list[next];
        if (!target?.audioUrl) {
          await sleep(500);
          continue;
        }
        const url = target.audioUrl;
        const controller = new AbortController();
        queue.current.inFlight = { index: next, url, controller };
        const started = Date.now();
        let outcome: 'ready' | 'retry' | 'fatal';
        try {
          outcome = await prefetchSpanAudio(
            url,
            controller.signal,
            prefetchTimeoutMs(target.durationSec),
          );
        } catch {
          outcome = 'retry';
        } finally {
          if (queue.current.inFlight?.controller === controller) {
            queue.current.inFlight = null;
          }
        }
        if (stopped || gen !== queue.current.generation) return;
        // The index effect aborted this render because the listener moved on.
        // That is not a failure: do not back off, and serve the new target now.
        if (controller.signal.aborted) continue;

        if (outcome === 'ready') {
          queue.current.done.add(url);
          queue.current.attempts.delete(url);
          queue.current.cooldownUntil.delete(next);
          // Wall time is not render time; readiness is enough here. The peaks
          // refresh fills renderSec/renderRatio from the server.
          setMovements((existing) =>
            existing ? markMovementReady(existing, next, url, 0) : existing,
          );
          refreshSpanPeaks();
          continue;
        }
        if (outcome === 'fatal') {
          queue.current.attempts.delete(url);
          queue.current.cooldownUntil.set(next, { url, until: Date.now() + 60_000 });
          continue;
        }
        const attempt = (queue.current.attempts.get(url) ?? 0) + 1;
        queue.current.attempts.set(url, attempt);
        const delay = retryDelay(attempt);
        if (!delay) {
          // Three failed attempts: rest for a minute, then try again. Never
          // block a chapter for the rest of the work.
          queue.current.attempts.delete(url);
          queue.current.cooldownUntil.set(next, { url, until: Date.now() + 60_000 });
          continue;
        }
        await sleep(delay);
      }
    })();

    return () => {
      stopped = true;
      queue.current.inFlight?.controller.abort();
      queue.current.inFlight = null;
    };
  }, [
    generation,
    hasMovements,
    refreshSpanPeaks,
    span,
    spanKey,
  ]);

  /** A render for a chapter the listener has passed is wasted work. */
  useEffect(() => {
    const flight = queue.current.inFlight;
    const currentReady = movementsRef.current?.[index]?.ready === true;
    const depth = lookaheadDepth({
      ratio: queue.current.renderRatio,
      paused: !playingRef.current,
      committed: committedRef.current,
    });
    // Keep only what helps the chapter being entered. If that chapter has no
    // file, the player needs the single slot, so a prefetch for a later
    // chapter must not sit in front of its request. A jump back also drops a
    // render that is now outside the window.
    if (
      flight &&
      shouldAbortOnIndexChange({
        flightIndex: flight.index,
        currentIndex: index,
        currentReady,
        depth,
      })
    ) {
      flight.controller.abort();
      queue.current.inFlight = null;
    }
    for (const target of [...queue.current.cooldownUntil.keys()]) {
      if (target >= index) queue.current.cooldownUntil.delete(target);
    }
    // The new chapter may not have a file yet: wait for the player to ask for
    // it before preparing the one after.
    playerStartedRef.current = false;
  }, [index, spanKey]);

  /** The player has actually started the heard chapter. */
  useEffect(() => {
    if (!currentMovement) return;
    if (
      playerHasStarted({
        ready: currentMovement.ready,
        audible,
        resting,
        mediaIndex: mediaIndex.current,
        currentIndex: index,
        mediaDurationSec: mediaDuration,
      })
    ) {
      playerStartedRef.current = true;
    }
  }, [audible, currentMovement, index, mediaDuration, resting]);

  /** The listener has heard enough to be treated as staying for the work. */
  useEffect(() => {
    if (span === '1D' || committedRef.current) return;
    const reason = commitReason({
      audible,
      heardSec: movementTime,
      movementSec: currentMovement?.durationSec ?? 0,
      seeked: false,
    });
    if (reason) committedRef.current = true;
  }, [audible, currentMovement, movementTime, span]);

  /**
   * Fallback when a background render or its peaks request failed: retry with
   * a small backoff while the heard movement still has no envelope. Only runs
   * while playing, so a paused room does not keep re-planning the span.
   */
  const heardHasPeaks = Boolean(spanPeaks?.[index]?.peaks?.length);
  useEffect(() => {
    if (span === '1D') return;
    const key = peaksPollKey({ symbol, span, variant, ensemble, index, playing });
    if (peaksPoll.current.key !== key) peaksPoll.current = { key, count: 0 };
    if (!playing || mediaDuration <= 0 || mediaIndex.current !== index || heardHasPeaks) return;
    if (peaksPoll.current.count >= PEAKS_POLL_BUDGET) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const pull = () => {
      if (stopped || peaksPoll.current.count >= PEAKS_POLL_BUDGET) return;
      peaksPoll.current.count += 1;
      refreshSpanPeaks();
      timer = setTimeout(pull, peaksPollDelay(peaksPoll.current.count));
    };
    timer = setTimeout(pull, peaksPollDelay(0));
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [
    ensemble,
    heardHasPeaks,
    index,
    mediaDuration,
    playing,
    refreshSpanPeaks,
    span,
    symbol,
    variant,
  ]);

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

  const listen = useCallback((paramsOverride?: SonifyParams) => {
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
    const shaped = paramsOverride ?? heardParams;
    const chosenDate = date;
    void (async () => {
      try {
        if (chosenSpan === '1D') {
          if (!chosenDate) return;
          const recap = await fetchRecap(
            chosenSymbol,
            chosenDate,
            chosenVariant,
            chosenEnsemble,
            controller.signal,
            shaped,
          );
          if (controller.signal.aborted) return;
          const detail = await fetchSessionMinutes(chosenSymbol, chosenDate, controller.signal);
          if (controller.signal.aborted) return;
          if (recap.barCount !== detail.prices.length) {
            const again = await fetchRecap(
              chosenSymbol,
              chosenDate,
              chosenVariant,
              chosenEnsemble,
              controller.signal,
              shaped,
            );
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
          shaped,
        );
        if (controller.signal.aborted) return;
        if (!plan.movements.length) {
          setError('Chưa đủ phiên để soạn bản này.');
          return;
        }
        setManifest(null);
        setMovements(plan.movements);
        // A new listen may re-plan the work, so pre-rendered URLs and peaks
        // from the previous run no longer describe the same movement.
        resetPeaksState();
        for (const movement of plan.movements) {
          if (movement.ready) queue.current.done.add(movement.audioUrl);
        }
        queue.current.renderRatio = maxRenderRatio(plan.movements);
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
  }, [date, ensemble, heardParams, resetPeaksState, span, symbol, variant]);

  // Play commits the latest saved profile first; this effect starts the listen
  // after the old identity has been cleared. Draft edits never bump playNonce.
  const listenRef = useRef(listen);
  listenRef.current = listen;
  const playSeen = useRef(0);
  useEffect(() => {
    if (playNonce === playSeen.current) return;
    playSeen.current = playNonce;
    if (!playNonce) return;
    listenRef.current(heardParams);
  }, [heardParams, playNonce]);

  const jumpToMovement = useCallback(
    (nextIndex: number, seconds: number, autoplay: boolean) => {
      // An explicit seek is a stronger signal than the dwell threshold.
      committedRef.current = true;
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
    if (composing) return;
    if (draftDirty || savedDirty) {
      requestPlay();
      return;
    }
    if (finished) return;
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
  }, [
    beginRest,
    composing,
    draftDirty,
    finished,
    index,
    listen,
    manifest,
    movements,
    requestPlay,
    restOffset,
    resting,
    savedDirty,
    span,
  ]);

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
    if (draftDirty || savedDirty) {
      requestPlay();
      return;
    }
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
    draftDirty,
    finished,
    index,
    issueSeek,
    jumpToMovement,
    listen,
    manifest,
    movementTime,
    movements,
    parked,
    requestPlay,
    savedDirty,
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
  const heardDfi = Boolean(movements?.[index]?.dfi);
  useEffect(() => {
    // Reset the budget before the early return. A pause writes `idle`; the
    // next play writes `play` and starts a fresh set of retries. Computing the
    // key only after the guard would keep the exhausted `play` budget across a
    // pause/resume.
    const pollKey = dfiPollKey({
      symbol,
      span,
      variant,
      ensemble,
      index,
      ready: heardReady,
      name: heardName,
      audible,
    });
    if (dfiPoll.current.key !== pollKey) dfiPoll.current = { key: pollKey, count: 0 };
    if (span === '1D' || !audible || (heardName && heardReady && heardDfi)) return;
    // A movement can be heard before its score exists, and an old cache can
    // hold audio without DFI. Neither number appears on its own: re-read the
    // plan until the current movement has both. Starting playback resets the
    // retry budget, so a page opened before the cache was written still fills
    // in after the user presses play.
    //
    // A null DFI is also terminal: the line did not move enough to score.
    // Bound the retries so a flat session does not poll the whole span
    // forever. A long movement's DFI sidecar can take a while to write, so
    // the budget is wider than the old twelve seconds.
    let stopped = false;
    let pending = false;
    const controller = new AbortController();
    const pull = async () => {
      if (stopped || pending || dfiPoll.current.count >= 24) return;
      dfiPoll.current.count += 1;
      pending = true;
      try {
        if (heardReady && heardName) {
          // A ready movement with a name only needs its own number. Ask the
          // compose-only endpoint instead of re-downloading every movement's
          // prices and volumes. Without a name (old guitar cache), fall
          // through to the plan so the dance can still arrive.
          const result = await fetchDfiPieces(
            {
              symbol,
              bucket: 'span',
              range: span,
              movement: index,
              variant,
              ensemble,
              params: heardParams,
            },
            controller.signal,
          );
          if (stopped) return;
          const piece =
            result.pieces.find((item) => item.variant === variant && item.ensemble === ensemble) ??
            (result.pieces.length === 1 ? result.pieces[0] : null);
          if (piece?.dfi) {
            setMovements((existing) => {
              if (!existing) return existing;
              const current = existing[index];
              if (!current || current.dfi) return existing;
              const next = existing.slice();
              next[index] = { ...current, dfi: piece.dfi };
              return next;
            });
          }
          return;
        }
        const plan = await fetchSpan(
          symbol,
          span,
          variant,
          ensemble,
          controller.signal,
          heardParams,
        );
        if (stopped) return;
        setMovements((existing) => {
          if (!existing) return existing;
          let changed = false;
          const next = existing.map((item, itemIndex) => {
            const incoming = plan.movements[itemIndex];
            if (!incoming) return item;
            const name = incoming.name?.trim() ?? '';
            const patch: Partial<SpanMovement> = {};
            if (!item.name?.trim() && name) patch.name = name;
            // A new plan can point at another fingerprint. Only an explicit
            // ready for the same URL may skip the pump.
            if (incoming.ready && !item.ready && incoming.audioUrl === item.audioUrl) {
              patch.ready = true;
              queue.current.done.add(item.audioUrl);
            }
            if (!item.dfi && incoming.dfi) patch.dfi = incoming.dfi;
            if (!Object.keys(patch).length) return item;
            changed = true;
            return { ...item, ...patch };
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
      controller.abort();
      clearInterval(timer);
    };
  }, [
    audible,
    ensemble,
    heardName,
    heardDfi,
    heardParams,
    heardReady,
    index,
    span,
    symbol,
    variant,
  ]);

  const lengths = movements?.map((item) => item.prices.length) ?? [];
  const offsets = movementOffsets(lengths);
  const totalCandles = lengths.reduce((sum, length) => sum + length, 0);
  const multi = (movements?.length ?? 0) > 1;
  const current = movements?.[index] ?? null;
  const activeDfi = span === '1D' ? (manifest?.dfi ?? null) : (current?.dfi ?? null);
  const activeDfiSignature =
    isDefaultParams(heardParams)
      ? (dfiSignatures.find(
          (row) => row.variant === variant && row.ensemble === ensemble,
        ) ??
        dfiSignatures.find((row) => row.variant === variant && row.ensemble === 'classic') ??
        null)
      : null;
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

  const waveform = useMemo(() => {
    if (span === '1D' || !movements) return null;
    return workWaveform(movements, spanPeaks);
  }, [movements, span, spanPeaks]);

  const selectedChangePercent = useMemo(() => {
    // The selected 1D session has its own close-vs-reference change. Using the
    // day quote here would label an old session with today's move.
    if (span === '1D') {
      return series?.changePercent ?? quotes?.[symbol]?.changePercent ?? null;
    }
    if (prices.length < 2) return null;
    const first = prices[0];
    const last = prices[prices.length - 1];
    return first > 0 ? ((last - first) / first) * 100 : null;
  }, [prices, quotes, series, span, symbol]);

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
    mediaIndex.current = -1;
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
  const nextChapterReady = span === '1D' ? null : (movements?.[index + 1]?.ready ?? null);
  const baseChapterLabel =
    current?.name?.trim() || (movements ? `Chương ${index + 1}` : null);
  const chapterLabel =
    span === '1D'
      ? manifest?.movementName?.trim() || null
      : baseChapterLabel && current && !current.ready
        ? `${baseChapterLabel} · đang soạn`
        : baseChapterLabel;

  // The merged timeline draws one groove per movement and a hairline groove
  // for each rest. Names come from the same movements the audio uses.
  const timelineParts = useMemo<TimelinePart[] | null>(() => {
    if (span === '1D' || !movements) return null;
    return workSegments(movements).map((segment) =>
      segment.kind === 'audio'
        ? {
            kind: 'audio' as const,
            start: segment.start,
            end: segment.end,
            label: movements[segment.index]?.name?.trim() || `Chương ${segment.index + 1}`,
          }
        : { kind: 'rest' as const, start: segment.start, end: segment.end, label: 'Nghỉ' },
    );
  }, [movements, span]);

  const restTotal = resting ? (movements?.[index]?.restAfterSec ?? 0) : 0;
  const restRemaining = resting ? Math.max(0, restTotal - restOffset) : 0;

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
            parts: timelineParts,
            peaks: waveform,
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

  useKeyboard(
    {
      onToggle: () => {
        if (tuningOpen) return;
        toggle();
      },
      onReplay: () => {
        if (tuningOpen) return;
        onReplay();
      },
      onSeekBy: (delta) => {
        if (tuningOpen) return;
        seekBy(delta);
      },
      onChapter: (delta) => {
        if (tuningOpen) return;
        jumpChapter(delta);
      },
      onGenre: (slot) => {
        if (tuningOpen) return;
        pickGenre(slot);
      },
      onFocusSearch: () => {
        if (tuningOpen) return;
        setFocusSignal((signal) => signal + 1);
      },
      onCommandPalette: () => {
        if (tuningOpen) return;
        setPaletteOpen((open) => !open);
      },
      onMute: () => {
        if (tuningOpen) return;
        setMuted((value) => !value);
      },
      onEscape: () => {
        if (tuningOpen) {
          setTuningOpen(false);
          return;
        }
        const doc = (
          globalThis as { document?: { activeElement?: { blur?: () => void } } }
        ).document;
        doc?.activeElement?.blur?.();
      },
    },
    // A palette owns the keyboard while it is open. The tuning panel keeps
    // Escape through this same listener and locks the transport above.
    !paletteOpen,
  );

  const identity =
    span === '1D'
      ? `${symbol}${date ? ` · ${englishDate(date) || date}` : ''}`
      : `${symbol} · ${span}`;

  return (
    <>
    <RoomFrame
      wide={wide}
      tuningBaseBpm={baseBpmFor(variant, ensemble)}
      tuningVariant={variant}
      topBar={
        <TopBar
          mode="replay"
          onMode={onMode}
          onSearch={() => setPaletteOpen(true)}
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
          selectedSparkline={prices.length > 1 ? prices : null}
          selectedChangePercent={selectedChangePercent}
          onVisibleSymbols={setVisibleSymbols}
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
          composing={composing}
          resting={resting}
          restRemaining={restRemaining}
          restTotal={restTotal}
          nextReady={nextChapterReady}
          playing={audible}
          chartKey={`${symbol}|${span}|${variant}|${date ?? ''}`}
          dfi={activeDfi}
          onDfi={() => setDfiOpen(true)}
        />
      }
      controls={
        <Controls
          mode="replay"
          variant={variant}
          ensemble={ensemble}
          playing={playing}
          finished={finished}
          composing={composing}
          muted={muted}
          timeline={timeline}
          chapterLabel={chapterLabel}
          chapterIndex={chapterIndex}
          chapterCount={chapterCount}
          onVariant={(next) => {
            setVariant(next);
            setEnsemble('classic');
          }}
          onEnsemble={setEnsemble}
          onPlay={onPlay}
          onPause={onPause}
          onReplay={onReplay}
          onMute={() => setMuted((value) => !value)}
          onTimeline={span === '1D' ? onFileScrub : onWorkScrub}
          notice={autoSavedNotice}
          tuningBaseBpm={baseBpmFor(variant, ensemble)}
          dfi={activeDfi}
          dfiSignature={activeDfiSignature}
          onDfi={() => setDfiOpen(true)}
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
        muted={muted}
        onTime={onTime}
        onEnded={onEnded}
        onAudible={() => setAudible(true)}
        onError={setError}
        onDuration={(seconds) => {
          mediaIndex.current = index;
          setMediaDuration(seconds);
          // The player only reports a duration after the file is written, so
          // the heard chapter is ready even if the plan has not refreshed yet.
          const heard = movementsRef.current?.[index];
          if (heard?.audioUrl) {
            queue.current.done.add(heard.audioUrl);
            setMovements((list) =>
              list ? markMovementReady(list, index, heard.audioUrl, 0) : list,
            );
          }
        }}
        onReady={refreshSpanPeaks}
      />
    ) : null}
    <CommandPalette
      visible={paletteOpen}
      onClose={() => setPaletteOpen(false)}
      symbols={symbols}
      symbol={symbol}
      span={span}
      variant={variant}
      date={date}
      sessions={sessions}
      onSymbol={setSymbol}
      onSpan={setSpan}
      onVariant={(next) => {
        if (next === variant) return;
        setVariant(next);
        setEnsemble('classic');
      }}
      onDate={setDate}
    />
    <DfiSheet
      visible={dfiOpen}
      onClose={() => setDfiOpen(false)}
      dfi={activeDfi}
      variant={variant}
      ensemble={ensemble}
      signatures={dfiSignatures}
      genrePieces={genrePieces}
      ensemblePieces={ensemblePieces}
      genreLoading={genreLoading}
      ensembleLoading={ensembleLoading}
      onVariant={(next) => {
        if (next === variant) return;
        setVariant(next);
        setEnsemble('classic');
      }}
      onEnsemble={setEnsemble}
    />
    </>
  );
}
