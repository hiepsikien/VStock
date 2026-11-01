import React, { useEffect, useRef } from 'react';
import {
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions,
  type TextInputInstance,
} from 'react-native';
import type { SessionSummary } from '../api/client';
import { Sparkline } from '../components/Sparkline';
import { englishDate } from '../sonify/program';
import { chipDate, formatDelta, LISTEN_SPANS, type ListenSpan } from './labels';
import type { LiveListRow } from './liveRows';
import { MotionPressable, RiseRule } from './motion';
import { palette, WIDE_BREAKPOINT } from './palette';
import { type } from './type';
import type { Quote } from './useQuotes';

export type SymbolChoice = { symbol: string; name: string; exchange?: string };

type ReplayColumn = {
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
  quotes?: Record<string, Quote> | null;
  focusSignal?: number;
};

type LiveColumn = {
  mode: 'live';
  rows: LiveListRow[];
  selectedKey: string;
  onRow: (row: LiveListRow) => void;
};

export function SymbolColumn(props: ReplayColumn | LiveColumn) {
  const { width } = useWindowDimensions();
  // Below the breakpoint the chooser becomes a single horizontal rail: the
  // chart has to be visible on the first screen, not after a 460px list.
  const compact = width < WIDE_BREAKPOINT;

  return (
    <View style={[styles.column, compact && styles.columnCompact]}>
      {compact ? null : (
        <Text style={[type.section, styles.eyebrow]}>
          {props.mode === 'replay' ? 'Thị trường' : 'Đài'}
        </Text>
      )}
      {props.mode === 'replay' ? (
        <ReplayList {...props} compact={compact} />
      ) : (
        <LiveList {...props} compact={compact} />
      )}
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
  quotes,
  focusSignal = 0,
  compact,
}: ReplayColumn & { compact: boolean }) {
  const inputRef = useRef<TextInputInstance>(null);
  const query = filter.trim().toUpperCase();
  const shown = symbols.filter((item) => {
    if (!query) return true;
    return item.symbol.includes(query) || item.name.toUpperCase().includes(query);
  });
  const exchange = shown.length > 0 && shown.every((item) => item.exchange === shown[0].exchange)
    ? shown[0].exchange
    : null;

  useEffect(() => {
    if (focusSignal > 0) inputRef.current?.focus();
  }, [focusSignal]);

  if (compact) {
    return (
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.rail}
        contentContainerStyle={styles.railContent}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.railFilterShell}>
          <TextInput
            ref={inputRef}
            value={filter}
            onChangeText={onFilter}
            placeholder="Lọc mã"
            placeholderTextColor={palette.textFaint}
            autoCapitalize="characters"
            autoCorrect={false}
            style={[type.sans, styles.railFilter]}
            accessibilityLabel="Lọc mã"
          />
        </View>

        {LISTEN_SPANS.map((item) => {
          const active = item === span;
          return (
            <MotionPressable
              key={item}
              onPress={() => onSpan(item)}
              style={[styles.railChip, active && styles.railChipActive]}
              accessibilityRole="button"
              accessibilityLabel={`Khung ${item}`}
              accessibilityState={{ selected: active }}
            >
              <Text style={[type.monoSmall, styles.railChipText, active && styles.railChipTextActive]}>
                {item}
              </Text>
            </MotionPressable>
          );
        })}

        {span === '1D' && sessions.length > 0 ? (
          <>
            <View style={styles.railDivider} />
            {sessions.map((session) => {
              const active = session.date === selectedDate;
              const chip = chipDate(session.date);
              return (
                <MotionPressable
                  key={session.date}
                  onPress={() => onDate(session.date)}
                  style={[styles.railChip, active && styles.railChipActive]}
                  accessibilityRole="button"
                  accessibilityLabel={`Phiên ${chip.day}`}
                  accessibilityState={{ selected: active }}
                >
                  <Text style={[type.monoSmall, styles.railChipText, active && styles.railChipTextActive]}>
                    {chip.day}
                  </Text>
                </MotionPressable>
              );
            })}
          </>
        ) : null}

        <View style={styles.railDivider} />

        {shown.map((item) => {
          const active = item.symbol === selectedSymbol;
          const quote = quotes?.[item.symbol] ?? null;
          const delta = quote ? formatDelta(quote.changePercent) : null;
          return (
            <MotionPressable
              key={item.symbol}
              onPress={() => onSymbol(item.symbol)}
              style={[styles.railSymbol, active && styles.railSymbolActive]}
              accessibilityRole="button"
              accessibilityLabel={`${item.symbol}${
                delta ? `, ${delta.positive ? 'tăng' : 'giảm'} ${delta.text}` : ''
              }`}
              accessibilityState={{ selected: active }}
            >
              <Text style={[type.monoSmall, styles.railSymbolText, active && styles.railSymbolTextActive]}>
                {item.symbol}
              </Text>
              {delta ? (
                <Text
                  style={[
                    type.monoSmall,
                    styles.railDelta,
                    delta.positive ? styles.deltaUp : styles.deltaDown,
                  ]}
                >
                  {delta.glyph}
                  {delta.text}
                </Text>
              ) : null}
              {active ? <RiseRule style={styles.railRule} /> : null}
            </MotionPressable>
          );
        })}
      </ScrollView>
    );
  }

  return (
    <>
      <View style={styles.filterShell}>
        <TextInput
          ref={inputRef}
          value={filter}
          onChangeText={onFilter}
          placeholder="Lọc mã"
          placeholderTextColor={palette.textFaint}
          autoCapitalize="characters"
          autoCorrect={false}
          style={[type.sans, styles.filter]}
          accessibilityLabel="Lọc mã"
        />
        {filter.length === 0 ? (
          <Text style={[type.monoSmall, styles.filterHint]}>
            {Platform.OS === 'web' ? '/' : ''}
          </Text>
        ) : null}
      </View>

      <View style={styles.rangeRow}>
        {LISTEN_SPANS.map((item) => {
          const active = item === span;
          return (
            <MotionPressable
              key={item}
              onPress={() => onSpan(item)}
              hitSlop={8}
              style={styles.range}
              accessibilityRole="button"
              accessibilityLabel={`Khung ${item}`}
              accessibilityState={{ selected: active }}
            >
              <Text style={[type.mono, styles.rangeText, active && styles.rangeTextActive]}>{item}</Text>
              {active ? <RiseRule style={styles.rangeRule} /> : <View style={styles.rangeRule} />}
            </MotionPressable>
          );
        })}
      </View>

      {span === '1D' && sessions.length > 0 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.sessionScroll}
          contentContainerStyle={styles.sessions}
        >
          {sessions.map((session) => {
            const active = session.date === selectedDate;
            const chip = chipDate(session.date);
            return (
              <MotionPressable
                key={session.date}
                onPress={() => onDate(session.date)}
                style={[styles.session, active && styles.sessionActive]}
                accessibilityRole="button"
                accessibilityLabel={`Phiên ${chip.day}`}
                accessibilityState={{ selected: active }}
              >
                <Text style={[type.monoSmall, styles.sessionWeek, active && styles.sessionTextActive]}>
                  {chip.weekday}
                </Text>
                <Text style={[type.mono, styles.sessionDay, active && styles.sessionTextActive]}>
                  {chip.day}
                </Text>
              </MotionPressable>
            );
          })}
        </ScrollView>
      ) : null}

      <ScrollView
        style={styles.list}
        contentContainerStyle={styles.listContent}
        keyboardShouldPersistTaps="handled"
      >
        {shown.map((item) => {
          const active = item.symbol === selectedSymbol;
          const quote = quotes?.[item.symbol] ?? null;
          const delta = quote ? formatDelta(quote.changePercent) : null;
          const activeDate = active && span === '1D' && selectedDate ? englishDate(selectedDate) : null;
          return (
            <MotionPressable
              key={item.symbol}
              onPress={() => onSymbol(item.symbol)}
              style={[styles.row, active && styles.rowActive]}
              accessibilityRole="button"
              accessibilityLabel={`${item.symbol}, ${item.name}${
                delta
                  ? delta.glyph === '·'
                    ? `, ${delta.text}`
                    : `, ${delta.positive ? 'tăng' : 'giảm'} ${delta.text}`
                  : ''
              }`}
              accessibilityState={{ selected: active }}
            >
              <View style={[styles.rowBar, active && styles.rowBarOn]} />
              <View style={styles.rowMain}>
                <Text style={[type.mono, styles.symbol]} numberOfLines={1}>
                  {item.symbol}
                </Text>
                <Text style={[type.sans, styles.name]} numberOfLines={1}>
                  {activeDate ?? item.name}
                </Text>
              </View>
              {quote && quote.sparkline.length > 1 ? (
                <Sparkline
                  data={quote.sparkline}
                  width={44}
                  height={18}
                  strokeWidth={1.25}
                  strokeColor={palette.data}
                />
              ) : null}
              {delta ? (
                <Text
                  style={[
                    type.monoSmall,
                    styles.delta,
                    delta.positive ? styles.deltaUp : styles.deltaDown,
                  ]}
                >
                  {delta.glyph}
                  {delta.text}
                </Text>
              ) : null}
            </MotionPressable>
          );
        })}
      </ScrollView>

      <View style={styles.footer}>
        <Text style={[type.sans, styles.footerText]}>
          {Platform.OS === 'web' ? 'Space phát/dừng · ←→ tua' : 'Chọn một mã để nghe'}
        </Text>
        <Text style={[type.monoSmall, styles.footerText]}>
          {shown.length}
          {exchange ? ` · ${exchange}` : ''}
        </Text>
      </View>
    </>
  );
}

