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
import { palette } from '../musicalize/palette';
import { type } from '../musicalize/type';
import {
  fetchFigureAudioJob,
  fetchFigureRenderAudio,
  fetchSentenceExamples,
  renderFigurePiece,
  requestMusicXmlSentenceDraft,
} from './api';
import { nextJobPollDelayMs } from './protocol';
import {
  DEFAULT_FIGURE_RENDER_MOVEMENT_INDEX,
  DEMO_SERIES_LABEL,
  FIGURE_RENDER_FORM_SPANS,
  FIGURE_RENDER_PLANS,
  FIGURE_TAGS,
  VILLA_COMPOSER,
  VILLA_RENDERER,
  VILLA_RENDERER_LABEL,
  appendPatternFigure,
  appendPatternSentence,
  buildFigureRenderRequest,
  composerOptions,
  createPatternDraft,
  demoSeries,
  existingTemplateOptions,
  figureAudioStatusLabel,
  figureRenderDraftKey,
  genericPatternOptions,
  isGenericPatternId,
  missingFigureTags,
  newPatternId,
  newPatternLabel,
  patternDraftComplete,
  patternDraftFigures,
  patternDraftJson,
  patternDraftLabel,
  patternFigureFromTextureSpec,
  removeFigureTag,
  removePatternFigure,
  removePatternSentence,
  sentenceDraftSourceLabel,
  setFigureTag,
  villaMeterSupported,
  villaTemplateOptions,
  type FigureRenderAudio,
  type FigureRenderFormSpan,
  type FigureRenderPlanId,
  type FigureRenderResponse,
  type FigureTag,
  type MusicXmlSentenceDraftRequest,
  type PatternDraft,
  type PatternDraftMeta,
  type PatternDraftSentence,
  type SentenceDraftMode,
  type SentenceDraftResponse,
  type SentenceTemplateOption,
} from './sentenceDraft';
import {
  SAMPLES,
  describeRequestFailure,
  examplesToSamples,
  valueLines,
  type StudioSample,
} from './spec';
import type { PassageRange } from './musicxml';

/** Existing generic patterns are Torroba/Sor; the MVP new pattern is Villa. */
const EXISTING_PATTERN_RENDERER = 'torroba_sor';

/** Compact labels for the five Studio role tags. */
const FIGURE_TAG_LABEL: Record<FigureTag, string> = {
  key: 'Key',
  'intro.short': 'Intro 2',
  'intro.long': 'Intro 4',
  'outro.short': 'Outro 2',
  'outro.long': 'Outro 4',
};

type Props = {
  importId: string;
  /** 1-based inclusive bars + quarter-note beats, same shape as the passage. */
  range: PassageRange;
  rangeLabel: string;
  /** Passage meter, read-only in the form. */
  meter: string;
  selectionValid: boolean;
  voices: number[];
};

type ErrorLine = { text: string } | null;

function firstErrorLine(
  errors: ReadonlyArray<{ path: string; message: string }>,
  fallback: string,
): string {
  const first = errors[0];
  if (!first) return fallback;
  const path = first.path && first.path !== '$' ? `${first.path}: ` : '';
  return `${path}${first.message}`;
}

function specText(value: unknown): string | null {
  if (typeof value !== 'string' || !value.trim()) return null;
  return value.trim();
}

function sentenceId(sentence: PatternDraftSentence): string {
  return specText(sentence.spec.id) ?? 'sentence';
}

function sentenceLetter(index: number): string {
  return String.fromCharCode(65 + (index % 26));
}

