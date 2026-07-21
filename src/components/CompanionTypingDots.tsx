import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';
import { colors } from '../theme';

type Props = {
  accent?: string;
};

/** Three bouncing dots — feels like a person typing, not a spinner. */
export function CompanionTypingDots({ accent = colors.accent }: Props) {
  const a = useRef(new Animated.Value(0)).current;
  const b = useRef(new Animated.Value(0)).current;
  const c = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const make = (v: Animated.Value, delay: number) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(delay),
          Animated.timing(v, { toValue: 1, duration: 280, useNativeDriver: true }),
          Animated.timing(v, { toValue: 0, duration: 280, useNativeDriver: true }),
          Animated.delay(320),
        ]),
      );
    const loops = [make(a, 0), make(b, 120), make(c, 240)];
    loops.forEach((l) => l.start());
    return () => loops.forEach((l) => l.stop());
  }, [a, b, c]);

  const dot = (v: Animated.Value) => (
    <Animated.View
      style={[
        styles.dot,
        {
          backgroundColor: accent,
          opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0.35, 1] }),
          transform: [
            {
              translateY: v.interpolate({ inputRange: [0, 1], outputRange: [0, -3] }),
            },
          ],
        },
      ]}
    />
  );

  return <View style={styles.row}>{dot(a)}{dot(b)}{dot(c)}</View>;
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingVertical: 2,
    minHeight: 18,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
});
