"""Ambient score: a held bed, a thinned glass line, rare swells and shimmer.

The form, Markov chords, and phrases already exist. This module only writes
the five parts. Silence is the default, and a rest still belongs to its section.
"""

from __future__ import annotations

from app.sonify.chords import Chord, Regime, fifth_above_bass, jazz_chord
from app.sonify.dynamics import SOUND
from app.sonify.form import (
    EIGHTHS_PER_BAR,
    ChordSlot,
    FormSection,
    FormSpec,
)
from app.sonify.jazz import _rhodes_voicing
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
    bell_budget,
    comp_pitches,
    hairpins,
    techniques,
    with_rests,
    written,
)

AMBIENT_BPM = 60
GLASS_HOLD = 2 * EIGHTHS_PER_BAR
FLAT_HOLD = 4 * EIGHTHS_PER_BAR
LEAP = 5
PILLARS_PER_EIGHT = 4
SHIMMER_EIGHTHS = EIGHTHS_PER_BAR
SHIMMER_GAP_BARS = 4
SHIMMER_TRIGGER = 79
GLASS_VELOCITY = 64
SWELL_VELOCITY = 96
_DRONE_MARKING = {"p": "p", "mp": "mp", "mf": "mf", "f": "mf"}
_HALO_VELOCITY = {"p": 40, "mp": 49, "mf": 64, "f": 64}


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
    start = start_bar * EIGHTHS_PER_BAR
    end = end_bar * EIGHTHS_PER_BAR
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


def _one_per_bar(runs: list[Run]) -> list[Run]:
    kept: list[Run] = []
    for run in runs:
        if kept and kept[-1].start // EIGHTHS_PER_BAR == run.start // EIGHTHS_PER_BAR:
            continue
        kept.append(run)
    return kept


def _pillars(section: FormSection, phrases: tuple[Phrase, ...], pitches: list[int]) -> list[Run]:
    start = section.start * EIGHTHS_PER_BAR
    if not phrases:
        return [Run(start, 1, pitches[start])]
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
    cap = PILLARS_PER_EIGHT * (section.end - section.start) // 8
    if cap < 1:
        cap = 1
    if len(kept) > cap:
        must = {kept[0].start, kept[-1].start}
        extra = [run for run in kept if run.start not in must]
        extra.sort(key=lambda run: (run.start in apex_starts, abs(run.midi - kept[0].midi)))
        drop: set[int] = set()
        for run in extra:
            if len(kept) - len(drop) <= cap:
                break
            drop.add(run.start)
        kept = [run for run in kept if run.start not in drop]
    thinned = [kept[0]]
    for run in kept[1:]:
        previous = thinned[-1]
        distant = run.midi == previous.midi and run.start - previous.start > GLASS_HOLD
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
                tie_in=tie_in,
                tie_out=tie_out,
            )
        )
    return notes


def _glass(
    form: FormSpec,
    phrases: tuple[Phrase, ...],
    pitches: list[int],
) -> tuple[list[NoteEvent], list[WedgeEvent], list[DynamicEvent]]:
    segments: list[tuple[int, int, int, bool, bool, bool]] = []
    wedges: list[WedgeEvent] = []
    dynamics: list[DynamicEvent] = []
    phrase_sections = [section for section in form.sections if section.kind == "phrase"]
    for section in phrase_sections:
        inside = _phrases_inside(phrases, section.start, section.end)
        end = section.end * EIGHTHS_PER_BAR
        span = pitches[section.start * EIGHTHS_PER_BAR : end]
        flat = not span or max(span) - min(span) < MIN_RISE
        if flat:
            opening_at = section.start * EIGHTHS_PER_BAR
            length = min(FLAT_HOLD, end - opening_at)
            placed = [(opening_at, length, pitches[opening_at], False)] if length > 0 else []
        else:
            placed = _place(_pillars(section, inside, pitches), end, hold=GLASS_HOLD)
            apexes = [phrase.apex.start for phrase in inside if phrase.rise >= MIN_RISE]
            apex = max(apexes) if apexes else None
            for start, length, _midi, _slur in placed:
                overlap_start = start
                overlap_end = start + length
                if apex is None or overlap_end - overlap_start < 2:
                    continue
                peak = min(max(apex, overlap_start), overlap_end - 1)
                wedges.extend(hairpins(overlap_start, overlap_end, peak))
        for start, length, midi, slur in placed:
            if not flat and start > 0:
                dynamics.append(
                    DynamicEvent(
                        bar=start // EIGHTHS_PER_BAR,
                        marking="mp",
                        sound=SOUND["mp"],
                        beat=(start % EIGHTHS_PER_BAR) * 0.5,
                    )
                )
            segments.append((start, length, midi, slur, False, False))

    intro = next((section for section in form.sections if section.kind == "intro"), None)
    if intro is not None and segments:
        intro_start = intro.start * EIGHTHS_PER_BAR
        intro_end = intro.end * EIGHTHS_PER_BAR
        first = segments[0]
        tie = first[0] == intro_end and intro_end > intro_start
        segments.insert(0, (intro_start, intro_end - intro_start, first[2], False, False, tie))
        if tie:
            start, length, midi, slur, _tie_in, tie_out = segments[1]
            segments[1] = (start, length, midi, slur, True, tie_out)

    outro = next((section for section in form.sections if section.kind == "outro"), None)
    if outro is not None and pitches:
        outro_start = outro.start * EIGHTHS_PER_BAR
        outro_end = min(outro.end * EIGHTHS_PER_BAR, len(pitches))
        outro_midi = pitches[outro_end - 1]
        if segments:
            start, length, midi, slur, tie_in, _tie_out = segments[-1]
            if midi == outro_midi and start + length == outro_start:
                segments[-1] = (start, outro_end - start, midi, slur, tie_in, False)
            else:
                segments.append((outro_start, outro_end - outro_start, outro_midi, False, False, False))
        else:
            segments.append((outro_start, outro_end - outro_start, outro_midi, False, False, False))
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


