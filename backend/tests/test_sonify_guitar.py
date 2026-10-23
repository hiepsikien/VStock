"""Classical guitar is one nylon part, and the long forms keep the symphony clock."""

import math

import pytest

from app.sonify.chords import KIND_SUSPENDED_FOURTH, C, Chord, DM, EM, F, G
from app.sonify.ensemble import ensemble_for
from app.sonify.form import METER_34, METER_44, METER_68, ChordSlot, FormSection, compose_meter
from app.sonify.guitar import (
    _arpeggio,
    _attack_eighth,
    _melody_line,
    _place_melody,
    _slur,
    _tremolo,
    assert_playable,
    guard_chromatic_approach,
    render_guitar_score,
)
from app.sonify.keys import C_KEY, D_KEY, compose_register, register_for
from app.sonify.model import Bar, NoteEvent, Phrase, Run, Score
from app.sonify.musicxml import score_to_musicxml
from app.sonify.phrasing import MIN_RISE
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
    # No tempo lift and no sixteenth tremolo grid: the slow movement sings
    # as arpeggio at its own tempo.
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


_MAJOR = (0, 2, 4, 5, 7, 9, 11)


def _joined(start: int, pitches: list[int], held: bool = False) -> Phrase:
    runs: list[Run] = []
    index = 0
    while index < len(pitches):
        nxt = index + 1
        while nxt < len(pitches) and pitches[nxt] == pitches[index]:
            nxt += 1
        runs.append(Run(start + index, nxt - index, pitches[index]))
        index = nxt
    return Phrase(start, start + len(pitches), tuple(runs), held)


def _pattern_score(
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    *,
    ensemble: str = "classic",
    bpm: int = 88,
    meter=METER_44,
    bands: dict[int, str] | None = None,
    chords: dict | None = None,
    kinds: dict[int, str] | None = None,
    sections: tuple[FormSection, ...] | None = None,
    character: str | None = "rally",
    rel_span: float = 0.02,
    mode: str = "major",
):
    epb = meter.eighths_per_bar
    bars = len(pitches) // epb
    bands = bands or {bar: "mf" for bar in range(bars)}
    chords = chords or {bar: C for bar in range(bars)}
    kinds = kinds or {bar: "phrase" for bar in range(bars)}
    slots = tuple(ChordSlot(bar, 1, chords[bar], "sideway", kinds[bar]) for bar in range(bars))

    def build():
        return render_guitar_score(
            title="Guitar",
            chosen=(),
            sample_indexes=None,
            slots=slots,
            pitches=list(pitches),
            phrases=phrases,
            dynamics=(),
            bands=[bands[bar] for bar in range(bars)],
            band_at=bands,
            musical_bars=bars,
            total_eighths=len(pitches),
            bpm=bpm,
            ensemble=ensemble,
            harmonies=(),
            mode=mode,
            character=character,  # type: ignore[arg-type]
            sections=sections,
            rel_span=rel_span,
        )

    with compose_meter(meter):
        return build()


def _on(voice, bar: int) -> list[tuple[float, int]]:
    return sorted(
        (round(note.beat, 2), note.midi)
        for note in voice
        if note.bar == bar and note.midi is not None
    )


def _degree(note: int) -> int:
    return _MAJOR.index(note % 12)


