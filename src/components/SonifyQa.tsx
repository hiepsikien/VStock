import React, { useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  fetchRecapScore,
  type RecapEnsemble,
  type SonifyQaReport,
} from '../api/client';
import { colors, spacing, typography } from '../theme';

type Props = {
  symbol: string;
  day: string;
  ensemble: RecapEnsemble;
  bars: number;
};

function isAbort(error: unknown): boolean {
  return error instanceof Error && (error.name === 'AbortError' || /aborted/i.test(error.message));
}

export function SonifyQa({ symbol, day, ensemble, bars }: Props) {
  const insets = useSafeAreaInsets();
  const [open, setOpen] = useState(false);
  const [report, setReport] = useState<SonifyQaReport | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setReport(null);
    setFailed(false);
    void fetchRecapScore(symbol, day, ensemble, controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) setReport(next);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && !isAbort(error)) setFailed(true);
      });
    return () => controller.abort();
  }, [symbol, day, ensemble, bars]);

  const status = report?.chip.replace(/^QA\s*·\s*/, '') ?? '';
  const statusColor = !report ? colors.textTertiary : report.gatesPass ? colors.positive : colors.negative;

  return (
    <>
      <Pressable
        onPress={() => {
          void Haptics.selectionAsync();
          setOpen(true);
        }}
        style={styles.chip}
        accessibilityRole="button"
        accessibilityLabel="Máy đo, xem chi tiết"
      >
        <Text style={styles.chipMark}>QA</Text>
        {status ? <Text style={[styles.chipStatus, { color: statusColor }]}>{status}</Text> : null}
      </Pressable>
      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <View style={styles.container}>
          <Pressable style={styles.backdrop} onPress={() => setOpen(false)} accessibilityLabel="Đóng" />
          <View style={[styles.sheet, { paddingBottom: Math.max(insets.bottom, spacing.lg) }]}>
            <View style={styles.header}>
              <View style={styles.headerCopy}>
                <Text style={styles.title}>Máy đo</Text>
                <Text style={styles.subtitle} numberOfLines={1}>
                  {symbol.toUpperCase()} · {day}
                </Text>
              </View>
              <Pressable
                onPress={() => {
                  void Haptics.selectionAsync();
                  setOpen(false);
                }}
                accessibilityRole="button"
                accessibilityLabel="Đóng"
              >
                <Text style={styles.close}>Đóng</Text>
              </Pressable>
            </View>
            <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={false}>
              {report ? (
                <>
                  {report.blocks.map((block) => (
                    <View key={block.title} style={styles.block}>
                      <Text style={styles.blockTitle}>{block.title}</Text>
                      {block.lines.map((line) => (
                        <View key={line.label} style={styles.line}>
                          <Text style={styles.lineLabel}>{line.label}</Text>
                          <Text style={styles.lineValue}>{line.value}</Text>
                        </View>
                      ))}
                    </View>
                  ))}
                  {report.notes.map((note) => (
                    <Text key={note} style={styles.note}>
                      {note}
                    </Text>
                  ))}
                </>
              ) : (
                <Text style={styles.note}>
                  {failed ? 'Không chấm được bản này.' : 'Đang chấm…'}
                </Text>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  chip: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: spacing.sm,
    paddingVertical: 2,
  },
  chipMark: {
    ...typography.caption,
    color: colors.textTertiary,
    fontWeight: '600',
    letterSpacing: 0.4,
  },
  chipStatus: {
    ...typography.caption,
    fontVariant: ['tabular-nums'],
  },
  container: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  backdrop: {
    ...StyleSheet.absoluteFill,
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    maxHeight: '78%',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
    gap: spacing.md,
  },
  headerCopy: {
    flex: 1,
  },
  title: {
    ...typography.title,
    color: colors.text,
    fontSize: 20,
  },
  subtitle: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  close: {
    color: colors.accent,
    fontSize: 16,
    fontWeight: '600',
  },
  body: {
    gap: spacing.md,
    paddingBottom: spacing.md,
  },
  block: {
    gap: 6,
  },
  blockTitle: {
    ...typography.caption,
    color: colors.textTertiary,
    fontWeight: '600',
    letterSpacing: 0.3,
  },
  line: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    gap: spacing.md,
  },
  lineLabel: {
    ...typography.body,
    color: colors.textSecondary,
    flex: 1,
  },
  lineValue: {
    ...typography.body,
    color: colors.text,
    fontVariant: ['tabular-nums'],
  },
  note: {
    ...typography.caption,
    color: colors.textSecondary,
  },
});
