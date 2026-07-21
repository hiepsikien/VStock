import AsyncStorage from '@react-native-async-storage/async-storage';
import type { CompanionCharacterId } from './characters';

export type StoredChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  ts: number;
};

export type CompanionBond = {
  firstMetAt: number;
  lastChatAt: number;
  messageCount: number;
  /** Symbols the user talks about / watches with Vy */
  symbolsOfInterest: string[];
  /** Short durable notes for bonding (Northern VN, plain text) */
  notes: string[];
};

const HISTORY_PREFIX = 'vstock.companion.chat.';
const BOND_PREFIX = 'vstock.companion.bond.';
const MAX_STORED = 100;
const MAX_NOTES = 12;
const MAX_SYMBOLS = 12;

function historyKey(id: CompanionCharacterId): string {
  return HISTORY_PREFIX + id;
}

function bondKey(id: CompanionCharacterId): string {
  return BOND_PREFIX + id;
}

export async function loadCompanionChat(
  id: CompanionCharacterId,
): Promise<StoredChatMessage[]> {
  try {
    const raw = await AsyncStorage.getItem(historyKey(id));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as StoredChatMessage[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (m) =>
        m &&
        (m.role === 'user' || m.role === 'assistant') &&
        typeof m.content === 'string' &&
        m.content.trim().length > 0,
    );
  } catch {
    return [];
  }
}

export async function saveCompanionChat(
  id: CompanionCharacterId,
  messages: StoredChatMessage[],
): Promise<void> {
  const trimmed = messages
    .filter((m) => m.content.trim().length > 0)
    .slice(-MAX_STORED);
  await AsyncStorage.setItem(historyKey(id), JSON.stringify(trimmed));
}

export async function loadCompanionBond(
  id: CompanionCharacterId,
): Promise<CompanionBond | null> {
  try {
    const raw = await AsyncStorage.getItem(bondKey(id));
    if (!raw) return null;
    return JSON.parse(raw) as CompanionBond;
  } catch {
    return null;
  }
}

export async function saveCompanionBond(
  id: CompanionCharacterId,
  bond: CompanionBond,
): Promise<void> {
  await AsyncStorage.setItem(bondKey(id), JSON.stringify(bond));
}

const TICKER_RE = /\b[A-Z]{3}\b/g;
const MOOD_PATTERNS: Array<{ re: RegExp; note: string }> = [
  { re: /\b(lo|sợ|stress|áp lực|hoảng)\b/i, note: 'Hay lo lắng khi thị trường xấu' },
  { re: /\b(fomo|sợ bỏ lỡ|đu đỉnh)\b/i, note: 'Đôi khi có FOMO' },
  { re: /\b(vui|hứng|phấn khích|mừng)\b/i, note: 'Hay phấn khích khi bảng xanh' },
  { re: /\b(kiên nhẫn|kỷ luật|lâu dài)\b/i, note: 'Quan tâm kỷ luật / dài hạn' },
];

function uniqPush(list: string[], item: string, max: number): string[] {
  const next = [item, ...list.filter((x) => x !== item)];
  return next.slice(0, max);
}

/** Update durable bond memory after a user turn. */
export function evolveBond(
  prev: CompanionBond | null,
  userText: string,
  extraSymbols: string[] = [],
): CompanionBond {
  const now = Date.now();
  const bond: CompanionBond = prev ?? {
    firstMetAt: now,
    lastChatAt: now,
    messageCount: 0,
    symbolsOfInterest: [],
    notes: [],
  };

  bond.lastChatAt = now;
  bond.messageCount += 1;

  const found = new Set<string>([
    ...extraSymbols.map((s) => s.toUpperCase()),
    ...((userText.toUpperCase().match(TICKER_RE) as string[] | null) ?? []),
  ]);
  for (const sym of found) {
    if (sym.length !== 3) continue;
    bond.symbolsOfInterest = uniqPush(bond.symbolsOfInterest, sym, MAX_SYMBOLS);
  }

  for (const { re, note } of MOOD_PATTERNS) {
    if (re.test(userText)) {
      bond.notes = uniqPush(bond.notes, note, MAX_NOTES);
    }
  }

  return bond;
}

export function bondToContextDto(bond: CompanionBond | null): {
  firstMetAt?: number;
  lastChatAt?: number;
  messageCount?: number;
  symbolsOfInterest?: string[];
  notes?: string[];
} | undefined {
  if (!bond) return undefined;
  return {
    firstMetAt: bond.firstMetAt,
    lastChatAt: bond.lastChatAt,
    messageCount: bond.messageCount,
    symbolsOfInterest: bond.symbolsOfInterest.slice(0, MAX_SYMBOLS),
    notes: bond.notes.slice(0, MAX_NOTES),
  };
}

/** Messages to send to the API (recent window). */
export function messagesForApi(
  messages: Array<{ role: 'user' | 'assistant'; content: string }>,
  limit = 30,
): Array<{ role: 'user' | 'assistant'; content: string }> {
  return messages
    .filter((m) => m.content.trim().length > 0)
    .slice(-limit)
    .map((m) => ({ role: m.role, content: m.content.trim() }));
}

export const WELCOME_BACK_GAP_MS = 8 * 60 * 60 * 1000;
