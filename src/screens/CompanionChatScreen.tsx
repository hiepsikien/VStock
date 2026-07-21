import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import * as Haptics from 'expo-haptics';
import type { RootStackParamList } from '../navigation/types';
import {
  sendCompanionChat,
  streamCompanionChat,
  type CompanionChatMessage,
} from '../api/client';
import { buildCompanionContext } from '../companion/orchestrator';
import { colors, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'CompanionChat'>;

type Bubble = CompanionChatMessage & { id: string };

export function CompanionChatScreen({ navigation, route }: Props) {
  const insets = useSafeAreaInsets();
  const seed = route.params?.seedMessage;
  const screen = route.params?.screen ?? 'Watchlist';
  const symbol = route.params?.symbol;
  const watchlistSymbols = route.params?.watchlistSymbols;
  const avgChange = route.params?.avgChange;
  const sessionLabel = route.params?.sessionLabel;

  const [input, setInput] = useState(seed ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<Bubble[]>([
    {
      id: 'hello',
      role: 'assistant',
      content:
        'Mình là Companion của VStock — cùng nhìn thị trường và giữ nhịp cảm xúc. Mình không tư vấn mua/bán.',
    },
  ]);
  const listRef = useRef<FlatList<Bubble>>(null);
  const seeded = useRef(false);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busy) return;

      setError(null);
      setBusy(true);
      setInput('');

      const userMsg: Bubble = {
        id: `u-${Date.now()}`,
        role: 'user',
        content: trimmed,
      };
      const history = [...messages.filter((m) => m.id !== 'hello'), userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const assistantId = `a-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        userMsg,
        { id: assistantId, role: 'assistant', content: '' },
      ]);

      try {
        const context = await buildCompanionContext({
          screen,
          symbol,
          sessionLabel,
          watchlistSymbols,
          avgChange,
        });

        let usedStream = true;
        try {
          await streamCompanionChat(
            history,
            context,
            (delta) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: m.content + delta } : m,
                ),
              );
            },
            (replace) => {
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, content: replace } : m)),
              );
            },
          );
        } catch {
          usedStream = false;
        }

        if (!usedStream) {
          const reply = await sendCompanionChat(history, context);
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: reply } : m)),
          );
        } else {
          setMessages((prev) => {
            const cur = prev.find((m) => m.id === assistantId);
            if (cur && !cur.content.trim()) {
              return prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      content:
                        'Mình chưa nhận được phản hồi. Thử lại giúp mình nhé.',
                    }
                  : m,
              );
            }
            return prev;
          });
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Lỗi kết nối Companion';
        setError(msg);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content:
                    'Không kết nối được Companion. Kiểm tra API local và GEMINI_API_KEY.',
                }
              : m,
          ),
        );
      } finally {
        setBusy(false);
        requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
      }
    },
    [
      avgChange,
      busy,
      messages,
      screen,
      sessionLabel,
      symbol,
      watchlistSymbols,
    ],
  );

  useEffect(() => {
    if (seed && !seeded.current) {
      seeded.current = true;
      void send(seed);
    }
  }, [seed, send]);

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <StatusBar style="light" />
      <View style={styles.nav}>
        <Pressable
          onPress={() => {
            void Haptics.selectionAsync();
            navigation.goBack();
          }}
          hitSlop={12}
          style={styles.backBtn}
        >
          <Text style={styles.backChevron}>‹</Text>
          <Text style={styles.backLabel}>Đóng</Text>
        </Pressable>
        <Text style={styles.title}>Companion</Text>
        <View style={styles.navSpacer} />
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={8}
      >
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
          renderItem={({ item }) => (
            <View
              style={[
                styles.bubble,
                item.role === 'user' ? styles.bubbleUser : styles.bubbleAssistant,
              ]}
            >
              <Text
                style={[
                  styles.bubbleText,
                  item.role === 'user' ? styles.bubbleTextUser : null,
                ]}
              >
                {item.content || (busy ? '…' : '')}
              </Text>
            </View>
          )}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Text style={styles.disclaimer}>
          Companion không đưa khuyến nghị mua/bán. Quyết định là của bạn.
        </Text>

        <View style={[styles.composer, { paddingBottom: Math.max(insets.bottom, 12) }]}>
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder="Nhắn với Companion…"
            placeholderTextColor={colors.textTertiary}
            style={styles.input}
            editable={!busy}
            multiline
            onSubmitEditing={() => void send(input)}
          />
          <Pressable
            onPress={() => void send(input)}
            disabled={busy || !input.trim()}
            style={[styles.send, (!input.trim() || busy) && styles.sendDisabled]}
          >
            {busy ? (
              <ActivityIndicator color={colors.text} />
            ) : (
              <Text style={styles.sendText}>Gửi</Text>
            )}
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
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
  title: {
    ...typography.title,
    fontSize: 17,
    color: colors.text,
  },
  navSpacer: { minWidth: 72 },
  list: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    gap: 10,
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
  },
  bubbleAssistant: {
    alignSelf: 'flex-start',
    backgroundColor: colors.surface,
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
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendDisabled: { opacity: 0.4 },
  sendText: { color: '#fff', fontWeight: '600', fontSize: 15 },
});
