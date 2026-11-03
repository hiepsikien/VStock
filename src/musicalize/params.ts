import { PARAMS_SCHEMA, type ParamsFieldSchema } from './paramsSchema.generated';

export type { ParamsFieldSchema } from './paramsSchema.generated';

/**
 * The listener's ten knobs. One schema is generated from the backend, so the
 * app never invents a minimum, a step, or a default of its own.
 *
 * The server owns the hash and the cache name. The client only needs a
 * canonical params string for React keys and a compact `p` query.
 */
export type SonifyParams = Record<string, number>;

export type ParamWarning = {
  code: 'clamped' | 'unknown_key' | 'high_humanize' | 'high_breath';
  key: string;
  value?: number;
};

export const PARAM_GROUPS = PARAMS_SCHEMA.groups;

export const PARAM_FIELDS: ParamsFieldSchema[] = PARAMS_SCHEMA.groups.flatMap(
  (group) => group.fields,
);

export const PARAM_FIELD_BY_KEY: Record<string, ParamsFieldSchema> = Object.fromEntries(
  PARAM_FIELDS.map((field) => [field.key, field]),
);

export const PARAM_KEYS = PARAM_FIELDS.map((field) => field.key);

export const DEFAULT_PARAMS: SonifyParams = Object.fromEntries(
  PARAM_FIELDS.map((field) => [field.key, field.default]),
);

export const DEFAULT_HASH = PARAMS_SCHEMA.defaultHash;
export const SCHEMA_VERSION = PARAMS_SCHEMA.schema;
export const P_MAX_LENGTH = 2048;
const HUMANIZE_SOFT_WARNING = 1.1;
const BREATH_SOFT_WARNING = 1.2;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function roundStep(value: number, step: number): number {
  if (!(step > 0)) return Math.round(value * 100) / 100;
  return Math.round(Math.round(value / step) * step * 100) / 100;
}

/** Round to the schema grid. Every read and every encode goes through here. */
export function stepValue(field: ParamsFieldSchema, value: number): number {
  const rounded = roundStep(value, field.step);
  return Math.min(field.max, Math.max(field.min, rounded));
}

/** Keys outside the schema are dropped; missing keys take the schema default. */
export function normalizeParams(raw: unknown): SonifyParams {
  const source = isRecord(raw) ? raw : {};
  const params: SonifyParams = {};
  for (const field of PARAM_FIELDS) {
    const value = source[field.key];
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      params[field.key] = field.default;
      continue;
    }
    params[field.key] = stepValue(field, value);
  }
  return params;
}

export function normalizeWithWarnings(raw: unknown): {
  params: SonifyParams;
  warnings: ParamWarning[];
} {
  const source = isRecord(raw) ? raw : {};
  const params = normalizeParams(source);
  const warnings: ParamWarning[] = [];
  for (const field of PARAM_FIELDS) {
    const rawValue = source[field.key];
    if (rawValue == null) continue;
    if (typeof rawValue !== 'number' || !Number.isFinite(rawValue)) {
      warnings.push({ code: 'clamped', key: field.key });
      continue;
    }
    if (roundStep(rawValue, field.step) !== params[field.key]) {
      warnings.push({ code: 'clamped', key: field.key, value: rawValue });
    }
  }
  for (const key of Object.keys(source)) {
    if (!(key in PARAM_FIELD_BY_KEY)) warnings.push({ code: 'unknown_key', key });
  }
  if (params.humanize > HUMANIZE_SOFT_WARNING) {
    warnings.push({ code: 'high_humanize', key: 'humanize', value: params.humanize });
  }
  if (params.breath > BREATH_SOFT_WARNING) {
    warnings.push({ code: 'high_breath', key: 'breath', value: params.breath });
  }
  return { params, warnings };
}

export function paramsEqual(left: SonifyParams, right: SonifyParams): boolean {
  return PARAM_KEYS.every((key) => left[key] === right[key]);
}

