"""Classical guitar is one nylon part, and the long forms keep the symphony clock."""

import math

import pytest

from app.sonify.chords import C, DM, EM, F, G, KIND_SUSPENDED_FOURTH, Chord
from app.sonify.ensemble import ensemble_for
from app.sonify.form import (
    METER_34,
    METER_44,
    METER_68,
    ChordSlot,
    FormSection,
    compose_meter,
)
from app.sonify.guitar import (
    _arpeggio,
    _attack_eighth,
    _melody_line,
    _place_melody,
    _slur,
    _tremolo,
    render_guitar_score,
)
from app.sonify.keys import D_KEY, compose_register, register_for
from app.sonify.model import Bar, NoteEvent, Phrase, Run
from app.sonify.phrasing import MIN_RISE
from app.sonify.musicxml import score_to_musicxml
from app.sonify.render import render
from app.sonify.span import month_specs


def _bars() -> list[Bar]:
    return [Bar(close=100 + (index % 9) * 0.4, volume=1000 + index * 10) for index in range(48)]


def test_guitar_score_is_one_nylon_part() -> None:
    expected = {"classic": (88, 2), "villa": (100, 2), "barrios": (120, 4)}
    for ensemble, (bpm, divisions) in expected.items():
        score = render(_bars(), title="Guitar", variant="guitar", ensemble=ensemble)  # type: ignore[arg-type]
        assert score.bpm == bpm
        assert score.divisions == divisions
        xml = score_to_musicxml(score)
        assert xml.count("<score-part ") == 1
        assert xml.count("<part ") == 1
        assert "<part-name>Acoustic Nylon</part-name>" in xml
        assert "<instrument-name>Classical Guitar</instrument-name>" in xml
        assert "<instrument-sound>pluck.guitar.nylon-string</instrument-sound>" in xml
        assert "<midi-program>25</midi-program>" in xml
        assert "<octave-change>-1</octave-change>" in xml
        first = xml.split("</measure>")[0]
        assert first.count("<backup>") == 2
        assert all(f"<voice>{voice}</voice>" in first for voice in (1, 2, 3))
        assert "<chord" not in first


def test_barrios_prints_mp_for_the_fill_and_the_thumb() -> None:
    import re

    score = render(_bars(), title="Guitar", variant="guitar", ensemble="barrios")  # type: ignore[arg-type]
    first = score_to_musicxml(score).split("</measure>")[0]
    assert re.findall(r"<dynamics>\s*<(\w+)", first) == ["mp", "mp", "mp"]
    classic = render(_bars(), title="Guitar", variant="guitar", ensemble="classic")  # type: ignore[arg-type]
    first_classic = score_to_musicxml(classic).split("</measure>")[0]
    assert re.findall(r"<dynamics>\s*<(\w+)", first_classic) == ["mp"]


def test_guitar_rejects_a_foreign_ensemble() -> None:
    assert ensemble_for("guitar", "villa") == "villa"
    assert ensemble_for("guitar", "barrios") == "barrios"
    with pytest.raises(ValueError):
        ensemble_for("guitar", "wood")


def test_written_bounds_move_both_ways_with_the_key() -> None:
    assert register_for(D_KEY).guitar_floor == 38
    assert register_for(D_KEY).guitar_treble_top == 79


def test_guitar_span_swaps_slow_and_scherzo_meters() -> None:
    guitar = month_specs("guitar")
    symphony = month_specs("symphony")
    assert guitar[1].meter == METER_34
    assert symphony[1].meter == METER_68
    assert guitar[2].meter == METER_68
    assert symphony[2].meter == METER_34
    assert any(section.trio for section in guitar[2].sections)
    assert [(spec.bars, spec.bpm) for spec in guitar] == [(spec.bars, spec.bpm) for spec in symphony]


def _phrase(start: int, pitches: list[int]) -> Phrase:
    runs = tuple(Run(start + offset, 1, midi) for offset, midi in enumerate(pitches))
    return Phrase(start, start + len(pitches), runs, False)


def test_a_phrase_already_in_the_window_stays_put() -> None:
    raw = [60, 62, 64, 65]
    placed = _place_melody(raw, (_phrase(0, raw),), 59, 81, {0: C}, "major")
    assert placed == raw


def test_a_rising_phrase_stays_rising_after_it_is_compressed() -> None:
    raw = [81, 96]
    placed = _place_melody(raw, (_phrase(0, raw),), 59, 81, {0: C}, "major")
    assert placed[1] > placed[0]
    assert all(59 <= note <= 81 for note in placed)


def test_a_minor_phrase_with_a_raised_leading_tone_is_placed() -> None:
    # B natural (83) is the raised leading tone the main pipeline sings over
    # the dominant; the natural-minor guitar scale has no place for it, and
    # placing the phrase used to crash the strong-beat quantize lookup.
    raw = [71, 83, 82, 79]
    placed = _place_melody(raw, (_phrase(0, raw),), 59, 81, {0: C}, "minor")
    assert all(59 <= note <= 81 for note in placed)
    assert all(note % 12 in {0, 2, 3, 5, 7, 8, 10} for note in placed)