def test_study_density_follows_the_band() -> None:
    melody = [72] * 8
    phrase = (_joined(0, melody),)

    def bass_beats(band: str) -> list[float]:
        score = _pattern_score(melody, phrase, bands={0: band}, bpm=88, character="rally")
        return [beat for beat, _midi in _on(score.low, 0)]

    def inner_beats(band: str) -> list[float]:
        score = _pattern_score(melody, phrase, bands={0: band}, bpm=88, character="rally")
        return [beat for beat, _midi in _on(score.support, 0)]

    assert bass_beats("p") == [0.0]
    assert inner_beats("p") == [2.0]
    assert bass_beats("mp") == [0.0, 2.0]
    assert inner_beats("mp") == [1.0, 3.0]
    assert bass_beats("mf") == [0.0, 2.0]
    assert inner_beats("mf") == [1.0, 1.5, 3.0, 3.5]
    forte = _pattern_score(melody, phrase, bands={0: "f"}, bpm=88, character="rally")
    assert [beat for beat, _midi in _on(forte.low, 0)] == [0.0, 2.0, 3.0]
    assert [beat for beat, _midi in _on(forte.support, 0)] == [1.0, 1.5, 3.0, 3.5]
    # 6/8 groups the bass at the two strong eighths. 3/4 keeps a secondary bass.
    six = _pattern_score([72] * 6, (_joined(0, [72] * 6),), meter=METER_68, bands={0: "mf"})
    assert [beat for beat, _midi in _on(six.low, 0)] == [0.0, 1.5]
    three = _pattern_score([72] * 6, (_joined(0, [72] * 6),), meter=METER_34, bands={0: "mf"})
    assert [beat for beat, _midi in _on(three.low, 0)] == [0.0, 2.0]


def test_villa_rolls_camps_and_approaches_and_colors_a_suspension() -> None:
    pitches = [72] * 24
    score = _pattern_score(
        pitches,
        (_joined(0, pitches),),
        ensemble="villa",
        bpm=100,
        bands={0: "f", 1: "f", 2: "f"},
        chords={0: C, 1: G, 2: C},
        character="volatile",
    )
    assert any(note.duration_beats >= 1.0 for note in score.support if note.midi is not None)
    accented = {note.bar for note in (*score.support, *score.low) if note.accent}
    assert accented == {0, 1}
    approach = next(note for note in score.low if note.bar == 0 and abs(note.beat - 3.5) < 1e-6)
    assert approach.midi == 42  # F♯ under the next bar's G
    suspended = Chord("Csus4", "C", KIND_SUSPENDED_FOURTH, "sus4", (60, 65, 67))
    colored = _pattern_score(
        [72] * 8,
        (_joined(0, [72] * 8),),
        ensemble="villa",
        bpm=100,
        bands={0: "mf"},
        chords={0: suspended},
        character="rally",
    )
    assert any(note.midi is not None and note.midi % 12 == 5 for note in colored.support)


def test_preludio_rings_for_two_bars_and_budgets_the_bell() -> None:
    melody = [72] * 32
    score = _pattern_score(
        melody,
        (_joined(0, melody),),
        ensemble="barrios",
        bpm=120,
        character="calm",
        rel_span=0.02,
    )
    attacks = [note.bar for note in score.low if note.midi is not None and not note.tie_stop]
    assert attacks == [0, 2]
    assert all(note.tie_stop for note in score.low if note.midi is not None and note.bar in {1, 3})
    bells = [note for note in score.lead if note.midi is not None and note.midi >= 76]
    assert bells
    assert all(76 <= note.midi <= 83 for note in bells if note.midi is not None)
    assert sorted({note.bar for note in bells}) == [0, 2]
    flat = _pattern_score(
        melody,
        (_joined(0, melody),),
        ensemble="barrios",
        bpm=120,
        character="calm",
        rel_span=0.0,
    )
    assert not any(note.midi is not None and note.midi >= 76 for note in flat.lead)
    # A later calm phrase is still preludio, without the opening bell.
    opening = [60, 62, 64, 65, 67, 65, 64, 62]
    later = [64, 65, 67, 65, 64, 62, 60, 62]
    reduced = _pattern_score(
        opening + later,
        (_joined(0, opening), _joined(8, later)),
        ensemble="barrios",
        bpm=96,
        character="calm",
        rel_span=0.02,
    )
    assert any(note.bar == 0 and note.midi is not None and note.midi >= 76 for note in reduced.lead)
    assert not any(note.bar == 1 and note.midi is not None and note.midi >= 76 for note in reduced.lead)