def _halo_midis(chord: Chord, band: str) -> tuple[int, ...]:
    if band in ("mf", "f"):
        _root, right = _rhodes_voicing(chord)
        return tuple(right)
    _root, guide = comp_pitches(chord)
    return tuple(guide)


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
                spans.append((start, bar * EIGHTHS_PER_BAR - start, midi, velocity))
        for midi in midis:
            if midi not in active:
                active[midi] = (bar * EIGHTHS_PER_BAR, velocity_at[bar])
    last = len(per_bar) * EIGHTHS_PER_BAR
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
    notes: list[NoteEvent] = []
    for (start, length), band in zip(windows, bands):
        if band != "f" or length < 2:
            continue
        bar = start + 1
        if kind_at.get(bar) != "phrase" or bar not in chord_at:
            continue
        _root, right = _rhodes_voicing(chord_at[bar])
        for midi in right:
            notes.append(
                NoteEvent(
                    bar=bar,
                    beat=0.0,
                    midi=midi,
                    duration_beats=2.0,
                    voice=1,
                    velocity=SWELL_VELOCITY,
                )
            )
    return notes


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
                bar = run.start // EIGHTHS_PER_BAR
                if bar in quiet or bar not in chord_at:
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
        eighths = (chunk[1] - chunk[0]) * EIGHTHS_PER_BAR
        raw = round(0.05 * eighths)
        ratio = bell_budget(_chunk_span(source_bars, source_groups, chunk[0], chunk[1])) / BELL_MAX_EIGHTHS
        budget = round(raw * ratio)
        spent = used.get(chunk, 0)
        if spent + SHIMMER_EIGHTHS > budget:
            continue
        notes.extend(
            written(bar * EIGHTHS_PER_BAR, SHIMMER_EIGHTHS, midi, velocity=GLASS_VELOCITY)
        )
        used[chunk] = spent + SHIMMER_EIGHTHS
        chosen_bars.append(bar)
    return notes


def _shimmer_midi(melody: int, chord: Chord) -> int:
    window = range(SHIMMER_TRIGGER, 97)
    tones = [note for note in window if note % 12 in chord.pitch_classes]
    pool = tones or list(window)
    return min(pool, key=lambda note: (abs(note - melody), note))


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
) -> Score:
    """Assemble one movement. The bed follows each bar; the line follows each section."""
    jazz_slots, harmonies, chord_at = promote_ambient_slots(slots)
    glass, wedges, glass_dynamics = _glass(form, phrases, pitches)
    roots: list[tuple[int, ...]] = []
    fifths: list[tuple[int, ...]] = []
    halos: list[tuple[int, ...]] = []
    halo_velocity: list[int | None] = []
    for bar in range(musical_bars):
        chord = chord_at[bar]
        band = band_at[bar]
        roots.append((chord.bass_midi,))
        if band in ("mf", "f"):
            fifths.append((fifth_above_bass(chord),))
        else:
            fifths.append(())
        halos.append(_halo_midis(chord, band))
        halo_velocity.append(_HALO_VELOCITY.get(band, 49))
    low = _sustain(roots, [None] * musical_bars) + _sustain(fifths, [None] * musical_bars)
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
        dynamics=_bed_dynamics(windows, bands),
        harmonies=harmonies,
        liquidity=tuple(bands),
        phrases=phrases,
        lead_wedges=tuple(wedges),
        support_wedges=(),
        lead_dynamics=tuple(glass_dynamics),
        support_dynamics=(),
        variant="ambient",
        divisions=2,
        swing=False,
    )
