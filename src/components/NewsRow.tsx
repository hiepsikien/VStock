import React from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import type { NewsItem } from '../types/news';
import { categoryLabel, formatNewsTime } from '../types/news';
import { colors, spacing, typography } from '../theme';

type Props = {
  item: NewsItem;
  onPress: (item: NewsItem) => void;
  compact?: boolean;
  isLast?: boolean;
};

export function NewsRow({ item, onPress, compact = false, isLast = false }: Props) {
  const time = formatNewsTime(item.publishedAt);
  const tag = item.symbols[0] ?? categoryLabel(item.category);

  return (
    <Pressable
      onPress={() => {
        void Haptics.selectionAsync();
        onPress(item);
      }}
      style={({ pressed }) => [
        styles.row,
        !isLast && styles.border,
        pressed && styles.pressed,
        compact && styles.compact,
      ]}
    >
      <View style={styles.content}>
        <View style={styles.metaRow}>
          <Text style={styles.source}>{item.source}</Text>
          {time ? <Text style={styles.time}>{time}</Text> : null}
        </View>
        <Text style={[styles.title, compact && styles.titleCompact]} numberOfLines={compact ? 2 : 3}>
          {item.title}
        </Text>
        {!compact && item.summary ? (
          <Text style={styles.summary} numberOfLines={2}>
            {item.summary}
          </Text>
        ) : null}
        <View style={styles.tagRow}>
          <View style={styles.tag}>
            <Text style={styles.tagText}>{tag}</Text>
          </View>
        </View>
      </View>
      {item.imageUrl ? (
        <Image source={{ uri: item.imageUrl }} style={styles.thumb} />
      ) : (
        <View style={[styles.thumb, styles.thumbPlaceholder]} />
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    paddingVertical: 14,
    gap: spacing.md,
    alignItems: 'flex-start',
  },
  compact: {
    paddingVertical: 12,
  },
  border: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  pressed: {
    opacity: 0.85,
  },
  content: {
    flex: 1,
    minWidth: 0,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  source: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  time: {
    fontSize: 12,
    color: colors.textTertiary,
  },
  title: {
    ...typography.symbol,
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    lineHeight: 22,
  },
  titleCompact: {
    fontSize: 15,
    lineHeight: 20,
  },
  summary: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 6,
    lineHeight: 18,
  },
  tagRow: {
    flexDirection: 'row',
    marginTop: 8,
  },
  tag: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  tagText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textTertiary,
  },
  thumb: {
    width: 72,
    height: 72,
    borderRadius: 8,
    backgroundColor: colors.surfaceElevated,
  },
  thumbPlaceholder: {
    backgroundColor: colors.surfaceElevated,
  },
});