export function isDefaultParams(params: SonifyParams): boolean {
  return paramsEqual(normalizeParams(params), DEFAULT_PARAMS);
}

function pythonNumber(value: number): string {
  // Python's json.dumps writes 1.0 for an integral float. The server hashes
  // this exact text, so the client string must match too.
  if (Number.isInteger(value)) return `${value}.0`;
  return String(value);
}

/** Canonical JSON, byte-identical to the server's `params_key`. */
export function paramsKey(params: SonifyParams): string {
  const normalized = normalizeParams(params);
  const body = [...PARAM_KEYS]
    .sort()
    .map((key) => `${JSON.stringify(key)}:${pythonNumber(normalized[key])}`)
    .join(',');
  return `{"params":{${body}},"schema":${SCHEMA_VERSION}}`;
}

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const B64_INDEX: Record<string, number> = Object.fromEntries(
  [...B64].map((char, index) => [char, index]),
);

function utf8Encode(text: string): number[] {
  const bytes: number[] = [];
  for (let index = 0; index < text.length; index += 1) {
    let code = text.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff && index + 1 < text.length) {
      const next = text.charCodeAt(index + 1);
      if (next >= 0xdc00 && next <= 0xdfff) {
        code = 0x10000 + ((code - 0xd800) << 10) + (next - 0xdc00);
        index += 1;
      }
    }
    if (code < 0x80) {
      bytes.push(code);
    } else if (code < 0x800) {
      bytes.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
    } else if (code < 0x10000) {
      bytes.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
    } else {
      bytes.push(
        0xf0 | (code >> 18),
        0x80 | ((code >> 12) & 0x3f),
        0x80 | ((code >> 6) & 0x3f),
        0x80 | (code & 0x3f),
      );
    }
  }
  return bytes;
}

function utf8Decode(bytes: number[]): string {
  let text = '';
  for (let index = 0; index < bytes.length; ) {
    const first = bytes[index];
    if (first < 0x80) {
      text += String.fromCharCode(first);
      index += 1;
      continue;
    }
    let size = 0;
    let code = 0;
    if ((first & 0xe0) === 0xc0) {
      size = 1;
      code = first & 0x1f;
    } else if ((first & 0xf0) === 0xe0) {
      size = 2;
      code = first & 0x0f;
    } else if ((first & 0xf8) === 0xf0) {
      size = 3;
      code = first & 0x07;
    } else {
      throw new Error('invalid utf-8');
    }
    for (let offset = 1; offset <= size; offset += 1) {
      const byte = bytes[index + offset];
      if (byte == null || (byte & 0xc0) !== 0x80) throw new Error('invalid utf-8');
      code = (code << 6) | (byte & 0x3f);
    }
    text += String.fromCodePoint(code);
    index += size + 1;
  }
  return text;
}

function bytesToBase64Url(bytes: number[]): string {
  let out = '';
  for (let index = 0; index < bytes.length; index += 3) {
    const a = bytes[index];
    const b = bytes[index + 1];
    const c = bytes[index + 2];
    out += B64[a >> 2];
    out += B64[((a & 0x03) << 4) | ((b ?? 0) >> 4)];
    if (b == null) break;
    out += B64[((b & 0x0f) << 2) | ((c ?? 0) >> 6)];
    if (c == null) break;
    out += B64[c & 0x3f];
  }
  return out;
}

function base64UrlToBytes(text: string): number[] {
  if (!/^[A-Za-z0-9_-]*$/.test(text)) throw new Error('p is not base64url');
  const bytes: number[] = [];
  let buffer = 0;
  let bits = 0;
  for (const char of text) {
    const value = B64_INDEX[char];
    if (value == null) throw new Error('p is not base64url');
    buffer = (buffer << 6) | value;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      bytes.push((buffer >> bits) & 0xff);
    }
  }
  return bytes;
}

