import React, { memo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { CompanionCharacter } from '../companion/characters';
import { colors } from '../theme';
import { CompanionAvatar } from './CompanionAvatar';
import { CompanionTypingDots } from './CompanionTypingDots';

export type ChatBubbleItem = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  typing?: boolean;
};

type Props = {
  item: ChatBubbleItem;
  character: CompanionCharacter;
  onPressAvatar: () => void;
};

function ChatBubbleInner({ item, character, onPressAvatar }: Props) {
  if (item.role === 'user') {
    return (
      <View style={[styles.bubble, styles.bubbleUser]}>
        <Text style={[styles.bubbleText, styles.bubbleTextUser]}>{item.content}</Text>
      </View>
    );
  }

  return (
    <View style={styles.assistantRow}>
      <Pressable onPress={onPressAvatar} hitSlop={6}>
        <CompanionAvatar character={character} size={28} />
      </Pressable>
      <View
        style={[
          styles.bubble,
          styles.bubbleAssistant,
          { borderColor: `${character.accent}33` },
        ]}
      >
        {item.typing && !item.content ? (
          <CompanionTypingDots accent={character.accent} />
        ) : (
          <Text style={styles.bubbleText}>{item.content}</Text>
        )}
      </View>
    </View>
  );
}

export const CompanionChatBubble = memo(
  ChatBubbleInner,
  (prev, next) =>
    prev.item.id === next.item.id &&
    prev.item.role === next.item.role &&
    prev.item.content === next.item.content &&
    prev.item.typing === next.item.typing &&
    prev.character.id === next.character.id &&
    prev.onPressAvatar === next.onPressAvatar,
);

const styles = StyleSheet.create({
  assistantRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    alignSelf: 'flex-start',
    maxWidth: '92%',
  },
  bubble: {
    maxWidth: '88%',
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  bubbleUser: {
    alignSelf: 'flex-end',
    backgroundColor: colors.accent,
    maxWidth: '82%',
  },
  bubbleAssistant: {
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderBottomLeftRadius: 6,
  },
  bubbleText: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 21,
  },
  bubbleTextUser: {
    color: '#fff',
  },
});