def test_a_wide_phrase_lands_inside_the_window_without_reversing() -> None:
    raw = [50, 53, 57, 60, 64, 67, 71]
    placed = _place_melody(raw, (_phrase(0, raw),), 59, 81, {0: C}, "major")
    assert all(59 <= note <= 81 for note in placed)
    assert placed[-1] >= placed[0]


def _sounding(events: tuple[NoteEvent, ...] | list[NoteEvent], bar: int) -> list[float]:
    return sorted(round(event.beat, 2) for event in events if event.bar == bar and event.midi is not None)


def test_barrios_opening_downbeat_of_g_is_not_silent() -> None:
    melody = [59] * 8
    with compose_meter(METER_44):
        lead, inner, bass = _tremolo(melody, {0: G}, {0: "phrase"}, 1, 76, 40, 53, 50, 65, ())
    assert _sounding(inner, 0) == [0.0]
    assert inner[0].midi is not None and inner[0].midi < 59
    assert inner[0].velocity == 58  # the middle voice is a thumb voice too
    # The thumb keeps the root under the colour, and the fill starts with it.
    assert 0.0 in _sounding(bass, 0)
    assert 0.0 in _sounding(lead, 0)


def test_barrios_scherzo_keeps_the_full_tremolo_grid() -> None:
    melody = [72] * 12
    chords = {0: G, 1: G}
    with compose_meter(METER_68):
        lead, _inner, bass = _tremolo(melody, chords, {0: "phrase", 1: "phrase"}, 2, 120, 40, 53, 50, 65, ())
    # Every sixteenth sings; the thumb opens every quarter-note cluster.
    assert _sounding(lead, 1) == [index * 0.25 for index in range(12)]
    # Root and fifth together on each cluster.
    assert _sounding(bass, 1) == [0.0, 0.0, 1.0, 1.0, 2.0, 2.0]


def test_barrios_fast_four_four_keeps_the_full_tremolo_grid() -> None:
    melody = [72] * 16
    chords = {0: G, 1: G}
    kinds = {0: "phrase", 1: "phrase"}
    with compose_meter(METER_44):
        lead, _inner, bass = _tremolo(melody, chords, kinds, 2, 120, 40, 53, 50, 65, ())
    # Every sixteenth sings; the thumb opens every quarter-note cluster.
    assert _sounding(bass, 1) == [0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0]
    assert _sounding(lead, 1) == [index * 0.25 for index in range(16)]


def test_barrios_tremolo_thumb_is_strongest_and_m_leads_the_fill() -> None:
    melody = [72] * 16
    chords = {0: G, 1: G}
    with compose_meter(METER_44):
        lead, _inner, bass = _tremolo(melody, chords, {0: "phrase", 1: "phrase"}, 2, 120, 40, 53, 50, 65, ())
    sung = sorted(
        (note for note in lead if note.bar == 1 and note.midi is not None),
        key=lambda note: note.beat,
    )
    thumb = next(note for note in bass if note.bar == 1 and note.midi is not None)
    # p-a-m-i: the thumb at 58 tops the cluster, then m 55, i 54, a 52.
    assert [note.velocity for note in sung[:4]] == [52, 55, 54, 52]
    assert thumb.velocity is not None and thumb.velocity == 58
    assert all(thumb.velocity > (note.velocity or 0) for note in sung[:4])


def test_barrios_cluster_holds_one_pitch_for_a_quarter_and_the_thumb_rings() -> None:
    melody = [60, 62, 64, 65, 67, 69, 71, 72]
    with compose_meter(METER_44):
        lead, _inner, bass = _tremolo(melody, {0: G}, {0: "phrase"}, 1, 120, 40, 53, 50, 65, ())
    sung = sorted(
        (note for note in lead if note.bar == 0 and note.midi is not None),
        key=lambda note: note.beat,
    )
    # One pitch per quarter-note cluster, four sixteenth repeats each.
    assert [note.midi for note in sung] == [60] * 4 + [64] * 4 + [67] * 4 + [71] * 4
    assert all(note.duration_beats == 0.25 for note in sung)
    thumbs = [note for note in bass if note.bar == 0 and note.midi is not None]
    assert sorted({note.beat for note in thumbs}) == [0.0, 1.0, 2.0, 3.0]
    assert len(thumbs) == 8  # root and fifth on every cluster
    assert all(note.duration_beats == 1.0 for note in thumbs)


def test_barrios_slow_movement_keeps_its_tempo_and_skips_tremolo() -> None:
    from app.sonify.span import month_specs, quarter_specs

    slow = quarter_specs("guitar")[1]
    assert slow.bpm == 60
    barrios = render(_bars(), title="Guitar", variant="guitar", ensemble="barrios", form=slow)  # type: ignore[arg-type]
    # No tempo lift and no sixteenth tremolo grid. Phase 1 sings this slow
    # movement as the Barrios chorale, still on the eighth-note grid.
    assert barrios.bpm == 60
    assert barrios.divisions == 2
    assert all(note.duration_beats != 0.25 for note in barrios.lead if note.midi is not None)
    fast = render(_bars(), title="Guitar", variant="guitar", ensemble="barrios", form=month_specs("guitar")[0])  # type: ignore[arg-type]
    assert fast.bpm == 96
    assert fast.divisions == 4


