import React, { useState } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from 'react-native';
import {
  ENSEMBLE_ROWS,
  type PafiBreakdown,
  type PafiPiece,
  type PafiSignature,
  type RecapEnsemble,
  type RecapVariant,
} from '../api/client';
import { GENRES, pafiBandLabel } from './labels';
import { MotionPressable } from './motion';
import { palette, TOUCH_TARGET } from './palette';
import { type } from './type';

type Props = {
  visible: boolean;
  onClose: () => void;
  pafi: PafiBreakdown | null;
  variant: RecapVariant;
  ensemble: RecapEnsemble;
  signatures: PafiSignature[];
  /** One row per genre, all at its default ensemble. */
  genrePieces: PafiPiece[] | null;
  /** One row per ensemble of `variant`. */
  ensemblePieces: PafiPiece[] | null;
  loading?: boolean;
  onVariant: (variant: RecapVariant) => void;
  onEnsemble: (ensemble: RecapEnsemble) => void;
};

const BREAKDOWN: {
  key: keyof PafiBreakdown;
  label: string;
  hint: string;
}[] = [
  {
    key: 'shape',
    label: 'Hình dạng',
    hint: 'Đường giá và đường cao độ có cùng hướng không.',
  },
  {
    key: 'motion',
    label: 'Chuyển động',
    hint: 'Giá đi xa thì nốt có đi xa hơn không.',
  },
  {
    key: 'structure',
    label: 'Cấu trúc',
    hint: 'Đỉnh, đáy và hướng của cả câu có rơi đúng chỗ không.',
  },
  {
    key: 'resolution',
    label: 'Độ phân giải',
    hint: 'Biến động nhỏ có nghe ra, và texture có chạy khi giá đứng không.',
  },
  {
    key: 'volume',
    label: 'Khối lượng',
    hint: 'Volume lớn có nghe to và rõ hơn không.',
  },
  {
    key: 'coverage',
    label: 'Độ phủ',
    hint: 'Phần thời gian đường giá thực sự phát, tính theo mức biến động giá.',
  },
];

function scoreOf(pieces: PafiPiece[] | null, variant: RecapVariant, ensemble: string): number | null {
  const row = pieces?.find((item) => item.variant === variant && item.ensemble === ensemble);
  return row?.pafi?.score ?? null;
}

function signatureOf(
  signatures: PafiSignature[],
  variant: RecapVariant,
  ensemble: string,
): PafiSignature | null {
  return (
    signatures.find((item) => item.variant === variant && item.ensemble === ensemble) ??
    signatures.find((item) => item.variant === variant && item.ensemble === 'classic') ??
    null
  );
}

