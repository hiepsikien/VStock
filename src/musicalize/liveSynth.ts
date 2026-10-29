/** Web Audio synth ported from backend/app/sonify/player.html. No MuseScore, no guitar. */

export type LiveVoice = {
  role: string;
  midi: number;
  dur_ms: number;
  velocity: number;
  wave: string;
};

export type LiveNote = {
  seq: number;
  swing?: boolean;
  velocity?: number;
  variant?: string;
  voices?: LiveVoice[];
  price?: number;
  midi?: number | null;
};

const ROLE_GAIN: Record<string, number> = {
  violin: 0.22,
  cello: 0.16,
  piano: 0.1,
  fill: 0.1,
  flute: 0.12,
  sax: 0.16,
  rhodes: 0.09,
  vibe: 0.11,
  bass: 0.34,
  arp: 0.14,
  pad: 0.07,
  pulse: 0.1,
  stab: 0.12,
  bell: 0.11,
  drone: 0.2,
  halo: 0.09,
  glass: 0.17,
  swell: 0.13,
  sub: 0.28,
  shimmer: 0.11,
};

const AMBIENT_ROLES = new Set(['drone', 'halo', 'glass', 'swell', 'sub', 'shimmer']);

type OscKind = 'sine' | 'square' | 'sawtooth' | 'triangle';

type GainParam = {
  value: number;
  setValueAtTime: (value: number, time: number) => void;
  exponentialRampToValueAtTime: (value: number, time: number) => void;
};

type GainLike = { gain: GainParam; connect: (dest: unknown) => void };
type OscLike = {
  type: OscKind;
  frequency: { value: number };
  connect: (dest: unknown) => void;
  start: (when: number) => void;
  stop: (when: number) => void;
};
type FilterLike = {
  type: string;
  frequency: GainParam;
  connect: (dest: unknown) => void;
};
type DelayLike = {
  delayTime: { value: number };
  connect: (dest: unknown) => void;
};

type AudioContextLike = {
  currentTime: number;
  state: string;
  destination: unknown;
  resume: () => Promise<void>;
  close: () => Promise<void>;
  createGain: () => GainLike;
  createOscillator: () => OscLike;
  createDelay?: (max: number) => DelayLike;
  createBiquadFilter?: () => FilterLike;
};

type SpaceBus = { input: GainLike; filter: FilterLike };

function oscillatorType(wave: string): OscKind {
  if (wave === 'square' || wave === 'sawtooth' || wave === 'triangle' || wave === 'sine') return wave;
  return 'sine';
}

export function whenFor(origin: number, seq: number, step: number, swing: boolean): number {
  if (!swing) return origin + seq * step;
  const beat = Math.floor(seq / 4);
  const pos = seq % 4;
  const beatStart = origin + beat * step * 4;
  const long = step * 4 * (2 / 3);
  const short = step * 4 - long;
  if (pos < 2) return beatStart + (pos * long) / 2;
  return beatStart + long + ((pos - 2) * short) / 2;
}

function createSpaceBus(ctx: AudioContextLike, master: GainLike): SpaceBus | null {
  if (typeof ctx.createDelay !== 'function' || typeof ctx.createBiquadFilter !== 'function') return null;
  const input = ctx.createGain();
  const filter = ctx.createBiquadFilter();
  const delayL = ctx.createDelay(2.0);
  const delayR = ctx.createDelay(2.0);
  const fbL = ctx.createGain();
  const fbR = ctx.createGain();
  const wet = ctx.createGain();
  filter.type = 'lowpass';
  filter.frequency.value = 1800;
  delayL.delayTime.value = 0.31;
  delayR.delayTime.value = 0.47;
  fbL.gain.value = 0.42;
  fbR.gain.value = 0.4;
  wet.gain.value = 0.36;
  input.connect(filter);
  filter.connect(delayL);
  filter.connect(delayR);
  delayL.connect(fbL);
  fbL.connect(delayR);
  delayR.connect(fbR);
  fbR.connect(delayL);
  delayL.connect(wet);
  delayR.connect(wet);
  wet.connect(master);
  return { input, filter };
}