function LiveList({
  rows,
  selectedKey,
  onRow,
  compact,
}: LiveColumn & { compact: boolean }) {
  if (compact) {
    return (
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.rail}
        contentContainerStyle={styles.railContent}
      >
        {rows.map((row) => {
          const active = row.key === selectedKey;
          return (
            <MotionPressable
              key={row.key}
              onPress={() => onRow(row)}
              style={[styles.railSymbol, active && styles.railSymbolActive]}
              accessibilityRole="button"
              accessibilityLabel={row.title}
              accessibilityState={{ selected: active }}
            >
              <Text
                style={[type.monoSmall, styles.railSymbolText, active && styles.railSymbolTextActive]}
                numberOfLines={1}
              >
                {row.title}
              </Text>
              {row.subtitle ? (
                <Text style={[type.sans, styles.railName]} numberOfLines={1}>
                  {row.subtitle}
                </Text>
              ) : null}
              {active ? <RiseRule style={styles.railRule} /> : null}
            </MotionPressable>
          );
        })}
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
      {rows.map((row) => {
        const active = row.key === selectedKey;
        return (
          <MotionPressable
            key={row.key}
            onPress={() => onRow(row)}
            style={[styles.row, active && styles.rowActive]}
            accessibilityRole="button"
            accessibilityLabel={row.title}
            accessibilityState={{ selected: active }}
          >
            <View style={[styles.rowBar, active && styles.rowBarOn]} />
            <View style={styles.rowMain}>
              <Text style={[type.mono, styles.symbol]} numberOfLines={1}>
                {row.title}
              </Text>
              {row.subtitle ? (
                <Text style={[type.sans, styles.name]} numberOfLines={1}>
                  {row.subtitle}
                </Text>
              ) : null}
            </View>
            {active ? <View style={styles.onAir} /> : null}
          </MotionPressable>
        );
      })}
    </ScrollView>
  );
}

