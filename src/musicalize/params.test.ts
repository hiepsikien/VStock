import {
  ALL_TIERS,
  DEFAULT_HASH,
  DEFAULT_PARAMS,
  LINK_SCHEMA_VERSION,
  PARAM_FIELDS,
  applyTiers,
  renderParams,
  visibleFields,
  baseBpmFor,
  createProfile,
  decodeParams,
  deleteProfile,
  duplicateProfile,
  effectiveBpm,
  encodeParams,
  initialProfileStore,
  isDefaultParams,
  layerColor,
  layerHumanize,
  normalizeParams,
  normalizeWithWarnings,
  paramValueText,
  paramsEqual,
  paramsFromFlags,
  paramsFromQuery,
  paramsKey,
  paramsQuery,
  parseProfileStore,
  planPlayParams,
  renameProfile,
  resetProfile,
  selectProfile,
  serializeProfileStore,
  stepValue,
  uniqueProfileName,
  updateProfileParams,
  warningText,
  warningTexts,
} from './params';

function equal<T>(actual: T, expected: T, label = '') {
  if (actual !== expected) {
    throw new Error(`${label} expected ${String(expected)}, got ${String(actual)}`);
  }
}

function ok(value: boolean, label: string) {
  if (!value) throw new Error(label);
}

function same(a: Record<string, number | string | boolean>, b: Record<string, number | string | boolean>, label = '') {
  if (!paramsEqual(a, b)) {
    throw new Error(`${label} ${JSON.stringify(a)} != ${JSON.stringify(b)}`);
  }
}

ok(DEFAULT_HASH === 'ce9ab87f3a0d', 'default hash is pinned');
ok(Object.keys(DEFAULT_PARAMS).length === 16, 'sixteen knobs');

const tempo = PARAM_FIELDS.find((field) => field.key === 'tempo');
ok(Boolean(tempo), 'tempo field exists');
if (!tempo) throw new Error('missing tempo');
equal(tempo.min, 0.75, 'tempo min');
equal(tempo.max, 1.25, 'tempo max');
equal(tempo.step, 0.01, 'tempo step');
equal(stepValue(tempo, 0.9600000001), 0.96, 'round to the step');

const color = PARAM_FIELDS.find((field) => field.key === 'color');
ok(Boolean(color), 'color field exists');
if (!color) throw new Error('missing color');
equal(color.min, 0, 'color min');
equal(color.max, 2, 'color max');
equal(color.step, 0.01, 'color step');

for (const key of ['humanize', 'breath', 'density']) {
  const field = PARAM_FIELDS.find((item) => item.key === key);
  ok(Boolean(field), `${key} field exists`);
  if (!field) throw new Error(`missing ${key}`);
  equal(field.min, 0, `${key} min`);
  equal(field.max, 2, `${key} max`);
  equal(field.step, 0.05, `${key} step`);
  equal(field.default, 1, `${key} default is centered`);
}

const noise = PARAM_FIELDS.find((field) => field.key === 'noise');
ok(Boolean(noise), 'noise field exists');
if (!noise) throw new Error('missing noise');
equal(noise.min, 0, 'noise min');
equal(noise.max, 0.5, 'noise max');
equal(noise.step, 0.05, 'noise step');
equal(noise.default, 0.1, 'noise default');
equal(noise.unit, '%', 'noise unit');
equal(paramValueText(noise, 0.1), '0.10%', 'noise value text');
equal(paramValueText(color, 2), '2.00', 'color value text');
equal(paramValueText(tempo, 1), '1.00×', 'tempo value text');

const guitar = PARAM_FIELDS.find((field) => field.key === 'guitar_bass');
ok(Boolean(guitar), 'guitar field exists');
if (!guitar) throw new Error('missing guitar');
equal(guitar.min, -12, 'guitar min');
equal(guitar.max, 12, 'guitar max');
equal(guitar.step, 1, 'guitar step');
equal(guitar.default, 0, 'guitar default');
equal(guitar.unit, '', 'guitar unit');
equal(guitar.signed, true, 'guitar signed');
equal(paramValueText(guitar, 0), '0', 'guitar zero text');
equal(paramValueText(guitar, 4), '+4', 'guitar positive text');
equal(paramValueText(guitar, -8), '-8', 'guitar negative text');

