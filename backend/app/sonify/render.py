"""Build a 30-bar score: violin and cello on the price, light piano comping, bass on liquidity."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.sonify.chords import Chord, Regime, progression
from app.sonify.dynamics import (
    MARKINGS,
    SOUND,
    average_liquidity,
    bass_marking,
    marking_for_volume,
    percentile,
)
from app.sonify.form import (
    BPM,
    MUSICAL_BARS,
    PHRASE_STARTS,
    SECTION_STARTS,
    ChordSlot,
    plan_slots,
)
from app.sonify.model import Bar, DynamicEvent, HarmonyEvent, NoteEvent, Score, WedgeEvent
from app.sonify.phrasing import COMMA, PERIOD, Phrase, Run, plan_phrases, swell
from app.sonify.quantize import c_major_scale, price_to_scale_index, resample
from app.sonify.regime import REGIME_BARS, classify_window

EIGHTHS_PER_BAR = 8
HALF_BAR = 4
TOTAL_EIGHTHS = MUSICAL_BARS * EIGHTHS_PER_BAR
VIOLIN_LOWEST = 55  # G3
CELLO_HANDBACK = 60  # C4
PIANO_ROOT_LOW = 41  # F2
GUIDE_LOW = 57  # A3

# Melody velocity rides one phrase: mp at its edges, up to MELODY_PEAK at the
# apex when the phrase climbs a full octave. The bass never goes above mp (64).
MELODY_FLOOR = 64
MELODY_PEAK = 88
MELODY_MARKING = "mp"
FULL_RISE = 12
# A phrase that climbs less than this many semitones is flat: no hairpins.
MIN_RISE = 3
ACCENT_LIFT = 8
STRONG_EIGHTHS = (0, 4)  # beats 1 and 3
WEDGE_MIN = 2  # eighths

# Colour on held melody notes (at least PERIOD eighths), at most one each.
TREMOLO = "tremolo"
BREAKOUT = "breakout"
TREMOLO_BAND = MARKINGS[-1]
BREAKOUT_LOOKBACK = 32  # eighths: four bars

# Piano answers a held cadence in its last beats, while the melody holds and breathes.
FILL_VELOCITY = 64  # mp, one step over the printed comping p
FILL_DELAY = 2
FILL_SPAN = 6
FILL_MIN = 2
FILL_LOW = 55  # G3
FILL_HIGH = 79  # G5
FILL_ABOVE_CELLO = 60  # C4
FILL_GAP = 3

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
    accent: bool = False,
    velocity: int | None = None,
    tenuto: bool = False,
    tremolo: bool = False,
    tie_in: bool = False,
    tie_out: bool = False,
) -> list[NoteEvent]:
    pieces = _spell(start, length)
    sounding = midi is not None
    last = len(pieces) - 1
    return [
        NoteEvent(
            bar=cursor // EIGHTHS_PER_BAR,
            beat=(cursor % EIGHTHS_PER_BAR) * 0.5,
            midi=midi,
            duration_beats=size * 0.5,
            voice=1,
            tie_start=sounding and (index < last or tie_out),
            tie_stop=sounding and (index > 0 or tie_in),
            slur_start=slur_start and index == 0,
            slur_stop=slur_stop and index == last,
            accent=accent and index == 0,
            velocity=velocity if sounding else None,
            tenuto=tenuto and index == 0,
            tremolo=tremolo and sounding,
        )
        for index, (cursor, size) in enumerate(pieces)
    ]


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


@dataclass
class _Line:
    notes: list[NoteEvent] = field(default_factory=list)
    wedges: list[WedgeEvent] = field(default_factory=list)
    dynamics: list[DynamicEvent] = field(default_factory=list)
    # A hairpin with no target letter moves playback one step and leaves it
    # there, so steps that do not cancel are reset with a printed letter.
    drift: int = 0


def _lift(phrase: Phrase) -> float:
    if phrase.rise < MIN_RISE:
        return 0.0
    return min(1.0, phrase.rise / FULL_RISE)


def accent_of(phrase: Phrase, skip: frozenset[int] = frozenset()) -> Run | None:
    """The phrase's longest held note that lands off beats 1 and 3, the earliest on a tie.

    One accent per phrase, so the syncopation reads as the phrase's stress.
    Runs starting at an eighth in skip are passed over.
    """
    syncopated = [
        run
        for run in phrase.runs
        if run.length >= COMMA
        and run.start % EIGHTHS_PER_BAR not in STRONG_EIGHTHS
        and run.start not in skip
    ]
    return max(syncopated, key=lambda run: (run.length, -run.start), default=None)


def techniques(phrase: Phrase, pitches: list[int], band_at: dict[int, str]) -> dict[int, str]:
    """A colour for some held notes of one phrase, keyed by run start.

    Tremolo: the price fell onto the note and stalls while liquidity is in the
    top band — heavy trading that no longer moves the price.
    Breakout: the price climbs above every note of the previous four bars and
    holds there; the first one in a phrase is accented and held tenuto.
    A note takes the first of these that applies.
    """
    chosen: dict[int, str] = {}
    for run in phrase.runs:
        if run.length < PERIOD:
            continue
        before = pitches[run.start - 1] if run.start else run.midi
        window = pitches[max(0, run.start - BREAKOUT_LOOKBACK) : run.start]
        if band_at[run.start // EIGHTHS_PER_BAR] == TREMOLO_BAND and before > run.midi:
            chosen[run.start] = TREMOLO
        elif (
            BREAKOUT not in chosen.values()
            and run.start >= BREAKOUT_LOOKBACK
            and run.midi > max(window)
        ):
            chosen[run.start] = BREAKOUT
    return chosen


def _velocity(phrase: Phrase, run: Run, lift: float, accented: bool) -> int:
    level = MELODY_FLOOR + (MELODY_PEAK - MELODY_FLOOR) * lift * swell(phrase, run.start)
    if accented:
        level += ACCENT_LIFT
    return round(level)


def _wedge_at(position: int, kind: str) -> WedgeEvent:
    """A stop on a bar line closes the bar before it."""
    if kind == "stop" and position > 0 and position % EIGHTHS_PER_BAR == 0:
        return WedgeEvent(position // EIGHTHS_PER_BAR - 1, 4.0, kind)
    return WedgeEvent(position // EIGHTHS_PER_BAR, (position % EIGHTHS_PER_BAR) * 0.5, kind)


def _hairpins(start: int, end: int, apex: int) -> list[WedgeEvent]:
    """Crescendo into the apex and diminuendo out of it, clipped to one instrument's span."""
    peak = min(max(apex, start), end)
    wedges: list[WedgeEvent] = []
    if peak - start >= WEDGE_MIN:
        wedges += [_wedge_at(start, "crescendo"), _wedge_at(peak, "stop")]
    if end - peak >= WEDGE_MIN:
        wedges += [_wedge_at(peak, "diminuendo"), _wedge_at(end, "stop")]
    return wedges


