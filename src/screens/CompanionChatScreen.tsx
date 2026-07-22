import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
  applyBondNotes,
  buildWelcomeBackMessage,
  clearCompanionSession,
  extractNicknameFromText,
  FALSE_TICKERS,
  loadCompanionBond,
  loadCompanionChat,
  messagesForApi,
  saveCompanionBond,
  saveCompanionChat,
  WELCOME_BACK_GAP_MS,
  type CompanionBond,
  type StoredChatMessage,
} from '../companion/chatStore';
import {
  appendCompanionActivity,
  loadCompanionActivities,
  type CompanionActivity,
} from '../companion/activityStore';
import { buildCompanionContext } from '../companion/orchestrator';
import { betweenBubblesPauseMs, revealText, thinkingPauseMs } from '../companion/reveal';
import { CompanionAvatar } from '../components/CompanionAvatar';
import { CompanionChatBubble } from '../components/CompanionChatBubble';
import { CompanionProfileModal } from '../components/CompanionProfileModal';
import { CompanionWatchlistConfirmSheet } from '../components/CompanionWatchlistConfirmSheet';
import { CompanionWatchlistPickerSheet } from '../components/CompanionWatchlistPickerSheet';
import {
  expandWatchlistActions,
  type CompanionWatchlistAction,
} from '../companion/watchlistActions';
import {
  addSymbolToWatchlist,
  createWatchlist,
  loadWatchlistsState,
  removeSymbolFromWatchlist,
  type WatchlistsState,
} from '../storage/watchlist';
import { colors, spacing, typography } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'CompanionChat'>;

type Bubble = CompanionChatMessage & {
  id: string;
  ts?: number;
  /** Empty content + typing = animated “đang gõ” row */
  typing?: boolean;
};

type Presence = 'online' | 'reading' | 'fetching' | 'typing';

