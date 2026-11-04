import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { palette, TOUCH_TARGET } from '../musicalize/palette';
import { TopBar, type RoomMode } from '../musicalize/TopBar';
import { type } from '../musicalize/type';
import {
  previewSentenceSpec,
  studioSentenceUrl,
  validateSentenceSpec,
  type StudioError,
  type StudioPreviewResponse,
  type StudioValidateResponse,
} from './api';
import {
  DEFAULT_SAMPLE,
  PATTERNS,
  checkSpecText,
  defaultSampleForPattern,
  describeRequestFailure,
  findSample,
  fixtureText as sampleFixtureText,
  meterLabel,
  normalizeErrorPath,
  notesLines,
  parseJsonObject,
  patternOption,
  planLines,
  prefixErrorPaths,
  sampleText,
  textStats,
  valueLines,
  type PatternId,
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

const DEFAULT_STUDIO_SAMPLE = DEFAULT_SAMPLE;

function msLabel(ms: number): string {
  return `${Math.max(1, Math.round(ms))} ms`;
}

function sampleFor(pattern: PatternId, meter: string): StudioSample {
  return findSample(pattern, meter) ?? defaultSampleForPattern(pattern);
}

export function StudioRoom({ wide, onMode }: Props) {
  const insets = useSafeAreaInsets();
  const [sampleKey, setSampleKey] = useState(DEFAULT_STUDIO_SAMPLE.key);
  const current = findSampleByKey(sampleKey) ?? DEFAULT_STUDIO_SAMPLE;
  const [specText, setSpecText] = useState(() => sampleText(current));
  const [fixtureJson, setFixtureJson] = useState(() => sampleFixtureText(current));
  const [showFixture, setShowFixture] = useState(false);
  const [result, setResult] = useState<StudioResult>({ kind: 'idle' });
  const [dirty, setDirty] = useState(false);

  const inFlight = useRef<AbortController | null>(null);
  const runId = useRef(0);
  const specTextRef = useRef(specText);
  const fixtureJsonRef = useRef(fixtureJson);
  specTextRef.current = specText;
  fixtureJsonRef.current = fixtureJson;

  useEffect(
    () => () => {
      inFlight.current?.abort();
    },
    [],
  );

  const applySample = useCallback((sample: StudioSample) => {
    inFlight.current?.abort();
    inFlight.current = null;
    runId.current += 1;
    setSampleKey(sample.key);
    setSpecText(sampleText(sample));
    setFixtureJson(sampleFixtureText(sample));
    setResult({ kind: 'idle' });
    setDirty(false);
  }, []);

  const choosePattern = useCallback(
    (pattern: PatternId) => {
      applySample(sampleFor(pattern, current.meter));
    },
    [applySample, current.meter],
  );

  const chooseMeter = useCallback(
    (meter: string) => {
      applySample(sampleFor(current.pattern, meter));
    },
    [applySample, current.pattern],
  );

  const run = useCallback(
    async (action: RunAction) => {
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
    [specText, fixtureJson],
  );

  const running = result.kind === 'running';
  const stale =
    dirty &&
    (result.kind === 'validate' ||
      result.kind === 'preview' ||
      result.kind === 'failure');
  const meters = patternOption(current.pattern)?.meters ?? [current.meter];
  const stats = textStats(specText);

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
              Edit one Torroba or Sor sentence spec, validate it against the registry,
              then preview the plan and render hash. Audio playback is the next workstream.
            </Text>
          </View>

          <View style={[styles.columns, wide && styles.columnsWide]}>
            <View style={[styles.column, wide && styles.columnWide]}>
              <View style={styles.card}>
                <Text style={[type.section, styles.cardLabel]}>Template</Text>
                <Text style={styles.cardTitle}>{current.title}</Text>
                <Text style={styles.hint}>
                  Picking a pattern or meter loads a known-good sample and replaces the
                  editor contents. The JSON below is always the source of truth for a run.
                </Text>

                <Text style={styles.fieldLabel}>Pattern</Text>
                <View style={styles.chips}>
                  {PATTERNS.map((item) => (
                    <Chip
                      key={item.id}
                      label={item.label}
                      active={current.pattern === item.id}
                      accessibilityLabel={`${item.label}, ${item.composer}`}
                      onPress={() => choosePattern(item.id)}
                    />
                  ))}
                </View>
                <Text style={styles.composerHint}>
                  Torroba: castillo, sonatina, fandanguillo, danza · Sor: galop
                </Text>

                <Text style={styles.fieldLabel}>Meter</Text>
                <View style={styles.chips}>
                  {meters.map((meter) => (
                    <Chip
                      key={meter}
                      label={meterLabel(meter)}
                      active={current.meter === meter}
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
                    disabled={running}
                    busy={result.kind === 'running' && result.action === 'validate'}
                  />
                  <ActionButton
                    label="Preview"
                    primary
                    onPress={() => void run('preview')}
                    disabled={running}
                    busy={result.kind === 'running' && result.action === 'preview'}
                  />
                  {running ? (
                    <ActivityIndicator color={palette.data} size="small" />
                  ) : null}
                  {stale ? (
                    <Text style={styles.stale}>Edited since the last run.</Text>
                  ) : null}
                </View>
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
                  <Text style={styles.code}>rise</Text>. The galop cycle uses{' '}
                  <Text style={styles.code}>run_length</Text>.
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
              <ResultPanel result={result} stale={stale} />
              <View style={styles.endpoints}>
                <Text style={styles.endpointLabel}>Endpoints</Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioSentenceUrl('validate')}
                </Text>
                <Text selectable style={styles.endpoint}>
                  POST {studioSentenceUrl('preview')}
                </Text>
              </View>
            </View>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

function findSampleByKey(key: string): StudioSample | undefined {
  // The sample list is small; avoid exporting another lookup just for this.
  const [pattern, ...meterParts] = key.split(':');
  return findSample(pattern, meterParts.join(':'));
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

function ResultPanel({ result, stale }: { result: StudioResult; stale: boolean }) {
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

      <View style={styles.audioRow}>
        <View style={styles.audioPill}>
          <Text style={styles.audioPillText}>AUDIO PREVIEW NEXT</Text>
        </View>
        <Text style={styles.audioText}>
          No playback in this sprint. Compare render hashes across edits.
        </Text>
      </View>

      <ResultBlock label="Plan" lines={plan} empty={planEmpty} />
      <ResultBlock label="Row" lines={row} empty="No row returned." />
      <ResultBlock label="Matrix" lines={matrix} empty="No matrix returned." />
      <ResultBlock label="Notes" lines={notes} empty="No notes returned." />
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
  audioRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
    paddingVertical: 2,
  },
  audioPill: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.playhead,
  },
  audioPillText: {
    color: palette.playhead,
    fontFamily: type.mono.fontFamily,
    fontSize: 10,
    lineHeight: 14,
    fontWeight: '700',
    letterSpacing: 0.8,
  },
  audioText: {
    flex: 1,
    minWidth: 180,
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
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
