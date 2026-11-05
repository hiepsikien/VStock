import type { StudioError } from './protocol';
import { checkSpecShape, isRecord, parseJsonObject } from './spec';
import {
  velocityContourIsEmpty,
  type MicroVelocity,
  type VelocityOffset,
} from './velocity';

/**
 * Pure bridge between the velocity lane and one SentenceSpec slot (docs §6.9).
 *
 * The lane edits a display contour; this module writes it into
 * `slots[slot].microVelocity` without touching any other slot field. It never
 * talks to the network. The caller still owns the editor text and decides
 * whether the returned `text` should replace it.
 */

function cleanEntry(entry: VelocityOffset): VelocityOffset {
  const layer = typeof entry.layer === 'string' && entry.layer.trim()
    ? entry.layer.trim()
    : null;
  return {
    bar: entry.bar,
    beat: entry.beat,
    voice: entry.voice,
    ...(entry.finger ? { finger: entry.finger } : {}),
    ...(entry.offset == null ? {} : { offset: entry.offset }),
    ...(entry.pinned === true ? { pinned: true } : {}),
    ...(entry.velocity == null ? {} : { velocity: entry.velocity }),
    ...(layer ? { layer } : {}),
  };
}

function cleanEntries(entries: readonly VelocityOffset[] | undefined): VelocityOffset[] {
  return (entries ?? []).map(cleanEntry);
}

/** JSON-safe contour, with empty `thumb` arrays omitted like the docs show. */
export function serializeVelocityContour(contour: MicroVelocity): Record<string, unknown> {
  if (contour.kind === 'rule') {
    const thumb = cleanEntries(contour.thumb);
    return {
      kind: 'rule',
      ruleId: contour.ruleId,
      ruleVersion: contour.ruleVersion,
      params: { ...contour.params },
      notes: cleanEntries(contour.notes),
      ...(thumb.length ? { thumb } : {}),
    };
  }
  const thumb = cleanEntries(contour.thumb);
  return {
    kind: 'offsets',
    notes: cleanEntries(contour.notes),
    ...(thumb.length ? { thumb } : {}),
  };
}

export type VelocitySpecSaveInput = {
  /** Current editor text; parsed as one SentenceSpec mapping. */
  specText: string;
  /** Index into `slots`; matches the preview slot number. */
  slot: number;
  /** Edited contour from the lane; `null`/empty removes the field. */
  contour: MicroVelocity | null;
  /**
   * True when a rule contour still has unmatched attacks. A rule is code-owned
   * and is never written back until every row has a flatten entry.
   */
  needsRule?: boolean;
  /** True when the lane has local edits that a rule carrier cannot express. */
  hasEdits?: boolean;
};

export type VelocitySpecSaveResult =
  | {
      ok: true;
      /** Pretty JSON ready to replace the editor text. */
      text: string;
      spec: Record<string, unknown>;
      slot: number;
      /** True when the save removed an empty `microVelocity` field. */
      omitted: boolean;
    }
  | { ok: false; errors: StudioError[] };

function failure(path: string, message: string): VelocitySpecSaveResult {
  return { ok: false, errors: [{ path, message }] };
}

/**
 * Write one slot's contour back into the sentence JSON.
 *
 * Failure is always inert: the caller keeps the old editor text. On success
 * every other spec/slot field is preserved and the result passes the same
 * local pre-flight (`checkSpecShape`) used before Validate/Preview.
 */
export function saveVelocityContourToSpec(
  input: VelocitySpecSaveInput,
): VelocitySpecSaveResult {
  const { specText, slot, contour, needsRule = false, hasEdits = false } = input;
  const path = `slots[${slot}].microVelocity`;

  if (contour?.kind === 'rule') {
    if (needsRule) {
      return failure(
        path,
        'Rule contour still needs a per-note flatten table; flatten it before saving.',
      );
    }
    if (hasEdits) {
      return failure(
        path,
        'Rule contour edits cannot be stored while the slot keeps a rule carrier; flatten to offsets first.',
      );
    }
  }

  const parsed = parseJsonObject(specText, 'Spec');
  if (!parsed.ok) return parsed;

  const slots = parsed.value.slots;
  if (!Array.isArray(slots)) {
    return failure('slots', 'must be a non-empty array');
  }
  if (!Number.isInteger(slot) || slot < 0 || slot >= slots.length) {
    return failure(`slots[${slot}]`, 'does not exist in the current spec JSON');
  }
  const current = slots[slot];
  if (!isRecord(current)) {
    return failure(`slots[${slot}]`, 'must be an object');
  }

  const nextSlot: Record<string, unknown> = { ...current };
  const omitted = velocityContourIsEmpty(contour);
  if (omitted) {
    delete nextSlot.microVelocity;
  } else if (contour) {
    nextSlot.microVelocity = serializeVelocityContour(contour);
  }

  const nextSlots = slots.map((entry, index) => (index === slot ? nextSlot : entry));
  const nextSpec: Record<string, unknown> = { ...parsed.value, slots: nextSlots };

  const errors = checkSpecShape(nextSpec);
  if (errors.length) return { ok: false, errors };

  return {
    ok: true,
    text: JSON.stringify(nextSpec, null, 2),
    spec: nextSpec,
    slot,
    omitted,
  };
}
