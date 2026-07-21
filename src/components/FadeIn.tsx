import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, type StyleProp, type ViewStyle } from 'react-native';

type Props = {
  children: React.ReactNode;
  /** When true, fade to visible; when false, fade out. */
  visible?: boolean;
  duration?: number;
  style?: StyleProp<ViewStyle>;
  /** If true, start transparent and fade in on mount (ignores visible until first paint). */
  mountFade?: boolean;
};

/** Soft opacity transition for skeleton → content (and similar swaps). */
export function FadeIn({
  children,
  visible = true,
  duration = 280,
  style,
  mountFade = false,
}: Props) {
  const opacity = useRef(new Animated.Value(mountFade || !visible ? 0 : 1)).current;

  useEffect(() => {
    Animated.timing(opacity, {
      toValue: visible ? 1 : 0,
      duration,
      useNativeDriver: true,
    }).start();
  }, [duration, opacity, visible]);

  return (
    <Animated.View style={[styles.fill, style, { opacity }]} pointerEvents={visible ? 'auto' : 'none'}>
      {children}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  fill: {
    flex: 1,
  },
});
