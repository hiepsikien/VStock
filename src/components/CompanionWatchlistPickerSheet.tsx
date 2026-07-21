import React, { useState } from 'react';
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import * as Haptics from 'expo-haptics';
import type { Watchlist } from '../storage/watchlist';
import { colors, spacing } from '../theme';

type Props = {
  visible: boolean;
  symbol: string;
  lists: Watchlist[];
  activeId: string;
  onClose: () => void;
  onSelectList: (watchlistId: string) => void;
  onCreateList: (name: string) => void;
};

export function CompanionWatchlistPickerSheet({
  visible,
  symbol,
  lists,
  activeId,
  onClose,
  onSelectList,
  onCreateList,
}: Props) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');

  const sym = symbol.toUpperCase();

  const close = () => {
    setCreating(false);
    setNewName('');
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={close}>
      <Pressable style={styles.backdrop} onPress={close}>
        <Pressable style={styles.sheet} onPress={() => {}}>
          <Text style={styles.title}>Thêm {sym} vào danh sách nào?</Text>

          {lists.map((list) => {
            const has = list.symbols.includes(sym);
            return (
              <Pressable
                key={list.id}
                disabled={has}
                onPress={() => {
                  void Haptics.selectionAsync();
                  onSelectList(list.id);
                  close();
                }}
                style={[
                  styles.row,
                  list.id === activeId && styles.rowActive,
                  has && styles.rowDisabled,
                ]}
              >
                <Text style={styles.rowName}>
                  {list.name}
                  {list.id === activeId ? ' · đang mở' : ''}
                </Text>
                <Text style={styles.rowMeta}>
                  {has ? 'Đã có mã này' : `${list.symbols.length} mã`}
                </Text>
              </Pressable>
            );
          })}

          {creating ? (
            <View style={styles.createBox}>
              <TextInput
                value={newName}
                onChangeText={setNewName}
                placeholder="Tên danh sách mới"
                placeholderTextColor={colors.textTertiary}
                style={styles.input}
                autoFocus
              />
              <Pressable
                onPress={() => {
                  const name = newName.trim() || 'Danh sách mới';
                  void Haptics.selectionAsync();
                  onCreateList(name);
                  close();
                }}
                style={styles.createBtn}
              >
                <Text style={styles.createBtnText}>Tạo & thêm {sym}</Text>
              </Pressable>
            </View>
          ) : (
            <Pressable
              onPress={() => {
                void Haptics.selectionAsync();
                setCreating(true);
              }}
              style={styles.newRow}
            >
              <Text style={styles.newRowText}>+ Tạo danh sách mới</Text>
            </Pressable>
          )}

          <Pressable onPress={close} style={styles.cancel}>
            <Text style={styles.cancelText}>Huỷ</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xl,
    gap: 8,
  },
  title: {
    fontSize: 17,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 4,
  },
  row: {
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 12,
    backgroundColor: colors.surfaceElevated,
  },
  rowActive: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.positive,
  },
  rowDisabled: { opacity: 0.45 },
  rowName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  rowMeta: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  newRow: {
    paddingVertical: 12,
    alignItems: 'center',
  },
  newRowText: {
    color: colors.accent,
    fontSize: 16,
    fontWeight: '600',
  },
  createBox: { gap: 8, marginTop: 4 },
  input: {
    borderRadius: 12,
    backgroundColor: colors.background,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: colors.text,
    fontSize: 16,
  },
  createBtn: {
    backgroundColor: colors.accent,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
  },
  createBtnText: {
    color: colors.text,
    fontWeight: '700',
    fontSize: 15,
  },
  cancel: {
    marginTop: 8,
    alignItems: 'center',
    paddingVertical: 8,
  },
  cancelText: {
    color: colors.textSecondary,
    fontSize: 16,
  },
});