function tone(
  ctx: AudioContextLike,
  master: GainLike,
  space: SpaceBus | null,
  midi: number,
  when: number,
  dur: number,
  velocity: number,
  type: string,
  role: string,
) {
  const freq = 440 * 2 ** ((midi - 69) / 12);
  const scale = ROLE_GAIN[role] || 0.12;
  const peak = Math.max(0.0008, (velocity / 127) * scale);
  const isAmbient = AMBIENT_ROLES.has(role);
  const attack =
    role === 'halo' || role === 'drone' || role === 'swell' ? 0.22 : role === 'glass' || role === 'shimmer' ? 0.045 : 0.012;
  const tail = isAmbient ? Math.max(0.4, dur * 1.35) : Math.max(0.05, dur);

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = oscillatorType(type);
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0.0001, when);
  gain.gain.exponentialRampToValueAtTime(peak, when + attack);
  gain.gain.exponentialRampToValueAtTime(0.0001, when + tail);
  osc.connect(gain);
  gain.connect(master);
  if (space && isAmbient) gain.connect(space.input);
  osc.start(when);
  osc.stop(when + tail + 0.05);

  if (isAmbient && (role === 'halo' || role === 'swell' || role === 'glass')) {
    const detuned = ctx.createOscillator();
    const shimmerGain = ctx.createGain();
    detuned.type = 'sine';
    detuned.frequency.value = freq * 1.0028;
    shimmerGain.gain.setValueAtTime(0.0001, when);
    shimmerGain.gain.exponentialRampToValueAtTime(peak * 0.55, when + attack * 1.2);
    shimmerGain.gain.exponentialRampToValueAtTime(0.0001, when + tail * 1.15);
    detuned.connect(shimmerGain);
    shimmerGain.connect(space ? space.input : master);
    detuned.start(when);
    detuned.stop(when + tail * 1.15 + 0.05);
  }
}

type AudioWindow = {
  AudioContext?: new () => AudioContextLike;
  webkitAudioContext?: new () => AudioContextLike;
};

function audioContextCtor(): (new () => AudioContextLike) | null {
  if (typeof window === 'undefined') return null;
  const host = window as unknown as AudioWindow;
  return host.AudioContext ?? host.webkitAudioContext ?? null;
}

export class LiveSynth {
  private ctx: AudioContextLike | null = null;
  private master: GainLike | null = null;
  private space: SpaceBus | null = null;
  private origin: number | null = null;
  private step = 0.25;
  private closed = false;

  async start(): Promise<void> {
    this.stop();
    this.closed = false;
    const Ctor = audioContextCtor();
    if (!Ctor) throw new Error('Trình duyệt không mở được tiếng.');
    const ctx = new Ctor();
    const master = ctx.createGain();
    master.gain.value = 0.55;
    master.connect(ctx.destination);
    this.ctx = ctx;
    this.master = master;
    this.space = createSpaceBus(ctx, master);
    this.origin = null;
    await ctx.resume();
    if (this.closed) this.stop();
  }

  setStep(seconds: number) {
    if (seconds > 0) this.step = seconds;
  }

  schedule(note: LiveNote) {
    const ctx = this.ctx;
    const master = this.master;
    if (!ctx || !master || this.closed) return;
    const now = ctx.currentTime;
    const swing = Boolean(note.swing);
    if (this.origin === null) this.origin = now + 0.3 - whenFor(0, note.seq, this.step, swing);
    let when = whenFor(this.origin, note.seq, this.step, swing);
    if (when < now + 0.02) {
      this.origin += now + 0.05 - when;
      when = now + 0.05;
    }
    if (this.space) {
      const velocity = note.velocity ?? 60;
      const cutoff = 900 + Math.max(0, Math.min(1, (velocity - 36) / 72)) * 3200;
      this.space.filter.frequency.setValueAtTime(cutoff, when);
    }
    for (const voice of note.voices ?? []) {
      tone(
        ctx,
        master,
        this.space,
        voice.midi,
        when,
        voice.dur_ms / 1000,
        voice.velocity,
        voice.wave,
        voice.role,
      );
    }
  }

  stop() {
    this.closed = true;
    const ctx = this.ctx;
    this.ctx = null;
    this.master = null;
    this.space = null;
    this.origin = null;
    if (ctx && ctx.state !== 'closed') void ctx.close().catch(() => undefined);
  }
}

export type LiveSocketMessage =
  | { type: 'hello'; bucket_ms?: number; variant?: string; source?: string; symbol?: string; text?: string }
  | { type: 'error'; text?: string }
  | { type: 'end'; notes?: number }
  | ({ type: 'note' } & LiveNote);

export function liveStageMessage(message: LiveSocketMessage, source: 'live' | 'history', symbol: string): string | null {
  if (message.type === 'error') return message.text || 'Không nối được đài.';
  if (message.type === 'hello') {
    return source === 'live' ? `Đang phát · ${symbol}` : `Đoạn lịch sử · ${symbol}`;
  }
  if (message.type === 'end') {
    return source === 'live' ? 'Dòng đã dừng.' : `Hết đoạn${message.notes != null ? `, ${message.notes} nốt` : ''}.`;
  }
  return null;
}
