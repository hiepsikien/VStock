"""Open-ended sonification of a 250 ms price tape.

The closed recap in render.py plans thirty bars from a finished session.
This machine never looks ahead: a bucket closes into one note, and appending
later trades does not rewrite notes that have already been emitted.

One wall-clock second is four sixteenth notes at 60 BPM. A chord is chosen
only on the downbeat of each 4/4 bar, from the Markov row of the current
chord tilted by the regime of the last twenty one-second closes.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass

from app.sonify.chords import REGIME_BIAS, TRANSITIONS, Chord, Regime, tonic
from app.sonify.dynamics import marking_for_volume, percentile
from app.sonify.model import STREAM_VARIANTS, StreamVariant
from app.sonify.quantize import c_major_scale, price_to_scale_index, quantize_chord_tone
from app.sonify.regime import MA_WINDOW, classify
from app.sonify.voices import HighBudget, Voice, arrange, sounding_chord, wants_high

BUCKET_MS = 250
BEAT_NOTES = 4
BAR_NOTES = 16
SCALE_TICKS = 60 * BEAT_NOTES
HOLD_VELOCITY = 36
# A one-cent print must not cover C3–C7. Ten basis points is the smallest
# window the scale will stretch across; a wider tape uses its own range.
MIN_SPAN_FRACTION = 0.001


@dataclass(frozen=True)
class Trade:
    t: int
    price: float
    qty: float


@dataclass(frozen=True)
class NoteEvent:
    seq: int
    t: int
    midi: int
    dur_ms: int
    velocity: int
    chord: str
    bass_midi: int | None
    bass_dur_ms: int
    regime: Regime
    price: float
    variant: StreamVariant
    band: str
    swing: bool
    voices: tuple[Voice, ...]
    volume: float = 0.0

    def payload(self) -> dict[str, object]:
        return {
            "type": "note",
            "seq": self.seq,
            "t": self.t,
            "midi": self.midi,
            "dur_ms": self.dur_ms,
            "velocity": self.velocity,
            "chord": self.chord,
            "bass_midi": self.bass_midi,
            "bass_dur_ms": self.bass_dur_ms,
            "regime": self.regime,
            "price": self.price,
            "volume": self.volume,
            "variant": self.variant,
            "band": self.band,
            "swing": self.swing,
            "voices": [voice.payload() for voice in self.voices],
        }


class StreamEngine:
    """Consume trades in time order and emit one note per closed 250 ms bucket."""

    def __init__(self, seed: int = 1, variant: StreamVariant = "symphony") -> None:
        if variant not in STREAM_VARIANTS:
            raise ValueError(f"unknown variant: {variant}")
        self.variant: StreamVariant = variant
        self._rng = random.Random(seed)
        self._scale = c_major_scale()
        self._chord: Chord = tonic("sideway")
        self._next_chord: Chord = tonic("sideway")
        self._regime: Regime = "sideway"
        self._band = "mf"
        self._prices: deque[float] = deque(maxlen=SCALE_TICKS)
        self._volumes: deque[float] = deque(maxlen=SCALE_TICKS)
        self._second_closes: deque[float] = deque(maxlen=MA_WINDOW)
        self._budget = HighBudget(SCALE_TICKS)
        self._seq = 0
        self._prev_midi: int | None = None
        self._prev_raw: int | None = None
        self._prev_sax: int | None = None
        self._prev_ambient: tuple[int, int] | None = None
        self._held_price: float | None = None
        self._hold_count = 0
        self._open: int | None = None
        self._price: float | None = None
        self._volume = 0.0
        self._last_price: float | None = None

    @property
    def chord(self) -> Chord:
        return self._chord

    def push_trade(self, ts: int, price: float, qty: float) -> list[NoteEvent]:
        """Fold one print into its bucket. Closes every earlier open bucket."""
        if not math.isfinite(price) or price <= 0:
            return []
        volume = float(qty) if math.isfinite(qty) and qty > 0 else 0.0
        bucket = (int(ts) // BUCKET_MS) * BUCKET_MS
        if self._open is None:
            self._open = bucket
            self._price = price
            self._volume = volume
            self._last_price = price
            return []
        if bucket < self._open:
            return []
        if bucket == self._open:
            self._price = price
            self._volume += volume
            self._last_price = price
            return []
        notes = self._close_until(bucket)
        self._open = bucket
        self._price = price
        self._volume = volume
        self._last_price = price
        return notes

    def advance_to(self, ts: int, *, piece_end: int | None = None) -> list[NoteEvent]:
        """Close buckets whose interval has ended by `ts`.

        `piece_end` is the first bucket start that must not be emitted. The
        bucket that would open at `piece_end` is dropped instead of held.
        """
        notes: list[NoteEvent] = []
        if self._open is None or self._last_price is None:
            return notes
        while self._open + BUCKET_MS <= ts:
            if piece_end is not None and self._open >= piece_end:
                return notes
            notes.extend(self._emit())
            nxt = self._open + BUCKET_MS
            if piece_end is not None and nxt >= piece_end:
                self._open = None
                self._price = None
                return notes
            self._open = nxt
            self._price = self._last_price
            self._volume = 0.0
        return notes

    def _close_until(self, bucket: int) -> list[NoteEvent]:
        notes: list[NoteEvent] = []
        while self._open is not None and self._open < bucket:
            notes.extend(self._emit())
            self._open += BUCKET_MS
            self._price = self._last_price
            self._volume = 0.0
        return notes

    def _emit(self) -> list[NoteEvent]:
        if self._open is None or self._price is None:
            return []
        price = self._price
        volume = self._volume
        if self._seq % BAR_NOTES == 0:
            self._band = self._band_now()
            if self._seq > 0:
                self._chord = self._next_chord
            self._next_chord = self._pick(self._chord)
        self._prices.append(price)
        self._volumes.append(volume)
        if self._held_price == price:
            self._hold_count += 1
        else:
            self._held_price = price
            self._hold_count = 1
        low, high = _scale_bounds(self._prices)
        raw = self._scale[price_to_scale_index(price, low, high, len(self._scale))]
        step = 0 if self._prev_raw is None else raw - self._prev_raw
        heard = sounding_chord(self.variant, self._chord)
        strong = self._seq % BEAT_NOTES == 0
        if strong:
            midi = quantize_chord_tone(
                raw,
                heard.pitch_classes,
                self._scale,
                previous=self._prev_midi,
                step=step,
            )
        else:
            midi = raw
        velocity = self._velocity(volume)
        allow_high = self._budget.take(wants_high(self.variant, raw))
        voices, sax = arrange(
            self.variant,
            seq=self._seq,
            midi=midi,
            velocity=velocity,
            chord=self._chord,
            next_chord=self._next_chord,
            band=self._band,
            prev_sax=self._prev_sax,
            allow_high=allow_high,
            price_held=self._hold_count == 4,
            prev_ambient=self._prev_ambient,
        )
        if sax is not None:
            self._prev_sax = sax
        if any(voice.role == "glass" for voice in voices):
            self._prev_ambient = (midi, self._seq)
        bass = next((voice for voice in voices if voice.role in ("bass", "drone", "sub")), None)
        note = NoteEvent(
            seq=self._seq,
            t=self._open,
            midi=midi,
            dur_ms=BUCKET_MS,
            velocity=velocity,
            chord=heard.name,
            bass_midi=None if bass is None else bass.midi,
            bass_dur_ms=0 if bass is None else bass.dur_ms,
            regime=self._regime,
            price=price,
            variant=self.variant,
            band=self._band,
            swing=self.variant == "jazz",
            voices=voices,
            volume=volume,
        )
        self._prev_midi = midi
        self._prev_raw = raw
        self._seq += 1
        if self._seq % BEAT_NOTES == 0:
            self._second_closes.append(price)
            self._regime = self._regime_now()
        return [note]

    def _regime_now(self) -> Regime:
        if len(self._second_closes) < MA_WINDOW:
            return "sideway"
        average = sum(self._second_closes) / MA_WINDOW
        return classify(self._second_closes[-1], average)

    def _band_now(self) -> str:
        positive = [item for item in self._volumes if item > 0]
        if len(positive) < 4:
            return "mf"
        low = percentile(positive, 0.10)
        high = percentile(positive, 0.90)
        window = list(self._volumes)[-BAR_NOTES:]
        recent = sum(window) / len(window) if window else 0.0
        return marking_for_volume(recent, low, high)

    def _pick(self, chord: Chord) -> Chord:
        bias = REGIME_BIAS[self._regime]
        choices: list[Chord] = []
        weights: list[float] = []
        for candidate, prob in TRANSITIONS[chord].items():
            if prob <= 0:
                continue
            choices.append(candidate)
            weights.append(prob / (0.05 + bias[candidate]))
        if not choices:
            return chord
        return self._rng.choices(choices, weights=weights, k=1)[0]

    def _velocity(self, volume: float) -> int:
        if volume <= 0:
            return HOLD_VELOCITY
        positive = [item for item in self._volumes if item > 0]
        if len(positive) < 4:
            return 78
        low = percentile(positive, 0.10)
        high = percentile(positive, 0.90)
        if low <= 0 or high / low < 2 or high <= low:
            return 78
        floor = math.log1p(low)
        ceiling = math.log1p(high)
        if ceiling <= floor:
            return 78
        norm = (math.log1p(volume) - floor) / (ceiling - floor)
        norm = min(1.0, max(0.0, norm))
        return round(52 + norm * 56)


def _scale_bounds(prices: deque[float]) -> tuple[float, float]:
    low = min(prices)
    high = max(prices)
    latest = prices[-1]
    floor = abs(latest) * MIN_SPAN_FRACTION
    if high - low >= floor or floor <= 0:
        return low, high
    mid = (low + high) / 2
    return mid - floor / 2, mid + floor / 2


def piece_bounds(trades: list[Trade]) -> tuple[int, int]:
    """Start of the first bucket and the exclusive end of the last one."""
    start = (trades[0].t // BUCKET_MS) * BUCKET_MS
    end = (trades[-1].t // BUCKET_MS) * BUCKET_MS + BUCKET_MS
    return start, end


def pump(
    engine: StreamEngine,
    trades: list[Trade],
    index: int,
    horizon: int,
    piece_end: int,
) -> tuple[int, list[NoteEvent]]:
    """Feed every trade that has arrived by `horizon`, then close finished buckets."""
    notes: list[NoteEvent] = []
    while index < len(trades) and trades[index].t < horizon:
        trade = trades[index]
        notes.extend(engine.push_trade(trade.t, trade.price, trade.qty))
        index += 1
    notes.extend(engine.advance_to(horizon, piece_end=piece_end))
    return index, notes


def render_stream(
    trades: list[Trade],
    seed: int = 1,
    variant: StreamVariant = "symphony",
) -> list[NoteEvent]:
    """Run the whole tape. Equivalent to pumping one bucket at a time."""
    if not trades:
        return []
    _start, piece_end = piece_bounds(trades)
    engine = StreamEngine(seed=seed, variant=variant)
    _index, notes = pump(engine, trades, 0, piece_end, piece_end)
    return notes
