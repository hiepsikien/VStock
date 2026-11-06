import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type PointerEvent as RNPointerEvent,
  type ScrollViewInstance,
} from 'react-native';
import { getApiBaseUrl } from '../api/client';
import { palette, TOUCH_TARGET } from '../musicalize/palette';
import { type } from '../musicalize/type';
import {
  requestMusicXmlPassage,
  uploadMusicXml,
  type StudioError,
} from './api';
import {
  MUSIC_XML_ROLE_LABELS,
  TICKS_PER_QUARTER,
  barLayouts,
  beatCountLabel,
  buildRoleLanes,
  clampZoom,
  defaultPassageRange,
  keySignatureLabel,
  meterChangeLabel,
  musicXmlGrid,
  normalizeMusicXmlSummary,
  passageBeatLabel,
  passageEndBeatLabel,
  passageRangeLabel,
  playheadTickAt,
  rangeTicks,
  selectionFromTicks,
  snapTick,
  tempoLabel,
  validatePassageRange,
  zoomLabel,
  type MusicXmlImport,
  type MusicXmlPassage,
  type MusicXmlRole,
  type MusicXmlRoleCell,
  type PassageRange,
} from './musicxml';
import { resolveAudioUrl } from './protocol';
import { byteSizeLabel, describeRequestFailure } from './spec';
import { SentenceDraftPanel } from './SentenceDraftPanel';

/**
 * Rhythm-first MusicXML import panel.
 *
 * The panel owns every piece of MusicXML state: the uploaded score, the bar
 * range, voice filter, passage audio and the local sentence/pattern draft. It
 * never writes into the SentenceSpec editor, so StudioRoom's dirty flag is
 * untouched.
 *
 * Pitch is intentionally hidden. Lead/Mid/Bass rows show rhythm cells only;
 * every gap is a faint explicit rest cell (empty cell = rest).
 */

const BASE_TICK_WIDTH = 1.2;
const ROW_HEIGHT = 30;
const RULER_HEIGHT = 38;
const LANE_LABEL_WIDTH = 62;
const MIN_NOTE_WIDTH = 2;
const PLAYHEAD_MARGIN = 48;

const ROLE_COLORS: Record<MusicXmlRole, string> = {
  lead: palette.data,
  mid: palette.sound,
  bass: palette.playhead,
};

const ROLE_FILLS: Record<MusicXmlRole, string> = {
  lead: 'rgba(62, 224, 224, 0.26)',
  mid: 'rgba(224, 64, 160, 0.24)',
  bass: 'rgba(245, 185, 66, 0.24)',
};

const EMPTY_SUMMARY = normalizeMusicXmlSummary(null);

type Props = {
  compact?: boolean;
};

type UploadState =
  | { kind: 'idle' }
  | { kind: 'busy'; filename: string }
  | { kind: 'error'; message: string; errors: StudioError[] };

type PassageError = {
  message: string;
  errors: StudioError[];
};

type AudioState = {
  url: string;
  durationSec: number;
  playing: boolean;
  bpm: number;
};

function parseBarText(value: string): number {
  const trimmed = value.trim();
  return /^\d+$/.test(trimmed) ? Number(trimmed) : Number.NaN;
}

/** Start beat is 1-based; the API uses a 0-based offset. */
function parseStartBeatText(value: string): number {
  const trimmed = value.trim();
  return /^\d+(?:\.\d+)?$/.test(trimmed) ? Number(trimmed) - 1 : Number.NaN;
}

/**
 * End beat is 1-based **inclusive** in the UI, while the API's `beatEnd` is
 * exclusive. `2` means "through beat 2"; the payload uses offset 2.
 */
function parseEndBeatText(value: string): number {
  const trimmed = value.trim();
  return /^\d+(?:\.\d+)?$/.test(trimmed) ? Number(trimmed) : Number.NaN;
}

function startBeatFieldText(offset: number): string {
  if (!Number.isFinite(offset)) return '';
  const value = Math.round((offset + 1) * 1_000_000) / 1_000_000;
  return String(value);
}

function endBeatFieldText(offset: number): string {
  if (!Number.isFinite(offset) || offset <= 0) return '';
  return String(Math.round(offset * 1_000_000) / 1_000_000);
}

function warningUnion(imported: MusicXmlImport | null): string[] {
  if (!imported) return [];
  const seen = new Set<string>();
  const merged: string[] = [];
  for (const warning of [...imported.warnings, ...imported.summary.warnings]) {
    const key = warning.trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    merged.push(key);
  }
  return merged;
}

function voiceOptions(imported: MusicXmlImport | null): number[] {
  if (!imported) return [];
  const voices = new Set(imported.summary.voices);
  for (const note of imported.notes) {
    if (!note.rest && note.voice >= 1 && note.voice <= 4) voices.add(note.voice);
  }
  return [...voices].sort((left, right) => left - right);
}

