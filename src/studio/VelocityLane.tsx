import React, { useEffect, useMemo, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { palette, TOUCH_TARGET } from '../musicalize/palette';
import { type } from '../musicalize/type';
import {
  mergeVelocityEdits,
  velocityLaneExtent,
  velocityLaneLabel,
  velocityLaneRows,
  noteKey,
  pinnedLabel,
  type MicroVelocity,
  type VelocityLaneId,
  type VelocityLaneRow,
} from './velocity';

/**
 * Compact, reusable velocity lane for the Studio preview.
 *
 * RN views only: no SVG, no gesture handler, no network. Every offset edit is
 * local component state and is never written back to the spec or preview. The
 * "view after layers" switch only changes what this component draws.
 */

const TRACK_HEIGHT = 48;
const BAR_WIDTH = 16;
const LANE_LABEL_WIDTH = 46;
const MAX_EDIT_OFFSET = 24;

const laneColors: Record<VelocityLaneId, string> = {
  thumb: '#E59A3C',
  voice1: palette.data,
  voice2: palette.sound,
  voice3: '#8B9DFF',
  voice4: '#B07CFF',
};

const laneNames: Record<VelocityLaneId, string> = {
  thumb: 'Thumb',
  voice1: 'V1',
  voice2: 'V2',
  voice3: 'V3',
  voice4: 'V4',
};

const laneOrder: VelocityLaneId[] = ['thumb', 'voice1', 'voice2', 'voice3', 'voice4'];

type Props = {
  notes: readonly unknown[];
  /** `null` means the backend returned no authored contour yet. */
  contour?: MicroVelocity | null;
  title?: string;
  /**
   * Local offset editing is optional; it is still display-only and is disabled
   * when the preview has no authored offsets.
   */
  editable?: boolean;
  /** Preview bar where the figure/slot starts; contour bars are relative. */
  barOffset?: number;
  /** Figure length in bars for a tiled preview; contour bars wrap modulo. */
  barSpan?: number;
  /** Simple flatten table for a rule contour, keyed by `noteKey(...)`. */
  ruleOffsets?: Readonly<Record<string, number>>;
  /**
   * Called with the merged contour when the user presses **Save to spec**.
   * The parent owns the spec text, pre-flight errors and validation.
   */
  onSaveContour?: (contour: MicroVelocity, info: VelocityLaneSaveInfo) => void;
};

export type VelocityLaneSaveInfo = {
  /** Local edits exist; a rule carrier cannot express them. */
  hasEdits: boolean;
  /** A rule contour still has rows without a flatten entry. */
  needsRule: boolean;
};

function clampOffset(value: number): number {
  return Math.max(-MAX_EDIT_OFFSET, Math.min(MAX_EDIT_OFFSET, Math.round(value)));
}

function velocityHeight(velocity: number | null): number {
  if (velocity == null) return 0;
  return Math.max(2, Math.round((Math.max(0, Math.min(127, velocity)) / 127) * TRACK_HEIGHT));
}

function offsetHeight(offset: number, maxAbs: number): number {
  const magnitude = Math.abs(offset);
  if (magnitude === 0) return 0;
  return Math.max(2, Math.round((magnitude / Math.max(4, maxAbs)) * (TRACK_HEIGHT / 2)));
}

function Chip({
  active,
  label,
  disabled,
  onPress,
  accessibilityLabel,
}: {
  active: boolean;
  label: string;
  disabled?: boolean;
  onPress: () => void;
  accessibilityLabel?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ selected: active, disabled }}
      style={({ pressed }) => [
        styles.chip,
        active && styles.chipActive,
        disabled && styles.chipDisabled,
        pressed && !disabled && styles.pressed,
      ]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

function StepButton({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`Offset ${label}`}
      style={({ pressed }) => [styles.stepButton, pressed && styles.pressed]}
    >
      <Text style={styles.stepText}>{label}</Text>
    </Pressable>
  );
}

export function VelocityLane({
  notes,
  contour = null,
  title,
  editable = true,
  barOffset,
  barSpan,
  ruleOffsets,
  onSaveContour,
}: Props) {
  const [voice, setVoice] = useState<number | null>(null);
  const [showThumb, setShowThumb] = useState(true);
  const [showAfterLayers, setShowAfterLayers] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, number>>({});

  // A new preview (or a different selected slot) reloads the authored contour;
  // local edits must never leak into another slot's coordinates.
  useEffect(() => {
    setEdits({});
    setSelectedKey(null);
    setEditMode(false);
  }, [contour]);

  const allRows = useMemo(
    () =>
      velocityLaneRows(notes, contour, {
        ...(barOffset == null ? {} : { barOffset }),
        ...(barSpan == null ? {} : { barSpan }),
        ...(ruleOffsets == null ? {} : { ruleOffsets }),
      }),
    [notes, contour, barOffset, barSpan, ruleOffsets],
  );
  const hasThumb = allRows.some((row) => row.thumb);
  const hasVoice4 = allRows.some((row) => row.voice === 4);
  const availableVoices = useMemo(
    () => [1, 2, 3, 4].filter((item) => allRows.some((row) => row.voice === item)),
    [allRows],
  );

  const rows = useMemo(
    () =>
      allRows.filter((row) => {
        if (!showThumb && row.thumb) return false;
        if (voice != null && !row.thumb && row.voice !== voice) return false;
        return true;
      }),
    [allRows, showThumb, voice],
  );

  const extent = useMemo(() => velocityLaneExtent(rows), [rows]);
  const hasAuthored = rows.some((row) => row.authored && !row.pinned);
  const canAfterLayers = hasAuthored && contour != null;
  const selected = rows.find((row) => row.key === selectedKey) ?? null;
  const editCount = Object.keys(edits).length;
  const ruleNeedsFlatten =
    contour?.kind === 'rule' && allRows.some((row) => row.needsRule);
  // Rule contours stay code-owned until the writer has a flatten table.
  const canEdit = hasAuthored && contour?.kind !== 'rule';
  const canSave =
    editable && contour != null && onSaveContour != null && !ruleNeedsFlatten;

  const effectiveOffset = (row: VelocityLaneRow): number => {
    if (row.pinned) return 0;
    const edited = edits[row.key];
    return edited == null ? row.offset : edited;
  };

  const afterLayersVelocity = (row: VelocityLaneRow): number | null => {
    if (row.pinned) return row.velocity;
    if (row.velocity == null) return null;
    return Math.max(
      0,
      Math.min(127, Math.round(row.velocity + effectiveOffset(row))),
    );
  };

  const displayVelocity = (row: VelocityLaneRow): number | null =>
    showAfterLayers && canAfterLayers ? afterLayersVelocity(row) : row.velocity;

  const laneRows = laneOrder
    .map((lane) => ({ lane, rows: rows.filter((row) => row.lane === lane) }))
    .filter((group) => group.rows.length > 0);

  const pinnedRows = rows.filter((row) => row.pinned);

  const adjustSelected = (delta: number) => {
    if (!selected || selected.pinned || !canEdit) return;
    setEdits((current) => {
      const base = current[selected.key] ?? selected.offset;
      const next = clampOffset(base + delta);
      if (next === selected.offset) {
        const copy = { ...current };
        delete copy[selected.key];
        return copy;
      }
      return { ...current, [selected.key]: next };
    });
  };

  const resetSelected = () => {
    if (!selected) return;
    setEdits((current) => {
      const copy = { ...current };
      delete copy[selected.key];
      return copy;
    });
  };

  const saveContour = () => {
    if (!onSaveContour || !canSave) return;
    onSaveContour(mergeVelocityEdits(contour, allRows, edits), {
      hasEdits: editCount > 0,
      needsRule: ruleNeedsFlatten,
    });
  };

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text style={[type.section, styles.label]}>{title ?? 'Velocity lane'}</Text>
          <Text style={styles.subtitle}>
            {contour == null
              ? 'Realized velocities · read-only'
              : contour.kind === 'rule'
                ? `Rule contour · ${contour.ruleId} v${contour.ruleVersion}`
                : 'Authored micro-velocity offsets'}
          </Text>
        </View>
        <View
          style={[
            styles.statusBadge,
            contour == null ? styles.statusRealized : styles.statusAuthored,
          ]}
        >
          <Text
            style={[
              styles.statusText,
              contour == null ? styles.statusTextRealized : styles.statusTextAuthored,
            ]}
          >
            {contour == null ? 'REALIZED' : 'AUTHORED'}
          </Text>
        </View>
      </View>

      <View style={styles.controls}>
        <Text style={styles.controlLabel}>Voice</Text>
        <Chip
          active={voice === null}
          label="All"
          onPress={() => setVoice(null)}
          accessibilityLabel="Show all voices"
        />
        {availableVoices.map((item) => (
          <Chip
            key={item}
            active={voice === item}
            label={`${item}`}
            onPress={() => setVoice(item)}
            accessibilityLabel={`Show voice ${item}`}
          />
        ))}
        <Chip
          active={showThumb}
          label="Thumb"
          disabled={!hasThumb}
          onPress={() => setShowThumb((current) => !current)}
          accessibilityLabel="Toggle thumb lane"
        />
        {hasVoice4 ? <Text style={styles.controlHint}>V4 present</Text> : null}
      </View>

      <View style={styles.controls}>
        <Chip
          active={showAfterLayers}
          label="View after layers"
          disabled={!canAfterLayers}
          onPress={() => setShowAfterLayers((current) => !current)}
          accessibilityLabel="View velocities after authored offsets"
        />
        {editable ? (
          <Chip
            active={editMode}
            label="Edit offsets"
            disabled={!canEdit}
            onPress={() => setEditMode((current) => !current)}
            accessibilityLabel="Edit authored offsets in local state"
          />
        ) : null}
        {showAfterLayers && canAfterLayers ? (
          <Text style={styles.controlHint}>
            view only · realized → after offset
          </Text>
        ) : null}
      </View>

      {contour == null ? (
        <View style={styles.noteBox}>
          <Text style={styles.noteText}>
            No authored <Text style={styles.mono}>microVelocity</Text> returned by the
            preview. These bars are the realized velocities; offsets are not loaded
            yet, so the lane is read-only.
          </Text>
        </View>
      ) : null}

      {contour?.kind === 'rule' ? (
        <View style={styles.noteBox}>
          <Text style={styles.noteText}>
            {ruleNeedsFlatten
              ? 'This rule contour needs a per-rule flatten table before the lane can show offsets. Unmatched notes stay empty instead of guessed, and Save to spec stays blocked.'
              : 'Rule contour flattened through the supplied offset table. The rule carrier stays code-owned, so the lane is read-only.'}
          </Text>
        </View>
      ) : null}

      {rows.length === 0 ? (
        <View style={styles.emptyBox}>
          <Text style={styles.emptyText}>
            {allRows.length === 0
              ? 'No preview notes to draw. Run a successful preview first.'
              : 'No notes match this voice or thumb filter.'}
          </Text>
        </View>
      ) : (
        <>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            <View style={styles.laneStack}>
              {laneRows.map((group) => (
                <View key={group.lane} style={styles.laneRow}>
                  <View style={styles.laneLabelCell}>
                    <Text style={[styles.laneLabel, { color: laneColors[group.lane] }]}>
                      {laneNames[group.lane]}
                    </Text>
                    <Text style={styles.laneCount}>{group.rows.length}</Text>
                  </View>
                  <View style={styles.bars}>
                    <View style={styles.baseline} />
                    {group.rows.map((row, index) => {
                      const previous = group.rows[index - 1];
                      const gap =
                        previous == null
                          ? 0
                          : row.bar !== previous.bar
                            ? 10
                            : row.beat !== previous.beat
                              ? 2
                              : 0;
                      const offset = effectiveOffset(row);
                      const shown = displayVelocity(row);
                      const offsetFill = offsetHeight(offset, extent.maxAbsOffset);
                      const color = row.pinned
                        ? palette.playhead
                        : laneColors[row.lane];
                      return (
                        <React.Fragment key={row.key}>
                          {gap > 0 ? <View style={{ width: gap }} /> : null}
                          <Pressable
                            onPress={() => setSelectedKey(row.key)}
                            accessibilityRole="button"
                            accessibilityLabel={`${velocityLaneLabel(row)} · ${
                              row.pinned ? pinnedLabel(row) : `offset ${offset}`
                            }`}
                            accessibilityState={{ selected: selectedKey === row.key }}
                            style={({ pressed }) => [
                              styles.barSlot,
                              selectedKey === row.key && styles.barSlotSelected,
                              pressed && styles.pressed,
                            ]}
                          >
                            <View style={styles.barTrack}>
                              <View
                                style={[
                                  styles.velocityFill,
                                  {
                                    height: velocityHeight(shown),
                                    backgroundColor: color,
                                    opacity: showAfterLayers && canAfterLayers ? 0.42 : 0.24,
                                  },
                                ]}
                              />
                              {offsetFill > 0 ? (
                                <View
                                  style={[
                                    styles.offsetFill,
                                    offset > 0
                                      ? { bottom: TRACK_HEIGHT / 2, height: offsetFill }
                                      : { top: TRACK_HEIGHT / 2, height: offsetFill },
                                    { backgroundColor: color },
                                  ]}
                                />
                              ) : null}
                              {row.pinned ? <View style={styles.pinDot} /> : null}
                            </View>
                            {row.pinned ? <Text style={styles.pinText}>P</Text> : null}
                          </Pressable>
                        </React.Fragment>
                      );
                    })}
                  </View>
                </View>
              ))}
            </View>
          </ScrollView>

          <View style={styles.legend}>
            <Text style={styles.legendText}>
              {extent.barCount
                ? `bars ${extent.barStart + 1}–${extent.barEnd + 1} · ${
                    extent.maxAbsOffset
                  } max |offset|`
                : 'no bars'}
            </Text>
            {pinnedRows.length ? (
              <Text style={styles.legendText}>
                {pinnedRows.length} pinned attack{pinnedRows.length === 1 ? '' : 's'}
              </Text>
            ) : null}
            <Text style={styles.legendText}>empty = 0</Text>
          </View>

          {pinnedRows.length ? (
            <View style={styles.pinnedList}>
              {pinnedRows.slice(0, 8).map((row) => (
                <Pressable
                  key={row.key}
                  onPress={() => setSelectedKey(row.key)}
                  accessibilityRole="button"
                  accessibilityLabel={`Pinned ${velocityLaneLabel(row)} ${pinnedLabel(row)}`}
                  style={({ pressed }) => [
                    styles.pinnedChip,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={styles.pinnedChipText}>
                    {velocityLaneLabel(row)} · {pinnedLabel(row)}
                  </Text>
                </Pressable>
              ))}
              {pinnedRows.length > 8 ? (
                <Text style={styles.legendText}>+{pinnedRows.length - 8} more</Text>
              ) : null}
            </View>
          ) : null}
        </>
      )}

      {selected ? (
        <View style={styles.detail}>
          <Text style={styles.detailTitle}>{velocityLaneLabel(selected)}</Text>
          <Text style={styles.detailKey}>
            key {noteKey(selected.bar, selected.beat, selected.voice, selected.finger)} ·
            midi {selected.note.midi ?? '—'}
          </Text>
          <Text style={styles.detailLine}>
            {selected.pinned
              ? pinnedLabel(selected)
              : `offset ${effectiveOffset(selected)}${
                  selected.authored ? ' (authored)' : ' (default 0)'
                }`}
          </Text>
          <Text style={styles.detailLine}>
            realized {selected.velocity ?? '—'}
            {selected.pinned
              ? ' · absolute writer, offset locked'
              : canAfterLayers && showAfterLayers
                ? ` → ${afterLayersVelocity(selected) ?? '—'} after layer`
                : ''}
          </Text>
          {editMode && canEdit && !selected.pinned ? (
            <View style={styles.editRow}>
              <Text style={styles.editLabel}>local</Text>
              <StepButton label="-4" onPress={() => adjustSelected(-4)} />
              <StepButton label="-1" onPress={() => adjustSelected(-1)} />
              <StepButton label="+1" onPress={() => adjustSelected(1)} />
              <StepButton label="+4" onPress={() => adjustSelected(4)} />
              <Pressable
                onPress={resetSelected}
                accessibilityRole="button"
                accessibilityLabel="Reset selected local offset"
                style={({ pressed }) => [styles.resetButton, pressed && styles.pressed]}
              >
                <Text style={styles.resetText}>Reset</Text>
              </Pressable>
            </View>
          ) : null}
          {editMode && canEdit && selected.pinned ? (
            <Text style={styles.detailWarn}>
              Pinned attack: the absolute layer owns this velocity, so the lane does
              not expose an offset.
            </Text>
          ) : null}
        </View>
      ) : (
        <Text style={styles.detailHint}>
          Click a bar to reveal its note key and offset. Bars are voice-colored;
          pinned bars carry P and their absolute layer label.
        </Text>
      )}

      {editMode && editCount > 0 ? (
        <View style={styles.editFooter}>
          <Text style={styles.editFooterText}>
            {editCount} local edit{editCount === 1 ? '' : 's'} · pending save
          </Text>
          <Pressable
            onPress={() => setEdits({})}
            accessibilityRole="button"
            accessibilityLabel="Clear all local offset edits"
            style={({ pressed }) => [styles.resetButton, pressed && styles.pressed]}
          >
            <Text style={styles.resetText}>Clear local edits</Text>
          </Pressable>
        </View>
      ) : null}

      {editable && onSaveContour ? (
        <View style={styles.saveRow}>
          <Pressable
            onPress={saveContour}
            disabled={!canSave}
            accessibilityRole="button"
            accessibilityLabel="Save velocity contour to sentence spec"
            accessibilityState={{ disabled: !canSave }}
            style={({ pressed }) => [
              styles.saveButton,
              !canSave && styles.saveButtonDisabled,
              pressed && canSave && styles.pressed,
            ]}
          >
            <Text style={[styles.saveText, !canSave && styles.saveTextDisabled]}>
              Save to spec
            </Text>
          </Pressable>
          <Text style={styles.saveHint}>
            {ruleNeedsFlatten
              ? 'Rule contour needs a flatten table; saving stays blocked.'
              : editCount > 0
                ? `Writes ${editCount} local edit${editCount === 1 ? '' : 's'} into slots[].microVelocity.`
                : 'Writes the loaded contour into slots[].microVelocity.'}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
    paddingTop: 10,
    gap: 8,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 8,
  },
  headerText: {
    flex: 1,
    gap: 2,
  },
  label: {
    color: palette.textFaint,
  },
  subtitle: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 15,
  },
  statusBadge: {
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 3,
    borderWidth: 1,
  },
  statusRealized: {
    borderColor: palette.hairlineStrong,
  },
  statusAuthored: {
    borderColor: palette.data,
  },
  statusText: {
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 11,
    fontWeight: '700',
    letterSpacing: 0.7,
  },
  statusTextRealized: {
    color: palette.textFaint,
  },
  statusTextAuthored: {
    color: palette.data,
  },
  controls: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 6,
  },
  controlLabel: {
    color: palette.textFaint,
    fontFamily: type.section.fontFamily,
    fontSize: 10,
    lineHeight: 13,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  controlHint: {
    color: palette.textFaint,
    fontFamily: type.sans.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  chip: {
    minHeight: 28,
    justifyContent: 'center',
    paddingHorizontal: 9,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
  },
  chipActive: {
    borderColor: palette.data,
    backgroundColor: palette.dataFill,
  },
  chipDisabled: {
    opacity: 0.38,
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
  noteBox: {
    paddingHorizontal: 9,
    paddingVertical: 7,
    borderRadius: 6,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.hairline,
  },
  noteText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  mono: {
    fontFamily: type.mono.fontFamily,
    color: palette.text,
  },
  emptyBox: {
    padding: 12,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
  },
  emptyText: {
    color: palette.textFaint,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 16,
  },
  laneStack: {
    gap: 2,
    paddingVertical: 2,
  },
  laneRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  laneLabelCell: {
    width: LANE_LABEL_WIDTH,
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 3,
  },
  laneLabel: {
    fontFamily: type.section.fontFamily,
    fontSize: 10,
    lineHeight: 13,
    fontWeight: '700',
    letterSpacing: 0.6,
  },
  laneCount: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 8,
    lineHeight: 10,
  },
  bars: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    minHeight: TRACK_HEIGHT + 10,
    position: 'relative',
  },
  baseline: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: TRACK_HEIGHT / 2,
    height: 1,
    backgroundColor: palette.hairline,
  },
  barSlot: {
    width: BAR_WIDTH,
    height: TRACK_HEIGHT + 10,
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingTop: 2,
    borderRadius: 2,
  },
  barSlotSelected: {
    backgroundColor: 'rgba(244, 241, 234, 0.08)',
  },
  barTrack: {
    width: BAR_WIDTH - 5,
    height: TRACK_HEIGHT,
    borderRadius: 2,
    backgroundColor: palette.track,
    overflow: 'hidden',
    position: 'relative',
  },
  velocityFill: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    borderTopLeftRadius: 2,
    borderTopRightRadius: 2,
  },
  offsetFill: {
    position: 'absolute',
    left: 0,
    right: 0,
    opacity: 0.92,
  },
  pinDot: {
    position: 'absolute',
    top: 2,
    left: (BAR_WIDTH - 5) / 2 - 2,
    width: 4,
    height: 4,
    borderRadius: 1,
    backgroundColor: palette.playhead,
  },
  pinText: {
    marginTop: 1,
    color: palette.playhead,
    fontFamily: type.mono.fontFamily,
    fontSize: 7,
    lineHeight: 9,
    fontWeight: '700',
  },
  legend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  legendText: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
  },
  pinnedList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 5,
  },
  pinnedChip: {
    paddingHorizontal: 7,
    paddingVertical: 4,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(245, 185, 66, 0.35)',
    backgroundColor: 'rgba(245, 185, 66, 0.08)',
  },
  pinnedChipText: {
    color: palette.playhead,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
  },
  detail: {
    gap: 3,
    padding: 9,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surface,
  },
  detailTitle: {
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 14,
    fontWeight: '700',
  },
  detailLine: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 15,
  },
  detailKey: {
    color: palette.textFaint,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
  },
  detailWarn: {
    color: palette.playhead,
    fontFamily: type.sans.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  detailHint: {
    color: palette.textFaint,
    fontFamily: type.sans.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  editRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 5,
    marginTop: 3,
  },
  editLabel: {
    color: palette.textFaint,
    fontFamily: type.section.fontFamily,
    fontSize: 9,
    lineHeight: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  stepButton: {
    minWidth: TOUCH_TARGET,
    minHeight: 30,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 8,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surfaceActive,
  },
  stepText: {
    color: palette.text,
    fontFamily: type.mono.fontFamily,
    fontSize: 11,
    lineHeight: 14,
    fontWeight: '700',
  },
  resetButton: {
    minHeight: 30,
    justifyContent: 'center',
    paddingHorizontal: 9,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
  },
  resetText: {
    color: palette.textMuted,
    fontFamily: type.sans.fontFamily,
    fontSize: 10,
    lineHeight: 13,
    fontWeight: '600',
  },
  editFooter: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    paddingTop: 2,
  },
  editFooterText: {
    color: palette.playhead,
    fontFamily: type.mono.fontFamily,
    fontSize: 9,
    lineHeight: 12,
  },
  saveRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 8,
    paddingTop: 2,
  },
  saveButton: {
    minHeight: 30,
    justifyContent: 'center',
    paddingHorizontal: 11,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.data,
    backgroundColor: palette.dataFill,
  },
  saveButtonDisabled: {
    opacity: 0.38,
  },
  saveText: {
    color: palette.data,
    fontFamily: type.sans.fontFamily,
    fontSize: 11,
    lineHeight: 14,
    fontWeight: '700',
  },
  saveTextDisabled: {
    color: palette.textMuted,
  },
  saveHint: {
    flexShrink: 1,
    color: palette.textFaint,
    fontFamily: type.sans.fontFamily,
    fontSize: 10,
    lineHeight: 14,
  },
  pressed: {
    opacity: 0.7,
  },
});
