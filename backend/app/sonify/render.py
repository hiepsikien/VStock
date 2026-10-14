"""Build a 30-bar score: violin and cello on the price, light piano comping, bass on liquidity."""

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
PIANO_ROOT_LOW = 41  # F2
GUIDE_LOW = 57  # A3

ROOT, FIFTH, OCTAVE = 0, 7, 12
# One bar of bass per dynamic: (start eighth, length in eighths, interval).
# A busier slot attacks more often, not only louder.
_HELD = ((0, 8, ROOT),)
_HALVES = ((0, 4, ROOT), (4, 4, FIFTH))
_QUARTERS = ((0, 2, ROOT), (2, 2, FIFTH), (4, 2, OCTAVE), (6, 2, FIFTH))
_EIGHTHS = (
    (0, 1, ROOT),
    (1, 1, ROOT),
    (2, 1, OCTAVE),
    (3, 1, ROOT),
    (4, 1, FIFTH),
    (5, 1, FIFTH),
    (6, 1, OCTAVE),
    (7, 1, FIFTH),
)
BASS_PATTERNS = {
    "p": _HELD,
    "mp": _HALVES,
    "mf": _QUARTERS,
    "f": _EIGHTHS,
}


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


def _bass_bar(chord: Chord, marking: str, bar: int) -> list[NoteEvent]:
    return [
        NoteEvent(
            bar=bar,
            beat=start * 0.5,
            midi=chord.bass_midi + interval,
            duration_beats=length * 0.5,
            voice=1,
        )
        for start, length, interval in BASS_PATTERNS[marking]
    ]


def comp_pitches(chord: Chord) -> tuple[int, tuple[int, int]]:
    """Root in F2–E3, and the third and seventh inside A3–G#4.

    The third and seventh alone say major, minor, or dominant; the fixed
    windows keep both hands within a few steps from one chord to the next.
    """
    root_pc, third_pc, _fifth_pc, seventh_pc = (pitch % 12 for pitch in chord.pitches)
    root = PIANO_ROOT_LOW + (root_pc - PIANO_ROOT_LOW) % 12
    guide = tuple(sorted(GUIDE_LOW + (pc - GUIDE_LOW) % 12 for pc in (third_pc, seventh_pc)))
    return root, guide


def _comp(slot: ChordSlot) -> list[NoteEvent]:
    """A light touch per bar so the harmony is heard without filling the texture.

    Right hand: third and seventh on beat 1, held for half a bar. Left hand:
    the root once, held through the first bar of the chord.
    """
    root, guide = comp_pitches(slot.chord)
    events: list[NoteEvent] = []
    for offset, bar in enumerate(slot.bars()):
        events.extend(
            NoteEvent(bar=bar, beat=0.0, midi=midi, duration_beats=2.0, voice=1)
            for midi in guide
        )
        events.append(NoteEvent(bar=bar, beat=2.0, midi=None, duration_beats=2.0, voice=1))
        events.append(
            NoteEvent(
                bar=bar,
                beat=0.0,
                midi=root if offset == 0 else None,
                duration_beats=4.0,
                voice=5,
                staff=2,
            )
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
    seven notes. Piano only touches the third, seventh, and root.
    Dynamics follow the average continuous volume of the slot and are written
    on the bass only. The same band sets how often the bass attacks: a held
    root at p, halves at mp, quarters at mf, a root–octave–fifth eighth-note
    drive at f.
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
    for slot, marking in zip(slots, markings):
        piano.extend(_comp(slot))
        for musical_bar in slot.bars():
            bass.extend(_bass_bar(slot.chord, marking, musical_bar))

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