def test_cantabile_locks_a_third_or_sixth_under_the_line() -> None:
    shape = [67, 69, 71, 72, 71, 69, 67, 65]
    early = _pattern_score(shape, (_joined(0, shape),), ensemble="classic", bpm=88, character="calm")
    lead = [note for note in early.lead if note.midi is not None]
    support = [note for note in early.support if note.midi is not None]
    assert [note.beat for note in support] == [note.beat for note in lead]
    for sung, inner in zip(lead, support):
        assert inner.midi is not None and sung.midi is not None
        assert inner.midi < sung.midi
        assert (_degree(sung.midi) - _degree(inner.midi)) % 7 in {2, 5}
    # At 90 the opening phrase stays a study. The next calm phrase sings in thirds.
    fast = _pattern_score(
        shape + shape,
        (_joined(0, shape), _joined(8, shape)),
        ensemble="classic",
        bpm=96,
        character="calm",
    )
    opening_lead = [note for note in fast.lead if note.bar == 0 and note.midi is not None]
    opening_inner = [note for note in fast.support if note.bar == 0 and note.midi is not None]
    assert len(opening_inner) < len(opening_lead)
    sung = [note for note in fast.lead if note.bar == 1 and note.midi is not None]
    inner = [note for note in fast.support if note.bar == 1 and note.midi is not None]
    assert [note.beat for note in inner] == [note.beat for note in sung]


def test_thumb_cantabile_sings_in_the_cello_window_only_in_trio_or_bridge() -> None:
    rising = [60, 62, 64, 65, 67, 69, 71, 72]
    trio = (FormSection(0, 2, "phrase", 1, trio=True),)
    score = _pattern_score(
        rising + rising,
        (_joined(0, rising), _joined(8, rising)),
        ensemble="villa",
        bpm=108,
        sections=trio,
        character="rally",
    )
    thumb = [note for note in score.low if note.bar == 1 and note.midi is not None]
    assert thumb
    assert all(48 <= note.midi <= 64 for note in thumb if note.midi is not None)
    assert [note.midi for note in thumb] == sorted(note.midi for note in thumb if note.midi is not None)
    assert not any(note.bar == 1 and abs(note.beat) < 1e-6 and note.midi is not None for note in score.lead)
    assert {round(note.beat, 2) for note in score.lead if note.bar == 1 and note.midi is not None} == {1.0, 3.0}
    bridge = (FormSection(0, 2, "phrase", 1, bridge=True),)
    slow = _pattern_score(
        [60, 62, 64, 65, 67, 64] * 2,
        (_joined(0, [60, 62, 64, 65, 67, 64]), _joined(6, [60, 62, 64, 65, 67, 64])),
        ensemble="villa",
        bpm=72,
        meter=METER_34,
        sections=bridge,
        character="calm",
        bands={0: "mp", 1: "mp"},
    )
    assert {round(note.beat, 2) for note in slow.lead if note.bar == 1 and note.midi is not None} == {1.0, 2.0}
    bare = (FormSection(0, 2, "phrase", 1),)
    plain = _pattern_score(
        rising + rising,
        (_joined(0, rising), _joined(8, rising)),
        ensemble="barrios",
        bpm=120,
        sections=bare,
        character="calm",
    )
    assert max(note.midi for note in plain.low if note.midi is not None) <= 53
    assert any(note.bar == 1 and abs(note.beat) < 1e-6 and note.midi is not None for note in plain.lead)
    wide = [48, 53, 59, 64, 67, 72, 76, 79]
    fitted = _pattern_score(
        rising + wide,
        (_joined(0, rising), _joined(8, wide)),
        ensemble="villa",
        bpm=108,
        sections=trio,
    )
    line = [note.midi for note in fitted.low if note.bar == 1 and note.midi is not None]
    assert line
    assert all(48 <= note <= 64 for note in line)
    assert line[-1] >= line[0]
    assert all(right >= left for left, right in zip(line, line[1:]))


