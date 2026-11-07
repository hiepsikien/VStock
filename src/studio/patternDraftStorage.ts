/**
 * Persist the Studio pattern draft so figures/tags survive a reload.
 *
 * Only the draft itself is stored. Render/audio results are intentionally
 * ephemeral: they are content-hashed and can be reproduced from the draft.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  normalizePatternDraft,
  type PatternDraft,
} from './sentenceDraft';

export const PATTERN_DRAFT_STORAGE_KEY = 'vstock.studio.patternDraft.v1';

export async function loadPatternDraft(): Promise<PatternDraft | null> {
  try {
    const raw = await AsyncStorage.getItem(PATTERN_DRAFT_STORAGE_KEY);
    if (!raw) return null;
    return normalizePatternDraft(JSON.parse(raw));
  } catch {
    return null;
  }
}

export async function savePatternDraft(
  draft: PatternDraft | null,
): Promise<void> {
  try {
    if (!draft) {
      await AsyncStorage.removeItem(PATTERN_DRAFT_STORAGE_KEY);
      return;
    }
    await AsyncStorage.setItem(
      PATTERN_DRAFT_STORAGE_KEY,
      JSON.stringify(draft),
    );
  } catch {
    // Storage is best-effort; a failed save must never block authoring.
  }
}
