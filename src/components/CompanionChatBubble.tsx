import React, { memo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { CompanionCharacter } from '../companion/characters';
import { colors } from '../theme';
import { CompanionAvatar } from './CompanionAvatar';
import { CompanionTypingDots } from './CompanionTypingDots';
import { TickerText } from './TickerText';

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
  /** Symbols that may deep-link to Detail */
  linkableSymbols?: ReadonlySet<string> | null;
  onPressSymbol?: (symbol: string) => void;
};

function ChatBubbleInner({
  item,
  character,
  onPressAvatar,
  linkableSymbols,
  onPressSymbol,
}: Props) {
  if (item.role === 'user') {
    return (
      <View style={[styles.bubble, styles.bubbleUser]}>
        <TickerText
          text={item.content}
          style={[styles.bubbleText, styles.bubbleTextUser]}
          linkColor="#FFFFFF"
          allowlist={linkableSymbols}
          onPressSymbol={onPressSymbol}
        />
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
        ) : item.typing ? (
          // Plain text while streaming — skip ticker parse on every chunk.
          <Text style={styles.bubbleText}>{item.content}</Text>
        ) : (
          <TickerText
            text={item.content}
            style={styles.bubbleText}
            linkColor={character.accent}
            allowlist={linkableSymbols}
            onPressSymbol={onPressSymbol}
          />
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
    prev.onPressAvatar === next.onPressAvatar &&
    prev.onPressSymbol === next.onPressSymbol &&
    prev.linkableSymbols === next.linkableSymbols,
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