def test_a_sixteenth_at_beat_075_stays_in_its_eighth() -> None:
    event = NoteEvent(bar=0, beat=0.75, midi=62, duration_beats=0.25, voice=1)
    with compose_meter(METER_44):
        assert _attack_eighth(event) == 1


def _step_line(phrases_notes: list[list[int]]) -> tuple[list[NoteEvent], tuple[Phrase, ...]]:
    events: list[NoteEvent] = []
    phrases: list[Phrase] = []
    index = 0
    for notes in phrases_notes:
        runs = tuple(Run(index + offset, 1, midi) for offset, midi in enumerate(notes))
        phrases.append(Phrase(index, index + len(notes), runs, False))
        for midi in notes:
            events.append(
                NoteEvent(
                    bar=index // 8,
                    beat=(index % 8) * 0.5,
                    midi=midi,
                    duration_beats=0.5,
                    voice=1,
                )
            )
            index += 1
    return events, tuple(phrases)


def test_hammers_are_rare_stressed_and_never_in_the_opening_phrase() -> None:
    # Each phrase climbs by step to its apex (offset 9), then falls by step.
    shape = [*range(60, 70), *range(68, 58, -1)]
    events, phrases = _step_line([shape] * 5)
    with compose_meter(METER_44):
        slurred = _slur(events, phrases)
    hammers = [index for index, note in enumerate(slurred) if note.slur_stop]
    # Only the step onto each later phrase's apex, capped under 5% of attacks.
    assert hammers == [29, 49, 69, 89]
    assert len(hammers) / len(events) < 0.05
    assert all(index >= 20 for index in hammers)


def test_an_unstressed_step_after_the_opening_phrase_stays_plucked() -> None:
    events, phrases = _step_line([[60, 61, 62, 63], [60, 61, 70, 69]])
    with compose_meter(METER_44):
        slurred = _slur(events, phrases)
    assert not any(note.slur_start or note.slur_stop for note in slurred)


def test_a_leap_or_a_rest_is_plucked() -> None:
    leap = [
        NoteEvent(bar=0, beat=0.0, midi=60, duration_beats=0.5, voice=1),
        NoteEvent(bar=0, beat=0.5, midi=67, duration_beats=0.5, voice=1),
    ]
    gap = [
        NoteEvent(bar=0, beat=0.0, midi=60, duration_beats=0.5, voice=1),
        NoteEvent(bar=0, beat=1.0, midi=62, duration_beats=0.5, voice=1),
    ]
    phrase = Phrase(0, 4, (Run(0, 4, 60),), False)
    with compose_meter(METER_44):
        leapt = _slur(leap, (phrase,))
        rested = _slur(gap, (phrase,))
    assert not any(note.slur_start or note.slur_stop for note in leapt)
    assert not any(note.slur_start or note.slur_stop for note in rested)


def test_the_apex_is_the_only_louder_melody_note() -> None:
    pitches = [60, 62, 64, 62, 60, 60, 60, 60]
    phrase = Phrase(
        0,
        4,
        (Run(0, 1, 60), Run(1, 1, 62), Run(2, 1, 64), Run(3, 1, 62)),
        False,
    )
    with compose_meter(METER_44):
        line = _melody_line(pitches, (phrase,), 1)
    sounding = [note for note in line if note.midi is not None]
    assert [note.velocity for note in sounding] == [64, 64, 72, 64, 64]


def test_a_quiet_bar_plucks_one_inner_note() -> None:
    melody = [72] * 8
    chords = {0: C}
    kinds = {0: "phrase"}

    def beats(band: str) -> list[float]:
        inner, _bass = _arpeggio(
            melody,
            chords,
            kinds,
            {0: band},
            1,
            rolling=False,
            character=None,
            character_at=None,
            bass_low=40,
            bass_high=51,
            mid_low=50,
            mid_high=65,
        )
        return _sounding(inner, 0)

    with compose_meter(METER_44):
        assert beats("p") == [0.5]
        assert beats("mp") == [0.5, 1.5, 3.0]
        assert beats("f") == [0.5, 1.0, 1.5, 2.5, 3.0, 3.5]


def test_villa_tresillo_is_only_two_volatile_bars_of_four_four() -> None:
    melody = [72] * 24
    chords = {bar: C for bar in range(3)}
    kinds = {bar: "phrase" for bar in range(3)}
    bands = {bar: "f" for bar in range(3)}
    with compose_meter(METER_44):
        inner, _bass = _arpeggio(
            melody,
            chords,
            kinds,
            bands,
            3,
            rolling=True,
            character="volatile",
            character_at=None,
            bass_low=40,
            bass_high=51,
            mid_low=50,
            mid_high=65,
        )
    accented = {event.bar for event in inner if event.accent}
    assert accented == {0, 1}
    with compose_meter(METER_68):
        six, _bass = _arpeggio(
            [72] * 6,
            {0: C},
            {0: "phrase"},
            {0: "f"},
            1,
            rolling=True,
            character="volatile",
            character_at=None,
            bass_low=40,
            bass_high=51,
            mid_low=50,
            mid_high=65,
        )
    assert not any(event.accent for event in six)


