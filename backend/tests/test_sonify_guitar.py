"""Classical guitar is one nylon part, and the long forms keep the symphony clock."""

import math

import pytest

from app.sonify.chords import KIND_SUSPENDED_FOURTH, C, Chord, DM, EM, F, G
from app.sonify.ensemble import ensemble_for
from app.sonify.form import METER_34, METER_44, METER_68, ChordSlot, FormSection, compose_meter
from app.sonify.guitar import (
    _MELODY_APEX,
    _apex_eighths,
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
from app.sonify.keys import C_KEY, D_KEY, compose_register, movement_character, register_for
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
    assert ensemble_for("guitar", "brouwer") == "brouwer"
    with pytest.raises(ValueError):
        ensemble_for("guitar", "wood")
    with pytest.raises(ValueError):
        ensemble_for("symphony", "brouwer")


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
    assert {round(note.beat, 2) for note in score.support if note.bar == 1 and note.midi is not None} == {1.0, 3.0}
    assert all(
        note.duration_beats == 0.5
        for note in (*score.lead, *score.support)
        if note.bar == 1 and note.midi is not None
    )
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
    # Barrios arpeggio is Preludio: a two-bar ringing root and flowing eighths.
    assert _onset_beats(score.low, 0) == [0.0]
    assert _onset_beats(score.low, 1) == [0.0]
    assert all(note.tie_stop for note in score.low if note.bar == 1 and note.midi is not None)
    assert _onset_beats(score.support, 1) == [index * 0.5 for index in range(8)]


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
    _assert_engraved(slow, "elegiaque")

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
    # At 90–100 BPM a running Barrios phrase falls back to reduced Preludio
    # (two-bar ringing bass and flowing eighths matching calm), not Sor's study.
    assert _onsets(at_100.low, 1) == [0.0]
    assert all(note.tie_stop for note in at_100.low if note.bar == 1 and note.midi is not None)
    assert _onsets(at_100.support, 1) == _onsets(calm.support, 1)
    assert 0.0 in _onsets(at_100.support, 1) and 0.5 in _onsets(at_100.support, 1)
    at_96 = _barrios_score([_C_RUN, _C_RUN], [C, C], bpm=96, character="rally")
    assert _onsets(at_96.low, 1) == [0.0]
    assert all(note.tie_stop for note in at_96.low if note.bar == 1 and note.midi is not None)
    assert _onsets(at_96.support, 1) == _onsets(calm.support, 1)


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

    # D7 falling to G is also a fifth, and its approach note is F# (off C major).
    from app.sonify.chords import D7
    from app.sonify.harmony import VILLA

    d7_run = [62, 66, 69, 72, 74, 72, 69, 66]
    sharp_choro = _barrios_score([_C_RUN, d7_run, _G_RUN], [C, D7, G], character="rally")
    fsharp = _notes_at(sharp_choro.low, 1, 3.75)
    assert len(fsharp) == 1 and fsharp[0].midi is not None and fsharp[0].midi % 12 == 6
    sharp_xml = score_to_musicxml(sharp_choro).split("</measure>")[1]
    assert "<step>F</step>\n          <alter>1</alter>" in sharp_xml

    # Flat Villa planing chords (Bbsus2, Ebsus2) spell their bass roots as Bb and Eb, not A# and D#.
    bbsus2 = next(chord for chord in VILLA.extra("major") if chord.name == "Bbsus2")
    ebsus2 = next(chord for chord in VILLA.extra("major") if chord.name == "Ebsus2")
    flat_villa = _pattern_score(
        [72] * 16,
        (_joined(0, [72] * 16),),
        ensemble="villa",
        bpm=100,
        chords={0: bbsus2, 1: ebsus2},
        character="calm",
    )
    flat_xml = score_to_musicxml(flat_villa)
    first_bar, second_bar = flat_xml.split("</measure>")[:2]
    assert "<step>B</step>\n          <alter>-1</alter>" in first_bar
    assert "<step>A</step>\n          <alter>1</alter>" not in first_bar
    assert "<step>E</step>\n          <alter>-1</alter>" in second_bar
    assert "<step>D</step>\n          <alter>1</alter>" not in second_bar

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


def _pitched(events: tuple[NoteEvent, ...], bar: int) -> list[NoteEvent]:
    return [note for note in events if note.bar == bar and note.midi is not None]


def _frame_score(
    ensemble: str,
    frame: int,
    *,
    character: str = "rally",
    mode: str = "major",
    body: int = 4,
):
    """Intro and outro of `frame` bars around a short body, with the form attached."""
    bpm = {"classic": 88, "villa": 100, "barrios": 120, "brouwer": 108}[ensemble]
    epb = 8
    phrases = (
        _held(0, frame * epb, 67),
        _held(frame * epb, body * epb, 67),
        _held((frame + body) * epb, frame * epb, 67),
    )
    total = frame + body + frame
    kinds = {
        bar: ("intro" if bar < frame else "outro" if bar >= frame + body else "phrase")
        for bar in range(total)
    }
    sections = (
        FormSection(0, frame, "intro", 0),
        FormSection(frame, frame + body, "phrase", 0),
        FormSection(frame + body, total, "outro", 0),
    )
    return _guitar(
        phrases,
        ensemble=ensemble,
        bpm=bpm,
        character=character,
        mode=mode,
        kinds=kinds,
        sections=sections,
    )


def _assert_under_apex(score, bars: tuple[int, ...] | list[int]) -> None:
    for bar in bars:
        for voice in (score.lead, score.support, score.low):
            for note in _pitched(voice, bar):
                assert note.velocity is not None and note.velocity < _MELODY_APEX


def test_a_flat_phrase_does_not_mark_every_eighth_as_the_apex() -> None:
    flat = Phrase(0, 16, (Run(0, 16, 60),), False)
    assert flat.rise == 0
    assert _apex_eighths((flat,)) == set()
    rising = Phrase(
        0,
        4,
        (Run(0, 1, 60), Run(1, 1, 62), Run(2, 1, 64), Run(3, 1, 62)),
        False,
    )
    assert _apex_eighths((rising,)) == {2}


def test_intro_and_outro_frames_are_not_hammered_at_the_apex() -> None:
    for ensemble in ("classic", "villa", "barrios"):
        score = render(_bars(), title="Guitar", variant="guitar", ensemble=ensemble)  # type: ignore[arg-type]
        _assert_under_apex(score, (0, 1, 32, 33))
        assert score_to_musicxml(score).split("</measure>")[0].count("<chord") == 0


def test_composer_intro_and_outro_frames_for_two_and_four_bars() -> None:
    from app.sonify.guitar_frame import frame_roles

    assert frame_roles(2) == [0, 1]
    assert frame_roles(4) == [0, 1, 2, 3]
    assert frame_roles(1) == [0]
    assert frame_roles(6) == [0, 0, 1, 2, 2, 3]

    classic = _frame_score("classic", 2)
    assert classic.divisions == 2
    assert _onset_beats(classic.low, 0) == [0.0]
    assert all(note.velocity <= 52 for note in _pitched(classic.low, 0))
    # Bar 2 of the direct frame is the dominant, then a root pickup into the body.
    assert any(note.midi % 12 in {2, 5, 7, 11} for note in _pitched(classic.low, 1) if note.beat < 3)
    assert any(note.staccato for note in (*classic.lead, *classic.low) if note.bar == classic.bars - 2)
    assert any(note.duration_beats >= 3 for note in _pitched(classic.low, classic.bars - 1))
    _assert_under_apex(classic, (0, 1, classic.bars - 2, classic.bars - 1))
    assert_playable(classic, C_KEY, "study")

    classic_long = _frame_score("classic", 4)
    assert any(note.staccato for note in (*classic_long.lead, *classic_long.low) if note.bar == 0)
    assert {0.0, 1.5} <= set(_onset_beats(classic_long.low, 2))
    assert any(note.beat == 0 and note.duration_beats >= 2 for note in _pitched(classic_long.low, 3))
    assert any(note.duration_beats >= 3 for note in _pitched(classic_long.low, classic_long.bars - 1))
    _assert_under_apex(classic_long, (0, 1, 2, 3, classic_long.bars - 4, classic_long.bars - 1))
    assert_playable(classic_long, C_KEY, "study")

    barrios = _frame_score("barrios", 2)
    bells = _pitched(barrios.lead, 0)
    assert len(bells) >= 2
    assert all(note.midi >= 76 and note.velocity <= 52 for note in bells)
    assert _pitched(barrios.low, 0) == []
    assert 0.0 in _onset_beats(barrios.low, 1)
    final = _pitched(barrios.lead, barrios.bars - 1)
    assert final and all(note.midi >= 76 and note.velocity <= 48 for note in final)
    assert _pitched(barrios.low, barrios.bars - 1)
    for bar in (0, 1, barrios.bars - 2, barrios.bars - 1):
        assert _sixteenths(barrios.lead, bar) == []
    body = {bar: "barrios_tremolo" if 2 <= bar < 6 else "study" for bar in range(barrios.bars)}
    assert_playable(barrios, C_KEY, body)

    barrios_long = _frame_score("barrios", 4)
    assert len(_pitched(barrios_long.lead, 0)) >= 2 and _pitched(barrios_long.low, 0) == []
    assert all(note.midi >= 76 for note in _pitched(barrios_long.lead, 0))
    assert 0.0 in _onset_beats(barrios_long.low, 1)
    assert any(note.midi >= 76 and note.velocity <= 48 for note in _pitched(barrios_long.lead, barrios_long.bars - 1))
    long_body = {bar: "barrios_tremolo" if 4 <= bar < 8 else "study" for bar in range(barrios_long.bars)}
    assert_playable(barrios_long, C_KEY, long_body)

    villa = _frame_score("villa", 2)
    assert villa.divisions == 2
    assert 0.0 in _onset_beats(villa.low, 0)
    assert min(_onset_beats(villa.support, 0)) > 0
    assert min(_onset_beats(villa.lead, 0)) >= min(_onset_beats(villa.support, 0))
    assert 0.5 in _onset_beats(villa.lead, 1)
    assert any(note.accent for note in _pitched(villa.lead, 1))
    assert 0.5 in _onset_beats(villa.lead, villa.bars - 1)
    _assert_under_apex(villa, (0, 1, villa.bars - 2, villa.bars - 1))
    assert_playable(villa, C_KEY, "study")

    villa_long = _frame_score("villa", 4)
    assert 0.0 in _onset_beats(villa_long.low, 0)
    assert 0.0 in _onset_beats(villa_long.low, 1)
    assert len(_onset_beats(villa_long.lead, 2)) >= 6
    assert any(note.accent and note.beat == 0.0 for note in _pitched(villa_long.lead, 3))
    assert_playable(villa_long, C_KEY, "study")


def test_a_daily_piece_keeps_one_pattern_across_the_body() -> None:
    def bass(score, bar: int) -> list[float]:
        return _onset_beats(score.low, bar)

    plain = render(_bars(), title="Guitar", variant="guitar", ensemble="classic")
    for bar in (2, 10, 20, 30):
        assert bass(plain, bar) == [0.0, 2.0]
        assert _sixteenths(plain.lead, bar) == []
    assert len({note.velocity for note in plain.lead if note.midi is not None and 2 <= note.bar <= 30}) > 1

    selloff = render(_bars(), title="Guitar", variant="guitar", ensemble="classic", character="selloff")
    for bar in (2, 10, 20, 30):
        assert bass(selloff, bar) == [0.0, 1.5, 2.0, 3.5]

    calm = render(_bars(), title="Guitar", variant="guitar", ensemble="classic", character="calm")
    matched = [
        bar
        for bar in range(2, 31)
        if _onset_beats(calm.support, bar) and _onset_beats(calm.support, bar) == _onset_beats(calm.lead, bar)
    ]
    assert len(matched) >= 20

    villa = render(_bars(), title="Guitar", variant="guitar", ensemble="villa", character="rally")
    assert villa.divisions == 2
    assert sum(1 for bar in range(2, 32) if 0.5 in _onset_beats(villa.support, bar)) == 30
    quiet = render(_bars(), title="Guitar", variant="guitar", ensemble="villa", character="calm")
    assert all(0.5 not in _onset_beats(quiet.support, bar) for bar in range(2, 32))

    barrios = render(_bars(), title="Guitar", variant="guitar", ensemble="barrios")
    assert _sixteenths(barrios.lead, 2) == [index * 0.25 for index in range(16)]
    assert _sixteenths(barrios.lead, 4) == [index * 0.25 for index in range(16)]
    tremolo_bars = sum(
        1
        for bar in range(2, 32)
        if sum(1 for note in _pitched(barrios.lead, bar) if abs(note.duration_beats - 0.25) < 1e-9) >= 8
    )
    assert tremolo_bars >= 20
    sung = render(_bars(), title="Guitar", variant="guitar", ensemble="barrios", character="calm")
    dense = sum(
        1
        for bar in range(2, 32)
        if sum(1 for note in _pitched(sung.lead, bar) if abs(note.duration_beats - 0.25) < 1e-9) >= 12
    )
    assert dense <= 2
    tail = sorted(
        (note.beat, note.velocity)
        for note in _pitched(barrios.lead, 31)
        if note.beat >= 2
    )
    assert [velocity for _beat, velocity in tail] == sorted(
        (velocity for _beat, velocity in tail), reverse=True
    )
    assert len({velocity for _beat, velocity in tail}) == len(tail)


def test_ternary_sections_share_one_pattern_and_hand_off_on_a_bass_pickup() -> None:
    epb = 8
    regions = (
        (0, 2, "intro", False),
        (2, 6, "phrase", False),
        (6, 10, "phrase", True),
        (10, 14, "phrase", False),
        (14, 16, "outro", False),
    )
    phrases = tuple(_held(start * epb, (end - start) * epb, 67) for start, end, _kind, _trio in regions)
    sections = tuple(
        FormSection(start, end, kind, 0, trio=trio) for start, end, kind, trio in regions
    )
    kinds = {bar: ("intro" if bar < 2 else "outro" if bar >= 14 else "phrase") for bar in range(16)}
    classic = _guitar(
        phrases,
        ensemble="classic",
        bpm=88,
        character="rally",
        mode="minor",
        kinds=kinds,
        sections=sections,
    )
    for bar in (3, 11):
        assert _onset_beats(classic.low, bar) == [0.0, 2.0]
    for bar in (6, 7, 8):
        assert _onset_beats(classic.low, bar) == [0.0, 1.5, 2.0, 3.5]
    for bar in (5, 9, 13):
        assert _covers(classic.lead, bar * epb + 7, epb)
        assert _covers(classic.low, bar * epb + 7, epb)
        pickup = _attack_at(classic.low, bar * epb + 7, epb)
        assert pickup is not None and pickup.midi is not None
        assert pickup.midi % 12 in {0, 7}
        assert pickup.midi % 12 != 11
    assert_playable(
        classic,
        C_KEY,
        {bar: "elegiaque" if 6 <= bar < 10 else "study" for bar in range(classic.bars)},
    )

    villa = _guitar(
        phrases,
        ensemble="villa",
        bpm=100,
        character="rally",
        kinds=kinds,
        sections=sections,
    )
    for bar in (3, 11):
        assert 0.5 in _onset_beats(villa.support, bar)
    assert 0.0 not in _onset_beats(villa.lead, 7)
    assert _onset_beats(villa.low, 7) == [0.0]
    assert 0.5 in _onset_beats(villa.support, 11)
    assert_playable(
        villa,
        C_KEY,
        {
            bar: "thumb_cantabile" if 6 <= bar < 10 else "villa_pattern" if 2 <= bar < 14 else "study"
            for bar in range(villa.bars)
        },
    )


def test_a_long_piece_locks_one_pattern_per_session() -> None:
    epb = 8
    phrases = (
        _held(0, 2 * epb, 67),
        _held(2 * epb, 22 * epb, 67),
        _held(24 * epb, 22 * epb, 67),
        _held(46 * epb, 2 * epb, 67),
    )
    sections = (
        FormSection(0, 2, "intro", 0),
        FormSection(2, 24, "phrase", 0),
        FormSection(24, 46, "phrase", 1),
        FormSection(46, 48, "outro", 1),
    )
    kinds = {bar: ("intro" if bar < 2 else "outro" if bar >= 46 else "phrase") for bar in range(48)}
    character_at = tuple("calm" if bar < 24 else "rally" for bar in range(48))
    score = _guitar(
        phrases,
        ensemble="classic",
        bpm=88,
        character="rally",
        character_at=character_at,
        kinds=kinds,
        sections=sections,
    )
    assert _onset_beats(score.support, 4) == _onset_beats(score.lead, 4)
    assert _onset_beats(score.low, 30) == [0.0, 2.0]
    assert 1.5 not in _onset_beats(score.low, 30)
    assert _covers(score.low, 23 * epb + 7, epb)


def _attacks(voice, bar: int) -> list[NoteEvent]:
    return sorted(
        (
            note
            for note in voice
            if note.bar == bar and note.midi is not None and not note.tie_stop
        ),
        key=lambda note: (note.beat, note.voice),
    )


def _covering(voice, bar: int, beat: float) -> NoteEvent | None:
    sounding = [
        note
        for note in voice
        if note.bar == bar
        and note.midi is not None
        and note.beat <= beat + 1e-6 < note.beat + note.duration_beats
    ]
    if not sounding:
        return None
    return max(sounding, key=lambda note: note.beat)


def _assert_voices_separate(score, bar: int, beats: list[float], *, thumb: bool = False) -> None:
    for beat in beats:
        lead = _covering(score.lead, bar, beat)
        inner = _covering(score.support, bar, beat)
        bass = _covering(score.low, bar, beat)
        assert lead is not None and inner is not None and bass is not None
        assert lead.velocity is not None and inner.velocity is not None and bass.velocity is not None
        if thumb:
            assert bass.velocity > lead.velocity
            assert bass.velocity > inner.velocity
        else:
            assert lead.velocity > bass.velocity > inner.velocity


def _assert_engraved(score, profiles) -> None:
    assert_playable(score, profiles=profiles)
    xml = score_to_musicxml(score)
    assert "<part-name>Acoustic Nylon</part-name>" in xml
    assert xml.count("<voice>1</voice>") >= 1
    assert xml.count("<voice>2</voice>") >= 1
    assert xml.count("<voice>3</voice>") >= 1


def test_arpeggio_families_alternate_inner_chord_tones() -> None:
    # A held C under a sustained E keeps several playable inner tones. Each
    # family has to walk across them instead of parking on the top one.
    held = [72] * 8
    study = _pattern_score(
        held,
        (_joined(0, held),),
        bands={0: "mf"},
        bpm=88,
        character="rally",
        rel_span=0.0,
    )
    study_inner = _attacks(study.support, 0)
    study_midis = [note.midi for note in study_inner]
    assert [round(note.beat, 2) for note in study_inner] == [1.0, 1.5, 3.0, 3.5]
    assert study_midis == [study_midis[0], study_midis[1], study_midis[0], study_midis[1]]
    assert study_midis[0] != study_midis[1]
    assert {note % 12 for note in study_midis} == {4, 7}  # i on the 3rd, m on the 5th
    assert {note.velocity for note in study_inner} == {56}
    assert {note.velocity for note in _attacks(study.low, 0)} == {60}
    _assert_engraved(study, "study")

    villa = _pattern_score(
        held,
        (_joined(0, held),),
        ensemble="villa",
        bpm=100,
        bands={0: "mf"},
        character="rally",
        rel_span=0.0,
    )
    villa_inner = _attacks(villa.support, 0)
    villa_midis = [note.midi for note in villa_inner]
    assert len(set(villa_midis)) >= 3
    assert all(left != right for left, right in zip(villa_midis, villa_midis[1:]))
    assert any(note.duration_beats >= 1.0 for note in villa.support if note.midi is not None)
    assert {note.velocity for note in villa_inner} == {56}
    _assert_engraved(villa, "villa_pattern")

    preludio = _pattern_score(
        [72] * 16,
        (_joined(0, [72] * 16),),
        ensemble="barrios",
        bpm=120,
        character="calm",
        rel_span=0.0,
    )
    rolled = _attacks(preludio.support, 0)
    rolled_midis = [note.midi for note in rolled]
    assert [round(note.beat, 2) for note in rolled] == [index * 0.5 for index in range(8)]
    assert rolled_midis[:4] == rolled_midis[4:]
    assert len(set(rolled_midis)) >= 3
    assert all(left != right for left, right in zip(rolled_midis, rolled_midis[1:]))
    for note in rolled:
        if int(round(note.beat * 2)) % 2 == 0:
            assert note.velocity == 56
        else:
            assert note.velocity == 52
    assert _attacks(preludio.low, 0)[0].velocity == 60
    _assert_engraved(preludio, "barrios_preludio")


def test_rising_phrases_swell_toward_the_apex_and_keep_the_voices_apart() -> None:
    # Chord blocks on a rising Villa line open quietly and arrive at the apex.
    rising = [67, 67, 69, 69, 71, 71, 74, 74]
    chord = _pattern_score(
        rising,
        (_joined(0, rising),),
        ensemble="villa",
        bpm=72,
        character="calm",
        bands={0: "mf"},
        rel_span=0.0,
    )
    chord_lead = _attacks(chord.lead, 0)
    chord_inner = _attacks(chord.support, 0)
    chord_bass = _attacks(chord.low, 0)
    assert [note.velocity for note in chord_lead] == [60, 65, 69, 72]
    assert [note.velocity for note in chord_bass] == [54, 54, 60, 64]
    assert [note.velocity for note in chord_inner] == [50, 50, 56, 60]
    assert len({note.midi for note in chord_inner}) >= 2
    assert {note.midi % 12 for note in chord_inner} <= {3, 4, 10, 11}
    _assert_voices_separate(chord, 0, [0.0, 1.0, 2.0, 3.0])
    _assert_engraved(chord, "villa_chord")

    # Cantabile sings 60 up to 72 and eases after the apex. The lower voice
    # stays a third or a sixth and never catches the bass.
    shape = [67, 69, 71, 72, 71, 69, 67, 65]
    cantabile = _pattern_score(
        shape,
        (_joined(0, shape),),
        ensemble="classic",
        bpm=88,
        character="calm",
        rel_span=0.0,
    )
    sung = _attacks(cantabile.lead, 0)
    inner = _attacks(cantabile.support, 0)
    assert [note.velocity for note in sung] == [60, 65, 69, 72, 68, 66, 64]
    assert [note.beat for note in inner] == [note.beat for note in sung]
    assert len({note.midi for note in inner}) >= 3
    for melody_note, lower in zip(sung, inner):
        assert melody_note.midi is not None and lower.midi is not None
        assert (_degree(melody_note.midi) - _degree(lower.midi)) % 7 in {2, 5}
    _assert_voices_separate(cantabile, 0, [note.beat for note in sung])
    _assert_engraved(cantabile, "cantabile")

    # The thumb is the singing voice. It leaves 64 and touches 72 only on the
    # apex, while the off-beat dyads stay bell-soft underneath it.
    line = [60, 62, 64, 65, 67, 69, 71, 72]
    trio = (FormSection(0, 2, "phrase", 1, trio=True),)
    thumb = _pattern_score(
        line + line,
        (_joined(0, line), _joined(8, line)),
        ensemble="villa",
        bpm=108,
        sections=trio,
        character="rally",
        rel_span=0.0,
    )
    cello = _attacks(thumb.low, 1)
    assert [note.velocity for note in cello] == [64, 65, 66, 67, 69, 70, 71, 72]
    assert cello[-1].velocity == 72
    assert all(note.velocity is not None and note.velocity < 72 for note in cello[:-1])
    dyad_beats = [1.0, 3.0]
    for beat in dyad_beats:
        upper = _covering(thumb.lead, 1, beat)
        lower = _covering(thumb.support, 1, beat)
        assert upper is not None and lower is not None
        assert upper.velocity is not None and lower.velocity is not None
        assert 52 <= lower.velocity <= upper.velocity <= 56
    _assert_voices_separate(thumb, 1, dyad_beats, thumb=True)
    _assert_engraved(thumb, {0: "villa_pattern", 1: "thumb_cantabile"})


def test_a_later_tremolo_bar_breathes_and_the_first_bar_stays_locked() -> None:
    # The opening bar is preludio. The next phrase holds, so it tremolos, and
    # only the bar after the phrase has begun is allowed to swell.
    opening = [60, 62, 64, 65, 67, 69, 71, 72]
    held = [67] * 8 + [72] * 8
    score = _pattern_score(
        opening + held,
        (_joined(0, opening), _joined(8, held)),
        ensemble="barrios",
        bpm=120,
        character="rally",
        rel_span=0.0,
    )
    first = [note.velocity for note in _attacks(score.lead, 1)[:4]]
    later = [note.velocity for note in _attacks(score.lead, 2)[:4]]
    assert first == [52, 55, 54, 52]
    assert later == [54, 57, 56, 54]
    first_thumb = {note.velocity for note in score.low if note.bar == 1 and abs(note.beat) < 1e-6 and note.midi}
    later_thumb = {note.velocity for note in score.low if note.bar == 2 and abs(note.beat) < 1e-6 and note.midi}
    assert first_thumb == {58}
    assert later_thumb == {60}
    # thumb > m > i > a still holds after the breath.
    assert 60 > later[1] > later[2] > later[0]
    _assert_engraved(score, {0: "barrios_preludio", 1: "barrios_tremolo", 2: "barrios_tremolo"})


def test_one_day_character_hears_a_hose_session() -> None:
    """0.45% separates a rally from a selloff. A 1.35% range with a mid close is volatile."""
    assert movement_character([100.0, 100.4, 100.8], "1D") == "rally"
    assert movement_character([100.0, 99.6, 99.2], "1D") == "selloff"
    # The close sits in the middle of a 1.8% range (low 99.2, high 101.0), so the day is volatile.
    assert movement_character([100.0, 101.0, 99.2, 100.1], "1D") == "volatile"
    # A wide range (>= 1.0%) that closes near the low (close_pos <= 0.28) or high (>= 0.72) is a trend.
    assert movement_character([100.0, 101.8, 100.2], "1D") == "selloff"
    assert movement_character([100.0, 98.8, 100.1], "1D") == "rally"
    assert movement_character([100.0, 100.1, 100.2], "1D") == "calm"
    # The old 1.2% cut called each of these calm. They are ordinary HOSE days.
    assert movement_character([100.0, 99.11], "1D") == "selloff"
    assert movement_character([100.0, 100.90], "1D") == "rally"
    assert movement_character([100.0, 99.48], "1D") == "selloff"


def test_sor_galop_and_mozart_variations_and_the_op9_overture() -> None:
    galop = _frame_score("classic", 2)
    bass = _pitched(galop.low, 2)
    assert [round(note.beat, 2) for note in bass] == [0.0, 2.0]
    assert all(note.staccato and abs(note.duration_beats - 1.0) < 1e-9 for note in bass)
    assert bass[0].accent
    inner = _pitched(galop.support, 2)
    assert [round(note.beat, 2) for note in inner] == [0.5, 1.5, 2.5, 3.5]
    assert all(note.staccato and note.accent for note in inner)
    assert len({note.midi for note in inner}) == 2
    lead = _pitched(galop.lead, 2)
    downbeat = next(note for note in lead if note.beat == 0.0)
    sparkle = next(note for note in lead if abs(note.beat - 0.5) < 1e-9)
    assert sparkle.staccato and sparkle.midi is not None and downbeat.midi is not None
    assert sparkle.midi > downbeat.midi
    assert _sixteenths(galop.lead, 2) == []
    assert_playable(galop, C_KEY, "study")

    # A narrow rally (< 1.2% span) stays on study; an energetic rally (>= 1.2%) dances Galop.
    narrow_bars = [Bar(close=100.0 + index * 0.015, volume=1000) for index in range(48)]
    narrow_rally = render(narrow_bars, title="Guitar", variant="guitar", ensemble="classic", character="rally")
    assert not any(note.staccato for note in _pitched(narrow_rally.low, 4))

    mozart = _frame_score("classic", 2, character="volatile")
    halves = _pitched(mozart.low, 2)
    assert [round(note.beat, 2) for note in halves] == [0.0, 2.0]
    assert all(abs(note.duration_beats - 2.0) < 1e-9 and not note.staccato for note in halves)
    counter = _pitched(mozart.support, 2)
    assert [round(note.beat, 2) for note in counter] == [0.5, 1.0, 1.5, 2.5, 3.0, 3.5]
    steps = [right.midi - left.midi for left, right in zip(counter, counter[1:]) if left.midi and right.midi]
    assert steps and all(0 < abs(step) <= 2 for step in steps)
    assert_playable(mozart, C_KEY, "study")

    # When the melody leaps across the half-bar, Op. 9 fills the beat-2 gap with passing steps.
    leaping = [64] * 8 + [64, 64, 64, 64, 72, 72, 72, 72]
    bridged = _pattern_score(
        leaping,
        (_joined(0, [64] * 8), _joined(8, [64, 64, 64, 64, 72, 72, 72, 72])),
        ensemble="classic",
        bpm=88,
        character="volatile",
        kinds={0: "intro", 1: "phrase"},
        sections=(FormSection(0, 1, "intro", 0), FormSection(1, 2, "phrase", 0)),
    )
    bridged_inner = _attacks(bridged.support, 1)
    bridged_steps = [abs(right.midi - left.midi) for left, right in zip(bridged_inner, bridged_inner[1:]) if left.midi and right.midi]
    assert any(abs(note.beat - 2.0) < 1e-6 for note in bridged_inner)
    assert bridged_steps and max(bridged_steps) <= 2
    assert_playable(bridged, C_KEY, "study")

    overture = galop
    tonic = _pitched(overture.lead, 0)
    assert [round(note.beat, 2) for note in tonic] == [0.0, 1.5, 2.0, 3.5]
    assert [round(note.duration_beats, 2) for note in tonic] == [1.5, 0.5, 1.5, 0.5]
    assert all(note.staccato for note in tonic if note.duration_beats <= 0.5)
    assert all(note.velocity is not None and note.velocity <= 52 for note in tonic)
    assert {note.voice for note in (*_pitched(overture.lead, 0), *_pitched(overture.support, 0), *_pitched(overture.low, 0)) if note.beat == 0.0} == {1, 2, 3}
    scale = [note.midi for note in _pitched(overture.lead, 1) if note.beat >= 2.0]
    assert len(scale) >= 3
    assert scale == sorted(scale)
    dominant = [note for note in _pitched(overture.low, 1) if note.beat < 3]
    assert {0.0, 1.5, 2.0} <= {round(note.beat, 2) for note in dominant}
    assert any(note.staccato and note.duration_beats <= 0.5 for note in dominant)

    long = _frame_score("classic", 4)
    assert any(note.staccato for note in _pitched(long.lead, 0))
    lyric = _pitched(long.support, 1)
    assert len(lyric) >= 2
    assert all(note.midi is not None and note.midi < _pitched(long.lead, 1)[0].midi for note in lyric)
    flourish = [note.midi for note in _pitched(long.lead, 3) if note.beat >= 2.0]
    assert len(flourish) >= 3 and flourish == sorted(flourish)


def _suite(movement: int, ensemble: str, *, character: str = "rally"):
    from app.sonify.span import attach_frame, month_specs

    form = attach_frame(month_specs("guitar")[movement], "1M")
    return render(_bars(), title="Guitar", variant="guitar", ensemble=ensemble, form=form, character=character)  # type: ignore[arg-type]


def _attack_onsets(voice, bar: int) -> list[float]:
    return sorted(
        round(note.beat, 2)
        for note in voice
        if note.bar == bar and note.midi is not None and not note.tie_stop
    )


_CATEDRAL_SUPPORT_44 = [0.25, 0.5, 0.75, 1.0, 1.25, 1.75, 2.25, 2.5, 2.75, 3.0, 3.25, 3.75]
_CATEDRAL_LEAD_44 = [(0.0, 1.5), (1.5, 0.5), (2.0, 1.5), (3.5, 0.5)]


def _assert_catedral_wave(notes: list[NoteEvent]) -> None:
    """V of three inner tones, or a two-tone line whose neighbours always change."""
    pitches = [note.midi for note in notes if note.midi is not None]
    assert len(pitches) == 6
    if len(set(pitches[:5])) >= 3:
        upper, mid, low, mid_again, upper_again, last = pitches
        assert low < mid < upper
        assert mid_again == mid and upper_again == upper
        assert last in {upper, mid}
    elif len(set(pitches)) >= 2:
        assert all(left != right for left, right in zip(pitches, pitches[1:]))


def _assert_catedral_shimmer(score, bar: int) -> None:
    """Canto stays in the warm nylon layer (54..64) right above the soft inner wave (48..55)."""
    semitones = score.key.semitones
    floor = 59 - semitones
    lead = _attacks(score.lead, bar)
    support = _attacks(score.support, bar)
    assert lead and support
    assert all(note.velocity is not None and 54 <= note.velocity <= 64 for note in lead)
    assert all(note.velocity is not None and 48 <= note.velocity <= 55 for note in support)
    assert all(note.midi is not None and note.midi >= floor for note in lead)
    for voice in (score.lead, score.support, score.low):
        assert not any(note.slur_start or note.slur_stop for note in voice if note.bar == bar)
    for beat in {round(note.beat, 2) for note in support}:
        canto = _covering(score.lead, bar, beat)
        inner = _covering(score.support, bar, beat)
        assert canto is not None and inner is not None
        assert canto.velocity is not None and inner.velocity is not None
        assert 2 <= canto.velocity - inner.velocity <= 16


def _assert_catedral_44(score, bar: int, *, pitches: list[int] | None = None) -> None:
    lead = _attacks(score.lead, bar)
    assert [(round(note.beat, 2), round(note.duration_beats, 2)) for note in lead] == _CATEDRAL_LEAD_44
    if pitches is not None:
        assert [note.midi for note in lead] == pitches
    support = _attacks(score.support, bar)
    assert [round(note.beat, 2) for note in support] == _CATEDRAL_SUPPORT_44
    assert all(abs(note.duration_beats - 0.25) < 1e-9 for note in support)
    onsets = sorted({round(note.beat, 2) for note in (*lead, *support)})
    assert onsets == [index * 0.25 for index in range(16)]
    _assert_catedral_wave(support[:6])
    _assert_catedral_wave(support[6:])
    for beat in (0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75):
        sung = _covering(score.lead, bar, beat)
        inner = _covering(score.support, bar, beat)
        bass = _covering(score.low, bar, beat)
        assert sung is not None and inner is not None and bass is not None
        assert sung.midi is not None and inner.midi is not None and bass.midi is not None
        assert bass.midi < inner.midi < sung.midi
    assert all(not note.tenuto and not note.accent for note in lead)


def _catedral_score(line: list[int], *, meter=METER_44, bpm: int = 96, bands: dict[int, str] | None = None):
    """Intro and outro around a calm Barrios body, so the body is framed Preludio."""
    epb = meter.eighths_per_bar
    frame = 2
    body_bars = 4
    phrases = (
        _held(0, frame * epb, 67),
        _from_notes(frame * epb, line * body_bars),
        _held((frame + body_bars) * epb, frame * epb, 67),
    )
    total = frame + body_bars + frame
    kinds = {
        bar: ("intro" if bar < frame else "outro" if bar >= frame + body_bars else "phrase")
        for bar in range(total)
    }
    sections = (
        FormSection(0, frame, "intro", 0),
        FormSection(frame, frame + body_bars, "phrase", 0),
        FormSection(frame + body_bars, total, "outro", 0),
    )
    return _guitar(
        phrases,
        ensemble="barrios",
        bpm=bpm,
        meter=meter,
        character="calm",
        kinds=kinds,
        sections=sections,
        bands=bands,
    )


def test_suite_movements_use_preludio_dances_tremolo_and_villa_chorale() -> None:
    opening = _suite(0, "barrios")
    assert opening.bpm == 96 and opening.divisions == 4
    ringing = [
        bar
        for bar in range(8, 40)
        if any(note.duration_beats >= 3.5 for note in _pitched(opening.low, bar))
        and len(_attack_onsets(opening.support, bar)) >= 8
    ]
    assert len(ringing) >= 10
    for bar in ringing:
        _assert_catedral_44(opening, bar)

    moderate = [Bar(close=100 + (index % 9) * 0.1, volume=1000 + index) for index in range(48)]
    day = render(moderate, title="Guitar", variant="guitar", ensemble="barrios", character="rally")
    assert day.bpm == 120 and day.bars == 34
    assert any(note.duration_beats >= 3.5 for note in _pitched(day.low, 4))
    assert len(_attack_onsets(day.support, 4)) >= 8

    choppy = [Bar(close=100.0 if index % 2 == 0 else 100.5, volume=1000 + index) for index in range(240)]
    dance = render(choppy, title="Guitar", variant="guitar", ensemble="barrios", character="volatile")
    assert _attack_onsets(dance.low, 4) == [0.0, 1.0, 2.0, 3.0]
    assert {0.75, 1.75} <= set(_attack_onsets(dance.support, 4))
    assert sum(1 for note in _pitched(dance.lead, 4) if abs(note.duration_beats - 0.25) < 1e-9) < 8

    wide = render(_bars(), title="Guitar", variant="guitar", ensemble="barrios", character="rally")
    assert sum(1 for note in _pitched(wide.lead, 4) if abs(note.duration_beats - 0.25) < 1e-9) >= 12

    scherzo = _suite(2, "barrios")
    assert scherzo.bpm == 120 and scherzo.beat_type == 8
    polca = next(note for note in _pitched(scherzo.low, 12) if abs(note.beat - 1.5) < 1e-9)
    assert polca.accent and 2.0 not in _attack_onsets(scherzo.low, 12)
    vals = next(note for note in _pitched(scherzo.low, 40) if abs(note.beat - 2.0) < 1e-9)
    assert vals.accent and abs(vals.duration_beats - 0.25) < 1e-9

    finale = _suite(3, "barrios")
    assert finale.bpm == 96
    tremolo_bars = sum(
        1
        for bar in range(10, 40)
        if sum(1 for note in _pitched(finale.lead, bar) if abs(note.duration_beats - 0.25) < 1e-9) >= 12
    )
    assert tremolo_bars >= 20

    slow = _suite(1, "villa")
    assert slow.bpm == 72 and slow.beats == 3 and slow.divisions == 2
    assert 0.0 in _attack_onsets(slow.lead, 12)
    assert 0.0 not in _attack_onsets(slow.lead, 48)
    assert _attack_onsets(slow.lead, 48) == _attack_onsets(slow.support, 48) == [1.0, 2.0]


def test_la_catedral_preludio_interlocks_two_high_melody_notes_with_sixteenth_arpeggio() -> None:
    # Strong beats stay chord tones so quantize leaves them. The other canto
    # notes are the 4th eighth of each 2-beat cell (index 3 and index 7).
    line = [72, 69, 67, 74, 76, 74, 72, 72]
    score = _catedral_score(line)
    assert score.divisions == 4
    for bar in (2, 3, 4, 5):
        _assert_catedral_44(score, bar, pitches=[72, 74, 76, 72])
        support = _attacks(score.support, bar)
        assert {note.midi % 12 for note in support if note.midi is not None} <= {0, 4, 7}
        canto = _covering(score.lead, bar, 0.25)
        inner = _covering(score.support, bar, 0.25)
        assert canto is not None and inner is not None
        assert canto.velocity is not None and inner.velocity is not None
        assert canto.velocity > inner.velocity
        _assert_catedral_shimmer(score, bar)
    # The pedal still rings for two bars. The last body bar keeps the wave
    # under the pickup bass.
    assert _onset_beats(score.low, 2) == [0.0]
    assert all(note.tie_stop for note in score.low if note.bar == 3 and note.midi is not None)
    assert 3.75 in _onsets(score.support, 5)
    assert_playable(score, C_KEY, "barrios_preludio")
    score_to_musicxml(score)

    # 3/4 keeps the 8-sixteenth cell, then one descending group on beat 3.
    three = _catedral_score([72, 69, 67, 74, 76, 74], meter=METER_34)
    for bar in (2, 3):
        lead = _attacks(three.lead, bar)
        assert [(round(note.beat, 2), round(note.duration_beats, 2)) for note in lead] == [
            (0.0, 1.5),
            (1.5, 0.5),
            (2.0, 1.0),
        ]
        assert [note.midi for note in lead] == [72, 74, 76]
        support = _attacks(three.support, bar)
        assert [round(note.beat, 2) for note in support] == [
            0.25,
            0.5,
            0.75,
            1.0,
            1.25,
            1.75,
            2.25,
            2.5,
            2.75,
        ]
        assert all(abs(note.duration_beats - 0.25) < 1e-9 for note in support)
        onsets = sorted({round(note.beat, 2) for note in (*lead, *support)})
        assert onsets == [index * 0.25 for index in range(12)]
        _assert_catedral_wave(support[:6])
        tail = [note.midi for note in support[6:] if note.midi is not None]
        assert tail[0] >= tail[1] >= tail[2]
        if len(set(tail)) >= 3:
            assert tail[0] > tail[1] > tail[2]
        _assert_catedral_shimmer(three, bar)
    assert_playable(three, C_KEY, "barrios_preludio")
    score_to_musicxml(three)

    # A low C4–E4 canto keeps its natural placed register while staying above the soft inner wave.
    hush_line = [60, 62, 64, 60, 64, 62, 60, 62]
    hush = _catedral_score(hush_line, bands={bar: "p" for bar in range(8)})
    for bar in (2, 3, 4, 5):
        _assert_catedral_44(hush, bar)
        _assert_catedral_shimmer(hush, bar)
        sung = [note.midi for note in _attacks(hush.lead, bar)]
        assert sung == [60, 60, 64, 62]
    assert_playable(hush, C_KEY, "barrios_preludio")
    score_to_musicxml(hush)

    opening = _suite(0, "barrios")
    assert opening.bpm == 96 and opening.divisions == 4
    pure = list(range(8, 40))
    for bar in pure:
        _assert_catedral_44(opening, bar)
        _assert_catedral_shimmer(opening, bar)
    waved = sum(
        1
        for bar in pure
        if len({note.midi for note in _attacks(opening.support, bar)[:5] if note.midi is not None}) >= 3
    )
    assert waved >= 1
    assert_playable(opening, C_KEY, "barrios_preludio")
    score_to_musicxml(opening)


def _brouwer_pattern(melody: list[int], **kwargs):
    bars = len(melody) // kwargs.get("meter", METER_44).eighths_per_bar
    chords = kwargs.pop("chords", None) or {bar: C for bar in range(bars)}
    return _pattern_score(
        melody,
        (_joined(0, melody),),
        ensemble="brouwer",
        bpm=kwargs.pop("bpm", 108),
        bands=kwargs.pop("bands", None) or {bar: "mf" for bar in range(bars)},
        chords=chords,
        character=kwargs.pop("character", "rally"),
        rel_span=0.0,
        **kwargs,
    )


def test_brouwer_renders_one_nylon_part_at_108() -> None:
    from app.sonify.guitar import GUITAR_BPM

    assert GUITAR_BPM["brouwer"] == 108
    score = render(_bars(), title="Guitar", variant="guitar", ensemble="brouwer")  # type: ignore[arg-type]
    assert score.bpm == 108
    assert score.ensemble == "brouwer"
    assert score.divisions == 2
    xml = score_to_musicxml(score)
    assert xml.count("<score-part ") == 1
    assert xml.count("<part ") == 1
    assert "<part-name>Acoustic Nylon</part-name>" in xml
    assert "<midi-program>25</midi-program>" in xml
    _assert_score_covers(score, 8)
    assert_playable(score, C_KEY, "brouwer")
    _assert_engraved(score, "brouwer")


def test_brouwer_dialect_planes_suspensions_and_the_minor_flat_seven() -> None:
    from app.sonify.chords import AF, AM7, BF, BF7, BM7B5, CM, CMAJ7, D7, DM7B5, E7, EF, EFMAJ7, F, FM, G7
    from app.sonify.harmony import BROUWER, COMMON, VILLA, color_pitch_classes, dialect_for

    assert dialect_for("brouwer") is BROUWER
    assert dialect_for("classic") is COMMON
    major = {chord.name for chord in BROUWER.extra("major")}
    minor = {chord.name for chord in BROUWER.extra("minor")}
    assert major == {"Csus2", "Dsus2", "Esus4", "Fsus2", "G7sus4", "Bbsus2", "Ebsus2"}
    assert minor == major - {"Dsus2", "Esus4", "Bbsus2"} | {"Dsus4", "Cmadd9", "Fmadd9", "Bb", "Bb7", "D7"}

    def named(mode: str, name: str):
        return next(chord for chord in BROUWER.extra(mode) if chord.name == name)

    csus2 = named("major", "Csus2")
    bbsus2 = named("major", "Bbsus2")
    fsus2 = named("major", "Fsus2")
    ebsus2 = named("major", "Ebsus2")
    for left, right in ((csus2, bbsus2), (bbsus2, fsus2), (fsus2, ebsus2)):
        assert BROUWER.transition(left, right, "major") == 0.32
        assert BROUWER.transition(right, left, "major") == 0.32
    fmadd9 = named("minor", "Fmadd9")
    g7sus4 = named("minor", "G7sus4")
    for left, right in (
        (FM, BF),
        (FM, BF7),
        (fmadd9, BF),
        (fmadd9, BF7),
        (BF, EF),
        (BF, EFMAJ7),
        (BF7, EF),
        (BF7, EFMAJ7),
        (EF, g7sus4),
        (EFMAJ7, g7sus4),
        (g7sus4, CM),
    ):
        assert BROUWER.transition(left, right, "minor") == 0.42
    assert BROUWER.transition(BF, CM, "minor") == 0.36
    assert BROUWER.transition(CM, BF, "minor") == 0.32
    assert BROUWER.transition(D7, G7, "minor") == 0.55
    assert BROUWER.transition(BF, AF, "minor") == 0.0
    g7sus4_major = named("major", "G7sus4")
    assert BROUWER.transition(g7sus4_major, C, "major") > 0
    assert BROUWER.transition(C, F, "major") is None
    assert BROUWER.transition(C, csus2, "major") == 0.30
    assert BROUWER.transition(csus2, C, "major") == 0.40
    assert BROUWER.transition(csus2, csus2, "major") == 0.0
    assert BROUWER.color_credit(csus2, frozenset({2}), C) == 0.65
    assert BROUWER.color_credit(csus2, frozenset({0, 7}), C) == 0.0
    assert BROUWER.color_credit(csus2, frozenset({2}), F) == 0.0
    assert BROUWER.is_parent(C, csus2, "major")
    assert BROUWER.shares_root(C, csus2)
    assert not BROUWER.shares_root(C, F)
    assert not BROUWER.allowed(csus2, pedal=True, phrase_downbeat=False, character="calm", mode="major")
    assert BROUWER.allowed(C, pedal=True, phrase_downbeat=False, character="calm", mode="major")
    assert not BROUWER.allowed(bbsus2, pedal=False, phrase_downbeat=True, character="rally", mode="major")
    cadd9 = next(chord for chord in VILLA.extra("major") if chord.name == "Cadd9")
    esus4 = named("major", "Esus4")

    def heard(chord):
        if chord.kind_text in {"maj7", "m7"} and len(chord.pitches) >= 4:
            return frozenset({chord.pitches[3] % 12})
        colors = color_pitch_classes(chord)
        if colors:
            return colors
        return chord.pitch_classes

    assert BROUWER.bias(CMAJ7, "calm", "major", heard(CMAJ7)) == -0.06
    assert BROUWER.bias(AM7, "rally", "major", heard(AM7)) == -0.06
    assert BROUWER.bias(csus2, "calm", "major", heard(csus2)) == -0.06
    assert BROUWER.bias(cadd9, "rally", "major", heard(cadd9)) == -0.06
    assert BROUWER.bias(g7sus4, "volatile", "minor", heard(g7sus4)) == -0.07
    assert BROUWER.bias(esus4, "selloff", "major", heard(esus4)) == -0.07
    for chord in (BF7, BM7B5, DM7B5, E7):
        assert BROUWER.bias(chord, "volatile", "minor", heard(chord)) == -0.07
    assert BROUWER.bias(CMAJ7, "calm", "major") == 0.0
    assert BROUWER.bias(CMAJ7, "calm", "major", frozenset({0, 4, 7})) == 0.0
    assert BROUWER.bias(csus2, "calm", "major", frozenset({0, 7})) == 0.0
    assert BROUWER.bias(BF7, "volatile", "minor") == 0.0
    assert BROUWER.bias(CMAJ7, "volatile", "major", heard(CMAJ7)) == 0.0
    assert BROUWER.bias(esus4, "calm", "major", heard(esus4)) == 0.0


def test_noviembre_sings_over_a_two_beat_pulse_and_a_walking_pickup() -> None:
    held = _brouwer_pattern([72] * 8, character="calm")
    assert _onset_beats(held.low, 0) == [0.0, 2.0]
    assert _onset_beats(held.support, 0) == [0.5, 1.0, 1.5, 2.5, 3.0]
    assert {note.velocity for note in _attacks(held.lead, 0)} == {64}
    _assert_engraved(held, "brouwer")

    walking = _pattern_score(
        [72] * 16,
        (_joined(0, [72] * 16),),
        ensemble="brouwer",
        bpm=108,
        chords={0: C, 1: F},
        character="calm",
        rel_span=0.0,
    )
    assert 3.5 in _onset_beats(walking.low, 0)
    pulse = next(note for note in _attacks(walking.low, 0) if abs(note.beat - 2.0) < 1e-6)
    pickup = next(note for note in _attacks(walking.low, 0) if abs(note.beat - 3.5) < 1e-6)
    assert pulse.velocity is not None and pickup.velocity is not None
    assert pickup.velocity < pulse.velocity
    _assert_engraved(walking, "brouwer")

    rising = [67, 69, 71, 72, 74, 72, 71, 69]
    sung = _brouwer_pattern(rising, character="calm")
    lead = _attacks(sung.lead, 0)
    assert lead[0].velocity == 60
    assert any(note.velocity == 72 for note in lead)
    assert lead[-1].velocity is not None and lead[-1].velocity < 72
    _assert_engraved(sung, "brouwer")


def test_brouwer_etude_plays_the_cuban_tumbao() -> None:
    score = _brouwer_pattern([72] * 8, character="rally")
    bass = _attacks(score.low, 0)
    assert [round(note.beat, 2) for note in bass] == [0.0, 1.5, 3.0]
    assert [round(note.duration_beats, 2) for note in bass] == [1.5, 1.5, 1.0]
    assert bass[0].accent
    for beat in (0.5, 1.0, 2.0, 2.5, 3.5):
        assert beat in _onset_beats(score.support, 0)
    assert any(note.duration_beats >= 1.0 for note in score.support if note.midi is not None)
    _assert_engraved(score, "brouwer")

    six = _brouwer_pattern([72] * 6, character="rally", meter=METER_68)
    six_bass = _attacks(six.low, 0)
    assert [round(note.beat, 2) for note in six_bass] == [0.0, 1.0, 2.5]
    assert [round(note.duration_beats, 2) for note in six_bass] == [1.0, 1.5, 0.5]
    _assert_engraved(six, "brouwer")
    opens = {note.midi for note in score.support if note.midi is not None} & {50, 55, 59}
    assert opens

    # Open strings are used only when the chord owns that pitch class.
    from app.sonify.chords import BF, EF
    from app.sonify.harmony import BROUWER

    bbsus2 = next(chord for chord in BROUWER.extra("major") if chord.name == "Bbsus2")
    for non_b_chord in (BF, EF, bbsus2):
        barred = _brouwer_pattern([72] * 8, character="rally", chords={0: non_b_chord})
        inner_pcs = {note.midi % 12 for note in _attacks(barred.support, 0) if note.midi is not None}
        allowed_pcs = set(non_b_chord.pitch_classes)
        assert inner_pcs <= allowed_pcs, (non_b_chord.name, inner_pcs, allowed_pcs)
        assert 11 not in inner_pcs

    three = _brouwer_pattern([72] * 6, character="rally", meter=METER_34)
    three_bass = _attacks(three.low, 0)
    assert [round(note.beat, 2) for note in three_bass] == [0.0, 1.5]
    assert [round(note.duration_beats, 2) for note in three_bass] == [1.5, 1.5]
    _assert_engraved(three, "brouwer")


def test_elogio_pizz_stabs_and_slaps_the_offbeat() -> None:
    score = _brouwer_pattern([72] * 8, character="volatile", bands={0: "mf"})
    bass = _attacks(score.low, 0)
    assert [round(note.beat, 2) for note in bass] == [0.0, 1.0, 1.5, 2.5, 3.0]
    assert all(note.staccato for note in bass)
    slap = next(note for note in bass if abs(note.beat - 1.5) < 1e-6)
    assert slap.accent and slap.staccato
    assert slap.velocity is not None and bass[0].velocity is not None
    assert slap.velocity > bass[0].velocity
    lead = _attacks(score.lead, 0)
    lead_slap = next(note for note in lead if abs(note.beat - 1.5) < 1e-6)
    assert lead_slap.accent and lead_slap.staccato
    assert lead_slap.velocity is not None and lead[0].velocity is not None
    assert lead_slap.velocity > lead[0].velocity
    _assert_engraved(score, "brouwer")


def test_sarabande_accents_beat_two_and_swarms_when_the_line_rises() -> None:
    flat = _brouwer_pattern([72] * 8, character="selloff")
    assert [round(note.beat, 2) for note in _attacks(flat.lead, 0)] == [0.0, 1.0]
    for voice in (flat.low, flat.support, flat.lead):
        accented = [note for note in _attacks(voice, 0) if abs(note.beat - 1.0) < 1e-6]
        assert len(accented) == 1
        assert accented[0].accent and not accented[0].staccato
    assert all(note.beat < 2 for note in _attacks(flat.lead, 0))
    _assert_engraved(flat, "brouwer")

    rising = [64, 65, 67, 69, 71, 72, 74, 76]
    swarm = _brouwer_pattern(rising, character="selloff")
    later = [note.midi for note in _attacks(swarm.lead, 0) if note.midi is not None and note.beat >= 2 - 1e-6]
    diffs = [abs(right - left) for left, right in zip(later, later[1:])]
    assert len(later) >= 4
    assert diffs and max(diffs) <= 2
    assert any(diff in {1, 2} for diff in diffs)
    assert abs(later[-1] - rising[-1]) <= 1
    early = [note.midi for note in _attacks(swarm.lead, 0) if note.midi is not None and note.beat < 2 - 1e-6]
    assert early and early[0] == rising[0]
    _assert_engraved(swarm, "brouwer")

    falling = [76, 74, 72, 71, 69, 67, 65, 64]
    selloff = _brouwer_pattern(falling, character="selloff")
    later = [note.midi for note in _attacks(selloff.lead, 0) if note.midi is not None and note.beat >= 2 - 1e-6]
    diffs = [abs(right - left) for left, right in zip(later, later[1:])]
    assert len(later) >= 4
    assert later[-1] < later[0]
    assert diffs and max(diffs) <= 2
    assert any(diff in {1, 2} for diff in diffs)
    assert later[-1] == falling[-1]
    opening = [note.midi for note in _attacks(selloff.lead, 0) if note.midi is not None and note.beat < 2 - 1e-6]
    assert opening and opening[0] == falling[0]
    _assert_engraved(selloff, "brouwer")

    # A flat bar inside a moving phrase stays flat instead of looping away from the price.
    mixed = falling + [64] * 8
    mixed_score = _pattern_score(
        mixed,
        (_joined(0, mixed),),
        ensemble="brouwer",
        bpm=108,
        character="selloff",
        rel_span=0.0,
    )
    assert len([note for note in _attacks(mixed_score.lead, 0) if note.beat >= 2 - 1e-6]) >= 4
    assert all(note.beat < 2 for note in _attacks(mixed_score.lead, 1))
    assert {note.midi for note in _attacks(mixed_score.lead, 1)} == {64}
    _assert_engraved(mixed_score, "brouwer")

    # A steep drop (> 6 semitones across the second half) subdivides into sixteenths and lands on the close.
    steep = [79, 77, 76, 74, 72, 69, 65, 62]
    steep_score = _brouwer_pattern(steep, character="selloff")
    steep_later = [note.midi for note in _attacks(steep_score.lead, 0) if note.midi is not None and note.beat >= 2 - 1e-6]
    steep_diffs = [abs(right - left) for left, right in zip(steep_later, steep_later[1:])]
    assert len(steep_later) == 8
    assert steep_later[0] == 72 and steep_later[-1] == 62
    assert max(steep_diffs) <= 2 and all(diff >= 1 for diff in steep_diffs)
    _assert_engraved(steep_score, "brouwer")

    # Even a full-window drop in 6/8, 3/4, or 4/4 keeps every step across the ENTIRE bar <= 2 semitones,
    # accents beat 2 (1.5 in 6/8, 1.0 in 3/4 and 4/4), and lands on the closing pitch.
    for meter, accent_beat, line_notes in (
        (METER_68, 1.5, [79, 76, 74, 79, 69, 60]),
        (METER_34, 1.0, [76, 76, 76, 76, 68, 60]),
        (METER_44, 1.0, [81, 80, 79, 79, 81, 74, 67, 59]),
    ):
        cliff_score = _brouwer_pattern(line_notes, character="selloff", meter=meter)
        all_lead = [note.midi for note in _attacks(cliff_score.lead, 0) if note.midi is not None]
        all_diffs = [abs(right - left) for left, right in zip(all_lead, all_lead[1:])]
        assert all_lead[-1] == line_notes[-1]
        assert max(all_diffs) <= 2 and all(diff >= 1 for diff in all_diffs)
        for voice in (cliff_score.low, cliff_score.support, cliff_score.lead):
            assert any(note.accent and abs(note.beat - accent_beat) < 1e-6 for note in _attacks(voice, 0))
        _assert_engraved(cliff_score, "brouwer")

    slow = _brouwer_pattern([72] * 8, character="rally", bpm=72)
    assert any(note.accent and abs(note.beat - 1.0) < 1e-6 for note in _attacks(slow.low, 0))
    assert [round(note.beat, 2) for note in _attacks(slow.low, 0)] == [0.0, 1.0]
    quiet = _brouwer_pattern([72] * 8, character="calm", bpm=60)
    assert _onset_beats(quiet.low, 0) == [0.0, 2.0]
    _assert_engraved(slow, "brouwer")
    _assert_engraved(quiet, "brouwer")


def test_brouwer_trio_answers_the_tumbao_with_noviembre() -> None:
    epb = 8
    regions = (
        (0, 2, "intro", False),
        (2, 6, "phrase", False),
        (6, 10, "phrase", True),
        (10, 14, "phrase", False),
        (14, 16, "outro", False),
    )
    phrases = tuple(_held(start * epb, (end - start) * epb, 67) for start, end, _kind, _trio in regions)
    sections = tuple(FormSection(start, end, kind, 0, trio=trio) for start, end, kind, trio in regions)
    kinds = {bar: ("intro" if bar < 2 else "outro" if bar >= 14 else "phrase") for bar in range(16)}
    score = _guitar(
        phrases,
        ensemble="brouwer",
        bpm=108,
        character="rally",
        kinds=kinds,
        sections=sections,
    )
    assert [round(note.beat, 2) for note in _attacks(score.low, 3)] == [0.0, 1.5, 3.0]
    assert _onset_beats(score.low, 7) == [0.0, 2.0]
    assert_playable(score, C_KEY, "brouwer")
    _assert_engraved(score, "brouwer")


def test_brouwer_frames_for_lyric_and_edge_modes() -> None:
    lyric = _frame_score("brouwer", 2, character="rally")
    assert _onset_beats(lyric.low, 0) == [0.0]
    assert _pitched(lyric.lead, 0) == []
    assert all(note.velocity is not None and note.velocity <= 50 for note in _pitched(lyric.low, 0))
    assert all(note.duration_beats >= 3 for note in _pitched(lyric.low, 0))
    assert len(_attacks(lyric.lead, 1)) >= 4
    final = _pitched(lyric.lead, lyric.bars - 1)
    assert final and all(note.midi >= 76 and note.velocity is not None and note.velocity <= 48 for note in final)
    assert _pitched(lyric.low, lyric.bars - 1)
    assert any(note.duration_beats >= 3 for note in _pitched(lyric.low, lyric.bars - 1))
    _assert_under_apex(lyric, (0, 1, lyric.bars - 2, lyric.bars - 1))
    _assert_engraved(lyric, "brouwer")

    lyric_long = _frame_score("brouwer", 4, character="calm")
    opening = _attacks(lyric_long.lead, 0)
    assert len(opening) == 1 and opening[0].midi >= 76 and opening[0].velocity is not None
    assert opening[0].velocity <= 48
    assert _pitched(lyric_long.low, 0) == []
    assert 0.0 in _onset_beats(lyric_long.low, 1)
    assert len(_attacks(lyric_long.support, 1)) >= 2
    assert len([note for note in _attacks(lyric_long.lead, 3) if note.beat >= 2]) >= 3
    assert len(_attacks(lyric_long.low, lyric_long.bars - 3)) >= 2
    farewell = _pitched(lyric_long.lead, lyric_long.bars - 1)
    assert farewell and any(note.midi >= 76 and note.velocity is not None and note.velocity <= 48 for note in farewell)
    assert _pitched(lyric_long.low, lyric_long.bars - 1)
    _assert_under_apex(lyric_long, (0, 1, 2, 3, lyric_long.bars - 4, lyric_long.bars - 1))
    _assert_engraved(lyric_long, "brouwer")

    edge = _frame_score("brouwer", 2, character="volatile")
    assert any(note.staccato and note.accent for note in (*edge.lead, *edge.support, *edge.low) if note.bar == 0)
    assert _pitched(edge.low, 0)
    assert len([note for note in _attacks(edge.lead, 1) if note.staccato]) >= 4
    penultimate = edge.bars - 2
    offbeat = [note for note in _attacks(edge.lead, penultimate) if note.staccato and note.beat > 0]
    assert len(offbeat) >= 2
    last = edge.bars - 1
    stab = [note for note in (*_attacks(edge.lead, last), *_attacks(edge.low, last)) if abs(note.beat) < 1e-6]
    assert stab and all(note.staccato and note.accent for note in stab)
    final = [note for note in (*_attacks(edge.lead, last), *_attacks(edge.low, last)) if abs(note.beat - 1.0) < 1e-6]
    assert final and all(note.staccato and note.accent for note in final)
    assert not any(note.beat >= 1.5 for note in _pitched(edge.lead, last))
    assert not any(note.beat >= 1.5 for note in _pitched(edge.low, last))
    _assert_under_apex(edge, (0, 1, penultimate, last))
    _assert_engraved(edge, "brouwer")

    edge_long = _frame_score("brouwer", 4, character="selloff")
    pluck = _attacks(edge_long.low, 0)
    assert len(pluck) == 1 and pluck[0].staccato and pluck[0].accent
    assert pluck[0].duration_beats <= 0.5
    assert len(_attacks(edge_long.low, 1)) >= 2
    assert all(note.duration_beats >= 1 for note in _attacks(edge_long.low, 1))
    assert any(note.staccato and abs(note.beat - 0.5) < 1e-6 for note in _attacks(edge_long.lead, 2))
    second_half = [note for note in _attacks(edge_long.lead, 3) if note.beat >= 2]
    first_half = [note for note in _attacks(edge_long.lead, 3) if note.beat < 2]
    assert len(second_half) >= 4 and len(second_half) > len(first_half)
    outro = edge_long.bars - 4
    sparse = _attacks(edge_long.lead, outro)
    assert 1 <= len(sparse) <= 3
    assert sparse[-1].velocity is not None and sparse[0].velocity is not None
    assert sparse[-1].velocity < sparse[0].velocity
    assert len(_attacks(edge_long.lead, outro + 1)) >= 4
    assert any(note.duration_beats >= 2 for note in _pitched(edge_long.low, outro + 2))
    ending = _attacks(edge_long.low, outro + 3)
    assert ending and ending[0].staccato and ending[0].accent and ending[0].midi <= 48
    _assert_under_apex(edge_long, (0, 1, 2, 3, outro, outro + 3))
    _assert_engraved(edge_long, "brouwer")

    for character in ("rally", "volatile"):
        compressed = _frame_score("brouwer", 1, character=character)
        assert_playable(compressed, C_KEY, "brouwer")
        _assert_engraved(compressed, "brouwer")


_SOR_JAZZ = frozenset({
    "Cmaj7", "Fmaj7", "Am7", "Em7",
    "Cm7", "Fm7", "Ebmaj7", "Abmaj7",
})
_SOR_MAJOR = frozenset({
    "C", "F", "G", "Am", "Dm", "Em", "G7", "Dm7",
    "D7", "E7", "A7", "C7", "F#dim7",
})
_SOR_MINOR = frozenset({
    "Cm", "Fm", "Dm7b5", "G", "G7", "Eb", "Ab", "D7", "F#dim7",
})
_PEDAL_SECTIONS = frozenset({"intro", "outro", "warmup", "cooldown"})


def _sor_bar(downbeat: int, middle: int, other: int) -> list[int]:
    row = [other] * 8
    row[0] = downbeat
    row[4] = middle
    return row


def _sor_plan(
    bars: list[list[int]],
    *,
    mode: str = "major",
    character: str = "rally",
    regime: str = "uptrend",
    kinds: tuple[str, ...] | None = None,
):
    from app.sonify.form import FormSection, FormSpec, plan_markov_chords
    from app.sonify.harmony import SOR
    from app.sonify.quantize import c_major_scale, c_natural_minor_scale

    if kinds is None:
        sections = (FormSection(0, len(bars), "phrase", 0),)
    else:
        sections = tuple(
            FormSection(index, index + 1, kind, 0)  # type: ignore[arg-type]
            for index, kind in enumerate(kinds)
        )
    spec = FormSpec(bars=len(bars), bpm=88, sections=sections, borrowed=True)
    scale = c_natural_minor_scale() if mode == "minor" else c_major_scale()
    return plan_markov_chords(
        (regime,) * spec.regime_slots,  # type: ignore[arg-type]
        [note for bar in bars for note in bar],
        scale,
        spec,
        character=character,  # type: ignore[arg-type]
        mode=mode,  # type: ignore[arg-type]
        dialect=SOR,
    )


def _sor_names(score) -> list[str]:
    return [slot.chord.name for slot in score.slots]


def test_guitar_classic_uses_sor_and_symphony_classic_stays_common() -> None:
    from app.sonify.chords import D7
    from app.sonify.harmony import COMMON, SOR, VILLA, SorDialect, dialect_for

    assert isinstance(dialect_for("classic", "guitar"), SorDialect)
    assert dialect_for("classic", "guitar") is SOR
    assert dialect_for("sor") is SOR
    assert dialect_for("sor", "guitar") is SOR
    assert dialect_for("classic") is COMMON
    assert dialect_for("classic", "symphony") is COMMON
    assert dialect_for("classic", "jazz") is COMMON
    assert dialect_for("villa", "guitar") is VILLA
    assert dialect_for("brass", "guitar") is COMMON
    assert SOR.extra("major") == ()
    assert SOR.extra("minor") == (D7,)
    assert SOR.name == "sor"


def test_sor_allows_triads_and_refuses_jazz_sevenths() -> None:
    from app.sonify.chords import (
        A7, AF, AFMAJ7, AM, AM7, BF, BM7B5, C, C7, CM, CM7, CMAJ7, D7, DM, DM7,
        DM7B5, E7, EF, EFMAJ7, EM, EM7, F, FDIM7, FM, FM7, FMAJ7, G, G7, GM,
    )
    from app.sonify.harmony import SOR

    def allowed(chord, *, pedal=False, downbeat=False, mode="major") -> bool:
        return SOR.allowed(
            chord, pedal=pedal, phrase_downbeat=downbeat, character=None, mode=mode
        )

    assert allowed(C, pedal=True) is True
    assert allowed(CM, pedal=True, mode="minor") is True
    for chord in (CMAJ7, AM7, F, G, G7, AM, DM):
        assert allowed(chord, pedal=True) is False
    assert allowed(CM7, pedal=True, mode="minor") is False
    assert allowed(FM, pedal=True, mode="minor") is False

    for chord in (CMAJ7, FMAJ7, AM7, EM7, AF, EF, BF, GM, FM, BM7B5):
        assert allowed(chord) is False
    for chord in (C, F, G, G7, DM, DM7, AM, EM):
        assert allowed(chord) is True
    for chord in (D7, E7, A7, C7, FDIM7):
        assert allowed(chord, downbeat=True) is False
        assert allowed(chord, downbeat=False) is True

    for chord in (CM7, FM7, EFMAJ7, AFMAJ7):
        assert allowed(chord, mode="minor") is False
    for chord in (CM, FM, DM7B5, G, G7, EF, AF):
        assert allowed(chord, mode="minor") is True
    for chord in (D7, FDIM7):
        assert allowed(chord, downbeat=True, mode="minor") is False
        assert allowed(chord, pedal=True, mode="minor") is False
        assert allowed(chord, downbeat=False, mode="minor") is True


def test_sor_weights_classical_cadences_and_blocks_retrogression() -> None:
    from app.sonify.chords import (
        A7, AF, AM, C, C7, CM, D7, DM, DM7, DM7B5, E7, EF, EM, F, FDIM7, FM, G, G7,
    )
    from app.sonify.harmony import SOR

    major = {
        (C, G): 0.28, (C, G7): 0.26, (C, F): 0.28, (C, DM): 0.18, (C, AM): 0.18,
        (F, G): 0.36, (F, G7): 0.40, (F, C): 0.24, (F, DM): 0.22, (F, DM7): 0.18,
        (F, D7): 0.18,
        (DM, G): 0.40, (DM, G7): 0.44, (DM7, G): 0.40, (DM7, G7): 0.46,
        (G, C): 0.62, (G7, C): 0.68, (G, AM): 0.20, (G7, AM): 0.18,
        (C, D7): 0.14, (AM, D7): 0.20, (D7, G): 0.52, (D7, G7): 0.48,
        (C, E7): 0.10, (AM, E7): 0.18, (E7, AM): 0.58,
        (DM, A7): 0.16, (A7, DM): 0.55,
        (C, C7): 0.12, (C7, F): 0.58,
        (F, FDIM7): 0.12, (FDIM7, G): 0.60, (FDIM7, G7): 0.40,
        (G, F): 0.0, (G7, F): 0.0, (G, DM): 0.0, (G7, DM): 0.0, (G, DM7): 0.0, (G7, DM7): 0.0,
    }
    minor = {
        (CM, FM): 0.34, (CM, G): 0.26, (CM, G7): 0.28, (CM, DM7B5): 0.22,
        (CM, EF): 0.18, (CM, AF): 0.14,
        (FM, G): 0.40, (FM, G7): 0.44, (FM, DM7B5): 0.24, (FM, D7): 0.20, (FM, CM): 0.22,
        (DM7B5, G): 0.44, (DM7B5, G7): 0.48, (DM7B5, D7): 0.24,
        (EF, AF): 0.38, (EF, FM): 0.26, (EF, G): 0.22, (EF, G7): 0.24,
        (AF, DM7B5): 0.36, (AF, FM): 0.28, (AF, G): 0.32, (AF, G7): 0.34, (AF, D7): 0.26,
        (D7, G): 0.52, (D7, G7): 0.56, (D7, D7): 0.12,
        (G, CM): 0.60, (G7, CM): 0.66, (G, AF): 0.20, (G7, AF): 0.18,
    }
    for (prev, curr), weight in major.items():
        assert SOR.transition(prev, curr, "major") == weight
    for (prev, curr), weight in minor.items():
        assert SOR.transition(prev, curr, "minor") == weight
    # Unlisted diatonic motion keeps the shared catalog. Unlisted D7 does not.
    assert SOR.transition(C, EM, "major") is None
    assert SOR.transition(D7, CM, "minor") == 0.0
    assert SOR.transition(G, D7, "minor") == 0.0


def test_sor_bias_prefers_the_primary_triads_and_the_character() -> None:
    from app.sonify.chords import AF, C, CM, D7, DM7B5, F, FDIM7, FM, G, G7
    from app.sonify.harmony import SOR

    assert SOR.bias(C, "calm", "major") == -0.06
    assert SOR.bias(F, "calm", "major") == -0.06
    assert SOR.bias(G, "rally", "major") == -0.06
    assert SOR.bias(CM, "calm", "minor") == -0.06
    assert SOR.bias(FM, "selloff", "minor") == -0.06
    assert SOR.bias(G, "calm", "minor") == -0.06
    assert SOR.bias(G7, None, "major", frozenset()) == 0.0
    assert SOR.bias(G7, "calm", "major", frozenset({5})) == -0.06
    assert SOR.bias(G7, "calm", "minor", frozenset({2})) == -0.06
    assert SOR.bias(G7, "rally", "major") == -0.06
    assert SOR.bias(D7, "rally", "major") == -0.06
    assert SOR.bias(D7, "calm", "major") == 0.0
    for chord in (CM, FM, DM7B5, G, G7, AF, FDIM7):
        assert SOR.bias(chord, "selloff", "minor") == -0.06
    assert SOR.bias(DM7B5, "calm", "minor") == 0.0
    assert SOR.bias(AF, "calm", "minor") == 0.0


def test_sor_cadences_resolve_and_the_secondary_dominant_reaches_the_dominant() -> None:
    tonic = _sor_plan([
        _sor_bar(60, 64, 67),  # C E G
        _sor_bar(65, 60, 69),  # F C A
        _sor_bar(65, 71, 67),  # F B G
        _sor_bar(60, 64, 67),
    ])
    assert [chord.name for chord in tonic] == ["C", "F", "G7", "C"]

    predominant = _sor_plan([
        _sor_bar(60, 64, 67),
        _sor_bar(62, 69, 65),  # D A, with F off the beat
        _sor_bar(65, 71, 67),
        _sor_bar(60, 64, 67),
    ], character="calm")
    names = [chord.name for chord in predominant]
    assert names[0] == "C", names
    assert names[1] in {"Dm", "Dm7"}, names
    assert names[2] == "G7", names
    assert names[3] == "C", names

    secondary = _sor_plan([
        _sor_bar(60, 64, 67),
        _sor_bar(60, 62, 69),  # C D A
        _sor_bar(67, 71, 62),  # G B D
        _sor_bar(60, 64, 67),
    ])
    heard = [chord.name for chord in secondary]
    assert heard[1] == "D7", heard
    assert heard[2] in {"G", "G7"}, heard

    minor = _sor_plan([
        _sor_bar(60, 63, 67),  # C Eb G
        _sor_bar(65, 68, 60),  # F Ab C
        _sor_bar(65, 70, 67),  # F Bb G
        _sor_bar(60, 63, 67),
    ], mode="minor", character="selloff", regime="downtrend")
    assert [chord.name for chord in minor] == ["Cm", "Fm", "G7", "Cm"]


def test_sor_downtrend_pedal_holds_the_major_triad() -> None:
    """Am/Am7 are the downtrend tonics. Sor still pedals C, never Am7."""
    kinds = ("intro", "intro", "phrase", "phrase", "outro", "outro")
    chords = _sor_plan(
        [_sor_bar(69, 64, 60)] * 6,
        mode="major",
        character="calm",
        regime="downtrend",
        kinds=kinds,
    )
    names = [chord.name for chord in chords]
    assert names[:2] == ["C", "C"], names
    assert names[4:] == ["C", "C"], names
    assert "Am7" not in names
    assert "Cmaj7" not in names


def test_rendered_sor_scores_never_use_jazz_sevenths() -> None:
    """1D and every 1M movement, in major and minor, stay inside the Classical vocabulary."""
    from app.sonify.span import plan_month

    def check(score, mode: str) -> None:
        found = set(_sor_names(score))
        legal = _SOR_MAJOR if mode == "major" else _SOR_MINOR
        assert not found & _SOR_JAZZ, sorted(found & _SOR_JAZZ)
        assert found <= legal, sorted(found - legal)
        if mode == "major":
            assert {"C", "F"} <= found
            assert found & {"G", "G7"}
        else:
            assert "Cm" in found
            assert found & {"Fm", "G", "G7", "Dm7b5"}
        pedal = {
            slot.chord.name
            for slot in score.slots
            if slot.section in _PEDAL_SECTIONS
        }
        assert pedal == {"C" if mode == "major" else "Cm"}, pedal

    forms = (None, *(movement.spec for movement in plan_month([8, 8, 8, 8], "guitar")))
    for form in forms:
        for mode, character in (("major", "rally"), ("minor", "selloff")):
            score = render(
                _bars(),
                title="Sor",
                variant="guitar",
                ensemble="classic",
                form=form,
                mode=mode,
                character=character,  # type: ignore[arg-type]
            )
            check(score, mode)


def _bach(melody: list[int], **kwargs):
    meter = kwargs.get("meter", METER_44)
    bars = len(melody) // meter.eighths_per_bar
    chords = kwargs.pop("chords", None) or {bar: C for bar in range(bars)}
    return _pattern_score(
        melody,
        kwargs.pop("phrases", None) or (_joined(0, melody),),
        ensemble="bach",
        bpm=kwargs.pop("bpm", 96),
        bands=kwargs.pop("bands", None) or {bar: "mf" for bar in range(bars)},
        chords=chords,
        character=kwargs.pop("character", "rally"),
        rel_span=kwargs.pop("rel_span", 0.02),
        **kwargs,
    )


def _signs(midis: list[int]) -> list[int]:
    signs = [0]
    for previous, current in zip(midis, midis[1:]):
        if current > previous:
            signs.append(1)
        elif current < previous:
            signs.append(-1)
        else:
            signs.append(0)
    return signs


def _chord_pcs(chord: Chord) -> set[int]:
    return {pitch % 12 for pitch in chord.pitches[:3]}


def test_bach_fuga_answers_two_bars_later_in_the_same_contour() -> None:
    """Lag 2 keeps the subject's rhythm and direction, and strong beats sit on this chord."""
    melody = [67, 69, 71, 72, 76, 74, 72, 71, 72, 71, 69, 67, 65, 67, 69, 71, 67, 69, 71, 72, 74, 72, 71, 69]
    chords = {0: C, 1: F, 2: G}
    score = _bach(melody, character="volatile", chords=chords)
    assert score.bpm == 96
    lead = [note.midi for note in _attacks(score.lead, 0)]
    bass = [note.midi for note in _attacks(score.low, 2)]
    assert [round(note.beat, 2) for note in _attacks(score.lead, 0)] == [
        round(note.beat, 2) for note in _attacks(score.low, 2)
    ]
    assert [round(note.duration_beats, 2) for note in _attacks(score.lead, 0)] == [
        round(note.duration_beats, 2) for note in _attacks(score.low, 2)
    ]
    assert _signs(bass) == _signs(lead)
    for note in _attacks(score.low, 2):
        if note.beat in {0.0, 2.0}:
            assert note.midi is not None and note.midi % 12 in _chord_pcs(G)
        else:
            previous = _covering(score.low, 2, note.beat - 0.5)
            assert previous is not None and note.midi is not None and previous.midi is not None
            assert abs(note.midi - previous.midi) <= 2
            assert note.midi % 12 in {0, 2, 4, 5, 7, 9, 11}
    # The answer has not entered yet: beat 1 holds the root, then the subject walks.
    opening = _attacks(score.low, 0)
    assert opening[0].duration_beats >= 1.5
    assert opening[0].midi is not None and opening[0].midi % 12 in _chord_pcs(C)
    _assert_engraved(score, "bach")


def test_bach_fuga_holds_a_flat_subject_and_the_bass_repeats_it() -> None:
    """A flat soprano stays flat. Two bars later the bass holds that rhythm, retargeted to G."""
    score = _bach([72] * 24, character="volatile", chords={0: C, 1: F, 2: G})
    subject = _attacks(score.lead, 0)
    subject_midis = [note.midi for note in subject]
    assert subject_midis and all(midi == subject_midis[0] for midi in subject_midis)
    assert all(right - left == 0 for left, right in zip(subject_midis, subject_midis[1:]) if left and right)
    answer = _attacks(score.low, 2)
    assert answer
    assert [round(note.beat, 2) for note in answer] == [round(note.beat, 2) for note in subject]
    assert [round(note.duration_beats, 2) for note in answer] == [
        round(note.duration_beats, 2) for note in subject
    ]
    answer_midis = [note.midi for note in answer]
    assert all(midi is not None and midi % 12 in _chord_pcs(G) for midi in answer_midis)
    assert all(right - left == 0 for left, right in zip(answer_midis, answer_midis[1:]) if left and right)
    _assert_engraved(score, "bach")


def test_bach_bourree_walks_under_a_hold_and_sits_under_a_running_treble() -> None:
    held = [72] * 8
    running = [67, 69, 71, 72, 74, 72, 71, 69]
    score = _bach(held + running, character="rally", chords={0: C, 1: G})
    assert [note.midi for note in _attacks(score.lead, 0)] == [72]
    bass = _attacks(score.low, 0)
    assert [(round(note.beat, 2), round(note.duration_beats, 2)) for note in bass] == [
        (0.0, 1.0),
        (1.0, 0.5),
        (1.5, 0.5),
        (2.0, 1.0),
        (3.0, 0.5),
        (3.5, 0.5),
    ]
    assert bass[1].staccato and bass[4].staccato
    moving = _attacks(score.low, 1)
    assert [(round(note.beat, 2), round(note.duration_beats, 2)) for note in moving] == [
        (0.0, 1.0),
        (1.0, 1.0),
        (2.0, 1.0),
        (3.0, 1.0),
    ]
    assert moving[1].staccato and moving[3].staccato
    assert moving[0].midi is not None and moving[0].midi % 12 in _chord_pcs(G)
    assert _onset_beats(score.support, 1) == [0.0, 2.0]
    _assert_engraved(score, "bach")


def test_bach_gavotte_phrases_quarters_then_parallel_eighths() -> None:
    score = _bach([72] * 16, character="calm", chords={0: C, 1: F}, rel_span=0.0)
    lead = _attacks(score.lead, 0)
    assert [(round(note.beat, 2), round(note.duration_beats, 2)) for note in lead] == [
        (0.0, 1.0),
        (1.0, 1.0),
        (2.0, 0.5),
        (2.5, 0.5),
        (3.0, 0.5),
        (3.5, 0.5),
    ]
    assert lead[1].staccato
    bass = _attacks(score.low, 0)
    assert [(round(note.beat, 2), round(note.duration_beats, 2)) for note in bass] == [
        (0.0, 1.0),
        (1.0, 1.0),
        (2.0, 2.0),
    ]
    assert bass[1].staccato
    assert bass[0].midi is not None and bass[0].midi % 12 == 0
    pairs = []
    for note in lead:
        if note.beat < 2:
            continue
        inner = next(item for item in _attacks(score.support, 0) if abs(item.beat - note.beat) < 1e-6)
        assert note.midi is not None and inner.midi is not None
        pairs.append((note.midi - inner.midi) % 12)
    assert pairs and set(pairs) <= {3, 4, 8, 9}
    _assert_engraved(score, "bach")


def test_bach_sarabande_weights_beat_two_and_passes_into_the_next_bar() -> None:
    score = _bach([72] * 12, character="calm", meter=METER_34, rel_span=0.005, chords={0: C, 1: G})
    assert score.divisions == 4
    for voice in (score.lead, score.low):
        accented = [note for note in _attacks(voice, 0) if abs(note.beat - 1.0) < 1e-6]
        assert len(accented) == 1 and accented[0].accent
    rolled = [note for note in _attacks(score.support, 0) if abs(note.beat - 1.25) < 1e-6]
    assert len(rolled) == 1 and rolled[0].accent
    ornament = [note for note in _attacks(score.lead, 0) if 1.0 <= note.beat < 2.0]
    assert [round(note.duration_beats, 2) for note in ornament] == [0.25, 0.25, 0.5]
    assert ornament[0].midi == ornament[2].midi
    assert ornament[1].midi != ornament[0].midi
    passing = [note.midi for note in _attacks(score.lead, 0) if note.beat >= 2.0]
    assert 2 <= len(passing) <= 4
    assert passing[-1] == _attacks(score.lead, 1)[0].midi
    assert all(abs(right - left) <= 2 for left, right in zip(passing, passing[1:]) if left and right)
    _assert_engraved(score, "bach")


def test_bach_gigue_breaks_the_chord_and_runs_when_the_line_rises() -> None:
    still = _bach([72] * 12, character="rally", meter=METER_68, chords={0: C, 1: G})
    assert [round(note.beat, 2) for note in _attacks(still.lead, 0)] == [0.0, 1.0, 1.5, 2.5]
    assert all(note.accent for note in _attacks(still.lead, 0) if note.beat in {0.0, 1.5})
    assert _onset_beats(still.support, 0) == [0.5, 1.0, 2.0, 2.5]
    assert len({note.midi for note in _attacks(still.support, 0)}) >= 2
    bass = _attacks(still.low, 0)
    assert [(round(note.beat, 2), round(note.duration_beats, 2)) for note in bass] == [
        (0.0, 1.5),
        (1.5, 1.0),
        (2.5, 0.5),
    ]
    assert bass[0].accent and bass[1].accent
    _assert_engraved(still, "bach")

    rising = [64, 65, 67, 69, 71, 72] * 2
    driving = _bach(rising, character="rally", meter=METER_68, chords={0: C, 1: G})
    assert driving.divisions == 4
    scale = [note for note in _attacks(driving.lead, 0) if note.beat >= 1.5 - 1e-6]
    assert len(scale) == 6
    assert all(note.duration_beats == 0.25 for note in scale)
    assert scale[-1].midi == _attacks(driving.lead, 1)[0].midi
    assert any(abs(right.midi - left.midi) in {1, 2} for left, right in zip(scale, scale[1:]) if left.midi and right.midi)
    _assert_engraved(driving, "bach")


def test_bach_chaconne_waves_in_sixteenths_and_breaks_into_a_scale() -> None:
    ground = _bach([72] * 16, character="selloff", chords={0: C, 1: C})
    assert ground.divisions == 4
    bass = _attacks(ground.low, 0)
    assert [(round(note.beat, 2), round(note.duration_beats, 2)) for note in bass] == [(0.0, 2.0), (2.0, 2.0)]
    assert bass[1].midi is not None and bass[0].midi is not None and bass[1].midi <= bass[0].midi
    onsets = set(_onset_beats(ground.lead, 0)) | set(_onset_beats(ground.support, 0))
    assert onsets == {index * 0.25 for index in range(16)}
    assert {50, 55, 59} & {note.midi for note in _attacks(ground.support, 0)}
    _assert_engraved(ground, "bach")

    rising = [67, 69, 71, 72, 74, 76, 77, 79] * 2
    breakout = _bach(rising, character="selloff", chords={0: C, 1: G}, bands={0: "f", 1: "f"})
    assert breakout.divisions == 4
    scale = [note for note in _attacks(breakout.lead, 0) if note.beat >= 2.0 - 1e-6]
    assert len(scale) == 8
    assert all(note.duration_beats == 0.25 for note in scale)
    assert scale[-1].midi == _attacks(breakout.lead, 1)[0].midi
    assert all(
        left.midi is not None and right.midi is not None and abs(right.midi - left.midi) <= 2
        for left, right in zip(scale, scale[1:])
    )
    _assert_engraved(breakout, "bach")


def test_bach_trio_answers_the_bourree_with_the_fugue() -> None:
    phrases = (_joined(0, [72] * 16), _joined(16, [72] * 16))
    sections = (
        FormSection(0, 2, "phrase", 0),
        FormSection(2, 4, "phrase", 0, trio=True),
    )
    score = _bach(
        [72] * 32,
        character="rally",
        phrases=phrases,
        sections=sections,
        chords={0: C, 1: F, 2: G, 3: C},
    )
    assert [(round(note.beat, 2), round(note.duration_beats, 2)) for note in _attacks(score.low, 0)] == [
        (0.0, 1.0),
        (1.0, 0.5),
        (1.5, 0.5),
        (2.0, 1.0),
        (3.0, 0.5),
        (3.5, 0.5),
    ]
    answer = _attacks(score.low, 2)
    assert [round(note.duration_beats, 2) for note in answer] == [4.0]
    assert answer[0].midi is not None and answer[0].midi % 12 in _chord_pcs(G)
    _assert_engraved(score, "bach")

    # A rally finale with a long coda still dances the bourrée, not the chaconne.
    finale = _suite(3, "bach", character="rally")
    assert finale.divisions == 2
    assert _sixteenths(finale.lead, 12) == []
    assert _sixteenths(finale.support, 12) == []


def test_bach_voices_stay_playable_across_meters_and_keys() -> None:
    from app.sonify.chords import DM7, G7

    melodies = (
        [67, 69, 71, 72, 74, 72, 71, 69],
        [60, 62, 64, 65, 67, 65, 64, 62],
        [76, 77, 79, 81, 79, 77, 76, 74],
        [72] * 8,
    )
    plans = (
        (METER_44, "volatile", 96, 0.02),
        (METER_44, "rally", 96, 0.02),
        (METER_44, "calm", 96, 0.0),
        (METER_44, "selloff", 96, 0.02),
        (METER_34, "calm", 90, 0.005),
        (METER_34, "selloff", 80, 0.02),
        (METER_68, "rally", 96, 0.02),
        (METER_44, "calm", 66, 0.0),
    )
    for melody in melodies:
        for meter, character, bpm, span in plans:
            epb = meter.eighths_per_bar
            pitches = (melody * 8)[: epb * 4]
            chords = {bar: (C, G7, DM7, F)[bar % 4] for bar in range(4)}
            score = _bach(
                pitches,
                meter=meter,
                character=character,
                bpm=bpm,
                rel_span=span,
                chords=chords,
            )
            _assert_engraved(score, "bach")
            if meter is METER_68:
                assert _onset_beats(score.low, 0)[0] == 0.0
    with compose_register(D_KEY):
        transposed = _bach([67, 69, 71, 72] * 4, character="volatile", chords={bar: C for bar in range(4)})
    assert_playable(transposed, D_KEY, "bach")
    score_to_musicxml(transposed)
    assert all(40 <= (note.midi or 0) + D_KEY.semitones <= 55 for note in transposed.low if note.midi is not None)


def test_villa_selloff_sings_thumb_cantabile_and_contrasts_with_chord_melody() -> None:
    selloff_day = render(_bars(), title="Guitar", variant="guitar", ensemble="villa", character="selloff")
    for bar in range(2, 31):
        assert 0.0 not in _onset_beats(selloff_day.lead, bar)
        assert {1.0, 3.0} <= set(_onset_beats(selloff_day.lead, bar))
        assert all(48 <= (note.midi or 0) <= 64 for note in _pitched(selloff_day.low, bar))

    epb = 8
    regions = (
        (0, 2, "intro", False),
        (2, 6, "phrase", False),
        (6, 10, "phrase", True),
        (10, 14, "phrase", False),
        (14, 16, "outro", False),
    )
    phrases = tuple(_held(start * epb, (end - start) * epb, 67) for start, end, _kind, _trio in regions)
    sections = tuple(FormSection(start, end, kind, 0, trio=trio) for start, end, kind, trio in regions)
    kinds = {bar: ("intro" if bar < 2 else "outro" if bar >= 14 else "phrase") for bar in range(16)}
    ternary = _guitar(
        phrases,
        ensemble="villa",
        bpm=100,
        character="selloff",
        kinds=kinds,
        sections=sections,
    )
    assert 0.0 not in _onset_beats(ternary.lead, 3)
    assert 0.0 in _onset_beats(ternary.lead, 7)
    assert 0.5 not in _onset_beats(ternary.support, 7)


def test_villa_live_tresillo_boosts_velocity_identically_in_mf_and_f_and_keeps_bass_without_mood() -> None:
    for band in ("mf", "f"):
        score = _pattern_score(
            [72] * 24,
            (_held(0, 24, 72),),
            ensemble="villa",
            bpm=100,
            character="volatile",
            bands={0: band, 1: band, 2: band},
            chords={0: C, 1: C, 2: C},
        )
        for bar in (0, 1):
            assert _onset_beats(score.low, bar)[:2] == [0.0, 2.0]
            assert {0.5, 1.0, 1.5, 2.5, 3.0} <= set(_onset_beats(score.support, bar))
            lead_vel = _pitched(score.lead, bar)[0].velocity or 64
            low_accents = {round(note.beat, 2): note.velocity for note in _pitched(score.low, bar) if note.accent}
            inner_accents = {
                round(note.beat, 2): note.velocity for note in _pitched(score.support, bar) if note.accent
            }
            unaccented_inner = [note.velocity for note in _pitched(score.support, bar) if not note.accent]
            assert low_accents == {0.0: 63}
            assert inner_accents == {1.5: 62, 3.0: 62}
            assert all(vel < 62 for vel in unaccented_inner if vel is not None)
            assert all(vel < lead_vel for vel in (*low_accents.values(), *inner_accents.values()) if vel is not None)
        assert not any(note.accent for note in _pitched(score.support, 2))

    # Framed daily score: even after _shape_dynamics adds band delta (+4 on `f`),
    # tresillo accents on bass and inner voice stay strictly below the melody.
    framed_vol = render(_bars(), title="Guitar", variant="guitar", ensemble="villa", character="volatile")
    for bar in range(2, 32):
        lead_vels = [note.velocity for note in _pitched(framed_vol.lead, bar) if note.velocity is not None]
        if not lead_vels:
            continue
        ceiling = max(lead_vels)
        for note in (*_pitched(framed_vol.low, bar), *_pitched(framed_vol.support, bar)):
            assert note.velocity is not None and note.velocity < ceiling

    unmarked = _pattern_score(
        [72] * 8,
        (_held(0, 8, 72),),
        ensemble="villa",
        bpm=100,
        character=None,
        bands={0: "mf"},
        chords={0: C},
    )
    assert _onset_beats(unmarked.low, 0) == [0.0, 2.0]


def test_barrios_mozart_brouwer_and_villa_feedback_regressions() -> None:
    # 1. Barrios: calm finale (trailing pedal >= 10 bars) still selects Ultimo Tremolo.
    finale = _suite(3, "barrios", character="calm")
    tremolo_bars = sum(
        1
        for bar in range(10, 40)
        if sum(1 for note in _pitched(finale.lead, bar) if abs(note.duration_beats - 0.25) < 1e-9) >= 12
    )
    assert tremolo_bars >= 20

    # Barrios 1D: flat/zero-activity rally or selloff under 1.4% span still sings Preludio.
    flat_day = [Bar(close=100.0, volume=1000 + index) for index in range(48)]
    preludio_day = render(flat_day, title="Guitar", variant="guitar", ensemble="barrios", character="rally")
    assert any(note.duration_beats >= 3.5 for note in _pitched(preludio_day.low, 4))

    # 2. Sor Op. 9 (`mozart_var`): held 76, arch, zig-zag leaps, and drops stay stepwise after `_repair`.
    for line in (
        [76] * 8,
        [64, 69, 74, 77, 77, 74, 71, 67],
        [60, 76, 62, 76, 64, 74, 67, 72],
        [76, 74, 72, 69, 67, 64, 62, 60],
    ):
        mozart = _pattern_score(
            line,
            (_joined(0, line),),
            ensemble="classic",
            bpm=88,
            character="volatile",
            chords={0: C},
        )
        inner_midis = [note.midi for note in _attacks(mozart.support, 0) if note.midi is not None]
        assert len(inner_midis) >= 5
        assert max(abs(right - left) for left, right in zip(inner_midis, inner_midis[1:])) <= 2
        _assert_engraved(mozart, "study")

    # 3. Brouwer `_modal_figure`: stays inside the bar's pitch range and preserves an early peak at eighth 1.
    drop_bar = [72, 64, 64, 64, 64, 64, 64, 60]
    drop_score = _pattern_score(
        drop_bar,
        (_joined(0, drop_bar),),
        ensemble="brouwer",
        bpm=108,
        character="selloff",
        chords={0: C},
    )
    drop_midis = [note.midi for note in _attacks(drop_score.lead, 0) if note.midi is not None]
    assert min(drop_midis) >= 60
    assert max(abs(right - left) for left, right in zip(drop_midis, drop_midis[1:])) <= 2

    arch_bar = [60, 72, 72, 72, 72, 72, 72, 67]
    arch_score = _pattern_score(
        arch_bar,
        (_joined(0, arch_bar),),
        ensemble="brouwer",
        bpm=108,
        character="selloff",
        chords={0: C},
    )
    arch_attacks = [note for note in _attacks(arch_score.lead, 0) if note.midi is not None]
    arch_midis = [note.midi for note in arch_attacks if note.midi is not None]
    assert max(arch_midis) == 72
    assert min(arch_midis) >= 60
    assert arch_midis[-1] == 67
    assert any(note.midi == 72 and note.beat < 2.0 - 1e-6 for note in arch_attacks)
    assert max(abs(right - left) for left, right in zip(arch_midis, arch_midis[1:])) <= 2
    assert all(1 <= abs(right - left) <= 2 for left, right in zip(arch_midis, arch_midis[1:]))

    # 4. Villa-Lobos: campanella rings across the thumb's 5th at beat 2.0 (eighth 3 -> 4),
    # and all three voices at beat 2.0 fit one hand position (`_playable`) even on high melodies.
    for villa_line in (
        [64, 65, 67, 69, 67, 65, 64, 62],
        [67, 69, 71, 72, 74, 72, 71, 69],
    ):
        villa_etude = _pattern_score(
            villa_line,
            (_joined(0, villa_line),),
            ensemble="villa",
            bpm=100,
            character="rally",
            bands={0: "mf"},
            chords={0: C},
        )
        campanella_notes = [
            note for note in _attacks(villa_etude.support, 0) if note.duration_beats >= 1.0 - 1e-6
        ]
        assert len(campanella_notes) >= 1
        ringing_inner = next(note for note in campanella_notes if abs(note.beat - 1.5) < 1e-6)
        bass_at_two = next(
            note for note in _pitched(villa_etude.low, 0) if note.beat <= 2.0 < note.beat + note.duration_beats
        )
        lead_at_two = next(
            note for note in _pitched(villa_etude.lead, 0) if note.beat <= 2.0 < note.beat + note.duration_beats
        )
        assert bass_at_two.midi is not None and ringing_inner.midi is not None and lead_at_two.midi is not None
        assert bass_at_two.midi < ringing_inner.midi < lead_at_two.midi
        _assert_engraved(villa_etude, "villa_pattern")

    # 5. Villa-Lobos: unframed `_select_body` and slow 72 BPM movements also sing `thumb_cantabile` on `selloff`.
    unframed_selloff = _pattern_score(
        [67, 69, 71, 72, 74, 72, 71, 69] * 2,
        (_joined(0, [67, 69, 71, 72, 74, 72, 71, 69]), _joined(8, [67, 69, 71, 72, 74, 72, 71, 69])),
        ensemble="villa",
        bpm=100,
        character="selloff",
    )
    assert 0.0 not in _onset_beats(unframed_selloff.lead, 1)
    assert all(48 <= (note.midi or 0) <= 64 for note in _pitched(unframed_selloff.low, 1))

    slow_selloff = _suite(1, "villa", character="selloff")
    assert 0.0 not in _attack_onsets(slow_selloff.lead, 12)
    assert 0.0 in _attack_onsets(slow_selloff.lead, 48)


def test_villa_preserves_forte_chromatic_approach_across_boundary_and_outro_reads_character_at() -> None:
    epb = 8
    regions = (
        (0, 2, "intro", False),
        (2, 6, "phrase", False),
        (6, 10, "phrase", True),
        (10, 14, "phrase", False),
        (14, 16, "outro", False),
    )
    phrases = tuple(_held(start * epb, (end - start) * epb, 72) for start, end, _kind, _trio in regions)
    sections = tuple(FormSection(start, end, kind, 0, trio=trio) for start, end, kind, trio in regions)
    kinds = {bar: ("intro" if bar < 2 else "outro" if bar >= 14 else "phrase") for bar in range(16)}
    bands = {bar: "f" for bar in range(16)}
    chords = {bar: C for bar in range(16)}
    score = _guitar(
        phrases,
        ensemble="villa",
        bpm=100,
        character="rally",
        kinds=kinds,
        sections=sections,
        bands=bands,
        chords=chords,
    )
    # Bar 5 is the last bar of section A (band="f") before Trio bar 6 on C.
    # Its eighth 7 keeps the chromatic approach B (pitch class 11) into C.
    approach = _attack_at(score.low, 5 * epb + 7, epb)
    assert approach is not None and approach.midi is not None
    assert approach.midi % 12 == 11

    # Movement character is calm, but the ending bars in character_at turn volatile.
    char_at = tuple(["calm"] * 12 + ["volatile"] * 4)
    outro_score = _guitar(
        phrases,
        ensemble="villa",
        bpm=100,
        character="calm",
        character_at=char_at,
        kinds=kinds,
        sections=sections,
        bands=bands,
        chords=chords,
    )
    assert 0.5 in _onset_beats(outro_score.lead, 15)
    assert any(note.accent for note in _pitched(outro_score.lead, 15))

