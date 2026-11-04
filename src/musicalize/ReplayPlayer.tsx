import React, { useCallback, useEffect, useRef, useState } from 'react';
import { setAudioModeAsync, useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import {
  completedSlot,
  loadedSlot,
  resumedSlot,
  shouldAnnounceAudible,
  type PlayerSlot as Slot,
} from './playerState';
import { shouldArmFinish, shouldResumePlay } from './seek';

export type SeekCommand = { id: number; seconds: number };

type SlotName = 'a' | 'b';

type Slots = Record<SlotName, Slot>;

export type ReplayPlayerProps = {
  url: string;
  startSec: number;
  wantPlay: boolean;
  seek: SeekCommand | null;
  muted?: boolean;
  /** Crossfade length for an A/B or movement switch. */
  crossfadeMs?: number;
  onTime: (seconds: number) => void;
  onEnded: () => void;
  onAudible: () => void;
  onError: (message: string) => void;
  onDuration: (seconds: number) => void;
  /** The file exists and is loaded: safe to ask the plan for its peaks. */
  onReady?: () => void;
  /** True while an incoming side is loading. */
  onPreparingChange?: (preparing: boolean) => void;
  /** The incoming file could not be prepared; the current side keeps playing. */
  onSwitchFailed?: (message: string) => void;
};

const EMPTY_SLOTS: Slots = {
  a: { url: null, startSec: 0, play: false, gain: 0 },
  b: { url: null, startSec: 0, play: false, gain: 0 },
};

const FADE_TICK_MS = 16;
const DEFAULT_CROSSFADE_MS = 120;
const SWITCH_TIMEOUT_MS = 15_000;

const other = (slot: SlotName): SlotName => (slot === 'a' ? 'b' : 'a');

type SlotPlayerProps = {
  slot: SlotName;
  url: string | null;
  startSec: number;
  play: boolean;
  gain: number;
  muted: boolean;
  active: boolean;
  seek: SeekCommand | null;
  onReady: (slot: SlotName) => void;
  onTime: (slot: SlotName, seconds: number) => void;
  onEnded: (slot: SlotName) => void;
  onError: (slot: SlotName) => void;
  onDuration: (slot: SlotName, seconds: number) => void;
};

function SlotPlayer({
  slot,
  url,
  startSec,
  play,
  gain,
  muted,
  active,
  seek,
  onReady,
  onTime,
  onEnded,
  onError,
  onDuration,
}: SlotPlayerProps) {
  const player = useAudioPlayer(url, { updateInterval: 80, downloadFirst: true });
  const status = useAudioPlayerStatus(player);
  const booted = useRef(false);
  const [bootTick, setBootTick] = useState(0);
  const readyNotified = useRef(false);
  const pending = useRef<number | null>(startSec > 0.05 ? startSec : null);
  const ended = useRef(false);
  const armFinish = useRef(true);
  const appliedSeek = useRef(0);
  const wasActive = useRef(active);
  const playRef = useRef(play);
  const onTimeRef = useRef(onTime);
  const onEndedRef = useRef(onEnded);
  const onErrorRef = useRef(onError);
  const onDurationRef = useRef(onDuration);
  const onReadyRef = useRef(onReady);
  playRef.current = play;
  onTimeRef.current = onTime;
  onEndedRef.current = onEnded;
  onErrorRef.current = onError;
  onDurationRef.current = onDuration;
  onReadyRef.current = onReady;

  useEffect(() => {
    if (!status.isLoaded || booted.current || status.error) return;
    let cancelled = false;
    void (async () => {
      try {
        await setAudioModeAsync({ playsInSilentMode: true });
      } catch {
        // Web can play without a native audio mode.
      }
      if (cancelled || booted.current) return;
      if (startSec > 0.05) {
        pending.current = startSec;
        await player.seekTo(startSec);
        if (cancelled) return;
      }
      booted.current = true;
      setBootTick((tick) => tick + 1);
      if (playRef.current) player.play();
    })();
    return () => {
      cancelled = true;
    };
  }, [player, startSec, status.error, status.isLoaded]);

  // Wait for a real duration: the server may still be writing the file even
  // after the URL is loaded. The parent starts the fade only after this.
  useEffect(() => {
    if (!booted.current || !status.isLoaded || status.duration <= 0) return;
    if (readyNotified.current) return;
    readyNotified.current = true;
    onReadyRef.current(slot);
  }, [bootTick, slot, status.currentTime, status.duration, status.isLoaded]);

  useEffect(() => {
    if (active && !wasActive.current) {
      // A slot that just became audible must not replay the previous side's
      // last explicit seek. Only a newer command should move it.
      appliedSeek.current = seek?.id ?? appliedSeek.current;
    }
    wasActive.current = active;
    if (!active || !booted.current || !status.isLoaded || !seek) return;
    if (seek.id === appliedSeek.current) return;
    appliedSeek.current = seek.id;
    pending.current = seek.seconds;
    ended.current = false;
    armFinish.current = false;
    void player.seekTo(seek.seconds);
  }, [active, player, seek, status.isLoaded]);

  useEffect(() => {
    if (!booted.current || !status.isLoaded) return;
    if (
      shouldResumePlay({
        wantPlay: play,
        playing: status.playing,
        didJustFinish: status.didJustFinish,
        ended: ended.current,
      })
    ) {
      player.play();
    }
    if (!play && status.playing) player.pause();
  }, [play, player, status.didJustFinish, status.isLoaded, status.playing]);

  useEffect(() => {
    if (!status.isLoaded) return;
    player.volume = muted ? 0 : Math.max(0, Math.min(1, gain));
  }, [gain, muted, player, status.isLoaded]);

  useEffect(() => {
    if (!status.isLoaded) return;
    const duration = status.duration > 0 ? status.duration : 0;
    if (active) {
      if (duration > 0) onDurationRef.current(slot, duration);
      if (pending.current != null && Math.abs(status.currentTime - pending.current) <= 0.45) {
        pending.current = null;
      }
      const shown = pending.current != null ? pending.current : status.currentTime;
      if (booted.current) onTimeRef.current(slot, shown);
      if (
        shouldArmFinish({
          didJustFinish: status.didJustFinish,
          currentTime: status.currentTime,
          durationSec: duration,
        })
      ) {
        armFinish.current = true;
      }
      const guarding = pending.current != null;
      if (status.didJustFinish && armFinish.current && !ended.current && !guarding) {
        ended.current = true;
        onEndedRef.current(slot);
      }
    }
  }, [active, slot, status.currentTime, status.didJustFinish, status.duration, status.isLoaded]);

  useEffect(() => {
    if (status.error) onErrorRef.current(slot);
  }, [slot, status.error]);

  return null;
}

export function ReplayPlayer({
  url,
  startSec,
  wantPlay,
  seek,
  muted = false,
  crossfadeMs = DEFAULT_CROSSFADE_MS,
  onTime,
  onEnded,
  onAudible,
  onError,
  onDuration,
  onReady,
  onPreparingChange,
  onSwitchFailed,
}: ReplayPlayerProps) {
  const [slots, setSlots] = useState<Slots>(EMPTY_SLOTS);
  const [loadSeq, setLoadSeq] = useState<Record<SlotName, number>>({ a: 0, b: 0 });
  const [active, setActive] = useState<SlotName>('a');
  const activeRef = useRef<SlotName>('a');
  const slotsRef = useRef(slots);
  const startSecRef = useRef(startSec);
  const wantPlayRef = useRef(wantPlay);
  slotsRef.current = slots;
  startSecRef.current = startSec;
  wantPlayRef.current = wantPlay;

  const pending = useRef<{ from: SlotName; to: SlotName } | null>(null);
  const ready = useRef<Record<SlotName, boolean>>({ a: false, b: false });
  const fadeTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const switchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onTimeRef = useRef(onTime);
  const onEndedRef = useRef(onEnded);
  const onAudibleRef = useRef(onAudible);
  const onErrorRef = useRef(onError);
  const onDurationRef = useRef(onDuration);
  const onReadyRef = useRef(onReady);
  const onPreparingRef = useRef(onPreparingChange);
  const onSwitchFailedRef = useRef(onSwitchFailed);
  onTimeRef.current = onTime;
  onEndedRef.current = onEnded;
  onAudibleRef.current = onAudible;
  onErrorRef.current = onError;
  onDurationRef.current = onDuration;
  onReadyRef.current = onReady;
  onPreparingRef.current = onPreparingChange;
  onSwitchFailedRef.current = onSwitchFailed;

  const clearFade = useCallback(() => {
    if (fadeTimer.current != null) {
      clearInterval(fadeTimer.current);
      fadeTimer.current = null;
    }
  }, []);

  const clearSwitchTimer = useCallback(() => {
    if (switchTimer.current != null) {
      clearTimeout(switchTimer.current);
      switchTimer.current = null;
    }
  }, []);

  const cancelPending = useCallback(() => {
    clearFade();
    clearSwitchTimer();
    const current = pending.current;
    pending.current = null;
    if (current) {
      ready.current[current.to] = false;
      const from = activeRef.current;
      setSlots((prev) => ({
        ...prev,
        [from]: { ...prev[from], gain: 1 },
        [current.to]: { ...prev[current.to], play: false, gain: 0 },
      }));
    }
    onPreparingRef.current?.(false);
  }, [clearFade, clearSwitchTimer]);

  const failSwitch = useCallback(
    (target: SlotName) => {
      const current = pending.current;
      if (!current || current.to !== target) return;
      cancelPending();
      onSwitchFailedRef.current?.('Không chuẩn bị được bản kia. Vẫn đang phát bản hiện tại.');
    },
    [cancelPending],
  );

  const finishSwitch = useCallback(
    (to: SlotName) => {
      clearFade();
      clearSwitchTimer();
      const from = activeRef.current;
      pending.current = null;
      activeRef.current = to;
      setActive(to);
      const play = wantPlayRef.current;
      setSlots((prev) => ({
        ...prev,
        [from]: { ...prev[from], play: false, gain: 0 },
        [to]: completedSlot(prev[to], play),
      }));
      onPreparingRef.current?.(false);
      if (play) onAudibleRef.current();
      onReadyRef.current?.();
    },
    [clearFade, clearSwitchTimer],
  );

  const startFade = useCallback(
    (from: SlotName, to: SlotName) => {
      clearFade();
      const duration = Math.max(0, crossfadeMs);
      if (duration === 0) {
        finishSwitch(to);
        return;
      }
      const started = Date.now();
      fadeTimer.current = setInterval(() => {
        const progress = Math.min(1, (Date.now() - started) / duration);
        setSlots((prev) => ({
          ...prev,
          [from]: { ...prev[from], gain: 1 - progress },
          [to]: { ...prev[to], play: true, gain: progress },
        }));
        if (progress >= 1) finishSwitch(to);
      }, FADE_TICK_MS);
    },
    [clearFade, crossfadeMs, finishSwitch],
  );

  const handleReady = useCallback(
    (slot: SlotName) => {
      if (ready.current[slot]) return;
      ready.current[slot] = true;
      const current = pending.current;
      if (current && current.to === slot) {
        if (!wantPlayRef.current) {
          finishSwitch(slot);
          return;
        }
        setSlots((prev) => ({
          ...prev,
          [slot]: { ...prev[slot], play: true, gain: 0 },
        }));
        startFade(current.from, current.to);
        return;
      }
      if (slot === activeRef.current) {
        onPreparingRef.current?.(false);
        onReadyRef.current?.();
        if (wantPlayRef.current) onAudibleRef.current();
      }
    },
    [finishSwitch, startFade],
  );

  // Start a source on the idle slot. The active slot keeps playing until the
  // new file has been loaded, seeked and reported ready.
  useEffect(() => {
    if (!url) return;
    const currentActive = activeRef.current;
    const current = slotsRef.current[currentActive];
    if (current.url === url) {
      cancelPending();
      return;
    }
    if (!current.url && !slotsRef.current[other(currentActive)].url) {
      setSlots((prev) => ({
        ...prev,
        [currentActive]: loadedSlot(url, startSecRef.current, wantPlayRef.current),
      }));
      return;
    }
    cancelPending();
    const target = other(currentActive);
    ready.current[target] = false;
    setSlots((prev) => ({
      ...prev,
      [target]: { url, startSec: startSecRef.current, play: false, gain: 0 },
    }));
    // Remount the idle slot even when it holds the same URL. It is not
    // audible, so this is the cheapest way to get a fresh seek to `startSec`.
    setLoadSeq((prev) => ({ ...prev, [target]: prev[target] + 1 }));
    pending.current = { from: currentActive, to: target };
    onPreparingRef.current?.(true);
    clearSwitchTimer();
    switchTimer.current = setTimeout(() => failSwitch(target), SWITCH_TIMEOUT_MS);
  }, [cancelPending, clearSwitchTimer, failSwitch, url]);

  // Keep the pending target's start position current (the room can update it
  // after the URL state lands).
  useEffect(() => {
    setSlots((prev) => {
      const target =
        prev[activeRef.current].url === url
          ? activeRef.current
          : prev[other(activeRef.current)].url === url
            ? other(activeRef.current)
            : null;
      if (!target || prev[target].startSec === startSec) return prev;
      return { ...prev, [target]: { ...prev[target], startSec } };
    });
  }, [startSec, url]);

  useEffect(() => {
    if (!wantPlay) {
      cancelPending();
      setSlots((prev) => ({
        a: { ...prev.a, play: false },
        b: { ...prev.b, play: false },
      }));
      return;
    }
    const current = slotsRef.current[activeRef.current];
    if (!current.url) return;
    setSlots((prev) => ({
      ...prev,
      [activeRef.current]: resumedSlot(prev[activeRef.current]),
    }));
    if (shouldAnnounceAudible(ready.current[activeRef.current], wantPlay)) {
      onAudibleRef.current();
    }
  }, [cancelPending, wantPlay]);

  useEffect(() => {
    return () => {
      clearFade();
      clearSwitchTimer();
    };
  }, [clearFade, clearSwitchTimer]);

  const handleTime = useCallback((slot: SlotName, seconds: number) => {
    if (slot === activeRef.current) onTimeRef.current(seconds);
  }, []);
  const handleDuration = useCallback((slot: SlotName, seconds: number) => {
    if (slot === activeRef.current) onDurationRef.current(seconds);
  }, []);
  const handleEnded = useCallback((slot: SlotName) => {
    // The outgoing side may finish while the incoming side is being prepared.
    // Advancing now would use the incoming plan's index for the old file.
    if (pending.current) return;
    if (slot === activeRef.current) onEndedRef.current();
  }, []);
  const handleError = useCallback(
    (slot: SlotName) => {
      if (slot === activeRef.current) {
        onErrorRef.current('Máy chủ chưa soạn được nhạc.');
        return;
      }
      failSwitch(slot);
    },
    [failSwitch],
  );

  return (
    <>
      <SlotPlayer
        key={`a:${slots.a.url ?? 'empty'}:${loadSeq.a}`}
        slot="a"
        url={slots.a.url}
        startSec={slots.a.startSec}
        play={slots.a.play}
        gain={slots.a.gain}
        muted={muted}
        active={active === 'a'}
        seek={active === 'a' ? seek : null}
        onReady={handleReady}
        onTime={handleTime}
        onEnded={handleEnded}
        onError={handleError}
        onDuration={handleDuration}
      />
      <SlotPlayer
        key={`b:${slots.b.url ?? 'empty'}:${loadSeq.b}`}
        slot="b"
        url={slots.b.url}
        startSec={slots.b.startSec}
        play={slots.b.play}
        gain={slots.b.gain}
        muted={muted}
        active={active === 'b'}
        seek={active === 'b' ? seek : null}
        onReady={handleReady}
        onTime={handleTime}
        onEnded={handleEnded}
        onError={handleError}
        onDuration={handleDuration}
      />
    </>
  );
}
