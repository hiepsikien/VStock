import React, { useCallback, useEffect, useRef, useState } from 'react';
import { fetchSonifySymbols, getApiBaseUrl, type SonifyTapeSymbol } from '../api/client';
import { Controls } from './Controls';
import type { StreamVariant } from './labels';
import { LiveSynth, liveStageMessage, type LiveSocketMessage } from './liveSynth';
import { liveListRows, type LiveListRow } from './liveRows';
import { RoomFrame } from './RoomFrame';
import { sonifySocketUrl } from './seek';
import { Stage } from './Stage';
import { SymbolColumn } from './SymbolColumn';

type Props = {
  wide: boolean;
  onMode: (mode: 'replay' | 'live') => void;
};

type SocketLike = {
  close: () => void;
  onmessage: ((event: { data: string }) => void) | null;
  onclose: ((event: { code: number }) => void) | null;
};

const DEFAULT_ROWS = liveListRows([{ symbol: 'BTCUSDT', base: 'BTC' }]);

export function LiveRoom({ wide, onMode }: Props) {
  const [rows, setRows] = useState<LiveListRow[]>(DEFAULT_ROWS);
  const [selectedKey, setSelectedKey] = useState('live:BTCUSDT');
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [source, setSource] = useState<'live' | 'history'>('live');
  const [variant, setVariant] = useState<StreamVariant>('symphony');
  const [playing, setPlaying] = useState(false);
  const [prices, setPrices] = useState<number[]>([]);
  const [banner, setBanner] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const session = useRef(0);
  const socket = useRef<SocketLike | null>(null);
  const synth = useRef<LiveSynth | null>(null);
  const playingRef = useRef(false);
  playingRef.current = playing;

  const stop = useCallback(() => {
    socket.current?.close();
    socket.current = null;
    synth.current?.stop();
    synth.current = null;
  }, []);

  useEffect(() => () => {
    session.current += 1;
    stop();
  }, [stop]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const symbols = await fetchSonifySymbols();
        if (cancelled || !symbols.length) return;
        const next = liveListRows(symbols.map(toTape));
        setRows(next);
        setSelectedKey((current) => (next.some((row) => row.key === current) ? current : next[0].key));
      } catch {
        if (!cancelled) setBanner('Không tải được danh sách đài.');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const start = useCallback(
    async (next: { symbol: string; source: 'live' | 'history'; variant: StreamVariant }) => {
      const mine = ++session.current;
      stop();
      setPrices([]);
      setBanner(null);
      setStatus('Đang nối…');
      setPlaying(true);
      const engine = new LiveSynth();
      synth.current = engine;
      try {
        await engine.start();
      } catch (err) {
        if (mine !== session.current) return;
        setPlaying(false);
        setBanner(err instanceof Error ? err.message : 'Không mở được tiếng.');
        return;
      }
      if (mine !== session.current) {
        engine.stop();
        return;
      }
      const Ctor = (globalThis as { WebSocket?: new (url: string) => SocketLike }).WebSocket;
      if (!Ctor) {
        setPlaying(false);
        setBanner('Trình duyệt không mở được đài.');
        engine.stop();
        return;
      }
      const opened = new Ctor(
        sonifySocketUrl(getApiBaseUrl(), {
          variant: next.variant,
          source: next.source,
          symbol: next.symbol,
        }),
      );
      if (mine !== session.current) {
        opened.close();
        return;
      }
      socket.current = opened;
      let announced = false;
      opened.onmessage = (event) => {
        if (mine !== session.current) return;
        let message: LiveSocketMessage;
        try {
          message = JSON.parse(event.data) as LiveSocketMessage;
        } catch {
          return;
        }
        if (message.type === 'hello' && message.bucket_ms) engine.setStep(message.bucket_ms / 1000);
        const line = liveStageMessage(message, next.source, message.type === 'hello' && message.symbol ? message.symbol : next.symbol);
        if (message.type === 'error') {
          announced = true;
          setBanner(line);
          setStatus(null);
          setPlaying(false);
          return;
        }
        if (message.type === 'hello' || message.type === 'end') {
          if (message.type === 'end') announced = true;
          setStatus(line);
          if (message.type === 'end') setPlaying(false);
          return;
        }
        if (message.type !== 'note') return;
        engine.schedule(message);
        if (typeof message.price === 'number' && Number.isFinite(message.price)) {
          const price = message.price;
          setPrices((existing) => {
            const kept = existing.length >= 360 ? existing.slice(existing.length - 359) : existing;
            return [...kept, price];
          });
        }
      };
      opened.onclose = (event) => {
        if (mine !== session.current) return;
        setPlaying(false);
        if (!announced && event.code === 1008) {
          setBanner('Đài cần trang và API cùng một host.');
        }
      };
    },
    [stop],
  );

  const choose = (row: LiveListRow) => {
    setSelectedKey(row.key);
    setSymbol(row.symbol);
    setSource(row.source);
    setPrices([]);
    setBanner(null);
    setStatus(null);
    if (playingRef.current) {
      void start({ symbol: row.symbol, source: row.source, variant });
    }
  };

  const chooseVariant = (next: StreamVariant) => {
    setVariant(next);
    if (playingRef.current) void start({ symbol, source, variant: next });
  };

  const cursor = prices.length > 1 ? prices.length - 1 : null;

  return (
    <RoomFrame
      wide={wide}
      chooser={<SymbolColumn mode="live" onMode={onMode} rows={rows} selectedKey={selectedKey} onRow={choose} />}
      stage={
        <Stage
          prices={prices}
          cursorIndex={cursor}
          cursorLabel={null}
          dimUnplayed={false}
          identity={
            prices.length > 1 ? null : source === 'history' ? `${symbol} · đoạn ~90s` : symbol
          }
          banner={banner ?? (!playing && prices.length < 2 ? status : null)}
          seekable={false}
        />
      }
      controls={
        <Controls
          mode="live"
          variant={variant}
          playing={playing}
          onVariant={chooseVariant}
          onPlay={() => void start({ symbol, source, variant })}
          onPause={() => {
            session.current += 1;
            stop();
            setPlaying(false);
          }}
          status={playing ? status : null}
        />
      }
    />
  );
}

function toTape(symbol: SonifyTapeSymbol): { symbol: string; base: string } {
  return { symbol: symbol.symbol, base: symbol.base || symbol.symbol.replace(/USDT$/, '') };
}
