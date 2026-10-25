import React, { useEffect, useRef, useState } from 'react';
import { Animated, Easing, StyleSheet, Text, View } from 'react-native';
import { colors, typography } from '../theme';

type Props = {
  title: string;
  instruments: string;
  movement: string | null;
  docked: boolean;
};

const SCALE = 0.7;
/** The opening playhead and its time label keep this strip. The title docks beside it. */
export const TITLE_DOCK_LEFT = 88;

export function PieceTitle({ title, instruments, movement, docked }: Props) {
  const progress = useRef(new Animated.Value(docked ? 1 : 0)).current;
  const [frame, setFrame] = useState({ width: 0, height: 0 });
  const [box, setBox] = useState({ width: 0, height: 0 });

  useEffect(() => {
    Animated.timing(progress, {
      toValue: docked ? 1 : 0,
      duration: 520,
      easing: Easing.inOut(Easing.cubic),
      useNativeDriver: false,
    }).start();
  }, [docked, progress]);

  const ready = frame.width > 0 && box.width > 0;
  const inset = (1 - SCALE) / 2;
  const centerLeft = Math.max(8, (frame.width - box.width) / 2);
  const centerTop = Math.max(8, (frame.height - box.height) / 2);
  const cornerLeft = TITLE_DOCK_LEFT - box.width * inset;
  const cornerTop = Math.max(4, 8 - box.height * inset);
  const left = progress.interpolate({ inputRange: [0, 1], outputRange: [centerLeft, cornerLeft] });
  const top = progress.interpolate({ inputRange: [0, 1], outputRange: [centerTop, cornerTop] });
  const scale = progress.interpolate({ inputRange: [0, 1], outputRange: [1, SCALE] });

  return (
    <View
      pointerEvents="none"
      style={styles.frame}
      onLayout={(event) => {
        const { width, height } = event.nativeEvent.layout;
        setFrame((current) => (current.width === width && current.height === height ? current : { width, height }));
      }}
    >
      <Animated.View
        style={[
          styles.copy,
          {
            maxWidth: Math.min(260, Math.max(160, frame.width - 48)),
            opacity: ready ? 1 : 0,
            left,
            top,
            transform: [{ scale }],
          },
        ]}
        onLayout={(event) => {
          const { width, height } = event.nativeEvent.layout;
          setBox((current) => (current.width === width && current.height === height ? current : { width, height }));
        }}
      >
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.line}>{instruments}</Text>
        {movement ? <Text style={styles.line}>{movement}</Text> : null}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
  },
  copy: {
    position: 'absolute',
    alignItems: 'center',
  },
  title: {
    ...typography.title,
    color: colors.text,
    textAlign: 'center',
  },
  line: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 2,
  },
});
