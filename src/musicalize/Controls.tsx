import React, { useState } from 'react';
import { Pressable, StyleSheet, Switch, Text, View } from 'react-native';
import {
  ENSEMBLE_ROWS,
  type RecapEnsemble,
  type RecapVariant,
} from '../api/client';
import { GENRES, STREAM_GENRES, type StreamVariant } from './labels';
import { palette } from './palette';
import { FlatScrubber, PeakScrubber } from './Scrubber';

type Scrub = {
  progress: number;
  time: number;
  duration: number;
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
  fileScrub: (Scrub & { peaks: number[] }) | null;
  movementScrub: Scrub | null;
  workScrub: Scrub | null;
  onVariant: (variant: RecapVariant) => void;
  onEnsemble: (ensemble: RecapEnsemble) => void;
  onHumanize: (value: boolean) => void;
  onColor: (value: boolean) => void;
  onPlay: () => void;
  onPause: () => void;
  onReplay: () => void;
  onFileScrub: (ratio: number) => void;
  onMovementScrub: (ratio: number) => void;
  onWorkScrub: (ratio: number) => void;
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

export function Controls(props: ReplayProps | LiveProps) {
  return (
    <View style={styles.wrap}>
      {props.mode === 'replay' ? <ReplayControls {...props} /> : <LiveControls {...props} />}
      {props.status ? <Text style={styles.status}>{props.status}</Text> : null}
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
  fileScrub,
  movementScrub,
  workScrub,
  onVariant,
  onEnsemble,
  onHumanize,
  onColor,
  onPlay,
  onPause,
  onReplay,
  onFileScrub,
  onMovementScrub,
  onWorkScrub,
}: ReplayProps) {
  const [optionsOpen, setOptionsOpen] = useState(false);
  const shelf = ENSEMBLE_ROWS[variant];
  return (
    <View>
      <ChipRow
        items={GENRES.map((item) => ({ id: item.id, label: item.label }))}
        selected={variant}
        onSelect={(id) => onVariant(id as RecapVariant)}
        large
      />
      <ChipRow
        items={shelf.map((item) => ({ id: item.id, label: item.label }))}
        selected={ensemble}
        onSelect={(id) => onEnsemble(id as RecapEnsemble)}
      />
      <View style={styles.transport}>
        <TransportButton
          label="Nghe"
          active={!playing && !finished}
          disabled={composing || finished}
          onPress={onPlay}
        />
        <TransportButton label="Tạm dừng" active={playing} disabled={!playing && !composing} onPress={onPause} />
        <TransportButton label="Nghe lại" onPress={onReplay} />
      </View>
      {fileScrub ? (
        <PeakScrubber
          peaks={fileScrub.peaks}
          progress={fileScrub.progress}
          time={fileScrub.time}
          duration={fileScrub.duration}
          onRatio={onFileScrub}
        />
      ) : null}
      {movementScrub ? (
        <FlatScrubber
          label="Chương"
          progress={movementScrub.progress}
          time={movementScrub.time}
          duration={movementScrub.duration}
          onRatio={onMovementScrub}
        />
      ) : null}
      {workScrub ? (
        <FlatScrubber
          label="Tác phẩm"
          progress={workScrub.progress}
          time={workScrub.time}
          duration={workScrub.duration}
          onRatio={onWorkScrub}
        />
      ) : null}
      <Pressable
        onPress={() => setOptionsOpen((open) => !open)}
        style={styles.disclosure}
        accessibilityRole="button"
        accessibilityState={{ expanded: optionsOpen }}
      >
        <Text style={styles.disclosureText}>{optionsOpen ? 'Tùy chọn nghe ▾' : 'Tùy chọn nghe ▸'}</Text>
      </Pressable>
      {optionsOpen ? (
        <View style={styles.options}>
          <OptionSwitch label="Humanize" value={humanize} onChange={onHumanize} />
          <OptionSwitch label="Màu" value={colorOn} onChange={onColor} />
        </View>
      ) : null}
    </View>
  );
}

function LiveControls({ variant, playing, onVariant, onPlay, onPause }: LiveProps) {
  return (
    <View>
      <ChipRow
        items={STREAM_GENRES.map((item) => ({ id: item.id, label: item.label }))}
        selected={variant}
        onSelect={(id) => onVariant(id as StreamVariant)}
        large
      />
      <View style={styles.transport}>
        <TransportButton label="Nghe" active={!playing} onPress={onPlay} />
        <TransportButton label="Tạm dừng" active={playing} disabled={!playing} onPress={onPause} />
      </View>
    </View>
  );
}

function ChipRow({
  items,
  selected,
  onSelect,
  large = false,
}: {
  items: { id: string; label: string }[];
  selected: string;
  onSelect: (id: string) => void;
  large?: boolean;
}) {
  return (
    <View style={styles.chips}>
      {items.map((item) => {
        const active = item.id === selected;
        return (
          <Pressable
            key={item.id}
            onPress={() => onSelect(item.id)}
            style={[styles.chip, active && styles.chipActive]}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
          >
            <Text style={[styles.chipText, large && styles.chipTextLarge, active && styles.chipTextActive]} numberOfLines={1}>
              {item.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function TransportButton({
  label,
  onPress,
  active = false,
  disabled = false,
}: {
  label: string;
  onPress: () => void;
  active?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={[styles.button, active && styles.buttonActive, disabled && styles.buttonDisabled]}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <Text style={styles.buttonText}>{label}</Text>
    </Pressable>
  );
}

function OptionSwitch({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <View style={styles.option}>
      <Text style={styles.optionLabel}>{label}</Text>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ false: palette.track, true: palette.sound }}
        thumbColor={palette.text}
        accessibilityLabel={label}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 16,
    backgroundColor: palette.background,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 8,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: palette.surface,
  },
  chipActive: {
    backgroundColor: palette.sound,
  },
  chipText: {
    color: palette.textMuted,
    fontSize: 13,
    fontWeight: '600',
  },
  chipTextLarge: {
    fontSize: 15,
  },
  chipTextActive: {
    color: palette.text,
  },
  transport: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 14,
  },
  button: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: palette.surface,
  },
  buttonActive: {
    backgroundColor: palette.sound,
  },
  buttonDisabled: {
    opacity: 0.45,
  },
  buttonText: {
    color: palette.text,
    fontSize: 16,
    fontWeight: '600',
  },
  disclosure: {
    marginTop: 14,
    alignSelf: 'flex-start',
  },
  disclosureText: {
    color: palette.textMuted,
    fontSize: 13,
    fontWeight: '600',
  },
  options: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
  },
  option: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingLeft: 10,
    paddingRight: 6,
    paddingVertical: 4,
    borderRadius: 8,
    backgroundColor: palette.surface,
  },
  optionLabel: {
    color: palette.text,
    fontSize: 13,
    fontWeight: '600',
  },
  status: {
    color: palette.playhead,
    fontSize: 13,
    textAlign: 'center',
    marginTop: 10,
  },
});
