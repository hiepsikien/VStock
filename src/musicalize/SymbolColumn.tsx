import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import type { SessionSummary } from '../api/client';
import { englishDate } from '../sonify/program';
import { chipDate, LISTEN_SPANS, type ListenSpan } from './labels';
import type { LiveListRow } from './liveRows';
import { palette } from './palette';

export type SymbolChoice = { symbol: string; name: string };

type Common = {
  onMode: (mode: 'replay' | 'live') => void;
};

type ReplayColumn = Common & {
  mode: 'replay';
  symbols: SymbolChoice[];
  filter: string;
  onFilter: (value: string) => void;
  selectedSymbol: string;
  span: ListenSpan;
  selectedDate: string | null;
  sessions: SessionSummary[];
  onSymbol: (symbol: string) => void;
  onSpan: (span: ListenSpan) => void;
  onDate: (date: string) => void;
};

type LiveColumn = Common & {
  mode: 'live';
  rows: LiveListRow[];
  selectedKey: string;
  onRow: (row: LiveListRow) => void;
};

export function SymbolColumn(props: ReplayColumn | LiveColumn) {
  return (
    <View style={styles.column}>
      <Text style={styles.brand}>Musicalize</Text>
      <View style={styles.switchRow}>
        <SwitchButton label="Nghe lại" active={props.mode === 'replay'} onPress={() => props.onMode('replay')} />
        <SwitchButton label="Đang phát" active={props.mode === 'live'} onPress={() => props.onMode('live')} />
      </View>
      {props.mode === 'replay' ? <ReplayList {...props} /> : <LiveList {...props} />}
    </View>
  );
}

function ReplayList({
  symbols,
  filter,
  onFilter,
  selectedSymbol,
  span,
  selectedDate,
  sessions,
  onSymbol,
  onSpan,
  onDate,
}: ReplayColumn) {
  const query = filter.trim().toUpperCase();
  const shown = symbols.filter((item) => {
    if (!query) return true;
    return item.symbol.includes(query) || item.name.toUpperCase().includes(query);
  });
  return (
    <>
      <View style={styles.rangeRow}>
        {LISTEN_SPANS.map((item) => {
          const active = item === span;
          return (
            <Pressable
              key={item}
              onPress={() => onSpan(item)}
              style={[styles.range, active && styles.rangeActive]}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
            >
              <Text style={[styles.rangeText, active && styles.rangeTextActive]}>{item}</Text>
            </Pressable>
          );
        })}
      </View>
      {span === '1D' && sessions.length > 0 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.sessions}>
          {sessions.map((session) => {
            const active = session.date === selectedDate;
            const chip = chipDate(session.date);
            return (
              <Pressable
                key={session.date}
                onPress={() => onDate(session.date)}
                style={[styles.session, active && styles.sessionActive]}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
              >
                <Text style={[styles.sessionWeek, active && styles.sessionTextActive]}>{chip.weekday}</Text>
                <Text style={[styles.sessionDay, active && styles.sessionTextActive]}>{chip.day}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}
      <TextInput
        value={filter}
        onChangeText={onFilter}
        placeholder="Lọc mã"
        placeholderTextColor={palette.textMuted}
        autoCapitalize="characters"
        autoCorrect={false}
        style={styles.filter}
      />
      <ScrollView style={styles.list} contentContainerStyle={styles.listContent} keyboardShouldPersistTaps="handled">
        {shown.map((item) => {
          const active = item.symbol === selectedSymbol;
          const detail =
            active && span === '1D' && selectedDate
              ? englishDate(selectedDate)
              : span;
          return (
            <Pressable
              key={item.symbol}
              onPress={() => onSymbol(item.symbol)}
              style={[styles.row, active && styles.rowActive]}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
            >
              <Text style={[styles.symbol, active && styles.symbolActive]}>{item.symbol}</Text>
              <Text style={[styles.detail, active && styles.symbolActive]}>{detail}</Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </>
  );
}

function LiveList({ rows, selectedKey, onRow }: LiveColumn) {
  return (
    <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
      {rows.map((row) => {
        const active = row.key === selectedKey;
        return (
          <Pressable
            key={row.key}
            onPress={() => onRow(row)}
            style={[styles.row, active && styles.rowActive]}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
          >
            <Text style={[styles.symbol, active && styles.symbolActive]}>{row.title}</Text>
            {row.subtitle ? (
              <Text style={[styles.detail, active && styles.symbolActive]}>{row.subtitle}</Text>
            ) : null}
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

function SwitchButton({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.switch, active && styles.switchActive]}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
    >
      <Text style={[styles.switchText, active && styles.switchTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  column: {
    flex: 1,
    backgroundColor: palette.surface,
    paddingTop: 12,
    paddingHorizontal: 12,
  },
  brand: {
    color: palette.textMuted,
    fontSize: 13,
    fontWeight: '600',
    letterSpacing: 0.4,
    marginBottom: 10,
  },
  switchRow: {
    flexDirection: 'row',
    gap: 6,
    marginBottom: 12,
  },
  switch: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: palette.background,
  },
  switchActive: {
    backgroundColor: palette.sound,
  },
  switchText: {
    color: palette.textMuted,
    fontSize: 14,
    fontWeight: '600',
  },
  switchTextActive: {
    color: palette.text,
  },
  rangeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 10,
  },
  range: {
    minWidth: 44,
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderRadius: 8,
    backgroundColor: palette.background,
  },
  rangeActive: {
    backgroundColor: palette.sound,
  },
  rangeText: {
    color: palette.textMuted,
    fontSize: 13,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  rangeTextActive: {
    color: palette.text,
  },
  sessions: {
    gap: 6,
    paddingBottom: 10,
  },
  session: {
    minWidth: 64,
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderRadius: 8,
    backgroundColor: palette.background,
  },
  sessionActive: {
    backgroundColor: palette.sound,
  },
  sessionWeek: {
    color: palette.textMuted,
    fontSize: 12,
  },
  sessionDay: {
    color: palette.text,
    fontSize: 13,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  sessionTextActive: {
    color: palette.text,
  },
  filter: {
    color: palette.text,
    backgroundColor: palette.background,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 14,
    marginBottom: 8,
  },
  list: {
    flex: 1,
  },
  listContent: {
    paddingBottom: 16,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: 8,
  },
  rowActive: {
    backgroundColor: palette.sound,
  },
  symbol: {
    color: palette.text,
    fontSize: 15,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  symbolActive: {
    color: palette.text,
  },
  detail: {
    color: palette.textMuted,
    fontSize: 13,
    fontVariant: ['tabular-nums'],
  },
});
