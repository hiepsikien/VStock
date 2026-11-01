import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Path, Rect } from 'react-native-svg';
import {
  ENSEMBLE_ROWS,
  type RecapEnsemble,
  type RecapVariant,
} from '../api/client';
import { clockText, GENRES, STREAM_GENRES, type StreamVariant } from './labels';
import { OptionsPopover } from './OptionsPopover';
import { palette, TOUCH_TARGET } from './palette';
import { Timeline } from './Scrubber';
import { type } from './type';

type Scrub = {
  label: string;
  progress: number;
  time: number;
  duration: number;
  peaks?: number[] | null;
};

type ReplayProps = {
  mode: 'replay';
  variant: RecapVariant;
  ensemble: RecapEnsemble;
  humanize: boolean;
  colorOn: boolean;
  playing: boolean;
  /** The work has ended. Nghe lại restarts it; Nghe stays quiet. */
  finished?: boolean;
  composing: boolean;
  timeline: Scrub | null;
  chapterLabel?: string | null;
  chapterIndex?: number;
  chapterCount?: number;
  onVariant: (variant: RecapVariant) => void;
  onEnsemble: (ensemble: RecapEnsemble) => void;
  onHumanize: (value: boolean) => void;
  onColor: (value: boolean) => void;
  onPlay: () => void;
  onPause: () => void;
  onReplay: () => void;
  onTimeline: (ratio: number) => void;
  status?: string | null;
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
  humanize,
  colorOn,
  playing,
  finished = false,
  composing,
  timeline,
  chapterLabel,
  chapterIndex,
  chapterCount,
  onVariant,
  onEnsemble,
  onHumanize,
  onColor,
  onPlay,
  onPause,
  onReplay,
  onTimeline,
  status,
}: ReplayProps) {
  const [optionsOpen, setOptionsOpen] = useState(false);
  const shelf = ENSEMBLE_ROWS[variant];
  return (
    <>
      <View style={styles.shelf}>
        {GENRES.map((item) => {
          const active = item.id === variant;
          return (
            <Pressable
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
              {active ? <View style={styles.tileRule} /> : null}
            </Pressable>
          );
        })}
      </View>

      <View style={styles.shelfRow}>
        <View style={styles.shelfLinks}>
          {shelf.map((item) => {
            const active = item.id === ensemble;
            return (
              <Pressable
                key={item.id}
                onPress={() => onEnsemble(item.id)}
                hitSlop={6}
                style={styles.shelfLink}
                accessibilityRole="button"
                accessibilityLabel={item.label}
                accessibilityState={{ selected: active }}
              >
                <Text style={[type.sans, styles.shelfLinkText, active && styles.shelfLinkTextActive]}>
                  {item.label}
                </Text>
                <View style={[styles.shelfLinkRule, active && styles.shelfLinkRuleActive]} />
              </Pressable>
            );
          })}
        </View>
        <Pressable
          onPress={() => setOptionsOpen(true)}
          hitSlop={6}
          style={styles.gear}
          accessibilityRole="button"
          accessibilityLabel="Tùy chọn nghe"
          accessibilityState={{ expanded: optionsOpen }}
        >
          <View style={styles.gearDot} />
          <View style={styles.gearDot} />
          <View style={styles.gearDot} />
        </Pressable>
      </View>

      <View style={styles.transport}>
        <Pressable
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
        </Pressable>

        <Pressable
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
        </Pressable>

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

      <OptionsPopover
        visible={optionsOpen}
        onClose={() => setOptionsOpen(false)}
        humanize={humanize}
        colorOn={colorOn}
        onHumanize={onHumanize}
        onColor={onColor}
      />
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
            <Pressable
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
              {active ? <View style={styles.tileRule} /> : null}
            </Pressable>
          );
        })}
      </View>

      <View style={styles.transport}>
        <Pressable
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
        </Pressable>
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
  shelfLinks: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 12,
    flex: 1,
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
  shelfLinkRuleActive: {
    backgroundColor: palette.hairlineStrong,
  },
  gear: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 3,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
  },
  gearDot: {
    width: 3,
    height: 3,
    borderRadius: 2,
    backgroundColor: palette.textMuted,
  },
  transport: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: 4,
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
});