same(normalizeParams({ tempo: 0.96 }), { ...DEFAULT_PARAMS, tempo: 0.96 }, 'missing keys default');
same(normalizeParams({ tempo: 1.4, humanize: 9 }), { ...DEFAULT_PARAMS, tempo: 1.25, humanize: 2.0 }, 'clamped');
same(normalizeParams({ tempo: 'fast' }), DEFAULT_PARAMS, 'wrong type falls back');
same(normalizeParams({ nope: 1 }), DEFAULT_PARAMS, 'unknown key dropped');

const warnings = normalizeWithWarnings({ tempo: 1.4, humanize: 1.4, nope: 1 }).warnings;
ok(warnings.some((warning) => warning.code === 'clamped' && warning.key === 'tempo'), 'clamp warning');
ok(warnings.some((warning) => warning.code === 'unknown_key'), 'unknown warning');
ok(warnings.some((warning) => warning.code === 'high_humanize'), 'soft humanize warning');

ok(isDefaultParams(DEFAULT_PARAMS), 'default detected');
ok(!isDefaultParams({ ...DEFAULT_PARAMS, tempo: 0.96 }), 'non-default detected');
equal(paramsQuery(DEFAULT_PARAMS), '', 'default has no p');
ok(paramsQuery({ ...DEFAULT_PARAMS, tempo: 0.96 }).startsWith('&p='), 'profile has p');
ok(!paramsQuery({ ...DEFAULT_PARAMS, tempo: 0.96 }).includes('humanize='), 'p replaces the old flags');

const shaped = { ...DEFAULT_PARAMS, tempo: 0.96, breath: 0.9 };
same(decodeParams(encodeParams(shaped)), shaped, 'encode/decode round trip');
equal(
  encodeParams({ ...DEFAULT_PARAMS, tempo: 0.9600000001 }),
  encodeParams({ ...DEFAULT_PARAMS, tempo: 0.96 }),
  'round before encode',
);
equal(
  paramsKey({ ...DEFAULT_PARAMS, tempo: 0.9600000001 }),
  paramsKey({ ...DEFAULT_PARAMS, tempo: 0.96 }),
  'round before the canonical key',
);
equal(
  paramsKey({ ...DEFAULT_PARAMS, tempo: 0.96 }),
  '{"params":{"breath":1.0,"color":1.0,"density":1.0,"dynamics":1.0,"frame":"auto","guitar_bass":0.0,"guitar_high":0.0,"guitar_mid":0.0,"harmony":1.0,"humanize":1.0,"meter":"auto","motion":1.0,"noise":0.1,"register":1.0,"technique":1.0,"tempo":0.96},"schema":3}',
  'canonical text matches the server',
);

let threw = false;
try {
  decodeParams('not-base64!');
} catch {
  threw = true;
}
ok(threw, 'bad p throws');

same(paramsFromFlags(false, true), { ...DEFAULT_PARAMS, humanize: 0, breath: 0 }, 'h=0 stops breath');
same(paramsFromFlags(true, false), { ...DEFAULT_PARAMS, color: 0 }, 'c=0 stops color');
same(paramsFromQuery(encodeParams(shaped)), shaped, 'p wins in a query');
same(paramsFromQuery(null, false, false), paramsFromFlags(false, false), 'legacy query');
same(paramsFromQuery('bad!', true, true), DEFAULT_PARAMS, 'bad shared p opens Default');

ok(layerHumanize(DEFAULT_PARAMS), 'default humanizes');
ok(!layerHumanize(paramsFromFlags(false, true)), 'h=0 layer off');
ok(layerHumanize({ ...DEFAULT_PARAMS, humanize: 0, breath: 1 }), 'breath alone keeps the layer');
ok(layerColor(DEFAULT_PARAMS), 'default colors');
ok(!layerColor({ ...DEFAULT_PARAMS, color: 0 }), 'color off');

