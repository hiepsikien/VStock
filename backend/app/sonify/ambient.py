"""Ambient score: a held bed, a thinned glass line, rare swells and shimmer.

The form, Markov chords, and phrases already exist. This module only writes
the five parts. Silence is the default, and a rest still belongs to its section.
"""

from __future__ import annotations

from app.sonify.chords import Chord, Regime, fifth_above_bass, jazz_chord
from app.sonify.dynamics import COOLDOWN_MARKING, SOUND
from app.sonify.form import (
    active_meter,
    ChordSlot,
    FormSection,
    FormSpec,
)
from app.sonify.keys import active_register
from app.sonify.model import (
    Bar,
    DynamicEvent,
    HarmonyEvent,
    NoteEvent,
    Phrase,
    Run,
    Score,
    WedgeEvent,
)
from app.sonify.phrasing import (
    BREAKOUT,
    MIN_RISE,
    BELL_MAX_EIGHTHS,
    _wedge_at,
    bell_budget,
    comp_pitches,
    hairpins,
    techniques,
    with_rests,
    written,
)

AMBIENT_BPM = 60
# A cool-down may keep sounding the note that touches it, up to five bars
# from the start of that breath. It does not open a second drone.
COOLDOWN_HOLD = 40
LEAP = 5
PILLARS_PER_EIGHT = 2
SHIMMER_GAP_BARS = 4
SWELL_GAP_BARS = 4
SHIMMER_TRIGGER = 76
SHIMMER_VELOCITY = 90
GLASS_VELOCITY = 60
SWELL_OPEN_VELOCITY = 49
SWELL_MP_VELOCITY = 64
SWELL_VELOCITY = 80


def _hold(raw: int) -> int:
    """Round an eighth-count onto the active bar, between one bar and 36 eighths."""
    epb = active_meter().eighths_per_bar
    if epb == 8:
        return raw
    table = {
        (32, 6): 30,
        (24, 6): 24,
        (16, 6): 12,
        (8, 6): 6,
        (32, 12): 36,
        (24, 12): 24,
        (16, 12): 12,
        (8, 12): 6,
    }
    return table.get((raw, epb), raw)


GLASS_HOLD = 32
FLAT_HOLD = 32
PILLAR_GAP = 24
SWELL_HOLD = 16
SHIMMER_EIGHTHS = 8
_DRONE_MARKING = {"p": "p", "mp": "mp", "mf": "mp", "f": "mp"}
_DRONE_VELOCITY = {"p": 52, "mp": 58, "mf": 64, "f": 68}
_FIFTH_VELOCITY = 48
_HALO_VELOCITY = {"p": 40, "mp": 46, "mf": 50, "f": 54}


def _middle(form: FormSpec, bar: int) -> bool:
    return any(section.bridge and section.start <= bar < section.end for section in form.sections)


def promote_ambient_slots(
    slots: tuple[ChordSlot, ...],
) -> tuple[tuple[ChordSlot, ...], tuple[HarmonyEvent, ...], dict[int, Chord]]:
    """Promote each slot, then join neighbours that become the same jazz chord."""
    merged: list[ChordSlot] = []
    for slot in slots:
        chord = jazz_chord(slot.chord)
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and previous.chord == chord
            and previous.start + previous.length == slot.start
        ):
            merged[-1] = ChordSlot(
                previous.start,
                previous.length + slot.length,
                chord,
                previous.regime,
                previous.section,
            )
            continue
        merged.append(
            ChordSlot(slot.start, slot.length, chord, slot.regime, slot.section)
        )
    harmonies = tuple(
        HarmonyEvent(slot.start, slot.chord)
        for index, slot in enumerate(merged)
        if index == 0 or slot.chord != merged[index - 1].chord
    )
    chord_at = {bar: slot.chord for slot in merged for bar in slot.bars()}
    return tuple(merged), harmonies, chord_at


def _clip_runs(runs: tuple[Run, ...], start: int, end: int) -> tuple[Run, ...]:
    clipped: list[Run] = []
    for run in runs:
        low = max(run.start, start)
        high = min(run.end, end)
        if low < high:
            clipped.append(Run(low, high - low, run.midi))
    return tuple(clipped)


def _phrases_inside(
    phrases: tuple[Phrase, ...], start_bar: int, end_bar: int
) -> tuple[Phrase, ...]:
    """Phrases that open inside the section, with any spill past the end removed."""
    start = start_bar * active_meter().eighths_per_bar
    end = end_bar * active_meter().eighths_per_bar
    kept: list[Phrase] = []
    for phrase in phrases:
        if phrase.start < start or phrase.start >= end:
            continue
        stop = min(phrase.end, end)
        runs = _clip_runs(phrase.runs, phrase.start, stop)
        if not runs:
            continue
        held = phrase.held_over and phrase.end <= end
        kept.append(Phrase(runs[0].start, runs[-1].end, runs, held))
    return tuple(kept)


