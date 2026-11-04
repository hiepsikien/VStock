import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Animated,
  Modal,
  PanResponder,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions,
} from 'react-native';
import * as Haptics from 'expo-haptics';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  DEFAULT_PROFILE_ID,
  PARAM_FIELD_BY_KEY,
  effectiveBpm,
  numberValue,
  paramsKey,
  stepValue,
  warningTexts,
  warningsFor,
  type ParamWarning,
  type ParamsFieldSchema,
  type ParamValue,
  type SonifyParams,
} from './params';
import { validateParams } from '../api/client';
import { copyCurrentLink, linkSupported } from './link';
import { WIDE_BREAKPOINT, palette, TOUCH_TARGET } from './palette';
import { TuningSpectrum } from './TuningSpectrum';
import { useTuning } from './tuning';
import { type } from './type';
import {
  anchorRatio,
  changedKeysForPanel,
  defaultRatio,
  hiddenChangedKeys,
  panelFields,
  panelGroups,
  panelLayout,
  panelPushes,
  panelWidthFor,
  paramDisplay,
  paramSummary,
  spectrumLevels,
  type PanelContext,
  type PanelLayout,
} from './tuningDisplay';

type Props = {
  baseBpm?: number;
  variant?: string;
  span?: string;
  ensemble?: string;
};

const PANEL_PADDING = 24;
const MIXER_KEYS = ['guitar_high', 'guitar_mid', 'guitar_bass'] as const;

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function clipboard(): { writeText?: (text: string) => Promise<void>; readText?: () => Promise<string> } | null {
  if (typeof navigator === 'undefined') return null;
  return navigator.clipboard ?? null;
}

async function writeClipboard(text: string): Promise<boolean> {
  const board = clipboard();
  if (!board?.writeText) return false;
  try {
    await board.writeText(text);
    return true;
  } catch {
    return false;
  }
}

async function readClipboard(): Promise<string | null> {
  const board = clipboard();
  if (!board?.readText) return null;
  try {
    return await board.readText();
  } catch {
    return null;
  }
}

function valueFor(params: SonifyParams, field: ParamsFieldSchema): ParamValue {
  return params[field.key] ?? field.default;
}

function valueText(
  field: ParamsFieldSchema,
  value: ParamValue,
  baseBpm?: number,
  compact = true,
): string {
  const display = paramDisplay(field, value, { baseBpm });
  if (compact && field.key === 'tempo' && display.secondary) {
    return `${display.primary} · ${display.secondary}`;
  }
  return display.primary;
}

/** One compact PC row: label/value on top, − slider + below. */
function ParamRow({
  field,
  value,
  baseBpm,
  rowHeight,
  compact,
  derived,
  hint,
  onChange,
}: {
  field: ParamsFieldSchema;
  value: ParamValue;
  baseBpm?: number;
  rowHeight: number;
  compact: boolean;
  derived?: string;
  hint?: string | null;
  onChange: (value: ParamValue) => void;
}) {
  const [helpOpen, setHelpOpen] = useState(false);
  const numeric = typeof value === 'number' ? value : field.min;
  const display = paramDisplay(field, value, { baseBpm });
  const changed = value !== field.default;
  const topHeight = compact ? 16 : 20;
  const controlHeight = Math.max(18, rowHeight - topHeight - (compact ? 8 : 14));
  const stepSize = Math.min(24, Math.max(16, controlHeight));

  const nudge = useCallback(
    (direction: 1 | -1) => {
      onChange(stepValue(field, numeric + direction * field.step));
      void Haptics.selectionAsync().catch(() => undefined);
    },
    [field, numeric, onChange],
  );

  return (
    <View style={[styles.param, compact ? { height: rowHeight } : null, helpOpen && styles.paramRaised]}>
      <View style={[styles.paramHead, compact ? { height: topHeight } : null]}>
        <View style={styles.paramLabelRow}>
          <Text style={[type.sans, styles.paramLabel]} numberOfLines={1}>
            {field.label}
          </Text>
          <Pressable
            onPress={() => setHelpOpen((current) => !current)}
            hitSlop={10}
            style={[styles.helpButton, helpOpen && styles.helpButtonOpen]}
            accessibilityRole="button"
            accessibilityLabel={`Giải thích ${field.label}`}
            accessibilityState={{ expanded: helpOpen }}
          >
            <Text style={[type.monoSmall, styles.helpMark, helpOpen && styles.helpMarkOpen]}>
              ?
            </Text>
          </Pressable>
        </View>
        <View style={styles.paramValueRow}>
          <Text style={[type.monoSmall, styles.paramValue]} numberOfLines={1}>
            {valueText(field, value, baseBpm, compact)}
          </Text>
          {changed ? (
            <Pressable
              onPress={() => onChange(field.default)}
              hitSlop={8}
              style={styles.resetButton}
              accessibilityRole="button"
              accessibilityLabel={`Đặt lại ${field.label}`}
            >
              <Text style={[type.monoSmall, styles.resetMark]}>↺</Text>
            </Pressable>
          ) : null}
        </View>
      </View>

      <View style={[styles.stepRow, { height: controlHeight }]}>
        <Pressable
          onPress={() => nudge(-1)}
          disabled={numeric <= field.min + 1e-9}
          hitSlop={8}
          style={[
            styles.stepButton,
            { width: stepSize, height: stepSize },
            numeric <= field.min + 1e-9 && styles.disabled,
          ]}
          accessibilityRole="button"
          accessibilityLabel={`Giảm ${field.label}`}
          accessibilityState={{ disabled: numeric <= field.min + 1e-9 }}
        >
          <Text style={[type.mono, styles.stepMark]}>−</Text>
        </Pressable>
        <SliderTrack field={field} value={numeric} height={controlHeight} onChange={onChange} />
        <Pressable
          onPress={() => nudge(1)}
          disabled={numeric >= field.max - 1e-9}
          hitSlop={8}
          style={[
            styles.stepButton,
            { width: stepSize, height: stepSize },
            numeric >= field.max - 1e-9 && styles.disabled,
          ]}
          accessibilityRole="button"
          accessibilityLabel={`Tăng ${field.label}`}
          accessibilityState={{ disabled: numeric >= field.max - 1e-9 }}
        >
          <Text style={[type.mono, styles.stepMark]}>+</Text>
        </Pressable>
      </View>

      {!compact && (derived || hint) ? (
        <View style={styles.paramFoot}>
          {derived ? <Text style={[type.monoSmall, styles.paramDerived]}>{derived}</Text> : null}
          {hint ? <Text style={[type.sans, styles.paramHint]}>{hint}</Text> : null}
        </View>
      ) : null}
      {helpOpen ? (
        <View style={[styles.helpPopover, !compact && styles.helpPopoverInline]}>
          <Text style={[type.sans, styles.helpText]}>{field.description}</Text>
        </View>
      ) : null}
    </View>
  );
}

