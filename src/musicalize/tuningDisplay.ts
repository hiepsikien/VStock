import {
  PARAM_FIELDS,
  PARAM_FIELD_BY_KEY,
  PARAM_GROUPS,
  effectiveBpm,
  numberValue,
  visibleFields,
  type ParamsFieldSchema,
  type ParamValue,
  type SonifyParams,
} from './params';
import { COLUMN_WIDTH, WIDE_BREAKPOINT } from './palette';

export const PANEL_MIN_WIDTH = 640;
export const PANEL_MAX_WIDTH = 1280;
export const PANEL_CONTENT_MAX = 1040;
export const PANEL_PUSH_CHART_MIN = 440;
export const DENSE_ROW_MAX_HEIGHT = 740;
export const DENSE_ROW_HEIGHT = 48;
export const COMFORTABLE_ROW_HEIGHT = 58;
export const PANEL_STATUS_HEIGHT = 24;

export const GUITAR_VOICE_KEYS = new Set(['guitar_high', 'guitar_mid', 'guitar_bass']);
const MIXER_KEYS = new Set(['register']);
const GROUP_LABELS: Record<string, string> = {
  performance: 'Trình diễn',
  texture: 'Chất liệu',
  guitar: 'Guitar',
  harmony: 'Hòa âm',
  space: 'Không gian',
  form: 'Dáng',
};

export type PanelContext = {
  variant?: string;
  span?: string;
  ensemble?: string;
  tiers: string[];
};

export type PanelLayout = {
  columns: 1 | 2 | 3;
  dense: boolean;
  rowHeight: number;
  contentWidth: number;
  dangStacked: boolean;
  estimatedHeight: number;
};

export type ParamDisplay = {
  primary: string;
  secondary?: string;
  negativeLabel: string;
  positiveLabel: string;
};

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

/** 50–67% of the viewport, clamped so a narrow PC still has room. */
export function panelWidthFor(windowWidth: number): number {
  return clamp(Math.round(windowWidth * 0.6), PANEL_MIN_WIDTH, PANEL_MAX_WIDTH);
}

/** Overlay and push leave the same visible chart; only push avoids covering it. */
export function panelPushes(windowWidth: number): boolean {
  return windowWidth - COLUMN_WIDTH - panelWidthFor(windowWidth) >= PANEL_PUSH_CHART_MIN;
}

export function panelContentWidth(windowWidth: number): number {
  if (windowWidth < WIDE_BREAKPOINT) return Math.min(windowWidth - 32, 640);
  return Math.min(panelWidthFor(windowWidth) - 48, PANEL_CONTENT_MAX);
}

/** The fields the panel actually renders. Guitar voices only exist on guitar. */
export function panelFields(context: PanelContext): ParamsFieldSchema[] {
  return visibleFields(context.variant, context.span, context.tiers, context.ensemble).filter(
    (field) => !GUITAR_VOICE_KEYS.has(field.key) || context.variant === 'guitar',
  );
}

/** Groups for the columns. Voices live in the mixer; register also lives there. */
export function panelGroups(context: PanelContext): typeof PARAM_GROUPS {
  const visible = new Set(panelFields(context).map((field) => field.key));
  return PARAM_GROUPS.map((group) => ({
    ...group,
    label: GROUP_LABELS[group.id] ?? group.label,
    fields: group.fields.filter((field) => {
      if (!visible.has(field.key)) return false;
      if (MIXER_KEYS.has(field.key)) return false;
      if (group.id === 'guitar' && GUITAR_VOICE_KEYS.has(field.key)) return false;
      return true;
    }),
  })).filter((group) => group.fields.length > 0);
}

export function changedKeysForPanel(params: SonifyParams, context: PanelContext): string[] {
  const visible = new Set(panelFields(context).map((field) => field.key));
  return Object.entries(params)
    .filter(([key, value]) => {
      const field = PARAM_FIELD_BY_KEY[key];
      return Boolean(field) && visible.has(key) && value !== field.default;
    })
    .map(([key]) => key);
}

export function hiddenChangedKeys(params: SonifyParams, context: PanelContext): string[] {
  const visible = new Set(panelFields(context).map((field) => field.key));
  return Object.entries(params)
    .filter(([key, value]) => {
      const field = PARAM_FIELD_BY_KEY[key];
      return Boolean(field) && !visible.has(key) && value !== field.default;
    })
    .map(([key]) => key);
}

export function paramSummary(params: SonifyParams, context: PanelContext): string {
  const count = changedKeysForPanel(params, context).length;
  return count === 0 ? 'Default' : `${count} thay đổi`;
}

export function fieldCenter(field: ParamsFieldSchema): number {
  return typeof field.default === 'number' ? field.default : field.min;
}

/** Noise is an amount: its fill and centre are anchored at zero. */
export function fieldAnchor(field: ParamsFieldSchema): number {
  if (field.key === 'noise') return 0;
  return fieldCenter(field);
}

export function anchorRatio(field: ParamsFieldSchema): number {
  const span = field.max - field.min;
  if (span <= 0) return 0;
  return clamp((fieldAnchor(field) - field.min) / span, 0, 1);
}

export function defaultRatio(field: ParamsFieldSchema): number {
  const span = field.max - field.min;
  if (span <= 0) return 0;
  return clamp((fieldCenter(field) - field.min) / span, 0, 1);
}

function signed(value: number, digits = 0): string {
  const rounded = digits > 0 ? Number(value.toFixed(digits)) : Math.round(value);
  if (rounded > 0) return `+${rounded}`;
  if (rounded < 0) return `−${Math.abs(rounded)}`;
  return '0';
}

