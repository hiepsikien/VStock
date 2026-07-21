import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  FlatList,
  Keyboard,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  type KeyboardEvent,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import * as Haptics from 'expo-haptics';
import type { RootStackParamList } from '../navigation/types';
import {
  getApiUrl,
  sendCompanionChat,
  type CompanionChatMessage,
} from '../api/client';
import { getCompanionCharacter } from '../companion/characters';
import {
  evolveBond,
  loadCompanionBond,
  loadCompanionChat,
  messagesForApi,
  saveCompanionBond,
  saveCompanionChat,
  WELCOME_BACK_GAP_MS,
  type CompanionBond,
  type StoredChatMessage,
} from '../companion/chatStore';
import { buildCompanionContext } from '../companion/orchestrator';
import { revealText, thinkingPauseMs } from '../companion/reveal';
import { CompanionAvatar } from '../components/CompanionAvatar';
import { CompanionProfileModal } from '../components/CompanionProfileModal';
import { CompanionTypingDots } from '../components/CompanionTypingDots';
import { colors, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'CompanionChat'>;

type Bubble = CompanionChatMessage & {
  id: string;
  ts?: number;
  /** Empty content + typing = animated “đang gõ” row */
  typing?: boolean;
};

type Presence = 'online' | 'reading' | 'typing';

export function CompanionChatScreen({ navigation, route }: Props) {
  const insets = useSafeAreaInsets();
  const character = getCompanionCharacter();
  const seed = route.params?.seedMessage;
  const screen = route.params?.screen ?? 'Watchlist';
  const symbol = route.params?.symbol;
  const watchlistSymbols = route.params?.watchlistSymbols;
  const avgChange = route.params?.avgChange;
  const sessionLabel = route.params?.sessionLabel;

  const [input, setInput] = useState(seed ?? '');
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [keyboardHeight, setKeyboardHeight] = useState(0);
  const [presence, setPresence] = useState<Presence>('online');
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<Bubble[]>([]);
  const [bond, setBond] = useState<CompanionBond | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const listRef = useRef<FlatList<Bubble>>(null);
  const seeded = useRef(false);
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const openProfile = useCallback(() => {
    Keyboard.dismiss();
    void Haptics.selectionAsync();
    setProfileOpen(true);
  }, []);

  const presenceLabel =
    presence === 'reading'
      ? 'đang đọc…'
      : presence === 'typing'
        ? 'đang gõ…'
        : 'đang online';

  const composerPad =
    keyboardHeight > 0 ? 10 : Math.max(insets.bottom, 12);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [stored, storedBond] = await Promise.all([
        loadCompanionChat(character.id),
        loadCompanionBond(character.id),
      ]);
      if (cancelled) return;

      setBond(storedBond);

      if (stored.length > 0) {
        const lastTs = stored[stored.length - 1]?.ts ?? 0;
        const bubbles: Bubble[] = stored.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          ts: m.ts,
        }));
        if (Date.now() - lastTs > WELCOME_BACK_GAP_MS) {
          bubbles.push({
            id: `wb-${Date.now()}`,
            role: 'assistant',
            content: character.welcomeBack,
            ts: Date.now(),
          });
        }
        setMessages(bubbles);
      } else {
        setMessages([
          {
            id: 'hello',
            role: 'assistant',
            content: character.greeting,
            ts: Date.now(),
          },
        ]);
      }
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [character.greeting, character.id, character.welcomeBack]);

  useEffect(() => {
    if (!ready) return;
    if (persistTimer.current) clearTimeout(persistTimer.current);
    persistTimer.current = setTimeout(() => {
      const toStore: StoredChatMessage[] = messages
        .filter((m) => !m.typing && m.content.trim().length > 0)
        .map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          ts: m.ts ?? Date.now(),
        }));
      void saveCompanionChat(character.id, toStore);
    }, 250);
    return () => {
      if (persistTimer.current) clearTimeout(persistTimer.current);
    };
  }, [character.id, messages, ready]);

  useEffect(() => {
    const showEvent = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const onShow = (e: KeyboardEvent) => {
      // iOS overlays the keyboard; Android usually resizes the window already.
      setKeyboardHeight(Platform.OS === 'ios' ? e.endCoordinates.height : 0);
      requestAnimationFrame(() =>
        listRef.current?.scrollToEnd({ animated: true }),
      );
    };
    const onHide = () => setKeyboardHeight(0);
    const subShow = Keyboard.addListener(showEvent, onShow);
    const subHide = Keyboard.addListener(hideEvent, onHide);
    return () => {
      subShow.remove();
      subHide.remove();
    };
  }, []);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busy || !ready) return;

      setError(null);
      setBusy(true);
      setInput('');

      const now = Date.now();
      const userMsg: Bubble = {
        id: `u-${now}`,
        role: 'user',
        content: trimmed,
        ts: now,
      };

      const nextBond = evolveBond(bond, trimmed, symbol ? [symbol] : []);
      setBond(nextBond);
      void saveCompanionBond(character.id, nextBond);

      const history = messagesForApi(
        [...messages.filter((m) => !m.typing), userMsg].map((m) => ({
          role: m.role,
          content: m.content,
        })),
      );

      const assistantId = `a-${now}`;
      setMessages((prev) => [...prev, userMsg]);
      setPresence('reading');

      try {
        await sleep(thinkingPauseMs());
        setPresence('typing');
        setMessages((prev) => [
          ...prev,
          { id: assistantId, role: 'assistant', content: '', typing: true, ts: Date.now() },
        ]);

        const context = await buildCompanionContext(
          {
            screen,
            symbol,
            sessionLabel,
            watchlistSymbols,
            avgChange,
          },
          nextBond,
        );

        const reply = await sendCompanionChat(history, context);
        const finalText =
          reply.trim() ||
          'Ối, tín hiệu hơi chậm. Bạn gửi lại giúp mình nhé.';

        await revealText(finalText, (partial) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: partial, typing: partial.length === 0 }
                : m,
            ),
          );
        });

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: finalText, typing: false, ts: Date.now() }
              : m,
          ),
        );
        void Haptics.selectionAsync();
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Lỗi kết nối Companion';
        setError(`${msg} (${getApiUrl()})`);
        setMessages((prev) => {
          const hasRow = prev.some((m) => m.id === assistantId);
          const failContent =
            'Hmm, mình chưa kết nối được server. Kiểm tra API local giúp mình nhé.';
          if (!hasRow) {
            return [
              ...prev,
              {
                id: assistantId,
                role: 'assistant',
                typing: false,
                content: failContent,
                ts: Date.now(),
              },
            ];
          }
          return prev.map((m) =>
            m.id === assistantId
              ? { ...m, typing: false, content: failContent, ts: Date.now() }
              : m,
          );
        });
      } finally {
        setPresence('online');
        setBusy(false);
        requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
      }
    },
    [
      avgChange,
      bond,
      busy,
      character.id,
      messages,
      ready,
      screen,
      sessionLabel,
      symbol,
      watchlistSymbols,
    ],
  );

  useEffect(() => {
    if (!ready || !seed || seeded.current) return;
    seeded.current = true;
    void send(seed);
  }, [ready, seed, send]);

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <StatusBar style="light" />
      <View style={styles.nav}>
        <Pressable
          onPress={() => {
            void Haptics.selectionAsync();
            Keyboard.dismiss();
            navigation.goBack();
          }}
          hitSlop={12}
          style={styles.backBtn}
        >
          <Text style={styles.backChevron}>‹</Text>
          <Text style={styles.backLabel}>Đóng</Text>
        </Pressable>
        <Pressable
          onPress={openProfile}
          style={styles.navCenter}
          accessibilityRole="button"
          accessibilityLabel={`Xem hồ sơ ${character.name}`}
        >
          <CompanionAvatar character={character} size={32} />
          <View style={styles.navTitles}>
            <Text style={styles.title}>{character.name}</Text>
            <Text style={styles.subtitle}>{presenceLabel}</Text>
          </View>
        </Pressable>
        <View style={styles.navSpacer} />
      </View>

      <CompanionProfileModal
        character={character}
        visible={profileOpen}
        onClose={() => setProfileOpen(false)}
      />

      <View style={[styles.flex, { paddingBottom: keyboardHeight }]}>
        <FlatList
          ref={listRef}
          style={styles.flex}
          data={messages}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="interactive"
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
          renderItem={({ item }) => {
            if (item.role === 'user') {
              return (
                <View style={[styles.bubble, styles.bubbleUser]}>
                  <Text style={[styles.bubbleText, styles.bubbleTextUser]}>
                    {item.content}
                  </Text>
                </View>
              );
            }

            return (
              <View style={styles.assistantRow}>
                <Pressable onPress={openProfile} hitSlop={6}>
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
          }}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Text style={styles.disclaimer}>
          {character.name} không đưa khuyến nghị mua/bán. Quyết định là của bạn.
        </Text>

        <View style={[styles.composer, { paddingBottom: composerPad }]}>
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder={character.placeholder}
            placeholderTextColor={colors.textTertiary}
            style={styles.input}
            editable={!busy && ready}
            multiline
            onFocus={() =>
              requestAnimationFrame(() =>
                listRef.current?.scrollToEnd({ animated: true }),
              )
            }
            onSubmitEditing={() => void send(input)}
          />
          <Pressable
            onPress={() => void send(input)}
            disabled={busy || !ready || !input.trim()}
            style={[
              styles.send,
              { backgroundColor: character.accent },
              (!input.trim() || busy || !ready) && styles.sendDisabled,
            ]}
          >
            <Text style={styles.sendText}>Gửi</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  flex: { flex: 1 },
  nav: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  backBtn: { flexDirection: 'row', alignItems: 'center', minWidth: 72 },
  backChevron: {
    color: colors.accent,
    fontSize: 32,
    lineHeight: 34,
    marginRight: 2,
    fontWeight: '300',
  },
  backLabel: { color: colors.accent, fontSize: 17 },
  navCenter: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  navTitles: { alignItems: 'flex-start' },
  title: {
    ...typography.symbol,
    fontSize: 16,
    color: colors.text,
  },
  subtitle: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 1,
  },
  navSpacer: { minWidth: 72 },
  list: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    gap: 12,
    flexGrow: 1,
    justifyContent: 'flex-end',
  },
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
  error: {
    color: colors.negative,
    fontSize: 12,
    paddingHorizontal: spacing.lg,
    marginBottom: 4,
  },
  disclaimer: {
    ...typography.caption,
    color: colors.textTertiary,
    paddingHorizontal: spacing.lg,
    marginBottom: 6,
  },
  composer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    paddingHorizontal: spacing.lg,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    paddingTop: 10,
  },
  input: {
    flex: 1,
    minHeight: 40,
    maxHeight: 120,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: colors.surface,
    color: colors.text,
    fontSize: 16,
  },
  send: {
    height: 40,
    paddingHorizontal: 14,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendDisabled: { opacity: 0.4 },
  sendText: { color: '#0B1220', fontWeight: '700', fontSize: 15 },
});