def test_vals_interlocks_six_eight_with_three_four() -> None:
    opening = [60, 62, 64, 65, 67, 69]
    dance = [60, 62, 64, 65, 67, 69, 60, 62, 64, 65, 67, 65]
    score = _pattern_score(
        opening + dance,
        (_joined(0, opening), _joined(6, dance)),
        ensemble="barrios",
        bpm=120,
        meter=METER_68,
        sections=(FormSection(0, 3, "phrase", 1, trio=True),),
        chords={0: C, 1: C, 2: F},
        character="volatile",
    )
    assert {round(note.beat, 2) for note in score.low if note.bar == 1 and note.midi is not None} >= {0.0, 1.5, 2.0, 2.75}
    assert {round(note.beat, 2) for note in score.support if note.bar == 1 and note.midi is not None} >= {0.5, 1.0, 2.0, 2.5}
    accent = next(note for note in score.low if note.bar == 1 and abs(note.beat - 2.0) < 1e-6)
    assert accent.accent
    approach = next(note for note in score.low if note.bar == 1 and abs(note.beat - 2.75) < 1e-6)
    assert approach.midi == 52
    # A held phrase in the same trio keeps the tremolo instead of the dance.
    held = _pattern_score(
        opening + [72] * 6,
        (_joined(0, opening), _joined(6, [72] * 6)),
        ensemble="barrios",
        bpm=120,
        meter=METER_68,
        sections=(FormSection(0, 2, "phrase", 1, trio=True),),
        character="volatile",
    )
    assert any(note.bar == 1 and note.duration_beats == 0.25 for note in held.lead if note.midi is not None)


def test_scale_and_grand_solo_ornament_without_moving_the_strong_beats() -> None:
    opening = [60, 62, 64, 65, 67, 65, 64, 62]
    level0 = [60, 62, 64, 65, 67, 65, 64, 62]
    level1 = [60, 62, 64, 67, 67, 67, 67, 67]
    level2 = [60, 62, 64, 65, 67, 65, 64, 62]
    tail = [64] * 32
    pitches = opening + level0 + level1 + level2 + tail
    phrases = tuple(_joined(index * 8, pitches[index * 8 : (index + 1) * 8]) for index in range(4)) + (
        _joined(32, tail),
    )
    bands = {0: "f", 1: "mp", 2: "mp", 3: "f", **{bar: "mp" for bar in range(4, 8)}}
    section = (FormSection(0, 8, "phrase", 0),)
    score = _pattern_score(
        pitches,
        phrases,
        ensemble="classic",
        bpm=96,
        bands=bands,
        sections=section,
        character="rally",
    )
    assert [beat for beat, _midi in _on(score.support, 1)] == [1.0, 3.0]
    assert 1.5 in [beat for beat, _midi in _on(score.support, 2)]
    sixteenths = [note for note in score.lead if note.duration_beats <= 0.25 and note.midi is not None]
    assert sixteenths
    assert {note.bar for note in sixteenths} == {3}
    assert len({note.bar for note in sixteenths}) / score.bars <= 0.15
    target = next(note for note in sixteenths if note.bar == 3 and abs(note.beat - 2.0) < 1e-6)
    assert target.midi == 67
    assert all(note.midi is not None and note.midi % 12 in _MAJOR for note in sixteenths)
    assert all(note.midi is not None for note in (score.lead[0], score.support[0], score.low[0]))
    assert all(
        any(note.bar == 0 and abs(note.beat) < 1e-6 and note.midi is not None for note in voice)
        for voice in (score.lead, score.support, score.low)
    )
    assert not any(
        note.bar == 2 and note.midi is not None and note.beat <= 3.5 + 1e-6 < note.beat + note.duration_beats
        for note in (*score.lead, *score.support, *score.low)
    )
    quiet = _pattern_score(
        pitches,
        phrases,
        ensemble="classic",
        bpm=88,
        bands=bands,
        sections=section,
        character="rally",
    )
    assert quiet.divisions == 2
    assert not any(note.bar == 0 and abs(note.beat) < 1e-6 and note.midi is not None for note in quiet.support)
    assert any(
        note.bar == 2 and note.midi is not None and note.beat <= 3.5 + 1e-6 < note.beat + note.duration_beats
        for note in quiet.low
    )