function SliderTrack({
  field,
  value,
  height,
  onChange,
}: {
  field: ParamsFieldSchema;
  value: number;
  height: number;
  onChange: (value: ParamValue) => void;
}) {
  const [width, setWidth] = useState(0);
  const widthRef = useRef(0);
  const valueRef = useRef(value);
  const onChangeRef = useRef(onChange);
  valueRef.current = value;
  onChangeRef.current = onChange;

  const fromX = useCallback(
    (x: number) => {
      const track = widthRef.current;
      if (track <= 0) return;
      const ratio = clamp(x / track, 0, 1);
      onChangeRef.current(stepValue(field, field.min + ratio * (field.max - field.min)));
    },
    [field],
  );

  const responder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: (event) => fromX(event.nativeEvent.locationX),
        onPanResponderMove: (event) => fromX(event.nativeEvent.locationX),
      }),
    [fromX],
  );

  const nudge = useCallback(
    (direction: 1 | -1) => {
      onChangeRef.current(stepValue(field, valueRef.current + direction * field.step));
      void Haptics.selectionAsync().catch(() => undefined);
    },
    [field],
  );

  const webProps =
    Platform.OS === 'web'
      ? ({
          onKeyDown: (event: {
            key: string;
            preventDefault?: () => void;
            metaKey?: boolean;
            ctrlKey?: boolean;
            altKey?: boolean;
          }) => {
            if (event.metaKey || event.ctrlKey || event.altKey) return;
            if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') {
              nudge(-1);
              event.preventDefault?.();
            } else if (event.key === 'ArrowRight' || event.key === 'ArrowUp') {
              nudge(1);
              event.preventDefault?.();
            } else if (event.key === 'Home') {
              onChangeRef.current(field.min);
              event.preventDefault?.();
            } else if (event.key === 'End') {
              onChangeRef.current(field.max);
              event.preventDefault?.();
            }
          },
        } as Record<string, unknown>)
      : {};

  const span = field.max - field.min;
  const ratio = clamp(span > 0 ? (value - field.min) / span : 0, 0, 1);
  const anchor = width * anchorRatio(field);
  const defaultValueX = width * defaultRatio(field);
  const knobX = width * ratio;
  const fillLeft = Math.min(anchor, knobX);
  const fillWidth = Math.abs(knobX - anchor);
  const trackTop = Math.max(0, height / 2 - 2);

  return (
    <View
      {...webProps}
      {...responder.panHandlers}
      onLayout={(event) => {
        const next = event.nativeEvent.layout.width;
        widthRef.current = next;
        setWidth(next);
      }}
      style={[styles.sliderHit, { height }]}
      focusable
      accessible
      accessibilityRole="adjustable"
      accessibilityLabel={field.label}
      accessibilityHint={field.description}
      accessibilityValue={{
        min: field.min,
        max: field.max,
        now: value,
        text: paramDisplay(field, value).primary,
      }}
      accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
      onAccessibilityAction={(event) => {
        if (event.nativeEvent.actionName === 'increment') nudge(1);
        if (event.nativeEvent.actionName === 'decrement') nudge(-1);
      }}
    >
      <View style={[styles.sliderTrack, { top: trackTop }]}>
        <View style={[styles.sliderFill, { left: fillLeft, width: fillWidth }]} />
        <View style={[styles.sliderAnchor, { left: anchor - 0.5 }]} />
        {Math.abs(defaultValueX - anchor) > 2 ? (
          <View style={[styles.sliderDefault, { left: defaultValueX - 1.5 }]} />
        ) : null}
        <View
          style={[
            styles.sliderKnob,
            { left: Math.max(0, Math.min(width - 12, knobX - 6)), top: -4 },
          ]}
        />
      </View>
    </View>
  );
}

function ParamFader({
  field,
  value,
  trackHeight,
  onChange,
}: {
  field: ParamsFieldSchema;
  value: number;
  trackHeight: number;
  onChange: (value: ParamValue) => void;
}) {
  const [height, setHeight] = useState(trackHeight);
  const heightRef = useRef(trackHeight);
  const valueRef = useRef(value);
  const onChangeRef = useRef(onChange);
  heightRef.current = height;
  valueRef.current = value;
  onChangeRef.current = onChange;

  const fromY = useCallback(
    (y: number) => {
      const track = heightRef.current;
      if (track <= 0) return;
      const ratio = clamp(1 - y / track, 0, 1);
      onChangeRef.current(stepValue(field, field.min + ratio * (field.max - field.min)));
    },
    [field],
  );

  const responder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: (event) => fromY(event.nativeEvent.locationY),
        onPanResponderMove: (event) => fromY(event.nativeEvent.locationY),
      }),
    [fromY],
  );

  const nudge = useCallback(
    (direction: 1 | -1) => {
      onChangeRef.current(stepValue(field, valueRef.current + direction * field.step));
      void Haptics.selectionAsync().catch(() => undefined);
    },
    [field],
  );

  const webProps =
    Platform.OS === 'web'
      ? ({
          onKeyDown: (event: { key: string; preventDefault?: () => void }) => {
            if (event.key === 'ArrowUp' || event.key === 'ArrowRight') {
              nudge(1);
              event.preventDefault?.();
            } else if (event.key === 'ArrowDown' || event.key === 'ArrowLeft') {
              nudge(-1);
              event.preventDefault?.();
            } else if (event.key === 'Home') {
              onChangeRef.current(field.min);
              event.preventDefault?.();
            } else if (event.key === 'End') {
              onChangeRef.current(field.max);
              event.preventDefault?.();
            }
          },
        } as Record<string, unknown>)
      : {};

  const span = field.max - field.min;
  const ratio = clamp(span > 0 ? (value - field.min) / span : 0, 0, 1);
  const filledTop = Math.min(0.5, ratio) * trackHeight;
  const filledHeight = Math.abs(ratio - 0.5) * trackHeight;
  const thumbTop = (1 - ratio) * trackHeight - 4;

  return (
    <View style={styles.fader}>
      <Text style={[type.sans, styles.faderLabel]} numberOfLines={1}>
        {field.label}
      </Text>
      <View
        {...webProps}
        {...responder.panHandlers}
        onLayout={(event) => {
          const next = event.nativeEvent.layout.height;
          heightRef.current = next;
          setHeight(next);
        }}
        style={[styles.faderHit, { height: trackHeight }]}
        focusable
        accessible
        accessibilityRole="adjustable"
        accessibilityLabel={field.label}
        accessibilityHint={field.description}
        accessibilityValue={{
          min: field.min,
          max: field.max,
          now: value,
          text: paramDisplay(field, value).primary,
        }}
        accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
        onAccessibilityAction={(event) => {
          if (event.nativeEvent.actionName === 'increment') nudge(1);
          if (event.nativeEvent.actionName === 'decrement') nudge(-1);
        }}
      >
        <View style={styles.faderTrack} />
        <View style={[styles.faderFill, { top: filledTop, height: filledHeight }]} />
        <View style={[styles.faderCenter, { top: trackHeight / 2 - 0.5 }]} />
        <View style={[styles.faderThumb, { top: thumbTop }]} />
      </View>
      <Text style={[type.monoSmall, styles.faderValue]}>{paramDisplay(field, value).primary}</Text>
    </View>
  );
}