export function MusicXmlPanel({ compact = false }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [upload, setUpload] = useState<UploadState>({ kind: 'idle' });
  const [imported, setImported] = useState<MusicXmlImport | null>(null);
  const [startText, setStartText] = useState('1');
  const [startBeatText, setStartBeatText] = useState('1');
  const [endText, setEndText] = useState('1');
  const [endBeatText, setEndBeatText] = useState('1');
  const [tapStart, setTapStart] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);
  const [dragging, setDragging] = useState(false);
  const [playheadTick, setPlayheadTick] = useState<number | null>(null);
  const [voices, setVoices] = useState<number[]>([]);
  const [passage, setPassage] = useState<MusicXmlPassage | null>(null);
  const [passageBusy, setPassageBusy] = useState<'play' | 'use' | null>(null);
  const [passageError, setPassageError] = useState<PassageError | null>(null);
  const [showWarnings, setShowWarnings] = useState(false);
  const [audio, setAudio] = useState<AudioState | null>(null);

  const uploadController = useRef<AbortController | null>(null);
  const passageController = useRef<AbortController | null>(null);
  const player = useRef<HTMLAudioElement | null>(null);
  const playheadFrame = useRef<number | null>(null);
  const playheadSpan = useRef<{ startTick: number; endTick: number; bpm: number } | null>(
    null,
  );
  const scrollRef = useRef<ScrollViewInstance | null>(null);
  const scrollOffset = useRef(0);
  const viewportWidth = useRef(0);
  const pendingScroll = useRef<number | null>(null);
  const dragSurface = useRef<React.ComponentRef<typeof View> | null>(null);
  const dragAnchor = useRef<{ tick: number } | null>(null);

  const cancelPlayhead = useCallback(() => {
    if (playheadFrame.current != null) {
      cancelAnimationFrame(playheadFrame.current);
      playheadFrame.current = null;
    }
    playheadSpan.current = null;
    setPlayheadTick(null);
  }, []);

  const stopPlayer = useCallback(() => {
    const current = player.current;
    player.current = null;
    if (current) current.pause();
    cancelPlayhead();
    setAudio(null);
  }, [cancelPlayhead]);

  const resetPassage = useCallback(() => {
    passageController.current?.abort();
    passageController.current = null;
    stopPlayer();
    setPassage(null);
    setPassageError(null);
    setPassageBusy(null);
  }, [stopPlayer]);

  useEffect(
    () => () => {
      uploadController.current?.abort();
      passageController.current?.abort();
      const current = player.current;
      player.current = null;
      if (current) current.pause();
      if (playheadFrame.current != null) {
        cancelAnimationFrame(playheadFrame.current);
        playheadFrame.current = null;
      }
    },
    [],
  );

  const bars = useMemo(
    () => (imported ? barLayouts(imported.summary) : []),
    [imported],
  );
  const grid = useMemo(() => musicXmlGrid(bars), [bars]);
  const barStartTicks = useMemo(
    () => new Map(grid.bars.map((bar) => [bar.bar, bar.startTick])),
    [grid],
  );
  const lanes = useMemo(
    () => (imported ? buildRoleLanes(imported.notes, bars) : []),
    [imported, bars],
  );
  const range: PassageRange = {
    barStart: parseBarText(startText),
    beatStart: parseStartBeatText(startBeatText),
    barEnd: parseBarText(endText),
    beatEnd: parseEndBeatText(endBeatText),
  };
  const rangeValidation = validatePassageRange(bars, range);
  const rangeLabel = passageRangeLabel(bars, range);
  const voicesInScore = useMemo(() => voiceOptions(imported), [imported]);
  const warnings = useMemo(() => warningUnion(imported), [imported]);
  const passageMeter =
    rangeValidation.meters.length === 1 ? rangeValidation.meters[0] : '';
  // The passage echoes the score warnings; the summary toggle already lists
  // those, so only show passage-specific messages here.
  const passageWarnings = useMemo(
    () =>
      passage
        ? passage.warnings.filter((warning) => !warnings.includes(warning))
        : [],
    [passage, warnings],
  );
  const tickWidth = BASE_TICK_WIDTH * zoom;
  const matrixWidth = Math.max(1, grid.totalTicks * tickWidth);
  const laneBodyHeight = Math.max(1, lanes.length) * ROW_HEIGHT;
  const summary = imported?.summary ?? EMPTY_SUMMARY;
  const tickWidthRef = useRef(tickWidth);
  tickWidthRef.current = tickWidth;

  const selectionTicks = useMemo(() => {
    if (bars.length === 0) return null;
    if (
      !Number.isFinite(range.barStart) ||
      !Number.isFinite(range.barEnd) ||
      !Number.isFinite(range.beatStart) ||
      !Number.isFinite(range.beatEnd)
    ) {
      return null;
    }
    if (
      range.barStart < 1 ||
      range.barEnd > bars.length ||
      range.barStart > range.barEnd
    ) {
      return null;
    }
    const ticks = rangeTicks(grid, range);
    return ticks.endTick > ticks.startTick ? ticks : null;
  }, [
    bars.length,
    grid,
    range.barStart,
    range.beatEnd,
    range.beatStart,
    range.barEnd,
  ]);

  const selectedBars = useMemo(() => {
    const selected = new Set<number>();
    if (bars.length === 0) return selected;
    if (
      !Number.isInteger(range.barStart) ||
      !Number.isInteger(range.barEnd) ||
      range.barStart < 1 ||
      range.barEnd > bars.length ||
      range.barStart > range.barEnd
    ) {
      return selected;
    }
    for (let bar = range.barStart; bar <= range.barEnd; bar += 1) {
      selected.add(bar);
    }
    return selected;
  }, [bars.length, range.barEnd, range.barStart]);

  const applyRange = useCallback((next: PassageRange) => {
    setStartText(String(next.barStart));
    setStartBeatText(startBeatFieldText(next.beatStart));
    setEndText(String(next.barEnd));
    setEndBeatText(endBeatFieldText(next.beatEnd));
  }, []);

  const changeZoom = useCallback(
    (nextZoom: number) => {
      const target = clampZoom(nextZoom);
      if (target === zoom) return;
      const ratio = target / zoom;
      const width = viewportWidth.current;
      pendingScroll.current = Math.max(
        0,
        (scrollOffset.current + width / 2) * ratio - width / 2,
      );
      setZoom(target);
    },
    [zoom],
  );

  useEffect(() => {
    const pending = pendingScroll.current;
    if (pending == null) return;
    pendingScroll.current = null;
    const frame = requestAnimationFrame(() => {
      scrollOffset.current = pending;
      scrollRef.current?.scrollTo({ x: pending, animated: false });
    });
    return () => cancelAnimationFrame(frame);
  }, [zoom]);

  const ensurePlayheadVisible = useCallback((tick: number) => {
    const scroll = scrollRef.current;
    const width = viewportWidth.current;
    if (!scroll || width <= 0) return;
    const x = tick * tickWidthRef.current;
    const offset = scrollOffset.current;
    const margin = Math.min(PLAYHEAD_MARGIN, width / 4);
    if (x >= offset + margin && x <= offset + width - margin) return;
    const next = Math.max(0, x - width / 2);
    scrollOffset.current = next;
    scroll.scrollTo({ x: next, animated: false });
  }, []);

  const startPlayhead = useCallback(
    (
      element: HTMLAudioElement,
      span: { startTick: number; endTick: number; bpm: number },
    ) => {
      if (playheadFrame.current != null) {
        cancelAnimationFrame(playheadFrame.current);
      }
      playheadSpan.current = span;
      setPlayheadTick(span.startTick);
      const step = () => {
        const active = playheadSpan.current;
        if (!active || player.current !== element) return;
        const raw = playheadTickAt(element.currentTime, active.bpm, active.startTick);
        const next = Math.min(active.endTick, Math.max(active.startTick, raw));
        setPlayheadTick(next);
        ensurePlayheadVisible(next);
        if (!element.paused && !element.ended) {
          playheadFrame.current = requestAnimationFrame(step);
        }
      };
      playheadFrame.current = requestAnimationFrame(step);
    },
    [ensurePlayheadVisible],
  );

  const onUpload = useCallback(async () => {
    if (!file) return;
    uploadController.current?.abort();
    const controller = new AbortController();
    uploadController.current = controller;
    setUpload({ kind: 'busy', filename: file.name || 'score.musicxml' });
    resetPassage();
    setTapStart(null);
    setVoices([]);
    try {
      const data = await uploadMusicXml(file, {
        filename: file.name || 'score.musicxml',
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (!data.importId) {
        setUpload({
          kind: 'error',
          message: data.errors[0]?.message ?? 'The MusicXML upload failed.',
          errors: data.errors,
        });
        return;
      }
      const nextBars = barLayouts(data.summary);
      setImported(data);
      applyRange(defaultPassageRange(nextBars));
      setShowWarnings(false);
      setUpload({ kind: 'idle' });
    } catch (error) {
      if (controller.signal.aborted) return;
      setUpload({
        kind: 'error',
        message: describeRequestFailure(error),
        errors: [],
      });
    } finally {
      if (uploadController.current === controller) uploadController.current = null;
    }
  }, [applyRange, file, resetPassage]);

  const loadPassage = useCallback(
    async (purpose: 'play' | 'use'): Promise<MusicXmlPassage | null> => {
      if (!imported || !rangeValidation.ok || passageBusy !== null) return null;
      passageController.current?.abort();
      const controller = new AbortController();
      passageController.current = controller;
      setPassageBusy(purpose);
      setPassageError(null);
      try {
        const data = await requestMusicXmlPassage(
          imported.importId,
          {
            barStart: range.barStart,
            beatStart: range.beatStart,
            barEnd: range.barEnd,
            beatEnd: range.beatEnd,
            ...(voices.length ? { voices } : {}),
          },
          controller.signal,
        );
        if (controller.signal.aborted) return null;
        setPassage(data);
        if (!data.ok) {
          setPassageError({
            message: data.errors[0]?.message ?? 'The passage preview failed.',
            errors: data.errors,
          });
        }
        return data;
      } catch (error) {
        if (controller.signal.aborted) return null;
        setPassageError({
          message: describeRequestFailure(error),
          errors: [],
        });
        return null;
      } finally {
        if (passageController.current === controller) {
          passageController.current = null;
          setPassageBusy(null);
        }
      }
    },
    [
      imported,
      passageBusy,
      range.barEnd,
      range.barStart,
      range.beatEnd,
      range.beatStart,
      rangeValidation.ok,
      voices,
    ],
  );

  const playPassage = useCallback(async () => {
    if (Platform.OS !== 'web') return;
    stopPlayer();
    const span = selectionTicks;
    if (!span) return;
    const data = await loadPassage('play');
    if (!data?.audioUrl) return;
    if (typeof Audio === 'undefined') {
      setPassageError({
        message: 'This browser does not expose the Audio element.',
        errors: [],
      });
      return;
    }
    const url = resolveAudioUrl(getApiBaseUrl(), data.audioUrl);
    if (!url) {
      setPassageError({
        message: 'The passage response did not include a usable audio URL.',
        errors: [],
      });
      return;
    }
    const bpm = Number.isFinite(data.bpm) && data.bpm > 0 ? data.bpm : 96;
    const next = new Audio(url);
    player.current = next;
    next.onended = () => {
      if (player.current !== next) return;
      player.current = null;
      cancelPlayhead();
      setAudio((current) =>
        current?.url === url ? { ...current, playing: false } : current,
      );
    };
    next.onerror = () => {
      if (player.current !== next) return;
      player.current = null;
      cancelPlayhead();
      setPassageError({
        message: 'The browser could not play the passage WAV.',
        errors: [],
      });
      setAudio(null);
    };
    try {
      await next.play();
      setAudio({
        url,
        durationSec: data.durationSec,
        playing: true,
        bpm,
      });
      startPlayhead(next, { ...span, bpm });
    } catch (error) {
      next.pause();
      if (player.current === next) player.current = null;
      cancelPlayhead();
      setPassageError({
        message: describeRequestFailure(error),
        errors: [],
      });
      setAudio(null);
    }
  }, [cancelPlayhead, loadPassage, selectionTicks, startPlayhead, stopPlayer]);

  const tapBar = useCallback(
    (bar: number) => {
      const barLayout = bars[bar - 1];
      if (!barLayout) return;
      const next: PassageRange =
        tapStart == null
          ? {
              barStart: bar,
              beatStart: 0,
              barEnd: bar,
              beatEnd: barLayout.quarterBeats,
            }
          : {
              barStart: Math.min(tapStart, bar),
              beatStart: 0,
              barEnd: Math.max(tapStart, bar),
              beatEnd: (bars[Math.max(tapStart, bar) - 1] ?? barLayout)
                .quarterBeats,
            };
      applyRange(next);
      setTapStart(tapStart == null ? bar : null);
      resetPassage();
    },
    [applyRange, bars, resetPassage, tapStart],
  );

  const toggleVoice = useCallback(
    (voice: number) => {
      setVoices((current) =>
        current.includes(voice)
          ? current.filter((item) => item !== voice)
          : [...current, voice].sort((left, right) => left - right),
      );
      resetPassage();
    },
    [resetPassage],
  );

  const onStartChange = (value: string) => {
    setStartText(value);
    setTapStart(null);
    resetPassage();
  };
  const onStartBeatChange = (value: string) => {
    setStartBeatText(value);
    setTapStart(null);
    resetPassage();
  };
  const onEndChange = (value: string) => {
    setEndText(value);
    setTapStart(null);
    resetPassage();
  };
  const onEndBeatChange = (value: string) => {
    setEndBeatText(value);
    setTapStart(null);
    resetPassage();
  };

  const tickFromClientX = useCallback(
    (clientX: number): number | null => {
      const node = dragSurface.current as unknown as HTMLElement | null;
      const rect =
        node && typeof node.getBoundingClientRect === 'function'
          ? node.getBoundingClientRect()
          : null;
      if (!rect || rect.width <= 0) return null;
      return snapTick((clientX - rect.left) / tickWidth);
    },
    [tickWidth],
  );

  const applyDragSelection = useCallback(
    (anchor: number, current: number) => {
      let start = Math.min(anchor, current);
      let end = Math.max(anchor, current);
      if (end - start < TICKS_PER_QUARTER) {
        if (current < anchor) start = end - TICKS_PER_QUARTER;
        else end = start + TICKS_PER_QUARTER;
      }
      applyRange(selectionFromTicks(grid, start, end));
    },
    [applyRange, grid],
  );

  const onPointerDown = useCallback(
    (event: RNPointerEvent) => {
      if (Platform.OS !== 'web') return;
      const tick = tickFromClientX(event.nativeEvent.clientX);
      if (tick == null) return;
      event.preventDefault?.();
      dragAnchor.current = { tick };
      resetPassage();
      applyRange(selectionFromTicks(grid, tick, tick + TICKS_PER_QUARTER));
      setDragging(true);
    },
    [applyRange, grid, resetPassage, tickFromClientX],
  );

  useEffect(() => {
    if (Platform.OS !== 'web' || !dragging) return;
    const onMove = (event: PointerEvent) => {
      const anchor = dragAnchor.current;
      if (!anchor) return;
      const tick = tickFromClientX(event.clientX);
      if (tick == null) return;
      event.preventDefault();
      applyDragSelection(anchor.tick, tick);
    };
    const onUp = () => {
      dragAnchor.current = null;
      setDragging(false);
    };
    window.addEventListener('pointermove', onMove, { passive: false });
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
    };
  }, [applyDragSelection, dragging, tickFromClientX]);

  const canRequest =
    imported != null && rangeValidation.ok && passageBusy == null;
  const canPlay = canRequest && Platform.OS === 'web';
  const noteCellCount = lanes.reduce(
    (sum, lane) => sum + lane.cells.filter((cell) => !cell.rest).length,
    0,
  );

  return (
    <View style={[styles.card, compact && styles.cardCompact]}>
      <View style={styles.header}>
        <Text style={[type.section, styles.cardLabel]}>XML · MusicXML import</Text>
        <Text style={styles.headerMeta}>
          {imported ? 'RHYTHM MATRIX' : 'NO SCORE'}
        </Text>
      </View>
      <Text style={styles.cardTitle}>MusicXML → role lanes</Text>
      <Text style={styles.hint}>
        Rhythm-first matrix. Lead is voice 1; Bass is the lowest non-lead note at
        each onset; Mid is everything left. Pitch stays hidden. Gaps are explicit
        faint rest cells, never collapsed. Drag the lane body to select
        quarter-note beats, zoom the ruler without changing lane height, and Play
        follows the preview audio with a vertical playhead. Passage audio and the
        sentence draft are previews only and never touch the sentence editor.
      </Text>

      {Platform.OS === 'web' ? (
        <View style={styles.importRow}>
          {React.createElement('input', {
            type: 'file',
            accept: '.musicxml,.xml',
            disabled: upload.kind === 'busy',
            'aria-label': 'Choose a MusicXML score',
            onChange: (event: React.ChangeEvent<HTMLInputElement>) => {
              const next = event.target.files?.[0] ?? null;
              // Reset so choosing the same file after an error fires again.
              event.target.value = '';
              setFile(next);
            },
            style: { color: palette.textMuted, fontSize: 12, maxWidth: '100%' },
          })}
          <View style={styles.importActions}>
            <ActionButton
              label="Upload XML"
              primary
              onPress={() => void onUpload()}
              disabled={!file || upload.kind === 'busy'}
              busy={upload.kind === 'busy'}
              busyLabel="Uploading…"
            />
            <Text numberOfLines={1} style={styles.fileName}>
              {file
                ? `${file.name || 'score.musicxml'} · ${byteSizeLabel(file.size)}`
                : 'No .musicxml/.xml file selected'}
            </Text>
          </View>
        </View>
      ) : (
        <View style={styles.noticeBox}>
          <Text style={styles.noticeTitle}>MusicXML import is web-only in this pass</Text>
          <Text style={styles.noticeText}>
            Open the Studio web build to pick a score file. The sentence editor
            below is unaffected on native.
          </Text>
        </View>
      )}

      {upload.kind === 'error' ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorTitle}>{upload.message}</Text>
          <ErrorRows errors={upload.errors} />
        </View>
      ) : null}

      {imported ? (
        <>
          <View style={styles.summaryBox}>
            <View style={styles.summaryHeader}>
              <Text numberOfLines={2} style={styles.summaryTitle}>
                {summary.title || imported.filename || 'MusicXML import'}
              </Text>
              <Badge
                ok={summary.meterSupported}
                label={summary.meterSupported ? 'METER OK' : 'METER CHECK'}
              />
            </View>
            <Text style={styles.summaryFile} numberOfLines={1}>
              {imported.filename || 'score.musicxml'}
            </Text>
            <View style={styles.metaGrid}>
              <MetaRow label="Meter" value={meterChangeLabel(bars) || summary.meter || '—'} />
              <MetaRow label="Key" value={keySignatureLabel(summary)} />
              <MetaRow label="Tempo" value={tempoLabel(summary.tempo)} />
              <MetaRow label="Measures" value={String(summary.measureCount)} />
              <MetaRow
                label="Notes"
                value={`${summary.noteCount} · ${noteCellCount} note cells`}
              />
              <MetaRow
                label="Voices"
                value={summary.voices.length ? summary.voices.join(', ') : '—'}
              />
            </View>
            <View style={styles.summaryFooter}>
              <Text style={styles.summaryHint}>
                source {summary.sourceHash ? summary.sourceHash.slice(0, 22) : '—'}
              </Text>
              <Pressable
                onPress={() => setShowWarnings((open) => !open)}
                disabled={warnings.length === 0}
                accessibilityRole="button"
                accessibilityLabel={`${warnings.length} MusicXML warnings`}
                accessibilityState={{ expanded: showWarnings, disabled: warnings.length === 0 }}
                style={({ pressed }) => [
                  styles.warningToggle,
                  pressed && warnings.length > 0 ? styles.pressed : null,
                ]}
              >
                <Text style={styles.warningToggleText}>
                  {warnings.length === 0
                    ? 'No warnings'
                    : `${warnings.length} warning${warnings.length === 1 ? '' : 's'}`}
                </Text>
              </Pressable>
            </View>
            {showWarnings && warnings.length ? (
              <View style={styles.warningList}>
                {warnings.map((warning, index) => (
                  <Text key={`musicxml-warning:${index}`} style={styles.warningText}>
                    {warning}
                  </Text>
                ))}
              </View>
            ) : null}
            {!summary.meterSupported ? (
              <Text style={styles.warnText}>
                The backend did not mark the summary meter as supported. Per-bar
                meters may still be accepted; a rejected Play/Use request will
                report the exact meter error.
              </Text>
            ) : null}
          </View>

          <View style={styles.matrixHeader}>
            <Text style={[type.section, styles.blockLabel]}>Passage matrix</Text>
            <View style={styles.zoomRow}>
              <Pressable
                onPress={() => changeZoom(zoom - 0.25)}
                accessibilityRole="button"
                accessibilityLabel="Zoom out"
                style={({ pressed }) => [
                  styles.zoomButton,
                  pressed ? styles.pressed : null,
                ]}
              >
                <Text style={styles.zoomButtonText}>−</Text>
              </Pressable>
              <Text style={styles.zoomValue}>{zoomLabel(zoom)}</Text>
              <Pressable
                onPress={() => changeZoom(zoom + 0.25)}
                accessibilityRole="button"
                accessibilityLabel="Zoom in"
                style={({ pressed }) => [
                  styles.zoomButton,
                  pressed ? styles.pressed : null,
                ]}
              >
                <Text style={styles.zoomButtonText}>+</Text>
              </Pressable>
              <Pressable
                onPress={() => changeZoom(1)}
                accessibilityRole="button"
                accessibilityLabel="Reset zoom to 100%"
                style={({ pressed }) => [
                  styles.zoomReset,
                  pressed ? styles.pressed : null,
                ]}
              >
                <Text style={styles.zoomResetText}>100%</Text>
              </Pressable>
            </View>
          </View>

          <View style={styles.legendRow}>
            {lanes.map((lane) => (
              <View key={`legend:${lane.role}`} style={styles.legendItem}>
                <View
                  style={[styles.legendSwatch, { backgroundColor: ROLE_COLORS[lane.role] }]}
                />
                <Text style={styles.legendText}>{lane.label}</Text>
              </View>
            ))}
            <View style={styles.legendItem}>
              <View style={styles.legendRestSwatch} />
              <Text style={styles.legendText}>rest</Text>
            </View>
            <Text style={styles.legendHint}>
              pitch hidden · drag the lanes for beats · tap a bar header for whole bars
            </Text>
          </View>

          <View style={styles.matrix}>
            <View style={styles.laneLabels}>
              <View style={[styles.rulerLabelCell, { height: RULER_HEIGHT }]}>
                <Text style={styles.rulerLabelText}>bar</Text>
              </View>
              {lanes.map((lane) => {
                const notes = lane.cells.filter((cell) => !cell.rest).length;
                return (
                  <View
                    key={`lane:${lane.role}`}
                    style={[styles.laneLabelRow, { height: ROW_HEIGHT }]}
                  >
                    <View
                      style={[
                        styles.laneSwatch,
                        { backgroundColor: ROLE_COLORS[lane.role] },
                      ]}
                    />
                    <Text style={[styles.laneLabelText, { color: ROLE_COLORS[lane.role] }]}>
                      {lane.label}
                    </Text>
                    <Text style={styles.laneCount}>{notes}</Text>
                  </View>
                );
              })}
            </View>

            <ScrollView
              horizontal
              showsHorizontalScrollIndicator
              style={styles.matrixScroll}
              ref={scrollRef}
              scrollEventThrottle={16}
              onScroll={(event) => {
                scrollOffset.current = event.nativeEvent.contentOffset.x;
              }}
              onLayout={(event) => {
                viewportWidth.current = event.nativeEvent.layout.width;
              }}
            >
              <View style={{ width: matrixWidth, position: 'relative' }}>
                <View style={[styles.ruler, { height: RULER_HEIGHT }]}>
                  {grid.bars.map((bar) => {
                    const width = Math.max(2, bar.ticks * tickWidth);
                    const selected = selectedBars.has(bar.bar);
                    const showBarNumber =
                      width >= 16 &&
                      !(zoom < 1 && bar.bar % 2 === 0 && !bar.meterStart);
                    const showMeter = bar.meterStart && width >= 24;
                    return (
                      <Pressable
                        key={`bar:${bar.bar}`}
                        onPress={() => tapBar(bar.bar)}
                        accessibilityRole="button"
                        accessibilityLabel={`Bar ${bar.bar}${
                          bar.meterStart ? `, meter ${bar.meter}` : ''
                        }. Set passage start or end.`}
                        accessibilityState={{ selected }}
                        style={({ pressed }) => [
                          styles.rulerCell,
                          {
                            left: bar.startTick * tickWidth,
                            width,
                            height: RULER_HEIGHT,
                          },
                          selected ? styles.rulerCellSelected : null,
                          tapStart === bar.bar ? styles.rulerCellAnchor : null,
                          pressed ? styles.pressed : null,
                        ]}
                      >
                        {showBarNumber ? (
                          <Text style={styles.barNumber}>{bar.bar}</Text>
                        ) : null}
                        {showMeter ? (
                          <Text style={styles.meterText} numberOfLines={1}>
                            {bar.meter}
                          </Text>
                        ) : null}
                        {bar.beatTicks.slice(1).map((tick) => (
                          <View
                            key={`beat:${bar.bar}:${tick}`}
                            pointerEvents="none"
                            style={[
                              styles.beatTick,
                              { left: tick * tickWidth },
                            ]}
                          />
                        ))}
                      </Pressable>
                    );
                  })}
                </View>

                <View
                  style={{
                    position: 'relative',
                    width: matrixWidth,
                    height: laneBodyHeight,
                  }}
                >
                  {grid.bars.map((bar) => (
                    <View
                      key={`grid:${bar.bar}`}
                      pointerEvents="none"
                      style={[
                        styles.barGrid,
                        {
                          left: bar.startTick * tickWidth,
                          width: Math.max(2, bar.ticks * tickWidth),
                        },
                        selectedBars.has(bar.bar) ? styles.barGridSelected : null,
                      ]}
                    >
                      {bar.beatTicks.slice(1).map((tick) => (
                        <View
                          key={`grid-beat:${bar.bar}:${tick}`}
                          style={[
                            styles.gridBeatTick,
                            { left: tick * tickWidth },
                          ]}
                        />
                      ))}
                    </View>
                  ))}

                  {lanes.map((lane, index) => (
                    <View
                      key={`row:${lane.role}`}
                      style={{
                        position: 'absolute',
                        left: 0,
                        top: index * ROW_HEIGHT,
                        width: matrixWidth,
                        height: ROW_HEIGHT,
                      }}
                    >
                      <View style={styles.rowLine} />
                      {lane.cells.map((cell) => (
                        <RoleCellView
                          key={`${lane.role}:${cell.bar}:${cell.startTick}`}
                          cell={cell}
                          role={lane.role}
                          offsetTicks={barStartTicks.get(cell.bar) ?? 0}
                          tickWidth={tickWidth}
                          zoom={zoom}
                        />
                      ))}
                    </View>
                  ))}

                  {selectionTicks ? (
                    <View
                      pointerEvents="none"
                      style={[
                        styles.selectionOverlay,
                        {
                          left: selectionTicks.startTick * tickWidth,
                          width: Math.max(
                            1,
                            (selectionTicks.endTick - selectionTicks.startTick) *
                              tickWidth,
                          ),
                          height: laneBodyHeight,
                        },
                      ]}
                    >
                      <View style={[styles.selectionEdge, { left: 0 }]} />
                      <View style={[styles.selectionEdge, { right: 0 }]} />
                      <Text style={[styles.selectionTag, { left: 3 }]}>
                        {passageBeatLabel(range.beatStart)}
                      </Text>
                      <Text style={[styles.selectionTag, styles.selectionTagEnd]}>
                        {passageEndBeatLabel(range.beatEnd)}
                      </Text>
                    </View>
                  ) : null}

                  {Platform.OS === 'web' ? (
                    <View
                      ref={dragSurface}
                      onPointerDown={onPointerDown}
                      accessibilityLabel="Drag to select a passage; snaps to quarter notes"
                      style={[
                        styles.dragSurface,
                        { width: matrixWidth, height: laneBodyHeight },
                      ]}
                    />
                  ) : null}
                </View>

                {playheadTick != null ? (
                  <View
                    pointerEvents="none"
                    accessibilityLabel="Playback position"
                    style={[
                      styles.playhead,
                      {
                        left: playheadTick * tickWidth - 1,
                        height: RULER_HEIGHT + laneBodyHeight,
                      },
                    ]}
                  />
                ) : null}
              </View>
            </ScrollView>
          </View>

          <View style={styles.selectionBox}>
            <Text style={[type.section, styles.blockLabel]}>Passage</Text>
            <View style={styles.rangeRow}>
              <View style={styles.rangeField}>
                <Text style={styles.inputLabel}>Start bar</Text>
                <TextInput
                  value={startText}
                  onChangeText={onStartChange}
                  keyboardType="number-pad"
                  inputMode="numeric"
                  maxLength={6}
                  style={styles.rangeInput}
                  placeholder="1"
                  placeholderTextColor={palette.textFaint}
                  accessibilityLabel="Passage start bar"
                />
              </View>
              <View style={styles.rangeField}>
                <Text style={styles.inputLabel}>Start beat</Text>
                <TextInput
                  value={startBeatText}
                  onChangeText={onStartBeatChange}
                  keyboardType="decimal-pad"
                  inputMode="decimal"
                  maxLength={6}
                  style={styles.rangeInput}
                  placeholder="1"
                  placeholderTextColor={palette.textFaint}
                  accessibilityLabel="Passage start beat"
                />
              </View>
              <View style={styles.rangeField}>
                <Text style={styles.inputLabel}>End bar</Text>
                <TextInput
                  value={endText}
                  onChangeText={onEndChange}
                  keyboardType="number-pad"
                  inputMode="numeric"
                  maxLength={6}
                  style={styles.rangeInput}
                  placeholder="1"
                  placeholderTextColor={palette.textFaint}
                  accessibilityLabel="Passage end bar"
                />
              </View>
              <View style={styles.rangeField}>
                <Text style={styles.inputLabel}>End beat</Text>
                <TextInput
                  value={endBeatText}
                  onChangeText={onEndBeatChange}
                  keyboardType="decimal-pad"
                  inputMode="decimal"
                  maxLength={6}
                  style={styles.rangeInput}
                  placeholder="1"
                  placeholderTextColor={palette.textFaint}
                  accessibilityLabel="Passage end beat"
                />
              </View>
              <Text style={styles.rangeSummary} numberOfLines={2}>
                {rangeLabel}
              </Text>
            </View>
            <Text style={styles.legendHint}>
              Beats are 1-based quarter notes; the end beat is the last beat
              included.
            </Text>

            <View style={styles.voiceRow}>
              <Text style={styles.inputLabel}>Voices</Text>
              <Chip
                label="All"
                active={voices.length === 0}
                onPress={() => {
                  setVoices([]);
                  resetPassage();
                }}
                accessibilityLabel="Use every voice"
              />
              {voicesInScore.map((voice) => (
                <Chip
                  key={`voice:${voice}`}
                  label={String(voice)}
                  active={voices.includes(voice)}
                  onPress={() => toggleVoice(voice)}
                  accessibilityLabel={`Toggle voice ${voice}`}
                />
              ))}
              {voicesInScore.length === 0 ? (
                <Text style={styles.legendHint}>no voices reported</Text>
              ) : null}
            </View>

            {rangeValidation.errors.length ? (
              <View style={styles.rangeErrors}>
                {rangeValidation.mixedMeter ? (
                  <Text style={styles.warnTitle}>Mixed meter range</Text>
                ) : null}
                {rangeValidation.errors.map((message, index) => (
                  <Text key={`range:${index}`} style={styles.warnText}>
                    {message}
                  </Text>
                ))}
              </View>
            ) : (
              <Text style={styles.rangeOk}>
                Valid range · {rangeValidation.meters.join(' → ') || 'no meter'}
              </Text>
            )}

            <View style={styles.actionRow}>
              <ActionButton
                label="Play passage"
                primary
                onPress={() => void playPassage()}
                disabled={!canPlay}
                busy={passageBusy === 'play'}
                busyLabel="Rendering…"
              />
              {audio?.playing ? (
                <ActionButton label="Stop" onPress={stopPlayer} />
              ) : null}
            </View>
            {Platform.OS !== 'web' ? (
              <Text style={styles.legendHint}>
                Passage Play is web-only. The sentence flow below still drafts
                from the selected passage.
              </Text>
            ) : null}
            {audio ? (
              <Text style={styles.audioLine}>
                {audio.playing ? 'Playing' : 'Ready'} ·{' '}
                {Math.round(audio.bpm)} BPM ·{' '}
                {audio.durationSec > 0 ? `${audio.durationSec.toFixed(2)} s` : 'duration unknown'}
              </Text>
            ) : null}
            {passageError ? (
              <View style={styles.errorBox}>
                <Text style={styles.errorTitle}>{passageError.message}</Text>
                <ErrorRows errors={passageError.errors} />
              </View>
            ) : null}
            {passageWarnings.length ? (
              <View style={styles.warningList}>
                {passageWarnings.map((warning, index) => (
                  <Text key={`passage-warning:${index}`} style={styles.warningText}>
                    {warning}
                  </Text>
                ))}
              </View>
            ) : null}
          </View>

          <SentenceDraftPanel
            importId={imported.importId}
            range={range}
            rangeLabel={rangeLabel}
            meter={passageMeter}
            selectionValid={rangeValidation.ok}
            voices={voices}
          />
        </>
      ) : (
        <Text style={styles.emptyHint}>
          Pick a .musicxml or .xml file and Upload XML to build the Lead / Mid /
          Bass rhythm matrix.
        </Text>
      )}
    </View>
  );
}

