"""Build a 30-bar score: violin, cello, and flute on the price, light piano comping, bass on liquidity."""

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
    LIQUIDITY_WINDOWS,
    MUSICAL_BARS,
    PHRASE_STARTS,
    SECTION_STARTS,
    ChordSlot,
    plan_slots,
)
from app.sonify.model import Bar, DynamicEvent, HarmonyEvent, NoteEvent, Score, WedgeEvent
from app.sonify.phrasing import COMMA, PERIOD, Phrase, Run, plan_phrases, runs_of, swell
from app.sonify.quantize import c_major_scale, price_to_scale_index, quantize_chord_tone, resample
from app.sonify.regime import REGIME_BARS, classify_window

EIGHTHS_PER_BAR = 8
HALF_BAR = 4
TOTAL_EIGHTHS = MUSICAL_BARS * EIGHTHS_PER_BAR
VIOLIN_LOWEST = 55  # G3
CELLO_HANDBACK = 60  # C4
CELLO_OVERLAP = 2  # eighths (1 beat) of dovetail overlap when Violin and Cello hand off
VIOLIN_CEILING = 84  # C6: notes above C6 fold down an octave so Violin never shrieks
FLUTE_CEILING = 88  # E6: keep Flute inside its sweet register (<= E6)
FLUTE_TRIGGER = 79  # G5: Flute enters on high apex (>= G5) or Breakout
FLUTE_HANDBACK = 76  # E5: Flute keeps soaring while melody stays at or above E5
FLUTE_OVERLAP = 2  # eighths (1 beat) of dovetail harmony before Violin yields
FLUTE_VELOCITY = 64  # mp ceiling so high flute stays airy and sweet
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

# Colour on held melody notes (at least PERIOD eighths).
BREAKOUT = "breakout"
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


def _window_candles(
    bars: list[Bar], groups: list[list[int]], start: int, length: int
) -> list[float]:
    """Continuous-auction volume only inside one fixed bar window. ATO/ATC prints are not liquidity."""
    volumes: list[float] = []
    for musical_bar in range(start, start + length):
        for index in groups[musical_bar]:
            bar = bars[index]
            if bar.auction:
                continue
            volumes.append(bar.volume)
    return volumes


def _slot_candles(bars: list[Bar], groups: list[list[int]], slot: ChordSlot) -> list[float]:
    """Continuous-auction volume only. ATO/ATC prints are not liquidity."""
    return _window_candles(bars, groups, slot.start, slot.length)


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