def _melody_parts(
    pitches: list[int], phrases: tuple[Phrase, ...], band_at: dict[int, str]
) -> tuple[_Line, _Line, list[tuple[Run, str]]]:
    """Split the legato line between violin and cello; the silent part rests.

    Same-pitch eighths are one held note for the length of a phrase, tied
    across chord changes. The cello takes over below the violin's open G and
    keeps the line until it climbs back to C4, so a price hovering near G3 does
    not bounce between them. Each instrument's share of a phrase is one slur
    with hairpins toward the phrase apex. The phrase's stress is its breakout
    note, else its syncopated held note, and is accented. Held notes take
    their colour from `techniques`. A share that opens after hairpins left the
    line off its starting step is marked mp again. A phrase that closes on a held note
    drops its last eighth for a breath; that eighth repeated the same price.
    A note held over into the next phrase is tied across, keeps its tremolo,
    and is not accented again.
    Returns both lines and each closing cadence with the instrument holding it.
    """
    lines = {"violin": _Line(), "cello": _Line()}
    cadences: list[tuple[Run, str]] = []
    on_cello = False
    tied_in = False
    carried: str | None = None
    for phrase in phrases:
        owners: list[str] = []
        for run in phrase.runs:
            on_cello = run.midi < CELLO_HANDBACK if on_cello else run.midi < VIOLIN_LOWEST
            owners.append("cello" if on_cello else "violin")
        breath = phrase.closes and phrase.end < TOTAL_EIGHTHS
        lift = _lift(phrase)
        colours = techniques(phrase, pitches, band_at)
        if tied_in and carried == TREMOLO:
            colours[phrase.start] = TREMOLO
        breakout = next(
            (run for run in phrase.runs if colours.get(run.start) == BREAKOUT), None
        )
        skip = frozenset(colours) | ({phrase.start} if tied_in else frozenset())
        stress = breakout or accent_of(phrase, skip)
        index = 0
        while index < len(phrase.runs):
            end = index + 1
            while end < len(phrase.runs) and owners[end] == owners[index]:
                end += 1
            segment = phrase.runs[index:end]
            line = lines[owners[index]]
            if line.drift:
                line.dynamics.append(
                    DynamicEvent(
                        bar=segment[0].start // EIGHTHS_PER_BAR,
                        marking=MELODY_MARKING,
                        sound=SOUND[MELODY_MARKING],
                        beat=(segment[0].start % EIGHTHS_PER_BAR) * 0.5,
                    )
                )
                line.drift = 0
            slurred = len(segment) > 1
            sounding_end = segment[0].start
            for run_index, run in enumerate(segment):
                length = run.length - (1 if breath and run.end == phrase.end else 0)
                sounding_end = run.start + length
                colour = colours.get(run.start)
                line.notes.extend(
                    _written(
                        run.start,
                        length,
                        run.midi,
                        slur_start=slurred and run_index == 0,
                        slur_stop=slurred and run_index == len(segment) - 1,
                        accent=run == stress,
                        velocity=_velocity(phrase, run, lift, run == stress),
                        tenuto=colour == BREAKOUT,
                        tremolo=colour == TREMOLO,
                        tie_in=tied_in and run.start == phrase.start,
                        tie_out=phrase.held_over and run.end == phrase.end,
                    )
                )
            if lift:
                hairpins = _hairpins(segment[0].start, sounding_end, phrase.apex.start)
                line.wedges.extend(hairpins)
                for wedge in hairpins:
                    line.drift += {"crescendo": 1, "diminuendo": -1}.get(wedge.kind, 0)
            index = end
        if phrase.closes:
            cadences.append((phrase.cadence, owners[-1]))
        tied_in = phrase.held_over
        carried = colours.get(phrase.cadence.start)
    return lines["violin"], lines["cello"], cadences


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