export function SentenceDraftPanel({
  importId,
  range,
  rangeLabel,
  meter,
  selectionValid,
  voices,
}: Props) {
  const [samples, setSamples] = useState<readonly StudioSample[]>(SAMPLES);
  const [mode, setMode] = useState<SentenceDraftMode>('existing');
  const [pattern, setPattern] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [newName, setNewName] = useState('');
  const [newComposer, setNewComposer] = useState(VILLA_COMPOSER);
  const [composerMode, setComposerMode] = useState<'existing' | 'new'>('existing');
  const [draft, setDraft] = useState<PatternDraft | null>(null);
  const [result, setResult] = useState<SentenceDraftResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorLine>(null);
  const [note, setNote] = useState<string | null>(null);
  const [warningsOpen, setWarningsOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [playingUrl, setPlayingUrl] = useState<string | null>(null);
  const [exportText, setExportText] = useState<string | null>(null);

  const draftController = useRef<AbortController | null>(null);
  const examplesController = useRef<AbortController | null>(null);
  const player = useRef<HTMLAudioElement | null>(null);

  const stopAudio = useCallback(() => {
    const current = player.current;
    player.current = null;
    if (current) current.pause();
    setPlayingUrl(null);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    examplesController.current = controller;
    void fetchSentenceExamples(controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        const next = examplesToSamples(response.examples);
        if (next.length) setSamples(next);
      })
      .catch(() => {
        // Embedded SAMPLES keep the pickers usable when examples are offline.
      })
      .finally(() => {
        if (examplesController.current === controller) {
          examplesController.current = null;
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(
    () => () => {
      draftController.current?.abort();
      examplesController.current?.abort();
      const current = player.current;
      player.current = null;
      if (current) current.pause();
    },
    [],
  );

  const patternOptions = useMemo(() => genericPatternOptions(samples), [samples]);
  useEffect(() => {
    if (patternOptions.length === 0) return;
    setPattern((current) =>
      patternOptions.some((option) => option.id === current)
        ? current
        : patternOptions[0].id,
    );
  }, [patternOptions]);

  const selectedPattern = patternOptions.find((option) => option.id === pattern);
  const existingTemplates = useMemo(
    () => existingTemplateOptions(samples, pattern, meter),
    [samples, pattern, meter],
  );
  const villaTemplates = useMemo(
    () => villaTemplateOptions(samples, meter),
    [samples, meter],
  );
  const templates: SentenceTemplateOption[] =
    mode === 'new' ? villaTemplates : existingTemplates;
  const templateValue = templateId || '';

  useEffect(() => {
    setTemplateId((current) =>
      current && !templates.some((option) => option.id === current) ? '' : current,
    );
  }, [templates]);

  // Any form or passage change invalidates the last preview. Nothing here
  // writes into the SentenceSpec editor.
  useEffect(() => {
    draftController.current?.abort();
    draftController.current = null;
    setBusy(false);
    setResult(null);
    setError(null);
    setWarningsOpen(false);
  }, [
    importId,
    meter,
    voices,
    mode,
    pattern,
    templateId,
    newName,
    newComposer,
    range.barStart,
    range.beatStart,
    range.barEnd,
    range.beatEnd,
  ]);

  // A different import is a different piece; never mix its sentences into the
  // pattern draft built from the previous score.
  useEffect(() => {
    setDraft(null);
    setNote(null);
  }, [importId]);

  const nextId = newPatternId(newName);
  const nextLabel = newPatternLabel(newName, nextId);
  const composers = composerOptions();
  const composer =
    composerMode === 'new'
      ? specText(newComposer) ?? ''
      : specText(newComposer) ?? VILLA_COMPOSER;
  const newMeterSupported = villaMeterSupported(meter);
  const formReady =
    importId.length > 0 &&
    selectionValid &&
    meter.length > 0 &&
    (mode === 'existing'
      ? Boolean(pattern) && isGenericPatternId(pattern)
      : Boolean(nextId) && newMeterSupported && composer.length > 0);
  const canPreview = formReady && !busy;

  const preview = useCallback(async () => {
    if (!canPreview) return;
    draftController.current?.abort();
    const controller = new AbortController();
    draftController.current = controller;
    stopAudio();
    setBusy(true);
    setError(null);
    setNote(null);
    setResult(null);
    setAdvancedOpen(false);
    try {
      const request: MusicXmlSentenceDraftRequest = {
        barStart: range.barStart,
        beatStart: range.beatStart,
        barEnd: range.barEnd,
        beatEnd: range.beatEnd,
        mode,
        ...(voices.length ? { voices } : {}),
        ...(mode === 'existing'
          ? { pattern, templateId: templateValue }
          : {
              newPattern: {
                id: nextId,
                label: nextLabel,
                composer,
                renderer: VILLA_RENDERER,
                meter,
                templateId: templateValue,
              },
            }),
      };
      const data = await requestMusicXmlSentenceDraft(
        importId,
        request,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setResult(data);
      if (!data.ok) {
        setError({
          text: firstErrorLine(data.errors, 'The sentence draft was rejected.'),
        });
      } else if (!data.spec) {
        setError({ text: 'The sentence draft returned no spec.' });
      }
    } catch (failure) {
      if (controller.signal.aborted) return;
      setError({ text: describeRequestFailure(failure) });
    } finally {
      if (draftController.current === controller) {
        draftController.current = null;
        setBusy(false);
      }
    }
  }, [
    canPreview,
    composer,
    importId,
    meter,
    mode,
    nextId,
    nextLabel,
    pattern,
    range.barEnd,
    range.barStart,
    range.beatEnd,
    range.beatStart,
    stopAudio,
    templateValue,
    voices,
  ]);

  const addSentence = useCallback(() => {
    if (!result?.ok || !result.spec) return;
    const sentence: PatternDraftSentence = {
      spec: result.spec,
      fixture: result.fixture,
      rangeLabel,
      audioUrl: result.preview?.audioUrl ?? null,
      durationSec: result.preview?.durationSec ?? 0,
      renderHash: result.preview?.renderHash ?? null,
    };

    if (!draft) {
      const meta: PatternDraftMeta =
        mode === 'new'
          ? {
              id: nextId,
              label: nextLabel,
              composer,
              renderer: VILLA_RENDERER,
              meter,
            }
          : {
              id: pattern,
              label: selectedPattern?.label ?? pattern,
              composer: selectedPattern?.composer ?? '',
              renderer: EXISTING_PATTERN_RENDERER,
              meter,
            };
      setDraft(createPatternDraft(meta, sentence));
      setResult(null);
      setError(null);
      setNote(`Added ${sentenceId(sentence)} to pattern ${meta.id}.`);
      return;
    }

    if (draft.id !== (mode === 'new' ? nextId : pattern)) {
      setError({
        text: `Draft already holds ${draft.id}; export or clear it before starting another pattern.`,
      });
      return;
    }
    if (draft.meter !== meter) {
      setError({
        text: `Draft is ${draft.meter}; preview a passage in ${draft.meter} or clear the draft.`,
      });
      return;
    }

    const appended = appendPatternSentence(draft, sentence);
    if (!appended.ok) {
      setError({ text: appended.error });
      return;
    }
    setDraft(appended.draft);
    setResult(null);
    setError(null);
    setNote(`Added ${sentenceId(sentence)}.`);
  }, [
    composer,
    draft,
    meter,
    mode,
    nextId,
    nextLabel,
    pattern,
    rangeLabel,
    result,
    selectedPattern,
  ]);

  const togglePlay = useCallback(
    async (url: string | null | undefined) => {
      if (!url) return;
      if (Platform.OS !== 'web' || typeof Audio === 'undefined') {
        setError({ text: 'Sentence audio playback is web-only in this pass.' });
        return;
      }
      if (player.current && playingUrl === url) {
        stopAudio();
        return;
      }
      stopAudio();
      setError(null);
      const next = new Audio(url);
      player.current = next;
      setPlayingUrl(url);
      next.onended = () => {
        if (player.current !== next) return;
        player.current = null;
        setPlayingUrl(null);
      };
      next.onerror = () => {
        if (player.current !== next) return;
        player.current = null;
        setPlayingUrl(null);
        setError({ text: 'The browser could not play the sentence WAV.' });
      };
      try {
        await next.play();
      } catch (failure) {
        next.pause();
        if (player.current === next) player.current = null;
        setPlayingUrl(null);
        setError({ text: describeRequestFailure(failure) });
      }
    },
    [playingUrl, stopAudio],
  );

  const exportBundle = useCallback(() => {
    if (
      !draft ||
      (draft.sentences.length === 0 && patternDraftFigures(draft).length === 0)
    ) {
      return;
    }
    const text = patternDraftJson(draft);
    if (
      Platform.OS === 'web' &&
      typeof document !== 'undefined' &&
      typeof Blob !== 'undefined' &&
      typeof URL !== 'undefined' &&
      typeof URL.createObjectURL === 'function'
    ) {
      const blob = new Blob([text], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'pattern.json';
      anchor.rel = 'noopener';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setExportText(null);
      setNote('Exported pattern.json.');
      return;
    }
    setExportText(text);
    setNote('Select and copy the JSON bundle below.');
  }, [draft]);

  const clearDraft = useCallback(() => {
    setDraft(null);
    setExportText(null);
    setNote('Pattern draft cleared.');
    setError(null);
    setAdvancedOpen(false);
    stopAudio();
  }, [stopAudio]);

  const removeSentence = useCallback(
    (index: number) => {
      const sentence = draft?.sentences[index];
      if (sentence?.audioUrl && sentence.audioUrl === playingUrl) stopAudio();
      setDraft((current) =>
        current ? removePatternSentence(current, index) : current,
      );
      setExportText(null);
      setNote(null);
    },
    [draft, playingUrl, stopAudio],
  );

  const addFigure = useCallback(() => {
    if (!result?.ok || !result.spec || mode !== 'new') return;
    const used = new Set(
      (draft ? patternDraftFigures(draft) : []).flatMap((figure) => [
        figure.id,
        figure.cellId,
      ]),
    );
    const base = specText(result.spec.id) || 'figure';
    let id = base;
    let suffix = 2;
    while (used.has(id)) id = `${base}_${suffix++}`;
    const figure = patternFigureFromTextureSpec(result.spec, { id });
    if (!figure) {
      setError({ text: 'This passage has no bars to save as a figure.' });
      return;
    }

    if (!draft) {
      const meta: PatternDraftMeta = {
        id: nextId,
        label: nextLabel,
        composer,
        renderer: VILLA_RENDERER,
        meter,
      };
      setDraft({ ...createPatternDraft(meta), figures: [figure] });
      setResult(null);
      setError(null);
      setNote(`Added figure ${figure.id} (${figure.bars} bars).`);
      return;
    }
    if (draft.id !== nextId) {
      setError({
        text: `Draft already holds ${draft.id}; export or clear it before starting another pattern.`,
      });
      return;
    }
    if (draft.meter !== meter) {
      setError({
        text: `Draft is ${draft.meter}; preview a passage in ${draft.meter} or clear the draft.`,
      });
      return;
    }
    const appended = appendPatternFigure(draft, figure);
    if (!appended.ok) {
      setError({ text: appended.error });
      return;
    }
    setDraft(appended.draft);
    setResult(null);
    setError(null);
    setNote(`Added figure ${figure.id} (${figure.bars} bars).`);
  }, [
    composer,
    draft,
    meter,
    mode,
    nextId,
    nextLabel,
    result,
  ]);

  const tagFigure = useCallback(
    (figureId: string, tag: FigureTag) => {
      if (!draft) return;
      const figure = patternDraftFigures(draft).find((item) => item.id === figureId);
      if (!figure) return;
      setExportText(null);
      setNote(null);
      if (figure.tags.includes(tag)) {
        setDraft(removeFigureTag(draft, figureId, tag));
        setError(null);
        return;
      }
      const tagged = setFigureTag(draft, figureId, tag);
      if (!tagged.ok) {
        setError({ text: tagged.error });
        return;
      }
      setDraft(tagged.draft);
      setError(null);
    },
    [draft],
  );

  const removeFigure = useCallback(
    (figureId: string) => {
      if (!draft) return;
      setDraft(removePatternFigure(draft, figureId));
      setExportText(null);
      setNote(null);
      setError(null);
    },
    [draft],
  );

  const advancedJson = useMemo(() => {
    if (draft) return patternDraftJson(draft);
    if (result?.spec) return JSON.stringify(result.spec, null, 2);
    return '';
  }, [draft, result]);

  const warnings = result?.warnings ?? [];
  const resultTemplate = sentenceDraftSourceLabel(
    templateValue,
    result?.rhythmTemplate ?? false,
  );
  const resultPattern =
    specText(result?.spec?.pattern) ??
    (mode === 'new' ? nextId : pattern) ??
    '—';
  const resultMeter = specText(result?.spec?.meter) ?? meter ?? '—';
  const resultNotes = result?.preview?.notes ?? 0;
  const canPlayResult =
    Platform.OS === 'web' && Boolean(result?.preview?.audioUrl);
  const draftFigures = draft ? patternDraftFigures(draft) : [];
  const missingTags = draft ? missingFigureTags(draft) : [];
  const draftComplete = draft ? patternDraftComplete(draft) : false;
  const canAddFigure = mode === 'new' && Boolean(result?.ok && result.spec);

  return (
    <View style={styles.box}>
      <View style={styles.headerRow}>
        <Text style={[type.section, styles.blockLabel]}>3 · Create sentence</Text>
        <Text style={styles.stepMeta}>PASSAGE → PATTERN</Text>
      </View>
      <Text style={styles.hint}>
        Draft one sentence from {rangeLabel}. Nothing is published and the
        SentenceSpec editor is not changed.
      </Text>

      <View style={styles.modeRow}>
        <ModeButton
          label="Existing pattern"
          active={mode === 'existing'}
          onPress={() => {
            setMode('existing');
            setTemplateId('');
          }}
        />
        <ModeButton
          label="New pattern"
          active={mode === 'new'}
          onPress={() => {
            setMode('new');
            setTemplateId('');
          }}
        />
      </View>

      {mode === 'existing' ? (
        <>
          <View style={styles.fieldGroup}>
            <Text style={styles.inputLabel}>Pattern</Text>
            {patternOptions.length ? (
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.chipRow}
              >
                {patternOptions.map((option) => (
                  <Chip
                    key={`pattern:${option.id}`}
                    label={option.label}
                    active={pattern === option.id}
                    onPress={() => {
                      setPattern(option.id);
                      setTemplateId('');
                    }}
                    accessibilityLabel={`Use pattern ${option.label}`}
                  />
                ))}
              </ScrollView>
            ) : (
              <Text style={styles.hint}>No generic patterns reported.</Text>
            )}
            <Text style={styles.fieldMeta}>
              Production patterns only; suite and preview families are hidden.
            </Text>
          </View>

          <TemplatePicker
            templates={existingTemplates}
            value={templateValue}
            onSelect={setTemplateId}
            hint="Auto picks the closest template; choose one to override."
          />
        </>
      ) : (
        <>
          <View style={styles.newGrid}>
            <View style={styles.nameField}>
              <Text style={styles.inputLabel}>Name</Text>
              <TextInput
                value={newName}
                onChangeText={setNewName}
                placeholder="Mazurka-Choro"
                placeholderTextColor={palette.textFaint}
                style={styles.input}
                accessibilityLabel="New pattern name"
              />
            </View>
            <View style={styles.composerField}>
              <Text style={styles.inputLabel}>Composer</Text>
              <ComposerPicker
                value={newComposer}
                mode={composerMode}
                options={composers}
                onSelect={(value) => {
                  setComposerMode('existing');
                  setNewComposer(value);
                }}
                onNew={() => {
                  setComposerMode('new');
                  setNewComposer('');
                }}
              />
              {composerMode === 'new' ? (
                <TextInput
                  value={newComposer}
                  onChangeText={setNewComposer}
                  placeholder="Composer name"
                  placeholderTextColor={palette.textFaint}
                  style={styles.input}
                  accessibilityLabel="New composer name"
                />
              ) : null}
            </View>
          </View>
          <View style={styles.metaRow}>
            <Text style={styles.fieldMeta}>
              id · {nextId || 'type a name'}
            </Text>
            <Text style={styles.fieldMeta}>
              {VILLA_RENDERER_LABEL} · meter {meter || '—'} (from passage)
            </Text>
          </View>
          {!newMeterSupported ? (
            <Text style={styles.warnText}>
              Villa preview supports 2/4, 3/4 and 4/4; choose a passage in one
              of those meters.
            </Text>
          ) : null}
          <Text style={styles.fieldMeta}>
            Source rhythm is used: the preview follows this passage's notes and
            durations, not a template.
          </Text>
        </>
      )}

      <View style={styles.actionRow}>
        <ActionButton
          label="Preview sentence"
          primary={!result?.ok && (draft?.sentences.length ?? 0) === 0}
          onPress={() => void preview()}
          disabled={!canPreview}
          busy={busy}
          busyLabel="Drafting…"
        />
      </View>
      {error ? (
        <Text
          selectable
          numberOfLines={1}
          accessibilityLabel={error.text}
          style={styles.errorLine}
        >
          {error.text}
        </Text>
      ) : null}
      {note ? <Text style={styles.noteLine}>{note}</Text> : null}

      {result?.ok && result.spec ? (
        <View style={styles.resultBox}>
          <View style={styles.resultHeader}>
            <Text style={styles.resultTitle}>
              {resultPattern} · {resultMeter}
            </Text>
            <Text style={styles.resultBadge}>
              {result.productionReady ? 'PRODUCTION OK' : 'PREVIEW ONLY'}
            </Text>
          </View>
          <Text style={styles.resultMeta} numberOfLines={2}>
            {resultTemplate} · bars {range.barStart}–{range.barEnd} ·{' '}
            {resultNotes} note{resultNotes === 1 ? '' : 's'}
            {result.preview?.durationSec
              ? ` · ${result.preview.durationSec.toFixed(2)} s`
              : ''}
          </Text>
          {result.rhythmTemplate ? (
            <Text style={styles.fieldMeta}>
              Preview follows the passage rhythm; preview/export only.
            </Text>
          ) : null}
          {warnings.length ? (
            <Pressable
              onPress={() => setWarningsOpen((open) => !open)}
              accessibilityRole="button"
              accessibilityState={{ expanded: warningsOpen }}
              style={({ pressed }) => [
                styles.warningToggle,
                pressed ? styles.pressed : null,
              ]}
            >
              <Text style={styles.warningToggleText}>
                {warnings.length} warning{warnings.length === 1 ? '' : 's'}{' '}
                {warningsOpen ? '▾' : '▸'}
              </Text>
            </Pressable>
          ) : null}
          {warningsOpen
            ? warnings.map((warning, index) => (
                <Text key={`draft-warning:${index}`} style={styles.warnText}>
                  {warning}
                </Text>
              ))
            : null}
          {result.errors.length ? (
            <Text selectable numberOfLines={1} style={styles.errorLine}>
              {firstErrorLine(result.errors, 'The sentence draft was rejected.')}
            </Text>
          ) : null}
          <View style={styles.actionRow}>
            {canPlayResult ? (
              <ActionButton
                label={
                  playingUrl === result.preview?.audioUrl ? 'Stop' : 'Play sentence'
                }
                onPress={() => void togglePlay(result.preview?.audioUrl)}
              />
            ) : null}
            {canAddFigure ? (
              <ActionButton label="Add to figures" onPress={addFigure} />
            ) : null}
            <ActionButton label="Add sentence" primary onPress={addSentence} />
          </View>
        </View>
      ) : null}

      <View style={styles.draftBox}>
        <View style={styles.headerRow}>
          <Text style={[type.section, styles.blockLabel]}>
            4 · Pattern draft
          </Text>
          {draft ? (
            <Pressable
              onPress={clearDraft}
              accessibilityRole="button"
              accessibilityLabel="Clear pattern draft"
              style={({ pressed }) => [
                styles.smallButton,
                pressed ? styles.pressed : null,
              ]}
            >
              <Text style={styles.smallButtonText}>Clear</Text>
            </Pressable>
          ) : null}
        </View>
        {draft ? (
          <>
            <Text style={styles.draftTitle}>{patternDraftLabel(draft)}</Text>
            <Text style={styles.fieldMeta} numberOfLines={1}>
              {draft.label || draft.id} · {draft.composer || 'composer unknown'} ·{' '}
              {draft.renderer || 'preview'}
            </Text>
            {draft.sentences.map((sentence, index) => (
              <View key={`draft-sentence:${index}`} style={styles.sentenceRow}>
                <Text style={styles.sentenceLetter}>{sentenceLetter(index)}</Text>
                <View style={styles.sentenceBody}>
                  <Text style={styles.sentenceRange} numberOfLines={1}>
                    {sentence.rangeLabel ?? 'passage'}
                  </Text>
                  <Text style={styles.sentenceId} numberOfLines={1}>
                    {sentenceId(sentence)}
                  </Text>
                </View>
                {Platform.OS === 'web' && sentence.audioUrl ? (
                  <Pressable
                    onPress={() => void togglePlay(sentence.audioUrl)}
                    accessibilityRole="button"
                    accessibilityLabel={`Play sentence ${sentenceLetter(index)}`}
                    style={({ pressed }) => [
                      styles.smallButton,
                      pressed ? styles.pressed : null,
                    ]}
                  >
                    <Text style={styles.smallButtonText}>
                      {playingUrl === sentence.audioUrl ? 'Stop' : 'Play'}
                    </Text>
                  </Pressable>
                ) : null}
                <Pressable
                  onPress={() => removeSentence(index)}
                  accessibilityRole="button"
                  accessibilityLabel={`Remove sentence ${sentenceLetter(index)}`}
                  style={({ pressed }) => [
                    styles.smallButton,
                    pressed ? styles.pressed : null,
                  ]}
                >
                  <Text style={styles.smallButtonText}>Remove</Text>
                </Pressable>
              </View>
            ))}

            <View style={styles.figureSection}>
              <View style={styles.headerRow}>
                <Text style={styles.inputLabel}>Figures</Text>
                <Text style={styles.fieldMeta}>
                  {draftFigures.length} figure
                  {draftFigures.length === 1 ? '' : 's'} ·{' '}
                  {missingTags.length
                    ? `missing ${missingTags.join(', ')}`
                    : '5/5 tags'}{' '}
                  · {draftComplete ? 'COMPLETE' : 'INCOMPLETE'}
                </Text>
              </View>
              {draftFigures.length === 0 ? (
                <Text style={styles.hint}>
                  No figures yet. In a new pattern, preview a passage and use
                  “Add to figures”; then tag it key / intro / outro.
                </Text>
              ) : (
                draftFigures.map((figure) => (
                  <View key={`draft-figure:${figure.id}`} style={styles.figureRow}>
                    <View style={styles.figureBody}>
                      <Text style={styles.figureTitle} numberOfLines={1}>
                        {figure.id} · {figure.bars} bar
                        {figure.bars === 1 ? '' : 's'}
                      </Text>
                      <Text style={styles.figureMeta} numberOfLines={1}>
                        cell {figure.cellId}
                        {figure.previewMode ? ` · ${figure.previewMode}` : ''}
                      </Text>
                      <ScrollView
                        horizontal
                        showsHorizontalScrollIndicator={false}
                        contentContainerStyle={styles.chipRow}
                      >
                        {FIGURE_TAGS.map((tag) => {
                          const active = figure.tags.includes(tag);
                          return (
                            <Chip
                              key={`figure-tag:${figure.id}:${tag}`}
                              label={FIGURE_TAG_LABEL[tag]}
                              active={active}
                              onPress={() => tagFigure(figure.id, tag)}
                              accessibilityLabel={`${
                                active ? 'Remove' : 'Set'
                              } ${tag} on figure ${figure.id}`}
                            />
                          );
                        })}
                      </ScrollView>
                    </View>
                    <Pressable
                      onPress={() => removeFigure(figure.id)}
                      accessibilityRole="button"
                      accessibilityLabel={`Remove figure ${figure.id}`}
                      style={({ pressed }) => [
                        styles.smallButton,
                        pressed ? styles.pressed : null,
                      ]}
                    >
                      <Text style={styles.smallButtonText}>Remove</Text>
                    </Pressable>
                  </View>
                ))
              )}
              <Text style={styles.fieldMeta}>
                Tagging never edits the SentenceSpec editor and never
                publishes. The key tag derives the body sentence at promote.
              </Text>
            </View>

            {draftComplete ? <RenderPieceSection draft={draft} /> : null}

            <View style={styles.actionRow}>
              <ActionButton
                label="Export bundle"
                primary={
                  !result?.ok &&
                  (draft.sentences.length > 0 || draftFigures.length > 0)
                }
                onPress={exportBundle}
                disabled={draft.sentences.length === 0 && draftFigures.length === 0}
              />
            </View>
            {exportText ? (
              <ScrollView
                style={styles.jsonScroll}
                nestedScrollEnabled
                keyboardShouldPersistTaps="handled"
              >
                <Text selectable style={styles.jsonText}>
                  {exportText}
                </Text>
              </ScrollView>
            ) : null}
          </>
        ) : (
          <Text style={styles.hint}>
            Preview a sentence, then Add sentence. Add another from a new
            passage to build a multi-sentence pattern.
          </Text>
        )}
      </View>

      <Pressable
        onPress={() => setAdvancedOpen((open) => !open)}
        accessibilityRole="button"
        accessibilityState={{ expanded: advancedOpen }}
        style={({ pressed }) => [
          styles.advancedToggle,
          pressed ? styles.pressed : null,
        ]}
      >
        <Text style={styles.advancedText}>
          Advanced {advancedOpen ? '▾' : '▸'}
        </Text>
      </Pressable>
      {advancedOpen ? (
        advancedJson ? (
          <ScrollView style={styles.jsonScroll} nestedScrollEnabled>
            <Text selectable style={styles.jsonText}>
              {valueLines(advancedJson, 160).join('\n')}
            </Text>
          </ScrollView>
        ) : (
          <Text style={styles.hint}>No draft JSON yet.</Text>
        )
      ) : null}
    </View>
  );
}

/* ------------------------------------------------------------------------- *
 * Render Piece (Phase D)
 * ------------------------------------------------------------------------- */

const MAX_RENDER_AUDIO_POLLS = 160;

function shortRenderHash(hash: string | null): string {
  if (!hash) return '—';
  return hash.replace(/^sha256:/i, '').slice(0, 10);
}

function waitForRenderPoll(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new Error('aborted'));
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(new Error('aborted'));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', onAbort);
      resolve();
    }, Math.max(0, ms));
    signal.addEventListener('abort', onAbort, { once: true });
  });
}

function downloadUrl(url: string, filename: string): boolean {
  if (
    Platform.OS === 'web' &&
    typeof document !== 'undefined' &&
    typeof URL !== 'undefined'
  ) {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.rel = 'noopener';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    return true;
  }
  return false;
}

/**
 * Render/Play/Export for a complete figure pool. Owns its own plan/form and
 * render state so the parent's sentence preview state cannot be disturbed.
 * Changing the draft, plan or form invalidates the render and any audio job.
 */
function RenderPieceSection({ draft }: { draft: PatternDraft }) {
  const [plan, setPlan] = useState<FigureRenderPlanId>('auto_aaba');
  const [span, setSpan] = useState<FigureRenderFormSpan>('1W');
  const [movementIndex, setMovementIndex] = useState(
    DEFAULT_FIGURE_RENDER_MOVEMENT_INDEX,
  );
  const [render, setRender] = useState<FigureRenderResponse | null>(null);
  const [audio, setAudio] = useState<FigureRenderAudio | null>(null);
  const [renderBusy, setRenderBusy] = useState(false);
  const [audioBusy, setAudioBusy] = useState(false);
  const [error, setError] = useState<ErrorLine>(null);
  const [note, setNote] = useState<string | null>(null);
  const [playingUrl, setPlayingUrl] = useState<string | null>(null);

  const renderController = useRef<AbortController | null>(null);
  const audioController = useRef<AbortController | null>(null);
  const audioPlayer = useRef<HTMLAudioElement | null>(null);
  const audioRun = useRef(0);

  const draftKey = useMemo(() => figureRenderDraftKey(draft), [draft]);
  // 1M movements need 104–108 source bars; the demo series pads to 128.
  const series = useMemo(() => demoSeries(span === '1M' ? 128 : 64), [span]);

  const stopAudio = useCallback(() => {
    const current = audioPlayer.current;
    audioPlayer.current = null;
    if (current) current.pause();
    setPlayingUrl(null);
  }, []);

  // Any input change invalidates a render/audio pair; never keep a stale WAV.
  useEffect(() => {
    renderController.current?.abort();
    audioController.current?.abort();
    renderController.current = null;
    audioController.current = null;
    audioRun.current += 1;
    setRender(null);
    setAudio(null);
    setRenderBusy(false);
    setAudioBusy(false);
    setError(null);
    setNote(null);
    stopAudio();
  }, [draftKey, plan, span, movementIndex, stopAudio]);

  useEffect(
    () => () => {
      renderController.current?.abort();
      audioController.current?.abort();
      const current = audioPlayer.current;
      audioPlayer.current = null;
      if (current) current.pause();
    },
    [],
  );

  const toggleAudio = useCallback(
    async (url: string | null | undefined) => {
      if (!url) return;
      if (Platform.OS !== 'web' || typeof Audio === 'undefined') {
        setError({ text: 'Render audio playback is web-only in this pass.' });
        return;
      }
      if (audioPlayer.current && playingUrl === url) {
        stopAudio();
        return;
      }
      stopAudio();
      setError(null);
      const next = new Audio(url);
      audioPlayer.current = next;
      setPlayingUrl(url);
      next.onended = () => {
        if (audioPlayer.current !== next) return;
        audioPlayer.current = null;
        setPlayingUrl(null);
      };
      next.onerror = () => {
        if (audioPlayer.current !== next) return;
        audioPlayer.current = null;
        setPlayingUrl(null);
        setError({ text: 'The browser could not play the rendered WAV.' });
      };
      try {
        await next.play();
      } catch (failure) {
        next.pause();
        if (audioPlayer.current === next) audioPlayer.current = null;
        setPlayingUrl(null);
        setError({ text: describeRequestFailure(failure) });
      }
    },
    [playingUrl, stopAudio],
  );

  const renderNow = useCallback(async () => {
    const built = buildFigureRenderRequest(draft, plan, series, {
      form: span === '1M' ? { span, movementIndex } : { span },
    });
    if (!built.ok) {
      setError({ text: built.error });
      return;
    }
    renderController.current?.abort();
    audioController.current?.abort();
    audioRun.current += 1;
    const controller = new AbortController();
    renderController.current = controller;
    stopAudio();
    setRenderBusy(true);
    setAudioBusy(false);
    setError(null);
    setNote(null);
    setRender(null);
    setAudio(null);
    try {
      const data = await renderFigurePiece(built.request, controller.signal);
      if (controller.signal.aborted) return;
      setRender(data);
      setAudio(data.ok ? data.audio : null);
      if (!data.ok) {
        setError({
          text: firstErrorLine(data.errors, 'Render Piece was rejected.'),
        });
      } else if (!data.renderHash) {
        setError({ text: 'Render Piece returned no renderHash.' });
      } else {
        setNote(
          `Rendered ${data.bars} bar${data.bars === 1 ? '' : 's'} · ${
            data.notes
          } notes · audio ${data.audio.status}.`,
        );
      }
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError({ text: describeRequestFailure(failure) });
      }
    } finally {
      if (renderController.current === controller) {
        renderController.current = null;
        setRenderBusy(false);
      }
    }
  }, [draft, movementIndex, plan, series, span, stopAudio]);

  const play = useCallback(async () => {
    const renderHash = render?.renderHash;
    if (!renderHash) return;
    if (audio?.status === 'ready' && audio.audioUrl) {
      void toggleAudio(audio.audioUrl);
      return;
    }
    if (audioBusy) return;
    audioController.current?.abort();
    const controller = new AbortController();
    audioController.current = controller;
    const run = audioRun.current + 1;
    audioRun.current = run;
    setAudioBusy(true);
    setError(null);
    setNote(null);
    try {
      let current: FigureRenderAudio | null = audio;
      // A failed or unseen export gets one fresh job; a queued/running job is
      // polled without submitting a duplicate.
      if (!current?.jobId || current.status === 'failed') {
        const accepted = await fetchFigureRenderAudio(renderHash, controller.signal);
        if (run !== audioRun.current) return;
        current = {
          status: accepted.status,
          jobId: accepted.jobId,
          audioUrl: null,
          audioHash: null,
          durationSec: 0,
          errors: [],
          retryAfterSec: null,
        };
        setAudio(current);
      }

      let attempt = 0;
      while (!current.audioUrl && current.status !== 'failed') {
        if (!current.jobId) throw new Error('The audio job has no id to poll.');
        if (attempt >= MAX_RENDER_AUDIO_POLLS) {
          throw new Error('Audio is still rendering. Try Play again in a moment.');
        }
        await waitForRenderPoll(
          nextJobPollDelayMs(attempt, current.retryAfterSec),
          controller.signal,
        );
        if (run !== audioRun.current) return;
        current = await fetchFigureAudioJob(
          renderHash,
          current.jobId,
          controller.signal,
        );
        if (run !== audioRun.current) return;
        setAudio(current);
        attempt += 1;
      }

      if (current.status === 'failed') {
        setError({
          text: firstErrorLine(
            current.errors,
            'The production audio export failed.',
          ),
        });
        return;
      }
      if (current.audioUrl) {
        void toggleAudio(current.audioUrl);
      } else {
        setNote('Audio is ready; use Export WAV.');
      }
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError({ text: describeRequestFailure(failure) });
      }
    } finally {
      if (audioController.current === controller) {
        audioController.current = null;
        setAudioBusy(false);
      }
    }
  }, [audio, audioBusy, render, toggleAudio]);

  const exportFile = useCallback(
    (url: string | null | undefined, filename: string) => {
      if (!url) return;
      if (downloadUrl(url, filename)) {
        setNote(`Downloading ${filename}.`);
        return;
      }
      setNote(url);
    },
    [],
  );

  const hashShort = render?.renderHash ? shortRenderHash(render.renderHash) : '';
  const audioStatus = audio?.status ?? null;
  const canPlay = Boolean(render?.renderHash) && !audioBusy;
  const canExportMusicXml = Boolean(render?.musicxmlUrl);
  const canExportWav =
    audio?.status === 'ready' && Boolean(audio.audioUrl) && !audioBusy;

  return (
    <View style={styles.renderBox}>
      <View style={styles.headerRow}>
        <Text style={[type.section, styles.blockLabel]}>5 · Render piece</Text>
        <Text style={styles.stepMeta}>FIGURES → PIECE → WAV</Text>
      </View>
      <Text style={styles.hint}>
        Render the tagged pool with a plan and a 1D series. Nothing is published;
        the SentenceSpec editor is not changed.
      </Text>

      <View style={styles.fieldGroup}>
        <Text style={styles.inputLabel}>Plan</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
        >
          {FIGURE_RENDER_PLANS.map((option) => (
            <Chip
              key={`render-plan:${option.id}`}
              label={`${option.label} · ${option.roles}`}
              active={plan === option.id}
              onPress={() => setPlan(option.id)}
              accessibilityLabel={`Use render plan ${option.label}`}
            />
          ))}
        </ScrollView>
        <Text style={styles.fieldMeta}>
          {FIGURE_RENDER_PLANS.find((option) => option.id === plan)?.hint ??
            'Select a plan.'}{' '}
          ABAB and Through are not implemented yet.
        </Text>
      </View>

      <View style={styles.fieldGroup}>
        <Text style={styles.inputLabel}>Form</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
        >
          {FIGURE_RENDER_FORM_SPANS.map((option) => (
            <Chip
              key={`render-span:${option}`}
              label={option}
              active={span === option}
              onPress={() => setSpan(option)}
              accessibilityLabel={`Use form ${option}`}
            />
          ))}
        </ScrollView>
        {span === '1M' ? (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chipRow}
          >
            {[0, 1, 2, 3].map((index) => (
              <Chip
                key={`render-movement:${index}`}
                label={`Mvt ${index + 1}`}
                active={movementIndex === index}
                onPress={() => setMovementIndex(index)}
                accessibilityLabel={`Use movement ${index + 1}`}
              />
            ))}
          </ScrollView>
        ) : null}
        <Text style={styles.fieldMeta}>
          {span === '1M'
            ? `Monthly form · movement index ${movementIndex}`
            : 'Weekly form · 32 bars'}
          {' · '}
          {series.length} demo bars, no truncation.
        </Text>
      </View>

      <View style={styles.seriesRow}>
        <Text style={[styles.seriesChip, styles.seriesChipActive]}>
          {DEMO_SERIES_LABEL}
        </Text>
        <Text style={styles.fieldMeta}>
          {series.length} bars · synthetic closes + volume · symbol picker later
        </Text>
      </View>

      <View style={styles.actionRow}>
        <ActionButton
          label="Render piece"
          primary={!render}
          onPress={() => void renderNow()}
          disabled={renderBusy}
          busy={renderBusy}
          busyLabel="Rendering…"
        />
        <ActionButton
          label={playingUrl ? 'Stop' : 'Play'}
          onPress={() => void play()}
          disabled={!canPlay}
          busy={audioBusy}
          busyLabel="Preparing audio…"
        />
        <ActionButton
          label="Export MusicXML"
          onPress={() =>
            exportFile(render?.musicxmlUrl, `studio-piece-${hashShort}.musicxml`)
          }
          disabled={!canExportMusicXml}
        />
        <ActionButton
          label="Export WAV"
          onPress={() =>
            exportFile(
              audio?.audioUrl,
              `studio-piece-${shortRenderHash(
                audio?.audioHash ?? render?.renderHash ?? null,
              )}.wav`,
            )
          }
          disabled={!canExportWav}
        />
      </View>

      {error ? (
        <Text
          selectable
          numberOfLines={2}
          accessibilityLabel={error.text}
          style={styles.errorLine}
        >
          {error.text}
        </Text>
      ) : null}
      {note ? <Text style={styles.noteLine}>{note}</Text> : null}

      {render ? (
        <View style={styles.renderResultBox}>
          <View style={styles.resultHeader}>
            <Text style={styles.resultTitle}>
              {render.plan ?? plan} · {render.meter ?? draft.meter}
            </Text>
            <Text style={styles.resultBadge}>
              {render.ok ? 'RENDERED' : 'REJECTED'}
            </Text>
          </View>
          <Text style={styles.resultMeta} numberOfLines={2}>
            hash {shortRenderHash(render.renderHash)} · {render.bars} bar
            {render.bars === 1 ? '' : 's'} · {render.notes} note
            {render.notes === 1 ? '' : 's'}
            {audio?.durationSec ? ` · ${audio.durationSec.toFixed(2)} s` : ''}
          </Text>
          <Text style={styles.renderStatusText}>
            {audioStatus
              ? figureAudioStatusLabel(audioStatus, audio?.durationSec ?? 0)
              : 'No audio job yet.'}
          </Text>
          {audio?.status === 'failed' && audio.errors.length ? (
            <Text selectable numberOfLines={2} style={styles.warnText}>
              {firstErrorLine(audio.errors, 'The production audio export failed.')}
            </Text>
          ) : null}
          {render.warnings.map((warning, index) => (
            <Text key={`render-warning:${index}`} style={styles.warnText}>
              {warning}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}

/* ------------------------------------------------------------------------- *
 * Presentational helpers (compact, local to this panel)
 * ------------------------------------------------------------------------- */

function ModeButton({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      style={({ pressed }) => [
        styles.modeButton,
        active ? styles.modeButtonActive : null,
        pressed ? styles.pressed : null,
      ]}
    >
      <View style={[styles.radioDot, active ? styles.radioDotActive : null]} />
      <Text style={[styles.modeText, active ? styles.modeTextActive : null]}>
        {label}
      </Text>
    </Pressable>
  );
}

function TemplatePicker({
  templates,
  value,
  onSelect,
  hint,
}: {
  templates: readonly SentenceTemplateOption[];
  value: string;
  onSelect: (id: string) => void;
  hint: string;
}) {
  return (
    <View style={styles.fieldGroup}>
      <Text style={styles.inputLabel}>Template</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chipRow}
      >
        <Chip
          label="Auto"
          active={value === ''}
          onPress={() => onSelect('')}
          accessibilityLabel="Let the backend pick a template"
        />
        {templates.map((option) => (
          <Chip
            key={`template:${option.id}`}
            label={option.id}
            active={value === option.id}
            onPress={() => onSelect(option.id)}
            accessibilityLabel={`Use template ${option.id}`}
          />
        ))}
      </ScrollView>
      <Text style={styles.fieldMeta}>{hint}</Text>
    </View>
  );
}

function ComposerPicker({
  value,
  mode,
  options,
  onSelect,
  onNew,
}: {
  value: string;
  mode: 'existing' | 'new';
  options: readonly string[];
  onSelect: (value: string) => void;
  onNew: () => void;
}) {
  if (Platform.OS === 'web') {
    return React.createElement(
      'select',
      {
        value: mode === 'new' ? '__new__' : value,
        'aria-label': 'New pattern composer',
        onChange: (event: React.ChangeEvent<HTMLSelectElement>) => {
          const next = event.target.value;
          if (next === '__new__') onNew();
          else onSelect(next);
        },
        style: {
          minHeight: 34,
          padding: '5px 8px',
          borderRadius: 5,
          border: `1px solid ${palette.hairlineStrong}`,
          backgroundColor: palette.background,
          color: palette.text,
          fontSize: 12,
        },
      },
      [
        ...options.map((composer) =>
          React.createElement(
            'option',
            { key: composer, value: composer },
            composer,
          ),
        ),
        React.createElement(
          'option',
          { key: '__new__', value: '__new__' },
          'New composer…',
        ),
      ],
    );
  }
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.chipRow}
    >
      {options.map((composer) => (
        <Chip
          key={`composer:${composer}`}
          label={composer}
          active={mode === 'existing' && value === composer}
          onPress={() => onSelect(composer)}
          accessibilityLabel={`Use composer ${composer}`}
        />
      ))}
      <Chip
        label="New…"
        active={mode === 'new'}
        onPress={onNew}
        accessibilityLabel="Add a new composer"
      />
    </ScrollView>
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
        active ? styles.chipActive : null,
        pressed ? styles.pressed : null,
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
          {busy && busyLabel ? busyLabel : label}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  box: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
    gap: 8,
  },
  headerRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 6,
  },
  blockLabel: {
    color: palette.textFaint,
  },
  stepMeta: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 8,
    lineHeight: 11,
    letterSpacing: 0.7,
  },
  hint: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  modeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  modeButton: {
    minHeight: 32,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.background,
  },
  modeButtonActive: {
    borderColor: palette.data,
    backgroundColor: palette.dataFill,
  },
  radioDot: {
    width: 9,
    height: 9,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.textFaint,
  },
  radioDotActive: {
    backgroundColor: palette.data,
    borderColor: palette.data,
  },
  modeText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 14,
    fontWeight: '600',
  },
  modeTextActive: {
    color: palette.data,
  },
  fieldGroup: {
    gap: 4,
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
  fieldMeta: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 13,
  },
  chipRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingRight: 4,
  },
  chip: {
    minHeight: 28,
    justifyContent: 'center',
    paddingHorizontal: 9,
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
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 13,
  },
  chipTextActive: {
    color: palette.data,
  },
  newGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  nameField: {
    flexGrow: 2,
    flexBasis: 150,
    gap: 2,
  },
  composerField: {
    flexGrow: 1,
    flexBasis: 120,
    gap: 2,
  },
  input: {
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
  metaRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: 4,
  },
  warnText: {
    color: palette.playhead,
    fontFamily: type.sans.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  actionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 8,
  },
  errorLine: {
    color: palette.sound,
    fontFamily: type.sans.fontFamily,
    fontSize: 10,
    lineHeight: 14,
    fontWeight: '600',
  },
  noteLine: {
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 13,
  },
  resultBox: {
    padding: 9,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(62, 224, 224, 0.35)',
    backgroundColor: 'rgba(62, 224, 224, 0.06)',
    gap: 6,
  },
  resultHeader: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 6,
  },
  resultTitle: {
    flexShrink: 1,
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 12,
    lineHeight: 16,
    fontWeight: '700',
  },
  resultBadge: {
    color: palette.playhead,
    fontFamily: type.mono.fontFamily,
    fontSize: 8,
    lineHeight: 11,
    letterSpacing: 0.5,
  },
  resultMeta: {
    color: palette.textMuted,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 13,
  },
  warningToggle: {
    alignSelf: 'flex-start',
    minHeight: 24,
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
  draftBox: {
    padding: 9,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.background,
    gap: 6,
  },
  draftTitle: {
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '700',
  },
  renderBox: {
    marginTop: 4,
    padding: 9,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.panel,
    gap: 6,
  },
  seriesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 6,
  },
  seriesChip: {
    color: palette.textMuted,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
    fontWeight: '700',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.background,
  },
  seriesChipActive: {
    color: palette.data,
    borderColor: palette.data,
    backgroundColor: palette.dataFill,
  },
  renderResultBox: {
    padding: 8,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(62, 224, 224, 0.35)',
    backgroundColor: 'rgba(62, 224, 224, 0.06)',
    gap: 4,
  },
  renderStatusText: {
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '700',
  },
  sentenceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    paddingVertical: 4,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
  },
  sentenceLetter: {
    width: 16,
    color: palette.data,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 13,
    fontWeight: '700',
  },
  sentenceBody: {
    flex: 1,
    minWidth: 0,
    gap: 1,
  },
  sentenceRange: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 10,
    lineHeight: 13,
  },
  sentenceId: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 8,
    lineHeight: 11,
  },
  figureSection: {
    gap: 4,
    paddingTop: 4,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
  },
  figureRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 7,
    paddingVertical: 4,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
  },
  figureBody: {
    flex: 1,
    minWidth: 0,
    gap: 2,
  },
  figureTitle: {
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 13,
    fontWeight: '700',
  },
  figureMeta: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 8,
    lineHeight: 11,
  },
  smallButton: {
    minHeight: 28,
    justifyContent: 'center',
    paddingHorizontal: 8,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
  },
  smallButtonText: {
    color: palette.textMuted,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
    fontWeight: '700',
  },
  advancedToggle: {
    alignSelf: 'flex-start',
    minHeight: 26,
    justifyContent: 'center',
  },
  advancedText: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
  },
  jsonScroll: {
    maxHeight: 240,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.panel,
  },
  jsonText: {
    padding: 8,
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 13,
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
});

export default SentenceDraftPanel;