equal(baseBpmFor('symphony', 'classic'), 90, 'symphony base');
equal(baseBpmFor('guitar', 'torroba'), 96, 'guitar base follows ensemble');
equal(effectiveBpm(90, 0.85), 77, 'half-up at .5');
equal(effectiveBpm(90, 0.95), 86, 'half-up at .5 again');
ok(Number.isInteger(effectiveBpm(88, 0.9)), 'derived BPM stays an integer');

let store = initialProfileStore();
equal(store.profiles.length, 1, 'default profile exists');
equal(store.activeId, 'default', 'default is active');

const created = createProfile(store, 'Ấm tối', { ...DEFAULT_PARAMS, tempo: 0.96 });
store = created.store;
equal(store.profiles.length, 2, 'profile created');
equal(store.activeId, created.profile.id, 'new profile is active');
equal(created.profile.name, 'Ấm tối', 'name kept');
same(created.profile.params, { ...DEFAULT_PARAMS, tempo: 0.96 }, 'params kept');

const duplicateName = createProfile(store, 'Ấm tối', DEFAULT_PARAMS);
equal(duplicateName.profile.name, 'Ấm tối 2', 'duplicate names get a suffix');

store = renameProfile(store, created.profile.id, 'Tối');
equal(store.profiles.find((profile) => profile.id === created.profile.id)?.name, 'Tối', 'rename keeps id');
equal(renameProfile(store, 'default', 'Nope'), store, 'Default cannot be renamed');

const duplicated = duplicateProfile(store, created.profile.id);
store = duplicated.store;
same(duplicated.profile.params, created.profile.params, 'duplicate copies params');
ok(duplicated.profile.id !== created.profile.id, 'duplicate gets an id');

store = resetProfile(store, duplicated.profile.id);
same(
  store.profiles.find((profile) => profile.id === duplicated.profile.id)?.params ?? {},
  DEFAULT_PARAMS,
  'reset keeps the name and restores defaults',
);
equal(
  store.profiles.find((profile) => profile.id === duplicated.profile.id)?.name,
  duplicated.profile.name,
  'reset keeps the name',
);

store = updateProfileParams(store, created.profile.id, { ...DEFAULT_PARAMS, density: 0.5 });
same(
  store.profiles.find((profile) => profile.id === created.profile.id)?.params ?? {},
  { ...DEFAULT_PARAMS, density: 0.5 },
  'update params',
);
equal(updateProfileParams(store, 'default', { ...DEFAULT_PARAMS, tempo: 0.8 }), store, 'Default is immutable');

store = selectProfile(store, 'default');
equal(store.activeId, 'default', 'select default');

store = deleteProfile(store, created.profile.id);
equal(store.profiles.some((profile) => profile.id === created.profile.id), false, 'delete removes');
equal(deleteProfile(store, 'default'), store, 'Default cannot be deleted');

const activeDeleted = deleteProfile(selectProfile(store, duplicated.profile.id), duplicated.profile.id);
equal(activeDeleted.activeId, 'default', 'deleting the active profile returns to Default');

const serialized = serializeProfileStore(store);
const parsed = parseProfileStore(serialized);
ok(parsed != null, 'store parses');
if (parsed) {
  equal(parsed.activeId, store.activeId, 'active id survives');
  equal(parsed.profiles.length, store.profiles.length, 'profiles survive');
}
equal(parseProfileStore('{oops'), null, 'bad json ignored');
ok(parsed != null && isDefaultParams(parsed.profiles[0].params), 'Default params survive');
equal(uniqueProfileName('   ', store.profiles), 'Bản của tôi', 'empty name gets a label');
equal(uniqueProfileName('x'.repeat(60), store.profiles).length, 40, 'name is capped');

const legacyStore = parseProfileStore(
  JSON.stringify({
    schema: 1,
    activeId: 'old',
    profiles: [{ id: 'old', name: 'Cũ', params: { ...DEFAULT_PARAMS, noise: 1 } }],
  }),
);
equal(
  legacyStore?.profiles.find((profile) => profile.id === 'old')?.params.noise,
  0.1,
  'schema 1 noise multiplier becomes a percent',
);

