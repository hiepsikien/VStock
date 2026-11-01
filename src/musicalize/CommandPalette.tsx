import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions,
  type ScrollViewInstance,
  type TextInputInstance,
} from 'react-native';
import {
  DEFAULT_SYMBOLS,
  type RecapVariant,
  type SessionSummary,
} from '../api/client';
import { englishDate } from '../sonify/program';
import { chipDate, foldText, GENRES, LISTEN_SPANS, type ListenSpan } from './labels';
import { palette } from './palette';
import { type } from './type';
import type { SymbolChoice } from './SymbolColumn';

type Props = {
  visible: boolean;
  onClose: () => void;
  symbols: SymbolChoice[];
  symbol: string;
  span: ListenSpan;
  variant: RecapVariant;
  date: string | null;
  sessions: SessionSummary[];
  onSymbol: (symbol: string) => void;
  onSpan: (span: ListenSpan) => void;
  onVariant: (variant: RecapVariant) => void;
  onDate: (date: string) => void;
};

type Section = 'Mã' | 'Thể loại' | 'Khung' | 'Ngày';

type Item = {
  key: string;
  section: Section;
  label: string;
  note?: string;
  active: boolean;
  run: () => void;
  /** Vertical offset inside the list, for keeping the selection on screen. */
  top: number;
};

type KeyEvent = {
  key: string;
  metaKey?: boolean;
  ctrlKey?: boolean;
  preventDefault?: () => void;
};

type Doc = {
  addEventListener?: (name: string, fn: (event: KeyEvent) => void, capture?: boolean) => void;
  removeEventListener?: (name: string, fn: (event: KeyEvent) => void, capture?: boolean) => void;
};

const HEADER_HEIGHT = 30;
const ROW_HEIGHT = 44;

/** Current symbol first, then the desk's shortlist, then the market order. */
function rank(id: string, current: string): number {
  if (id === current) return -1;
  const at = DEFAULT_SYMBOLS.indexOf(id);
  return at >= 0 ? at : DEFAULT_SYMBOLS.length;
}

/**
 * One input for the four things that change what the room plays: the symbol,
 * the genre, the span and the session. Everything else stays on the dock.
 */