def test_barrios_scale_may_lead_by_a_chromatic_and_a_hold_can_wave() -> None:
    opening = [64] * 8
    rise = [60, 62, 64, 65, 67, 65, 64, 62]
    tail = [64] * 48
    pitches = opening + rise + tail
    phrases = (_joined(0, opening), _joined(8, rise), _joined(16, tail))
    score = _pattern_score(
        pitches,
        phrases,
        ensemble="barrios",
        bpm=96,
        sections=(FormSection(0, 8, "phrase", 0),),
        character="rally",
        bands={bar: "mf" for bar in range(8)},
    )
    run = [note for note in score.lead if note.bar == 1 and note.duration_beats <= 0.25 and note.midi is not None]
    assert run
    chromatic = [note for note in run if note.midi is not None and note.midi % 12 not in _MAJOR]
    assert len(chromatic) <= 1
    if chromatic:
        assert abs(chromatic[0].midi - 72) == 1 or abs(chromatic[0].midi - 67) <= 1
    hold = [72] * 16
    rest = [64] * (8 * 13)
    wave_pitches = opening + hold + rest
    wave = _pattern_score(
        wave_pitches,
        (_joined(0, opening), _joined(8, hold), _joined(24, rest)),
        ensemble="barrios",
        bpm=120,
        sections=(FormSection(0, 16, "phrase", 0),),
        character="volatile",
        bands={bar: "f" for bar in range(16)},
    )
    for bar in (1, 2):
        lead = [note for note in wave.lead if note.bar == bar and note.midi is not None]
        assert len(lead) == 16
        assert all(note.duration_beats == 0.25 for note in lead)
        assert {round(note.beat, 2) for note in wave.low if note.bar == bar and note.midi is not None} == {0.0, 2.0}
        assert not any(note.bar == bar and note.midi is not None for note in wave.support)
        anchors = [note.midi for note in lead if abs(note.beat - round(note.beat)) < 1e-6]
        assert anchors == [72, 72, 72, 72]
        moving = [note.midi for note in lead if abs((note.beat * 4) % 4 - 2) < 1e-6]
        assert moving and all(note != 72 for note in moving)
    # The third bar of the hold is ordinary tremolo again: thumb on every quarter.
    assert {round(note.beat, 2) for note in wave.low if note.bar == 3 and note.midi is not None} == {0.0, 1.0, 2.0, 3.0}


def _bare(lead=(), support=(), low=(), slots=None, bars: int = 1, bar_beats: float = 4.0):
    if slots is None:
        slots = (ChordSlot(0, bars, C, "sideway", "phrase"),)
    return Score(
        title="Guitar",
        bpm=88,
        bars=bars,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=slots,
        high=(),
        lead=tuple(lead),
        support=tuple(support),
        comp=(),
        low=tuple(low),
        dynamics=(),
        harmonies=(),
        liquidity=(),
        phrases=(),
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant="guitar",
        ensemble="classic",
        divisions=4,
        beats=4 if bar_beats == 4 else 6,
        beat_type=4,
        bar_beats=bar_beats,
    )


