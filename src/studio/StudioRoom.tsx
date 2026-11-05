import React, { useCallback, useEffect, useRef, useState } from 'react';
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
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { getApiBaseUrl } from '../api/client';
import { palette, TOUCH_TARGET } from '../musicalize/palette';
import { TopBar, type RoomMode } from '../musicalize/TopBar';
import { type } from '../musicalize/type';
import {
  fetchPublishedSpec,
  fetchPublishedSpecs,
  fetchSentenceExamples,
  previewSentenceSpec,
  publishSentenceSpec,
  requestSentenceAudio,
  studioSentenceUrl,
  validateSentenceSpec,
  type StudioError,
  type StudioPreviewResponse,
  type StudioPublishedSpec,
  type StudioValidateResponse,
} from './api';
import { resolveAudioUrl } from './protocol';
import {
  DEFAULT_SAMPLE,
  SAMPLES,
  examplesToSamples,
  checkSpecText,
  defaultSampleForPattern,
  describeRequestFailure,
  durationLabel,
  findSample,
  fixtureText as sampleFixtureText,
  fixtureTextForSpec,
  meterLabel,
  metersForPattern,
  normalizeErrorPath,
  notesLines,
  parseJsonObject,
  patternCatalogHint,
  patternIds,
  patternLabel,
  planLines,
  prefixErrorPaths,
  publishedAtLabel,
  publishedSpecMeta,
  publishedSpecTitle,
  sampleText,
  shortId,
  textStats,
  valueLines,
  type StudioSample,
} from './spec';

type Props = {
  wide: boolean;
  onMode: (mode: RoomMode) => void;
};

type RunAction = 'validate' | 'preview';

type StudioResult =
  | { kind: 'idle' }
  | { kind: 'running'; action: RunAction }
  | { kind: 'validate'; data: StudioValidateResponse; elapsedMs: number }
  | { kind: 'preview'; data: StudioPreviewResponse; elapsedMs: number }
  | { kind: 'failure'; action: RunAction; message: string; errors: StudioError[] };

type Selection = {
  key: string;
  pattern: string;
  meter: string;
  title: string;
  id?: string;
};

type PreviewSnapshot = {
  spec: Record<string, unknown>;
  fixture: Record<string, unknown>;
  renderHash: string | null;
};

type AudioState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | {
      kind: 'ready';
      url: string;
      durationSec: number;
      renderHash: string | null;
      playing: boolean;
    }
  | { kind: 'error'; message: string; errors: StudioError[] };

type PublishState =
  | { kind: 'idle' }
  | { kind: 'running' }
  | {
      kind: 'ok';
      id: string;
      pattern: string;
      meter: string;
      version: number;
    }
  | { kind: 'failure'; message: string; errors: StudioError[] };

type PublishedListState = {
  loading: boolean;
  items: StudioPublishedSpec[];
  error: string | null;
};

type CatalogState = {
  loading: boolean;
  source: 'api' | 'fallback';
  note: string | null;
};

const DEFAULT_STUDIO_SAMPLE = DEFAULT_SAMPLE;
const DEFAULT_SELECTION: Selection = {
  key: DEFAULT_STUDIO_SAMPLE.key,
  pattern: DEFAULT_STUDIO_SAMPLE.pattern,
  meter: DEFAULT_STUDIO_SAMPLE.meter,
  title: DEFAULT_STUDIO_SAMPLE.title,
  id: DEFAULT_STUDIO_SAMPLE.id,
};

function msLabel(ms: number): string {
  return `${Math.max(1, Math.round(ms))} ms`;
}

function selectionForSample(sample: StudioSample): Selection {
  return {
    key: sample.key,
    pattern: sample.pattern,
    meter: sample.meter,
    title: sample.title,
    id: sample.id,
  };
}