const SESSION_CHIP_HEIGHT = 8 + 16 + 18 + 8 + 4;

const styles = StyleSheet.create({
  column: {
    flex: 1,
    backgroundColor: palette.panel,
    paddingTop: 12,
    paddingHorizontal: 12,
  },
  columnCompact: {
    paddingTop: 0,
    paddingHorizontal: 0,
    justifyContent: 'flex-start',
  },
  eyebrow: {
    color: palette.textFaint,
    marginBottom: 8,
  },
  filterShell: {
    flexDirection: 'row',
    alignItems: 'center',
    height: 32,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.background,
    paddingHorizontal: 8,
    marginBottom: 10,
  },
  filter: {
    flex: 1,
    color: palette.text,
    fontSize: 13,
    paddingVertical: 0,
  },
  filterHint: {
    color: palette.textFaint,
  },
  rangeRow: {
    flexDirection: 'row',
    marginBottom: 10,
  },
  range: {
    flex: 1,
    alignItems: 'center',
    paddingTop: 4,
  },
  rangeText: {
    color: palette.textFaint,
    fontSize: 12,
  },
  rangeTextActive: {
    color: palette.text,
  },
  rangeRule: {
    alignSelf: 'stretch',
    height: 2,
    marginTop: 6,
    backgroundColor: 'transparent',
  },
  sessionScroll: {
    height: SESSION_CHIP_HEIGHT,
    flexGrow: 0,
    flexShrink: 0,
    marginBottom: 10,
  },
  sessions: {
    alignItems: 'flex-start',
    gap: 6,
  },
  session: {
    height: SESSION_CHIP_HEIGHT,
    alignSelf: 'flex-start',
    minWidth: 56,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  sessionActive: {
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surface,
  },
  sessionWeek: {
    color: palette.textFaint,
    lineHeight: 16,
    includeFontPadding: false,
  },
  sessionDay: {
    color: palette.textMuted,
    lineHeight: 18,
    includeFontPadding: false,
    fontSize: 12,
  },
  sessionTextActive: {
    color: palette.text,
  },
  list: {
    flex: 1,
  },
  listContent: {
    paddingBottom: 8,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 44,
    paddingVertical: 6,
    paddingLeft: 10,
    paddingRight: 8,
    borderRadius: 4,
    gap: 8,
  },
  rowActive: {
    backgroundColor: palette.surfaceActive,
  },
  rowBar: {
    position: 'absolute',
    left: 0,
    top: 8,
    bottom: 8,
    width: 2,
    borderRadius: 1,
    backgroundColor: 'transparent',
  },
  rowBarOn: {
    backgroundColor: palette.sound,
  },
  rowMain: {
    flex: 1,
    minWidth: 0,
  },
  symbol: {
    color: palette.text,
    fontSize: 14,
    fontWeight: '600',
  },
  name: {
    color: palette.textFaint,
    fontSize: 11,
    lineHeight: 15,
  },
  delta: {
    color: palette.text,
  },
  deltaUp: {
    color: palette.text,
  },
  deltaDown: {
    color: palette.textMuted,
  },
  onAir: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: palette.sound,
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 28,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
  },
  footerText: {
    color: palette.textFaint,
    fontSize: 10,
    lineHeight: 14,
  },
  rail: {
    flexGrow: 0,
    height: 56,
  },
  railContent: {
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 12,
  },
  railFilterShell: {
    width: 128,
    height: 32,
    justifyContent: 'center',
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.background,
    paddingHorizontal: 8,
  },
  railFilter: {
    color: palette.text,
    fontSize: 13,
    paddingVertical: 0,
  },
  railChip: {
    height: 32,
    minWidth: 44,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 10,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.background,
  },
  railChipActive: {
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surface,
  },
  railChipText: {
    color: palette.textFaint,
  },
  railChipTextActive: {
    color: palette.text,
  },
  railDivider: {
    width: 1,
    height: 24,
    backgroundColor: palette.hairline,
  },
  railSymbol: {
    minHeight: 40,
    justifyContent: 'center',
    paddingHorizontal: 10,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
    backgroundColor: palette.surface,
  },
  railSymbolActive: {
    borderColor: palette.hairlineStrong,
    backgroundColor: palette.surfaceActive,
  },
  railSymbolText: {
    color: palette.textFaint,
  },
  railSymbolTextActive: {
    color: palette.text,
  },
  railName: {
    color: palette.textFaint,
    fontSize: 10,
    lineHeight: 13,
  },
  railDelta: {
    fontSize: 10,
    lineHeight: 13,
  },
  railRule: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: 2,
    borderTopLeftRadius: 2,
    borderTopRightRadius: 2,
  },
});
