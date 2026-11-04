import { ALL_TIERS, DEFAULT_PARAMS, PARAM_FIELD_BY_KEY } from './params';
import {
  anchorRatio,
  changedKeysForPanel,
  defaultRatio,
  fieldAnchor,
  helpText,
  hiddenChangedKeys,
  panelContentWidth,
  panelFields,
  panelGroups,
  panelColumns,
  panelLayout,
  panelPushes,
  panelWidthFor,
  paramDisplay,
  paramSummary,
  spectrumLevels,
} from './tuningDisplay';

function equal<T>(actual: T, expected: T, label = '') {
  if (actual !== expected) {
    throw new Error(`${label} expected ${String(expected)}, got ${String(actual)}`);
  }
}

function near(actual: number, expected: number, label: string, epsilon = 1e-9) {
  if (Math.abs(actual - expected) > epsilon) {
    throw new Error(`${label} expected ${expected}, got ${actual}`);
  }
}

const guitar = { variant: 'guitar', span: '1M', ensemble: 'torroba', tiers: [...ALL_TIERS] };
const symphony = { variant: 'symphony', span: '1M', ensemble: 'classic', tiers: [...ALL_TIERS] };

equal(panelWidthFor(960), 640, '960 clamps to 640');
equal(panelWidthFor(1024), 640, '1024 clamps to 640');
equal(panelWidthFor(1440), 864, '1440 is 60%');
equal(panelWidthFor(1920), 1152, '1920 is 60%');
equal(panelWidthFor(2560), 1280, '2560 clamps to 1280');

equal(panelContentWidth(1920), 1040, 'content max at 1920');
equal(panelContentWidth(2560), 1040, 'content max at 2560');
equal(panelContentWidth(1440), 816, 'content at 1440');

equal(panelPushes(1878), false, '1878 does not push');
equal(panelPushes(1879), true, '1879 pushes');
equal(panelPushes(1920), true, '1920 pushes');

const layout1366 = panelLayout(1366, 660, guitar);
equal(layout1366.columns, 3, '1366 columns');
equal(layout1366.dense, true, '1366 dense');
equal(layout1366.rowHeight, 50, '1366 row height');
equal(layout1366.estimatedHeight, 636, '1366 estimated height');

const layout1440 = panelLayout(1440, 800, guitar);
equal(layout1440.columns, 3, '1440 columns');
equal(layout1440.dense, false, '1440 not dense');
equal(layout1440.rowHeight, 60, '1440 row height');
equal(layout1440.estimatedHeight, 720, '1440 estimated height');

const layout1920 = panelLayout(1920, 980, guitar);
equal(layout1920.columns, 3, '1920 columns');
equal(layout1920.contentWidth, 1040, '1920 content');
equal(layout1920.estimatedHeight, 720, '1920 estimated height');

const layout1024 = panelLayout(1024, 620, guitar);
equal(layout1024.columns, 2, '1024 columns');
equal(layout1024.dense, true, '1024 dense');
equal(layout1024.dangStacked, true, '1024 stacks form');
equal(layout1024.estimatedHeight, 900, '1024 estimated height');

const layout1280 = panelLayout(1280, 600, guitar);
equal(layout1280.columns, 3, '1280 columns');
equal(layout1280.dense, true, '1280 dense');
equal(layout1280.dangStacked, false, '1280 form side by side');

const guitarFields = panelFields(guitar).map((field) => field.key);
const symphonyFields = panelFields(symphony).map((field) => field.key);
if (!guitarFields.includes('guitar_high')) throw new Error('guitar voices visible on guitar');
if (symphonyFields.includes('guitar_high')) throw new Error('guitar voices hidden on symphony');

const guitarGroups = panelGroups(guitar);
const guitarGroup = guitarGroups.find((group) => group.id === 'guitar');
if (guitarGroup?.fields.some((field) => field.key.startsWith('guitar_'))) {
  throw new Error('guitar voices must not be in the generic guitar group');
}
if (guitarGroups.some((group) => group.id === 'space')) {
  throw new Error('register belongs in the mixer, not a generic group');
}
if (guitarGroups.some((group) => group.id === 'performance' && group.fields.some((field) => field.key === 'color'))) {
  throw new Error('color belongs in the mixer, not a generic group');
}
const guitarColumns = panelColumns(guitar, 3);
const merged = guitarColumns.flat().find((group) => group.id === 'harmony+guitar');
if (!merged || merged.label !== 'Hòa âm / Guitar') {
  throw new Error('harmony and guitar must share one header');
}