export function CommandPalette({
  visible,
  onClose,
  symbols,
  symbol,
  span,
  variant,
  date,
  sessions,
  onSymbol,
  onSpan,
  onVariant,
  onDate,
}: Props) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<TextInputInstance>(null);
  const listRef = useRef<ScrollViewInstance>(null);
  const { width } = useWindowDimensions();

  const items = useMemo(() => {
    const needle = foldText(query);
    const matches = (...parts: (string | null | undefined)[]) =>
      !needle || parts.some((part) => Boolean(part) && foldText(part as string).includes(needle));
    const out: Item[] = [];
    let last: Section | null = null;
    let top = 0;
    const add = (item: Omit<Item, 'top'>) => {
      if (item.section !== last) {
        top += HEADER_HEIGHT;
        last = item.section;
      }
      out.push({ ...item, top });
      top += ROW_HEIGHT;
    };

    symbols
      .filter((item) => matches(item.symbol, item.name))
      .slice()
      .sort((a, b) => rank(a.symbol, symbol) - rank(b.symbol, symbol))
      .slice(0, needle ? 12 : 8)
      .forEach((item) =>
        add({
          key: `s:${item.symbol}`,
          section: 'Mã',
          label: item.symbol,
          note: item.name,
          active: item.symbol === symbol,
          run: () => onSymbol(item.symbol),
        }),
      );

    GENRES.filter((item) => matches(item.label, item.id)).forEach((item) =>
      add({
        key: `g:${item.id}`,
        section: 'Thể loại',
        label: item.label,
        note: item.id,
        active: item.id === variant,
        run: () => onVariant(item.id),
      }),
    );

    LISTEN_SPANS.filter((item) => matches(item)).forEach((item) =>
      add({
        key: `r:${item}`,
        section: 'Khung',
        label: item,
        active: item === span,
        run: () => onSpan(item),
      }),
    );

    if (span === '1D' && sessions.length) {
      sessions
        .slice()
        .sort((a, b) => (a.date < b.date ? 1 : -1))
        .filter((session) =>
          matches(session.date, englishDate(session.date), chipDate(session.date).weekday),
        )
        .slice(0, needle ? 8 : 5)
        .forEach((session) =>
          add({
            key: `d:${session.date}`,
            section: 'Ngày',
            label: `${chipDate(session.date).weekday} ${englishDate(session.date)}`,
            note: session.date,
            active: session.date === date,
            run: () => onDate(session.date),
          }),
        );
    }

    return out;
  }, [date, onDate, onSpan, onSymbol, onVariant, query, sessions, span, symbol, symbols, variant]);

  const itemsRef = useRef(items);
  itemsRef.current = items;
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!visible) return;
    setQuery('');
    setSelected(0);
    const frame = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [visible]);

  useEffect(() => {
    setSelected((index) => (index < items.length ? index : 0));
  }, [items.length]);

  useEffect(() => {
    setSelected(0);
  }, [query]);

  useEffect(() => {
    if (!visible) return;
    const doc = (globalThis as { document?: Doc }).document;
    if (!doc?.addEventListener) return;
    const onKey = (event: KeyEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault?.();
        closeRef.current();
        return;
      }
      if ((event.metaKey || event.ctrlKey) && (event.key === 'k' || event.key === 'K')) {
        event.preventDefault?.();
        closeRef.current();
        return;
      }
      const list = itemsRef.current;
      if (!list.length) return;
      if (event.key === 'ArrowDown') {
        event.preventDefault?.();
        setSelected((selectedRef.current + 1) % list.length);
        return;
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault?.();
        setSelected((selectedRef.current - 1 + list.length) % list.length);
        return;
      }
      if (event.key === 'Enter') {
        event.preventDefault?.();
        list[selectedRef.current]?.run();
        closeRef.current();
      }
    };
    doc.addEventListener('keydown', onKey, true);
    return () => doc.removeEventListener?.('keydown', onKey, true);
  }, [visible]);

  useEffect(() => {
    if (!visible) return;
    const target = items[selected];
    if (!target) return;
    listRef.current?.scrollTo({ y: Math.max(0, target.top - ROW_HEIGHT * 2), animated: false });
  }, [items, selected, visible]);

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable
        style={styles.backdrop}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Đóng bảng lệnh"
      >
        <View />
      </Pressable>
      <View style={styles.anchor} pointerEvents="box-none">
        <View style={[styles.card, { width: Math.min(560, Math.max(280, width - 32)) }]} accessibilityRole="menu">
          <View style={[styles.searchRow, focused && styles.searchRowFocused]}>
            <Text style={[type.monoSmall, styles.prompt]}>⌘K</Text>
            <TextInput
              ref={inputRef}
              value={query}
              onChangeText={setQuery}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder="Mã, thể loại, khung, ngày"
              placeholderTextColor={palette.textFaint}
              autoCapitalize="none"
              autoCorrect={false}
              style={[type.sans, styles.input]}
              accessibilityLabel="Tìm trong bảng lệnh"
            />
            <Text style={[type.monoSmall, styles.count]}>{items.length}</Text>
          </View>

          <ScrollView
            ref={listRef}
            style={styles.list}
            contentContainerStyle={styles.listContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {items.length === 0 ? (
              <Text style={[type.sans, styles.empty]}>Không có kết quả</Text>
            ) : null}
            {items.map((item, index) => {
              const isSelected = index === selected;
              const previous = items[index - 1];
              const mono = item.section !== 'Thể loại';
              return (
                <React.Fragment key={item.key}>
                  {item.section !== previous?.section ? (
                    <Text style={[type.section, styles.sectionHeader]}>{item.section}</Text>
                  ) : null}
                  <Pressable
                    onPress={() => {
                      item.run();
                      onClose();
                    }}
                    style={[styles.row, isSelected && styles.rowSelected]}
                    accessibilityRole="menuitem"
                    accessibilityLabel={`${item.section}: ${item.label}`}
                    accessibilityState={{ selected: isSelected }}
                  >
                    {isSelected ? <View style={styles.rowBar} /> : null}
                    <Text
                      style={[
                        mono ? type.mono : type.sans,
                        styles.rowLabel,
                        item.active && styles.rowLabelActive,
                      ]}
                      numberOfLines={1}
                    >
                      {item.label}
                    </Text>
                    {item.note ? (
                      <Text style={[type.sans, styles.rowNote]} numberOfLines={1}>
                        {item.note}
                      </Text>
                    ) : null}
                    {item.active ? <View style={styles.rowDot} /> : null}
                  </Pressable>
                </React.Fragment>
              );
            })}
          </ScrollView>

          <View style={styles.footer}>
            <Text style={[type.sans, styles.footerText]}>↑↓ chọn · ↵ mở · esc đóng</Text>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFill,
    backgroundColor: 'rgba(8, 9, 12, 0.72)',
  },
  anchor: {
    flex: 1,
    alignItems: 'center',
    paddingTop: 72,
    paddingHorizontal: 16,
  },
  card: {
    maxHeight: '72%',
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.panel,
    overflow: 'hidden',
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    height: 52,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderBottomColor: palette.hairline,
  },
  searchRowFocused: {
    borderBottomColor: palette.hairlineStrong,
  },
  prompt: {
    color: palette.textFaint,
  },
  input: {
    flex: 1,
    color: palette.text,
    fontSize: 15,
    paddingVertical: 0,
    // The browser's default focus ring is amber on this machine, which belongs
    // to the playhead. The row's border carries focus instead.
    outlineStyle: 'solid',
    outlineWidth: 0,
    outlineColor: 'transparent',
  },
  count: {
    color: palette.textFaint,
  },
  list: {
    flexGrow: 0,
    flexShrink: 1,
  },
  listContent: {
    paddingBottom: 6,
  },
  sectionHeader: {
    color: palette.textFaint,
    paddingHorizontal: 14,
    paddingTop: 10,
    paddingBottom: 4,
    fontSize: 10,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    height: ROW_HEIGHT,
    paddingHorizontal: 14,
  },
  rowSelected: {
    backgroundColor: palette.surfaceActive,
  },
  rowBar: {
    position: 'absolute',
    left: 0,
    top: 8,
    bottom: 8,
    width: 2,
    borderRadius: 1,
    backgroundColor: palette.sound,
  },
  rowLabel: {
    color: palette.textMuted,
    fontSize: 14,
  },
  rowLabelActive: {
    color: palette.text,
  },
  rowNote: {
    flex: 1,
    color: palette.textFaint,
    fontSize: 11,
    lineHeight: 15,
    textAlign: 'right',
  },
  rowDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: palette.sound,
  },
  empty: {
    color: palette.textFaint,
    padding: 16,
  },
  footer: {
    height: 30,
    justifyContent: 'center',
    paddingHorizontal: 14,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
  },
  footerText: {
    color: palette.textFaint,
    fontSize: 11,
    lineHeight: 15,
  },
});