def test_assert_playable_rejects_a_profile_that_does_not_own_the_bass() -> None:
    approach = _bare(
        low=(NoteEvent(bar=0, beat=3.5, midi=42, duration_beats=0.5, voice=3),),
        slots=(ChordSlot(0, 1, C, "sideway", "phrase"), ChordSlot(1, 1, G, "sideway", "phrase")),
        bars=2,
    )
    with pytest.raises(ValueError):
        assert_playable(approach, C_KEY, "study")
    assert_playable(approach, C_KEY, "villa_pattern")
    with pytest.raises(ValueError):
        assert_playable(approach, C_KEY, "barrios_preludio")
    assert_playable(approach, C_KEY, "barrios_dance")

    lament = _bare(
        low=(
            NoteEvent(bar=0, beat=0.0, midi=48, duration_beats=1.5, voice=3),
            NoteEvent(bar=0, beat=1.5, midi=47, duration_beats=0.5, voice=3),
        )
    )
    with pytest.raises(ValueError):
        assert_playable(lament, C_KEY, "study")
    assert_playable(lament, C_KEY, "elegiaque")

    sung = _bare(low=(NoteEvent(bar=0, beat=0.0, midi=60, duration_beats=1.0, voice=3),))
    with pytest.raises(ValueError):
        assert_playable(sung, C_KEY, "study")
    assert_playable(sung, C_KEY, "thumb_cantabile")

    stretched = _bare(
        lead=(NoteEvent(bar=0, beat=0.0, midi=76, duration_beats=1.0, voice=1),),
        low=(NoteEvent(bar=0, beat=0.0, midi=43, duration_beats=1.0, voice=3),),
    )
    with pytest.raises(ValueError):
        assert_playable(stretched, C_KEY, "study")
    opens = _bare(
        lead=(NoteEvent(bar=0, beat=0.0, midi=64, duration_beats=1.0, voice=1),),
        support=(NoteEvent(bar=0, beat=0.0, midi=55, duration_beats=1.0, voice=2),),
        low=(NoteEvent(bar=0, beat=0.0, midi=40, duration_beats=1.0, voice=3),),
    )
    assert_playable(opens, C_KEY, "study")


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


def _runs_of(start: int, notes: list[int]) -> tuple[Run, ...]:
    runs: list[Run] = []
    cursor = 0
    while cursor < len(notes):
        nxt = cursor + 1
        while nxt < len(notes) and notes[nxt] == notes[cursor]:
            nxt += 1
        runs.append(Run(start + cursor, nxt - cursor, notes[cursor]))
        cursor = nxt
    return tuple(runs)


def _barrios_score(
    groups: list[list[int]],
    chords: list,
    *,
    bpm: int = 120,
    meter=METER_44,
    character: str = "rally",
    band: str = "mf",
):
    phrases = []
    pitches: list[int] = []
    for notes in groups:
        phrases.append(Phrase(len(pitches), len(pitches) + len(notes), _runs_of(len(pitches), notes), False))
        pitches.extend(notes)
    bars = len(chords)
    slots = tuple(ChordSlot(bar, 1, chord, "sideway", "phrase") for bar, chord in enumerate(chords))
    with compose_meter(meter):
        score = render_guitar_score(
            title="Guitar",
            chosen=(),
            sample_indexes=None,
            slots=slots,
            pitches=pitches,
            phrases=tuple(phrases),
            dynamics=(),
            bands=[band] * bars,
            band_at={bar: band for bar in range(bars)},
            musical_bars=bars,
            total_eighths=len(pitches),
            bpm=bpm,
            ensemble="barrios",
            harmonies=(),
            character=character,  # type: ignore[arg-type]
        )
    # Every voice has to fill the bar. Overlapping chord tones (tremolo root
    # and fifth) count once; a gap or a note past the bar line fails.
    for bar in range(bars):
        for voice in (score.lead, score.support, score.low):
            _assert_covers(voice, bar, score.bar_beats)
    score_to_musicxml(score)
    return score


def _assert_covers(events, bar: int, bar_beats: float) -> None:
    spans = sorted(
        (event.beat, event.beat + event.duration_beats)
        for event in events
        if event.bar == bar
    )
    assert spans, f"voice has no events in bar {bar}"
    cursor = 0.0
    for start, end in spans:
        assert start <= cursor + 1e-6, f"gap before beat {start} in bar {bar}"
        cursor = max(cursor, end)
    assert abs(cursor - bar_beats) < 1e-6