def _render_guitar(slots, pitches, *, ensemble="classic", bpm=88, key=None):
    bars = len(pitches) // 8
    phrase = _phrase(0, pitches)

    def build():
        return render_guitar_score(
            title="Guitar",
            chosen=(),
            sample_indexes=None,
            slots=tuple(slots),
            pitches=list(pitches),
            phrases=(phrase,),
            dynamics=(),
            bands=["mf"] * bars,
            band_at={bar: "mf" for bar in range(bars)},
            musical_bars=bars,
            total_eighths=len(pitches),
            bpm=bpm,
            ensemble=ensemble,
            harmonies=(),
        )

    if key is None:
        return build()
    with compose_register(key):
        return build()


def _bass_pitches(score, bar: int) -> set[int]:
    return {note.midi for note in score.low if note.bar == bar and note.midi is not None}


def test_bass_folds_the_stored_root_up_to_f3() -> None:
    score = _render_guitar(
        (
            ChordSlot(0, 1, DM, "sideway", "phrase"),
            ChordSlot(1, 1, EM, "sideway", "phrase"),
            ChordSlot(2, 1, F, "sideway", "phrase"),
        ),
        [74] * 8 + [76] * 8 + [77] * 8,
    )
    # D3 stays. E4 folds to E3, not E2. F4 folds to F3, the ceiling.
    assert _bass_pitches(score, 0) == {50}
    assert _bass_pitches(score, 1) == {52}
    assert _bass_pitches(score, 2) == {53}

    tremolo = _render_guitar(
        (ChordSlot(0, 1, EM, "sideway", "phrase"),),
        [76] * 8,
        ensemble="barrios",
        bpm=120,
    )
    thumb = _bass_pitches(tremolo, 0)
    assert 52 in thumb and 40 not in thumb
    assert all(40 <= note <= 53 for note in thumb)

    # FPT writes in [38, 51]. D4 (62) folds to 50, which the old Eb3 ceiling pushed to 38.
    written = _render_guitar(
        (ChordSlot(0, 1, DM, "sideway", "phrase"),),
        [74] * 8,
        key=D_KEY,
    )
    assert _bass_pitches(written, 0) == {50}


CSUS4 = Chord("Csus4", "C", KIND_SUSPENDED_FOURTH, "sus4", (60, 65, 67))


def _held(start: int, eighths: int, midi: int, *, held_over: bool = False) -> Phrase:
    return Phrase(start, start + eighths, (Run(start, eighths, midi),), held_over)


def _running(start: int, midis: list[int], *, held_over: bool = False) -> Phrase:
    runs = tuple(Run(start + offset, 1, midi) for offset, midi in enumerate(midis))
    return Phrase(start, start + len(midis), runs, held_over)


def _from_notes(start: int, midis: list[int], *, held_over: bool = False) -> Phrase:
    runs: list[Run] = []
    index = 0
    while index < len(midis):
        nxt = index + 1
        while nxt < len(midis) and midis[nxt] == midis[index]:
            nxt += 1
        runs.append(Run(start + index, nxt - index, midis[index]))
        index = nxt
    return Phrase(start, start + len(midis), tuple(runs), held_over)


def _start16(event: NoteEvent, sixteenths_per_bar: int) -> int:
    return event.bar * sixteenths_per_bar + int(math.floor(event.beat * 4 + 1e-9))


def _dur16(event: NoteEvent) -> int:
    return int(round(event.duration_beats * 4))


def _assert_voice_covers(events: tuple[NoteEvent, ...], total_eighths: int, epb: int) -> None:
    """Every sixteenth of the voice is covered once. Notes that share an onset are a chord."""
    spb = epb * 2
    total = total_eighths * 2
    cursor = 0
    chord_starts: set[int] = set()
    for event in sorted(events, key=lambda item: (_start16(item, spb), -_dur16(item))):
        dur = _dur16(event)
        start = _start16(event, spb)
        assert dur > 0
        assert start >= cursor or start in chord_starts, f"overlap at sixteenth {start}"
        assert start <= cursor, f"gap before sixteenth {start}"
        chord_starts.add(start)
        cursor = max(cursor, start + dur)
    assert cursor == total, f"voice ends at sixteenth {cursor}, score has {total}"


def _assert_score_covers(score, epb: int) -> None:
    total = score.bars * epb
    for voice in (score.lead, score.support, score.low):
        _assert_voice_covers(voice, total, epb)
    score_to_musicxml(score)


def _onset_beats(events: tuple[NoteEvent, ...], bar: int) -> list[float]:
    return sorted(
        round(event.beat, 2) for event in events if event.bar == bar and event.midi is not None
    )


def _covers(events: tuple[NoteEvent, ...], eighth: int, epb: int) -> bool:
    """True when a sounding note covers this eighth."""
    window = eighth * 2
    for event in events:
        if event.midi is None:
            continue
        start = _start16(event, epb * 2)
        if start < window + 2 and start + _dur16(event) > window:
            return True
    return False


def _attack_at(events: tuple[NoteEvent, ...], eighth: int, epb: int) -> NoteEvent | None:
    for event in events:
        if event.midi is not None and _start16(event, epb * 2) == eighth * 2:
            return event
    return None