export function StudioRoom({ wide, onMode }: Props) {
  const insets = useSafeAreaInsets();
  const [samples, setSamples] = useState<readonly StudioSample[]>(SAMPLES);
  const [catalog, setCatalog] = useState<CatalogState>({
    loading: true,
    source: 'fallback',
    note: null,
  });
  const [selection, setSelection] = useState<Selection>(DEFAULT_SELECTION);
  const [specText, setSpecText] = useState(() => sampleText(DEFAULT_STUDIO_SAMPLE));
  const [fixtureJson, setFixtureJson] = useState(() =>
    sampleFixtureText(DEFAULT_STUDIO_SAMPLE),
  );
  const [showFixture, setShowFixture] = useState(false);
  const [result, setResult] = useState<StudioResult>({ kind: 'idle' });
  const [dirty, setDirty] = useState(false);
  const [previewSnapshot, setPreviewSnapshot] = useState<PreviewSnapshot | null>(null);
  const [audio, setAudio] = useState<AudioState>({ kind: 'idle' });
  const [publishState, setPublishState] = useState<PublishState>({ kind: 'idle' });
  const [published, setPublished] = useState<PublishedListState>({
    loading: true,
    items: [],
    error: null,
  });
  const [loadingSpecId, setLoadingSpecId] = useState<string | null>(null);

  const inFlight = useRef<AbortController | null>(null);
  const examplesController = useRef<AbortController | null>(null);
  const specsController = useRef<AbortController | null>(null);
  const publishController = useRef<AbortController | null>(null);
  const specDetailController = useRef<AbortController | null>(null);
  const audioController = useRef<AbortController | null>(null);
  const audioPlayer = useRef<HTMLAudioElement | null>(null);
  const audioRunId = useRef(0);
  const runId = useRef(0);
  const specTextRef = useRef(specText);
  const fixtureJsonRef = useRef(fixtureJson);
  const dirtyRef = useRef(dirty);
  const selectionRef = useRef(selection);
  // A run/publish started before the examples response lands must not be wiped
  // by the palette swap.
  const engagedRef = useRef(false);
  specTextRef.current = specText;
  fixtureJsonRef.current = fixtureJson;
  dirtyRef.current = dirty;
  selectionRef.current = selection;

  const stopPlayer = useCallback(() => {
    const player = audioPlayer.current;
    audioPlayer.current = null;
    if (player) {
      try {
        player.pause();
        player.currentTime = 0;
      } catch {
        // The element may already be detached; nothing to release.
      }
    }
  }, []);

  const resetAudio = useCallback(() => {
    audioRunId.current += 1;
    audioController.current?.abort();
    audioController.current = null;
    stopPlayer();
    setAudio({ kind: 'idle' });
  }, [stopPlayer]);

  const applyEditor = useCallback(
    (nextSpecText: string, nextFixtureText: string, nextSelection: Selection) => {
      inFlight.current?.abort();
      inFlight.current = null;
      runId.current += 1;
      resetAudio();
      setSelection(nextSelection);
      setSpecText(nextSpecText);
      setFixtureJson(nextFixtureText);
      setResult({ kind: 'idle' });
      setPreviewSnapshot(null);
      setDirty(false);
    },
    [resetAudio],
  );

  const applySample = useCallback(
    (sample: StudioSample) => {
      applyEditor(sampleText(sample), sampleFixtureText(sample), selectionForSample(sample));
    },
    [applyEditor],
  );

  useEffect(
    () => () => {
      inFlight.current?.abort();
      examplesController.current?.abort();
      specsController.current?.abort();
      publishController.current?.abort();
      specDetailController.current?.abort();
      audioController.current?.abort();
      stopPlayer();
    },
    [stopPlayer],
  );

  // The API examples are the palette. Embedded Torroba/Sor samples only fill in
  // when the endpoint is missing, so the hand-copied list cannot silently drift.
  useEffect(() => {
    const controller = new AbortController();
    examplesController.current = controller;
    void (async () => {
      try {
        const data = await fetchSentenceExamples(controller.signal);
        if (controller.signal.aborted) return;
        const next = examplesToSamples(data.examples);
        if (!next.length) {
          setCatalog({
            loading: false,
            source: 'fallback',
            note: 'Examples API returned no examples — using the embedded Torroba/Sor samples.',
          });
          return;
        }
        setSamples(next);
        setCatalog({ loading: false, source: 'api', note: null });
        if (!dirtyRef.current && !engagedRef.current) {
          const match =
            findSample(selectionRef.current.pattern, selectionRef.current.meter, next) ??
            next[0];
          applySample(match);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        setCatalog({
          loading: false,
          source: 'fallback',
          note: `Examples API unavailable (${describeRequestFailure(error)}) — using embedded Torroba/Sor samples.`,
        });
      } finally {
        if (examplesController.current === controller) examplesController.current = null;
      }
    })();
    return () => controller.abort();
  }, [applySample]);

  const loadPublished = useCallback(async () => {
    specsController.current?.abort();
    const controller = new AbortController();
    specsController.current = controller;
    setPublished((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const items = await fetchPublishedSpecs(controller.signal);
      if (controller.signal.aborted) return;
      setPublished({ loading: false, items, error: null });
    } catch (error) {
      if (controller.signal.aborted) return;
      setPublished((prev) => ({
        loading: false,
        items: prev.items,
        error: describeRequestFailure(error),
      }));
    } finally {
      if (specsController.current === controller) specsController.current = null;
    }
  }, []);

  useEffect(() => {
    void loadPublished();
    return () => specsController.current?.abort();
  }, [loadPublished]);

  const choosePattern = useCallback(
    (pattern: string) => {
      const sample =
        findSample(pattern, selection.meter, samples) ??
        defaultSampleForPattern(pattern, samples);
      applySample(sample);
    },
    [applySample, samples, selection.meter],
  );

  const chooseMeter = useCallback(
    (meter: string) => {
      const sample = findSample(selection.pattern, meter, samples);
      if (sample) applySample(sample);
    },
    [applySample, samples, selection.pattern],
  );

  const run = useCallback(
    async (action: RunAction) => {
      engagedRef.current = true;
      const checked = checkSpecText(specText);
      if (!checked.ok) {
        setResult({
          kind: 'failure',
          action,
          message: 'Fix the spec JSON before sending it.',
          errors: checked.errors,
        });
        return;
      }

      let fixture: Record<string, unknown> | null = null;
      if (action === 'preview') {
        const parsed = parseJsonObject(fixtureJson, 'Fixture');
        if (!parsed.ok) {
          setResult({
            kind: 'failure',
            action,
            message: 'Fix the preview fixture before sending it.',
            errors: prefixErrorPaths(parsed.errors, 'fixture'),
          });
          return;
        }
        fixture = parsed.value;
      }

      resetAudio();
      setPreviewSnapshot(null);
      inFlight.current?.abort();
      const controller = new AbortController();
      inFlight.current = controller;
      const id = ++runId.current;
      const startedAt = Date.now();
      const startedSpec = specText;
      const startedFixture = fixtureJson;
      setResult({ kind: 'running', action });

      try {
        if (action === 'validate') {
          const data = await validateSentenceSpec(checked.spec, controller.signal);
          if (id !== runId.current) return;
          setResult({ kind: 'validate', data, elapsedMs: Date.now() - startedAt });
        } else {
          const data = await previewSentenceSpec(
            checked.spec,
            fixture as Record<string, unknown>,
            controller.signal,
          );
          if (id !== runId.current) return;
          setResult({ kind: 'preview', data, elapsedMs: Date.now() - startedAt });
          if (data.ok) {
            setPreviewSnapshot({
              spec: checked.spec,
              fixture: fixture ?? {},
              renderHash: data.renderHash,
            });
          }
        }
        if (
          specTextRef.current === startedSpec &&
          fixtureJsonRef.current === startedFixture
        ) {
          setDirty(false);
        }
      } catch (error) {
        if (controller.signal.aborted || id !== runId.current) return;
        setResult({
          kind: 'failure',
          action,
          message: describeRequestFailure(error),
          errors: [],
        });
      } finally {
        if (inFlight.current === controller) inFlight.current = null;
      }
    },
    [fixtureJson, resetAudio, specText],
  );

  const playAudio = useCallback(async () => {
    if (!previewSnapshot) return;
    if (Platform.OS !== 'web') {
      setAudio({
        kind: 'error',
        message: 'Audio playback is web-only in this sprint.',
        errors: [],
      });
      return;
    }

    audioController.current?.abort();
    const controller = new AbortController();
    audioController.current = controller;
    const id = ++audioRunId.current;
    stopPlayer();
    setAudio({ kind: 'loading' });

    try {
      const data = await requestSentenceAudio(
        { spec: previewSnapshot.spec, fixture: previewSnapshot.fixture },
        controller.signal,
      );
      if (controller.signal.aborted || id !== audioRunId.current) return;
      if (!data.ok || !data.audioUrl) {
        setAudio({
          kind: 'error',
          message: data.errors[0]?.message ?? 'Audio preview failed.',
          errors: data.errors,
        });
        return;
      }
      const url = resolveAudioUrl(getApiBaseUrl(), data.audioUrl);
      if (!url) {
        setAudio({
          kind: 'error',
          message: 'The audio response did not include a usable URL.',
          errors: [],
        });
        return;
      }

      const player = new Audio(url);
      audioPlayer.current = player;
      player.onended = () => {
        if (id === audioRunId.current) {
          setAudio((prev) => (prev.kind === 'ready' ? { ...prev, playing: false } : prev));
        }
      };
      player.onerror = () => {
        if (id === audioRunId.current) {
          setAudio({
            kind: 'error',
            message: 'The browser could not play the preview WAV.',
            errors: [],
          });
        }
      };
      await player.play();
      if (controller.signal.aborted || id !== audioRunId.current) {
        player.pause();
        return;
      }
      setAudio({
        kind: 'ready',
        url,
        durationSec: data.durationSec,
        renderHash: data.renderHash ?? previewSnapshot.renderHash,
        playing: true,
      });
    } catch (error) {
      if (controller.signal.aborted || id !== audioRunId.current) return;
      setAudio({
        kind: 'error',
        message: describeRequestFailure(error),
        errors: [],
      });
    } finally {
      if (audioController.current === controller) audioController.current = null;
    }
  }, [previewSnapshot, stopPlayer]);

  const publish = useCallback(async () => {
    engagedRef.current = true;
    const checked = checkSpecText(specTextRef.current);
    if (!checked.ok) {
      setPublishState({
        kind: 'failure',
        message: 'Fix the spec JSON before publishing.',
        errors: checked.errors,
      });
      return;
    }

    publishController.current?.abort();
    const controller = new AbortController();
    publishController.current = controller;
    setPublishState({ kind: 'running' });
    try {
      const data = await publishSentenceSpec(checked.spec, controller.signal);
      if (controller.signal.aborted) return;
      if (!data.ok || !data.id) {
        setPublishState({
          kind: 'failure',
          message: data.errors[0]?.message ?? 'Publish failed.',
          errors: data.errors,
        });
        return;
      }
      setPublishState({
        kind: 'ok',
        id: data.id,
        pattern: data.pattern ?? String(checked.spec.pattern ?? ''),
        meter: data.meter ?? String(checked.spec.meter ?? ''),
        version: data.version ?? 0,
      });
      void loadPublished();
    } catch (error) {
      if (controller.signal.aborted) return;
      setPublishState({
        kind: 'failure',
        message: describeRequestFailure(error),
        errors: [],
      });
    } finally {
      if (publishController.current === controller) publishController.current = null;
    }
  }, [loadPublished]);

  const openPublished = useCallback(
    async (id: string) => {
      specDetailController.current?.abort();
      const controller = new AbortController();
      specDetailController.current = controller;
      setLoadingSpecId(id);
      setPublished((prev) => ({ ...prev, error: null }));
      try {
        const detail = await fetchPublishedSpec(id, controller.signal);
        if (controller.signal.aborted) return;
        applyEditor(
          JSON.stringify(detail.payload, null, 2),
          fixtureTextForSpec(detail.payload),
          {
            key: `${detail.pattern}:${detail.meter}`,
            pattern: detail.pattern,
            meter: detail.meter,
            title: `${publishedSpecTitle(detail)} · v${detail.version}`,
            id: detail.id,
          },
        );
        setPublishState({ kind: 'idle' });
      } catch (error) {
        if (controller.signal.aborted) return;
        setPublished((prev) => ({
          ...prev,
          error: `Could not load ${shortId(id)}: ${describeRequestFailure(error)}`,
        }));
      } finally {
        if (specDetailController.current === controller) {
          specDetailController.current = null;
        }
        setLoadingSpecId((current) => (current === id ? null : current));
      }
    },
    [applyEditor],
  );

  const running = result.kind === 'running';
  const publishing = publishState.kind === 'running';
  const stale =
    dirty &&
    (result.kind === 'validate' ||
      result.kind === 'preview' ||
      result.kind === 'failure');
  const stats = textStats(specText);

  const catalogPatterns = patternIds(samples);
  const patternChoices = catalogPatterns.includes(selection.pattern)
    ? catalogPatterns
    : [selection.pattern, ...catalogPatterns];
  const catalogMeters = metersForPattern(samples, selection.pattern);
  const meterChoices = catalogMeters.includes(selection.meter)
    ? catalogMeters
    : [selection.meter, ...catalogMeters];

  return (
    <View
      style={[
        styles.root,
        { paddingTop: insets.top, paddingBottom: insets.bottom },
      ]}
    >
      <TopBar mode="studio" onMode={onMode} searchEnabled={false} />

      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.shell}>
          <View style={styles.header}>
            <View style={styles.eyebrowRow}>
              <Text style={[type.section, styles.eyebrow]}>Studio · sentence JSON</Text>
              <View style={styles.devBadge}>
                <Text style={styles.devBadgeText}>DEV</Text>
              </View>
            </View>
            <Text style={[type.displayNarrow, styles.title]}>Sentence lab</Text>
            <Text style={styles.subtitle}>
              Edit one sentence spec, validate it against the registry, preview the
              plan and render hash, then play the short preview WAV and publish a
              version. The JSON editor remains the source of truth.
            </Text>
          </View>

          <View style={[styles.columns, wide && styles.columnsWide]}>
            <View style={[styles.column, wide && styles.columnWide]}>
              <View style={styles.card}>
                <Text style={[type.section, styles.cardLabel]}>
                  {catalog.source === 'api' ? 'API example' : 'Embedded template'}
                </Text>
                <Text style={styles.cardTitle}>{selection.title}</Text>
                {selection.id ? (
                  <Text selectable style={styles.templateId}>
                    id {selection.id}
                  </Text>
                ) : null}
                <Text style={styles.hint}>
                  Picking a pattern or meter loads a known-good example and replaces
                  the editor contents. The JSON below is always the source of truth
                  for a run.
                </Text>
                {catalog.loading ? (
                  <Text style={styles.catalogNote}>Loading examples…</Text>
                ) : catalog.note ? (
                  <Text style={styles.catalogWarning}>{catalog.note}</Text>
                ) : null}

                <Text style={styles.fieldLabel}>Pattern</Text>
                <View style={styles.chips}>
                  {patternChoices.map((pattern) => (
                    <Chip
                      key={pattern}
                      label={patternLabel(pattern)}
                      active={selection.pattern === pattern}
                      accessibilityLabel={patternLabel(pattern)}
                      onPress={() => choosePattern(pattern)}
                    />
                  ))}
                </View>
                <Text style={styles.composerHint}>{patternCatalogHint(samples)}</Text>

                <Text style={styles.fieldLabel}>Meter</Text>
                <View style={styles.chips}>
                  {meterChoices.map((meter) => (
                    <Chip
                      key={meter}
                      label={meterLabel(meter)}
                      active={selection.meter === meter}
                      accessibilityLabel={meterLabel(meter)}
                      onPress={() => chooseMeter(meter)}
                    />
                  ))}
                </View>

                <View style={styles.editorHeader}>
                  <View>
                    <Text style={[type.section, styles.cardLabel]}>Spec JSON</Text>
                    <Text style={styles.hint}>One sentence spec mapping.</Text>
                  </View>
                  <Text style={styles.stats}>
                    {stats.lines} lines · {stats.chars} chars
                  </Text>
                </View>

                <TextInput
                  multiline
                  value={specText}
                  onChangeText={(next) => {
                    setSpecText(next);
                    setDirty(true);
                  }}
                  style={styles.editor}
                  accessibilityLabel="Sentence spec JSON"
                  autoCapitalize="none"
                  autoCorrect={false}
                  autoComplete="off"
                  placeholder="Paste one sentence spec mapping…"
                  placeholderTextColor={palette.textFaint}
                  selectionColor={palette.data}
                  textAlignVertical="top"
                />

                <View style={styles.actions}>
                  <ActionButton
                    label="Validate"
                    onPress={() => void run('validate')}
                    disabled={running || publishing}
                    busy={result.kind === 'running' && result.action === 'validate'}
                  />
                  <ActionButton
                    label="Preview"
                    primary
                    onPress={() => void run('preview')}
                    disabled={running || publishing}
                    busy={result.kind === 'running' && result.action === 'preview'}
                  />
                  <ActionButton
                    label="Publish"
                    onPress={() => void publish()}
                    disabled={running || publishing}
                    busy={publishing}
                  />
                  {running || publishing ? (
                    <ActivityIndicator color={palette.data} size="small" />
                  ) : null}
                  {stale ? (
                    <Text style={styles.stale}>Edited since the last run.</Text>
                  ) : null}
                </View>

                <PublishStatus state={publishState} />
              </View>

              <View style={styles.card}>
                <Pressable
                  onPress={() => setShowFixture((open) => !open)}
                  accessibilityRole="button"
                  accessibilityState={{ expanded: showFixture }}
                  accessibilityLabel="Preview fixture"
                  style={({ pressed }) => [
                    styles.fixtureHeader,
                    pressed && styles.pressed,
                  ]}
                >
                  <View style={styles.fixtureHeaderText}>
                    <Text style={[type.section, styles.cardLabel]}>Preview fixture</Text>
                    <Text style={styles.cardTitle}>
                      {showFixture ? 'Fixture JSON' : 'Show the fixture sent with Preview'}
                    </Text>
                  </View>
                  <Text style={styles.fixtureToggle}>{showFixture ? '−' : '+'}</Text>
                </Pressable>
                <Text style={styles.hint}>
                  Figure sentences use <Text style={styles.code}>length</Text>,{' '}
                  <Text style={styles.code}>n</Text>,{' '}
                  <Text style={styles.code}>closes</Text>, and{' '}
                  <Text style={styles.code}>rise</Text>. Cell/cycle specs use{' '}
                  <Text style={styles.code}>run_length</Text>. API examples derive a
                  fixture from the spec; edit it for a different render.
                </Text>
                {showFixture ? (
                  <TextInput
                    multiline
                    value={fixtureJson}
                    onChangeText={(next) => {
                      setFixtureJson(next);
                      setDirty(true);
                    }}
                    style={[styles.editor, styles.fixtureEditor]}
                    accessibilityLabel="Preview fixture JSON"
                    autoCapitalize="none"
                    autoCorrect={false}
                    autoComplete="off"
                    placeholder="Preview fixture JSON…"
                    placeholderTextColor={palette.textFaint}
                    selectionColor={palette.data}
                    textAlignVertical="top"
                  />
                ) : null}
              </View>
            </View>

            <View style={[styles.column, wide && styles.columnWide]}>
              <ResultPanel
                result={result}
                stale={stale}
                audio={audio}
                audioSupported={Platform.OS === 'web'}
                canPlayAudio={previewSnapshot !== null}
                onPlayAudio={() => void playAudio()}
              />
              <PublishedPanel
                state={published}
                loadingId={loadingSpecId}
                onRefresh={() => void loadPublished()}
                onOpen={(id) => void openPublished(id)}
              />
              <View style={styles.endpoints}>
                <Text style={styles.endpointLabel}>Endpoints</Text>
                <Text selectable style={styles.endpoint}>
                  GET {studioSentenceUrl('examples')}
                </Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioSentenceUrl('validate')}
                </Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioSentenceUrl('preview')}
                </Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioSentenceUrl('audio')}
                </Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioSentenceUrl('publish')}
                </Text>
                <Text selectable style={styles.endpoint}>
                  GET {studioSentenceUrl('specs')}
                </Text>
              </View>
            </View>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