def _onsets(events, bar: int) -> list[float]:
    return sorted(round(event.beat, 2) for event in events if event.bar == bar and event.midi is not None)


def _notes_at(events, bar: int, beat: float) -> list[NoteEvent]:
    return [
        event
        for event in events
        if event.bar == bar and event.midi is not None and abs(event.beat - beat) < 1e-6
    ]


# Chord tones inside the guitar treble window, neighbours always different,
# so each eighth is a new melody attack and strong-beat quantize leaves it.
_C_RUN = [60, 64, 67, 72, 76, 79, 67, 64]
_G_RUN = [67, 71, 74, 79, 71, 74, 67, 71]
_C_RUN_68 = [60, 64, 67, 72, 76, 79]
_G_RUN_68 = [67, 71, 74, 79, 71, 67]


def test_barrios_choro_dances_only_the_later_running_phrase() -> None:
    # Opening body phrase stays arpeggio. The next running phrase, above 100
    # and not calm, is choro: bass on the beat, inner notes on the off sixteenths.
    score = _barrios_score([_C_RUN, _C_RUN, _C_RUN], [C, C, C], character="rally")
    assert score.divisions == 4
    assert 0.75 not in _onsets(score.support, 0)
    assert 0.75 not in _onsets(score.low, 0)
    assert all(note.duration_beats != 0.25 for note in score.lead if note.bar == 0 and note.midi is not None)

    low = _notes_at(score.low, 1, 0.0) + _notes_at(score.low, 1, 1.0)
    low += _notes_at(score.low, 1, 2.0) + _notes_at(score.low, 1, 3.0)
    assert [round(note.beat, 2) for note in low] == [0.0, 1.0, 2.0, 3.0]
    assert [note.midi % 12 for note in low] == [0, 7, 0, 7]
    assert all(note.duration_beats == 0.25 for note in low)
    # Same chord next bar: sixteenth 15 stays an inner note, not a leading tone.
    assert _onsets(score.support, 1) == [0.75, 1.5, 1.75, 2.75, 3.5, 3.75]
    assert all(note.duration_beats == 0.25 for note in score.support if note.bar == 1 and note.midi is not None)
    # Sixteenth 2 is the melody alone. The sung pitch is the data eighth.
    assert [note.midi for note in _notes_at(score.lead, 1, 0.5)] == [64]
    assert _onsets(score.low, 1).count(0.5) == 0
    assert 0.5 not in _onsets(score.support, 1)
    melody_beats = [index * 0.5 for index in range(8)]
    assert _onsets(score.lead, 1) == melody_beats

    calm = _barrios_score([_C_RUN, _C_RUN], [C, C], character="calm")
    assert 0.75 not in _onsets(calm.support, 1)
    assert all(note.duration_beats != 0.25 for note in calm.low if note.midi is not None)

    with compose_meter(METER_34):
        three = _barrios_score(
            [_C_RUN_68, _C_RUN_68],
            [C, C],
            meter=METER_34,
            character="rally",
        )
    assert 0.75 not in _onsets(three.support, 1)
    assert three.divisions == 4

    at_100 = _barrios_score([_C_RUN, _C_RUN], [C, C], bpm=100, character="rally")
    assert at_100.divisions == 4
    assert 0.75 not in _onsets(at_100.support, 1)
    assert all(note.duration_beats != 0.25 for note in at_100.support if note.midi is not None)


