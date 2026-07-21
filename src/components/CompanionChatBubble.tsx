import React, { memo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { CompanionCharacter } from '../companion/characters';
import {
  actionLabel,
  expandWatchlistActions,
  type CompanionWatchlistAction,
} from '../companion/watchlistActions';
import type { Watchlist } from '../storage/watchlist';
import { colors } from '../theme';
import { CompanionAvatar } from './CompanionAvatar';
import { CompanionTypingDots } from './CompanionTypingDots';
import { TickerText } from './TickerText';

export type ChatBubbleItem = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  typing?: boolean;
  actions?: CompanionWatchlistAction[];
};

type Props = {
  item: ChatBubbleItem;
  character: CompanionCharacter;
  onPressAvatar: () => void;
  /** Symbols that may deep-link to Detail */
  linkableSymbols?: ReadonlySet<string> | null;
  onPressSymbol?: (symbol: string) => void;
  watchlists?: Watchlist[];
  onPressAction?: (action: CompanionWatchlistAction) => void;
};

function actionsEqual(
  a?: CompanionWatchlistAction[],
  b?: CompanionWatchlistAction[],
): boolean {
  if (a === b) return true;
  if (!a?.length && !b?.length) return true;
  if (!a?.length || !b?.length || a.length !== b.length) return false;
  return JSON.stringify(a) === JSON.stringify(b);
}

function ChatBubbleInner({
  item,
  character,
  onPressAvatar,
  linkableSymbols,
  onPressSymbol,
  watchlists,
  onPressAction,
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

  const displayActions =
    item.actions?.length && !item.typing
      ? expandWatchlistActions(item.actions, watchlists ?? [])
      : [];

  return (
    <View style={styles.assistantRow}>
      <Pressable onPress={onPressAvatar} hitSlop={6}>
        <CompanionAvatar character={character} size={28} />
      </Pressable>
      <View style={styles.assistantContent}>
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
            <TickerText
              text={item.content}
              style={styles.bubbleText}
              linkColor={character.accent}
              allowlist={linkableSymbols}
              onPressSymbol={onPressSymbol}
            />
          )}
        </View>
        {displayActions.length > 0 ? (
          <View style={styles.actionRow}>
            {displayActions.map((action, index) => (
              <Pressable
                key={`${action.type}-${index}`}
                onPress={() => onPressAction?.(action)}
                style={[
                  styles.actionBtn,
                  {
                    borderColor: `${character.accent}55`,
                    backgroundColor: `${character.accent}14`,
                  },
                ]}
              >
                <Text style={[styles.actionText, { color: character.accent }]}>
                  {actionLabel(action)}
                </Text>
              </Pressable>
            ))}
          </View>
        ) : null}
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
    actionsEqual(prev.item.actions, next.item.actions) &&
    prev.character.id === next.character.id &&
    prev.onPressAvatar === next.onPressAvatar &&
    prev.onPressSymbol === next.onPressSymbol &&
    prev.onPressAction === next.onPressAction &&
    prev.linkableSymbols === next.linkableSymbols &&
    prev.watchlists === next.watchlists,
);

const styles = StyleSheet.create({
  assistantRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    alignSelf: 'flex-start',
    maxWidth: '92%',
  },
  assistantContent: {
    flexShrink: 1,
    gap: 8,
    maxWidth: '88%',
  },
  bubble: {
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
  actionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  actionBtn: {
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  actionText: {
    fontSize: 14,
    fontWeight: '600',
    lineHeight: 18,
  },
});