def fill_tones(chord: Chord, melody: int, owner: str) -> list[int]:
    """Up to four chord tones for the answer, out of the melody's way.

    Under the violin: the highest tones at least FILL_GAP semitones below it.
    Over the cello: the lowest tones from C4 up, at least FILL_GAP semitones above it.
    """
    pcs = {pitch % 12 for pitch in chord.pitches}
    if owner == "cello":
        floor = max(FILL_ABOVE_CELLO, melody + FILL_GAP)
        return [midi for midi in range(floor, FILL_HIGH + 1) if midi % 12 in pcs][:4]
    ceiling = min(FILL_HIGH, melody - FILL_GAP)
    return [midi for midi in range(FILL_LOW, ceiling + 1) if midi % 12 in pcs][-4:]


def _fills(
    cadences: list[tuple[Run, str]], chord_at: dict[int, Chord]
) -> list[tuple[int, int, int]]:
    """An ascending arpeggio in the last beats of each held cadence, as start, length, midi.

    Downbeats stay with the comping chord. The top tone holds once the
    arpeggio runs out; a chord change restarts it from the bottom. A cadence
    whose chord has fewer than three tones out of the melody's way gets none.
    """
    notes: list[tuple[int, int, int]] = []
    for run, owner in cadences:
        first = max(run.start + FILL_DELAY, run.end - FILL_SPAN)
        eighths = [eighth for eighth in range(first, run.end) if eighth % EIGHTHS_PER_BAR]
        if len(eighths) < FILL_MIN:
            continue
        chords = {chord_at[eighth // EIGHTHS_PER_BAR] for eighth in eighths}
        tones = {chord: fill_tones(chord, run.midi, owner) for chord in chords}
        if any(len(found) < 3 for found in tones.values()):
            continue
        step = 0
        previous: Chord | None = None
        for eighth in eighths:
            chord = chord_at[eighth // EIGHTHS_PER_BAR]
            if chord != previous:
                step = 0
                previous = chord
            midi = tones[chord][min(step, len(tones[chord]) - 1)]
            step += 1
            if notes and sum(notes[-1][:2]) == eighth and notes[-1][2] == midi:
                start, length, _midi = notes[-1]
                notes[-1] = (start, length + 1, midi)
            else:
                notes.append((eighth, 1, midi))
    return notes


def _right_hand(
    slots: tuple[ChordSlot, ...], fills: list[tuple[int, int, int]]
) -> tuple[NoteEvent, ...]:
    """Third and seventh on beat 1 for half a bar, cut short when a fill comes in."""
    first_fill: dict[int, int] = {}
    for start, _length, _midi in fills:
        bar = start // EIGHTHS_PER_BAR
        first_fill[bar] = min(first_fill.get(bar, start), start)
    events: list[NoteEvent] = []
    for slot in slots:
        _root, guide = comp_pitches(slot.chord)
        for bar in slot.bars():
            downbeat = bar * EIGHTHS_PER_BAR
            length = min(HALF_BAR, first_fill.get(bar, downbeat + HALF_BAR) - downbeat)
            events.extend(
                NoteEvent(bar=bar, beat=0.0, midi=midi, duration_beats=length * 0.5, voice=1)
                for midi in guide
            )
    for start, length, midi in fills:
        events.extend(_written(start, length, midi, velocity=FILL_VELOCITY))
    return _with_rests(events, TOTAL_EIGHTHS)


def _left_hand(slot: ChordSlot) -> list[NoteEvent]:
    """The root once, held through the first bar of the chord."""
    root, _guide = comp_pitches(slot.chord)
    return [
        NoteEvent(
            bar=bar,
            beat=0.0,
            midi=root if offset == 0 else None,
            duration_beats=4.0,
            voice=5,
            staff=2,
        )
        for offset, bar in enumerate(slot.bars())
    ]


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
    seven notes. Piano touches the third, seventh, and root, and answers each
    phrase that closes on a held note with a short arpeggio.
    The melody is cut into phrases where the price stalls; see phrasing.py.
    Liquidity is the average continuous volume of the slot, ranked p–f. The
    band sets how often the bass attacks: a held root at p, halves at mp,
    quarters at mf, a root–octave–fifth eighth-note drive at f. The bass is
    marked at that band but never above BASS_CEILING.
    """
    if not bars:
        raise ValueError("need at least one price bar")

    groups = assign_source_bars(len(bars))
    if regimes is None:
        samples = tuple(_phrase_regime(bars, groups, start) for start in PHRASE_STARTS)
        sample_indexes: tuple[int, int, int] | None = tuple(index for index, _regime in samples)
        chosen = tuple(regime for _index, regime in samples)
    else:
        sample_indexes = None
        chosen = regimes
    for regime in chosen:
        progression(regime)
    slots = plan_slots(chosen)

    slot_volumes = average_liquidity(
        [_slot_candles(bars, groups, slot) for slot in slots]
    )
    traded = [volume for volume in slot_volumes if volume > 0]
    low_volume = percentile(traded, 0.10)
    high_volume = percentile(traded, 0.90)
    bands = [marking_for_volume(volume, low_volume, high_volume) for volume in slot_volumes]
    dynamics = tuple(
        DynamicEvent(bar=slot.start, marking=bass_marking(band), sound=SOUND[bass_marking(band)])
        for slot, band in zip(slots, bands)
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

    phrases = plan_phrases(pitches, tuple(start * EIGHTHS_PER_BAR for start in SECTION_STARTS))
    band_at = {bar: band for slot, band in zip(slots, bands) for bar in slot.bars()}
    violin, cello, cadences = _melody_parts(pitches, phrases, band_at)
    chord_at = {bar: slot.chord for slot in slots for bar in slot.bars()}
    piano: list[NoteEvent] = list(_right_hand(slots, _fills(cadences, chord_at)))
    bass: list[NoteEvent] = []
    for slot, band in zip(slots, bands):
        piano.extend(_left_hand(slot))
        for musical_bar in slot.bars():
            bass.extend(_bass_bar(slot.chord, band, musical_bar))

    return Score(
        title=title,
        bpm=BPM,
        bars=MUSICAL_BARS,
        regimes=chosen,
        regime_samples=sample_indexes,
        slots=slots,
        violin=_with_rests(violin.notes, TOTAL_EIGHTHS),
        cello=_with_rests(cello.notes, TOTAL_EIGHTHS),
        piano=tuple(piano),
        bass=tuple(bass),
        dynamics=dynamics,
        harmonies=harmonies,
        liquidity=tuple(bands),
        phrases=phrases,
        violin_wedges=tuple(violin.wedges),
        cello_wedges=tuple(cello.wedges),
        violin_dynamics=tuple(violin.dynamics),
        cello_dynamics=tuple(cello.dynamics),
    )
