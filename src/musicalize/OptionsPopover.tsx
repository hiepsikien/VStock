import React, { useEffect } from 'react';
import { Modal, Platform, Pressable, StyleSheet, Switch, Text, View } from 'react-native';
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
});
