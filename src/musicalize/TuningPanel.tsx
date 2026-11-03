import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Animated,
  Modal,
  PanResponder,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
  useWindowDimensions,
} from 'react-native';
import * as Haptics from 'expo-haptics';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  DEFAULT_PROFILE_ID,
  PARAM_FIELDS,
  PARAM_GROUPS,
  effectiveBpm,
  paramValueText,
  stepValue,
  warningsFor,
  type ParamsFieldSchema,
  type SonifyParams,
} from './params';
import { copyCurrentLink, linkSupported } from './link';
import { WIDE_BREAKPOINT, palette, TOUCH_TARGET } from './palette';
import { useTuning } from './tuning';
import { type } from './type';

export const DRAWER_WIDTH = 380;

type Props = {
  baseBpm?: number;
  variant?: string;
};

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

function changedCount(params: SonifyParams): number {
  return PARAM_FIELDS.filter((field) => params[field.key] !== field.default).length;
}

function paramSummary(params: SonifyParams): string {
  const count = changedCount(params);
  return count === 0 ? 'Default' : `${count} thay đổi`;
}

/** One knob. Drag, tap, arrow keys, and accessibility actions share one value. */
function ParamSlider({
  field,
  value,
  derived,
  hint,
  onChange,
  onComplete,
}: {
  field: ParamsFieldSchema;
  value: number;
  derived?: string;
  hint?: string | null;
  onChange: (value: number) => void;
  onComplete: (value: number) => void;
}) {
  const [width, setWidth] = useState(0);
  const widthRef = useRef(0);
  const valueRef = useRef(value);
  const latest = useRef(value);
  const onChangeRef = useRef(onChange);
  const onCompleteRef = useRef(onComplete);
  valueRef.current = value;
  latest.current = value;
  onChangeRef.current = onChange;
  onCompleteRef.current = onComplete;

  const commit = useCallback(
    (next: number) => {
      latest.current = next;
      onChangeRef.current(next);
    },
    [],
  );

  const fromX = useCallback(
    (x: number) => {
      const track = widthRef.current;
      if (track <= 0) return;
      const ratio = clamp(x / track, 0, 1);
      commit(stepValue(field, field.min + ratio * (field.max - field.min)));
    },
    [commit, field],
  );

  const responder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: (event) => {
          fromX(event.nativeEvent.locationX);
        },
        onPanResponderMove: (event) => {
          fromX(event.nativeEvent.locationX);
        },
        onPanResponderRelease: () => {
          onCompleteRef.current(latest.current);
        },
        onPanResponderTerminate: () => {
          onCompleteRef.current(latest.current);
        },
      }),
    [fromX],
  );

  const nudge = useCallback(
    (direction: 1 | -1) => {
      const next = stepValue(field, valueRef.current + direction * field.step);
      commit(next);
      onCompleteRef.current(next);
    },
    [commit, field],
  );

  const ratio = clamp((value - field.min) / (field.max - field.min), 0, 1);
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
              commit(field.min);
              onCompleteRef.current(field.min);
              event.preventDefault?.();
            } else if (event.key === 'End') {
              commit(field.max);
              onCompleteRef.current(field.max);
              event.preventDefault?.();
            }
          },
        } as Record<string, unknown>)
      : {};

  return (
    <View style={styles.param}>
      <View style={styles.paramHead}>
        <Text style={[type.sans, styles.paramLabel]}>{field.label}</Text>
        <Text style={[type.mono, styles.paramValue]}>{paramValueText(field, value)}</Text>
      </View>
      <View
        {...webProps}
        {...responder.panHandlers}
        onLayout={(event) => {
          const next = event.nativeEvent.layout.width;
          widthRef.current = next;
          setWidth(next);
        }}
        style={styles.sliderHit}
        focusable
        accessible
        accessibilityRole="adjustable"
        accessibilityLabel={field.label}
        accessibilityValue={{
          min: field.min,
          max: field.max,
          now: value,
          text: paramValueText(field, value),
        }}
        accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
        onAccessibilityAction={(event) => {
          if (event.nativeEvent.actionName === 'increment') nudge(1);
          if (event.nativeEvent.actionName === 'decrement') nudge(-1);
        }}
      >
        <View style={styles.sliderTrack}>
          <View style={[styles.sliderFill, { width: `${Math.round(ratio * 100)}%` }]} />
          <View
            style={[
              styles.sliderKnob,
              { left: Math.max(0, Math.min(width - 12, width * ratio - 6)) },
            ]}
          />
        </View>
      </View>
      {derived || hint ? (
        <View style={styles.paramFoot}>
          {derived ? <Text style={[type.monoSmall, styles.paramDerived]}>{derived}</Text> : null}
          {hint ? <Text style={[type.sans, styles.paramHint]}>{hint}</Text> : null}
        </View>
      ) : null}
    </View>
  );
}

