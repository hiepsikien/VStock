import React, { useEffect, useRef, useSyncExternalStore } from 'react';
import {
  AccessibilityInfo,
  Animated,
  Easing,
  Pressable,
  type PressableProps,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { palette } from './palette';

/**
 * Motion for the listening surface. Everything here is 120–240ms and eases out.
 * Web honours `prefers-reduced-motion`: pulses stop and transitions run at 0ms.
 */

let reduced = false;
let watching = false;
const listeners = new Set<() => void>();

function setReduced(next: boolean) {
  if (reduced === next) return;
  reduced = next;
  listeners.forEach((notify) => notify());
}

function watchReducedMotion() {
  if (watching) return;
  watching = true;
  try {
    void AccessibilityInfo.isReduceMotionEnabled()
      .then((value) => setReduced(Boolean(value)))
      .catch(() => {});
    AccessibilityInfo.addEventListener('reduceMotionChanged', (value: boolean) =>
      setReduced(Boolean(value)),
    );
  } catch {
    // Keep motion on when the platform has no accessibility bridge.
  }
}

function subscribe(notify: () => void) {
  watchReducedMotion();
  listeners.add(notify);
  return () => {
    listeners.delete(notify);
  };
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => reduced,
    () => false,
  );
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

type MotionPressableProps = Omit<PressableProps, 'style'> & {
  /** 0.97 by default: a press should feel like a key, not a bounce. */
  scaleTo?: number;
  style?: StyleProp<ViewStyle>;
};

/** `Pressable` with the shared 120ms press: scale 0.97 and opacity 0.9. */
export function MotionPressable({
  scaleTo = 0.97,
  style,
  onPressIn,
  onPressOut,
  disabled,
  ...rest
}: MotionPressableProps) {
  const isReduced = useReducedMotion();
  const press = useRef(new Animated.Value(0)).current;
  const run = (to: number) => {
    Animated.timing(press, {
      toValue: to,
      duration: isReduced ? 0 : 120,
      easing: Easing.out(Easing.quad),
      useNativeDriver: false,
    }).start();
  };
  const motion = {
    opacity: press.interpolate({ inputRange: [0, 1], outputRange: [1, 0.9] }),
    transform: [{ scale: press.interpolate({ inputRange: [0, 1], outputRange: [1, scaleTo] }) }],
  };
  return (
    <AnimatedPressable
      {...rest}
      disabled={disabled}
      onPressIn={(event) => {
        if (!disabled) run(1);
        onPressIn?.(event);
      }}
      onPressOut={(event) => {
        run(0);
        onPressOut?.(event);
      }}
      style={[style, motion] as StyleProp<ViewStyle>}
    />
  );
}

/** The 2px active rule under a chip or tile, growing from the centre. */
export function RiseRule({
  color = palette.sound,
  style,
}: {
  color?: string;
  style?: StyleProp<ViewStyle>;
}) {
  const isReduced = useReducedMotion();
  const rise = useRef(new Animated.Value(isReduced ? 1 : 0)).current;

  useEffect(() => {
    if (isReduced) {
      rise.setValue(1);
      return;
    }
    rise.setValue(0);
    const step = Animated.timing(rise, {
      toValue: 1,
      duration: 160,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    });
    step.start();
    return () => step.stop();
  }, [isReduced, rise]);

  return (
    <Animated.View
      pointerEvents="none"
      style={[style, { backgroundColor: color, transform: [{ scaleX: rise }] }]}
    />
  );
}

/**
 * Chart fade on a symbol, span or genre change: opacity 0 → 1 and translateY
 * 8 → 0. The first mount is already settled so nothing flashes on load.
 */
export function useChartEntrance(key: string, distance = 8, duration = 180) {
  const isReduced = useReducedMotion();
  const value = useRef(new Animated.Value(1)).current;
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (isReduced) {
      value.setValue(1);
      return;
    }
    value.setValue(0);
    const step = Animated.timing(value, {
      toValue: 1,
      duration,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    });
    step.start();
    return () => step.stop();
  }, [distance, duration, isReduced, key, value]);

  return {
    opacity: value,
    transform: [
      {
        translateY: value.interpolate({ inputRange: [0, 1], outputRange: [distance, 0] }),
      },
    ],
  };
}

/** A slow opacity pulse (live dot, audible playhead). Returns 1 when idle. */
export function usePulse(active: boolean, duration = 1600, low = 0.25): Animated.Value {
  const isReduced = useReducedMotion();
  const value = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    value.stopAnimation();
    if (!active || isReduced) {
      value.setValue(1);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(value, {
          toValue: low,
          duration: duration / 2,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: false,
        }),
        Animated.timing(value, {
          toValue: 1,
          duration: duration / 2,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: false,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [active, duration, isReduced, low, value]);

  return value;
}