def _guitar(
    phrases: tuple[Phrase, ...],
    *,
    ensemble: str = "barrios",
    bpm: int = 120,
    meter=METER_44,
    chord: Chord = C,
    kinds: dict[int, str] | None = None,
    bands: dict[int, str] | None = None,
    chords: dict[int, Chord] | None = None,
    character: str | None = None,
    character_at: tuple | None = None,
    mode: str = "major",
    sections: tuple = (),
):
    epb = meter.eighths_per_bar
    end = max(phrase.end for phrase in phrases)
    bars = math.ceil(end / epb)
    total = bars * epb
    pitches = [60] * total
    for phrase in phrases:
        for run in phrase.runs:
            for offset in range(run.length):
                slot = run.start + offset
                if slot < total:
                    pitches[slot] = run.midi
    kinds = kinds or {}
    bands = bands or {}
    chords = chords or {}
    slots = tuple(
        ChordSlot(
            bar,
            1,
            chords.get(bar, chord),
            "sideway",
            kinds.get(bar, "phrase"),  # type: ignore[arg-type]
        )
        for bar in range(bars)
    )
    with compose_meter(meter):
        score = render_guitar_score(
            title="Guitar",
            chosen=(),
            sample_indexes=None,
            slots=slots,
            pitches=pitches,
            phrases=phrases,
            dynamics=(),
            bands=[bands.get(bar, "mf") for bar in range(bars)],
            band_at={bar: bands.get(bar, "mf") for bar in range(bars)},
            musical_bars=bars,
            total_eighths=total,
            bpm=bpm,
            ensemble=ensemble,  # type: ignore[arg-type]
            harmonies=(),
            mode=mode,
            character=character,  # type: ignore[arg-type]
            character_at=character_at,
            sections=sections,
        )
    _assert_score_covers(score, epb)
    return score


def _sixteenths(events: tuple[NoteEvent, ...], bar: int) -> list[float]:
    return sorted(
        round(event.beat, 2)
        for event in events
        if event.bar == bar and event.midi is not None and abs(event.duration_beats - 0.25) < 1e-9
    )


def test_phase1_held_melody_tremolo_tapers_and_breathes() -> None:
    """120 BPM, from the second body phrase: tremolo, with a tail only on a long phrase."""
    # Non-closing phrase whose successor stays tremolo: the whole bar is sixteenths.
    full = _guitar(
        (
            _held(0, 8, 72, held_over=True),
            _held(8, 8, 72, held_over=True),
            _held(16, 8, 72, held_over=True),
        ),
        bpm=120,
    )
    assert full.divisions == 4
    assert _sixteenths(full.lead, 0) == []  # opening body phrase is arpeggio
    assert _sixteenths(full.lead, 1) == [index * 0.25 for index in range(16)]
    sung = sorted(
        (note for note in full.lead if note.bar == 1 and note.midi is not None),
        key=lambda note: note.beat,
    )
    assert [note.velocity for note in sung[:4]] == [52, 55, 54, 52]
    thumbs = [note for note in full.low if note.bar == 1 and note.midi is not None]
    assert sorted({round(note.beat, 2) for note in thumbs}) == [0.0, 1.0, 2.0, 3.0]
    assert all(note.duration_beats == 1.0 and note.velocity == 58 for note in thumbs)
    assert len(thumbs) == 8  # root and fifth on every quarter

    # A closing 6/8 bar is only three quarter beats, so the tremolo is not cut.
    short = _guitar(
        (
            _held(0, 6, 72),
            _held(6, 6, 72),
            _held(12, 6, 72, held_over=True),
        ),
        bpm=120,
        meter=METER_68,
    )
    assert short.divisions == 4
    assert _sixteenths(short.lead, 1) == [index * 0.25 for index in range(12)]
    assert sorted(
        {round(note.beat, 2) for note in short.low if note.bar == 1 and note.midi is not None}
    ) == [0.0, 1.0, 2.0]

    # Two bars that close, and the next body phrase is still tremolo: tail, no breath.
    closing = _guitar(
        (
            _held(0, 8, 72, held_over=True),
            _held(8, 16, 72),
            _held(24, 8, 72, held_over=True),
        ),
        bpm=120,
    )
    assert _sixteenths(closing.lead, 1) == [index * 0.25 for index in range(16)]
    assert _sixteenths(closing.lead, 2) == [index * 0.25 for index in range(8)]
    assert all(note.duration_beats >= 0.5 for note in closing.lead if note.bar == 2 and note.beat >= 2)
    assert _covers(closing.lead, 23, 8)  # last eighth still sings; the pattern did not change
    tail_bass = [note for note in closing.low if note.bar == 2 and note.midi is not None and note.beat >= 2]
    assert tail_bass and all(note.velocity == 60 for note in tail_bass)
    assert len({note.midi for note in tail_bass}) == 1  # arpeggio root, not the tremolo fifth

    # Long tremolo before a running phrase: tail, and the last eighth is a breath.
    changing = _guitar(
        (
            _held(0, 8, 72, held_over=True),
            _held(8, 16, 72, held_over=True),
            _running(24, [64, 67, 72, 76, 74, 71, 69, 65]),
        ),
        bpm=120,
    )
    assert _sixteenths(changing.lead, 2) == [index * 0.25 for index in range(8)]
    assert not _covers(changing.lead, 23, 8)
    assert not _covers(changing.support, 23, 8)
    assert _covers(changing.low, 23, 8)


