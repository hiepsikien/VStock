import React, { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, typography } from '../theme';
import type { PiecePhase } from '../sonify/program';

type Props = {
  title: string;
  instruments: string;
  movement: string | null;
  /** `playing` is drawn by the chart caption, not this card. */
  phase: Exclude<PiecePhase, 'playing'>;
};

export function PieceTitle({ title, instruments, movement, phase }: Props) {
  const [frameWidth, setFrameWidth] = useState(0);
  const copyWidth = Math.max(0, frameWidth - 32);

  return (
    <View
      pointerEvents="none"
      style={styles.frame}
      onLayout={(event) => {
        const width = event.nativeEvent.layout.width;
        setFrameWidth((current) => (current === width ? current : width));
      }}
    >
      <View style={[styles.copy, { width: copyWidth }]}>
        {phase === 'movement' ? (
          <Text style={styles.movement} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>
            {movement}
          </Text>
        ) : (
          <>
            <Text style={styles.title} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.6}>
              {title}
            </Text>
            <Text style={styles.line} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>
              {instruments}
            </Text>
            {movement ? (
              <Text style={styles.line} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>
                {movement}
              </Text>
            ) : null}
          </>
        )}
      </View>
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
    alignItems: 'center',
    justifyContent: 'center',
  },
  copy: {
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
  movement: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: 'center',
  },
});