const FIELD_ENDS: Record<string, { negative: string; positive: string }> = {
  tempo: { negative: 'Chậm', positive: 'Nhanh' },
  humanize: { negative: 'Ít', positive: 'Nhiều' },
  breath: { negative: 'Đều', positive: 'Cong câu' },
  color: { negative: 'Khô', positive: 'Đậm' },
  dynamics: { negative: 'Phẳng', positive: 'Tương phản' },
  noise: { negative: 'Sạch', positive: 'Nhiễu' },
  density: { negative: 'Thưa', positive: 'Dày' },
  harmony: { negative: 'Tối giản', positive: 'Nhiều màu' },
  motion: { negative: 'Giữ lâu', positive: 'Dồn dập' },
  register: { negative: 'Thấp/ấm', positive: 'Cao/sáng' },
  technique: { negative: 'Dễ', positive: 'Điêu luyện' },
  guitar_high: { negative: 'Nhỏ', positive: 'Lớn' },
  guitar_mid: { negative: 'Nhỏ', positive: 'Lớn' },
  guitar_bass: { negative: 'Nhỏ', positive: 'Lớn' },
};

export function paramDisplay(
  field: ParamsFieldSchema,
  value: ParamValue,
  options: { baseBpm?: number } = {},
): ParamDisplay {
  const ends = FIELD_ENDS[field.key] ?? { negative: 'Giảm', positive: 'Tăng' };
  const labels = { negativeLabel: ends.negative, positiveLabel: ends.positive };
  if (field.type === 'choice') {
    const choice = field.choices.find((item) => item.value === value);
    return { primary: choice?.label ?? String(value), ...labels };
  }
  if (field.type === 'toggle') {
    return { primary: value ? 'Bật' : 'Tắt', ...labels };
  }
  const number = typeof value === 'number' && Number.isFinite(value) ? value : field.min;
  if (field.key === 'tempo') {
    const bpm = options.baseBpm == null ? null : effectiveBpm(options.baseBpm, number);
    return {
      primary: `${signed((number - 1) * 100)}%`,
      secondary: bpm == null ? undefined : `${bpm} BPM`,
      ...labels,
    };
  }
  if (field.key === 'noise') {
    return {
      primary: `${number.toFixed(2)}%`,
      secondary: 'mặc định 0.10%',
      ...labels,
    };
  }
  if (GUITAR_VOICE_KEYS.has(field.key)) {
    return {
      primary: signed(number),
      secondary: `${Math.round(number)} velocity`,
      ...labels,
    };
  }
  return {
    primary: `${signed((number - 1) * 100)}%`,
    secondary: number.toFixed(2),
    ...labels,
  };
}

/** Estimated preview only. The label below the card says it is not audio. */
export function spectrumLevels(
  params: SonifyParams,
  variant?: string,
): [number, number, number] {
  const register = numberValue(params, 'register');
  const tilt = (register - 1) * 0.3;
  const guitar = variant === 'guitar';
  const low = 0.55 - tilt + (guitar ? (numberValue(params, 'guitar_bass') / 12) * 0.22 : 0);
  const mid = 0.55 + (guitar ? (numberValue(params, 'guitar_mid') / 12) * 0.22 : 0);
  const high = 0.55 + tilt + (guitar ? (numberValue(params, 'guitar_high') / 12) * 0.22 : 0);
  return [clamp(low, 0.08, 0.95), clamp(mid, 0.08, 0.95), clamp(high, 0.08, 0.95)];
}

function groupHeight(
  groups: typeof PARAM_GROUPS,
  ids: string[],
  rowHeight: number,
  labelHeight: number,
): number {
  const byId = new Map(groups.map((group) => [group.id, group]));
  return ids.reduce((total, id) => {
    const group = byId.get(id);
    if (!group) return total;
    return total + group.fields.length * rowHeight + labelHeight;
  }, 0);
}

export function panelLayout(
  windowWidth: number,
  windowHeight: number,
  context: PanelContext,
): PanelLayout {
  if (windowWidth < WIDE_BREAKPOINT) {
    return {
      columns: 1,
      dense: false,
      rowHeight: 0,
      contentWidth: Math.min(windowWidth - 32, 640),
      dangStacked: true,
      estimatedHeight: 0,
    };
  }
  const dense = windowHeight < DENSE_ROW_MAX_HEIGHT;
  const rowHeight = dense ? DENSE_ROW_HEIGHT : COMFORTABLE_ROW_HEIGHT;
  const contentWidth = panelContentWidth(windowWidth);
  const columns: 2 | 3 = panelWidthFor(windowWidth) >= 768 ? 3 : 2;
  const groups = panelGroups(context);
  const labelHeight = dense ? 20 : 24;
  const columnsSpec = columns === 3
    ? [['performance'], ['texture'], ['harmony', 'guitar']]
    : [['performance', 'texture'], ['harmony', 'guitar']];
  const controlsHeight = Math.max(
    ...columnsSpec.map((ids) => groupHeight(groups, ids, rowHeight, labelHeight)),
    0,
  );
  const form = groups.find((group) => group.id === 'form');
  const formFields = form?.fields.length ?? 0;
  const formHeight = formFields === 0
    ? 0
    : contentWidth < 640
      ? formFields * 52 + 20
      : dense
        ? 64
        : 76;
  const headerHeight = dense ? 64 : 76;
  const mixerHeight = dense ? 180 : 210;
  const estimatedHeight =
    headerHeight + PANEL_STATUS_HEIGHT + mixerHeight + controlsHeight + formHeight + 56 + 16;
  return {
    columns,
    dense,
    rowHeight,
    contentWidth,
    dangStacked: contentWidth < 640,
    estimatedHeight,
  };
}
