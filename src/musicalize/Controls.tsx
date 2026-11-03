import React from 'react';
import { StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import Svg, { Path, Rect } from 'react-native-svg';
import {
  ENSEMBLE_ROWS,
  type DfiBreakdown,
  type DfiSignature,
  type RecapEnsemble,
  type RecapVariant,
} from '../api/client';
import { clockText, GENRES, dfiPillText, STREAM_GENRES, type StreamVariant } from './labels';
import { MotionPressable, RiseRule } from './motion';
import { palette, TOUCH_TARGET, WIDE_BREAKPOINT } from './palette';
import { Timeline, type TimelinePart } from './Scrubber';
import { type } from './type';
import { TuningTrigger } from './TuningPanel';

type Scrub = {
  label: string;
  progress: number;
  time: number;
  duration: number;
  parts?: TimelinePart[] | null;
  peaks?: number[] | null;
};

type ReplayProps = {
  mode: 'replay';
  variant: RecapVariant;
  ensemble: RecapEnsemble;
  playing: boolean;
  /** The work has ended. Nghe lại restarts it; Nghe stays quiet. */
  finished?: boolean;
  composing: boolean;
  muted?: boolean;
  timeline: Scrub | null;
  chapterLabel?: string | null;
  chapterIndex?: number;
  chapterCount?: number;
  onVariant: (variant: RecapVariant) => void;
  onEnsemble: (ensemble: RecapEnsemble) => void;
  onPlay: () => void;
  onPause: () => void;
  onReplay: () => void;
  abSide?: 'A' | 'B';
  onAB?: (side: 'A' | 'B') => void;
  onMute?: () => void;
  onTimeline: (ratio: number) => void;
  status?: string | null;
  /** Brief confirmation from the tuning layer. */
  notice?: string | null;
  /** The unmodified BPM, so the trigger can hide when no panel can render. */
  tuningBaseBpm?: number;
  /** Data fidelity of the piece being heard. */
  dfi?: DfiBreakdown | null;
  /** Corpus median for the active genre/ensemble, when the artifact exists. */
  dfiSignature?: DfiSignature | null;
  onDfi?: () => void;
};

type LiveProps = {
  mode: 'live';
  variant: StreamVariant;
  playing: boolean;
  onVariant: (variant: StreamVariant) => void;
  onPlay: () => void;
  onPause: () => void;
  status?: string | null;
};

const MOTIF: Record<RecapVariant, string> = {
  symphony: '■',
  jazz: '●',
  minimalist: '▤',
  ambient: '○',
  guitar: '≈',
};

/** Spectrum width in px. Percent strings are unreliable on native. */
const DFI_TRACK_WIDTH = 84;

export function Controls(props: ReplayProps | LiveProps) {
  return (
    <View style={styles.wrap}>
      {props.mode === 'replay' ? <ReplayControls {...props} /> : <LiveControls {...props} />}
    </View>
  );
}

function ReplayControls({
  variant,
  ensemble,
  playing,
  finished = false,
  composing,
  muted = false,
  timeline,
  chapterLabel,
  chapterIndex,
  chapterCount,
  onVariant,
  onEnsemble,
  onPlay,
  onPause,
  onReplay,
  onMute,
  abSide,
  onAB,
  onTimeline,
  status,
  notice,
  tuningBaseBpm,
  dfi = null,
  dfiSignature = null,
  onDfi,
}: ReplayProps) {
  const shelf = ENSEMBLE_ROWS[variant];
  const wide = useWindowDimensions().width >= WIDE_BREAKPOINT;

  return (
    <>
      <View style={styles.shelf}>
        {GENRES.map((item) => {
          const active = item.id === variant;
          return (
            <MotionPressable
              key={item.id}
              onPress={() => onVariant(item.id)}
              style={[styles.tile, active && styles.tileActive]}
              accessibilityRole="button"
              accessibilityLabel={item.label}
              accessibilityState={{ selected: active }}
            >
              <Text style={[styles.motif, active && styles.motifActive]}>{MOTIF[item.id]}</Text>
              <Text style={[type.sans, styles.tileText, active && styles.tileTextActive]} numberOfLines={1}>
                {item.label}
              </Text>
              {active ? <RiseRule style={styles.tileRule} /> : null}
            </MotionPressable>
          );
        })}
      </View>

      <View style={styles.shelfRow}>
        <View style={[styles.shelfLinks, wide && styles.shelfLinksWide]}>
          {shelf.map((item) => {
            const active = item.id === ensemble;
            return (
              <MotionPressable
                key={item.id}
                onPress={() => onEnsemble(item.id)}
                hitSlop={6}
                style={styles.shelfLink}
                accessibilityRole="button"
                accessibilityLabel={item.label}
                accessibilityState={{ selected: active }}
              >
                <Text style={[type.sans, styles.shelfLinkText, active && styles.shelfLinkTextActive]}>
                  {active && dfi ? `${item.label} · ${Math.round(dfi.score)}` : item.label}
                </Text>
                {active ? <RiseRule color={palette.hairlineStrong} style={styles.shelfLinkRule} /> : null}
              </MotionPressable>
            );
          })}
        </View>
        <MotionPressable
          onPress={onDfi}
          disabled={!onDfi}
          hitSlop={6}
          style={styles.dfiSpectrum}
          accessibilityRole={onDfi ? 'button' : 'text'}
          accessibilityLabel={
            dfi
              ? `Độ trung thực dữ liệu ${Math.round(dfi.score)} trên 100${dfiSignature ? `, chuẩn ${Math.round(dfiSignature.score)}` : ''}`
              : 'Chưa đủ mẫu để đo độ trung thực dữ liệu'
          }
        >
          <View style={styles.dfiTrack}>
            <View
              style={[
                styles.dfiFill,
                { width: Math.round(DFI_TRACK_WIDTH * Math.max(0, Math.min(1, (dfi?.score ?? 0) / 100))) },
              ]}
            />
            {dfiSignature ? (
              <View
                style={[
                  styles.dfiMark,
                  {
                    left:
                      Math.round(DFI_TRACK_WIDTH * Math.max(0, Math.min(1, dfiSignature.score / 100))) -
                      1,
                  },
                ]}
              />
            ) : null}
          </View>
          <Text style={[type.monoSmall, styles.dfiSpectrumText]}>
            {dfiPillText(dfi?.score, dfi?.confidence)}
          </Text>
        </MotionPressable>
        <TuningTrigger available={tuningBaseBpm != null} />
      </View>

      <View style={styles.transport}>
        <View style={styles.playWrap}>
          {playing ? <View pointerEvents="none" style={styles.playHalo} /> : null}
          <MotionPressable
            onPress={playing ? onPause : onPlay}
            disabled={composing || (finished && !playing)}
            style={[styles.play, (composing || (finished && !playing)) && styles.playDisabled]}
            accessibilityRole="button"
            accessibilityLabel={playing ? 'Tạm dừng' : 'Nghe'}
          >
            {playing ? (
              <Svg width={16} height={18} viewBox="0 0 16 18">
                <Rect x={1} y={0} width={5} height={18} rx={1} fill={palette.background} />
                <Rect x={10} y={0} width={5} height={18} rx={1} fill={palette.background} />
              </Svg>
            ) : (
              <Svg width={16} height={18} viewBox="0 0 16 18">
                <Path d="M1 1 L15 9 L1 17 Z" fill={palette.background} />
              </Svg>
            )}
          </MotionPressable>
        </View>

        <MotionPressable
          onPress={onReplay}
          hitSlop={4}
          style={styles.replay}
          accessibilityRole="button"
          accessibilityLabel="Nghe lại"
        >
          <Svg width={20} height={20} viewBox="0 0 20 20">
            <Path
              d="M16 10a6 6 0 1 1-1.76-4.24"
              fill="none"
              stroke={palette.textMuted}
              strokeWidth={1.6}
              strokeLinecap="round"
            />
            <Path
              d="M16.4 1.6v4h-4"
              fill="none"
              stroke={palette.textMuted}
              strokeWidth={1.6}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </Svg>
        </MotionPressable>

        {onAB ? (
          <View style={styles.abGroup}>
            {(['A', 'B'] as const).map((side) => (
              <MotionPressable
                key={side}
                onPress={() => onAB(side)}
                hitSlop={4}
                style={[styles.abButton, abSide === side && styles.abButtonActive]}
                accessibilityRole="button"
                accessibilityLabel={`Nghe bản ${side}`}
                accessibilityState={{ selected: abSide === side }}
              >
                <Text style={[type.monoSmall, styles.abText, abSide === side && styles.abTextActive]}>
                  {side}
                </Text>
              </MotionPressable>
            ))}
          </View>
        ) : null}

        {onMute ? (
          <MotionPressable
            onPress={onMute}
            hitSlop={6}
            style={styles.mute}
            accessibilityRole="button"
            accessibilityLabel={muted ? 'Bật tiếng' : 'Tắt tiếng'}
            accessibilityState={{ selected: muted }}
          >
            <Svg width={16} height={16} viewBox="0 0 16 16">
              <Path
                d="M2 6h2.5L8 3.2v9.6L4.5 10H2z"
                fill="none"
                stroke={muted ? palette.textFaint : palette.textMuted}
                strokeWidth={1.4}
                strokeLinejoin="round"
              />
              {muted ? (
                <Path
                  d="M10.4 6.2l3.2 3.6M13.6 6.2l-3.2 3.6"
                  fill="none"
                  stroke={palette.textFaint}
                  strokeWidth={1.4}
                  strokeLinecap="round"
                />
              ) : (
                <>
                  <Path
                    d="M10 6.1a2.7 2.7 0 0 1 0 3.8"
                    fill="none"
                    stroke={palette.textMuted}
                    strokeWidth={1.4}
                    strokeLinecap="round"
                  />
                  <Path
                    d="M11.9 4.4a5 5 0 0 1 0 7.2"
                    fill="none"
                    stroke={palette.textMuted}
                    strokeWidth={1.4}
                    strokeLinecap="round"
                  />
                </>
              )}
            </Svg>
          </MotionPressable>
        ) : null}

        <View style={styles.clock}>
          <Text style={[type.mono, styles.clockNow]}>
            {timeline ? clockText(timeline.time, timeline.duration) : '0:00'}
          </Text>
          <Text style={[type.monoSmall, styles.clockTotal]}>
            {timeline ? `/ ${clockText(timeline.duration, timeline.duration)}` : '/ 0:00'}
          </Text>
        </View>

        {status ? (
          <Text style={[type.sans, styles.transportStatus]} numberOfLines={1}>
            {status}
          </Text>
        ) : null}

        {notice ? (
          <Text style={[type.sans, styles.tuningNotice]} numberOfLines={1}>
            {notice}
          </Text>
        ) : null}

        {chapterLabel ? (
          <View style={styles.chapter}>
            <Text style={[type.section, styles.chapterName]} numberOfLines={1}>
              {chapterLabel}
            </Text>
            {chapterCount && chapterCount > 1 ? (
              <Text style={[type.monoSmall, styles.chapterIndex]}>
                {Math.min(chapterCount, (chapterIndex ?? 0) + 1)}/{chapterCount}
              </Text>
            ) : null}
          </View>
        ) : null}
      </View>

      {timeline ? <Timeline {...timeline} onRatio={onTimeline} /> : null}
    </>
  );
}

function LiveControls({ variant, playing, onVariant, onPlay, onPause, status }: LiveProps) {
  return (
    <>
      <View style={styles.shelf}>
        {STREAM_GENRES.map((item) => {
          const active = item.id === variant;
          return (
            <MotionPressable
              key={item.id}
              onPress={() => onVariant(item.id)}
              style={[styles.tile, active && styles.tileActive]}
              accessibilityRole="button"
              accessibilityLabel={item.label}
              accessibilityState={{ selected: active }}
            >
              <Text style={[styles.motif, active && styles.motifActive]}>{MOTIF[item.id]}</Text>
              <Text style={[type.sans, styles.tileText, active && styles.tileTextActive]} numberOfLines={1}>
                {item.label}
              </Text>
              {active ? <RiseRule style={styles.tileRule} /> : null}
            </MotionPressable>
          );
        })}
      </View>

      <View style={styles.transport}>
        <View style={styles.playWrap}>
          {playing ? <View pointerEvents="none" style={styles.playHalo} /> : null}
          <MotionPressable
            onPress={playing ? onPause : onPlay}
            style={styles.play}
            accessibilityRole="button"
            accessibilityLabel={playing ? 'Tạm dừng' : 'Nghe đài'}
          >
            {playing ? (
              <Svg width={16} height={18} viewBox="0 0 16 18">
                <Rect x={1} y={0} width={5} height={18} rx={1} fill={palette.background} />
                <Rect x={10} y={0} width={5} height={18} rx={1} fill={palette.background} />
              </Svg>
            ) : (
              <Svg width={16} height={18} viewBox="0 0 16 18">
                <Path d="M1 1 L15 9 L1 17 Z" fill={palette.background} />
              </Svg>
            )}
          </MotionPressable>
        </View>
        <Text style={[type.section, styles.liveHint]}>
          {playing ? 'Đang thu tín hiệu' : 'Chọn đài rồi bấm nghe'}
        </Text>
        {status ? (
          <Text style={[type.sans, styles.transportStatus]} numberOfLines={1}>
            {status}
          </Text>
        ) : null}
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 6,
    backgroundColor: palette.panel,
  },
  shelf: {
    flexDirection: 'row',
    gap: 8,
  },
  tile: {
    flex: 1,
    height: 56,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
    paddingHorizontal: 4,
  },
  tileActive: {
    backgroundColor: palette.surfaceActive,
    borderColor: palette.hairlineStrong,
  },
  motif: {
    color: palette.textFaint,
    fontSize: 10,
    lineHeight: 14,
  },
  motifActive: {
    color: palette.sound,
  },
  tileText: {
    color: palette.textMuted,
    fontSize: 13,
    lineHeight: 18,
  },
  tileTextActive: {
    color: palette.text,
  },
  tileRule: {
    position: 'absolute',
    left: 10,
    right: 10,
    bottom: 0,
    height: 3,
    borderTopLeftRadius: 2,
    borderTopRightRadius: 2,
    backgroundColor: palette.sound,
  },
  shelfRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 34,
    marginTop: 0,
  },
  dfiSpectrum: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 4,
    height: 28,
  },
  dfiTrack: {
    width: DFI_TRACK_WIDTH,
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
    backgroundColor: palette.track,
  },
  dfiFill: {
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.sound,
  },
  dfiMark: {
    position: 'absolute',
    top: -2,
    width: 2,
    height: 8,
    backgroundColor: palette.textMuted,
  },
  dfiSpectrumText: {
    color: palette.textMuted,
    fontVariant: ['tabular-nums'],
    minWidth: 38,
  },
  shelfLinks: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  shelfLinksWide: {
    flexWrap: 'nowrap',
    overflow: 'hidden',
    minWidth: 0,
  },
  shelfLink: {
    paddingVertical: 4,
  },
  shelfLinkText: {
    color: palette.textFaint,
    fontSize: 13,
  },
  shelfLinkTextActive: {
    color: palette.text,
  },
  shelfLinkRule: {
    height: 1,
    marginTop: 3,
    backgroundColor: 'transparent',
  },
  abGroup: {
    flexDirection: 'row',
    gap: 4,
    marginLeft: 4,
  },
  abButton: {
    minWidth: 26,
    height: 26,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
    alignItems: 'center',
    justifyContent: 'center',
  },
  abButtonActive: {
    borderColor: palette.sound,
    backgroundColor: palette.soundSoft,
  },
  abText: {
    color: palette.textMuted,
  },
  abTextActive: {
    color: palette.sound,
  },
  mute: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: palette.hairline,
  },
  transport: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: 4,
  },
  playWrap: {
    width: 56,
    height: 56,
    alignItems: 'center',
    justifyContent: 'center',
  },
  playHalo: {
    position: 'absolute',
    left: -4,
    top: -4,
    width: 64,
    height: 64,
    borderRadius: 32,
    borderWidth: 1,
    borderColor: palette.soundSoft,
  },
  play: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: palette.sound,
  },
  playDisabled: {
    opacity: 0.35,
  },
  replay: {
    width: TOUCH_TARGET,
    height: TOUCH_TARGET,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: palette.hairline,
  },
  clock: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 4,
  },
  clockNow: {
    color: palette.text,
  },
  clockTotal: {
    color: palette.textFaint,
  },
  chapter: {
    flex: 1,
    alignItems: 'flex-end',
  },
  chapterName: {
    color: palette.textFaint,
  },
  chapterIndex: {
    color: palette.textMuted,
    marginTop: 2,
  },
  liveHint: {
    color: palette.textFaint,
  },
  transportStatus: {
    color: palette.textMuted,
    flexShrink: 1,
    fontSize: 12,
    lineHeight: 16,
  },
  tuningNotice: {
    color: palette.sound,
    flexShrink: 1,
    fontSize: 12,
    lineHeight: 16,
  },
});