export function encodeParams(params: SonifyParams): string {
  return bytesToBase64Url(utf8Encode(paramsKey(params)));
}

/** Throws on a malformed `p`. Callers that must stay alive catch it. */
export function decodeParams(text: string): SonifyParams {
  if (!text) throw new Error('p is empty');
  if (text.length > P_MAX_LENGTH) throw new Error('p is too long');
  const payload = JSON.parse(utf8Decode(base64UrlToBytes(text))) as unknown;
  if (!isRecord(payload)) throw new Error('p must decode to an object');
  const version = payload.schema ?? SCHEMA_VERSION;
  if (version !== SCHEMA_VERSION) throw new Error('unsupported params schema');
  const body = payload.params ?? payload;
  if (!isRecord(body)) throw new Error('p params must be an object');
  return normalizeParams(body);
}

/** `humanize=false` used to skip the whole layer, tempo clock included. */
export function paramsFromFlags(humanize: boolean, color: boolean): SonifyParams {
  const params = { ...DEFAULT_PARAMS };
  if (!humanize) {
    params.humanize = 0;
    params.breath = 0;
  }
  if (!color) params.color = 0;
  return params;
}

export function paramsFromQuery(
  p: string | null | undefined,
  humanize = true,
  color = true,
): SonifyParams {
  if (p) {
    try {
      return decodeParams(p);
    } catch {
      // A bad shared link opens the room at Default rather than failing.
      return { ...DEFAULT_PARAMS };
    }
  }
  return paramsFromFlags(humanize, color);
}

/** `&p=...`, or empty for Default so old audio URLs keep their cache name. */
export function paramsQuery(params: SonifyParams): string {
  const normalized = normalizeParams(params);
  if (paramsEqual(normalized, DEFAULT_PARAMS)) return '';
  return `&p=${encodeParams(normalized)}`;
}

export function layerHumanize(params: SonifyParams): boolean {
  return params.humanize !== 0 || params.breath !== 0;
}

export function layerColor(params: SonifyParams): boolean {
  return params.color !== 0;
}

export type ParamLayers = { humanize: boolean; color: boolean };

export function paramsLayers(params: SonifyParams): ParamLayers {
  return { humanize: layerHumanize(params), color: layerColor(params) };
}

export function effectiveBpm(baseBpm: number, tempo: number): number {
  // Half-up, never banker's rounding. The server writes the same integer.
  return Math.floor(baseBpm * tempo + 0.5);
}

const SCHEMA_BPM = PARAMS_SCHEMA.baseBpm;

/** The unmodified tempo of a line, before the knob. Comes from the schema. */
export function baseBpmFor(variant: string, ensemble: string): number {
  const value = SCHEMA_BPM[variant];
  if (typeof value === 'number') return value;
  if (value && typeof value === 'object') {
    return value[ensemble] ?? value.classic ?? 90;
  }
  return 90;
}

export function paramValueText(field: ParamsFieldSchema, value: number): string {
  if (field.step >= 1) {
    const text = value.toFixed(0);
    const signed = value > 0 ? `+${text}` : text;
    return field.unit ? `${signed}${field.unit}` : signed;
  }
  const text = value.toFixed(2);
  return field.unit ? `${text}${field.unit}` : text;
}

/** Soft copy only; never blocks a render. */
export function warningsFor(params: SonifyParams): ParamWarning[] {
  const warnings: ParamWarning[] = [];
  if (params.humanize > HUMANIZE_SOFT_WARNING) {
    warnings.push({ code: 'high_humanize', key: 'humanize', value: params.humanize });
  }
  if (params.breath > BREATH_SOFT_WARNING) {
    warnings.push({ code: 'high_breath', key: 'breath', value: params.breath });
  }
  return warnings;
}

export type SonifyProfile = {
  id: string;
  name: string;
  params: SonifyParams;
};

export type ProfileStore = {
  schema: number;
  activeId: string;
  profiles: SonifyProfile[];
};

