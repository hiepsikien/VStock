"""Classical guitar is one nylon part, and the long forms keep the symphony clock."""

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
    render_guitar_score,
)
from app.sonify.keys import C_KEY, D_KEY, compose_register, register_for
from app.sonify.model import Bar, NoteEvent, Phrase, Run, Score
from app.sonify.musicxml import score_to_musicxml
from app.sonify.render import render
from app.sonify.span import month_specs


def _bars() -> list[Bar]:
    return [Bar(close=100 + (index % 9) * 0.4, volume=1000 + index * 10) for index in range(48)]


def test_guitar_score_is_one_nylon_part() -> None:
    # Villa at 100 BPM may carry a sixteenth scale run. Barrios tremolo is sixteenths.
    expected = {"classic": (88, 2), "villa": (100, 4), "barrios": (120, 4)}
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
        # Barrios may print the Saudade bell against the price note. The other
        # two composers keep one note per voice at each attack.
        if ensemble == "barrios":
            assert "<chord" in first
        else:
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
    # D3 stays, with the fifth folded into the same window. E4 folds to E3,
    # not E2. F4 folds to F3, the ceiling.
    assert _bass_pitches(score, 0) == {50, 45}
    assert _bass_pitches(score, 1) == {52, 47}
    assert _bass_pitches(score, 2) == {53, 48}

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
    assert 50 in _bass_pitches(written, 0)
    assert all(38 <= note <= 51 for note in _bass_pitches(written, 0))


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
