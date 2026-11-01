import React, { useEffect, useState } from 'react';
import { Modal, Platform, Pressable, StyleSheet, Switch, Text, View } from 'react-native';
import { copyCurrentLink, linkSupported } from './link';
import { palette } from './palette';
import { type } from './type';

type Props = {
  visible: boolean;
  onClose: () => void;
  humanize: boolean;
  colorOn: boolean;
  onHumanize: (value: boolean) => void;
  onColor: (value: boolean) => void;
};

export function OptionsPopover({
  visible,
  onClose,
  humanize,
  colorOn,
  onHumanize,
  onColor,
}: Props) {
  const [copyState, setCopyState] = useState<'idle' | 'done' | 'fail'>('idle');
  const [canCopy] = useState(() => linkSupported());

  useEffect(() => {
    if (copyState === 'idle') return;
    const timer = setTimeout(() => setCopyState('idle'), 2000);
    return () => clearTimeout(timer);
  }, [copyState]);

  useEffect(() => {
    if (!visible) setCopyState('idle');
  }, [visible]);

  const copyLink = async () => {
    const ok = await copyCurrentLink();
    setCopyState(ok ? 'done' : 'fail');
  };

  useEffect(() => {
    if (!visible || Platform.OS !== 'web') return;
    const doc = (globalThis as {
      document?: {
        addEventListener?: (name: string, fn: (event: { key: string }) => void) => void;
        removeEventListener?: (name: string, fn: (event: { key: string }) => void) => void;
      };
    }).document;
    if (!doc?.addEventListener) return;
    const onKey = (event: { key: string }) => {
      if (event.key === 'Escape') onClose();
    };
    doc.addEventListener('keydown', onKey);
    return () => doc.removeEventListener?.('keydown', onKey);
  }, [onClose, visible]);

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable
        style={styles.backdrop}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Đóng tùy chọn nghe"
      >
        <View />
      </Pressable>
      <View style={styles.anchor} pointerEvents="box-none">
        <View style={styles.card} accessibilityRole="menu">
          <Text style={[type.section, styles.title]}>Tùy chọn nghe</Text>
          <OptionRow label="Humanize" value={humanize} onChange={onHumanize} />
          <OptionRow label="Màu" value={colorOn} onChange={onColor} />
          {canCopy ? (
            <Pressable
              onPress={() => void copyLink()}
              style={styles.linkRow}
              accessibilityRole="button"
              accessibilityLabel="Chép liên kết"
            >
              <Text style={[type.sans, styles.rowLabel]}>Chép liên kết</Text>
              <Text style={[type.section, styles.linkHint, copyState === 'done' && styles.linkHintOn]}>
                {copyState === 'done' ? 'Đã chép' : copyState === 'fail' ? 'Thử lại' : 'URL'}
              </Text>
            </Pressable>
          ) : null}
        </View>
      </View>
    </Modal>
  );
}

function OptionRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <View style={styles.row}>
      <Text style={[type.sans, styles.rowLabel]}>{label}</Text>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ false: palette.track, true: palette.sound }}
        thumbColor={palette.text}
        accessibilityLabel={label}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFill,
    backgroundColor: 'rgba(8, 9, 12, 0.55)',
  },
  anchor: {
    flex: 1,
    justifyContent: 'flex-end',
    alignItems: 'flex-end',
    padding: 16,
  },
  card: {
    width: 240,
    padding: 12,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.panel,
    gap: 4,
  },
  title: {
    color: palette.textFaint,
    marginBottom: 4,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 44,
  },
  rowLabel: {
    color: palette.text,
  },
  linkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 44,
    marginTop: 4,
    paddingTop: 4,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
  },
  linkHint: {
    color: palette.textFaint,
    fontSize: 10,
  },
  linkHintOn: {
    color: palette.sound,
  },
});
