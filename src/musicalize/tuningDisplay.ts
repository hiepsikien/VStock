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
export const DENSE_ROW_HEIGHT = 50;
export const COMFORTABLE_ROW_HEIGHT = 60;
export const PANEL_STATUS_HEIGHT = 24;
export const GROUP_GAP = 8;
export const COLUMN_GAP = 10;
export const BODY_GAP = 14;
export const BODY_PADDING = 28;
export const FOOTER_HEIGHT = 50;
export const HEADER_DENSE = 64;
export const HEADER_COMFORTABLE = 76;
export const MIXER_DENSE = 184;
export const MIXER_COMFORTABLE = 210;
export const MIXER_DENSE_NO_GUITAR = 148;
export const MIXER_COMFORTABLE_NO_GUITAR = 176;
export const DANG_DENSE = 64;
export const DANG_COMFORTABLE = 76;
export const DANG_STACKED = 124;

export const GUITAR_VOICE_KEYS = new Set(['guitar_high', 'guitar_mid', 'guitar_bass']);
/** `register` and `color` live in the mixer strip, not in the columns. */
const MIXER_KEYS = new Set(['register', 'color']);
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

export type PanelGroup = {
  id: string;
  label: string;
  fields: ParamsFieldSchema[];
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
  detail?: string;
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

/** Groups for the columns. Voices/register/color live in the mixer. */
export function panelGroups(context: PanelContext): PanelGroup[] {
  const visible = new Set(panelFields(context).map((field) => field.key));
  return PARAM_GROUPS.map((group) => ({
    id: group.id,
    label: GROUP_LABELS[group.id] ?? group.label,
    fields: group.fields.filter((field) => {
      if (!visible.has(field.key)) return false;
      if (MIXER_KEYS.has(field.key)) return false;
      if (group.id === 'guitar' && GUITAR_VOICE_KEYS.has(field.key)) return false;
      return true;
    }),
  })).filter((group) => group.fields.length > 0);
}

function mergeGroups(groups: PanelGroup[], ids: string[], label: string): PanelGroup | null {
  const fields = ids.flatMap((id) => groups.find((group) => group.id === id)?.fields ?? []);
  if (fields.length === 0) return null;
  return { id: ids.join('+'), label, fields };
}

/**
 * Column composition. `harmony` and `guitar` share one header so a single
 * technique row does not pay for a second group label in the 3-column layout.
 */
export function panelColumns(context: PanelContext, columns: 1 | 2 | 3): PanelGroup[][] {
  const groups = panelGroups(context);
  const byId = (id: string) => groups.find((group) => group.id === id) ?? null;
  const performance = byId('performance');
  const texture = byId('texture');
  const harmonyGuitar = mergeGroups(groups, ['harmony', 'guitar'], 'Hòa âm / Guitar');
  const base = columns === 3
    ? [[performance], [texture], [harmonyGuitar]]
    : columns === 2
      ? [[performance, texture], [harmonyGuitar]]
      : [[performance, texture, harmonyGuitar]];
  return base.map((column) => column.filter((group): group is PanelGroup => Boolean(group)));
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
  const hidden = hiddenChangedKeys(params, context).length;
  if (count === 0 && hidden === 0) return 'Default';
  if (count === 0) return `${hidden} ẩn`;
  return hidden > 0 ? `${count} thay đổi · ${hidden} ẩn` : `${count} thay đổi`;
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
      detail: bpm == null ? `${number.toFixed(2)}×` : `${number.toFixed(2)}× · ${bpm} BPM`,
      ...labels,
    };
  }
  if (field.key === 'noise') {
    return {
      primary: `${number.toFixed(2)}%`,
      secondary: 'mặc định',
      detail: 'mặc định 0.10%',
      ...labels,
    };
  }
  if (GUITAR_VOICE_KEYS.has(field.key)) {
    return {
      primary: signed(number),
      secondary: `${Math.round(number)} velocity`,
      detail: `${Math.round(number)} velocity`,
      ...labels,
    };
  }
  return {
    primary: `${signed((number - 1) * 100)}%`,
    secondary: number.toFixed(2),
    detail: number.toFixed(2),
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

function groupHeight(group: PanelGroup, rowHeight: number, labelHeight: number): number {
  const fields = group.fields.length;
  return labelHeight + fields * rowHeight + fields * GROUP_GAP;
}

function columnHeight(column: PanelGroup[], rowHeight: number, labelHeight: number): number {
  if (column.length === 0) return 0;
  return (
    column.reduce((total, group) => total + groupHeight(group, rowHeight, labelHeight), 0) +
    (column.length - 1) * COLUMN_GAP
  );
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
  const columnsGroups = panelColumns(context, columns);
  const labelHeight = dense ? 20 : 24;
  const controlsHeight = Math.max(
    ...columnsGroups.map((column) => columnHeight(column, rowHeight, labelHeight)),
    0,
  );
  const form = panelGroups(context).find((group) => group.id === 'form');
  const formFields = form?.fields.length ?? 0;
  const formHeight = formFields === 0
    ? 0
    : contentWidth < 640
      ? DANG_STACKED
      : dense
        ? DANG_DENSE
        : DANG_COMFORTABLE;
  const headerHeight = dense ? HEADER_DENSE : HEADER_COMFORTABLE;
  const guitar = context.variant === 'guitar';
  const mixerHeight = guitar
    ? dense
      ? MIXER_DENSE
      : MIXER_COMFORTABLE
    : dense
      ? MIXER_DENSE_NO_GUITAR
      : MIXER_COMFORTABLE_NO_GUITAR;
  const bodyGap = formHeight > 0 ? BODY_GAP * 2 : BODY_GAP;
  const estimatedHeight =
    headerHeight +
    PANEL_STATUS_HEIGHT +
    BODY_PADDING +
    mixerHeight +
    bodyGap +
    controlsHeight +
    formHeight +
    FOOTER_HEIGHT;
  return {
    columns,
    dense,
    rowHeight,
    contentWidth,
    dangStacked: contentWidth < 640,
    estimatedHeight,
  };
}