function TuningTab({
  baseBpm,
  variant,
  autoPreview,
  onAutoPreview,
}: {
  baseBpm: number;
  variant?: string;
  autoPreview: boolean;
  onAutoPreview: (value: boolean) => void;
}) {
  const {
    profile,
    params,
    dirty,
    commit,
    revert,
    saveChanges,
    setParam,
  } = useTuning();
  const bpm = effectiveBpm(baseBpm, params.tempo);
  const warnings = warningsFor(params);
  const highHumanize = warnings.some((warning) => warning.code === 'high_humanize');
  const highBreath = warnings.some((warning) => warning.code === 'high_breath');
  const guitarLow = variant === 'guitar' && bpm < 90;

  const finish = (key: string, value: number) => {
    if (!autoPreview) return;
    void Haptics.selectionAsync().catch(() => undefined);
    commit({ ...params, [key]: value }, true);
  };

  return (
    <>
      <View style={styles.profileLine}>
        <Text style={[type.sans, styles.profileName]} numberOfLines={1}>
          {profile.name}
        </Text>
        {dirty ? <Text style={[type.monoSmall, styles.modified]}>• đã sửa</Text> : null}
      </View>
      <View style={styles.actionRow}>
        <SmallButton label="Lưu" onPress={saveChanges} disabled={!dirty} />
        <SmallButton label="Hoàn tác" onPress={revert} disabled={!dirty} />
        <View style={{ flex: 1 }} />
        <View style={styles.autoRow}>
          <Text style={[type.sans, styles.autoLabel]}>Nghe thử</Text>
          <Switch
            value={autoPreview}
            onValueChange={onAutoPreview}
            trackColor={{ false: palette.track, true: palette.sound }}
            thumbColor={palette.text}
            accessibilityLabel="Nghe thử tự động"
          />
        </View>
      </View>
      {profile.id === DEFAULT_PROFILE_ID && dirty ? (
        <Text style={[type.sans, styles.note]}>
          Default bất biến. Lưu sẽ tạo một bản sao có tên.
        </Text>
      ) : null}

      {PARAM_GROUPS.map((group) => (
        <View key={group.id} style={styles.group}>
          <Text style={[type.section, styles.groupLabel]}>{group.label}</Text>
          {group.fields.map((field) => {
            const value = params[field.key];
            const isTempo = field.key === 'tempo';
            const derived = isTempo ? `${bpm} BPM` : undefined;
            const hint =
              isTempo && guitarLow
                ? 'Dưới ngưỡng tremolo'
                : field.key === 'humanize' && highHumanize
                  ? 'Trên 1.10 dễ làm phẳng contour'
                  : field.key === 'breath' && highBreath
                    ? 'Trên 1.20 đã chạm trần câu'
                    : null;
            return (
              <ParamSlider
                key={field.key}
                field={field}
                value={value}
                derived={derived}
                hint={hint}
                onChange={(next) => setParam(field.key, next)}
                onComplete={(next) => finish(field.key, next)}
              />
            );
          })}
        </View>
      ))}

    </>
  );
}