export const DEFAULT_PROFILE_ID = 'default';
export const PROFILE_NAME_MAX = 40;

export function defaultProfile(): SonifyProfile {
  return { id: DEFAULT_PROFILE_ID, name: 'Default', params: { ...DEFAULT_PARAMS } };
}

export function initialProfileStore(params?: SonifyParams): ProfileStore {
  const active = params ? normalizeParams(params) : { ...DEFAULT_PARAMS };
  return {
    schema: SCHEMA_VERSION,
    activeId: DEFAULT_PROFILE_ID,
    profiles: [{ ...defaultProfile(), params: active }],
  };
}

/** Names are unique case-insensitively. An empty name falls back to a label. */
export function uniqueProfileName(
  name: string,
  profiles: SonifyProfile[],
  exceptId?: string,
): string {
  const base = (name.trim() || 'Bản của tôi').slice(0, PROFILE_NAME_MAX);
  const taken = new Set(
    profiles
      .filter((profile) => profile.id !== exceptId)
      .map((profile) => profile.name.trim().toLocaleLowerCase()),
  );
  if (!taken.has(base.toLocaleLowerCase())) return base;
  for (let suffix = 2; ; suffix += 1) {
    const tail = ` ${suffix}`;
    const candidate = `${base.slice(0, PROFILE_NAME_MAX - tail.length).trimEnd()}${tail}`;
    if (!taken.has(candidate.toLocaleLowerCase())) return candidate;
  }
}

let profileSeq = 0;

function newProfileId(): string {
  profileSeq += 1;
  return `p_${Date.now().toString(36)}${profileSeq.toString(36)}${Math.floor(
    Math.random() * 1296,
  )
    .toString(36)
    .padStart(2, '0')}`;
}

function withProfiles(store: ProfileStore, profiles: SonifyProfile[]): ProfileStore {
  return { ...store, profiles };
}

/** Schema 1 treated `noise` as a multiplier of a per-variant bed. */
function legacyParams(raw: unknown): unknown {
  if (!isRecord(raw)) return raw;
  const noise = raw.noise;
  if (typeof noise !== 'number' || !Number.isFinite(noise)) return raw;
  return { ...raw, noise: noise * 0.1 };
}

export function normalizeProfileStore(raw: unknown, fallback?: SonifyParams): ProfileStore {
  const base = initialProfileStore(fallback);
  if (!isRecord(raw) || !Array.isArray(raw.profiles)) return base;
  const legacy = typeof raw.schema === 'number' && raw.schema < SCHEMA_VERSION;
  const profiles: SonifyProfile[] = [];
  const seen = new Set<string>();
  for (const item of raw.profiles) {
    if (!isRecord(item)) continue;
    const id = typeof item.id === 'string' ? item.id.trim() : '';
    if (!id || seen.has(id)) continue;
    seen.add(id);
    const name =
      id === DEFAULT_PROFILE_ID
        ? 'Default'
        : typeof item.name === 'string' && item.name.trim()
          ? item.name.trim().slice(0, PROFILE_NAME_MAX)
          : 'Bản của tôi';
    const params =
      id === DEFAULT_PROFILE_ID
        ? { ...DEFAULT_PARAMS }
        : normalizeParams(legacy ? legacyParams(item.params) : item.params);
    profiles.push({ id, name, params });
  }
  if (!profiles.some((profile) => profile.id === DEFAULT_PROFILE_ID)) {
    profiles.unshift(defaultProfile());
  }
  const activeId =
    typeof raw.activeId === 'string' && profiles.some((profile) => profile.id === raw.activeId)
      ? raw.activeId
      : DEFAULT_PROFILE_ID;
  return { schema: SCHEMA_VERSION, activeId, profiles };
}