def test_barrios_scherzo_picks_tremolo_polca_or_hemiola_by_the_line() -> None:
    held = [72] * 6
    tremolo = _barrios_score(
        [_C_RUN_68, held],
        [C, C],
        meter=METER_68,
        character="rally",
        band="mp",
    )
    assert all(note.duration_beats != 0.25 for note in tremolo.lead if note.bar == 0 and note.midi is not None)
    assert _onsets(tremolo.lead, 1) == [index * 0.25 for index in range(12)]
    assert all(note.duration_beats == 0.25 for note in tremolo.lead if note.bar == 1 and note.midi is not None)

    # A running line at band f is hemiola: accompaniment only on eighths 0, 2, 4.
    hemiola = _barrios_score(
        [_G_RUN_68, _G_RUN_68, _G_RUN_68],
        [G, G, G],
        meter=METER_68,
        character="rally",
        band="f",
    )
    accompaniment = set(_onsets(hemiola.low, 1)) | set(_onsets(hemiola.support, 1))
    assert accompaniment == {0.0, 1.0, 2.0}
    assert {0.5, 1.5, 2.5} <= set(_onsets(hemiola.lead, 1))
    assert 2.75 not in _onsets(hemiola.low, 1)

    # The same band on a held line stays tremolo. Hemiola never repeats sixteenths.
    held_forte = _barrios_score(
        [_C_RUN_68, held],
        [C, C],
        meter=METER_68,
        character="rally",
        band="f",
    )
    assert _onsets(held_forte.lead, 1) == [index * 0.25 for index in range(12)]

    polca = _barrios_score(
        [_G_RUN_68, _G_RUN_68, _G_RUN_68],
        [G, G, G],
        meter=METER_68,
        character="rally",
        band="mp",
    )
    assert _onsets(polca.low, 1) == [0.0, 1.5]
    assert [note.midi % 12 for note in _notes_at(polca.low, 1, 0.0)] == [7]
    assert [note.midi % 12 for note in _notes_at(polca.low, 1, 1.5)] == [2]
    assert _onsets(polca.support, 1) == [0.5, 1.0, 2.0, 2.5]
    assert all(note.duration_beats == 0.25 for note in polca.support if note.bar == 1 and note.midi is not None)
    assert 2.75 not in _onsets(polca.low, 1)


def test_barrios_dance_approaches_a_fifth_and_tapers_when_it_leaves() -> None:
    # G falling to C is one fifth. The dance continues, so the last sixteenth
    # is a bass note one semitone under the next root.
    choro = _barrios_score([_C_RUN, _G_RUN, _C_RUN], [C, G, C], character="rally")
    approach = _notes_at(choro.low, 1, 3.75)
    assert len(approach) == 1
    assert approach[0].duration_beats == 0.25
    assert approach[0].midi is not None and approach[0].midi % 12 == 11
    assert 40 <= approach[0].midi <= 53
    assert not _notes_at(choro.support, 1, 3.75)
    guard_chromatic_approach(approach[0].midi, 0, profile="barrios_dance")
    with pytest.raises(ValueError):
        guard_chromatic_approach(approach[0].midi, 0, profile="study")

    polca = _barrios_score(
        [_C_RUN_68, _G_RUN_68, _C_RUN_68],
        [C, G, C],
        meter=METER_68,
        character="rally",
        band="mp",
    )
    leading = _notes_at(polca.low, 1, 2.75)
    assert len(leading) == 1
    assert leading[0].midi is not None and leading[0].midi % 12 == 11
    assert leading[0].duration_beats == 0.25
    kept = _notes_at(polca.support, 1, 2.5)
    assert len(kept) == 1 and kept[0].duration_beats == 0.25
    guard_chromatic_approach(leading[0].midi, 0, profile="barrios_dance")
    with pytest.raises(ValueError):
        guard_chromatic_approach(leading[0].midi, 0, profile="study")

    # The next phrase is held, so it is tremolo. The dance bar rests its last
    # sixteenth and gives the last eighth of the melody and the inner voice
    # back as a breath, even though the roots fall a fifth.
    leaving = _barrios_score(
        [_C_RUN, _G_RUN, [72] * 8],
        [C, G, C],
        character="rally",
    )
    assert 3.75 not in _onsets(leaving.low, 1)
    assert 3.75 not in _onsets(leaving.support, 1)
    assert 3.5 not in _onsets(leaving.lead, 1)
    assert 3.5 not in _onsets(leaving.support, 1)
    assert _onsets(leaving.lead, 2) == [index * 0.25 for index in range(16)]
