import {
  DEFAULT_HASH,
  DEFAULT_PARAMS,
  PARAM_FIELDS,
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
  paramsEqual,
  paramsFromFlags,
  paramsFromQuery,
  paramsKey,
  paramsQuery,
  parseProfileStore,
  renameProfile,
  resetProfile,
  selectProfile,
  serializeProfileStore,
  stepValue,
  uniqueProfileName,
  updateProfileParams,
} from './params';

function equal<T>(actual: T, expected: T, label = '') {
  if (actual !== expected) {
    throw new Error(`${label} expected ${String(expected)}, got ${String(actual)}`);
  }
}

function ok(value: boolean, label: string) {
  if (!value) throw new Error(label);
}

function same(a: Record<string, number>, b: Record<string, number>, label = '') {
  if (!paramsEqual(a, b)) {
    throw new Error(`${label} ${JSON.stringify(a)} != ${JSON.stringify(b)}`);
  }
}

ok(DEFAULT_HASH === '35d9a160e9a3', 'default hash is pinned');
ok(Object.keys(DEFAULT_PARAMS).length === 7, 'seven knobs');

const tempo = PARAM_FIELDS.find((field) => field.key === 'tempo');
ok(Boolean(tempo), 'tempo field exists');
if (!tempo) throw new Error('missing tempo');
equal(tempo.min, 0.75, 'tempo min');
equal(tempo.max, 1.25, 'tempo max');
equal(tempo.step, 0.01, 'tempo step');
equal(stepValue(tempo, 0.9600000001), 0.96, 'round to the step');

same(normalizeParams({ tempo: 0.96 }), { ...DEFAULT_PARAMS, tempo: 0.96 }, 'missing keys default');
same(normalizeParams({ tempo: 1.4, humanize: 9 }), { ...DEFAULT_PARAMS, tempo: 1.25, humanize: 1.5 }, 'clamped');
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
  '{"params":{"breath":1.0,"color":1.0,"density":1.0,"dynamics":1.0,"humanize":1.0,"noise":1.0,"tempo":0.96},"schema":1}',
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

console.log('musicalize params tests passed');
