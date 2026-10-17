"""Melodic phrases, cut where the price stalls or leaps.

A close that stays on one scale tone for several eighths is a held note. A
held note of at least PERIOD eighths (two beats) ends a phrase once the
phrase is MIN_EIGHTHS long; an earlier one stays inside the phrase. A phrase
that reaches MAX_EIGHTHS without one is cut after its longest COMMA-length
note, then after a BEAT_EIGHTHS-length note followed by a wide LEAP_SEMITONES,
then after its latest note change, and only then mid-note. A note cut mid-note
is held over into the next phrase rather than closing this one. Section starts
open a new phrase unless the closing phrase carries up to PERIOD eighths across
the bar line to finish on a held note or before a wide leap.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.sonify.chords import Chord
from app.sonify.dynamics import SOUND
from app.sonify.form import EIGHTHS_PER_BAR, HALF_BAR, TOTAL_EIGHTHS, ChordSlot
from app.sonify.model import PERIOD, DynamicEvent, NoteEvent, Phrase, Run, WedgeEvent
from app.sonify.quantize import quantize_chord_tone

COMMA = 3
BEAT_EIGHTHS = 2
LEAP_SEMITONES = 5
MIN_EIGHTHS = 8
MAX_EIGHTHS = 32

VIOLIN_LOWEST = 55  # G3
CELLO_HANDBACK = 60  # C4
CELLO_OVERLAP = 2  # eighths (1 beat) of dovetail overlap when Violin and Cello hand off
VIOLIN_CEILING = 84  # C6: notes above C6 fold down an octave so Violin never shrieks
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


def runs_of(pitches: list[int], start: int, end: int) -> list[Run]:
    runs: list[Run] = []
    for index in range(start, end):
        midi = pitches[index]
        if runs and runs[-1].midi == midi:
            runs[-1] = Run(runs[-1].start, runs[-1].length + 1, midi)
        else:
            runs.append(Run(index, 1, midi))
    return runs


def _clip(runs: list[Run], start: int, end: int) -> tuple[Run, ...]:
    clipped: list[Run] = []
    for run in runs:
        low = max(run.start, start)
        high = min(run.end, end)
        if low < high:
            clipped.append(Run(low, high - low, run.midi))
    return tuple(clipped)


def _leap_after(run: Run, midi_at: dict[int, int]) -> int:
    following = midi_at.get(run.end)
    return abs(following - run.midi) if following is not None else 0


def _cut(
    runs: list[Run],
    midi_at: dict[int, int],
    start: int,
    end: int,
    *,
    tied_in: bool = False,
) -> int:
    """Where the phrase opened at start ends, inside a section ending at end."""
    low = start + MIN_EIGHTHS
    high = min(start + MAX_EIGHTHS, end - MIN_EIGHTHS)
    candidates = [
        run
        for run in runs
        if low <= run.end <= high and not (tied_in and run.start < start)
    ]

    def held(run: Run) -> int:
        return run.end - max(run.start, start)

    for run in candidates:
        if held(run) >= PERIOD:
            return run.end
    if end - start <= MAX_EIGHTHS:
        return end
    commas = [run for run in candidates if held(run) >= COMMA]
    if commas:
        return max(commas, key=lambda run: (held(run), run.end)).end
    leaps = [
        run
        for run in candidates
        if held(run) >= BEAT_EIGHTHS and _leap_after(run, midi_at) >= LEAP_SEMITONES
    ]
    if leaps:
        return max(
            leaps, key=lambda run: (_leap_after(run, midi_at), held(run), run.end)
        ).end
    changes = [run for run in runs if low <= run.end <= high]
    if changes:
        return changes[-1].end
    return high


def _settle_edge(
    runs: list[Run],
    midi_at: dict[int, int],
    start: int,
    edge: int,
    next_edge: int,
) -> int:
    """Let a phrase carry up to PERIOD eighths across a section bar line to resolve."""
    high = min(edge + PERIOD, start + MAX_EIGHTHS, next_edge - MIN_EIGHTHS)
    if high <= edge:
        return edge

    def held(run: Run) -> int:
        return run.end - max(run.start, start)

    at_edge = next((run for run in runs if run.start < edge <= run.end), None)
    if at_edge is not None:
        if at_edge.end == edge and held(at_edge) >= COMMA:
            return edge
        if edge - max(at_edge.start, start) >= PERIOD:
            return edge

    after = [run for run in runs if edge < run.end <= high]
    for run in after:
        if held(run) >= PERIOD:
            return run.end
    commas = [run for run in after if held(run) >= COMMA]
    if commas:
        return max(commas, key=lambda run: (held(run), run.end)).end
    leaps = [
        run
        for run in after
        if held(run) >= BEAT_EIGHTHS and _leap_after(run, midi_at) >= LEAP_SEMITONES
    ]
    if leaps:
        return max(
            leaps, key=lambda run: (_leap_after(run, midi_at), held(run), run.end)
        ).end
    return edge


def plan_phrases(pitches: list[int], section_starts: tuple[int, ...]) -> tuple[Phrase, ...]:
    """Phrases over a line of one pitch per eighth; section starts are eighth indexes."""
    total = len(pitches)
    bounds = sorted({0, *(start for start in section_starts if 0 < start < total)})
    bounds.append(total)
    section_set = set(bounds)
    runs = runs_of(pitches, 0, total)
    midi_at = {run.start: run.midi for run in runs}
    phrases: list[Phrase] = []
    cursor = 0
    for index, edge in enumerate(bounds[1:], 1):
        while cursor < edge:
            tied_in = bool(phrases and phrases[-1].held_over)
            cut = _cut(runs, midi_at, cursor, edge, tied_in=tied_in)
            if cut == edge and edge < total:
                cut = _settle_edge(runs, midi_at, cursor, edge, bounds[index + 1])
            held_over = (
                cut < total and cut not in section_set and pitches[cut] == pitches[cut - 1]
            )
            phrases.append(Phrase(cursor, cut, _clip(runs, cursor, cut), held_over))
            cursor = cut
    return tuple(phrases)


def swell(phrase: Phrase, onset: int) -> float:
    """0 at the phrase edges and 1 at the apex, linear in between."""
    apex = phrase.apex.start
    if onset <= apex:
        if apex == phrase.start:
            return 1.0
        return (onset - phrase.start) / (apex - phrase.start)
    return 1.0 - (onset - apex) / (phrase.end - apex)


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


def comp_pitches(chord: Chord) -> tuple[int, tuple[int, int]]:
    """Root in F2–E3, and two upper guide tones inside A3–G#4.

    Seventh chords play the third and seventh; triads play the third and fifth.
    The fixed windows keep both hands within a few steps from one chord to the next.
    """
    pcs = tuple(pitch % 12 for pitch in chord.pitches)
    if len(pcs) >= 4:
        root_pc, third_pc, _fifth_pc, upper_pc = pcs[:4]
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
