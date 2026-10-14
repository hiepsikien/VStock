"""Build a 30-bar score: violin and cello on the price, piano arpeggio, bass on the root."""

from __future__ import annotations

from app.sonify.chords import Chord, Regime, progression
from app.sonify.dynamics import SOUND, average_liquidity, marking_for_volume, percentile
from app.sonify.form import BPM, MUSICAL_BARS, PHRASE_STARTS, ChordSlot, plan_slots
from app.sonify.model import Bar, DynamicEvent, HarmonyEvent, NoteEvent, Score
from app.sonify.quantize import c_major_scale, price_to_scale_index, resample
from app.sonify.regime import REGIME_BARS, classify_window

EIGHTHS_PER_BAR = 8
HALF_BAR = 4
VIOLIN_LOWEST = 55  # G3
CELLO_HANDBACK = 60  # C4


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


def _spell(start: int, length: int) -> list[tuple[int, int]]:
    """Cut a run of eighths at bar lines, and inside a bar at beat 3.

    A run that fills a whole bar stays one whole note. Every other piece is
    1 to 4 eighths: eighth, quarter, dotted quarter, or half.
    """
    pieces: list[tuple[int, int]] = []
    cursor = start
    end = start + length
    while cursor < end:
        bar_end = (cursor // EIGHTHS_PER_BAR + 1) * EIGHTHS_PER_BAR
        if cursor % EIGHTHS_PER_BAR == 0 and end >= bar_end:
            stop = bar_end
        else:
            stop = min(end, cursor - cursor % HALF_BAR + HALF_BAR)
        pieces.append((cursor, stop - cursor))
        cursor = stop
    return pieces


def _written(
    start: int,
    length: int,
    midi: int | None,
    *,
    slur_start: bool = False,
    slur_stop: bool = False,
) -> list[NoteEvent]:
    pieces = _spell(start, length)
    sounding = midi is not None
    return [
        NoteEvent(
            bar=cursor // EIGHTHS_PER_BAR,
            beat=(cursor % EIGHTHS_PER_BAR) * 0.5,
            midi=midi,
            duration_beats=size * 0.5,
            voice=1,
            tie_start=sounding and index < len(pieces) - 1,
            tie_stop=sounding and index > 0,
            slur_start=slur_start and index == 0,
            slur_stop=slur_stop and index == len(pieces) - 1,
        )
        for index, (cursor, size) in enumerate(pieces)
    ]


def _runs(pitches: list[int], slot: ChordSlot) -> list[tuple[int, int, int]]:
    """Same-pitch eighths inside one chord slot, as start, length, midi."""
    runs: list[tuple[int, int, int]] = []
    first = slot.start * EIGHTHS_PER_BAR
    last = (slot.start + slot.length) * EIGHTHS_PER_BAR
    for eighth in range(first, last):
        midi = pitches[eighth]
        if runs and runs[-1][2] == midi:
            start, length, _midi = runs[-1]
            runs[-1] = (start, length + 1, midi)
        else:
            runs.append((eighth, 1, midi))
    return runs


def _with_rests(notes: list[NoteEvent], total: int) -> tuple[NoteEvent, ...]:
    def position(event: NoteEvent) -> int:
        return event.bar * EIGHTHS_PER_BAR + int(event.beat * 2)

    filled: list[NoteEvent] = []
    cursor = 0
    for event in sorted(notes, key=position):
        start = position(event)
        if start > cursor:
            filled.extend(_written(cursor, start - cursor, None))
        filled.append(event)
        cursor = start + int(event.duration_beats * 2)
    if cursor < total:
        filled.extend(_written(cursor, total - cursor, None))
    return tuple(filled)


def _melody_parts(
    pitches: list[int], slots: tuple[ChordSlot, ...]
) -> tuple[tuple[NoteEvent, ...], tuple[NoteEvent, ...]]:
    """Split the legato line between violin and cello; the silent part rests.

    Same-pitch eighths merge into one held note, restarted on each chord change.
    The cello takes over below the violin's open G and keeps the line until it
    climbs back to C4, so a price hovering near G3 does not bounce between them.
    Each run of one instrument inside a chord slot is one slur.
    """
    parts: dict[str, list[NoteEvent]] = {"violin": [], "cello": []}
    on_cello = False
    for slot in slots:
        runs = _runs(pitches, slot)
        owners: list[str] = []
        for _start, _length, midi in runs:
            on_cello = midi < CELLO_HANDBACK if on_cello else midi < VIOLIN_LOWEST
            owners.append("cello" if on_cello else "violin")
        index = 0
        while index < len(runs):
            end = index + 1
            while end < len(runs) and owners[end] == owners[index]:
                end += 1
            phrase = runs[index:end]
            slurred = len(phrase) > 1
            for run_index, (start, length, midi) in enumerate(phrase):
                parts[owners[index]].extend(
                    _written(
                        start,
                        length,
                        midi,
                        slur_start=slurred and run_index == 0,
                        slur_stop=slurred and run_index == len(phrase) - 1,
                    )
                )
            index = end
    total = MUSICAL_BARS * EIGHTHS_PER_BAR
    return _with_rests(parts["violin"], total), _with_rests(parts["cello"], total)


def _arpeggio(chord: Chord, bar: int) -> list[NoteEvent]:
    """Broken chord in eighths, twice per bar.

    Left hand plays root and fifth an octave down on beats 1 and 3; right hand
    answers on beats 2 and 4, third–seventh, then fifth–third on the way back.
    """
    root, third, fifth, seventh = chord.pitches
    answers = ((third, seventh), (fifth, third))
    events: list[NoteEvent] = []
    for half, (upper, lower) in enumerate(answers):
        beat = half * 2.0
        events.extend(
            [
                NoteEvent(bar=bar, beat=beat, midi=None, duration_beats=1.0, voice=1),
                NoteEvent(bar=bar, beat=beat + 1.0, midi=upper, duration_beats=0.5, voice=1),
                NoteEvent(bar=bar, beat=beat + 1.5, midi=lower, duration_beats=0.5, voice=1),
                NoteEvent(bar=bar, beat=beat, midi=root - 12, duration_beats=0.5, voice=5, staff=2),
                NoteEvent(bar=bar, beat=beat + 0.5, midi=fifth - 12, duration_beats=0.5, voice=5, staff=2),
                NoteEvent(bar=bar, beat=beat + 1.0, midi=None, duration_beats=1.0, voice=5, staff=2),
            ]
        )
    return events


def render(
    bars: list[Bar],
    *,
    title: str = "1-Day Recap",
    regimes: tuple[Regime, Regime, Regime] | None = None,
) -> Score:
    """Turn one session of closes into violin, cello, piano, bass, and symbols.

    Each phrase regime is the average of the first few source bars at that
    phrase's downbeat, then held for the phrase. Intro uses phrase 1's regime;
    outro uses phrase 3's. The melody walks the whole C major scale rather than
    only chord tones: every chord is diatonic, so its own mode shares those
    seven notes. Piano arpeggiates the chord; bass attacks once per chord and
    holds the root.
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

    scale = c_major_scale()
    session_low = min(bar.close for bar in bars)
    session_high = max(bar.close for bar in bars)
    held_close = bars[0].close
    pitches: list[int] = []
    for group in groups:
        if group:
            closes = [bars[index].close for index in group]
            held_close = closes[-1]
        else:
            closes = [held_close]
        for close in resample(closes, EIGHTHS_PER_BAR):
            pitches.append(scale[price_to_scale_index(close, session_low, session_high, len(scale))])

    piano: list[NoteEvent] = []
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
            piano.extend(_arpeggio(slot.chord, musical_bar))

    violin, cello = _melody_parts(pitches, slots)
    return Score(
        title=title,
        bpm=BPM,
        bars=MUSICAL_BARS,
        regimes=chosen,
        regime_samples=sample_indexes,
        slots=slots,
        violin=violin,
        cello=cello,
        piano=tuple(piano),
        bass=tuple(bass),
        dynamics=dynamics,
        harmonies=harmonies,
    )