function ChoiceField({
  field,
  value,
  onChange,
}: {
  field: ParamsFieldSchema;
  value: ParamValue;
  onChange: (value: ParamValue) => void;
}) {
  const display = paramDisplay(field, value);
  return (
    <View style={styles.choiceField}>
      <View style={styles.choiceHead}>
        <Text style={[type.sans, styles.paramLabel]}>{field.label}</Text>
        <Text style={[type.monoSmall, styles.paramValue]}>{display.primary}</Text>
      </View>
      <View style={styles.choiceRow}>
        {field.choices.map((choice) => {
          const active = choice.value === value;
          return (
            <Pressable
              key={choice.value}
              onPress={() => onChange(choice.value)}
              style={[styles.choice, active && styles.choiceActive]}
              accessibilityRole="radio"
              accessibilityLabel={choice.label}
              accessibilityState={{ selected: active }}
            >
              <Text style={[type.sans, styles.choiceText, active && styles.choiceTextActive]}>
                {choice.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function ToggleRow({
  field,
  value,
  onChange,
}: {
  field: ParamsFieldSchema;
  value: ParamValue;
  onChange: (value: ParamValue) => void;
}) {
  const active = value === true;
  return (
    <View style={styles.param}>
      <View style={styles.paramHead}>
        <Text style={[type.sans, styles.paramLabel]}>{field.label}</Text>
        <Text style={[type.monoSmall, styles.paramValue]}>{active ? 'Bật' : 'Tắt'}</Text>
      </View>
      <Pressable
        onPress={() => onChange(!active)}
        style={[styles.choice, active && styles.choiceActive, styles.toggleWide]}
        accessibilityRole="switch"
        accessibilityLabel={field.label}
        accessibilityState={{ checked: active }}
      >
        <Text style={[type.sans, styles.choiceText, active && styles.choiceTextActive]}>
          {active ? 'Bật' : 'Tắt'}
        </Text>
      </Pressable>
    </View>
  );
}

function GroupSection({
  group,
  params,
  rowHeight,
  compact,
  baseBpm,
  hints,
  onChange,
}: {
  group: ReturnType<typeof panelGroups>[number];
  params: SonifyParams;
  rowHeight: number;
  compact: boolean;
  baseBpm?: number;
  hints: Record<string, string | null | undefined>;
  onChange: (key: string, value: ParamValue) => void;
}) {
  return (
    <View style={styles.group}>
      <Text style={[type.section, styles.groupLabel]}>{group.label}</Text>
      {group.fields.map((field) => {
        const value = valueFor(params, field);
        if (field.type === 'choice') {
          return (
            <ChoiceField
              key={field.key}
              field={field}
              value={value}
              onChange={(next) => onChange(field.key, next)}
            />
          );
        }
        if (field.type === 'toggle') {
          return (
            <ToggleRow
              key={field.key}
              field={field}
              value={value}
              onChange={(next) => onChange(field.key, next)}
            />
          );
        }
        return (
          <ParamRow
            key={field.key}
            field={field}
            value={value}
            baseBpm={baseBpm}
            rowHeight={rowHeight}
            compact={compact}
            derived={field.key === 'tempo' && baseBpm != null ? `${effectiveBpm(baseBpm, numberValue(params, 'tempo'))} BPM` : undefined}
            hint={hints[field.key]}
            onChange={(next) => onChange(field.key, next)}
          />
        );
      })}
    </View>
  );
}

function Mixer({
  context,
  params,
  dense,
  rowHeight,
  compact,
  onChange,
}: {
  context: PanelContext;
  params: SonifyParams;
  dense: boolean;
  rowHeight: number;
  compact: boolean;
  onChange: (key: string, value: ParamValue) => void;
}) {
  const register = PARAM_FIELD_BY_KEY.register;
  const registerVisible = panelFields(context).some((field) => field.key === 'register');
  const guitar = context.variant === 'guitar';
  const levels = spectrumLevels(params, context.variant);
  const guitarFields = MIXER_KEYS.map((key) => PARAM_FIELD_BY_KEY[key]).filter(Boolean);
  const allZero = guitarFields.every((field) => numberValue(params, field.key) === 0);
  const mixerHeight = compact ? (dense ? 180 : 210) : 232;
  const topHeight = compact ? (dense ? 120 : 138) : 156;
  const bottomHeight = compact ? (dense ? 40 : 48) : 56;
  const waveHeight = compact ? (dense ? 66 : 84) : 82;
  const faderHeight = compact ? (dense ? 58 : 74) : 70;

  return (
    <View style={[styles.mixer, { height: mixerHeight }]}>
      <View style={[styles.mixerTop, { height: topHeight }]}>
        <View style={styles.mixerWave}>
          <Text style={[type.section, styles.groupLabel]}>CÂN BẰNG BÈ</Text>
          <TuningSpectrum levels={levels} height={waveHeight} />
          <View style={styles.waveLabels}>
            <Text style={[type.monoSmall, styles.waveLabel]}>THẤP</Text>
            <Text style={[type.monoSmall, styles.waveLabel]}>TRUNG</Text>
            <Text style={[type.monoSmall, styles.waveLabel]}>CAO</Text>
          </View>
          <Text style={[type.sans, styles.waveNote]}>Phổ ước lượng từ tham số</Text>
        </View>
        <View style={styles.mixerFaders}>
          {guitar ? (
            guitarFields.map((field) => (
              <ParamFader
                key={field.key}
                field={field}
                value={numberValue(params, field.key)}
                trackHeight={faderHeight}
                onChange={(next) => onChange(field.key, next)}
              />
            ))
          ) : (
            <Text style={[type.sans, styles.mixerEmpty]}>
              Bè guitar chỉ mở ở thể loại Guitar.
            </Text>
          )}
        </View>
      </View>
      <View style={[styles.mixerBottom, { height: bottomHeight }]}>
        {registerVisible ? (
          <View style={styles.mixerRegister}>
            <ParamRow
              field={register}
              value={params.register}
              rowHeight={bottomHeight}
              compact={compact}
              onChange={(next) => onChange(register.key, next)}
            />
          </View>
        ) : null}
        {guitar ? (
          <SmallButton
            label="Đưa 3 bè về 0"
            onPress={() => {
              for (const key of MIXER_KEYS) onChange(key, 0);
            }}
            disabled={allZero}
          />
        ) : null}
      </View>
    </View>
  );
}

function FormStrip({
  fields,
  params,
  dangStacked,
  onChange,
}: {
  fields: ParamsFieldSchema[];
  params: SonifyParams;
  dangStacked: boolean;
  onChange: (key: string, value: ParamValue) => void;
}) {
  if (fields.length === 0) return null;
  return (
    <View style={styles.formStrip}>
      <Text style={[type.section, styles.formTitle]}>DÁNG</Text>
      <View style={[styles.formFields, dangStacked ? styles.formFieldsColumn : styles.formFieldsRow]}>
        {fields.map((field) => (
          <View key={field.key} style={styles.formField}>
            <ChoiceField
              field={field}
              value={valueFor(params, field)}
              onChange={(next) => onChange(field.key, next)}
            />
          </View>
        ))}
      </View>
    </View>
  );
}

function TuningBody({
  baseBpm,
  context,
  layout,
  compact,
}: {
  baseBpm: number;
  context: PanelContext;
  layout: PanelLayout;
  compact: boolean;
}) {
  const { params, setParam } = useTuning();
  const groups = panelGroups(context);
  const groupById = new Map(groups.map((group) => [group.id, group]));
  const formGroup = groupById.get('form');
  const bpm = effectiveBpm(baseBpm, numberValue(params, 'tempo'));
  const guitarLow = context.variant === 'guitar' && bpm < 90;
  const highHumanize = warningsFor(params).some((warning) => warning.code === 'high_humanize');
  const highBreath = warningsFor(params).some((warning) => warning.code === 'high_breath');
  const hints: Record<string, string | null | undefined> = {
    tempo: guitarLow ? 'Dưới ngưỡng tremolo' : undefined,
    humanize: highHumanize ? 'Trên 1.10 dễ làm phẳng contour' : undefined,
    breath: highBreath ? 'Trên 1.20 đã chạm trần câu' : undefined,
    guitar_high: numberValue(params, 'guitar_high') > 4 ? 'Trên +4 đẩy nốt snap khỏi dải móng' : undefined,
    guitar_mid: numberValue(params, 'guitar_mid') > 4 ? 'Trên +4 đẩy nốt snap khỏi dải móng' : undefined,
    guitar_bass: numberValue(params, 'guitar_bass') > 4 ? 'Trên +4 đẩy nốt snap khỏi dải móng' : undefined,
  };

  const columnIds = layout.columns === 3
    ? [['performance'], ['texture'], ['harmony', 'guitar']]
    : layout.columns === 2
      ? [['performance', 'texture'], ['harmony', 'guitar']]
      : [['performance', 'texture', 'harmony', 'guitar']];

  return (
    <View style={styles.body}>
      <Mixer
        context={context}
        params={params}
        dense={layout.dense}
        rowHeight={layout.rowHeight}
        compact={compact}
        onChange={(key, value) => setParam(key, value)}
      />
      <View style={[styles.columns, layout.columns === 1 && styles.columnsStacked]}>
        {columnIds.map((ids, index) => (
          <View key={index} style={styles.column}>
            {ids.map((id) => {
              const group = groupById.get(id);
              return group ? (
                <GroupSection
                  key={id}
                  group={group}
                  params={params}
                  rowHeight={layout.rowHeight || 58}
                  compact={compact}
                  baseBpm={baseBpm}
                  hints={hints}
                  onChange={(key, value) => setParam(key, value)}
                />
              ) : null;
            })}
          </View>
        ))}
      </View>
      <FormStrip
        fields={formGroup?.fields ?? []}
        params={params}
        dangStacked={layout.dangStacked}
        onChange={(key, value) => setParam(key, value)}
      />
    </View>
  );
}

function ProfileTab({ context }: { context: PanelContext }) {
  const {
    store,
    profile,
    dirty,
    select,
    saveChanges,
    addProfile,
    duplicate,
    rename,
    remove,
    reset,
    importProfiles,
    exportProfiles,
  } = useTuning();
  const [editor, setEditor] = useState<'create' | 'rename' | null>(null);
  const [nameDraft, setNameDraft] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const canClipboard = useMemo(
    () => Platform.OS === 'web' && Boolean(clipboard()?.writeText),
    [],
  );
  const canRead = useMemo(
    () => Platform.OS === 'web' && Boolean(clipboard()?.readText),
    [],
  );
  const canCopyLink = useMemo(() => linkSupported(), []);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 2200);
    return () => clearTimeout(timer);
  }, [notice]);

  const begin = (mode: 'create' | 'rename') => {
    setEditor(mode);
    setNameDraft(mode === 'rename' ? profile.name : '');
  };

  const confirmName = () => {
    if (editor === 'create') addProfile(nameDraft);
    if (editor === 'rename') rename(profile.id, nameDraft);
    setEditor(null);
    setNameDraft('');
  };

  const copyProfiles = async () => {
    const ok = await writeClipboard(exportProfiles());
    setNotice(ok ? 'Đã chép JSON' : 'Không chép được');
  };

  const pasteProfiles = async () => {
    const text = await readClipboard();
    if (!text) {
      setNotice('Không đọc được clipboard');
      return;
    }
    setNotice(importProfiles(text) ? 'Đã nhập profile' : 'JSON không hợp lệ');
  };

  return (
    <View style={styles.profileTab}>
      <View style={styles.profileList}>
        {store.profiles.map((item) => {
          const active = item.id === profile.id;
          return (
            <Pressable
              key={item.id}
              onPress={() => select(item.id)}
              style={[styles.profileRow, active && styles.profileRowActive]}
              accessibilityRole="button"
              accessibilityLabel={`Chọn ${item.name}`}
              accessibilityState={{ selected: active }}
            >
              <View style={styles.profileRowText}>
                <Text style={[type.sans, styles.profileName]} numberOfLines={1}>
                  {item.name}
                </Text>
                <Text style={[type.monoSmall, styles.profileMeta]} numberOfLines={1}>
                  {item.id === DEFAULT_PROFILE_ID ? 'khoá · ' : ''}
                  {paramSummary(item.params, context)}
                </Text>
              </View>
              {active ? <Text style={[type.monoSmall, styles.activeMark]}>đang dùng</Text> : null}
            </Pressable>
          );
        })}
      </View>

      {editor ? (
        <View style={styles.editor}>
          <TextInput
            value={nameDraft}
            onChangeText={setNameDraft}
            placeholder={editor === 'create' ? 'Tên profile mới' : 'Tên mới'}
            placeholderTextColor={palette.textFaint}
            maxLength={40}
            autoFocus
            style={[type.sans, styles.input]}
            onSubmitEditing={confirmName}
            accessibilityLabel="Tên profile"
          />
          <View style={styles.actionRow}>
            <SmallButton label="Huỷ" onPress={() => setEditor(null)} />
            <SmallButton label="Lưu tên" onPress={confirmName} />
          </View>
        </View>
      ) : (
        <View style={styles.actionRow}>
          <SmallButton label="Tạo mới" onPress={() => begin('create')} />
          <SmallButton label="Nhân bản" onPress={() => duplicate(profile.id)} />
          <SmallButton
            label="Đổi tên"
            onPress={() => begin('rename')}
            disabled={profile.id === DEFAULT_PROFILE_ID}
          />
          <SmallButton
            label="Xoá"
            onPress={() => remove(profile.id)}
            disabled={profile.id === DEFAULT_PROFILE_ID}
          />
        </View>
      )}

      <View style={styles.actionRow}>
        <SmallButton
          label="Về Default"
          onPress={() => reset(profile.id)}
          disabled={profile.id === DEFAULT_PROFILE_ID}
        />
        <SmallButton label="Lưu thay đổi" onPress={saveChanges} disabled={!dirty} />
      </View>

      {canClipboard || canRead || canCopyLink ? (
        <View style={styles.actionRow}>
          {canClipboard ? <SmallButton label="Chép JSON" onPress={() => void copyProfiles()} /> : null}
          {canRead ? <SmallButton label="Nhập JSON" onPress={() => void pasteProfiles()} /> : null}
          {canCopyLink ? (
            <SmallButton
              label="Chép liên kết"
              onPress={() => {
                void copyCurrentLink().then((ok) => setNotice(ok ? 'Đã chép liên kết' : 'Không chép được'));
              }}
            />
          ) : null}
        </View>
      ) : null}
      {notice ? <Text style={[type.sans, styles.notice]}>{notice}</Text> : null}
      <Text style={[type.sans, styles.footNote]}>
        Profile lưu trên máy. Tên không đi vào hash hay URL. Bấm Play bên ngoài để nghe profile đang chọn.
      </Text>
    </View>
  );
}

function SmallButton({
  label,
  onPress,
  disabled = false,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={[styles.smallButton, disabled && styles.disabled]}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled }}
    >
      <Text style={[type.sans, styles.smallButtonText]}>{label}</Text>
    </Pressable>
  );
}

export function TuningPanel({ baseBpm, variant, span, ensemble }: Props) {
  const {
    enabled,
    enabledTiers,
    open,
    setOpen,
    dirty,
    revert,
    saveChanges,
    params,
    profile,
    setPanelContext,
  } = useTuning();
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const wide = width >= WIDE_BREAKPOINT;
  const panelWidth = wide ? panelWidthFor(width) : width;
  const context = useMemo<PanelContext>(
    () => ({ variant, span, ensemble, tiers: enabledTiers }),
    [enabledTiers, ensemble, span, variant],
  );
  useEffect(() => {
    setPanelContext(context);
  }, [context, setPanelContext]);
  const layout = panelLayout(width, height, context);
  const push = wide && panelPushes(width);
  const compact = wide;
  const [rendered, setRendered] = useState(open);
  const [tab, setTab] = useState<'tune' | 'profile'>('tune');
  const [snap, setSnap] = useState<'half' | 'full'>('half');
  const [statusOpen, setStatusOpen] = useState(false);
  const [availableHeight, setAvailableHeight] = useState(0);
  const [contentHeight, setContentHeight] = useState(0);
  const drawerX = useRef(new Animated.Value(panelWidth)).current;
  const sheetHeight = Math.max(260, Math.round(height * 0.88));
  const halfOffset = Math.max(0, sheetHeight - Math.round(height * 0.48));
  const sheetY = useRef(new Animated.Value(halfOffset)).current;
  const dragStart = useRef(halfOffset);
  const [serverWarnings, setServerWarnings] = useState<{
    key: string;
    warnings: ParamWarning[];
  }>({ key: '', warnings: [] });

  const currentParamsKey = paramsKey(params);
  const hiddenCount = hiddenChangedKeys(params, context).length;
  const changedCount = changedKeysForPanel(params, context).length;
  const bpm = baseBpm == null ? null : effectiveBpm(baseBpm, numberValue(params, 'tempo'));
  const localWarnings = warningsFor(params);
  const highHumanize = localWarnings.some((warning) => warning.code === 'high_humanize');
  const highBreath = localWarnings.some((warning) => warning.code === 'high_breath');

  useEffect(() => {
    if (!enabled || baseBpm == null) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void validateParams(params, { variant, ensemble, span }, controller.signal)
        .then((result) => {
          if (!controller.signal.aborted) {
            setServerWarnings({ key: currentParamsKey, warnings: result.warnings });
          }
        })
        .catch(() => {
          // Offline keeps the last server copy and local hints.
        });
    }, 350);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [baseBpm, currentParamsKey, enabled, ensemble, params, span, variant]);

  const serverNotes =
    serverWarnings.key === currentParamsKey
      ? warningTexts(
          serverWarnings.warnings.filter(
            (warning) => warning.code !== 'high_humanize' && warning.code !== 'high_breath',
          ),
        )
      : [];
  const notes = useMemo(() => {
    const next = new Set<string>();
    next.add(changedCount === 0 ? 'Default' : `${changedCount} thay đổi`);
    if (profile.id === DEFAULT_PROFILE_ID && dirty) {
      next.add('Default bất biến. Lưu sẽ tạo một bản sao có tên.');
    }
    if (hiddenCount > 0) next.add(`Còn ${hiddenCount} thay đổi ẩn không áp dụng cho màn này.`);
    for (const text of warningTexts(localWarnings)) next.add(text);
    for (const text of serverNotes) next.add(text);
    return [...next];
  }, [changedCount, dirty, hiddenCount, localWarnings, profile.id, serverNotes]);

  const scrollEnabled = !wide || contentHeight > availableHeight + 1;

  useEffect(() => {
    if (!open) drawerX.setValue(panelWidth);
  }, [drawerX, open, panelWidth]);

  useEffect(() => {
    if (open) {
      setRendered(true);
      if (!wide) setSnap('half');
    }
  }, [open, wide]);

  useEffect(() => {
    if (wide) {
      Animated.timing(drawerX, {
        toValue: open ? 0 : panelWidth,
        duration: 220,
        useNativeDriver: true,
      }).start(({ finished }) => {
        if (finished && !open) setRendered(false);
      });
      return;
    }
    const target = !open ? sheetHeight : snap === 'full' ? 0 : halfOffset;
    Animated.spring(sheetY, {
      toValue: target,
      damping: 24,
      stiffness: 240,
      mass: 0.9,
      useNativeDriver: false,
    }).start(({ finished }) => {
      if (finished && !open) setRendered(false);
    });
  }, [drawerX, halfOffset, open, panelWidth, sheetHeight, sheetY, snap, wide]);

  const close = () => setOpen(false);

  const handleResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_event, gesture) => Math.abs(gesture.dy) > 4,
        onPanResponderGrant: () => {
          sheetY.stopAnimation((value) => {
            dragStart.current = value;
          });
        },
        onPanResponderMove: (_event, gesture) => {
          sheetY.setValue(clamp(dragStart.current + gesture.dy, 0, sheetHeight));
        },
        onPanResponderRelease: (_event, gesture) => {
          const current = Math.max(0, dragStart.current + gesture.dy);
          const next =
            gesture.dy > 48 || gesture.vy > 0.6
              ? 'half'
              : gesture.dy < -48 || gesture.vy < -0.6
                ? 'full'
                : current < halfOffset / 2
                  ? 'full'
                  : 'half';
          setSnap(next);
        },
      }),
    [halfOffset, sheetHeight, sheetY],
  );

  if (!enabled || baseBpm == null) return null;

  const headerHeight = wide && layout.dense ? 64 : 76;
  const content = (
    <>
      <View
        style={[
          styles.header,
          {
            height: headerHeight,
            paddingHorizontal: wide ? PANEL_PADDING : 16,
          },
        ]}
      >
        <View style={styles.headerMain}>
          <View style={styles.tabs}>
            <Pressable
              onPress={() => setTab('tune')}
              style={[styles.tab, tab === 'tune' && styles.tabActive]}
              accessibilityRole="tab"
              accessibilityState={{ selected: tab === 'tune' }}
              accessibilityLabel="Tinh chỉnh"
            >
              <Text style={[type.section, tab === 'tune' ? styles.tabTextOn : styles.tabText]}>
                Tinh chỉnh
              </Text>
            </Pressable>
            <Pressable
              onPress={() => setTab('profile')}
              style={[styles.tab, tab === 'profile' && styles.tabActive]}
              accessibilityRole="tab"
              accessibilityState={{ selected: tab === 'profile' }}
              accessibilityLabel="Profile"
            >
              <Text style={[type.section, tab === 'profile' ? styles.tabTextOn : styles.tabText]}>
                Profile
              </Text>
            </Pressable>
          </View>
          <View style={styles.profileLine}>
            <Text style={[type.sans, styles.profileName]} numberOfLines={1}>
              {profile.name}
            </Text>
            {dirty ? <Text style={[type.monoSmall, styles.modified]}>• đã sửa</Text> : null}
          </View>
        </View>
        <Pressable
          onPress={close}
          hitSlop={8}
          style={styles.close}
          accessibilityRole="button"
          accessibilityLabel="Đóng tinh chỉnh"
        >
          <Text style={[type.sans, styles.closeText]}>✕</Text>
        </Pressable>
      </View>

      <Pressable
        onPress={() => setStatusOpen((current) => !current)}
        style={[styles.statusStrip, { paddingHorizontal: wide ? PANEL_PADDING : 16 }]}
        accessibilityRole="button"
        accessibilityLabel="Xem ghi chú và cảnh báo"
        accessibilityState={{ expanded: statusOpen }}
      >
        <Text
          style={[
            type.monoSmall,
            styles.statusText,
            (localWarnings.length > 0 || serverNotes.length > 0) && styles.statusTextWarn,
          ]}
          numberOfLines={1}
        >
          {notes.join(' · ')}
        </Text>
        <Text style={[type.monoSmall, styles.statusChevron]}>{statusOpen ? '▴' : '▾'}</Text>
      </Pressable>

      {statusOpen ? (
        <View
          style={[
            styles.statusPopover,
            {
              top: headerHeight + 28,
              left: wide ? PANEL_PADDING : 16,
              right: wide ? PANEL_PADDING : 16,
            },
          ]}
        >
          <View style={styles.statusPopoverHead}>
            <Text style={[type.section, styles.groupLabel]}>GHI CHÚ</Text>
            <Pressable
              onPress={() => setStatusOpen(false)}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel="Đóng ghi chú"
            >
              <Text style={[type.sans, styles.closeText]}>✕</Text>
            </Pressable>
          </View>
          {notes.map((note) => (
            <Text key={note} style={[type.sans, styles.note]}>
              {note}
            </Text>
          ))}
        </View>
      ) : null}

      <View
        style={styles.bodyShell}
        onLayout={(event) => setAvailableHeight(event.nativeEvent.layout.height)}
      >
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={[
            styles.scrollBody,
            { paddingHorizontal: wide ? PANEL_PADDING : 16 },
            !scrollEnabled && styles.scrollBodyStatic,
          ]}
          keyboardShouldPersistTaps="handled"
          scrollEnabled={scrollEnabled}
          showsVerticalScrollIndicator={scrollEnabled}
          onContentSizeChange={(_width, nextHeight) => setContentHeight(nextHeight)}
        >
          {tab === 'tune' ? (
            <TuningBody baseBpm={baseBpm} context={context} layout={layout} compact={compact} />
          ) : (
            <ProfileTab context={context} />
          )}
        </ScrollView>
      </View>

      {tab === 'tune' ? (
        <View style={[styles.footerFixed, { paddingHorizontal: wide ? PANEL_PADDING : 16 }]}>
          <View style={styles.footerActions}>
            <SmallButton label="Reset" onPress={revert} disabled={!dirty} />
            <Pressable
              onPress={saveChanges}
              disabled={!dirty}
              style={[styles.primary, styles.footerPrimary, !dirty && styles.disabled]}
              accessibilityRole="button"
              accessibilityLabel="Lưu profile"
              accessibilityState={{ disabled: !dirty }}
            >
              <Text style={[type.section, styles.primaryText]}>Lưu</Text>
            </Pressable>
          </View>
        </View>
      ) : null}
    </>
  );

  const drawer = (
    <Animated.View
      style={[
        styles.drawer,
        {
          width: panelWidth,
          paddingTop: insets.top,
          paddingBottom: insets.bottom,
          transform: [{ translateX: drawerX }],
        },
      ]}
    >
      {content}
    </Animated.View>
  );

  // Push mode keeps the chart live; wide overlays use a modal with a backdrop.
  if (push) return rendered ? drawer : null;

  return (
    <Modal
      visible={rendered}
      transparent
      animationType="none"
      onRequestClose={close}
      statusBarTranslucent
    >
      <View style={StyleSheet.absoluteFill} pointerEvents="box-none">
        <Pressable
          onPress={close}
          style={[StyleSheet.absoluteFill, styles.backdrop]}
          accessibilityRole="button"
          accessibilityLabel="Đóng tinh chỉnh"
        />
        {wide ? (
          drawer
        ) : (
          <Animated.View
            style={[
              styles.sheet,
              {
                height: sheetHeight,
                paddingBottom: insets.bottom,
                transform: [{ translateY: sheetY }],
              },
            ]}
          >
            <View {...handleResponder.panHandlers} style={styles.handleWrap}>
              <View style={styles.handle} />
            </View>
            {content}
          </Animated.View>
        )}
      </View>
    </Modal>
  );
}