const v2Store = parseProfileStore(
  JSON.stringify({
    schema: 2,
    activeId: 'v2',
    profiles: [{ id: 'v2', name: 'V2', params: { ...DEFAULT_PARAMS, noise: 0.2 } }],
  }),
);
equal(
  v2Store?.profiles.find((profile) => profile.id === 'v2')?.params.noise,
  0.2,
  'schema 2 noise is not scaled again',
);

let playStore = initialProfileStore();
const playDefault = playStore.profiles[0].params;
let plan = planPlayParams(playStore, playDefault, playDefault);
equal(plan.store, playStore, 'unchanged draft does not touch the store');
equal(plan.savedName, null, 'unchanged draft has no auto-save notice');

plan = planPlayParams(playStore, { ...DEFAULT_PARAMS, tempo: 0.96 }, playDefault);
equal(plan.store.profiles.length, 2, 'changed Default draft creates one copy');
equal(plan.savedName, 'Bản của tôi', 'auto-save names the new profile');
same(plan.savedParams, { ...DEFAULT_PARAMS, tempo: 0.96 }, 'auto-save plays the draft');

const oneCopy = plan.store;
const firstId = oneCopy.activeId;
plan = planPlayParams(oneCopy, { ...DEFAULT_PARAMS, density: 0.5 }, plan.savedParams);
equal(plan.store.profiles.length, 2, 'second Play updates the same copy');
equal(plan.store.activeId, firstId, 'second Play keeps the same active profile');
same(plan.savedParams, { ...DEFAULT_PARAMS, density: 0.5 }, 'second Play saves the new draft');

plan = planPlayParams(playStore, playDefault, { ...DEFAULT_PARAMS, tempo: 0.96 });
equal(plan.store.profiles.length, 1, 'a default draft never creates an empty copy');
equal(plan.savedName, null, 'a default draft has no notice');

console.log('musicalize params tests passed');


ok(ALL_TIERS.join(',') === 'A,B,C', 'all tiers bundled');
ok(!visibleFields('guitar', '1D', ALL_TIERS, 'classic').some((field) => field.key === 'technique'), 'classic hides technique');
ok(visibleFields('guitar', '1D', ALL_TIERS, 'bach').some((field) => field.key === 'technique'), 'bach sees technique');
ok(visibleFields('guitar', '1D', ALL_TIERS, 'torroba').some((field) => field.key === 'technique'), 'torroba sees technique');
ok(!visibleFields('symphony', '1D', ALL_TIERS).some((field) => field.key === 'technique'), 'symphony hides technique');
ok(visibleFields('symphony', '1M', ALL_TIERS).some((field) => field.key === 'frame'), 'long span sees frame');
ok(!visibleFields('symphony', '1D', ALL_TIERS).some((field) => field.key === 'frame'), 'daily hides frame');
ok(!visibleFields('guitar', '1D', ALL_TIERS, 'classic').some((field) => field.key === 'meter'), 'meter hides outside torroba');
ok(visibleFields('guitar', '1D', ALL_TIERS, 'torroba').some((field) => field.key === 'meter'), 'meter shows for torroba');
const tiered = applyTiers({ ...DEFAULT_PARAMS, harmony: 0, technique: 2 }, ['A']);
ok(tiered.harmony === 1 && tiered.technique === 1, 'tier A strips B/C');
ok(normalizeParams({ frame: 'nope' }).frame === 'auto', 'unknown choice falls back');
ok(LINK_SCHEMA_VERSION === 2, 'link schema stays 2');


const effective = renderParams(
  { ...DEFAULT_PARAMS, technique: 2, harmony: 0.5 },
  'guitar',
  '1D',
  'classic',
  ALL_TIERS,
);
ok(effective.technique === 1, 'renderParams drops inapplicable technique');
ok(effective.harmony === 0.5, 'renderParams keeps applicable harmony');

ok(
  warningText({ code: 'inapplicable', key: 'technique' }).includes('Kỹ thuật'),
  'server warning uses the field label',
);
ok(
  warningTexts([
    { code: 'inapplicable', key: 'technique' },
    { code: 'inapplicable', key: 'technique' },
    { code: 'tier_disabled', key: 'harmony' },
  ]).length === 2,
  'warning copy is deduplicated',
);
