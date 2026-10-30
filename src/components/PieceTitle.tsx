import React, { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, typography } from '../theme';
type Props = {
  title: string;
  instruments: string;
  movement: string | null;
  titleColor?: string;
  lineColor?: string;
};

export function PieceTitle({ title, instruments, movement, titleColor, lineColor }: Props) {
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
        <Text
          style={[styles.title, titleColor ? { color: titleColor } : null]}
          numberOfLines={1}
          adjustsFontSizeToFit
          minimumFontScale={0.6}
        >
          {title}
        </Text>
        <Text
          style={[styles.line, lineColor ? { color: lineColor } : null]}
          numberOfLines={1}
          adjustsFontSizeToFit
          minimumFontScale={0.7}
        >
          {instruments}
        </Text>
        {movement ? (
          <Text
            style={[styles.line, lineColor ? { color: lineColor } : null]}
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.7}
          >
            {movement}
          </Text>
        ) : null}
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
});