/* ------------------------------------------------------------------------- *
 * Presentational helpers
 * ------------------------------------------------------------------------- */

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metaRow}>
      <Text style={styles.metaLabel}>{label}</Text>
      <Text selectable numberOfLines={2} style={styles.metaValue}>
        {value}
      </Text>
    </View>
  );
}

function RoleCellView({
  cell,
  role,
  offsetTicks,
  tickWidth,
  zoom,
}: {
  cell: MusicXmlRoleCell;
  role: MusicXmlRole;
  /** Absolute start tick of the cell's bar in the score-wide matrix. */
  offsetTicks: number;
  tickWidth: number;
  zoom: number;
}) {
  const width = Math.max(MIN_NOTE_WIDTH, cell.ticks * tickWidth);
  const height = ROW_HEIGHT - 8;
  const durationWidth = zoom >= 2 ? 12 : 17;
  const countWidth = zoom >= 2 ? 26 : 33;
  const showDuration = !cell.rest && width >= durationWidth;
  const showCount = !cell.rest && cell.count > 1 && width >= countWidth;
  const beat = Math.round((cell.startTick / TICKS_PER_QUARTER) * 1_000_000) / 1_000_000;
  const label = cell.rest
    ? `Bar ${cell.bar} · ${MUSIC_XML_ROLE_LABELS[role]} · rest · ${beatCountLabel(
        cell.durationBeats,
      )} beats`
    : `Bar ${cell.bar} · beat ${beat} · ${MUSIC_XML_ROLE_LABELS[role]} · ${beatCountLabel(
        cell.durationBeats,
      )} beats${cell.count > 1 ? ` · chord ${cell.count}` : ''}${
        cell.tie ? ` · tie ${cell.tie}` : ''
      }`;
  return (
    <View
      accessible
      accessibilityRole="text"
      accessibilityLabel={label}
      pointerEvents="none"
      style={[
        styles.cell,
        {
          left: (offsetTicks + cell.startTick) * tickWidth,
          width,
          height,
          top: 4,
        },
        cell.rest
          ? styles.restCell
          : {
              backgroundColor: ROLE_FILLS[role],
              borderColor: ROLE_COLORS[role],
            },
      ]}
    >
      {cell.rest ? (
        width >= 10 ? (
          <View style={styles.restDash} />
        ) : null
      ) : showDuration || showCount ? (
        <Text numberOfLines={1} style={styles.cellText}>
          {showDuration ? beatCountLabel(cell.durationBeats) : ''}
          {showCount ? ` ×${cell.count}` : ''}
        </Text>
      ) : null}
    </View>
  );
}

