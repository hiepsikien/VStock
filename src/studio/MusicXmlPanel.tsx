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
} from 'react-native';
import { getApiBaseUrl } from '../api/client';
import { palette, TOUCH_TARGET } from '../musicalize/palette';
import { type } from '../musicalize/type';
import {
  requestMusicXmlPassage,
  uploadMusicXml,
  validateTextureSpec,
  type StudioError,
  type StudioValidateResponse,
} from './api';
import {
  MUSIC_XML_ROLE_LABELS,
  TICKS_PER_QUARTER,
  barLayouts,
  beatCountLabel,
  buildRoleLanes,
  defaultPassageRange,
  keySignatureLabel,
  meterChangeLabel,
  musicXmlGrid,
  normalizeMusicXmlSummary,
  passageRangeLabel,
  tempoLabel,
  validatePassageRange,
  type MusicXmlImport,
  type MusicXmlPassage,
  type MusicXmlRole,
  type MusicXmlRoleCell,
  type PassageRange,
} from './musicxml';
import { resolveAudioUrl } from './protocol';
import { byteSizeLabel, describeRequestFailure, valueLines } from './spec';

/**
 * Rhythm-first MusicXML import panel.
 *
 * The panel owns every piece of MusicXML state: the uploaded score, the bar
 * range, voice filter, passage audio/spec and texture validation. It never
 * writes into the SentenceSpec editor, so StudioRoom's dirty flag is untouched.
 *
 * Pitch is intentionally hidden. Lead/Mid/Bass rows show rhythm cells only;
 * every gap is a faint explicit rest cell (empty cell = rest).
 */

const TICK_WIDTH = 1.2;
const ROW_HEIGHT = 30;
const RULER_HEIGHT = 38;
const LANE_LABEL_WIDTH = 62;
const MIN_NOTE_WIDTH = 2;

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
};

type ValidationState =
  | { kind: 'idle' }
  | { kind: 'running' }
  | { kind: 'done'; data: StudioValidateResponse }
  | { kind: 'error'; message: string; errors: StudioError[] };