def test_phase1_a_running_line_stays_arpeggio() -> None:
    score = _guitar(
        (
            _running(0, [64, 67, 72, 76, 67, 64, 76, 72]),
            _running(8, [64, 67, 72, 76, 67, 64, 76, 72]),
        ),
        bpm=120,
    )
    assert score.divisions == 2  # the movement never leaves the eighth grid
    assert _sixteenths(score.lead, 1) == []
    assert _onset_beats(score.low, 1) == [0.0, 2.0]
    assert _onset_beats(score.support, 1) == [0.5, 1.0, 1.5, 2.5, 3.0, 3.5]


def test_phase1_pedal_bars_and_the_opening_phrase_do_not_tremolo() -> None:
    score = _guitar(
        (
            _held(0, 8, 72),
            _held(8, 8, 72),
            _held(16, 8, 72),
            _held(24, 8, 72),
            _held(32, 8, 72),
        ),
        bpm=120,
        kinds={0: "intro", 1: "warmup", 2: "phrase", 3: "cooldown", 4: "outro"},
    )
    assert score.bpm == 120
    for bar in (0, 1, 3, 4):
        assert _sixteenths(score.lead, bar) == []
        bass = [note for note in score.low if note.bar == bar and note.midi is not None]
        assert [(note.beat, note.duration_beats, note.midi) for note in bass] == [(0.0, 4.0, 48)]
        assert not any(note.midi is not None for note in score.support if note.bar == bar)
    # The held line is the first body phrase, so it stays an opening arpeggio.
    assert _sixteenths(score.lead, 2) == []
    assert _onset_beats(score.low, 2) == [0.0, 2.0]
    assert score.divisions == 2


def test_phase1_slow_movements_sing_the_house_chorale() -> None:
    barrios = _guitar((_held(0, 12, 72, held_over=True), _held(12, 6, 67)), bpm=66, meter=METER_34, ensemble="barrios")
    assert barrios.bpm == 66 and barrios.divisions == 2
    assert _sixteenths(barrios.lead, 0) == [] and _sixteenths(barrios.lead, 1) == []
    # Apex bar of the first phrase gains the second block; the later bar does not.
    assert _onset_beats(barrios.low, 0) == [0.0, 2.0]
    assert _onset_beats(barrios.support, 0) == [0.0, 2.0]
    assert _onset_beats(barrios.lead, 0) == [0.0, 2.0]
    assert _onset_beats(barrios.low, 1) == [0.0]
    assert all(note.duration_beats == 3.0 for note in barrios.low if note.bar == 1 and note.midi is not None)

    sor = _guitar((_held(0, 6, 76),), bpm=72, meter=METER_34, ensemble="classic", character="calm")
    assert sor.bpm == 72 and sor.divisions == 2
    assert _sixteenths(sor.lead, 0) == []
    # Calm does not leave Élégiaque while the movement is this slow, and the
    # final bar of a closing phrase sustains the root.
    assert [(round(note.beat, 2), note.duration_beats) for note in sor.low if note.midi is not None] == [
        (0.0, 3.0)
    ]

    villa = _guitar((_held(0, 6, 72),), bpm=60, meter=METER_34, ensemble="villa")
    assert villa.bpm == 60 and villa.divisions == 2
    assert _sixteenths(villa.lead, 0) == []
    assert _onset_beats(villa.low, 0) == _onset_beats(villa.support, 0) == _onset_beats(villa.lead, 0)
    assert 1.0 not in _onset_beats(villa.low, 0)


def test_phase1_the_third_tremolo_phrase_becomes_andante_on_the_sixteenth_grid() -> None:
    score = _guitar(
        (
            _held(0, 8, 72, held_over=True),
            _held(8, 8, 72, held_over=True),
            _held(16, 8, 72, held_over=True),
            _held(24, 8, 72, held_over=True),
        ),
        bpm=120,
    )
    assert score.divisions == 4
    assert _sixteenths(score.lead, 1) == [index * 0.25 for index in range(16)]
    # The phrase before the chorale is still tremolo, so it tapers; the chorale itself has no sixteenths.
    assert _sixteenths(score.lead, 3) == []
    for voice in (score.lead, score.support, score.low):
        assert _onset_beats(voice, 3) == [0.0, 2.0]
        sounding = [note for note in voice if note.bar == 3 and note.midi is not None]
        assert [note.duration_beats for note in sounding] == [2.0, 2.0]
    support = next(note for note in score.support if note.bar == 3 and note.midi is not None)
    lead = next(note for note in score.lead if note.bar == 3 and note.midi is not None)
    bass = next(note for note in score.low if note.bar == 3 and note.midi is not None)
    assert bass.midi < support.midi < lead.midi