function ProfileTab() {
  const {
    store,
    profile,
    params,
    dirty,
    heardDirty,
    select,
    commit,
    saveChanges,
    addProfile,
    duplicate,
    rename,
    remove,
    reset,
    importProfiles,
    exportProfiles,
    setOpen,
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
    <>
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
                  {paramSummary(item.params)}
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
          label="Reset"
          onPress={() => reset(profile.id)}
          disabled={profile.id === DEFAULT_PROFILE_ID}
        />
        <SmallButton label="Lưu thay đổi" onPress={saveChanges} disabled={!dirty} />
      </View>

      <Pressable
        onPress={() => {
          commit(params, true);
          setOpen(false);
        }}
        style={styles.primary}
        accessibilityRole="button"
        accessibilityLabel="Dùng profile này"
      >
        <Text style={[type.section, styles.primaryText]}>
          {heardDirty ? 'Dùng profile này' : 'Nghe lại profile này'}
        </Text>
      </Pressable>

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
        Profile lưu trên máy. Tên không đi vào hash hay URL.
      </Text>
    </>
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

export function TuningPanel({ baseBpm, variant }: Props) {
  const { enabled, open, setOpen, params, commit } = useTuning();
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const wide = width >= WIDE_BREAKPOINT;
  const [rendered, setRendered] = useState(open);
  const [tab, setTab] = useState<'tune' | 'profile'>('tune');
  const [autoPreview, setAutoPreview] = useState(true);
  const [snap, setSnap] = useState<'half' | 'full'>('half');
  const drawerX = useRef(new Animated.Value(DRAWER_WIDTH)).current;
  const sheetHeight = Math.max(260, Math.round(height * 0.88));
  const halfOffset = Math.max(0, sheetHeight - Math.round(height * 0.48));
  const sheetY = useRef(new Animated.Value(halfOffset)).current;
  const dragStart = useRef(halfOffset);

  useEffect(() => {
    if (open) {
      setRendered(true);
      if (!wide) setSnap('half');
    }
  }, [open, wide]);

  useEffect(() => {
    if (wide) {
      Animated.timing(drawerX, {
        toValue: open ? 0 : DRAWER_WIDTH,
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
  }, [drawerX, halfOffset, open, sheetHeight, sheetY, snap, wide]);

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

  const content = (
    <>
      <View style={styles.header}>
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
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollBody}
        keyboardShouldPersistTaps="handled"
      >
        {tab === 'tune' ? (
          <TuningTab
            baseBpm={baseBpm}
            variant={variant}
            autoPreview={autoPreview}
            onAutoPreview={setAutoPreview}
          />
        ) : (
          <ProfileTab />
        )}
      </ScrollView>
      {tab === 'tune' ? (
        <View style={styles.footerFixed}>
          <Pressable
            onPress={() => {
              commit(params, true);
              setOpen(false);
            }}
            style={styles.primary}
            accessibilityRole="button"
            accessibilityLabel="Nghe bản này"
          >
            <Text style={[type.section, styles.primaryText]}>Nghe bản này</Text>
          </Pressable>
        </View>
      ) : null}
    </>
  );

  const drawer = (
    <Animated.View
      style={[
        styles.drawer,
        {
          paddingTop: insets.top + 8,
          paddingBottom: insets.bottom,
          transform: [{ translateX: drawerX }],
        },
      ]}
    >
      {content}
    </Animated.View>
  );

  // Push mode keeps the chart live: no Modal and no tap-catching layer. The
  // drawer sits in the reserved gutter, so the chart can still be used.
  if (wide && width >= 1280) {
    return rendered ? drawer : null;
  }

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
          style={StyleSheet.absoluteFill}
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
    width: DRAWER_WIDTH,
    backgroundColor: palette.panel,
    borderLeftWidth: 1,
    borderLeftColor: palette.hairlineStrong,
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
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: palette.hairline,
  },
  tabs: {
    flexDirection: 'row',
    gap: 16,
  },
  tab: {
    minHeight: TOUCH_TARGET,
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
  scroll: {
    flex: 1,
  },
  scrollBody: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 24,
    gap: 10,
  },
  profileLine: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 8,
    minHeight: 24,
  },
  profileName: {
    color: palette.text,
    flexShrink: 1,
  },
  modified: {
    color: palette.sound,
  },
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6,
  },
  smallButton: {
    minHeight: 34,
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
  autoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  autoLabel: {
    color: palette.textFaint,
    fontSize: 12,
  },
  note: {
    color: palette.textFaint,
    fontSize: 12,
    lineHeight: 17,
  },
  group: {
    marginTop: 8,
    gap: 6,
  },
  groupLabel: {
    color: palette.textFaint,
    marginBottom: 2,
  },
  param: {
    gap: 5,
    paddingVertical: 3,
  },
  paramHead: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
  },
  paramLabel: {
    color: palette.text,
    fontSize: 13,
  },
  paramValue: {
    color: palette.textMuted,
    fontSize: 12,
  },
  sliderHit: {
    height: 34,
    justifyContent: 'center',
  },
  sliderTrack: {
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.track,
    overflow: 'visible',
  },
  sliderFill: {
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.sound,
  },
  sliderKnob: {
    position: 'absolute',
    top: -4,
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: palette.text,
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
  primary: {
    minHeight: TOUCH_TARGET,
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: palette.sound,
    marginTop: 8,
  },
  primaryText: {
    color: palette.background,
  },
  footer: {
    marginTop: 4,
  },
  footerFixed: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 8,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
  },
  profileList: {
    gap: 6,
    paddingBottom: 6,
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