function Chip({
  label,
  active,
  onPress,
  accessibilityLabel,
  disabled = false,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
  accessibilityLabel: string;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ selected: active, disabled }}
      style={({ pressed }) => [
        styles.chip,
        active ? styles.chipActive : null,
        pressed && !disabled ? styles.pressed : null,
        disabled ? styles.disabled : null,
      ]}
    >
      <Text style={[styles.chipText, active ? styles.chipTextActive : null]}>
        {label}
      </Text>
    </Pressable>
  );
}

function ActionButton({
  label,
  onPress,
  primary = false,
  disabled = false,
  busy = false,
  busyLabel,
}: {
  label: string;
  onPress: () => void;
  primary?: boolean;
  disabled?: boolean;
  busy?: boolean;
  busyLabel?: string;
}) {
  const text = busy && busyLabel ? busyLabel : label;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled, busy }}
      style={({ pressed }) => [
        styles.button,
        primary ? styles.buttonPrimary : styles.buttonSecondary,
        pressed && !disabled ? styles.pressed : null,
        disabled ? styles.disabled : null,
      ]}
    >
      <View style={styles.buttonContent}>
        {busy ? (
          <ActivityIndicator
            color={primary ? palette.background : palette.data}
            size="small"
          />
        ) : null}
        <Text style={[styles.buttonText, primary ? styles.buttonTextPrimary : null]}>
          {text}
        </Text>
      </View>
    </Pressable>
  );
}

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <View style={[styles.badge, ok ? styles.badgePass : styles.badgeFail]}>
      <Text style={[styles.badgeText, ok ? styles.badgeTextPass : styles.badgeTextFail]}>
        {label}
      </Text>
    </View>
  );
}

