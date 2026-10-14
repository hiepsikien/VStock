"""Build a 30-bar score: piano inside the chord, bass on the root."""

from __future__ import annotations

from app.sonify.chords import Regime, progression
from app.sonify.dynamics import SOUND, average_liquidity, marking_for_volume, percentile
from app.sonify.form import BPM, MUSICAL_BARS, PHRASE_STARTS, ChordSlot, plan_slots
from app.sonify.model import Bar, DynamicEvent, HarmonyEvent, NoteEvent, Score
from app.sonify.quantize import c_major_scale, price_to_scale_index, quantize, resample
from app.sonify.regime import REGIME_BARS, classify_window

EIGHTHS_PER_BAR = 8


def assign_source_bars(count: int, musical_bars: int = MUSICAL_BARS) -> list[list[int]]:
    """Drop each source index into one musical bar, in order.

    The first source bar always lands in musical bar 0. When there are fewer
    source bars than musical bars, the empty bars later repeat the price that
    was already sounding.
    """
    if count < 1:
        raise ValueError("need at least one source bar")
    groups: list[list[int]] = [[] for _ in range(musical_bars)]
    for index in range(count):
        group = (index * musical_bars) // count
        if group >= musical_bars:
            group = musical_bars - 1
        groups[group].append(index)
    return groups


def _sample_index(groups: list[list[int]], musical_bar: int) -> int:
    if groups[musical_bar]:
        return groups[musical_bar][0]
    for previous in range(musical_bar - 1, -1, -1):
        if groups[previous]:
            return groups[previous][-1]
    return 0


def _phrase_regime(bars: list[Bar], groups: list[list[int]], musical_bar: int) -> tuple[int, str]:
    start = _sample_index(groups, musical_bar)
    window = bars[start : start + REGIME_BARS]
    regime = classify_window(
        [bar.close for bar in window],
        [bar.ma20 for bar in window],
    )
    return start, regime


def _slot_candles(bars: list[Bar], groups: list[list[int]], slot: ChordSlot) -> list[float]:
    """Continuous-auction volume only. ATO/ATC prints are not liquidity."""
    volumes: list[float] = []
    for musical_bar in slot.bars():
        for index in groups[musical_bar]:
            bar = bars[index]
            if bar.auction:
                continue
            volumes.append(bar.volume)
    return volumes


def render(
    bars: list[Bar],
    *,
    title: str = "1-Day Recap",
    regimes: tuple[Regime, Regime, Regime] | None = None,
) -> Score:
    """Turn one session of closes into piano, chord voicing, bass, and symbols.

    Each phrase regime is the average of the first few source bars at that
    phrase's downbeat, then held for the phrase. Intro uses phrase 1's regime;
    outro uses phrase 3's. Bass attacks once per chord and holds the root.
    Dynamics follow the average continuous volume of the slot and are written
    on the bass only.
    """
    if not bars:
        raise ValueError("need at least one price bar")

    groups = assign_source_bars(len(bars))
    samples = tuple(_phrase_regime(bars, groups, start) for start in PHRASE_STARTS)
    sample_indexes = tuple(index for index, _regime in samples)
    inferred = tuple(regime for _index, regime in samples)
    chosen = inferred if regimes is None else regimes
    for regime in chosen:
        progression(regime)
    slots = plan_slots(chosen)

    slot_volumes = average_liquidity(
        [_slot_candles(bars, groups, slot) for slot in slots]
    )
    low_volume = percentile(slot_volumes, 0.10)
    high_volume = percentile(slot_volumes, 0.90)
    markings = [
        marking_for_volume(volume, low_volume, high_volume) for volume in slot_volumes
    ]
    dynamics = tuple(
        DynamicEvent(bar=slot.start, marking=marking, sound=SOUND[marking])
        for slot, marking in zip(slots, markings)
    )
    harmonies = tuple(HarmonyEvent(slot.start, slot.chord) for slot in slots)

    chord_at = [slots[0].chord for _ in range(MUSICAL_BARS)]
    for slot in slots:
        for musical_bar in slot.bars():
            chord_at[musical_bar] = slot.chord

    scale = c_major_scale()
    session_low = min(bar.close for bar in bars)
    session_high = max(bar.close for bar in bars)
    held_close = bars[0].close
    piano: list[NoteEvent] = []
    previous: int | None = None
    for musical_bar, group in enumerate(groups):
        if group:
            closes = [bars[index].close for index in group]
            held_close = closes[-1]
        else:
            closes = [held_close]
        for eighth, close in enumerate(resample(closes, EIGHTHS_PER_BAR)):
            target_index = price_to_scale_index(close, session_low, session_high, len(scale))
            midi = quantize(scale[target_index], chord_at[musical_bar], scale, previous)
            previous = midi
            piano.append(
                NoteEvent(
                    bar=musical_bar,
                    beat=eighth * 0.5,
                    midi=midi,
                    duration_beats=0.5,
                    voice=1,
                )
            )

    pad: list[NoteEvent] = []
    bass: list[NoteEvent] = []
    for slot in slots:
        for offset, musical_bar in enumerate(slot.bars()):
            tie_start = offset < slot.length - 1
            tie_stop = offset > 0
            bass.append(
                NoteEvent(
                    bar=musical_bar,
                    beat=0.0,
                    midi=slot.chord.bass_midi,
                    duration_beats=4.0,
                    voice=1,
                    tie_start=tie_start,
                    tie_stop=tie_stop,
                )
            )
            for pitch in slot.chord.pitches:
                pad.append(
                    NoteEvent(
                        bar=musical_bar,
                        beat=0.0,
                        midi=pitch,
                        duration_beats=4.0,
                        voice=2,
                        tie_start=tie_start,
                        tie_stop=tie_stop,
                    )
                )

    return Score(
        title=title,
        bpm=BPM,
        bars=MUSICAL_BARS,
        regimes=chosen,
        regime_samples=sample_indexes,
        slots=slots,
        piano=tuple(piano),
        pad=tuple(pad),
        bass=tuple(bass),
        dynamics=dynamics,
        harmonies=harmonies,
    )