export function activeProfile(store: ProfileStore): SonifyProfile {
  return (
    store.profiles.find((profile) => profile.id === store.activeId) ??
    store.profiles.find((profile) => profile.id === DEFAULT_PROFILE_ID) ??
    defaultProfile()
  );
}

export function selectProfile(store: ProfileStore, id: string): ProfileStore {
  if (!store.profiles.some((profile) => profile.id === id)) return store;
  return { ...store, activeId: id };
}

export function createProfile(
  store: ProfileStore,
  name: string,
  params: SonifyParams,
): { store: ProfileStore; profile: SonifyProfile } {
  const profile: SonifyProfile = {
    id: newProfileId(),
    name: uniqueProfileName(name, store.profiles),
    params: normalizeParams(params),
  };
  return {
    store: { ...withProfiles(store, [...store.profiles, profile]), activeId: profile.id },
    profile,
  };
}

export function duplicateProfile(
  store: ProfileStore,
  id: string,
  name?: string,
): { store: ProfileStore; profile: SonifyProfile } {
  const source =
    store.profiles.find((profile) => profile.id === id) ?? activeProfile(store);
  return createProfile(store, name ?? `${source.name} 2`, source.params);
}

export function renameProfile(store: ProfileStore, id: string, name: string): ProfileStore {
  if (id === DEFAULT_PROFILE_ID) return store;
  return withProfiles(
    store,
    store.profiles.map((profile) =>
      profile.id === id
        ? { ...profile, name: uniqueProfileName(name, store.profiles, id) }
        : profile,
    ),
  );
}

export function updateProfileParams(
  store: ProfileStore,
  id: string,
  params: SonifyParams,
): ProfileStore {
  if (id === DEFAULT_PROFILE_ID) return store;
  return withProfiles(
    store,
    store.profiles.map((profile) =>
      profile.id === id ? { ...profile, params: normalizeParams(params) } : profile,
    ),
  );
}

export function deleteProfile(store: ProfileStore, id: string): ProfileStore {
  if (id === DEFAULT_PROFILE_ID) return store;
  const profiles = store.profiles.filter((profile) => profile.id !== id);
  const activeId = store.activeId === id ? DEFAULT_PROFILE_ID : store.activeId;
  return { ...withProfiles(store, profiles), activeId };
}

export function resetProfile(store: ProfileStore, id: string): ProfileStore {
  if (id === DEFAULT_PROFILE_ID) return store;
  return updateProfileParams(store, id, DEFAULT_PARAMS);
}

export type PlayPlan = {
  store: ProfileStore;
  savedParams: SonifyParams;
  draft: SonifyParams;
  savedName: string | null;
};

/** Decide what Play does with a draft that was never explicitly saved. */
export function planPlayParams(
  store: ProfileStore,
  draft: SonifyParams,
  saved: SonifyParams,
): PlayPlan {
  if (paramsEqual(draft, saved)) {
    return { store, savedParams: saved, draft: saved, savedName: null };
  }
  const shaped = normalizeParams(draft);
  const profile = activeProfile(store);
  if (profile.id === DEFAULT_PROFILE_ID) {
    // A default draft is not a new profile; it is the immutable Default.
    if (isDefaultParams(shaped)) {
      return { store, savedParams: shaped, draft: shaped, savedName: null };
    }
    const created = createProfile(store, 'Bản của tôi', shaped);
    return {
      store: created.store,
      savedParams: created.profile.params,
      draft: created.profile.params,
      savedName: created.profile.name,
    };
  }
  return {
    store: updateProfileParams(store, profile.id, shaped),
    savedParams: shaped,
    draft: shaped,
    savedName: profile.name,
  };
}

export function serializeProfileStore(store: ProfileStore): string {
  return JSON.stringify(normalizeProfileStore(store));
}

export function parseProfileStore(text: string | null | undefined): ProfileStore | null {
  if (!text) return null;
  try {
    return normalizeProfileStore(JSON.parse(text));
  } catch {
    return null;
  }
}
