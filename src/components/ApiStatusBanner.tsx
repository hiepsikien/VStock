import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { colors, spacing } from '../theme';

type Props = {
  message: string;
  onRetry?: () => void;
};

export function ApiStatusBanner({ message, onRetry }: Props) {
  return (
    <View style={styles.wrap}>
      <Text style={styles.text}>{message}</Text>
      {onRetry ? (
        <Pressable
          onPress={() => {
            void Haptics.selectionAsync();
            onRetry();
          }}
          hitSlop={8}
        >
          <Text style={styles.retry}>Thử lại</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    backgroundColor: 'rgba(255, 69, 58, 0.12)',
    borderRadius: 10,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  text: {
    color: colors.negative,
    fontSize: 13,
    flex: 1,
    lineHeight: 18,
  },
  retry: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: '700',
  },
});