def test_phase1_elegiaque_march_appoggiatura_and_lament() -> None:
    # Slow, and calm: Élégiaque from the first phrase. Dotted bass, one step sparser than study.
    slow = _guitar((_held(0, 8, 76),), bpm=72, ensemble="classic", character="calm")
    assert [(round(note.beat, 2), note.duration_beats, note.midi) for note in slow.low if note.midi] == [
        (0.0, 1.5, 48),
        (1.5, 0.5, 47),
        (2.0, 1.5, 43),
        (3.5, 0.5, 41),
    ]
    assert _onset_beats(slow.support, 0) == [0.5, 1.5, 3.0]

    # 1D at 88 is under 90, so selloff is Élégiaque from the first body phrase.
    daily = _guitar((_held(0, 8, 76),), bpm=88, ensemble="classic", character="selloff")
    assert _onset_beats(daily.low, 0) == [0.0, 1.5, 2.0, 3.5]

    # At 96 the opening phrase stays arpeggio; the next selloff phrase is the march.
    fast = _guitar(
        (_held(0, 8, 72), _held(8, 8, 76)),
        bpm=96,
        ensemble="classic",
        character="selloff",
    )
    assert _onset_beats(fast.low, 0) == [0.0, 2.0]
    assert _onset_beats(fast.low, 1) == [0.0, 1.5, 2.0, 3.5]
    assert not _covers(fast.lead, 7, 8)
    assert not _covers(fast.support, 7, 8)
    assert _covers(fast.low, 7, 8)

    # section.trio in minor, from the second phrase. A major trio does not open the march.
    trio = (FormSection(1, 2, "phrase", 0, trio=True),)
    minor = _guitar(
        (_held(0, 8, 72, held_over=True), _held(8, 8, 70)),
        bpm=120,
        ensemble="classic",
        character="rally",
        mode="minor",
        sections=trio,
    )
    assert _onset_beats(minor.low, 0) == [0.0, 2.0]
    assert _onset_beats(minor.low, 1) == [0.0, 1.5, 2.0, 3.5]
    major = _guitar(
        (_held(0, 8, 72, held_over=True), _held(8, 8, 72, held_over=True)),
        bpm=120,
        ensemble="classic",
        character="rally",
        mode="major",
        sections=trio,
    )
    assert _onset_beats(major.low, 1) == [0.0, 2.0]

    # 6/8 march, and the 3/4 final bar of a closing phrase holds the root.
    six = _guitar((_held(0, 6, 76),), bpm=72, meter=METER_68, ensemble="classic")
    assert [(round(note.beat, 2), note.duration_beats) for note in six.low if note.midi] == [
        (0.0, 1.0),
        (1.0, 0.5),
        (1.5, 1.0),
        (2.5, 0.5),
    ]
    three = _guitar((_held(0, 12, 72),), bpm=72, meter=METER_34, ensemble="classic")
    assert [(round(note.beat, 2), note.duration_beats) for note in three.low if note.bar == 0 and note.midi] == [
        (0.0, 1.5),
        (1.5, 0.5),
        (2.0, 1.0),
    ]
    assert [(round(note.beat, 2), note.duration_beats, note.midi) for note in three.low if note.bar == 1 and note.midi] == [
        (0.0, 3.0, 48),
    ]

    # Last two bars of a closing minor phrase walk down the scale, folded into the bass window.
    lament = _guitar((_held(0, 16, 67),), bpm=72, ensemble="classic", mode="minor")
    bass = [
        note.midi
        for note in sorted(
            (note for note in lament.low if note.midi is not None),
            key=lambda note: (note.bar, note.beat),
        )
    ]
    assert bass == [48, 46, 44, 43, 41, 51, 50, 48]
    assert all(40 <= note <= 53 for note in bass)

    # One appoggiatura per phrase, resolving back to the strong-beat note.
    ornament = _guitar(
        (
            _from_notes(0, [64, 64, 62, 62, 67, 67, 67, 65]),
            _from_notes(8, [64, 64, 65, 65, 67, 67, 67, 67]),
        ),
        bpm=72,
        ensemble="classic",
    )
    first = _attack_at(ornament.lead, 0, 8)
    resolution = _attack_at(ornament.lead, 1, 8)
    assert first is not None and first.midi == 65 and first.accent
    assert resolution is not None and resolution.midi == 64 and not resolution.accent
    second_chance = _attack_at(ornament.lead, 4, 8)
    assert second_chance is not None and second_chance.midi == 67 and not second_chance.accent
    assert sum(note.accent for note in ornament.lead if note.bar == 0) == 1
    rising = _attack_at(ornament.lead, 8, 8)
    rising_resolution = _attack_at(ornament.lead, 9, 8)
    assert rising is not None and rising.midi == 62 and rising.accent
    assert rising_resolution is not None and rising_resolution.midi == 64
    assert sum(note.accent for note in ornament.lead if note.bar == 1) == 1