def techniques(phrase: Phrase, pitches: list[int], band_at: dict[int, str] | None = None) -> dict[int, str]:
    """A colour for some held notes of one phrase, keyed by run start.

    Breakout: the price climbs above every note of the previous four bars and
    holds there; the first one in a phrase is accented and held tenuto.
    """
    chosen: dict[int, str] = {}
    for run in phrase.runs:
        if run.length < PERIOD:
            continue
        window = pitches[max(0, run.start - BREAKOUT_LOOKBACK) : run.start]
        if (
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


def flute_harmony_pitch(
    melody_midi: int,
    chord: Chord,
    scale: tuple[int, ...],
) -> int:
    """A diatonic third or fifth above the melody (3, 4, or 7 semitones), preferring chord tones.

    Only true thirds (+3, +4 semitones) and perfect fifths (+7 semitones) are
    allowed — never a fourth (+5) or tritone (+6).
    """
    extended = c_major_scale(scale[0], scale[-1] + 24)
    if melody_midi in extended:
        idx = extended.index(melody_midi)
        diatonic_candidates = [
            extended[idx + step]
            for step in (2, 4)
            if idx + step < len(extended)
            and (extended[idx + step] - melody_midi) in (3, 4, 7)
        ]
        chord_matches = [
            note for note in diatonic_candidates if note % 12 in chord.pitch_classes
        ]
        if chord_matches:
            return chord_matches[0]
        if diatonic_candidates:
            return diatonic_candidates[0]
    chord_tones = [
        melody_midi + offset
        for offset in (3, 4, 7)
        if (melody_midi + offset) % 12 in chord.pitch_classes
    ]
    if chord_tones:
        return chord_tones[0]
    return melody_midi + 4


def _flute_and_violin_dovetail(
    phrases: tuple[Phrase, ...],
    pitches: list[int],
    band_at: dict[int, str],
    chord_at: dict[int, Chord],
    scale: tuple[int, ...],
) -> tuple[list[NoteEvent], list[tuple[int, int]]]:
    """Build Flute highlight notes and record spans where Violin yields.

    When a rising phrase reaches a high Apex (>= FLUTE_TRIGGER) or a BREAKOUT
    run, Flute enters softly (tenuto + legato slur) onto a chordal 3rd/5th
    above the melody. For the first FLUTE_OVERLAP eighths (1 beat), Violin and
    Flute play together (dovetail layering); if the high passage continues
    above FLUTE_HANDBACK, Violin rests from (span_start + FLUTE_OVERLAP) up to
    span_end and yields the high line to Flute until the melody drops below
    FLUTE_HANDBACK or the phrase ends. Any remaining phrase runs above
    VIOLIN_CEILING (> C6) are also handed to Flute so Violin never has to fold
    individual notes down an octave or sawtooth across C6.
    """
    flute_notes: list[NoteEvent] = []
    yield_spans: list[tuple[int, int]] = []
    flute_tied_in = False
    prev_flute_midi: int | None = None

    for phrase in phrases:
        colours = techniques(phrase, pitches, band_at)
        apex = phrase.apex
        breath = phrase.closes and phrase.end < TOTAL_EIGHTHS
        crosses_ceiling = (
            max(r.midi for r in phrase.runs) > VIOLIN_CEILING
            and min(r.midi for r in phrase.runs) <= VIOLIN_CEILING
        )
        ended_on_flute = False

        idx = 0
        while idx < len(phrase.runs):
            run = phrase.runs[idx]
            continued_hold = (
                flute_tied_in
                and idx == 0
                and run.midi >= FLUTE_HANDBACK
            )
            is_breakout = (
                phrase.rise >= MIN_RISE
                and colours.get(run.start) == BREAKOUT
                and run.midi >= FLUTE_HANDBACK
            )
            is_high_apex = (
                phrase.rise >= MIN_RISE
                and run.start == apex.start
                and run.midi >= FLUTE_TRIGGER
            )
            above_ceiling = (
                phrase.rise > 0 or crosses_ceiling
            ) and run.midi > VIOLIN_CEILING
            if not (continued_hold or is_breakout or is_high_apex or above_ceiling):
                idx += 1
                continue

            end_idx = idx + 1
            while end_idx < len(phrase.runs) and phrase.runs[end_idx].midi >= FLUTE_HANDBACK:
                end_idx += 1

            soar_runs = phrase.runs[idx:end_idx]
            span_start = soar_runs[0].start
            span_end = soar_runs[-1].end
            sounding_end = span_end - (1 if breath and span_end == phrase.end else 0)
            idx = end_idx
            if sounding_end <= span_start:
                continue

            # Keep Flute in its sweet register (<= FLUTE_CEILING / E6) by folding any
            # note > E6 down an octave (-12) while preserving pitch class and step changes.
            flute_line: list[int] = []
            for eighth in range(span_start, sounding_end):
                f_pitch = flute_harmony_pitch(
                    pitches[eighth],
                    chord_at[eighth // EIGHTHS_PER_BAR],
                    scale,
                )
                while f_pitch > FLUTE_CEILING:
                    f_pitch -= 12
                flute_line.append(f_pitch)
            merged_flute_runs = [
                Run(span_start + r.start, r.length, r.midi)
                for r in runs_of(flute_line, 0, len(flute_line))
            ]
            has_slur = len(merged_flute_runs) > 1
            tie_first_in = (
                continued_hold
                and span_start == phrase.start
                and prev_flute_midi == merged_flute_runs[0].midi
            )
            # Only tie Flute across a held_over phrase boundary when the next phrase
            # will begin on the exact same Flute pitch (same chord at phrase.end).
            next_flute_midi: int | None = None
            if phrase.held_over and span_end == phrase.end and phrase.end < TOTAL_EIGHTHS:
                nf_pitch = flute_harmony_pitch(
                    pitches[phrase.end],
                    chord_at[phrase.end // EIGHTHS_PER_BAR],
                    scale,
                )
                while nf_pitch > FLUTE_CEILING:
                    nf_pitch -= 12
                next_flute_midi = nf_pitch
            tie_last_out = (
                phrase.held_over
                and span_end == phrase.end
                and next_flute_midi == merged_flute_runs[-1].midi
            )

            for r_i, f_run in enumerate(merged_flute_runs):
                is_first = r_i == 0
                is_last = r_i == len(merged_flute_runs) - 1
                flute_notes.extend(
                    _written(
                        f_run.start,
                        f_run.length,
                        f_run.midi,
                        slur_start=has_slur and is_first,
                        slur_stop=has_slur and is_last,
                        velocity=FLUTE_VELOCITY,
                        tenuto=is_first and not tie_first_in,
                        tie_in=is_first and tie_first_in,
                        tie_out=is_last and tie_last_out,
                    )
                )

            # Yield immediately when continuing a held_over Flute note from the previous
            # phrase, or when the entry run is already above VIOLIN_CEILING (> C6) mid-phrase;
            # otherwise overlap for FLUTE_OVERLAP eighths.
            yield_start = (
                span_start
                if (
                    continued_hold
                    or (soar_runs[0].midi > VIOLIN_CEILING and soar_runs[0].start > phrase.start)
                )
                else span_start + FLUTE_OVERLAP
            )
            if yield_start < span_end:
                yield_spans.append((yield_start, span_end))
                if span_end == phrase.end:
                    ended_on_flute = True
            prev_flute_midi = merged_flute_runs[-1].midi

        flute_tied_in = phrase.held_over and ended_on_flute

    return flute_notes, yield_spans


def _apply_violin_yield(
    runs: tuple[Run, ...],
    owners: list[str],
    yield_spans: list[tuple[int, int]] | None,
) -> tuple[list[Run], list[str]]:
    """Split violin runs at yield boundaries so the yielded spans become 'flute'."""
    out_runs = list(runs)
    out_owners = list(owners)
    if not yield_spans:
        return out_runs, out_owners
    for y_start, y_end in yield_spans:
        next_runs: list[Run] = []
        next_owners: list[str] = []
        for run, owner in zip(out_runs, out_owners):
            if owner != "violin" or run.end <= y_start or run.start >= y_end:
                next_runs.append(run)
                next_owners.append(owner)
                continue
            if run.start < y_start:
                next_runs.append(Run(run.start, y_start - run.start, run.midi))
                next_owners.append("violin")
            mid_start = max(run.start, y_start)
            mid_end = min(run.end, y_end)
            if mid_start < mid_end:
                next_runs.append(Run(mid_start, mid_end - mid_start, run.midi))
                next_owners.append("flute")
            if run.end > y_end:
                next_runs.append(Run(y_end, run.end - y_end, run.midi))
                next_owners.append("violin")
        out_runs, out_owners = next_runs, next_owners
    return out_runs, out_owners


def _cross_phrase_cello_overlaps(
    phrases: tuple[Phrase, ...],
    all_runs: list[list[Run]],
    all_owners: list[list[str]],
) -> tuple[dict[int, Run], dict[int, int]]:
    """Record cross-phrase lead-ins and trail-outs when Violin and Cello hand off at a phrase boundary."""
    lead_ins: dict[int, Run] = {}
    trail_outs: dict[int, int] = {}
    for p_idx in range(len(phrases) - 1):
        curr_p = phrases[p_idx]
        if curr_p.held_over:
            continue
        last_owner = all_owners[p_idx][-1]
        next_owner = all_owners[p_idx + 1][0]
        if {last_owner, next_owner} != {"violin", "cello"}:
            continue
        last_run = all_runs[p_idx][-1]
        next_run = all_runs[p_idx + 1][0]
        if (
            not curr_p.closes
            and last_owner == "violin"
            and next_owner == "cello"
            and last_run.midi < CELLO_HANDBACK
        ):
            if last_run.length >= 2:
                lead = min(CELLO_OVERLAP, last_run.length)
                lead_ins[p_idx + 1] = Run(last_run.end - lead, lead, last_run.midi)
            else:
                max_trail = 0
                for step in range(1, min(CELLO_OVERLAP, next_run.length) + 1):
                    if (last_run.end + step - 1) % EIGHTHS_PER_BAR in STRONG_EIGHTHS:
                        break
                    max_trail = step
                if max_trail > 0:
                    trail_outs[p_idx] = max_trail
        elif (
            not curr_p.closes
            and last_owner == "cello"
            and next_owner == "violin"
            and last_run.midi >= VIOLIN_LOWEST
        ):
            if last_run.length >= 2:
                lead = min(CELLO_OVERLAP, last_run.length)
                lead_ins[p_idx + 1] = Run(last_run.end - lead, lead, last_run.midi)
            else:
                max_trail = 0
                for step in range(1, min(CELLO_OVERLAP, next_run.length) + 1):
                    if (last_run.end + step - 1) % EIGHTHS_PER_BAR in STRONG_EIGHTHS:
                        break
                    max_trail = step
                if max_trail > 0:
                    trail_outs[p_idx] = max_trail
        elif (
            curr_p.closes
            and last_owner == "violin"
            and next_owner == "cello"
            and next_run.midi < CELLO_HANDBACK
        ):
            # Store on negative key -(p_idx + 1) so Cello plays the last beat of
            # Violin's closing G3..B3 note before the breath rest.
            eff_len = last_run.length - (1 if curr_p.end < TOTAL_EIGHTHS else 0)
            if eff_len >= 2 and last_run.midi < CELLO_HANDBACK:
                lead = min(CELLO_OVERLAP, eff_len)
                lead_ins[-(p_idx + 1)] = Run(
                    last_run.start + eff_len - lead, lead, last_run.midi
                )
    return lead_ins, trail_outs


def _clip_segment(seg: list[Run], clip_start: int) -> list[Run]:
    """Trim or drop runs in `seg` that start before `clip_start`."""
    if not seg or seg[0].start >= clip_start:
        return seg
    clipped: list[Run] = []
    for r in seg:
        if r.end <= clip_start:
            continue
        if r.start < clip_start:
            clipped.append(Run(clip_start, r.end - clip_start, r.midi))
        else:
            clipped.append(r)
    return clipped


def _instrument_segments(
    p_runs: list[Run],
    owners: list[str],
    target: str,
    cross_lead: Run | None = None,
    cross_trail: int = 0,
    min_start: int = 0,
) -> list[list[Run]]:
    """Build contiguous run segments for `target` ('violin' or 'cello') with dovetail overlap.

    Instead of a hard cut when Violin and Cello hand off inside or across a phrase:
    - When Cello enters from Violin, Cello joins on the tail of Violin's last
      handoff run (when in G3..B3 and >= 2 eighths), or Violin extends its 1-eighth
      G3..B3 handoff note into Cello's entry.
    - When Violin re-enters from Cello, Violin anticipates on Cello's last
      G3..B3 run (when >= 2 eighths), or Cello extends its last note under
      Violin's entry when Cello's final run was below G3 or only 1 eighth.
    Trail-out extensions stop before any strong beat (beat 1 or 3) so a held
    handoff note never bleeds onto a new strong beat with a non-chord tone.
    """
    segments: list[list[Run]] = []
    n = len(p_runs)
    index = 0
    while index < n:
        if owners[index] != target:
            index += 1
            continue
        end = index + 1
        while end < n and owners[end] == target:
            end += 1
        seg = list(p_runs[index:end])
        lead_added = 0

        if index == 0 and cross_lead is not None:
            seg.insert(0, cross_lead)
            lead_added = 1

        # Lead-in overlap from the preceding instrument's final run
        if index > 0:
            prev_owner = owners[index - 1]
            prev_run = p_runs[index - 1]
            if (
                target == "cello"
                and prev_owner == "violin"
                and prev_run.midi < CELLO_HANDBACK
                and prev_run.length >= 2
            ):
                lead = min(CELLO_OVERLAP, prev_run.length)
                seg.insert(0, Run(prev_run.end - lead, lead, prev_run.midi))
                lead_added = 1
            elif (
                target == "violin"
                and prev_owner == "cello"
                and prev_run.midi >= VIOLIN_LOWEST
                and prev_run.length >= 2
            ):
                lead = min(CELLO_OVERLAP, prev_run.length)
                seg.insert(0, Run(prev_run.end - lead, lead, prev_run.midi))
                lead_added = 1

        # Trail-out overlap into the succeeding instrument's opening run
        if end < n:
            next_owner = owners[end]
            next_run = p_runs[end]
            next_end = end + 1
            while next_end < n and owners[next_end] == next_owner:
                next_end += 1
            next_span = p_runs[next_end - 1].end - next_run.start
            # Do not extend a trail-out note onto a strong beat (beat 1 or 3)
            max_trail = 0
            for step in range(1, min(CELLO_OVERLAP, next_span) + 1):
                if (seg[-1].end + step - 1) % EIGHTHS_PER_BAR in STRONG_EIGHTHS:
                    break
                max_trail = step
            if (
                target == "violin"
                and next_owner == "cello"
                and seg[-1].midi < CELLO_HANDBACK
                and seg[-1].length == 1
            ):
                if max_trail > 0:
                    seg[-1] = Run(seg[-1].start, seg[-1].length + max_trail, seg[-1].midi)
            elif (
                target == "cello"
                and next_owner == "violin"
                and next_run.midi >= CELLO_HANDBACK
                and (seg[-1].length == 1 or seg[-1].midi < VIOLIN_LOWEST)
            ):
                if max_trail > 0:
                    seg[-1] = Run(seg[-1].start, seg[-1].length + max_trail, seg[-1].midi)
                elif seg[-1].midi >= VIOLIN_LOWEST:
                    # Strong beat blocked trail-out, so let Cello join Violin's new note
                    # for up to CELLO_OVERLAP eighths instead of cutting off on the barline.
                    lead = min(CELLO_OVERLAP, next_run.length)
                    seg.append(Run(next_run.start, lead, next_run.midi))
        elif end == n and cross_trail > 0:
            seg[-1] = Run(seg[-1].start, seg[-1].length + cross_trail, seg[-1].midi)

        # Merge only the lead-in run with the first segment run if they share a pitch and touch
        if lead_added and len(seg) >= 2 and seg[0].end == seg[1].start and seg[0].midi == seg[1].midi:
            seg[:2] = [Run(seg[0].start, seg[0].length + seg[1].length, seg[0].midi)]

        # Ensure segments of the same instrument never overlap each other or a previous phrase
        clip_start = max(min_start, segments[-1][-1].end if segments else 0)
        seg = _clip_segment(seg, clip_start)

        if seg:
            segments.append(seg)
        index = end
    return segments


def _melody_parts(
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    band_at: dict[int, str],
    yield_spans: list[tuple[int, int]] | None = None,
) -> tuple[_Line, _Line, list[tuple[Run, str]]]:
    """Split the legato line between violin and cello with dovetail handoffs.

    Same-pitch eighths are one held note for the length of a phrase, tied
    across chord changes. The cello takes over below the violin's open G and
    keeps the line until it climbs back to C4, so a price hovering near G3 does
    not bounce between them. At handoffs between violin and cello, the two
    instruments overlap for up to a beat (dovetail) so neither cuts off
    abruptly. Each instrument's share of a phrase is one slur with hairpins
    toward the phrase apex. The phrase's stress is its breakout note, else its
    syncopated held note, and is accented. A share that opens after hairpins
    left the line off its starting step is marked mp again. A phrase that
    closes on a held note drops its last eighth for a breath; that eighth
    repeated the same price. A note held over into the next phrase is tied
    across and is not accented again.
    Returns both lines and each closing cadence with the instrument holding it.
    """
    lines = {"violin": _Line(), "cello": _Line()}
    cadences: list[tuple[Run, str]] = []
    on_cello = False
    tied_in = False
    all_base_owners: list[list[str]] = []
    all_p_runs: list[list[Run]] = []
    all_owners: list[list[str]] = []
    for phrase in phrases:
        base_owners: list[str] = []
        for run in phrase.runs:
            on_cello = run.midi < CELLO_HANDBACK if on_cello else run.midi < VIOLIN_LOWEST
            base_owners.append("cello" if on_cello else "violin")
        phrase_yields = (
            [
                (ys, ye)
                for ys, ye in yield_spans
                if ys < phrase.end and ye > phrase.start
            ]
            if yield_spans
            else []
        )
        p_runs, owners = _apply_violin_yield(phrase.runs, base_owners, phrase_yields)
        all_base_owners.append(base_owners)
        all_p_runs.append(p_runs)
        all_owners.append(owners)

    cross_leads, cross_trails = _cross_phrase_cello_overlaps(
        phrases, all_p_runs, all_owners
    )
    last_end_by_owner = {"violin": 0, "cello": 0}

    for p_idx, phrase in enumerate(phrases):
        base_owners = all_base_owners[p_idx]
        p_runs = all_p_runs[p_idx]
        owners = all_owners[p_idx]
        breath = phrase.closes and phrase.end < TOTAL_EIGHTHS
        lift = _lift(phrase)
        colours = techniques(phrase, pitches, band_at)
        breakout = next(
            (run for run in p_runs if colours.get(run.start) == BREAKOUT), None
        )
        skip = frozenset(colours) | ({phrase.start} if tied_in else frozenset())
        stress_orig = breakout or accent_of(phrase, skip)
        stress_start = stress_orig.start if stress_orig is not None else None
        for owner, line in lines.items():
            c_lead = cross_leads.get(p_idx) if owners[0] == owner else None
            c_trail = cross_trails.get(p_idx, 0) if owners[-1] == owner else 0
            segs = _instrument_segments(
                p_runs,
                owners,
                owner,
                cross_lead=c_lead,
                cross_trail=c_trail,
                min_start=last_end_by_owner[owner],
            )
            closing_warmup = cross_leads.get(-(p_idx + 1))
            if closing_warmup is not None and owner == "cello":
                prev_end = segs[-1][-1].end if segs else last_end_by_owner[owner]
                clipped_warmup = _clip_segment([closing_warmup], prev_end)
                if clipped_warmup:
                    segs.append(clipped_warmup)
            for segment in segs:
                attacks = [
                    run
                    for run in segment
                    if not (
                        tied_in
                        and run.start == phrase.start
                        and owners[0] == owner
                    )
                ]
                swell_from: int | None = segment[0].start
                if line.drift:
                    swell_from = attacks[0].start if attacks else None
                    if attacks:
                        line.dynamics.append(
                            DynamicEvent(
                                bar=attacks[0].start // EIGHTHS_PER_BAR,
                                marking=MELODY_MARKING,
                                sound=SOUND[MELODY_MARKING],
                                beat=(attacks[0].start % EIGHTHS_PER_BAR) * 0.5,
                            )
                        )
                        line.drift = 0
                yield_adjacent = any(o == "flute" for o in owners) and owner == "violin"
                single_len = segment[0].length - (
                    1 if breath and segment[0].end == phrase.end else 0
                )
                slurred = len(segment) > 1 or (
                    yield_adjacent and len(_spell(segment[0].start, max(1, single_len))) > 1
                )
                sounding_end = segment[0].start
                for run_index, run in enumerate(segment):
                    length = run.length - (1 if breath and run.end == phrase.end else 0)
                    if length <= 0:
                        continue
                    sounding_end = run.start + length
                    colour = colours.get(run.start)
                    is_stress = run.start == stress_start and owners[
                        next(
                            (i for i, pr in enumerate(p_runs) if pr.start <= run.start < pr.end),
                            0,
                        )
                    ] == owner
                    v_midi = (
                        run.midi - 12
                        if (owner == "violin" and run.midi > VIOLIN_CEILING)
                        else run.midi
                    )
                    line.notes.extend(
                        _written(
                            run.start,
                            length,
                            v_midi,
                            slur_start=slurred and run_index == 0,
                            slur_stop=slurred and run_index == len(segment) - 1,
                            accent=is_stress,
                            velocity=_velocity(phrase, run, lift, is_stress),
                            tenuto=colour == BREAKOUT,
                            tie_in=(
                                tied_in
                                and run.start == phrase.start
                                and owners[0] == owner
                            ),
                            tie_out=(
                                phrase.held_over
                                and run.end == phrase.end
                                and owners[-1] == owner
                            ),
                        )
                    )
                last_end_by_owner[owner] = max(last_end_by_owner[owner], sounding_end)
                if lift and swell_from is not None and sounding_end > swell_from:
                    hairpins = _hairpins(swell_from, sounding_end, phrase.apex.start)
                    line.wedges.extend(hairpins)
                    for wedge in hairpins:
                        line.drift += {"crescendo": 1, "diminuendo": -1}.get(wedge.kind, 0)
        if phrase.closes:
            cadence_midi = (
                phrase.cadence.midi - 12
                if (base_owners[-1] == "violin" and phrase.cadence.midi > VIOLIN_CEILING)
                else phrase.cadence.midi
            )
            cadences.append(
                (Run(phrase.cadence.start, phrase.cadence.length, cadence_midi), base_owners[-1])
            )
        tied_in = phrase.held_over and owners[-1] != "flute"
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
    """Root in F2–E3, and two upper guide tones inside A3–G#4.

    Seventh chords play the third and seventh; triads play the third and fifth.
    The fixed windows keep both hands within a few steps from one chord to the next.
    """
    pcs = tuple(pitch % 12 for pitch in chord.pitches)
    if len(pcs) == 4:
        root_pc, third_pc, _fifth_pc, upper_pc = pcs
    elif len(pcs) == 3:
        root_pc, third_pc, upper_pc = pcs
    else:
        raise ValueError(f"expected triad or seventh chord, got {len(pcs)} pitches")
    root = PIANO_ROOT_LOW + (root_pc - PIANO_ROOT_LOW) % 12
    guide = tuple(sorted(GUIDE_LOW + (pc - GUIDE_LOW) % 12 for pc in (third_pc, upper_pc)))
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
    """The root held for a bar and re-struck every two bars (or once on the outro pedal)."""
    root, _guide = comp_pitches(slot.chord)
    return [
        NoteEvent(
            bar=bar,
            beat=0.0,
            midi=(
                root
                if (offset == 0 if slot.section == "outro" else offset % 2 == 0)
                else None
            ),
            duration_beats=4.0,
            voice=5,
            staff=2,
        )
        for offset, bar in enumerate(slot.bars())
    ]


def _quantize_strong_beats(
    raw: list[int],
    chord_at: dict[int, Chord],
    scale: tuple[int, ...],
) -> list[int]:
    """Snap runs that land on or hold through beats 1 and 3 to the active chord.

    Weak-beat runs keep their diatonic scale tone as passing or neighbour notes.
    A run that spans a chord change snaps once to a tone shared by the chords on
    its strong beats when one lies within a scale step of the original note;
    otherwise (or when a run spans three or more chords with no common tone)
    each chord slot snaps its own span.
    """
    pitches = list(raw)
    previous: int | None = None
    previous_raw: int | None = None
    for run in runs_of(raw, 0, len(raw)):
        step = 0 if previous_raw is None else run.midi - previous_raw
        strong = [
            eighth
            for eighth in range(run.start, run.end)
            if eighth % EIGHTHS_PER_BAR in STRONG_EIGHTHS
        ]
        if not strong:
            previous = pitches[run.end - 1]
            previous_raw = run.midi
            continue
        common = frozenset.intersection(
            *(chord_at[eighth // EIGHTHS_PER_BAR].pitch_classes for eighth in strong)
        )
        if common:
            snapped = quantize_chord_tone(run.midi, common, scale, previous, step)
            if abs(scale.index(snapped) - scale.index(run.midi)) <= 1:
                for eighth in range(run.start, run.end):
                    pitches[eighth] = snapped
                previous = snapped
                previous_raw = run.midi
                continue
        cursor = run.start
        for index, beat_eighth in enumerate(strong):
            chord = chord_at[beat_eighth // EIGHTHS_PER_BAR]
            if (
                index + 1 < len(strong)
                and chord_at[strong[index + 1] // EIGHTHS_PER_BAR] == chord
            ):
                continue
            next_bar = (beat_eighth // EIGHTHS_PER_BAR + 1) * EIGHTHS_PER_BAR
            stop = run.end if index == len(strong) - 1 else min(run.end, next_bar)
            snapped = quantize_chord_tone(
                run.midi, chord.pitch_classes, scale, previous, step
            )
            for eighth in range(cursor, stop):
                pitches[eighth] = snapped
            previous = snapped
            cursor = stop
        previous_raw = run.midi
    return pitches


def render(
    bars: list[Bar],
    *,
    title: str = "1-Day Recap",
    regimes: tuple[Regime, Regime, Regime] | None = None,
) -> Score:
    """Turn one session of closes into flute, violin, cello, piano, bass, and symbols.

    Each phrase regime is the average of the first few source bars at that
    phrase's downbeat, then held for the phrase. Intro uses phrase 1's regime;
    outro uses phrase 3's. The melody stays on the C major home scale, snapping
    notes on strong beats (beats 1 and 3) to chord tones of the active chord
    while keeping non-chord scale tones on weak beats as passing notes. Piano
    touches the third, seventh, and root, and answers each phrase that closes
    on a held note with a short arpeggio.
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

    scale = c_major_scale()
    session_low = min(bar.close for bar in bars)
    session_high = max(bar.close for bar in bars)
    held_close = bars[0].close
    raw_pitches: list[int] = []
    for group in groups:
        if group:
            closes = [bars[index].close for index in group]
            held_close = closes[-1]
        else:
            closes = [held_close]
        for close in resample(closes, EIGHTHS_PER_BAR):
            raw_pitches.append(
                scale[price_to_scale_index(close, session_low, session_high, len(scale))]
            )

    slots = plan_slots(chosen, raw_pitches, scale)

    window_volumes = average_liquidity(
        [_window_candles(bars, groups, start, length) for start, length in LIQUIDITY_WINDOWS]
    )
    traded = [volume for volume in window_volumes if volume > 0]
    low_volume = percentile(traded, 0.10)
    high_volume = percentile(traded, 0.90)
    bands = [marking_for_volume(volume, low_volume, high_volume) for volume in window_volumes]
    dynamics = tuple(
        DynamicEvent(bar=start, marking=bass_marking(band), sound=SOUND[bass_marking(band)])
        for (start, _length), band in zip(LIQUIDITY_WINDOWS, bands)
    )
    harmonies = tuple(
        HarmonyEvent(slot.start, slot.chord)
        for index, slot in enumerate(slots)
        if index == 0 or slot.chord != slots[index - 1].chord
    )

    chord_at = {bar: slot.chord for slot in slots for bar in slot.bars()}
    pitches = _quantize_strong_beats(raw_pitches, chord_at, scale)
    raw_phrases = plan_phrases(
        raw_pitches, tuple(start * EIGHTHS_PER_BAR for start in SECTION_STARTS)
    )
    phrases = tuple(
        Phrase(
            phrase.start,
            phrase.end,
            tuple(
                part
                for run in phrase.runs
                for part in runs_of(pitches, run.start, run.end)
            ),
            phrase.held_over and pitches[phrase.end] == pitches[phrase.end - 1],
        )
        for phrase in raw_phrases
    )
    band_at = {
        bar: band
        for (start, length), band in zip(LIQUIDITY_WINDOWS, bands)
        for bar in range(start, start + length)
    }
    flute_notes, yield_spans = _flute_and_violin_dovetail(
        phrases, pitches, band_at, chord_at, scale
    )
    violin, cello, cadences = _melody_parts(pitches, phrases, band_at, yield_spans)
    piano: list[NoteEvent] = list(_right_hand(slots, _fills(cadences, chord_at)))
    bass: list[NoteEvent] = []
    for slot in slots:
        piano.extend(_left_hand(slot))
    for bar in range(MUSICAL_BARS):
        bass.extend(_bass_bar(chord_at[bar], band_at[bar], bar))

    return Score(
        title=title,
        bpm=BPM,
        bars=MUSICAL_BARS,
        regimes=chosen,
        regime_samples=sample_indexes,
        slots=slots,
        flute=_with_rests(flute_notes, TOTAL_EIGHTHS),
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