export function CompanionChatScreen({ navigation, route }: Props) {
  const insets = useSafeAreaInsets();
  const character = getCompanionCharacter();
  const seedUserMessage = route.params?.seedUserMessage;
  const seedAssistantMessage = route.params?.seedAssistantMessage;
  const screen = route.params?.screen ?? 'Watchlist';
  const symbol = route.params?.symbol;
  const watchlistSymbols = route.params?.watchlistSymbols;
  const avgChange = route.params?.avgChange;
  const sessionLabel = route.params?.sessionLabel;

  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [keyboardHeight, setKeyboardHeight] = useState(0);
  const [presence, setPresence] = useState<Presence>('online');
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<Bubble[]>([]);
  const [bond, setBond] = useState<CompanionBond | null>(null);
  const [activities, setActivities] = useState<CompanionActivity[]>([]);
  const [profileOpen, setProfileOpen] = useState(false);
  const [watchlistsState, setWatchlistsState] = useState<WatchlistsState | null>(null);
  const [pickerSymbol, setPickerSymbol] = useState<string | null>(null);
  const [confirmActions, setConfirmActions] = useState<
    CompanionWatchlistAction[] | null
  >(null);
  const listRef = useRef<FlatList<Bubble>>(null);
  const seeded = useRef(false);
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scrollThrottle = useRef(0);

  const openProfile = useCallback(() => {
    Keyboard.dismiss();
    void Haptics.selectionAsync();
    setProfileOpen(true);
  }, []);

  const resetSession = useCallback(async () => {
    await clearCompanionSession(character.id);
    setBond(null);
    setActivities([]);
    setMessages([
      {
        id: `hello-${Date.now()}`,
        role: 'assistant',
        content: character.greeting,
        ts: Date.now(),
      },
    ]);
    setError(null);
    setPresence('online');
  }, [character.greeting, character.id]);

  const logActivity = useCallback(
    async (
      entry: Omit<CompanionActivity, 'id' | 'ts'> & { ts?: number },
    ) => {
      const next = await appendCompanionActivity(character.id, entry);
      setActivities(next);
    },
    [character.id],
  );

  const saveNickname = useCallback(
    async (nickname: string) => {
      const now = Date.now();
      const next: CompanionBond = bond ?? {
        firstMetAt: now,
        lastChatAt: now,
        messageCount: 0,
        symbolsOfInterest: [],
        notes: [],
      };
      const trimmed = nickname.trim().slice(0, 24);
      const prevNick = bond?.userNickname?.trim() || '';
      next.userNickname = trimmed.length > 0 ? trimmed : undefined;
      await saveCompanionBond(character.id, next);
      setBond(next);
      if (trimmed && trimmed !== prevNick) {
        void logActivity({
          type: 'set_nickname',
          label: `Vy sẽ gọi bạn là ${trimmed}`,
        });
      }
    },
    [bond, character.id, logActivity],
  );

  const openSymbol = useCallback(
    (sym: string) => {
      void Haptics.selectionAsync();
      Keyboard.dismiss();
      navigation.navigate('Detail', { symbol: sym.toUpperCase() });
    },
    [navigation],
  );

  const validSymbols = useMemo(() => {
    const set = new Set<string>();
    if (symbol) set.add(symbol.toUpperCase());
    for (const s of watchlistSymbols ?? []) set.add(s.toUpperCase());
    for (const list of watchlistsState?.lists ?? []) {
      for (const s of list.symbols) set.add(s.toUpperCase());
    }
    for (const s of bond?.symbolsOfInterest ?? []) set.add(s.toUpperCase());
    return set;
  }, [bond?.symbolsOfInterest, symbol, watchlistSymbols, watchlistsState?.lists]);

  const linkableKey = useMemo(() => {
    const out: string[] = [];
    for (const s of validSymbols) {
      if (!FALSE_TICKERS.has(s)) out.push(s);
    }
    out.sort();
    return out.join(',');
  }, [validSymbols]);

  const linkableSymbols = useMemo(() => {
    if (!linkableKey) return null;
    return new Set(linkableKey.split(','));
  }, [linkableKey]);

  const presenceLabel =
    presence === 'reading'
      ? 'đang đọc…'
      : presence === 'fetching'
        ? 'đang lấy giá…'
        : presence === 'typing'
          ? 'đang gõ…'
          : 'đang online';

  const composerPad =
    keyboardHeight > 0 ? 10 : Math.max(insets.bottom, 12);

  useEffect(() => {
    void loadWatchlistsState().then(setWatchlistsState);
  }, []);

  const appendAssistantNote = useCallback((content: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `sys-${Date.now()}`,
        role: 'assistant',
        content,
        ts: Date.now(),
      },
    ]);
  }, []);

  const executeAddSymbol = useCallback(
    async (sym: string, watchlistId: string) => {
      const next = await addSymbolToWatchlist(sym, watchlistId);
      setWatchlistsState(next);
      const list = next.lists.find((l) => l.id === watchlistId);
      const listName = list?.name ?? 'danh sách';
      appendAssistantNote(
        `Xong rồi — mình đã thêm ${sym.toUpperCase()} vào “${listName}”.`,
      );
      void logActivity({
        type: 'add_symbol',
        label: `Thêm ${sym.toUpperCase()} vào “${listName}”`,
        symbol: sym,
        watchlistName: listName,
      });
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    },
    [appendAssistantNote, logActivity],
  );

  const executeCreateWatchlist = useCallback(
    async (name: string, symbols?: string[]) => {
      let next = await createWatchlist(name);
      const added: string[] = [];
      for (const sym of symbols ?? []) {
        next = await addSymbolToWatchlist(sym, next.activeId);
        added.push(sym.toUpperCase());
      }
      setWatchlistsState(next);
      const list = next.lists.find((l) => l.id === next.activeId);
      const listName = list?.name ?? name;
      appendAssistantNote(
        added.length
          ? `Đã tạo “${listName}” với ${added.join(', ')}.`
          : `Đã tạo danh sách “${listName}”.`,
      );
      void logActivity({
        type: 'create_watchlist',
        label: added.length
          ? `Tạo “${listName}” với ${added.join(', ')}`
          : `Tạo danh sách “${listName}”`,
        watchlistName: listName,
      });
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    },
    [appendAssistantNote, logActivity],
  );

  const executeRemoveSymbol = useCallback(
    async (sym: string, watchlistId: string) => {
      const next = await removeSymbolFromWatchlist(sym, watchlistId);
      setWatchlistsState(next);
      const list = next.lists.find((l) => l.id === watchlistId);
      const listName = list?.name ?? 'danh sách';
      appendAssistantNote(
        `Đã xóa ${sym.toUpperCase()} khỏi “${listName}”.`,
      );
      void logActivity({
        type: 'remove_symbol',
        label: `Xóa ${sym.toUpperCase()} khỏi “${listName}”`,
        symbol: sym,
        watchlistName: listName,
      });
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    },
    [appendAssistantNote, logActivity],
  );

  const onWatchlistActionPress = useCallback(
    (action: CompanionWatchlistAction) => {
      if (action.type === 'create_watchlist') {
        setConfirmActions(null);
        const syms = action.symbols?.length
          ? action.symbols
          : action.symbol
            ? [action.symbol]
            : [];
        void executeCreateWatchlist(action.name, syms);
        return;
      }

      if (action.type === 'add_symbol' && action.watchlistId) {
        setConfirmActions(null);
        void executeAddSymbol(action.symbol, action.watchlistId);
        return;
      }

      if (action.type === 'remove_symbol' && action.watchlistId) {
        void executeRemoveSymbol(action.symbol, action.watchlistId);
        // Keep sheet open if more removes remain (multi-delete).
        setConfirmActions((prev) => {
          if (!prev?.length) return null;
          const next = prev.filter((item) => {
            if (item.type !== 'remove_symbol') return true;
            return !(
              item.symbol.toUpperCase() === action.symbol.toUpperCase() &&
              item.watchlistId === action.watchlistId
            );
          });
          return next.length ? next : null;
        });
        return;
      }

      setConfirmActions(null);
      if (action.type === 'add_symbol' || action.type === 'suggest_add_symbol') {
        setPickerSymbol(action.symbol.toUpperCase());
      }
    },
    [executeAddSymbol, executeCreateWatchlist, executeRemoveSymbol],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [stored, storedBond, storedActivities] = await Promise.all([
        loadCompanionChat(character.id),
        loadCompanionBond(character.id),
        loadCompanionActivities(character.id),
      ]);
      if (cancelled) return;

      setBond(storedBond);
      setActivities(storedActivities);

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
            content: buildWelcomeBackMessage(storedBond),
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
    if (!ready || busy) return;
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
    }, 400);
    return () => {
      if (persistTimer.current) clearTimeout(persistTimer.current);
    };
  }, [busy, character.id, messages, ready]);

  const scrollToEnd = useCallback((animated = false) => {
    requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated }));
  }, []);

  useEffect(() => {
    const showEvent = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const onShow = (e: KeyboardEvent) => {
      setKeyboardHeight(Platform.OS === 'ios' ? e.endCoordinates.height : 0);
      scrollToEnd(true);
    };
    const onHide = () => setKeyboardHeight(0);
    const subShow = Keyboard.addListener(showEvent, onShow);
    const subHide = Keyboard.addListener(hideEvent, onHide);
    return () => {
      subShow.remove();
      subHide.remove();
    };
  }, [scrollToEnd]);

  /** Coalesce streaming patches so FlatList isn't updated every ~70ms chunk. */
  const pendingPatch = useRef<{
    id: string;
    content: string;
    typing: boolean;
  } | null>(null);
  const patchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastPatchFlushAt = useRef(0);

  const flushAssistantPatch = useCallback(() => {
    patchTimer.current = null;
    const pending = pendingPatch.current;
    if (!pending) return;
    pendingPatch.current = null;
    lastPatchFlushAt.current = Date.now();
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === pending.id);
      if (idx < 0) return prev;
      const cur = prev[idx];
      if (cur.content === pending.content && cur.typing === pending.typing) {
        return prev;
      }
      const next = prev.slice();
      next[idx] = {
        ...cur,
        content: pending.content,
        typing: pending.typing,
      };
      return next;
    });
    const now = Date.now();
    if (now - scrollThrottle.current >= 280) {
      scrollThrottle.current = now;
      scrollToEnd(false);
    }
  }, [scrollToEnd]);

  const patchAssistant = useCallback(
    (assistantId: string, content: string, typing: boolean) => {
      pendingPatch.current = { id: assistantId, content, typing };
      // Final frames (typing=false) flush immediately for snappy finish.
      if (!typing) {
        if (patchTimer.current) {
          clearTimeout(patchTimer.current);
          patchTimer.current = null;
        }
        flushAssistantPatch();
        return;
      }
      const elapsed = Date.now() - lastPatchFlushAt.current;
      if (elapsed >= 100) {
        if (patchTimer.current) {
          clearTimeout(patchTimer.current);
          patchTimer.current = null;
        }
        flushAssistantPatch();
        return;
      }
      if (!patchTimer.current) {
        patchTimer.current = setTimeout(flushAssistantPatch, 100 - elapsed);
      }
    },
    [flushAssistantPatch],
  );

  useEffect(() => {
    return () => {
      if (patchTimer.current) clearTimeout(patchTimer.current);
    };
  }, []);
  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busy || !ready) return;

      setError(null);
      setBusy(true);
      setInput('');
      setConfirmActions(null);

      const now = Date.now();
      const userMsg: Bubble = {
        id: `u-${now}`,
        role: 'user',
        content: trimmed,
        ts: now,
      };

      const nextBond = evolveBond(
        bond,
        trimmed,
        symbol ? [symbol] : [],
        validSymbols,
      );
      setBond(nextBond);
      void saveCompanionBond(character.id, nextBond);

      const extractedNick = extractNicknameFromText(trimmed);
      if (
        extractedNick &&
        extractedNick !== (bond?.userNickname?.trim() || '')
      ) {
        void logActivity({
          type: 'set_nickname',
          label: `Vy sẽ gọi bạn là ${extractedNick}`,
        });
      }

      const history = messagesForApi(
        [...messages.filter((m) => !m.typing), userMsg].map((m) => ({
          role: m.role,
          content: m.content,
        })),
      );

      const assistantId = `a-${now}`;
      setMessages((prev) => [...prev, userMsg]);
      setPresence('reading');

      let fetchStatusTimer: ReturnType<typeof setTimeout> | null = null;
      try {
        await sleep(thinkingPauseMs());
        setPresence('fetching');
        setMessages((prev) => [
          ...prev,
          { id: assistantId, role: 'assistant', content: '', typing: true, ts: Date.now() },
        ]);

        // If enrichment/API is slow, reinforce the "đang lấy giá" status with haptic.
        fetchStatusTimer = setTimeout(() => {
          setPresence('fetching');
          void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        }, 650);

        const context = await buildCompanionContext(
          {
            screen,
            symbol,
            sessionLabel,
            watchlistSymbols,
            avgChange,
            characterId: character.id,
          },
          nextBond,
        );

        const result = await sendCompanionChat(history, context);
        if (fetchStatusTimer) clearTimeout(fetchStatusTimer);
        setPresence('typing');
        void Haptics.selectionAsync();

        const bubbles = (
          result.bubbles.length ? result.bubbles : [result.message]
        )
          .map((b) => b.trim())
          .filter(Boolean);
        const parts =
          bubbles.length > 0
            ? bubbles
            : ['Ối, tín hiệu hơi chậm. Bạn gửi lại giúp mình nhé.'];

        if (result.bondNotes?.length) {
          const enrichedBond = applyBondNotes(nextBond, result.bondNotes);
          setBond(enrichedBond);
          void saveCompanionBond(character.id, enrichedBond);
        }

        const pendingActions = result.actions?.length
          ? (result.actions as CompanionWatchlistAction[])
          : undefined;

        const first = parts[0];
        await revealText(first, (partial) => {
          patchAssistant(assistantId, partial, true);
        });
        patchAssistant(assistantId, first, false);

        for (let i = 1; i < parts.length; i += 1) {
          await sleep(betweenBubblesPauseMs());
          setPresence('typing');
          const followId = `${assistantId}-${i}`;
          setMessages((prev) => [
            ...prev,
            {
              id: followId,
              role: 'assistant',
              content: '',
              typing: true,
              ts: Date.now(),
            },
          ]);
          await sleep(420 + Math.floor(Math.random() * 280));
          const text = parts[i];
          await revealText(text, (partial) => {
            patchAssistant(followId, partial, true);
          });
          patchAssistant(followId, text, false);
        }

        if (pendingActions?.length) {
          const freshLists = await loadWatchlistsState();
          setWatchlistsState(freshLists);
          const expanded = expandWatchlistActions(
            pendingActions,
            freshLists.lists,
          );
          if (expanded.length) {
            setConfirmActions(expanded);
            void Haptics.notificationAsync(
              Haptics.NotificationFeedbackType.Warning,
            );
          }
        }

        void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      } catch (err) {
        if (fetchStatusTimer) clearTimeout(fetchStatusTimer);
        const raw = err instanceof Error ? err.message : 'Lỗi kết nối Companion';
        const api = getApiUrl();
        const hint404 =
          /\b404\b/i.test(raw)
            ? ' — Cloud API chưa có Companion; dùng API local hoặc deploy lại GCE.'
            : '';
        setError(`${raw}${hint404} (${api})`);
        setMessages((prev) => {
          const hasRow = prev.some((m) => m.id === assistantId);
          const failContent = /\b404\b/i.test(raw)
            ? 'Server cloud chưa có Companion. Chạy API local trên Mac hoặc deploy bản mới lên GCE nhé.'
            : 'Hmm, mình chưa kết nối được server. Kiểm tra API local giúp mình nhé.';
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
        void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      } finally {
        if (fetchStatusTimer) clearTimeout(fetchStatusTimer);
        setPresence('online');
        setBusy(false);
        scrollToEnd(true);
      }
    },
    [
      avgChange,
      bond,
      busy,
      character.id,
      logActivity,
      messages,
      patchAssistant,
      ready,
      screen,
      scrollToEnd,
      sessionLabel,
      symbol,
      validSymbols,
      watchlistSymbols,
    ],
  );

  useEffect(() => {
    if (!ready || seeded.current) return;
    seeded.current = true;
    setMessages((prev) => {
      const next = [...prev];
      if (seedAssistantMessage?.trim()) {
        next.push({
          id: `seed-a-${Date.now()}`,
          role: 'assistant',
          content: seedAssistantMessage.trim(),
          ts: Date.now(),
        });
      }
      return next;
    });
    if (seedUserMessage?.trim()) {
      void send(seedUserMessage.trim());
    }
  }, [ready, seedAssistantMessage, seedUserMessage, send]);

  const renderItem = useCallback(
    ({ item }: { item: Bubble }) => (
      <CompanionChatBubble
        item={item}
        character={character}
        onPressAvatar={openProfile}
        linkableSymbols={linkableSymbols}
        onPressSymbol={openSymbol}
      />
    ),
    [character, linkableSymbols, openProfile, openSymbol],
  );

  const onContentSizeChange = useCallback(() => {
    // Streaming already scrolls from coalesced patches — avoid VirtualizedList storms.
    if (busy) return;
    scrollToEnd(true);
  }, [busy, scrollToEnd]);

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
        onResetSession={resetSession}
        nickname={bond?.userNickname ?? ''}
        onSaveNickname={saveNickname}
        activities={activities}
      />

      <View style={[styles.flex, { paddingBottom: keyboardHeight }]}>
        <FlatList
          ref={listRef}
          style={styles.flex}
          data={messages}
          keyExtractor={keyExtractor}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="interactive"
          removeClippedSubviews
          initialNumToRender={10}
          maxToRenderPerBatch={4}
          updateCellsBatchingPeriod={80}
          windowSize={5}
          onContentSizeChange={onContentSizeChange}
          renderItem={renderItem}
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
            onFocus={() => scrollToEnd(true)}
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

      <CompanionWatchlistConfirmSheet
        visible={confirmActions != null && confirmActions.length > 0}
        actions={confirmActions ?? []}
        accent={character.accent}
        onConfirm={onWatchlistActionPress}
        onClose={() => setConfirmActions(null)}
      />

      <CompanionWatchlistPickerSheet
        visible={pickerSymbol != null}
        symbol={pickerSymbol ?? ''}
        lists={watchlistsState?.lists ?? []}
        activeId={watchlistsState?.activeId ?? ''}
        onClose={() => setPickerSymbol(null)}
        onSelectList={(id) => {
          if (!pickerSymbol) return;
          void executeAddSymbol(pickerSymbol, id);
          setPickerSymbol(null);
        }}
        onCreateList={(name) => {
          void executeCreateWatchlist(
            name,
            pickerSymbol ? [pickerSymbol] : undefined,
          );
          setPickerSymbol(null);
        }}
      />
    </View>
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function keyExtractor(item: Bubble): string {
  return item.id;
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