def test_phase1_villa_chord_melody_follows_the_meter() -> None:
    # Slow 3/4, including the first phrase. Rise through the apex, and the closing bar, gain eighth 4.
    rising = _from_notes(0, [67] * 6 + [74] * 6 + [69] * 6)
    assert rising.rise >= MIN_RISE
    slow = _guitar(
        (rising, _from_notes(18, [67] * 6 + [69] * 6, held_over=True)),
        bpm=72,
        meter=METER_34,
        ensemble="villa",
    )
    assert slow.divisions == 2
    for bar in (0, 1, 2):
        assert _onset_beats(slow.low, bar) == [0.0, 2.0]
        assert _onset_beats(slow.support, bar) == [0.0, 2.0]
        assert _onset_beats(slow.lead, bar) == [0.0, 2.0]
        assert [note.duration_beats for note in slow.low if note.bar == bar and note.midi] == [2.0, 1.0]
    assert _onset_beats(slow.low, 3) == [0.0]
    assert [note.duration_beats for note in slow.low if note.bar == 3 and note.midi] == [3.0]
    assert _onset_beats(slow.low, 4) == [0.0, 2.0]  # apex bar, even though the phrase does not rise by MIN_RISE
    for bar in range(slow.bars):
        assert 1.0 not in _onset_beats(slow.low, bar)  # never a block on eighth 2
        support = next(note for note in slow.support if note.bar == bar and note.beat == 0 and note.midi)
        lead = next(note for note in slow.lead if note.bar == bar and note.beat == 0 and note.midi)
        bass = next(note for note in slow.low if note.bar == bar and note.beat == 0 and note.midi)
        assert bass.midi < support.midi < lead.midi

    # 6/8 calm, from the second phrase. Only the apex and the bar before it intensify.
    six_notes = [67] * 6 + [67] * 6 + [74] * 6
    six = _guitar(
        (_held(0, 6, 72, held_over=True), _from_notes(6, six_notes)),
        bpm=120,
        meter=METER_68,
        ensemble="villa",
        character="calm",
    )
    assert _onset_beats(six.low, 0) == [0.0, 1.5]  # opening arpeggio, strong eighths of 6/8
    assert _sixteenths(six.lead, 0) == []
    assert _onset_beats(six.low, 1) == [0.0]
    assert [note.duration_beats for note in six.low if note.bar == 1 and note.midi] == [3.0]
    for bar in (2, 3):
        assert _onset_beats(six.low, bar) == _onset_beats(six.support, bar) == [0.0, 1.5]
        assert [note.duration_beats for note in six.low if note.bar == bar and note.midi] == [1.5, 1.5]
    for bar in range(1, 4):
        beats = set(_onset_beats(six.low, bar))
        assert beats.isdisjoint({0.5, 1.0, 2.0, 2.5})

    # 4/4 calm, rise through the apex: those bars strike every quarter, and the bar after does not.
    four = _guitar(
        (
            _held(0, 8, 72, held_over=True),
            _from_notes(8, [67] * 8 + [74] * 8 + [69] * 8),
        ),
        bpm=100,
        ensemble="villa",
        character="calm",
        chords={2: CSUS4},
    )
    assert _onset_beats(four.low, 0) == [0.0, 2.0]
    for bar in (1, 2):
        assert _onset_beats(four.low, bar) == [0.0, 1.0, 2.0, 3.0]
        assert [note.duration_beats for note in four.low if note.bar == bar and note.midi] == [1.0, 1.0, 1.0, 1.0]
    assert _onset_beats(four.low, 3) == [0.0, 2.0]
    suspended = [note.midi for note in four.support if note.bar == 2 and note.midi is not None]
    assert suspended and all(note % 12 in {2, 5, 10} for note in suspended)
    tertian = next(note for note in four.support if note.bar == 1 and note.midi is not None)
    assert tertian.midi % 12 in {3, 4, 10, 11}


def test_phase1_a_calm_scherzo_still_tremolos_a_held_line() -> None:
    score = _guitar(
        (_held(0, 6, 72), _held(6, 6, 72)),
        bpm=120,
        meter=METER_68,
        character="calm",
        bands={0: "f", 1: "f"},
    )
    assert score.divisions == 4
    assert _sixteenths(score.lead, 0) == []
    assert _onset_beats(score.low, 0) == [0.0, 1.5]
    assert _sixteenths(score.lead, 1) == [index * 0.25 for index in range(12)]
    sung = sorted(
        (note for note in score.lead if note.bar == 1 and note.midi is not None),
        key=lambda note: note.beat,
    )
    assert [note.velocity for note in sung[:4]] == [52, 55, 54, 52]


def test_phase1_rendered_guitar_voices_cover_every_measure() -> None:
    from app.sonify.span import month_specs, quarter_specs

    for ensemble in ("classic", "villa", "barrios"):
        score = render(_bars(), title="Guitar", variant="guitar", ensemble=ensemble)  # type: ignore[arg-type]
        epb = score.beats * 8 // score.beat_type
        _assert_score_covers(score, epb)
    slow = render(
        _bars(),
        title="Guitar",
        variant="guitar",
        ensemble="barrios",
        form=quarter_specs("guitar")[1],
    )
    assert slow.bpm == 60 and slow.divisions == 2
    _assert_score_covers(slow, slow.beats * 8 // slow.beat_type)
    fast = render(
        _bars(),
        title="Guitar",
        variant="guitar",
        ensemble="barrios",
        form=month_specs("guitar")[0],
    )
    assert fast.bpm == 96 and fast.divisions == 4
    _assert_score_covers(fast, fast.beats * 8 // fast.beat_type)