function ErrorRows({ errors }: { errors: StudioError[] }) {
  if (errors.length === 0) return null;
  return (
    <View style={styles.errorRows}>
      {errors.map((error, index) => (
        <View key={`${error.path}:${index}`} style={styles.errorRow}>
          <Text selectable style={styles.errorPath}>
            {error.path || '$'}
          </Text>
          <Text selectable style={styles.errorMessage}>
            {error.message}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: palette.panel,
    borderWidth: 1,
    borderColor: palette.hairline,
    borderRadius: 10,
    padding: 14,
    gap: 10,
  },
  cardCompact: {
    padding: 10,
    gap: 8,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  cardLabel: {
    color: palette.textFaint,
  },
  headerMeta: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
    letterSpacing: 0.8,
  },
  cardTitle: {
    color: palette.text,
    fontFamily: type.sans.fontFamily,
    fontSize: 15,
    lineHeight: 20,
    fontWeight: '600',
  },
  hint: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 17,
  },
  importRow: {
    gap: 8,
  },
  importActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 10,
  },
  fileName: {
    flexShrink: 1,
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  noticeBox: {
    paddingHorizontal: 9,
    paddingVertical: 8,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
    gap: 3,
  },
  noticeTitle: {
    color: palette.text,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 16,
    fontWeight: '600',
  },
  noticeText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  summaryBox: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
    gap: 7,
  },
  summaryHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 8,
  },
  summaryTitle: {
    flex: 1,
    color: palette.text,
    fontFamily: type.displayNarrow.fontFamily,
    fontSize: 18,
    lineHeight: 22,
    fontWeight: '600',
  },
  summaryFile: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  metaGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  metaRow: {
    minWidth: 104,
    flexGrow: 1,
    flexBasis: '30%',
    gap: 1,
  },
  metaLabel: {
    color: palette.textFaint,
    fontFamily: type.section.fontFamily,
    fontSize: 9,
    lineHeight: 12,
    fontWeight: '700',
    letterSpacing: 0.7,
    textTransform: 'uppercase',
  },
  metaValue: {
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 15,
  },
  summaryFooter: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 6,
  },
  summaryHint: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
  },
  warningToggle: {
    minHeight: 26,
    justifyContent: 'center',
    paddingHorizontal: 8,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
  },
  warningToggleText: {
    color: palette.playhead,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
  },
  warningList: {
    gap: 3,
    paddingTop: 2,
  },
  warningText: {
    color: palette.playhead,
    fontFamily: type.sans.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  warnTitle: {
    color: palette.playhead,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '700',
  },
  warnText: {
    color: palette.playhead,
    fontFamily: type.sans.fontFamily,
    fontSize: 10,
    lineHeight: 15,
  },
  matrixHeader: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 6,
  },
  zoomRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  zoomButton: {
    minWidth: 28,
    minHeight: 26,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 5,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.background,
  },
  zoomButtonText: {
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 14,
    lineHeight: 18,
    fontWeight: '700',
  },
  zoomValue: {
    minWidth: 42,
    textAlign: 'center',
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 14,
    fontWeight: '700',
  },
  zoomReset: {
    minHeight: 26,
    justifyContent: 'center',
    paddingHorizontal: 7,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.background,
  },
  zoomResetText: {
    color: palette.textMuted,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
    fontWeight: '700',
  },
  blockLabel: {
    color: palette.textFaint,
  },
  legendRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 10,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  legendSwatch: {
    width: 7,
    height: 7,
    borderRadius: 1,
  },
  legendRestSwatch: {
    width: 10,
    height: 4,
    borderRadius: 1,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: palette.hairlineStrong,
    backgroundColor: 'rgba(244, 241, 234, 0.03)',
  },
  legendText: {
    color: palette.textMuted,
    fontFamily: type.section.fontFamily,
    fontSize: 9,
    lineHeight: 12,
    fontWeight: '700',
    letterSpacing: 0.4,
  },
  legendHint: {
    flexShrink: 1,
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 13,
  },
  matrix: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    borderWidth: 1,
    borderColor: palette.hairline,
    borderRadius: 8,
    backgroundColor: palette.background,
    overflow: 'hidden',
  },
  laneLabels: {
    width: LANE_LABEL_WIDTH,
    borderRightWidth: 1,
    borderRightColor: palette.hairlineStrong,
    backgroundColor: palette.panel,
  },
  rulerLabelCell: {
    justifyContent: 'flex-end',
    paddingBottom: 4,
    paddingLeft: 6,
    borderBottomWidth: 1,
    borderBottomColor: palette.hairlineStrong,
  },
  rulerLabelText: {
    color: palette.textFaint,
    fontFamily: type.section.fontFamily,
    fontSize: 8,
    lineHeight: 11,
    fontWeight: '700',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
  },
  laneLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingLeft: 6,
    borderBottomWidth: 1,
    borderBottomColor: palette.hairline,
  },
  laneSwatch: {
    width: 6,
    height: 6,
    borderRadius: 1,
  },
  laneLabelText: {
    fontFamily: type.section.fontFamily,
    fontSize: 10,
    lineHeight: 13,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  laneCount: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 8,
    lineHeight: 10,
  },
  matrixScroll: {
    flex: 1,
    minWidth: 0,
  },
  ruler: {
    position: 'relative',
    borderBottomWidth: 1,
    borderBottomColor: palette.hairlineStrong,
    backgroundColor: palette.surface,
  },
  rulerCell: {
    position: 'absolute',
    top: 0,
    paddingLeft: 3,
    paddingTop: 3,
    borderLeftWidth: 1,
    borderLeftColor: palette.hairline,
  },
  rulerCellSelected: {
    backgroundColor: 'rgba(62, 224, 224, 0.10)',
  },
  rulerCellAnchor: {
    borderLeftColor: palette.data,
    borderLeftWidth: 2,
  },
  barNumber: {
    color: palette.textMuted,
    fontFamily: type.mono.fontFamily,
    fontSize: 8,
    lineHeight: 10,
    fontWeight: '700',
  },
  meterText: {
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 7,
    lineHeight: 10,
  },
  beatTick: {
    position: 'absolute',
    bottom: 0,
    width: 1,
    height: 4,
    backgroundColor: palette.hairlineStrong,
  },
  barGrid: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    borderLeftWidth: 1,
    borderLeftColor: palette.hairline,
  },
  barGridSelected: {
    backgroundColor: 'rgba(62, 224, 224, 0.045)',
  },
  gridBeatTick: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: 1,
    backgroundColor: 'rgba(244, 241, 234, 0.035)',
  },
  selectionOverlay: {
    position: 'absolute',
    top: 0,
    backgroundColor: 'rgba(62, 224, 224, 0.12)',
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: 'rgba(62, 224, 224, 0.5)',
    overflow: 'hidden',
  },
  selectionEdge: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: 2,
    backgroundColor: palette.data,
  },
  selectionTag: {
    position: 'absolute',
    top: 1,
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 8,
    lineHeight: 10,
    fontWeight: '700',
  },
  selectionTagEnd: {
    right: 3,
    textAlign: 'right',
  },
  dragSurface: {
    position: 'absolute',
    left: 0,
    top: 0,
    cursor: 'pointer',
  },
  playhead: {
    position: 'absolute',
    top: 0,
    width: 2,
    backgroundColor: palette.playhead,
    opacity: 0.9,
  },
  rowLine: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: 1,
    backgroundColor: palette.hairline,
  },
  cell: {
    position: 'absolute',
    borderRadius: 2,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  restCell: {
    borderStyle: 'dashed',
    borderColor: 'rgba(244, 241, 234, 0.13)',
    backgroundColor: 'rgba(244, 241, 234, 0.025)',
  },
  restDash: {
    width: '60%',
    height: 1,
    backgroundColor: palette.hairlineStrong,
  },
  cellText: {
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 8,
    lineHeight: 10,
    fontWeight: '700',
  },
  selectionBox: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
    gap: 8,
  },
  rangeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'flex-end',
    gap: 8,
  },
  rangeField: {
    gap: 2,
  },
  inputLabel: {
    color: palette.textFaint,
    fontFamily: type.section.fontFamily,
    fontSize: 9,
    lineHeight: 12,
    fontWeight: '700',
    letterSpacing: 0.7,
    textTransform: 'uppercase',
  },
  rangeInput: {
    minWidth: 72,
    minHeight: 34,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.background,
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 12,
    lineHeight: 16,
  },
  rangeSummary: {
    flexShrink: 1,
    flexGrow: 1,
    color: palette.textMuted,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 14,
    paddingBottom: 4,
  },
  voiceRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 6,
  },
  chip: {
    minHeight: 30,
    justifyContent: 'center',
    paddingHorizontal: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.background,
  },
  chipActive: {
    borderColor: palette.data,
    backgroundColor: palette.dataFill,
  },
  chipText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 14,
    fontWeight: '600',
  },
  chipTextActive: {
    color: palette.data,
  },
  rangeErrors: {
    gap: 2,
  },
  rangeOk: {
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 13,
  },
  actionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 8,
  },
  button: {
    minHeight: 34,
    justifyContent: 'center',
    paddingHorizontal: 12,
    borderRadius: 6,
    borderWidth: 1,
  },
  buttonPrimary: {
    backgroundColor: palette.dataFill,
    borderColor: palette.data,
  },
  buttonSecondary: {
    backgroundColor: palette.background,
    borderColor: palette.hairlineStrong,
  },
  buttonContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  buttonText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '700',
  },
  buttonTextPrimary: {
    color: palette.data,
  },
  disabled: {
    opacity: 0.4,
  },
  pressed: {
    opacity: 0.75,
  },
  audioLine: {
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 13,
  },
  errorBox: {
    paddingHorizontal: 9,
    paddingVertical: 7,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(224, 64, 160, 0.35)',
    backgroundColor: 'rgba(224, 64, 160, 0.07)',
    gap: 3,
  },
  errorTitle: {
    color: palette.sound,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '700',
  },
  errorRows: {
    gap: 3,
  },
  errorRow: {
    flexDirection: 'row',
    gap: 6,
  },
  errorPath: {
    color: palette.sound,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 13,
  },
  errorMessage: {
    flex: 1,
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 10,
    lineHeight: 15,
  },
  badgeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  badge: {
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 4,
    borderWidth: 1,
  },
  badgePass: {
    borderColor: 'rgba(62, 224, 224, 0.5)',
    backgroundColor: 'rgba(62, 224, 224, 0.10)',
  },
  badgeFail: {
    borderColor: 'rgba(224, 64, 160, 0.5)',
    backgroundColor: 'rgba(224, 64, 160, 0.10)',
  },
  badgeText: {
    fontFamily: type.mono.fontFamily,
    fontSize: 8,
    lineHeight: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  badgeTextPass: {
    color: palette.data,
  },
  badgeTextFail: {
    color: palette.sound,
  },
  specBox: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
    gap: 8,
  },
  specHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  specHint: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  specScroll: {
    maxHeight: 260,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.background,
  },
  specText: {
    padding: 8,
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  emptyHint: {
    color: palette.textFaint,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
});

export default MusicXmlPanel;
