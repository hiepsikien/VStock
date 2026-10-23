"""Classical guitar is one nylon part, and the long forms keep the symphony clock."""

import pytest

from app.sonify.chords import C, DM, EM, F, G
from app.sonify.ensemble import ensemble_for
from app.sonify.form import METER_34, METER_44, METER_68, ChordSlot, compose_meter
from app.sonify.guitar import (
    _arpeggio,
    _attack_eighth,
    _melody_line,
    _place_melody,
    _slur,
    _tremolo,
    guard_chromatic_approach,
    render_guitar_score,
)
from app.sonify.keys import D_KEY, compose_register, register_for
from app.sonify.model import Bar, NoteEvent, Phrase, Run
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
