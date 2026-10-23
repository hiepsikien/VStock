"""Ambient score: section-sized lines, a tied bed, and chunk shimmer."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from app.sonify.ambient import (
    COOLDOWN_HOLD,
    GLASS_HOLD,
    _anchors,
    _attach_daily_frames,
    _breath_spans,
    _glass,
    _omit_same_pitch_reattacks,
    promote_ambient_slots,
)
from app.sonify.chords import AM9, C, CMAJ7, CMAJ9, G9
from app.sonify.form import (
    DAILY_AMBIENT_SPEC,
    METER_34,
    METER_64,
    ChordSlot,
    FormSection,
    FormSpec,
    compose_meter,
)
from app.sonify.groove import BarGroove, compose_groove
from app.sonify.model import Bar, NoteEvent
from app.sonify.musicxml import score_to_musicxml
from app.sonify.playback import ambient_daily_candle_index, piece_seconds
from app.sonify.render import assign_daily_ambient_bars, assign_source_bars, render
from app.sonify.span import month_specs, prepare_week


def _onsets(notes: tuple[NoteEvent, ...]) -> list[NoteEvent]:
    return [note for note in notes if note.midi is not None and not note.tie_stop]


def _chains(notes: tuple[NoteEvent, ...]) -> list[list[NoteEvent]]:
    chains: list[list[NoteEvent]] = []
    current: list[NoteEvent] = []
    for note in sorted(notes, key=lambda item: (item.bar, item.beat)):
        if note.midi is None:
            continue
        if not note.tie_stop and current:
            chains.append(current)
            current = []
        current.append(note)
    if current:
        chains.append(current)
    return chains


def _breaths(notes: tuple[NoteEvent, ...]) -> list[list[NoteEvent]]:
    breaths: list[list[NoteEvent]] = []
    current: list[NoteEvent] = []
    in_slur = False
    for note in sorted(notes, key=lambda item: (item.bar, item.beat)):
        if note.midi is None:
            continue
        if current and (note.tie_stop or in_slur):
            current.append(note)
        else:
            if current:
                breaths.append(current)
            current = [note]
        if note.slur_start:
            in_slur = True
        if note.slur_stop:
            in_slur = False
    if current:
        breaths.append(current)
    return breaths


def _phrase_breaths(
    breaths: list[list[NoteEvent]],
    start: int,
    end: int,
    earlier: tuple[int, ...],
) -> list[list[NoteEvent]]:
    selected: list[list[NoteEvent]] = []
    for breath in breaths:
        if not any(start <= note.bar < end for note in breath):
            continue
        origin = breath[0].bar
        if any(phrase_start <= origin < start for phrase_start in earlier):
            continue
        selected.append(breath)
    return selected


def _beats(chain: list[NoteEvent]) -> float:
    return sum(note.duration_beats for note in chain)


def _sounding_eighths(notes: tuple[NoteEvent, ...]) -> int:
    return sum(int(round(note.duration_beats * 2)) for note in notes if note.midi is not None)


def _part(xml: str, part_id: str) -> ET.Element:
    root = ET.fromstring(xml)
    return next(part for part in root.findall("part") if part.get("id") == part_id)


def test_flat_day_states_the_flute_pitch_once() -> None:
    score = render([Bar(80.0, 0.0, 80.0) for _ in range(30)], variant="ambient")
    assert score.variant == "ambient"
    assert score.bpm == 60
    assert score.bars == 34
    chains = _chains(score.lead)
    assert [chain[0].bar for chain in chains] == [0]
    assert _beats(chains[0]) == 24
    assert len({note.midi for note in chains[0]}) == 1
    assert chains[0][0].midi % 12 == 0
    assert not any(note.bar >= 32 and note.midi is not None for note in score.lead)
    assert score.lead_dynamics[0].marking == "p"
    assert score.dynamics[0].marking == "p"
    assert (score.dynamics[-1].bar, score.dynamics[-1].marking) == (33, "ppp")
    assert score.support_dynamics[-1].marking == "ppp"
    assert any(wedge.kind == "crescendo" and wedge.bar == 0 for wedge in score.lead_wedges)
    assert any(wedge.kind == "diminuendo" and wedge.bar == 32 for wedge in score.support_wedges)
    assert _sounding_eighths(score.high) == 0


def test_a_touching_same_pitch_finishes_four_bars_then_rests() -> None:
    kept = _omit_same_pitch_reattacks(
        [
            (56, 24, 84, False, False, False),
            (80, 32, 84, False, False, False),
            (144, 32, 84, False, False, False),
        ]
    )
    assert kept == [(56, GLASS_HOLD, 84, False, False, False)]


def test_a_finished_breath_releases_when_the_same_pitch_touches() -> None:
    note = (0, GLASS_HOLD, 84, False, False, False)
    assert _omit_same_pitch_reattacks([note, (GLASS_HOLD, GLASS_HOLD, 84, False, False, False)]) == [note]


def test_breath_windows_follow_the_meter_and_calm() -> None:
    assert _breath_spans(0, 4) == [(0, 4)]
    assert _breath_spans(0, 5) == [(0, 1), (2, 5)]
    assert _breath_spans(0, 6) == [(0, 2), (3, 6)]
    assert _breath_spans(0, 7) == [(0, 2), (3, 7)]
    assert _breath_spans(2, 12) == [(2, 5), (8, 12)]
    assert _breath_spans(12, 20) == [(12, 14), (16, 20)]
    assert _breath_spans(20, 32) == [(20, 22), (24, 26), (28, 32)]
    calm = {bar: BarGroove(calm=True) for bar in range(34)}
    with compose_groove(calm):
        assert _breath_spans(2, 12) == [(2, 5), (8, 12)]
        assert _breath_spans(12, 20) == [(12, 14), (16, 20)]
        assert _breath_spans(20, 32) == [(20, 22), (24, 26), (28, 32)]
    with compose_meter(METER_34):
        assert _breath_spans(0, 5) == [(0, 5)]
        assert _breath_spans(0, 6) == [(0, 2), (3, 6)]
        assert _breath_spans(0, 11) == [(0, 3), (6, 11)]
    with compose_meter(METER_64):
        assert _breath_spans(0, 3) == [(0, 3)]
        assert _breath_spans(0, 4) == [(0, 1), (2, 4)]
        assert _breath_spans(0, 8) == [(0, 3), (5, 8)]
        assert _breath_spans(0, 12) == [(0, 3), (4, 7), (9, 12)]
        assert _breath_spans(0, 14) == [(0, 3), (4, 7), (11, 14)]
        assert _breath_spans(0, 16) == [(0, 3), (4, 7), (8, 11), (13, 16)]
        assert _breath_spans(0, 24) == [(0, 3), (4, 7), (8, 11), (12, 15), (16, 19), (21, 24)]
        assert _breath_spans(0, 26) == [(0, 3), (4, 7), (8, 11), (12, 15), (16, 19), (23, 26)]
        with compose_groove(calm):
            assert _breath_spans(0, 8) == [(0, 3), (5, 8)]


def test_a_rise_that_levels_off_ties_across_the_bar_then_rests() -> None:
    closes = [100.0, 102.0, 104.0, 106.0] + [106.0] * 26
    score = render([Bar(close, 1_000.0, close) for close in closes], variant="ambient")
    breaths = _breaths(score.lead)
    opening = breaths[0]
    assert opening[0].bar == 0
    assert opening[0].midi % 12 == 0
    tonic = [note for note in opening if note.midi == opening[0].midi]
    assert _beats(tonic) == 12
    assert any(note.bar == 2 and note.tie_stop and note.midi % 12 == 0 for note in score.lead)
    step = next(note for note in opening if note.midi != opening[0].midi)
    assert step.bar == 3
    assert not step.tenuto
    assert not any(note.bar in (5, 6, 7) and note.midi is not None for note in score.lead)
    leveled = next(breath for breath in breaths if breath[0].bar == 8)
    held = [note for note in leveled if note.midi == leveled[-1].midi]
    assert _beats(held) == 16
    carried = next(note for note in score.lead if note.bar == 10 and note.midi == leveled[-1].midi)
    assert carried.tie_stop
    assert carried.beat == 0.0
    assert not any(
        note.bar == 10 and note.midi == leveled[-1].midi and not note.tie_stop for note in score.lead
    )
    assert not any(
        note.bar >= 13 and note.midi == leveled[-1].midi and not note.tie_stop for note in score.lead
    )


def test_cool_down_extends_a_touching_breath_to_five_bars_then_rests() -> None:
    outro = 32 * 8
    chords = {bar: CMAJ7 for bar in range(34)}

    def body(segments: list[tuple[int, int, int, bool, bool, bool]]):
        attached = _attach_daily_frames(segments, DAILY_AMBIENT_SPEC, chords)
        return [segment for segment in attached if segment[0] >= 16]

    four_bars = (outro - GLASS_HOLD, GLASS_HOLD, 72, False, False, False)
    assert body([four_bars]) == [(outro - GLASS_HOLD, COOLDOWN_HOLD, 72, False, False, False)]

    two_bars = (outro - 16, 16, 72, False, False, False)
    assert body([two_bars]) == [(outro - 16, 16 + 16, 72, False, False, False)]

    five_bars = (outro - COOLDOWN_HOLD, COOLDOWN_HOLD, 72, False, False, False)
    assert body([five_bars]) == [five_bars]

    rested = (outro - 48, GLASS_HOLD, 72, False, False, False)
    assert all(segment[0] < outro for segment in body([rested]))

    other = body([(outro - GLASS_HOLD, GLASS_HOLD, 67, False, False, False)])
    assert other[-1][:3] == (outro, 2 * 8, 72)


def test_a_faded_pitch_is_not_rebreathed_until_the_line_moves() -> None:
    held = (0, 16, 64, False, False, False)
    sideways = [
        (32, 8, 64, True, False, False),
        (40, 8, 65, True, False, False),
        (48, 8, 64, False, False, False),
    ]
    assert _omit_same_pitch_reattacks([held, *sideways]) == [held]
    assert _omit_same_pitch_reattacks(
        [held, (32, 8, 64, False, False, False)],
        pitches=[64] * 32 + [77] * 8 + [64] * 8,
    ) == [held]
    kept_step = _omit_same_pitch_reattacks([held, (32, 8, 64, True, False, False), (40, 8, 65, False, False, False)])
    assert [segment[2] for segment in kept_step] == [64, 64, 65]
    kept_leap = _omit_same_pitch_reattacks(
        [held, (32, 8, 64, True, False, False), (40, 8, 67, True, False, False), (48, 8, 64, False, False, False)]
    )
    assert [segment[2] for segment in kept_leap] == [64, 64, 67, 64]
    kept_fold = _omit_same_pitch_reattacks(
        [held, (32, 8, 64, False, False, False)],
        pitches=[64] * 32 + [79] * 8,
    )
    assert [segment[2] for segment in kept_fold] == [64, 64]


def test_a_rising_phrase_section_keeps_at_most_four_glass_attacks() -> None:
    closes = [100.0 + index * 4.0 for index in range(30)]
    score = render([Bar(close, 1_000.0, close) for close in closes], variant="ambient")
    breaths = _breaths(score.lead)
    phrases = ((2, 12), (12, 20), (20, 32))
    counted = [
        _phrase_breaths(breaths, start, end, tuple(item[0] for item in phrases if item[0] < start))
        for start, end in phrases
    ]
    assert [len(group) for group in counted] == [2, 2, 3]
    for group, (_start, end) in zip(counted, phrases):
        assert any(note.bar == end - 1 for note in group[-1])
    assert any(event.marking == "mf" for event in score.lead_dynamics)
    for note in score.lead:
        if note.midi is not None:
            assert 55 <= note.midi <= 84
            assert note.beat == 0.0
            assert note.duration_beats == 4.0
    assert _sounding_eighths(score.high) == 8


def _held(midi: int, bars: int) -> list[int]:
    return [midi] * (bars * 8)


def _line(
    sections: tuple[FormSection, ...],
    pitches: list[int],
    chord_at: dict | None = None,
):
    form = FormSpec(bars=sections[-1].end, bpm=60, sections=sections)
    return _glass(form, (), pitches, chord_at=chord_at)


def test_the_eight_bar_diagram_slurs_two_breaths() -> None:
    notes, _wedges, dynamics = _line(
        (FormSection(0, 8, "phrase", 0),),
        _held(72, 1) + _held(76, 2) + _held(74, 4) + _held(72, 1),
    )
    breaths = _breaths(tuple(notes))
    assert [[note.bar for note in breath if not note.tie_stop] for breath in breaths] == [
        [0, 1],
        [4, 7],
    ]
    assert [breath[0].midi for breath in breaths] == [72, 74]
    assert breaths[0][-1].midi == 76
    assert breaths[1][-1].midi == 72
    opening, close = [note for note in breaths[0] if not note.tie_stop]
    assert opening.slur_start and opening.tenuto and not opening.slur_stop
    assert close.slur_stop and not close.slur_start and not close.tenuto
    assert [(event.bar, event.marking) for event in dynamics] == [(0, "mf"), (4, "mp")]
    assert not any(note.bar in (2, 3) and note.midi is not None for note in notes)


def test_a_weak_beat_extreme_moves_to_the_downbeat_under_one_slur() -> None:
    dipped = [72, 76, 76, 76, 76, 76, 76, 76]
    notes, _wedges, _dynamics = _line(
        (FormSection(0, 4, "phrase", 0),),
        _held(72, 1) + dipped + _held(72, 1) + _held(74, 1),
    )
    attacks = _onsets(tuple(notes))
    assert [(note.bar, note.midi) for note in attacks] == [(0, 72), (1, 76), (3, 74)]
    assert attacks[0].slur_start and attacks[0].tenuto
    assert not attacks[1].slur_start and not attacks[1].slur_stop and not attacks[1].tenuto
    assert attacks[2].slur_stop and not attacks[2].tenuto


def test_anchors_keep_a_semitone_and_the_earlier_tied_extreme() -> None:
    assert _anchors(0, 4, _held(60, 3) + _held(61, 1), None, None) == [(0, 60), (3, 61)]
    assert _anchors(0, 4, _held(60, 4), None, None) == [(0, 60)]
    tied = _held(60, 1) + _held(56, 1) + _held(64, 1) + _held(60, 1)
    assert _anchors(0, 4, tied, None, None)[1][0] == 1


def test_a_major_chord_drops_the_perfect_fourth_and_minor_or_dominant_keep_it() -> None:
    fourth = [60] + [65] * 7
    body = _held(60, 1) + fourth + _held(60, 2)
    major, _wedges, _dynamics = _line((FormSection(0, 4, "phrase", 0),), body, {1: CMAJ9})
    assert [note.midi for note in _onsets(tuple(major))] == [60]
    minor, _wedges, _dynamics = _line((FormSection(0, 4, "phrase", 0),), body, {1: AM9})
    assert [(note.bar, note.midi) for note in _onsets(tuple(minor))] == [(0, 60), (1, 65), (3, 60)]
    eleventh = [67] + [60] * 7
    dominant, _wedges, _dynamics = _line(
        (FormSection(0, 4, "phrase", 0),),
        _held(67, 1) + eleventh + _held(67, 2),
        {1: G9},
    )
    assert [(note.bar, note.midi) for note in _onsets(tuple(dominant))] == [(0, 67), (1, 60), (3, 67)]


def test_an_unframed_outro_does_not_reattack_the_same_pitch_after_a_rest() -> None:
    sections = (FormSection(0, 8, "phrase", 0), FormSection(8, 12, "outro", 0))
    rested, _wedges, _dynamics = _line(sections, _held(72, 8) + _held(72, 1) + _held(76, 1) + _held(72, 2))
    held = [note for note in rested if note.midi is not None]
    assert [(note.bar, note.midi) for note in held] == [(0, 72), (1, 72), (2, 72), (3, 72)]
    assert not any(note.bar >= 8 and note.midi is not None for note in rested)
    sounded, _wedges, _dynamics = _line(sections, _held(72, 8) + _held(76, 4))
    outro = [note for note in sounded if note.bar >= 8 and note.midi is not None]
    assert outro[0].bar == 8 and outro[0].midi == 76 and outro[0].tenuto
    assert _beats(outro) == 16
    touching, _wedges, _dynamics = _line(
        (FormSection(0, 2, "phrase", 0), FormSection(2, 6, "outro", 0)),
        _held(72, 6),
    )
    assert [note.bar for note in _onsets(tuple(touching))] == [0]
    assert _beats([note for note in touching if note.midi is not None]) == 16


def test_a_calm_day_keeps_the_same_flute_rests() -> None:
    closes = [100.0 + index * 4.0 for index in range(30)]
    bars = [Bar(close, 1_000.0, close) for close in closes]
    plain = render(bars, variant="ambient")
    calm = render(bars, variant="ambient", character="calm")

    def flute(score):
        return [
            (note.bar, note.midi, note.tie_stop)
            for note in score.lead
            if note.midi is not None
        ]

    assert flute(calm) == flute(plain)
    sounding = {bar for bar, _midi, _tie in flute(plain)}
    assert {2, 3, 4, 8, 9, 10, 11, 12, 13, 16, 17, 18, 19} <= sounding
    assert {20, 21, 24, 25, 28, 29, 30, 31} <= sounding
    assert not sounding & {5, 6, 7, 14, 15, 22, 23, 26, 27}


def test_same_jazz_chord_is_one_drone_attack() -> None:
    slots, harmonies, chord_at = promote_ambient_slots(
        (
            ChordSlot(0, 2, C, "sideway", "phrase"),
            ChordSlot(2, 2, CMAJ7, "sideway", "phrase"),
        )
    )
    assert len(slots) == 1
    assert slots[0].length == 4
    assert slots[0].chord.name == "Cmaj9"
    assert len(harmonies) == 1
    assert chord_at[0] == chord_at[3]

    score = render([Bar(80.0, 0.0, 80.0) for _ in range(30)], variant="ambient")
    bass = {
        bar: slot.chord.bass_midi
        for slot in score.slots
        for bar in slot.bars()
    }
    for bar in range(score.bars - 1):
        if bass[bar] != bass[bar + 1]:
            continue
        assert any(note.bar == bar and note.tie_start and note.midi == bass[bar] for note in score.low)


def test_fifth_is_a_chord_on_loud_bars_and_absent_on_quiet_ones() -> None:
    volumes = [100.0] * 16 + [50_000.0] * 14
    closes = [100.0 + index for index in range(30)]
    score = render(
        [Bar(close, volume, close) for close, volume in zip(closes, volumes)],
        variant="ambient",
    )
    xml = score_to_musicxml(score)
    bass = _part(xml, "P4")
    quiet = bass.find("measure[@number='5']")
    loud = bass.find("measure[@number='19']")
    assert quiet is not None and loud is not None
    assert quiet.find("note/chord") is None
    assert loud.find("note/chord") is not None
    for measure in bass.findall("measure"):
        non_chord = [note for note in measure.findall("note") if note.find("chord") is None]
        assert sum(int(note.find("duration").text) for note in non_chord) == 8

    swell = _part(xml, "P3")
    assert swell.find("measure/attributes/staves") is None
    assert swell.findall("measure/harmony") == []
    assert any(
        measure.find("direction/direction-type/dynamics/mp") is not None
        or measure.find("direction/direction-type/dynamics/mf") is not None
        for measure in swell.findall("measure")
    )
    assert any(
        measure.find("direction/direction-type/wedge[@type='crescendo']") is not None
        for measure in swell.findall("measure")
    )
    halo = _part(xml, "P2")
    assert halo.find("measure/attributes/clef/sign").text == "G"
    assert halo.find("measure[@number='1']/direction/direction-type/dynamics/p") is not None
    assert _sounding_eighths(score.support) > 0
    programs = {
        part.get("id"): part.find("midi-instrument/midi-program").text
        for part in ET.fromstring(xml).find("part-list").findall("score-part")
    }
    assert programs == {"P5": "9", "P1": "74", "P2": "74", "P3": "61", "P4": "43"}


def test_week_uses_form_tempo_and_chunk_spans_for_shimmer() -> None:
    prepared = prepare_week(
        [
            [Bar(100.0, 10.0, 100.0) for _ in range(40)],
            [Bar(100.0 + index * 3.0, 10.0 + index, 100.0) for index in range(40)],
        ]
    )[0]
    score = render(
        prepared.bars,
        variant="ambient",
        form=prepared.spec,
        source_groups=prepared.groups,
    )
    assert score.bars == 64
    assert score.bpm == 90
    assert len(_onsets(score.lead)) >= 1
    assert len([note for note in _onsets(score.lead) if note.bar < 8]) == 1
    shimmer = [note for note in score.high if note.midi is not None]
    assert shimmer
    assert all(note.bar >= 32 for note in shimmer)
    assert _sounding_eighths(score.high) == 8


def test_month_movement_without_an_outro_does_not_invent_one() -> None:
    spec = month_specs("ambient")[1]
    assert all(section.kind != "outro" for section in spec.sections)
    bars = [Bar(40.0, 0.0, 40.0) for _ in range(spec.bars)]
    score = render(
        bars,
        variant="ambient",
        form=spec,
        source_groups=assign_source_bars(len(bars), spec.bars),
    )
    assert score.bars == 48
    assert score.bpm == 72
    assert [note.bar for note in _onsets(score.lead)] == [0]


def test_breathing_directions_land_before_a_sounding_note_and_harp_swell_is_open() -> None:
    closes = [100.0] * 10 + [100.0 + (index % 5) * 3.0 for index in range(10)] + [102.0] * 10
    volumes = [100.0] * 8 + [50_000.0] * 22
    score = render(
        [Bar(close, volume, close) for close, volume in zip(closes, volumes)],
        variant="ambient",
    )
    xml = score_to_musicxml(score)
    lead = _part(xml, "P1")
    for measure in lead.findall("measure"):
        children = list(measure)
        for index, node in enumerate(children):
            if node.tag != "direction":
                continue
            has_dynamic = node.find("direction-type/dynamics") is not None
            wedge = node.find("direction-type/wedge")
            is_opening_wedge = wedge is not None and wedge.get("type") in ("crescendo", "diminuendo")
            if has_dynamic or is_opening_wedge:
                assert any(
                    later.tag == "note" and later.find("rest") is None
                    for later in children[index + 1 :]
                ), f"direction at bar {measure.get('number')} fell after the last sounding note"

    chord_by_bar = {bar: slot.chord for slot in score.slots for bar in slot.bars()}
    by_bar: dict[int, list[NoteEvent]] = {}
    for note in score.comp:
        if note.midi is not None and not note.tie_stop:
            by_bar.setdefault(note.bar, []).append(note)
    assert by_bar
    swell_part = _part(xml, "P3")
    for bar, notes in by_bar.items():
        ordered = sorted(note.midi for note in notes if note.midi is not None)
        assert len(ordered) == 3
        pcs = chord_by_bar[bar].pitch_classes
        assert all(midi % 12 in pcs for midi in ordered)
        assert ordered[1] - ordered[0] >= 3
        assert ordered[2] - ordered[1] >= 3
        assert ordered[2] - ordered[0] >= 8
        assert all(note.velocity == 49 for note in notes)
        measure = swell_part.find(f"measure[@number='{bar + 1}']")
        assert measure is not None
        assert measure.find("direction/direction-type/dynamics/p") is not None
        assert measure.find("direction/direction-type/wedge[@type='crescendo']") is not None
        first_note = measure.find("note")
        assert first_note is not None and first_note.get("dynamics") == "54.44"
        next_measure = swell_part.find(f"measure[@number='{bar + 2}']")
        assert any(
            m is not None and m.find("direction/direction-type/wedge[@type='diminuendo']") is not None
            for m in (measure, next_measure)
        )


def test_daily_warmup_is_the_tonic_and_the_price_starts_at_the_phrase() -> None:
    groups = assign_daily_ambient_bars(30)
    assert len(groups) == 34
    assert groups[0] == []
    assert groups[1] == []
    assert groups[2] == [0]
    assert groups[31] == [29]
    assert groups[32] == []
    assert groups[33] == []
    assert [index for group in groups for index in group] == list(range(30))
    assert assign_source_bars(30)[0] == [0]

    closes = [200.0 - index * 0.5 for index in range(30)]
    score = render([Bar(close, 1_000.0, close) for close in closes], variant="ambient")
    intro = next(note for note in score.lead if note.midi is not None and note.bar == 0)
    phrase = next(note for note in _onsets(score.lead) if note.bar >= 2)
    assert intro.midi % 12 == score.slots[0].chord.pitches[0] % 12 == 0
    assert phrase.midi != intro.midi
    outro = next(note for note in score.lead if note.midi is not None and note.bar == 32)
    assert outro.tie_stop
    assert outro.midi % 12 == 0
    assert not any(
        note.bar >= 32 and note.midi is not None and not note.tie_stop for note in score.lead
    )
    assert (score.lead_dynamics[-1].bar, score.lead_dynamics[-1].marking) == (33, "ppp")
    symphony = render([Bar(close, 1_000.0, close) for close in closes], variant="symphony")
    assert symphony.bars == 34
    assert not any(note.bar == 0 and note.midi is not None for note in symphony.lead)
    assert any(note.bar == 0 and note.midi is not None and note.midi % 12 == 0 for note in symphony.support)


def test_ambient_daily_playhead_holds_the_open_and_the_close() -> None:
    duration = piece_seconds(34, 60)
    assert duration == 136
    assert ambient_daily_candle_index(0, 100, duration) == 0
    assert ambient_daily_candle_index(7.9, 100, duration) == 0
    assert ambient_daily_candle_index(8.0, 100, duration) == 0
    assert ambient_daily_candle_index(8.0 + 60, 100, duration) == 50
    assert ambient_daily_candle_index(128, 100, duration) == 99
    assert ambient_daily_candle_index(135.9, 100, duration) == 99


def test_minimalist_score_stays_on_its_own_clock() -> None:
    bars = [Bar(100.0 + index * 0.2, 20.0, 100.0) for index in range(30)]
    minimalist = render(bars, variant="minimalist")
    ambient = render(bars, variant="ambient")
    assert minimalist.variant == "minimalist"
    assert minimalist.bpm == 118
    assert ambient.bpm == 60
    assert len(_onsets(minimalist.lead)) > len(_onsets(ambient.lead))
