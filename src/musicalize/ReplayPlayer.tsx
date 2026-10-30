import React, { useEffect, useRef, useState } from 'react';
import { setAudioModeAsync, useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { shouldArmFinish, shouldResumePlay } from './seek';

export type SeekCommand = { id: number; seconds: number };

type Props = {
  url: string;
  startSec: number;
  wantPlay: boolean;
  seek: SeekCommand | null;
  onTime: (seconds: number) => void;
  onEnded: () => void;
  onAudible: () => void;
  onError: (message: string) => void;
  onDuration: (seconds: number) => void;
};

export function ReplayPlayer({
  url,
  startSec,
  wantPlay,
  seek,
  onTime,
  onEnded,
  onAudible,
  onError,
  onDuration,
}: Props) {
  const player = useAudioPlayer(url, { updateInterval: 80, downloadFirst: true });
  const status = useAudioPlayerStatus(player);
  const booted = useRef(false);
  const [ready, setReady] = useState(false);
  const ended = useRef(false);
  const armFinish = useRef(true);
  const appliedSeek = useRef(0);
  const pending = useRef<number | null>(startSec > 0.05 ? startSec : null);
  const seekRef = useRef(seek);
  const wantPlayRef = useRef(wantPlay);
  const onTimeRef = useRef(onTime);
  const onEndedRef = useRef(onEnded);
  const onAudibleRef = useRef(onAudible);
  const onErrorRef = useRef(onError);
  const onDurationRef = useRef(onDuration);
  seekRef.current = seek;
  wantPlayRef.current = wantPlay;
  onTimeRef.current = onTime;
  onEndedRef.current = onEnded;
  onAudibleRef.current = onAudible;
  onErrorRef.current = onError;
  onDurationRef.current = onDuration;

  useEffect(() => {
    if (status.error) onErrorRef.current('Máy chủ chưa soạn được nhạc.');
  }, [status.error]);

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
      }
      const queued = seekRef.current;
      if (queued && queued.id !== appliedSeek.current) {
        appliedSeek.current = queued.id;
        pending.current = queued.seconds;
        armFinish.current = false;
        ended.current = false;
        await player.seekTo(queued.seconds);
      }
      if (cancelled || booted.current) return;
      booted.current = true;
      setReady(true);
      onAudibleRef.current();
      if (wantPlayRef.current) player.play();
    })();
    return () => {
      cancelled = true;
    };
  }, [player, startSec, status.error, status.isLoaded]);

  useEffect(() => {
    if (!booted.current || !status.isLoaded || !seek || seek.id === appliedSeek.current) return;
    appliedSeek.current = seek.id;
    pending.current = seek.seconds;
    ended.current = false;
    armFinish.current = false;
    void player.seekTo(seek.seconds);
  }, [player, ready, seek, status.isLoaded]);

  useEffect(() => {
    if (!booted.current || !status.isLoaded) return;
    if (
      shouldResumePlay({
        wantPlay,
        playing: status.playing,
        didJustFinish: status.didJustFinish,
        ended: ended.current,
      })
    ) {
      player.play();
    }
    if (!wantPlay && status.playing) player.pause();
  }, [player, status.didJustFinish, status.isLoaded, status.playing, wantPlay]);

  useEffect(() => {
    if (!status.isLoaded) return;
    const duration = status.duration > 0 ? status.duration : 0;
    if (duration > 0) onDurationRef.current(duration);
    if (pending.current != null && Math.abs(status.currentTime - pending.current) <= 0.45) {
      pending.current = null;
    }
    const shown = pending.current != null ? pending.current : status.currentTime;
    onTimeRef.current(shown);
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
      onEndedRef.current();
    }
  }, [status.currentTime, status.didJustFinish, status.duration, status.isLoaded]);

  return null;
}