/** The trigger lives in the shelf row; it carries the active profile name. */
export function TuningTrigger({ available = true }: { available?: boolean } = {}) {
  const { enabled, open, setOpen, profile, dirty } = useTuning();
  if (!enabled || !available) return null;
  return (
    <Pressable
      onPress={() => setOpen(!open)}
      hitSlop={6}
      style={styles.trigger}
      accessibilityRole="button"
      accessibilityLabel={`Tinh chỉnh ${profile.name}`}
      accessibilityState={{ expanded: open }}
    >
      <Text style={[type.sans, styles.triggerText]} numberOfLines={1} ellipsizeMode="tail">
        Tinh chỉnh · {profile.name}
        {dirty ? ' •' : ''}
      </Text>
      <Text style={[type.sans, styles.triggerChevron]}>›</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  trigger: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    maxWidth: 220,
    flexShrink: 1,
    height: 32,
    paddingHorizontal: 8,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
  },
  triggerText: {
    color: palette.textMuted,
    fontSize: 12,
    flexShrink: 1,
  },
  triggerChevron: {
    color: palette.textFaint,
    fontSize: 13,
  },
  drawer: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    backgroundColor: palette.panel,
    borderLeftWidth: 1,
    borderLeftColor: palette.hairlineStrong,
    overflow: 'hidden',
  },
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: palette.panel,
    borderTopLeftRadius: 14,
    borderTopRightRadius: 14,
    borderTopWidth: 1,
    borderTopColor: palette.hairlineStrong,
    overflow: 'hidden',
  },
  backdrop: {
    backgroundColor: 'rgba(8, 9, 12, 0.58)',
  },
  handleWrap: {
    height: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  handle: {
    width: 42,
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.hairlineStrong,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: palette.hairline,
  },
  headerMain: {
    flex: 1,
    minWidth: 0,
  },
  tabs: {
    flexDirection: 'row',
    gap: 16,
    height: 40,
  },
  tab: {
    minHeight: 40,
    justifyContent: 'center',
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabActive: {
    borderBottomColor: palette.sound,
  },
  tabText: {
    color: palette.textFaint,
  },
  tabTextOn: {
    color: palette.text,
  },
  profileLine: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 8,
    minHeight: 20,
  },
  profileName: {
    color: palette.text,
    flexShrink: 1,
  },
  modified: {
    color: palette.sound,
  },
  close: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  closeText: {
    color: palette.textMuted,
    fontSize: 16,
  },
  statusStrip: {
    height: 24,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: palette.hairline,
  },
  statusText: {
    flex: 1,
    color: palette.textFaint,
  },
  statusTextWarn: {
    color: palette.textMuted,
  },
  statusChevron: {
    color: palette.textFaint,
  },
  statusPopover: {
    position: 'absolute',
    zIndex: 40,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    borderRadius: 4,
    padding: 10,
    gap: 6,
  },
  statusPopoverHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  bodyShell: {
    flex: 1,
    minHeight: 0,
  },
  scroll: {
    flex: 1,
  },
  scrollBody: {
    paddingTop: 12,
    paddingBottom: 16,
    gap: 12,
  },
  scrollBodyStatic: {
    flexGrow: 1,
  },
  body: {
    gap: 12,
  },
  mixer: {
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairline,
    borderRadius: 4,
    padding: 10,
    gap: 0,
  },
  mixerTop: {
    flexDirection: 'row',
    gap: 14,
    minHeight: 0,
  },
  mixerWave: {
    flex: 1.25,
    minWidth: 0,
    gap: 2,
  },
  waveLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
  },
  waveLabel: {
    color: palette.textFaint,
    fontSize: 9,
  },
  waveNote: {
    color: palette.textFaint,
    fontSize: 10,
    lineHeight: 13,
  },
  mixerFaders: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-around',
    gap: 4,
  },
  mixerEmpty: {
    color: palette.textFaint,
    fontSize: 11,
    lineHeight: 16,
    flex: 1,
  },
  fader: {
    flex: 1,
    alignItems: 'center',
    gap: 2,
    minWidth: 0,
  },
  faderLabel: {
    color: palette.textMuted,
    fontSize: 11,
    lineHeight: 14,
    textAlign: 'center',
  },
  faderHit: {
    width: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  faderTrack: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: 20,
    width: 4,
    borderRadius: 2,
    backgroundColor: palette.track,
  },
  faderFill: {
    position: 'absolute',
    left: 20,
    width: 4,
    borderRadius: 2,
    backgroundColor: palette.sound,
  },
  faderCenter: {
    position: 'absolute',
    left: 14,
    width: 16,
    height: 1,
    backgroundColor: palette.hairlineStrong,
  },
  faderThumb: {
    position: 'absolute',
    left: 13,
    width: 18,
    height: 8,
    borderRadius: 2,
    backgroundColor: palette.text,
  },
  faderValue: {
    color: palette.textMuted,
    fontSize: 10,
    lineHeight: 13,
  },
  mixerBottom: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  mixerRegister: {
    flex: 1,
    minWidth: 0,
  },
  columns: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 14,
  },
  columnsStacked: {
    flexDirection: 'column',
    gap: 10,
  },
  column: {
    flex: 1,
    minWidth: 0,
    gap: 10,
  },
  group: {
    gap: 6,
  },
  groupLabel: {
    color: palette.textFaint,
  },
  param: {
    position: 'relative',
    justifyContent: 'space-between',
    paddingVertical: 3,
  },
  paramRaised: {
    zIndex: 30,
  },
  paramHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 6,
  },
  paramLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    flexShrink: 1,
    minWidth: 0,
  },
  paramValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    flexShrink: 0,
  },
  paramLabel: {
    color: palette.text,
    fontSize: 13,
    lineHeight: 16,
    flexShrink: 1,
  },
  helpButton: {
    width: 16,
    height: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    alignItems: 'center',
    justifyContent: 'center',
  },
  helpButtonOpen: {
    borderColor: palette.sound,
    backgroundColor: palette.soundSoft,
  },
  helpMark: {
    color: palette.textFaint,
    fontSize: 9,
    lineHeight: 11,
  },
  helpMarkOpen: {
    color: palette.sound,
  },
  paramValue: {
    color: palette.textMuted,
    fontSize: 11,
    lineHeight: 15,
    maxWidth: 110,
    textAlign: 'right',
  },
  resetButton: {
    width: 16,
    height: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  resetMark: {
    color: palette.sound,
    fontSize: 12,
  },
  helpPopover: {
    position: 'absolute',
    top: 46,
    left: 0,
    right: 0,
    zIndex: 50,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 6,
  },
  helpPopoverInline: {
    position: 'relative',
    top: 0,
    marginTop: 4,
  },
  helpText: {
    color: palette.textMuted,
    fontSize: 12,
    lineHeight: 17,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  stepButton: {
    borderRadius: 3,
    borderWidth: 1,
    borderColor: palette.hairline,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: palette.surface,
  },
  stepMark: {
    color: palette.textMuted,
    fontSize: 13,
  },
  sliderHit: {
    flex: 1,
    justifyContent: 'center',
    minWidth: 24,
  },
  sliderTrack: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.track,
  },
  sliderFill: {
    position: 'absolute',
    top: 0,
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.sound,
  },
  sliderAnchor: {
    position: 'absolute',
    top: -6,
    width: 1,
    height: 4,
    backgroundColor: palette.hairlineStrong,
  },
  sliderDefault: {
    position: 'absolute',
    top: -8,
    width: 3,
    height: 7,
    borderRadius: 1.5,
    backgroundColor: palette.sound,
  },
  sliderKnob: {
    position: 'absolute',
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: palette.text,
  },
  choiceField: {
    gap: 4,
    minWidth: 0,
  },
  choiceHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  choiceRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 5,
  },
  choice: {
    minHeight: 28,
    paddingHorizontal: 8,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: palette.surface,
  },
  choiceActive: {
    borderColor: palette.sound,
    backgroundColor: palette.soundSoft,
  },
  toggleWide: {
    alignSelf: 'flex-start',
    minWidth: 72,
  },
  choiceText: {
    color: palette.textMuted,
    fontSize: 11,
  },
  choiceTextActive: {
    color: palette.sound,
  },
  formStrip: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    minHeight: 64,
    paddingVertical: 4,
  },
  formTitle: {
    color: palette.textFaint,
    width: 42,
    paddingTop: 2,
  },
  formFields: {
    flex: 1,
    minWidth: 0,
    gap: 10,
  },
  formFieldsRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  formFieldsColumn: {
    flexDirection: 'column',
  },
  formField: {
    flex: 1,
    minWidth: 0,
  },
  paramFoot: {
    gap: 2,
  },
  paramDerived: {
    color: palette.textMuted,
  },
  paramHint: {
    color: palette.textFaint,
    fontSize: 11,
    lineHeight: 15,
  },
  footerFixed: {
    paddingTop: 8,
    paddingBottom: 8,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
  },
  footerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  primary: {
    minHeight: TOUCH_TARGET,
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: palette.sound,
  },
  primaryText: {
    color: palette.background,
  },
  footerPrimary: {
    flex: 1,
    marginTop: 0,
  },
  smallButton: {
    minHeight: 32,
    paddingHorizontal: 10,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: palette.surface,
  },
  smallButtonText: {
    color: palette.textMuted,
    fontSize: 12,
  },
  disabled: {
    opacity: 0.35,
  },
  note: {
    color: palette.textFaint,
    fontSize: 12,
    lineHeight: 17,
  },
  profileTab: {
    width: '100%',
    maxWidth: 560,
    alignSelf: 'center',
    gap: 10,
  },
  profileList: {
    gap: 6,
  },
  profileRow: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
  },
  profileRowActive: {
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surfaceActive,
  },
  profileRowText: {
    flex: 1,
    minWidth: 0,
    gap: 2,
  },
  profileMeta: {
    color: palette.textFaint,
  },
  activeMark: {
    color: palette.sound,
  },
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6,
  },
  editor: {
    gap: 6,
  },
  input: {
    height: 40,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surface,
    color: palette.text,
    paddingHorizontal: 10,
    fontSize: 14,
  },
  notice: {
    color: palette.sound,
    fontSize: 12,
  },
  footNote: {
    color: palette.textFaint,
    fontSize: 11,
    lineHeight: 16,
  },
});