function Chip({
  label,
  active,
  onPress,
  accessibilityLabel,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
  accessibilityLabel: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ selected: active }}
      style={({ pressed }) => [
        styles.chip,
        active && styles.chipActive,
        pressed && styles.pressed,
      ]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

function ActionButton({
  label,
  onPress,
  primary = false,
  disabled = false,
  busy = false,
}: {
  label: string;
  onPress: () => void;
  primary?: boolean;
  disabled?: boolean;
  busy?: boolean;
}) {
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
        disabled ? styles.buttonDisabled : null,
      ]}
    >
      <Text style={[styles.buttonText, primary && styles.buttonTextPrimary]}>
        {label}
      </Text>
    </Pressable>
  );
}

function ErrorList({ errors }: { errors: StudioError[] }) {
  if (errors.length === 0) return null;
  return (
    <View style={styles.errorList}>
      {errors.map((error, index) => (
        <View key={`${error.path}:${index}`} style={styles.errorRow}>
          <Text selectable style={styles.errorPath}>
            {normalizeErrorPath(error.path)}
          </Text>
          <Text selectable style={styles.errorMessage}>
            {error.message}
          </Text>
        </View>
      ))}
    </View>
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

function ResultBlock({
  label,
  lines,
  empty,
}: {
  label: string;
  lines: string[];
  empty: string;
}) {
  return (
    <View style={styles.block}>
      <View style={styles.blockHeader}>
        <Text style={[type.section, styles.blockLabel]}>{label}</Text>
        {lines.length ? <Text style={styles.blockCount}>{lines.length}</Text> : null}
      </View>
      {lines.length ? (
        <Text selectable style={styles.codeBlock}>
          {lines.join('\n')}
        </Text>
      ) : (
        <Text style={styles.empty}>{empty}</Text>
      )}
    </View>
  );
}

function PublishStatus({ state }: { state: PublishState }) {
  if (state.kind === 'idle') return null;
  if (state.kind === 'running') {
    return (
      <View style={styles.publishStatus}>
        <ActivityIndicator color={palette.data} size="small" />
        <Text style={styles.publishStatusText}>Publishing current spec…</Text>
      </View>
    );
  }
  if (state.kind === 'failure') {
    return (
      <View style={styles.publishStatus}>
        <Text style={styles.publishFailure}>{state.message}</Text>
        <ErrorList errors={state.errors} />
      </View>
    );
  }
  return (
    <View style={styles.publishStatus}>
      <Text style={styles.publishOk}>
        Published v{state.version} · {shortId(state.id)}
      </Text>
      <Text style={styles.publishStatusText}>
        {patternLabel(state.pattern)} · {meterLabel(state.meter)}
      </Text>
    </View>
  );
}

function AudioControls({
  state,
  supported,
  canPlay,
  onPlay,
}: {
  state: AudioState;
  supported: boolean;
  canPlay: boolean;
  onPlay: () => void;
}) {
  if (!supported) {
    return (
      <View style={styles.audioRow}>
        <Text style={styles.audioText}>
          Audio playback is web-only in this sprint. The render hash and duration
          still identify the server-side WAV.
        </Text>
      </View>
    );
  }
  if (!canPlay) {
    return (
      <View style={styles.audioRow}>
        <Text style={styles.audioText}>
          Run a successful preview to render its short preview WAV.
        </Text>
      </View>
    );
  }
  return (
    <View style={styles.audioPanel}>
      <View style={styles.audioRow}>
        <ActionButton
          label={state.kind === 'loading' ? 'Rendering audio…' : 'Play preview'}
          onPress={onPlay}
          disabled={state.kind === 'loading'}
          busy={state.kind === 'loading'}
        />
        {state.kind === 'loading' ? (
          <Text style={styles.audioText}>Synthesizing the cached WAV…</Text>
        ) : state.kind === 'ready' ? (
          <Text style={styles.audioText}>
            {durationLabel(state.durationSec)} WAV
            {state.playing ? ' · playing' : ''}
          </Text>
        ) : state.kind === 'error' ? (
          <Text style={styles.audioText}>{state.message}</Text>
        ) : (
          <Text style={styles.audioText}>
            Calls /sentence/audio for this preview&apos;s spec and fixture.
          </Text>
        )}
      </View>
      {state.kind === 'error' ? <ErrorList errors={state.errors} /> : null}
    </View>
  );
}

function ResultPanel({
  result,
  stale,
  audio,
  audioSupported,
  canPlayAudio,
  onPlayAudio,
}: {
  result: StudioResult;
  stale: boolean;
  audio: AudioState;
  audioSupported: boolean;
  canPlayAudio: boolean;
  onPlayAudio: () => void;
}) {
  if (result.kind === 'idle') {
    return (
      <View style={[styles.card, styles.resultCard]}>
        <Text style={[type.section, styles.cardLabel]}>Result</Text>
        <Text style={styles.cardTitle}>Nothing run yet</Text>
        <Text style={styles.hint}>
          Validate checks the spec without rendering. Preview sends the spec plus a
          fixture and returns a plan, row, matrix, note list, and render hash.
        </Text>
        <View style={styles.emptyBox}>
          <Text style={styles.empty}>Validate or Preview to see output here.</Text>
        </View>
      </View>
    );
  }

  if (result.kind === 'running') {
    return (
      <View style={[styles.card, styles.resultCard]}>
        <Text style={[type.section, styles.cardLabel]}>Result</Text>
        <View style={styles.loadingRow}>
          <ActivityIndicator color={palette.data} />
          <Text style={styles.loadingText}>
            {result.action === 'validate' ? 'Validating spec…' : 'Rendering preview…'}
          </Text>
        </View>
      </View>
    );
  }

  if (result.kind === 'failure') {
    return (
      <View style={[styles.card, styles.resultCard]}>
        <View style={styles.resultHeader}>
          <Badge ok={false} label="NOT SENT" />
          <Text style={styles.actionLabel}>
            {result.action === 'validate' ? 'Validate' : 'Preview'}
          </Text>
        </View>
        <Text style={styles.failureTitle}>{result.message}</Text>
        <ErrorList errors={result.errors} />
        <Text style={styles.hint}>
          The request was stopped in the app. Fix the highlighted JSON and run it
          again.
        </Text>
      </View>
    );
  }

  if (result.kind === 'validate') {
    const { data } = result;
    return (
      <View style={[styles.card, styles.resultCard]}>
        <View style={styles.resultHeader}>
          <Badge ok={data.ok} label={data.ok ? 'VALID' : 'INVALID'} />
          <Text style={styles.actionLabel}>Validate · {msLabel(result.elapsedMs)}</Text>
        </View>
        {stale ? <Text style={styles.stale}>Editor changed since this run.</Text> : null}
        <ErrorList errors={data.errors} />
        {data.ok && data.errors.length === 0 ? (
          <View style={styles.filledBox}>
            <Text style={styles.successText}>
              Spec accepted by the server. Run Preview to render a plan.
            </Text>
          </View>
        ) : !data.ok && data.errors.length === 0 ? (
          <View style={styles.filledBox}>
            <Text style={styles.empty}>
              Server rejected the spec without returning an error path.
            </Text>
          </View>
        ) : null}
      </View>
    );
  }

  const { data } = result;
  const plan = planLines(data.plan);
  const row = valueLines(data.row, 24);
  const matrix = valueLines(data.matrix, 40);
  const notes = notesLines(data.notes);
  const planEmpty =
    Array.isArray(data.plan) && data.plan.length === 0
      ? 'No spans matched this fixture. The select did not match, or the pattern/meter pair has no plan.'
      : 'No plan returned.';

  return (
    <View style={[styles.card, styles.resultCard]}>
      <View style={styles.resultHeader}>
        <Badge ok={data.ok} label={data.ok ? 'PREVIEW OK' : 'PREVIEW FAILED'} />
        <Text style={styles.actionLabel}>Preview · {msLabel(result.elapsedMs)}</Text>
      </View>
      {stale ? <Text style={styles.stale}>Editor changed since this run.</Text> : null}
      <ErrorList errors={data.errors} />

      <View style={styles.hashRow}>
        <Text style={[type.section, styles.blockLabel]}>Render hash</Text>
        <Text selectable style={styles.hash}>
          {data.renderHash ?? 'not returned'}
        </Text>
      </View>

      <AudioControls
        state={audio}
        supported={audioSupported}
        canPlay={canPlayAudio && data.ok}
        onPlay={onPlayAudio}
      />

      <ResultBlock label="Plan" lines={plan} empty={planEmpty} />
      <ResultBlock label="Row" lines={row} empty="No row returned." />
      <ResultBlock label="Matrix" lines={matrix} empty="No matrix returned." />
      <ResultBlock label="Notes" lines={notes} empty="No notes returned." />
    </View>
  );
}

function PublishedPanel({
  state,
  loadingId,
  onRefresh,
  onOpen,
}: {
  state: PublishedListState;
  loadingId: string | null;
  onRefresh: () => void;
  onOpen: (id: string) => void;
}) {
  return (
    <View style={styles.card}>
      <View style={styles.publishedHeader}>
        <View style={styles.fixtureHeaderText}>
          <Text style={[type.section, styles.cardLabel]}>Published specs</Text>
          <Text style={styles.cardTitle}>
            {state.items.length
              ? `${state.items.length} version${state.items.length === 1 ? '' : 's'}`
              : 'No versions yet'}
          </Text>
        </View>
        <Pressable
          onPress={onRefresh}
          disabled={state.loading}
          accessibilityRole="button"
          accessibilityLabel="Refresh published specs"
          style={({ pressed }) => [
            styles.refreshButton,
            pressed && styles.pressed,
            state.loading ? styles.buttonDisabled : null,
          ]}
        >
          <Text style={styles.refreshText}>{state.loading ? 'Loading…' : 'Refresh'}</Text>
        </Pressable>
      </View>

      {state.error ? <Text style={styles.catalogWarning}>{state.error}</Text> : null}
      {state.items.length === 0 && !state.loading && !state.error ? (
        <Text style={styles.empty}>
          Publish a spec to start its version history. Rows load the stored payload
          back into the editor.
        </Text>
      ) : null}

      {state.items.map((item) => (
        <Pressable
          key={item.id}
          onPress={() => onOpen(item.id)}
          accessibilityRole="button"
          accessibilityLabel={`Load published ${publishedSpecTitle(item)}, ${publishedSpecMeta(item)}, id ${item.id}`}
          style={({ pressed }) => [
            styles.publishedRow,
            pressed && styles.pressed,
          ]}
        >
          <View style={styles.publishedRowMain}>
            <Text style={styles.publishedTitle}>{publishedSpecTitle(item)}</Text>
            <Text selectable numberOfLines={1} style={styles.publishedId}>
              {item.id}
            </Text>
          </View>
          <View style={styles.publishedRight}>
            <Text style={styles.publishedVersion}>v{item.version}</Text>
            <Text style={styles.publishedTime}>{publishedAtLabel(item.createdAt)}</Text>
          </View>
          {loadingId === item.id ? (
            <ActivityIndicator color={palette.data} size="small" />
          ) : null}
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: palette.background,
  },
  scroll: {
    padding: 20,
    paddingBottom: 40,
  },
  shell: {
    width: '100%',
    maxWidth: 1280,
    alignSelf: 'center',
    gap: 16,
  },
  header: {
    gap: 6,
  },
  eyebrowRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  eyebrow: {
    color: palette.data,
  },
  devBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 3,
    borderWidth: 1,
    borderColor: palette.playhead,
  },
  devBadgeText: {
    color: palette.playhead,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
  },
  title: {
    color: palette.text,
  },
  subtitle: {
    maxWidth: 760,
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 13,
    lineHeight: 19,
  },
  columns: {
    gap: 16,
  },
  columnsWide: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  column: {
    gap: 16,
  },
  columnWide: {
    flex: 1,
    minWidth: 0,
  },
  card: {
    backgroundColor: palette.panel,
    borderWidth: 1,
    borderColor: palette.hairline,
    borderRadius: 10,
    padding: 14,
    gap: 10,
  },
  resultCard: {
    minHeight: 260,
  },
  cardLabel: {
    color: palette.textFaint,
  },
  cardTitle: {
    color: palette.text,
    fontFamily: type.sans.fontFamily,
    fontSize: 15,
    lineHeight: 20,
    fontWeight: '600',
  },
  templateId: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  catalogNote: {
    color: palette.data,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  catalogWarning: {
    color: palette.playhead,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  hint: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 17,
  },
  code: {
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
  },
  fieldLabel: {
    marginTop: 4,
    color: palette.textMuted,
    fontFamily: type.section.fontFamily,
    fontSize: 11,
    lineHeight: 14,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    minHeight: 34,
    justifyContent: 'center',
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surface,
  },
  chipActive: {
    borderColor: palette.data,
    backgroundColor: palette.dataFill,
  },
  chipText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 13,
    lineHeight: 16,
    fontWeight: '500',
  },
  chipTextActive: {
    color: palette.text,
  },
  composerHint: {
    color: palette.textFaint,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  editorHeader: {
    marginTop: 6,
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
  },
  stats: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 16,
    fontVariant: ['tabular-nums'],
  },
  editor: {
    minHeight: 360,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.background,
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 12,
    lineHeight: 18,
  },
  fixtureEditor: {
    minHeight: 140,
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 10,
  },
  button: {
    minHeight: TOUCH_TARGET,
    minWidth: 104,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 18,
    borderRadius: 8,
    borderWidth: 1,
  },
  buttonSecondary: {
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surface,
  },
  buttonPrimary: {
    borderColor: palette.data,
    backgroundColor: palette.data,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: palette.text,
    fontFamily: type.sans.fontFamily,
    fontSize: 14,
    lineHeight: 18,
    fontWeight: '600',
  },
  buttonTextPrimary: {
    color: palette.background,
  },
  pressed: {
    opacity: 0.8,
  },
  stale: {
    color: palette.playhead,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  publishStatus: {
    gap: 6,
    padding: 10,
    borderRadius: 8,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairline,
  },
  publishStatusText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  publishOk: {
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 12,
    lineHeight: 17,
  },
  publishFailure: {
    color: palette.sound,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 17,
    fontWeight: '600',
  },
  fixtureHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  fixtureHeaderText: {
    flex: 1,
    gap: 4,
  },
  fixtureToggle: {
    color: palette.textMuted,
    fontFamily: type.mono.fontFamily,
    fontSize: 20,
    lineHeight: 24,
  },
  resultHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    flexWrap: 'wrap',
  },
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 4,
  },
  badgePass: {
    backgroundColor: palette.dataFill,
  },
  badgeFail: {
    backgroundColor: palette.soundSoft,
  },
  badgeText: {
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '700',
    letterSpacing: 1,
  },
  badgeTextPass: {
    color: palette.data,
  },
  badgeTextFail: {
    color: palette.sound,
  },
  actionLabel: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  failureTitle: {
    color: palette.sound,
    fontFamily: type.sans.fontFamily,
    fontSize: 14,
    lineHeight: 20,
    fontWeight: '600',
  },
  errorList: {
    gap: 8,
  },
  errorRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    padding: 8,
    borderRadius: 6,
    backgroundColor: palette.surface,
    borderLeftWidth: 2,
    borderLeftColor: palette.sound,
  },
  errorPath: {
    color: palette.playhead,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  errorMessage: {
    flex: 1,
    minWidth: 160,
    color: palette.text,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 16,
  },
  filledBox: {
    padding: 12,
    borderRadius: 8,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairline,
  },
  emptyBox: {
    marginTop: 6,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: palette.hairlineStrong,
  },
  successText: {
    color: palette.data,
    fontFamily: type.sans.fontFamily,
    fontSize: 13,
    lineHeight: 18,
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 24,
  },
  loadingText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 13,
  },
  hashRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    gap: 12,
    padding: 10,
    borderRadius: 8,
    backgroundColor: palette.surface,
    flexWrap: 'wrap',
  },
  hash: {
    flex: 1,
    minWidth: 160,
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 12,
    lineHeight: 18,
  },
  audioPanel: {
    gap: 8,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
  },
  audioRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 10,
  },
  audioText: {
    flex: 1,
    minWidth: 160,
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  publishedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  refreshButton: {
    minHeight: 34,
    justifyContent: 'center',
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surface,
  },
  refreshText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 16,
    fontWeight: '600',
  },
  publishedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 10,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
  },
  publishedRowMain: {
    flex: 1,
    minWidth: 150,
    gap: 2,
  },
  publishedTitle: {
    color: palette.text,
    fontFamily: type.sans.fontFamily,
    fontSize: 13,
    lineHeight: 18,
    fontWeight: '600',
  },
  publishedId: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  publishedRight: {
    alignItems: 'flex-end',
    gap: 2,
  },
  publishedVersion: {
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '700',
  },
  publishedTime: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  block: {
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
    paddingTop: 10,
    gap: 6,
  },
  blockHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  blockLabel: {
    color: palette.textFaint,
  },
  blockCount: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  codeBlock: {
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 17,
    padding: 10,
    borderRadius: 6,
    backgroundColor: palette.background,
  },
  empty: {
    color: palette.textFaint,
    fontFamily: type.sans.fontFamily,
    fontSize: 12,
    lineHeight: 17,
  },
  endpoints: {
    gap: 4,
    paddingHorizontal: 2,
  },
  endpointLabel: {
    color: palette.textFaint,
    fontFamily: type.section.fontFamily,
    fontSize: 10,
    lineHeight: 14,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  endpoint: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 15,
  },
});
