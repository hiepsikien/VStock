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
  /** How Vy addresses the user, e.g. "Anh", "Lan" */
  userNickname?: string;
};

/** Daily prefs — survives bond fields but cleared on session reset. */
export type CompanionPrefs = {
  /** Local calendar day YYYY-MM-DD when mood check-in last shown/answered */
  lastMoodCheckInDate?: string;
  lastMoodResponse?: string;
  /** Epoch ms — throttle topic-recall nudges */
  lastRecallNudgeAt?: number;
};

const HISTORY_PREFIX = 'vstock.companion.chat.';
const BOND_PREFIX = 'vstock.companion.bond.';
const PREFS_PREFIX = 'vstock.companion.prefs.';
const MAX_STORED = 100;
const MAX_NOTES = 12;
const MAX_SYMBOLS = 12;

function historyKey(id: CompanionCharacterId): string {
  return HISTORY_PREFIX + id;
}

function bondKey(id: CompanionCharacterId): string {
  return BOND_PREFIX + id;
}

function prefsKey(id: CompanionCharacterId): string {
  return PREFS_PREFIX + id;
}

export function localDateString(d = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function bondDisplayName(bond: CompanionBond | null | undefined): string {
  const nick = bond?.userNickname?.trim();
  return nick && nick.length > 0 ? nick : 'bạn';
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
  const trimmed = bond.userNickname?.trim();
  await AsyncStorage.setItem(
    bondKey(id),
    JSON.stringify({
      ...bond,
      userNickname: trimmed && trimmed.length > 0 ? trimmed.slice(0, 24) : undefined,
    }),
  );
}

export async function loadCompanionPrefs(
  id: CompanionCharacterId,
): Promise<CompanionPrefs | null> {
  try {
    const raw = await AsyncStorage.getItem(prefsKey(id));
    if (!raw) return null;
    return JSON.parse(raw) as CompanionPrefs;
  } catch {
    return null;
  }
}

export async function saveCompanionPrefs(
  id: CompanionCharacterId,
  prefs: CompanionPrefs,
): Promise<void> {
  await AsyncStorage.setItem(prefsKey(id), JSON.stringify(prefs));
}

export async function markMoodCheckInDone(
  id: CompanionCharacterId,
  response?: string,
): Promise<void> {
  const prev = (await loadCompanionPrefs(id)) ?? {};
  await saveCompanionPrefs(id, {
    ...prev,
    lastMoodCheckInDate: localDateString(),
    lastMoodResponse: response?.trim() || prev.lastMoodResponse,
  });
}

export async function markRecallNudgeShown(id: CompanionCharacterId): Promise<void> {
  const prev = (await loadCompanionPrefs(id)) ?? {};
  await saveCompanionPrefs(id, {
    ...prev,
    lastRecallNudgeAt: Date.now(),
  });
}

/** Wipe chat history + bonding memory for a fresh start with this character. */
export async function clearCompanionSession(
  id: CompanionCharacterId,
): Promise<void> {
  await AsyncStorage.multiRemove([historyKey(id), bondKey(id), prefsKey(id)]);
}

const TICKER_RE = /\b[A-Z]{3}\b/g;
/** Vietnamese / chat words that look like tickers when uppercased. */
const FALSE_TICKERS = new Set([
  'NAY',
  'SAO',
  'THE',
  'ROI',
  'CUA',
  'CHO',
  'VAO',
  'VOI',
  'MOT',
  'HAI',
  'BON',
  'NAM',
  'SAU',
  'BAY',
  'TAM',
  'HON',
  'RAT',
  'LAI',
  'VAN',
  'DEN',
  'NUA',
  'THI',
  'NEU',
  'KHI',
  'LAM',
  'CAI',
  'DAY',
  'NOI',
  'XEM',
  'HOI',
  'GIA',
  'MUC',
  'LOI',
  'NEN',
  'BAN',
  'MUA',
  'NHA',
  'ONG',
  'CHI',
  'ANH',
  'TOI',
  'APP',
  'API',
  'CEO',
  'ETF',
  'USD',
  'VND',
  'AND',
  'FOR',
  'YOU',
  'ALL',
  'CAN',
  'HOW',
  'NEW',
  'NOW',
  'OLD',
  'SEE',
  'TWO',
  'WAY',
  'WHO',
  'DID',
  'ITS',
  'LET',
  'PUT',
  'SAY',
  'SHE',
  'TOO',
  'USE',
  'BUT',
  'NOT',
  'ARE',
  'WAS',
  'ONE',
  'OUR',
  'OUT',
  'DAY',
  'GET',
  'HAS',
  'HIM',
  'HIS',
  'HER',
]);

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
    if (FALSE_TICKERS.has(sym)) continue;
    bond.symbolsOfInterest = uniqPush(bond.symbolsOfInterest, sym, MAX_SYMBOLS);
  }

  for (const { re, note } of MOOD_PATTERNS) {
    if (re.test(userText)) {
      bond.notes = uniqPush(bond.notes, note, MAX_NOTES);
    }
  }

  return bond;
}

