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
import { fetchSentenceExamples, requestMusicXmlSentenceDraft } from './api';
import {
  VILLA_COMPOSER,
  VILLA_RENDERER,
  VILLA_RENDERER_LABEL,
  appendPatternSentence,
  composerOptions,
  createPatternDraft,
  existingTemplateOptions,
  genericPatternOptions,
  isGenericPatternId,
  newPatternId,
  newPatternLabel,
  patternDraftJson,
  patternDraftLabel,
  removePatternSentence,
  sentenceDraftSourceLabel,
  villaMeterSupported,
  villaTemplateOptions,
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
    if (!draft || draft.sentences.length === 0) return;
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
            <View style={styles.actionRow}>
              <ActionButton
                label="Export bundle"
                primary={!result?.ok && draft.sentences.length > 0}
                onPress={exportBundle}
                disabled={draft.sentences.length === 0}
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