function parseBarText(value: string): number {
  const trimmed = value.trim();
  return /^\d+$/.test(trimmed) ? Number(trimmed) : Number.NaN;
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
  const [endText, setEndText] = useState('1');
  const [tapStart, setTapStart] = useState<number | null>(null);
  const [voices, setVoices] = useState<number[]>([]);
  const [passage, setPassage] = useState<MusicXmlPassage | null>(null);
  const [passageBusy, setPassageBusy] = useState<'play' | 'use' | null>(null);
  const [passageError, setPassageError] = useState<PassageError | null>(null);
  const [showSpec, setShowSpec] = useState(false);
  const [showWarnings, setShowWarnings] = useState(false);
  const [audio, setAudio] = useState<AudioState | null>(null);
  const [validation, setValidation] = useState<ValidationState>({ kind: 'idle' });
  const [copyNote, setCopyNote] = useState<string | null>(null);

  const uploadController = useRef<AbortController | null>(null);
  const passageController = useRef<AbortController | null>(null);
  const validateController = useRef<AbortController | null>(null);
  const player = useRef<HTMLAudioElement | null>(null);

  const stopPlayer = useCallback(() => {
    const current = player.current;
    player.current = null;
    if (current) current.pause();
    setAudio(null);
  }, []);

  const resetPassage = useCallback(() => {
    passageController.current?.abort();
    passageController.current = null;
    validateController.current?.abort();
    validateController.current = null;
    stopPlayer();
    setPassage(null);
    setPassageError(null);
    setPassageBusy(null);
    setShowSpec(false);
    setValidation({ kind: 'idle' });
    setCopyNote(null);
  }, [stopPlayer]);

  useEffect(
    () => () => {
      uploadController.current?.abort();
      passageController.current?.abort();
      validateController.current?.abort();
      const current = player.current;
      player.current = null;
      if (current) current.pause();
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
    barEnd: parseBarText(endText),
  };
  const rangeValidation = validatePassageRange(
    bars,
    range.barStart,
    range.barEnd,
  );
  const rangeLabel = passageRangeLabel(bars, range);
  const voicesInScore = useMemo(() => voiceOptions(imported), [imported]);
  const warnings = useMemo(() => warningUnion(imported), [imported]);
  // The passage echoes the score warnings; the summary toggle already lists
  // those, so only show passage-specific messages here.
  const passageWarnings = useMemo(
    () =>
      passage
        ? passage.warnings.filter((warning) => !warnings.includes(warning))
        : [],
    [passage, warnings],
  );
  const matrixWidth = Math.max(1, grid.totalTicks * TICK_WIDTH);
  const summary = imported?.summary ?? EMPTY_SUMMARY;

  const selectedBars = useMemo(() => {
    const selected = new Set<number>();
    if (bars.length === 0 || !rangeValidation.ok) return selected;
    const from = Math.min(range.barStart, range.barEnd);
    const to = Math.max(range.barStart, range.barEnd);
    for (let bar = from; bar <= to; bar += 1) selected.add(bar);
    return selected;
  }, [bars.length, range.barEnd, range.barStart, rangeValidation.ok]);

  const applyRange = useCallback((next: PassageRange) => {
    setStartText(String(next.barStart));
    setEndText(String(next.barEnd));
  }, []);

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
      setCopyNote(null);
      setValidation({ kind: 'idle' });
      try {
        const data = await requestMusicXmlPassage(
          imported.importId,
          {
            barStart: range.barStart,
            barEnd: range.barEnd,
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
    [imported, passageBusy, range.barEnd, range.barStart, rangeValidation.ok, voices],
  );

  const playPassage = useCallback(async () => {
    if (Platform.OS !== 'web') return;
    stopPlayer();
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
    const next = new Audio(url);
    player.current = next;
    next.onended = () => {
      setAudio((current) =>
        current?.url === url ? { ...current, playing: false } : current,
      );
    };
    next.onerror = () => {
      setPassageError({
        message: 'The browser could not play the passage WAV.',
        errors: [],
      });
      if (player.current === next) player.current = null;
      setAudio(null);
    };
    try {
      await next.play();
      setAudio({
        url,
        durationSec: data.durationSec,
        playing: true,
      });
    } catch (error) {
      next.pause();
      if (player.current === next) player.current = null;
      setPassageError({
        message: describeRequestFailure(error),
        errors: [],
      });
      setAudio(null);
    }
  }, [loadPassage, stopPlayer]);

  const usePassage = useCallback(async () => {
    const data = await loadPassage('use');
    if (data) setShowSpec(true);
  }, [loadPassage]);

  const copySpec = useCallback(async () => {
    if (!passage?.spec) return;
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(JSON.stringify(passage.spec, null, 2));
        setCopyNote('Passage spec JSON copied.');
        return;
      }
    } catch {
      // The spec block is selectable; fall through.
    }
    setCopyNote('Clipboard unavailable — select the passage spec instead.');
  }, [passage]);

  const validatePassageSpec = useCallback(async () => {
    if (!passage?.spec) return;
    validateController.current?.abort();
    const controller = new AbortController();
    validateController.current = controller;
    setValidation({ kind: 'running' });
    try {
      const data = await validateTextureSpec(passage.spec, controller.signal);
      if (controller.signal.aborted) return;
      setValidation({ kind: 'done', data });
    } catch (error) {
      if (controller.signal.aborted) return;
      setValidation({
        kind: 'error',
        message: describeRequestFailure(error),
        errors: [],
      });
    } finally {
      if (validateController.current === controller) validateController.current = null;
    }
  }, [passage]);

  const tapBar = useCallback(
    (bar: number) => {
      const next =
        tapStart == null
          ? { barStart: bar, barEnd: bar }
          : {
              barStart: Math.min(tapStart, bar),
              barEnd: Math.max(tapStart, bar),
            };
      applyRange(next);
      setTapStart(tapStart == null ? bar : null);
      resetPassage();
    },
    [applyRange, resetPassage, tapStart],
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
  const onEndChange = (value: string) => {
    setEndText(value);
    setTapStart(null);
    resetPassage();
  };

  const canRequest =
    imported != null && rangeValidation.ok && passageBusy == null;
  const canPlay = canRequest && Platform.OS === 'web';
  const specText = useMemo(
    () =>
      passage?.spec
        ? valueLines(passage.spec, 240).join('\n')
        : '',
    [passage],
  );
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
        faint rest cells, never collapsed. Passage audio/spec is a preview only
        and never touches the sentence editor.
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
            <Text style={styles.legendHint}>empty cell = rest</Text>
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
              pitch hidden · tap a bar header to set start, then end
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
            >
              <View style={{ width: matrixWidth }}>
                <View style={[styles.ruler, { height: RULER_HEIGHT }]}>
                  {grid.bars.map((bar) => {
                    const width = Math.max(2, bar.ticks * TICK_WIDTH);
                    const selected = selectedBars.has(bar.bar);
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
                            left: bar.startTick * TICK_WIDTH,
                            width,
                            height: RULER_HEIGHT,
                          },
                          selected ? styles.rulerCellSelected : null,
                          tapStart === bar.bar ? styles.rulerCellAnchor : null,
                          pressed ? styles.pressed : null,
                        ]}
                      >
                        <Text style={styles.barNumber}>{bar.bar}</Text>
                        {bar.meterStart ? (
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
                              { left: tick * TICK_WIDTH },
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
                    height: Math.max(1, lanes.length) * ROW_HEIGHT,
                  }}
                >
                  {grid.bars.map((bar) => (
                    <View
                      key={`grid:${bar.bar}`}
                      pointerEvents="none"
                      style={[
                        styles.barGrid,
                        {
                          left: bar.startTick * TICK_WIDTH,
                          width: Math.max(2, bar.ticks * TICK_WIDTH),
                        },
                        selectedBars.has(bar.bar) ? styles.barGridSelected : null,
                      ]}
                    >
                      {bar.beatTicks.slice(1).map((tick) => (
                        <View
                          key={`grid-beat:${bar.bar}:${tick}`}
                          style={[
                            styles.gridBeatTick,
                            { left: tick * TICK_WIDTH },
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
                        />
                      ))}
                    </View>
                  ))}
                </View>
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
              <Text style={styles.rangeSummary} numberOfLines={2}>
                {rangeLabel}
              </Text>
            </View>

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
              <ActionButton
                label="Use passage"
                onPress={() => void usePassage()}
                disabled={!canRequest}
                busy={passageBusy === 'use'}
                busyLabel="Building…"
              />
              {audio?.playing ? (
                <ActionButton label="Stop" onPress={stopPlayer} />
              ) : null}
            </View>
            {Platform.OS !== 'web' ? (
              <Text style={styles.legendHint}>
                Play is web-only. Use passage still returns the read-only spec.
              </Text>
            ) : null}
            {audio ? (
              <Text style={styles.audioLine}>
                {audio.playing ? 'Playing' : 'Ready'} ·{' '}
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

          {showSpec && passage?.spec ? (
            <View style={styles.specBox}>
              <View style={styles.specHeader}>
                <Text style={[type.section, styles.blockLabel]}>
                  Passage TextureSpec
                </Text>
                <Text style={styles.legendHint}>read-only preview</Text>
              </View>
              <Text style={styles.specHint}>
                This spec is generated from bars {range.barStart}–{range.barEnd}. It
                is not loaded into the SentenceSpec editor and nothing is
                registered or published.
              </Text>
              <ScrollView style={styles.specScroll} nestedScrollEnabled>
                <Text selectable style={styles.specText}>
                  {specText}
                </Text>
              </ScrollView>
              <View style={styles.actionRow}>
                <ActionButton label="Copy spec JSON" onPress={() => void copySpec()} />
                <ActionButton
                  label="Validate spec"
                  onPress={() => void validatePassageSpec()}
                  disabled={validation.kind === 'running'}
                  busy={validation.kind === 'running'}
                  busyLabel="Validating…"
                />
              </View>
              {copyNote ? <Text style={styles.legendHint}>{copyNote}</Text> : null}
              {validation.kind === 'done' ? (
                <>
                  <View style={styles.badgeRow}>
                    <Badge
                      ok={validation.data.ok}
                      label={
                        validation.data.ok
                          ? 'TEXTURE SPEC OK'
                          : 'TEXTURE SPEC ERRORS'
                      }
                    />
                  </View>
                  <ErrorRows errors={validation.data.errors} />
                </>
              ) : validation.kind === 'error' ? (
                <View style={styles.errorBox}>
                  <Text style={styles.errorTitle}>{validation.message}</Text>
                  <ErrorRows errors={validation.errors} />
                </View>
              ) : (
                <Text style={styles.legendHint}>
                  Validate runs the existing offline TextureSpec validator only.
                </Text>
              )}
            </View>
          ) : null}
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
}: {
  cell: MusicXmlRoleCell;
  role: MusicXmlRole;
  /** Absolute start tick of the cell's bar in the score-wide matrix. */
  offsetTicks: number;
}) {
  const width = Math.max(MIN_NOTE_WIDTH, cell.ticks * TICK_WIDTH);
  const height = ROW_HEIGHT - 8;
  const showDuration = !cell.rest && width >= 17;
  const showCount = !cell.rest && cell.count > 1 && width >= 33;
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
          left: (offsetTicks + cell.startTick) * TICK_WIDTH,
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