export function applyBondNotes(
  prev: CompanionBond | null,
  notes: string[],
): CompanionBond {
  const now = Date.now();
  const base = prev ?? {
    firstMetAt: now,
    lastChatAt: now,
    messageCount: 0,
    symbolsOfInterest: [],
    notes: [],
  };
  return {
    ...base,
    lastChatAt: now,
    notes: notes.filter((n) => n.trim().length > 0).slice(0, MAX_NOTES),
  };
}

export function bondToContextDto(bond: CompanionBond | null): {
  firstMetAt?: number;
  lastChatAt?: number;
  messageCount?: number;
  symbolsOfInterest?: string[];
  notes?: string[];
  userNickname?: string;
} | undefined {
  if (!bond) return undefined;
  return {
    firstMetAt: bond.firstMetAt,
    lastChatAt: bond.lastChatAt,
    messageCount: bond.messageCount,
    symbolsOfInterest: bond.symbolsOfInterest.slice(0, MAX_SYMBOLS),
    notes: bond.notes.slice(0, MAX_NOTES),
    userNickname: bond.userNickname?.trim() || undefined,
  };
}

/** Personalized welcome when reopening chat after a gap. */
export function buildWelcomeBackMessage(bond: CompanionBond | null): string {
  const who = bondDisplayName(bond);
  const sym = bond?.symbolsOfInterest[0];
  const days = bond
    ? Math.max(0, Math.floor((Date.now() - bond.lastChatAt) / (24 * 60 * 60 * 1000)))
    : 0;
  if (sym && days >= 2) {
    return `Lại gặp ${who} rồi. Hôm trước hay ngó ${sym} — dạo này còn theo không?`;
  }
  if (sym) {
    return `Chào ${who}. Dạo này ${sym} vẫn trong tầm mắt nhỉ?`;
  }
  if (days >= 2) {
    return `Lâu rồi không trò chuyện, ${who}. Watchlist dạo này thế nào?`;
  }
  return `Lại gặp ${who} rồi nhỉ. Dạo này bảng thế nào?`;
}

export const RECALL_GAP_MS = 2 * 24 * 60 * 60 * 1000;

export const MOOD_CHECKIN_REPLIES = ['Bình thường', 'Hơi lo', 'Khỏe'] as const;

export function buildMoodCheckInMessage(bond: CompanionBond | null): string {
  const who = bondDisplayName(bond);
  return `Hôm nay ${who} thế nào — bình thường hay hơi căng?`;
}

export function moodSeedFromReply(chip: string): string {
  if (chip === 'Hơi lo') return 'Hôm nay mình hơi lo một chút.';
  if (chip === 'Khỏe') return 'Hôm nay mình khá ổn.';
  return 'Hôm nay mình bình thường thôi.';
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