export function PafiSheet({
  visible,
  onClose,
  pafi,
  variant,
  ensemble,
  signatures,
  genrePieces,
  ensemblePieces,
  loading = false,
  onVariant,
  onEnsemble,
}: Props) {
  const { width, height } = useWindowDimensions();
  const cardWidth = Math.min(420, Math.max(280, width - 32));
  const activeSignature = signatureOf(signatures, variant, ensemble);
  const genreComparable = genrePieces != null;
  const ensembleComparable = ensemblePieces != null;
  const [openHint, setOpenHint] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(false);

  const toggleHint = (key: string) => {
    setOpenHint((current) => (current === key ? null : key));
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable
        style={styles.backdrop}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Đóng độ trung thực dữ liệu"
      >
        <View />
      </Pressable>
      <View style={styles.anchor} pointerEvents="box-none">
        <View
          style={[styles.card, { width: cardWidth, maxHeight: Math.min(height - 64, 640) }]}
          accessibilityRole="menu"
        >
          <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
            <View style={styles.header}>
              <Text style={[type.section, styles.kicker]}>Độ trung thực dữ liệu</Text>
              <Text style={[type.mono, styles.score]}>
                {pafi ? Math.round(pafi.score) : '—'}
              </Text>
              <Text style={[type.sans, styles.band]}>
                {pafiBandLabel(pafi?.band)}
                {pafi?.confidence === 'low' ? ' · ít mẫu' : ''}
              </Text>
              <MotionPressable
                onPress={() => setShowHelp((value) => !value)}
                hitSlop={10}
                style={[styles.helpButton, showHelp && styles.helpButtonOn]}
                accessibilityRole="button"
                accessibilityState={{ expanded: showHelp }}
                accessibilityLabel={showHelp ? 'Ẩn cách đọc điểm' : 'Xem cách đọc điểm'}
              >
                <Text style={[type.monoSmall, styles.helpGlyph]}>?</Text>
              </MotionPressable>
            </View>

            {showHelp ? (
              <Text style={[type.sans, styles.helpText]} accessibilityLiveRegion="polite">
                PA phản ánh mức nghe rõ của giá và volume, không phải độ hay của bản nhạc.
              </Text>
            ) : null}

            {pafi ? (
              <View style={styles.breakdown}>
                {BREAKDOWN.map((row) => {
                  const raw = pafi[row.key];
                  const value = typeof raw === 'number' ? raw : null;
                  const open = openHint === row.key;
                  return (
                    <View key={row.key}>
                      <MotionPressable
                        onPress={() => toggleHint(row.key)}
                        style={styles.meterRow}
                        accessibilityRole="button"
                        accessibilityState={{ expanded: open }}
                        accessibilityLabel={`${row.label} ${value == null ? 'chưa có số' : value.toFixed(2)}. ${open ? 'Ẩn' : 'Xem'} giải thích`}
                      >
                        <View style={styles.meterLabelCell}>
                          <Text style={[type.sans, styles.meterLabel]}>{row.label}</Text>
                          <Text style={[type.monoSmall, styles.hintGlyph, open && styles.hintGlyphOn]}>
                            ?
                          </Text>
                        </View>
                        <View style={styles.meterTrack}>
                          <View
                            style={[
                              styles.meterFill,
                              { width: Math.round(112 * Math.max(0, Math.min(1, value ?? 0))) },
                            ]}
                          />
                        </View>
                        <Text style={[type.monoSmall, styles.meterValue]}>
                          {value == null ? '—' : value.toFixed(2)}
                        </Text>
                      </MotionPressable>
                      {open ? (
                        <Text
                          style={[type.sans, styles.hintText]}
                          accessibilityLiveRegion="polite"
                        >
                          {row.hint}
                        </Text>
                      ) : null}
                    </View>
                  );
                })}
              </View>
            ) : (
              <Text style={[type.sans, styles.empty]}>
                Phiên này chưa đủ chuyển động giá để đo. Không hiển thị 0 điểm.
              </Text>
            )}

            <View style={styles.rule} />
            <View style={styles.tableHeader}>
              <Text style={[type.section, styles.tableTitle]}>Thể loại</Text>
              <Text style={[type.monoSmall, styles.tableHint]}>
                {loading ? 'đang soạn…' : activeSignature ? `chuẩn ${Math.round(activeSignature.score)}` : 'chuẩn —'}
              </Text>
            </View>
            {GENRES.map((item) => {
              const active = item.id === variant;
              const score = scoreOf(genrePieces, item.id, 'classic');
              const signature = signatureOf(signatures, item.id, 'classic');
              return (
                <MotionPressable
                  key={item.id}
                  onPress={() => onVariant(item.id)}
                  style={[styles.row, active && styles.rowActive]}
                  accessibilityRole="button"
                  accessibilityLabel={`${item.label}${score == null ? '' : `, độ rõ ${Math.round(score)}`}`}
                  accessibilityState={{ selected: active }}
                >
                  <View style={styles.labelCell}>
                    <Text style={[type.sans, styles.rowLabel, active && styles.rowLabelActive]}>
                      {item.label}
                    </Text>
                    {active ? <Text style={[type.monoSmall, styles.badge]}>đang nghe</Text> : null}
                  </View>
                  <Text style={[type.monoSmall, styles.range]}>
                    {signature ? `${Math.round(signature.p25)}–${Math.round(signature.p75)}` : '—'}
                  </Text>
                  <Text style={[type.mono, styles.rowScore, !genreComparable && styles.rowScoreMuted]}>
                    {score == null ? '—' : Math.round(score)}
                  </Text>
                </MotionPressable>
              );
            })}

            <View style={styles.rule} />
            <View style={styles.tableHeader}>
              <Text style={[type.section, styles.tableTitle]}>Dàn nhạc</Text>
              <Text style={[type.monoSmall, styles.tableHint]}>
                {loading ? 'đang soạn…' : 'cùng thước đo'}
              </Text>
            </View>
            {ENSEMBLE_ROWS[variant].map((item) => {
              const active = item.id === ensemble;
              const score = scoreOf(ensemblePieces, variant, item.id);
              const signature = signatureOf(signatures, variant, item.id);
              return (
                <MotionPressable
                  key={item.id}
                  onPress={() => onEnsemble(item.id)}
                  style={[styles.row, active && styles.rowActive]}
                  accessibilityRole="button"
                  accessibilityLabel={`${item.label}${score == null ? '' : `, độ rõ ${Math.round(score)}`}`}
                  accessibilityState={{ selected: active }}
                >
                  <View style={styles.labelCell}>
                    <Text style={[type.sans, styles.rowLabel, active && styles.rowLabelActive]}>
                      {item.label}
                    </Text>
                    {active ? <Text style={[type.monoSmall, styles.badge]}>đang nghe</Text> : null}
                  </View>
                  <Text style={[type.monoSmall, styles.range]}>
                    {signature ? `${Math.round(signature.p25)}–${Math.round(signature.p75)}` : '—'}
                  </Text>
                  <Text style={[type.mono, styles.rowScore, !ensembleComparable && styles.rowScoreMuted]}>
                    {score == null ? '—' : Math.round(score)}
                  </Text>
                </MotionPressable>
              );
            })}

            <Text style={[type.monoSmall, styles.note]}>
              PA không đo độ hay của bản nhạc. Đổi âm sắc không nên đổi độ trung thực dữ liệu.
            </Text>
          </ScrollView>
          <MotionPressable
            onPress={onClose}
            style={styles.close}
            accessibilityRole="button"
            accessibilityLabel="Đóng"
          >
            <Text style={[type.sans, styles.closeText]}>Đóng</Text>
          </MotionPressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFill,
    backgroundColor: 'rgba(8, 9, 12, 0.62)',
  },
  anchor: {
    flex: 1,
    justifyContent: 'flex-end',
    alignItems: 'center',
    padding: 16,
  },
  card: {
    borderRadius: 8,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.panel,
  },
  scroll: {
    padding: 16,
    gap: 4,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 8,
  },
  kicker: {
    color: palette.textFaint,
    flex: 1,
  },
  score: {
    color: palette.text,
    fontSize: 28,
    lineHeight: 32,
    fontVariant: ['tabular-nums'],
  },
  band: {
    color: palette.textMuted,
    fontSize: 12,
  },
  helpButton: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1,
    borderColor: palette.hairline,
    alignItems: 'center',
    justifyContent: 'center',
  },
  helpButtonOn: {
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surface,
  },
  helpGlyph: {
    color: palette.textMuted,
  },
  helpText: {
    color: palette.textMuted,
    fontSize: 12,
    lineHeight: 18,
    marginBottom: 10,
  },
  breakdown: {
    gap: 2,
  },
  meterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    minHeight: 30,
    borderRadius: 4,
  },
  meterLabelCell: {
    width: 108,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  meterLabel: {
    color: palette.textMuted,
    fontSize: 12,
    flexShrink: 1,
  },
  hintGlyph: {
    color: palette.textFaint,
    fontSize: 10,
  },
  hintGlyphOn: {
    color: palette.sound,
  },
  hintText: {
    color: palette.textMuted,
    fontSize: 11,
    lineHeight: 16,
    marginLeft: 4,
    marginBottom: 6,
    paddingLeft: 8,
    borderLeftWidth: 1,
    borderLeftColor: palette.hairline,
  },
  meterTrack: {
    width: 112,
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
    backgroundColor: palette.track,
  },
  meterFill: {
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.data,
  },
  meterValue: {
    color: palette.textFaint,
    minWidth: 32,
    textAlign: 'right',
    fontVariant: ['tabular-nums'],
  },
  empty: {
    color: palette.textMuted,
    fontSize: 12,
    lineHeight: 18,
  },
  rule: {
    height: 1,
    backgroundColor: palette.hairline,
    marginVertical: 10,
  },
  tableHeader: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginBottom: 2,
  },
  tableTitle: {
    color: palette.textFaint,
  },
  tableHint: {
    color: palette.textFaint,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: TOUCH_TARGET,
    paddingHorizontal: 4,
    borderRadius: 4,
    gap: 8,
  },
  rowActive: {
    backgroundColor: palette.surface,
  },
  labelCell: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  rowLabel: {
    color: palette.textMuted,
    fontSize: 13,
  },
  rowLabelActive: {
    color: palette.text,
  },
  badge: {
    color: palette.sound,
    fontSize: 9,
  },
  range: {
    color: palette.textFaint,
    minWidth: 44,
    textAlign: 'right',
    fontVariant: ['tabular-nums'],
  },
  rowScore: {
    color: palette.text,
    minWidth: 28,
    textAlign: 'right',
    fontVariant: ['tabular-nums'],
  },
  rowScoreMuted: {
    color: palette.textFaint,
  },
  note: {
    color: palette.textFaint,
    fontSize: 10,
    lineHeight: 14,
    marginTop: 10,
  },
  close: {
    height: TOUCH_TARGET,
    alignItems: 'center',
    justifyContent: 'center',
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
  },
  closeText: {
    color: palette.textMuted,
  },
});