const withGuitar = { ...DEFAULT_PARAMS, guitar_high: 3 };
equal(changedKeysForPanel(withGuitar, guitar).length, 1, 'guitar voices count on guitar');
equal(changedKeysForPanel(withGuitar, symphony).length, 0, 'guitar voices hidden on symphony');
equal(hiddenChangedKeys(withGuitar, symphony).length, 1, 'hidden guitar voice on symphony');
equal(paramSummary(withGuitar, guitar), '1 thay đổi', 'panel summary counts guitar');
equal(paramSummary(withGuitar, symphony), '1 ẩn', 'panel summary hides guitar');

const noise = PARAM_FIELD_BY_KEY.noise;
equal(fieldAnchor(noise), 0, 'noise anchor is zero');
near(anchorRatio(noise), 0, 'noise anchor ratio');
near(defaultRatio(noise), 0.2, 'noise default ratio is 20%');

const humanize = PARAM_FIELD_BY_KEY.humanize;
near(anchorRatio(humanize), 0.5, 'humanize anchor is centre');
near(defaultRatio(humanize), 0.5, 'humanize default is centre');

const tempo = paramDisplay(PARAM_FIELD_BY_KEY.tempo, 1.08, { baseBpm: 96 });
equal(tempo.primary, '+8%', 'tempo percent');
equal(tempo.secondary, '104 BPM', 'tempo BPM');
equal(tempo.detail, '1.08× · 104 BPM', 'tempo detail');

equal(paramDisplay(PARAM_FIELD_BY_KEY.humanize, 1.6).primary, '+60%', 'humanize +60%');
equal(paramDisplay(PARAM_FIELD_BY_KEY.humanize, 0.4).primary, '−60%', 'humanize −60%');
equal(paramDisplay(PARAM_FIELD_BY_KEY.dynamics, 1.5).primary, '+50%', 'dynamics +50%');
equal(paramDisplay(PARAM_FIELD_BY_KEY.dynamics, 0.5).primary, '−50%', 'dynamics −50%');
equal(paramDisplay(PARAM_FIELD_BY_KEY.noise, 0.1).primary, '0.10%', 'noise percent');
equal(paramDisplay(PARAM_FIELD_BY_KEY.guitar_high, -3).primary, '−3', 'guitar offset');

const motionHelp = helpText(PARAM_FIELD_BY_KEY.motion);
if (motionHelp.includes('0 giữ') || motionHelp.includes('2 đổi')) {
  throw new Error('motion help still uses the old 0/1/2 wording');
}
if (!motionHelp.includes('−100%…+100%')) {
  throw new Error('motion help must describe the signed range');
}
const colorHelp = helpText(PARAM_FIELD_BY_KEY.color);
if (colorHelp.includes('0 là khô, 2 là')) {
  throw new Error('color help still uses the old 0/2 wording');
}

const flat = spectrumLevels(DEFAULT_PARAMS, 'guitar');
near(flat[0], 0.55, 'spectrum low flat');
near(flat[1], 0.55, 'spectrum mid flat');
near(flat[2], 0.55, 'spectrum high flat');

const bright = spectrumLevels({ ...DEFAULT_PARAMS, register: 2 }, 'symphony');
near(bright[0], 0.25, 'register 2 lowers low');
near(bright[2], 0.85, 'register 2 raises high');

const guitarHigh = spectrumLevels({ ...DEFAULT_PARAMS, guitar_high: 12 }, 'guitar');
near(guitarHigh[2], 0.77, 'guitar high adds to spectrum');
const nonGuitarHigh = spectrumLevels({ ...DEFAULT_PARAMS, guitar_high: 12 }, 'symphony');
near(nonGuitarHigh[2], 0.55, 'guitar high ignored outside guitar');
