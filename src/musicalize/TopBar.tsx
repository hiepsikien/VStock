import React, { useEffect, useRef } from 'react';
import { Animated, Platform, Pressable, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { palette, TOPBAR_HEIGHT } from './palette';
import { type } from './type';

type Props = {
  mode: 'replay' | 'live';
  onMode: (mode: 'replay' | 'live') => void;
  onSearch?: () => void;
  searchEnabled?: boolean;
};

export function TopBar({ mode, onMode, onSearch, searchEnabled = true }: Props) {
  const pulse = useRef(new Animated.Value(1)).current;
  const { width } = useWindowDimensions();
  // Phones keep only the wordmark and the mode switch; the search key and the
  // status label would push the pill off the bar.
  const compact = width < 720;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.25, duration: 800, useNativeDriver: false }),
        Animated.timing(pulse, { toValue: 1, duration: 800, useNativeDriver: false }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  return (
    <View style={styles.bar}>
      <View style={styles.brand}>
        <Text style={[type.wordmark, styles.wordmark]}>Musicalize</Text>
        <View style={styles.brandDot} />
      </View>

      <View style={styles.right}>
        {searchEnabled && onSearch && !compact ? (
          <Pressable
            onPress={onSearch}
            hitSlop={8}
            style={styles.search}
            accessibilityRole="button"
            accessibilityLabel="Bảng lệnh"
          >
            <Text style={[type.monoSmall, styles.searchText]}>
              {Platform.OS === 'web' ? '⌘K' : 'TÌM'}
            </Text>
          </Pressable>
        ) : null}

        <View style={styles.pill} accessibilityRole="tablist">
          <ModePill label="Nghe lại" active={mode === 'replay'} onPress={() => onMode('replay')} />
          <ModePill label="Đang phát" active={mode === 'live'} onPress={() => onMode('live')} />
        </View>

        {compact ? (
          mode === 'live' ? (
            <View style={[styles.status, styles.statusCompact]}>
              <Animated.View style={[styles.liveDot, { opacity: pulse }]} />
            </View>
          ) : null
        ) : mode === 'live' ? (
          <View style={styles.status}>
            <Animated.View style={[styles.liveDot, { opacity: pulse }]} />
            <Text style={[type.section, styles.statusText]}>Trực tiếp</Text>
          </View>
        ) : (
          <Text style={[type.section, styles.statusIdle]}>Phòng nghe</Text>
        )}
      </View>
    </View>
  );
}

function ModePill({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      hitSlop={8}
      style={[styles.pillItem, active && styles.pillItemActive]}
      accessibilityRole="tab"
      accessibilityLabel={label}
      accessibilityState={{ selected: active }}
    >
      <View style={[styles.pillDot, active && styles.pillDotActive]} />
      <Text style={[type.sans, styles.pillText, active && styles.pillTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: TOPBAR_HEIGHT,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    backgroundColor: palette.panel,
    borderBottomWidth: 1,
    borderBottomColor: palette.hairline,
  },
  brand: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  wordmark: {
    color: palette.text,
  },
  brandDot: {
    width: 6,
    height: 6,
    marginLeft: 10,
    backgroundColor: palette.sound,
  },
  right: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  search: {
    height: 28,
    minWidth: 44,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 8,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: palette.hairline,
  },
  searchText: {
    color: palette.textFaint,
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.hairline,
    padding: 2,
  },
  pillItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    height: 28,
    paddingHorizontal: 12,
    borderRadius: 999,
    minHeight: 28,
  },
  pillItemActive: {
    backgroundColor: palette.surface,
  },
  pillDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: palette.textFaint,
  },
  pillDotActive: {
    backgroundColor: palette.sound,
  },
  pillText: {
    color: palette.textFaint,
    fontSize: 13,
  },
  pillTextActive: {
    color: palette.text,
  },
  status: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    minWidth: 92,
    justifyContent: 'flex-end',
  },
  statusCompact: {
    minWidth: 0,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: palette.sound,
  },
  statusText: {
    color: palette.text,
  },
  statusIdle: {
    color: palette.textFaint,
    minWidth: 92,
    textAlign: 'right',
  },
});