def _fold_glass(midi: int, previous: int | None = None) -> int:
    low = active_register().violin_lowest
    high = active_register().violin_ceiling
    while midi > high:
        midi -= 12
    while midi < low:
        midi += 12
    if previous is None:
        return midi
    while midi - previous > 12 and midi - 12 >= low:
        midi -= 12
    while previous - midi > 12 and midi + 12 <= high:
        midi += 12
    return midi


def _one_per_bar(runs: list[Run]) -> list[Run]:
    kept: list[Run] = []
    for run in runs:
        bar_start = (run.start // active_meter().eighths_per_bar) * active_meter().eighths_per_bar
        if kept and kept[-1].start == bar_start:
            continue
        kept.append(Run(bar_start, run.length, run.midi))
    return kept


def _pillars(
    section: FormSection,
    phrases: tuple[Phrase, ...],
    pitches: list[int],
    previous_midi: int | None = None,
) -> list[Run]:
    start = section.start * active_meter().eighths_per_bar
    end = section.end * active_meter().eighths_per_bar
    if not phrases:
        return [Run(start, 1, _fold_glass(pitches[start], previous_midi))]
    covered = next(
        (run for phrase in phrases for run in phrase.runs if run.start <= start < run.end),
        None,
    )
    opening = covered if covered is not None else Run(start, 1, pitches[start])
    closing = phrases[-1].runs[-1]
    apex_starts = {
        phrase.apex.start
        for phrase in phrases
        if phrase.rise >= MIN_RISE
        and phrase.apex.start != opening.start
        and phrase.apex.start != closing.start
    }
    apex_bars = {pos // active_meter().eighths_per_bar for pos in apex_starts}
    kept: list[Run] = [opening]
    for phrase in phrases:
        if phrase.apex.start in apex_starts:
            kept.append(phrase.apex)
    kept.sort(key=lambda run: run.start)
    for phrase in phrases:
        for run in phrase.runs:
            if any(run.start == pillar.start for pillar in kept):
                continue
            earlier = sorted(
                (pillar for pillar in kept if pillar.start < run.start),
                key=lambda pillar: pillar.start,
            )
            if earlier and abs(run.midi - earlier[-1].midi) >= LEAP:
                kept.append(run)
    if all(run.start != closing.start for run in kept):
        kept.append(closing)
    kept.sort(key=lambda run: run.start)
    kept = _one_per_bar(kept)
    from app.sonify.groove import groove_at

    def _gap(start: int) -> int:
        gap = _hold(PILLAR_GAP)
        if groove_at(start // max(active_meter().eighths_per_bar, 1)).calm:
            gap += active_meter().eighths_per_bar
        return gap

    kept = [
        run
        for index, run in enumerate(kept)
        if index == 0 or end - run.start >= _gap(run.start)
    ]
    folded: list[Run] = []
    last_midi = previous_midi
    for run in kept:
        midi = _fold_glass(run.midi, last_midi)
        folded.append(Run(run.start, run.length, midi))
        last_midi = midi
    kept = folded
    spaced: list[Run] = []
    for run in kept:
        if not spaced or run.start - spaced[-1].start >= _hold(PILLAR_GAP):
            spaced.append(run)
            continue
        prev = spaced[-1]
        run_is_apex = (run.start // active_meter().eighths_per_bar) in apex_bars
        prev_is_apex = (prev.start // active_meter().eighths_per_bar) in apex_bars
        if prev.start != kept[0].start and run_is_apex and not prev_is_apex:
            spaced[-1] = run
    kept = spaced
    section_eighths = (section.end - section.start) * active_meter().eighths_per_bar
    cap = 2 * section_eighths // 64
    if cap < 1:
        cap = 1
    if len(kept) > cap:
        must = {kept[0].start}
        if (
            len(kept) > 1
            and kept[-1].start - kept[0].start >= _hold(GLASS_HOLD)
            and end - kept[-1].start >= _hold(PILLAR_GAP)
        ):
            must.add(kept[-1].start)
        extra = [run for run in kept if run.start not in must]
        extra.sort(
            key=lambda run: (
                (run.start // active_meter().eighths_per_bar) in apex_bars,
                abs(run.midi - kept[0].midi),
            )
        )
        drop: set[int] = set()
        for run in extra:
            if len(kept) - len(drop) <= cap:
                break
            drop.add(run.start)
        kept = [run for run in kept if run.start not in drop]
    thinned = [kept[0]]
    for run in kept[1:]:
        previous = thinned[-1]
        distant = run.midi == previous.midi and run.start - previous.start > _hold(GLASS_HOLD)
        if distant and run.start != kept[-1].start:
            continue
        thinned.append(run)
    return thinned


def _place(pillars: list[Run], section_end: int, *, hold: int) -> list[tuple[int, int, int, bool]]:
    """(start, length, midi, slur into the next pillar) inside one section."""
    placed: list[tuple[int, int, int, bool]] = []
    index = 0
    while index < len(pillars):
        pillar = pillars[index]
        limit = pillar.start + hold
        nxt = index + 1
        while nxt < len(pillars) and pillars[nxt].midi == pillar.midi and pillars[nxt].start <= limit:
            nxt += 1
        if nxt < len(pillars) and pillars[nxt].midi != pillar.midi and pillars[nxt].start - pillar.start <= hold:
            length = pillars[nxt].start - pillar.start
            slur = True
        else:
            length = min(hold, section_end - pillar.start)
            slur = False
        if length > 0:
            placed.append((pillar.start, length, pillar.midi, slur))
        index = nxt if nxt > index else index + 1
    return placed


def _breath_eighths(
    kept: list[tuple[int, int, int, bool, bool, bool]], midi: int, at: int
) -> int:
    """How long the contiguous same-pitch breath has already sounded at `at`."""
    start = at
    for seg_start, seg_length, seg_midi, *_rest in reversed(kept):
        if seg_midi != midi or seg_start + seg_length != start:
            break
        start = seg_start
    return at - start


def _omit_same_pitch_reattacks(
    segments: list[tuple[int, int, int, bool, bool, bool]],
) -> list[tuple[int, int, int, bool, bool, bool]]:
    """Finish a breath that reaches the next bar, and do not tongue it again.

    A same pitch that merely touches is tied on for whatever is left of the
    four-bar hold, then released. A same pitch after a rest is dropped. A
    breath that already lasts ``_hold(GLASS_HOLD)`` releases at the boundary. Tied
    intro notes stay as written. The line speaks again when the pitch moves.
    """
    kept: list[tuple[int, int, int, bool, bool, bool]] = []
    for start, length, midi, slur, tie_in, tie_out in segments:
        if kept:
            prev_start, prev_length, prev_midi, _prev_slur, prev_tie_in, prev_tie_out = kept[-1]
            touches = prev_start + prev_length == start
            linked = touches and (kept[-1][3] or prev_tie_out or tie_in)
            if midi == prev_midi and not linked:
                if touches:
                    room = _hold(GLASS_HOLD) - _breath_eighths(kept, midi, start)
                    if room > 0:
                        take = min(length, room)
                        kept[-1] = (
                            prev_start,
                            prev_length + take,
                            midi,
                            slur if take == length else False,
                            prev_tie_in,
                            False,
                        )
                continue
            if not touches:
                kept[-1] = (prev_start, prev_length, prev_midi, False, prev_tie_in, False)
                tie_in = False
        kept.append((start, length, midi, slur, tie_in, tie_out))
    if kept:
        start, length, midi, _slur, tie_in, _tie_out = kept[-1]
        kept[-1] = (start, length, midi, False, tie_in, False)
    return kept


def _emit(segments: list[tuple[int, int, int, bool, bool, bool]]) -> list[NoteEvent]:
    """segments are start, length, midi, slur-into-next, tie-in, tie-out."""
    notes: list[NoteEvent] = []
    for index, (start, length, midi, slur, tie_in, tie_out) in enumerate(segments):
        previous_slur = index > 0 and segments[index - 1][3]
        notes.extend(
            written(
                start,
                length,
                midi,
                slur_start=slur,
                slur_stop=previous_slur,
                velocity=GLASS_VELOCITY,
                tenuto=not tie_in and not previous_slur,
                tie_in=tie_in,
                tie_out=tie_out,
            )
        )
    return notes


def _breath(
    start: int,
    length: int,
    *,
    peak_marking: str = "mp",
) -> tuple[list[WedgeEvent], list[DynamicEvent]]:
    """Open at peak_marking and fade slowly across the entire held span."""
    end = start + length
    wedges = hairpins(start, end, start)
    dynamics = [
        DynamicEvent(
            bar=start // active_meter().eighths_per_bar,
            marking=peak_marking,
            sound=SOUND[peak_marking],
            beat=(start % active_meter().eighths_per_bar) * 0.5,
        )
    ]
    return wedges, dynamics


def _arc_breaths(
    segments: list[tuple[int, int, int, bool, bool, bool]],
    prev_arc_midi: int | None = None,
) -> tuple[list[WedgeEvent], list[DynamicEvent]]:
    """One diminuendo for each tied or slurred chain."""
    wedges: list[WedgeEvent] = []
    dynamics: list[DynamicEvent] = []
    index = 0
    while index < len(segments):
        arc_start = segments[index][0]
        arc_midis = [segments[index][2]]
        end_idx = index
        while (
            end_idx + 1 < len(segments)
            and (segments[end_idx][3] or segments[end_idx][5])
            and segments[end_idx][0] + segments[end_idx][1] == segments[end_idx + 1][0]
        ):
            end_idx += 1
            arc_midis.append(segments[end_idx][2])
        arc_end = segments[end_idx][0] + segments[end_idx][1]
        step = abs(arc_midis[0] - prev_arc_midi) if prev_arc_midi is not None else 0
        peak = (
            "mf"
            if max(arc_midis) - min(arc_midis) >= MIN_RISE or step >= MIN_RISE
            else "mp"
        )
        arc_wedges, arc_dynamics = _breath(arc_start, arc_end - arc_start, peak_marking=peak)
        wedges.extend(arc_wedges)
        dynamics.extend(arc_dynamics)
        prev_arc_midi = arc_midis[-1]
        index = end_idx + 1
    return wedges, dynamics


def _tonic_glass(chord: Chord, neighbor: int | None) -> int:
    """The chord's root inside the flute register, within an octave of `neighbor`."""
    pitch_class = chord.pitches[0] % 12
    low = active_register().violin_lowest
    high = active_register().violin_ceiling
    seeds = [note for note in range(low, high + 1) if note % 12 == pitch_class]
    if not seeds:
        return _fold_glass(60 + pitch_class, neighbor)
    if neighbor is None:
        middle = (low + high) // 2
        return min(seeds, key=lambda note: (abs(note - middle), note))
    return min(seeds, key=lambda note: (abs(note - neighbor) > 12, abs(note - neighbor), note))


def _attach_daily_frames(
    segments: list[tuple[int, int, int, bool, bool, bool]],
    form: FormSpec,
    chord_at: dict[int, Chord],
) -> list[tuple[int, int, int, bool, bool, bool]]:
    """Prepend a tonic warm-up and append a tonic cool-down.

    Neither frame reads the price inside its bars. A cool-down on the same
    pitch follows the four-bar breath rule, except a note that still touches
    it may sound on for whatever is left of five bars, then rests. The same
    pitch after a rest is not tongued again. A different pitch holds the
    cool-down.
    """
    intro = next(section for section in form.sections if section.kind == "intro")
    outro = next((section for section in form.sections if section.kind == "outro"), None)
    intro_start = intro.start * active_meter().eighths_per_bar
    intro_end = intro.end * active_meter().eighths_per_bar
    neighbor = segments[0][2] if segments else None
    intro_midi = _tonic_glass(chord_at[intro.start], neighbor)
    tie = bool(segments) and segments[0][0] == intro_end and segments[0][2] == intro_midi
    if tie:
        start, length, midi, slur, _tie_in, tie_out = segments[0]
        segments[0] = (start, length, midi, slur, True, tie_out)
    segments.insert(0, (intro_start, intro_end - intro_start, intro_midi, False, False, tie))
    if outro is None or outro.start not in chord_at:
        return segments
    outro_start = outro.start * active_meter().eighths_per_bar
    outro_end = min(outro.end * active_meter().eighths_per_bar, outro.start * active_meter().eighths_per_bar + (outro.end - outro.start) * active_meter().eighths_per_bar)
    length = outro_end - outro_start
    if length <= 0:
        return segments
    prev_start, prev_length, prev_midi, prev_slur, prev_tie_in, prev_tie_out = segments[-1]
    outro_midi = _tonic_glass(chord_at[outro.start], prev_midi)
    touches = prev_start + prev_length == outro_start
    same = prev_midi == outro_midi
    if same:
        if touches:
            room = COOLDOWN_HOLD - _breath_eighths(segments, prev_midi, outro_start)
            if room > 0:
                take = min(length, room)
                segments[-1] = (
                    prev_start,
                    prev_length + take,
                    prev_midi,
                    False,
                    prev_tie_in,
                    False,
                )
                return segments
        if touches and (prev_slur or prev_tie_out):
            segments[-1] = (prev_start, prev_length, prev_midi, False, prev_tie_in, False)
        return segments
    if touches and (prev_slur or prev_tie_out):
        segments[-1] = (prev_start, prev_length, prev_midi, False, prev_tie_in, False)
    segments.append((outro_start, length, outro_midi, False, False, False))
    return segments


def _daily_frame_breaths(
    segments: list[tuple[int, int, int, bool, bool, bool]],
    form: FormSpec,
) -> tuple[list[WedgeEvent], list[DynamicEvent]]:
    """Warm-up grows from p to the phrase. Cool-down leaves mp and settles to ppp."""
    intro = next(section for section in form.sections if section.kind == "intro")
    outro = next((section for section in form.sections if section.kind == "outro"), None)
    intro_end = intro.end * active_meter().eighths_per_bar
    outro_start = outro.start * active_meter().eighths_per_bar if outro is not None else 10**9
    intro_midi = next(segment[2] for segment in segments if segment[0] < intro_end)
    phrase_segments = [segment for segment in segments if intro_end <= segment[0] < outro_start]
    outro_segments = [segment for segment in segments if segment[0] >= outro_start]
    wedges = [_wedge_at(intro.start * active_meter().eighths_per_bar, "crescendo"), WedgeEvent(intro.end, 0.0, "stop")]
    dynamics = [
        DynamicEvent(
            bar=intro.start,
            marking="p",
            sound=SOUND["p"],
            beat=0.0,
        )
    ]
    phrase_wedges, phrase_dynamics = _arc_breaths(phrase_segments, intro_midi)
    wedges.extend(phrase_wedges)
    dynamics.extend(phrase_dynamics)
    if outro_segments:
        start, length, _midi, _slur, tie_in, _tie_out = outro_segments[0]
        end = start + length
        if not tie_in:
            dynamics.append(
                DynamicEvent(
                    bar=start // active_meter().eighths_per_bar,
                    marking="mp",
                    sound=SOUND["mp"],
                    beat=(start % active_meter().eighths_per_bar) * 0.5,
                )
            )
        last = max(start // active_meter().eighths_per_bar, end // active_meter().eighths_per_bar - 1)
        wedges.append(_wedge_at(start, "diminuendo"))
        wedges.append(WedgeEvent(last, 0.0, "stop"))
        dynamics.append(
            DynamicEvent(
                bar=last,
                marking=COOLDOWN_MARKING,
                sound=SOUND[COOLDOWN_MARKING],
                beat=0.0,
            )
        )
    return wedges, dynamics


def _glass(
    form: FormSpec,
    phrases: tuple[Phrase, ...],
    pitches: list[int],
    *,
    frame: bool = False,
    chord_at: dict[int, Chord] | None = None,
) -> tuple[list[NoteEvent], list[WedgeEvent], list[DynamicEvent]]:
    segments: list[tuple[int, int, int, bool, bool, bool]] = []
    last_midi: int | None = None
    phrase_sections = [section for section in form.sections if section.kind == "phrase"]
    for section in phrase_sections:
        inside = _phrases_inside(phrases, section.start, section.end)
        end = section.end * active_meter().eighths_per_bar
        span = pitches[section.start * active_meter().eighths_per_bar : end]
        flat = not span or max(span) - min(span) < MIN_RISE
        if flat:
            opening_at = section.start * active_meter().eighths_per_bar
            length = min(_hold(FLAT_HOLD), end - opening_at)
            folded = _fold_glass(pitches[opening_at], last_midi)
            placed = [(opening_at, length, folded, False)] if length > 0 else []
        else:
            placed = _place(_pillars(section, inside, pitches, last_midi), end, hold=_hold(GLASS_HOLD))
        for start, length, midi, slur in placed:
            segments.append((start, length, midi, slur, False, False))
            last_midi = midi

    if frame and chord_at is not None:
        segments = _attach_daily_frames(_omit_same_pitch_reattacks(segments), form, chord_at)
        wedges, dynamics = _daily_frame_breaths(segments, form)
        return _emit(segments), wedges, dynamics

    intro = next((section for section in form.sections if section.kind == "intro"), None)
    if intro is not None and segments:
        intro_start = intro.start * active_meter().eighths_per_bar
        intro_end = intro.end * active_meter().eighths_per_bar
        first = segments[0]
        tie = first[0] == intro_end and intro_end > intro_start
        segments.insert(0, (intro_start, intro_end - intro_start, first[2], False, False, tie))
        if tie:
            start, length, midi, slur, _tie_in, tie_out = segments[1]
            segments[1] = (start, length, midi, slur, True, tie_out)

    outro = next((section for section in form.sections if section.kind == "outro"), None)
    if outro is not None and pitches:
        outro_start = outro.start * active_meter().eighths_per_bar
        outro_end = min(outro.end * active_meter().eighths_per_bar, len(pitches))
        if outro_end > outro_start:
            outro_midi = _fold_glass(pitches[outro_end - 1], last_midi)
            segments.append(
                (outro_start, outro_end - outro_start, outro_midi, False, False, False)
            )

    segments = _omit_same_pitch_reattacks(segments)
    wedges, dynamics = _arc_breaths(segments)
    return _emit(segments), wedges, dynamics


def _bed_marking(band: str) -> str:
    return _DRONE_MARKING.get(band, "mp")


def _bed_dynamics(windows: list[tuple[int, int]] | tuple[tuple[int, int], ...], bands: list[str]) -> tuple[DynamicEvent, ...]:
    events: list[DynamicEvent] = []
    previous: str | None = None
    for (start, _length), band in zip(windows, bands):
        marking = _bed_marking(band)
        if marking == previous:
            continue
        events.append(DynamicEvent(bar=start, marking=marking, sound=SOUND[marking]))
        previous = marking
    return tuple(events)


def _quiet_frame_bands(
    form: FormSpec,
    windows: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    bands: list[str],
    band_at: dict[int, str],
) -> tuple[list[str], dict[int, str]]:
    """Warm-up stays p. Cool-down stays mp, so neither frame grows a fifth."""
    kind_at = {
        bar: section.kind
        for section in form.sections
        for bar in range(section.start, section.end)
    }
    framed = dict(band_at)
    for bar, kind in kind_at.items():
        if kind == "intro":
            framed[bar] = "p"
        elif kind == "outro":
            framed[bar] = "mp"
    quiet = [
        "p" if kind_at.get(start) == "intro" else "mp" if kind_at.get(start) == "outro" else band
        for (start, _length), band in zip(windows, bands)
    ]
    return quiet, framed


def _framed_bed_dynamics(
    windows: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    bands: list[str],
    form: FormSpec,
) -> tuple[DynamicEvent, ...]:
    """p rising to mp across the warm-up, then volume, then mp falling to ppp."""
    intro = next(section for section in form.sections if section.kind == "intro")
    phrase = next(section for section in form.sections if section.kind == "phrase")
    outro = next((section for section in form.sections if section.kind == "outro"), None)
    events: list[DynamicEvent] = []
    previous: str | None = None

    def add(bar: int, marking: str) -> None:
        nonlocal previous
        if marking == previous:
            return
        events.append(DynamicEvent(bar=bar, marking=marking, sound=SOUND[marking]))
        previous = marking

    add(intro.start, "p")
    add(phrase.start, "mp")
    for (start, _length), band in zip(windows, bands):
        if start <= phrase.start:
            continue
        if outro is not None and start >= outro.start:
            continue
        add(start, _bed_marking(band))
    if outro is not None:
        add(outro.start, "mp")
        add(outro.end - 1, COOLDOWN_MARKING)
    return tuple(events)


def _frame_bed_wedges(form: FormSpec) -> tuple[WedgeEvent, ...]:
    intro = next(section for section in form.sections if section.kind == "intro")
    outro = next((section for section in form.sections if section.kind == "outro"), None)
    wedges = [
        _wedge_at(intro.start * active_meter().eighths_per_bar, "crescendo"),
        WedgeEvent(intro.end, 0.0, "stop"),
    ]
    if outro is not None:
        wedges.append(_wedge_at(outro.start * active_meter().eighths_per_bar, "diminuendo"))
        wedges.append(WedgeEvent(outro.end - 1, 0.0, "stop"))
    return tuple(wedges)


def _halo_midis(chord: Chord) -> tuple[int, ...]:
    """Low, warm guide tones in D3–C#4 (50..61) for a soft Bass Flute murmur."""
    _root, guide = comp_pitches(chord)
    return tuple(sorted(midi - 12 if midi >= 62 else midi for midi in guide))


def _sustain(
    per_bar: list[tuple[int, ...]],
    velocity_at: list[int | None],
) -> list[NoteEvent]:
    active: dict[int, tuple[int, int | None]] = {}
    spans: list[tuple[int, int, int, int | None]] = []
    for bar, midis in enumerate(per_bar):
        sounding = set(midis)
        for midi in list(active):
            if midi not in sounding:
                start, velocity = active.pop(midi)
                spans.append((start, bar * active_meter().eighths_per_bar - start, midi, velocity))
        for midi in midis:
            if midi not in active:
                active[midi] = (bar * active_meter().eighths_per_bar, velocity_at[bar])
    last = len(per_bar) * active_meter().eighths_per_bar
    for midi, (start, velocity) in active.items():
        spans.append((start, last - start, midi, velocity))
    notes: list[NoteEvent] = []
    for start, length, midi, velocity in spans:
        if length <= 0:
            continue
        notes.extend(written(start, length, midi, velocity=velocity))
    return notes


def _swell(
    form: FormSpec,
    windows: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    bands: list[str],
    chord_at: dict[int, Chord],
) -> list[NoteEvent]:
    kind_at = {
        bar: section.kind
        for section in form.sections
        for bar in range(section.start, section.end)
    }
    section_end_at = {
        bar: section.end
        for section in form.sections
        for bar in range(section.start, section.end)
    }
    notes: list[NoteEvent] = []
    chosen_bars: list[int] = []
    for (start, length), band in zip(windows, bands):
        if band not in ("mf", "f") or length < 2:
            continue
        bar = start + 1
        if kind_at.get(bar) != "phrase" or bar not in chord_at:
            continue
        from app.sonify.groove import groove_at

        if groove_at(bar).trio_thin:
            continue
        gap = 3 if groove_at(bar).volatile else SWELL_GAP_BARS
        if any(abs(bar - other) < gap for other in chosen_bars):
            continue
        chosen_bars.append(bar)
        chord = chord_at[bar]
        high_tones = [note for note in range(60, 70) if note % 12 in chord.pitch_classes]
        top = high_tones[-1]
        low_tones = [
            note
            for note in range(max(45, top - 16), top - 7)
            if note % 12 in chord.pitch_classes and (top - note) % 12 not in (1, 2, 10, 11)
        ]
        bottom = low_tones[0] if low_tones else max(48, top - 12)
        mid_tones = [
            note
            for note in range(bottom + 3, top - 2)
            if note % 12 in chord.pitch_classes
            and (note - bottom) % 12 not in (0, 1, 2, 10, 11)
            and (top - note) % 12 not in (0, 1, 2, 10, 11)
        ]
        if not mid_tones:
            mid_tones = [
                note
                for note in range(bottom + 3, top - 2)
                if note % 12 in chord.pitch_classes
            ]
        middle = min(mid_tones, key=lambda note: abs(note - (bottom + top) / 2))
        if groove_at(bar).selloff:
            top -= 12
            bottom -= 12
            middle -= 12
        peak_vel = SWELL_VELOCITY if band == "f" else SWELL_MP_VELOCITY
        hold_eighths = min(
            _hold(SWELL_HOLD),
            (section_end_at.get(bar, bar + 1) - bar) * active_meter().eighths_per_bar,
        )
        half = hold_eighths // 2
        start_eighth = bar * active_meter().eighths_per_bar
        for midi in (bottom, middle, top):
            notes.extend(
                written(
                    start_eighth,
                    half,
                    midi,
                    velocity=SWELL_OPEN_VELOCITY,
                    tie_out=True,
                )
            )
            notes.extend(
                written(
                    start_eighth + half,
                    hold_eighths - half,
                    midi,
                    velocity=peak_vel,
                    tie_in=True,
                )
            )
    return notes


def _body_window(form: FormSpec, chunk: tuple[int, int]) -> tuple[int, int]:
    """Clip a chunk to the body. Warm-up and cool-down stay outside the shimmer budget."""
    warm = 0
    cool = form.bars
    for section in form.sections:
        if section.kind == "warmup":
            warm = max(warm, section.end)
        elif section.kind == "cooldown":
            cool = min(cool, section.start)
    return max(chunk[0], warm), min(chunk[1], cool)


def _chunk_span(bars: list[Bar], groups: list[list[int]], start: int, end: int) -> float:
    from app.sonify.render import _section_rel_span

    return _section_rel_span(bars, groups, start, end)


def _shimmer(
    form: FormSpec,
    phrases: tuple[Phrase, ...],
    pitches: list[int],
    chord_at: dict[int, Chord],
    source_bars: list[Bar],
    source_groups: list[list[int]],
) -> list[NoteEvent]:
    quiet: set[int] = set()
    for section in form.sections:
        if section.kind == "outro" and section.end - section.start >= 2:
            quiet.add(section.end - 1)
            quiet.add(section.end - 2)
    candidates: list[tuple[float, int, int]] = []
    for section in form.sections:
        if section.kind != "phrase":
            continue
        for phrase in _phrases_inside(phrases, section.start, section.end):
            colours = techniques(phrase, pitches)
            for run in phrase.runs:
                breakout = colours.get(run.start) == BREAKOUT and run.midi >= SHIMMER_TRIGGER
                apex = run.start == phrase.apex.start and phrase.apex.midi >= SHIMMER_TRIGGER and phrase.rise >= MIN_RISE
                if not breakout and not apex:
                    continue
                bar = run.start // active_meter().eighths_per_bar
                from app.sonify.groove import groove_at

                if bar in quiet or bar not in chord_at or groove_at(bar).caesura:
                    continue
                candidates.append((phrase.rise, bar, _shimmer_midi(run.midi, chord_at[bar])))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    chosen_bars: list[int] = []
    notes: list[NoteEvent] = []
    used: dict[tuple[int, int], int] = {}
    for _rise, bar, midi in candidates:
        chunk = next(
            (bounds for bounds in form.chunk_bounds() if bounds[0] <= bar < bounds[1]),
            None,
        )
        if chunk is None:
            continue
        if any(abs(bar - other) < SHIMMER_GAP_BARS for other in chosen_bars):
            continue
        body_start, body_end = _body_window(form, chunk)
        eighths = max(0, body_end - body_start) * active_meter().eighths_per_bar
        raw = round(0.05 * eighths)
        ratio = bell_budget(_chunk_span(source_bars, source_groups, body_start, body_end)) / BELL_MAX_EIGHTHS
        budget = round(raw * ratio)
        spent = used.get(chunk, 0)
        if spent + _hold(SHIMMER_EIGHTHS) > budget:
            continue
        notes.extend(
            written(bar * active_meter().eighths_per_bar, _hold(SHIMMER_EIGHTHS), midi, velocity=SHIMMER_VELOCITY)
        )
        used[chunk] = spent + _hold(SHIMMER_EIGHTHS)
        chosen_bars.append(bar)
    return notes


def _shimmer_midi(melody: int, chord: Chord) -> int:
    folded = melody
    while folded > 84:
        folded -= 12
    while folded < 74:
        folded += 12
    window = range(74, 85)
    tones = [note for note in window if note % 12 in chord.pitch_classes]
    pool = tones or list(window)
    return min(pool, key=lambda note: (abs(note - folded), note))


def render_ambient_score(
    *,
    title: str,
    chosen: tuple[Regime, ...],
    sample_indexes: tuple[int, ...] | None,
    slots: tuple[ChordSlot, ...],
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    bands: list[str],
    band_at: dict[int, str],
    windows: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    form: FormSpec,
    source_bars: list[Bar],
    source_groups: list[list[int]],
    musical_bars: int,
    total_eighths: int,
    bpm: int,
    frame: bool = False,
) -> Score:
    """Assemble one movement. The bed follows each bar; the line follows each section."""
    jazz_slots, harmonies, chord_at = promote_ambient_slots(slots)
    if frame:
        bands, band_at = _quiet_frame_bands(form, windows, bands, band_at)
    glass, wedges, glass_dynamics = _glass(
        form, phrases, pitches, frame=frame, chord_at=chord_at
    )
    roots: list[tuple[int, ...]] = []
    fifths: list[tuple[int, ...]] = []
    root_velocity: list[int | None] = []
    fifth_velocity: list[int | None] = []
    halos: list[tuple[int, ...]] = []
    halo_velocity: list[int | None] = []
    tonic_bar = next(
        (
            bar
            for section in form.sections
            if section.kind not in ("warmup", "cooldown")
            for bar in range(section.start, section.end)
        ),
        0,
    )
    tonic_bass = chord_at[tonic_bar].bass_midi
    for bar in range(musical_bars):
        chord = chord_at[bar]
        band = band_at[bar]
        if _middle(form, bar):
            roots.append((tonic_bass,))
        else:
            roots.append((chord.bass_midi,))
        root_velocity.append(_DRONE_VELOCITY.get(band, 58))
        if band in ("mf", "f") and not _middle(form, bar):
            fifths.append((fifth_above_bass(chord),))
            fifth_velocity.append(_FIFTH_VELOCITY)
        else:
            fifths.append(())
            fifth_velocity.append(None)
        halos.append(_halo_midis(chord))
        halo_velocity.append(_HALO_VELOCITY.get(band, 46))
    low = _sustain(roots, root_velocity) + _sustain(fifths, fifth_velocity)
    halo = _sustain(halos, halo_velocity)
    swell = _swell(form, windows, bands, chord_at)
    shimmer = _shimmer(form, phrases, pitches, chord_at, source_bars, source_groups)
    return Score(
        title=title,
        bpm=bpm,
        bars=musical_bars,
        regimes=chosen,
        regime_samples=sample_indexes,
        slots=jazz_slots,
        high=with_rests(shimmer, total_eighths),
        lead=with_rests(glass, total_eighths),
        support=with_rests(halo, total_eighths),
        comp=with_rests(swell, total_eighths),
        low=with_rests(low, total_eighths),
        dynamics=_framed_bed_dynamics(windows, bands, form) if frame else _bed_dynamics(windows, bands),
        harmonies=harmonies,
        liquidity=tuple(bands),
        phrases=phrases,
        lead_wedges=tuple(wedges),
        support_wedges=_frame_bed_wedges(form) if frame else (),
        lead_dynamics=tuple(glass_dynamics),
        support_dynamics=(
            (
                DynamicEvent(bar=next(section.start for section in form.sections if section.kind == "phrase"), marking="mp", sound=SOUND["mp"]),
                DynamicEvent(
                    bar=next(section.end for section in form.sections if section.kind == "outro") - 1,
                    marking=COOLDOWN_MARKING,
                    sound=SOUND[COOLDOWN_MARKING],
                ),
            )
            if frame
            else ()
        ),
        variant="ambient",
        divisions=2,
        swing=False,
    )
