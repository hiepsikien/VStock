"""Ambient score: section-sized lines, a tied bed, and chunk shimmer."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from app.sonify.ambient import GLASS_HOLD, _omit_same_pitch_reattacks, promote_ambient_slots
from app.sonify.chords import C, CMAJ7
from app.sonify.form import ChordSlot
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
    assert score.bars == 36
    chains = _chains(score.lead)
    assert [chain[0].bar for chain in chains] == [0, 32]
    assert _beats(chains[0]) == 24
    assert _beats(chains[1]) == 16
    assert len({note.midi for note in chains[0]}) == 1
    assert chains[0][0].midi % 12 == chains[1][0].midi % 12 == 0
    assert score.lead_dynamics[0].marking == "p"
    assert any(wedge.kind == "crescendo" and wedge.bar == 0 for wedge in score.lead_wedges)
    assert any(wedge.kind == "diminuendo" and wedge.bar == 32 for wedge in score.lead_wedges)
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


def test_a_rise_that_levels_off_ties_across_the_bar_then_rests() -> None:
    closes = [100.0, 102.0, 104.0, 106.0] + [106.0] * 26
    score = render([Bar(close, 1_000.0, close) for close in closes], variant="ambient")
    chains = _chains(score.lead)
    assert chains[0][0].bar == 0
    assert chains[0][0].midi % 12 == 0
    assert _beats(chains[0]) == 24
    held = next(chain for chain in chains if chain[0].bar == 9)
    assert _beats(held) == 16
    assert len({note.midi for note in held}) == 1
    carried = next(note for note in score.lead if note.bar == 10 and note.midi == held[0].midi)
    assert carried.tie_stop
    assert carried.beat == 0.0
    assert not any(
        note.bar == 10 and note.midi == held[0].midi and not note.tie_stop for note in score.lead
    )
    outro = chains[-1]
    assert outro[0].bar == 32
    assert outro[0].midi % 12 == 0
    assert _beats(outro) == 16


def test_a_faded_pitch_is_not_rebreathed_until_the_line_moves() -> None:
    closes = [80.0] * 12 + [80.4, 80.8, 81.2, 80.8, 80.4] + [80.2] * 13
    score = render([Bar(close, 1_000.0, close) for close in closes], variant="ambient")
    attacks = _onsets(score.lead)
    assert attacks[0].bar == 0
    assert all(left.midi != right.midi for left, right in zip(attacks, attacks[1:]))
    assert any(note.bar >= 10 for note in attacks)


def test_a_rising_phrase_section_keeps_at_most_four_glass_attacks() -> None:
    closes = [100.0 + index * 4.0 for index in range(30)]
    score = render([Bar(close, 1_000.0, close) for close in closes], variant="ambient")
    all_attacks = _onsets(score.lead)
    assert all(
        b.bar - a.bar >= 3
        for a, b in zip(all_attacks, all_attacks[1:])
    )
    assert any(event.marking == "mf" for event in score.lead_dynamics)
    for start in (2, 10, 18):
        attacks = [note for note in all_attacks if start <= note.bar < start + 8]
        assert 1 <= len(attacks) <= 2
        bars = [note.bar for note in attacks]
        assert bars == sorted(bars)
        assert len(bars) == len(set(bars))
    for note in score.lead:
        if note.midi is not None:
            assert 55 <= note.midi <= 84
            assert note.beat == 0.0
            assert note.duration_beats == 4.0
    assert _sounding_eighths(score.high) == 8


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
    spec = month_specs()[1]
    assert all(section.kind != "outro" for section in spec.sections)
    bars = [Bar(40.0, 0.0, 40.0) for _ in range(spec.bars)]
    score = render(
        bars,
        variant="ambient",
        form=spec,
        source_groups=assign_source_bars(len(bars), spec.bars),
    )
    assert score.bars == 72
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
    assert len(groups) == 36
    assert groups[0] == []
    assert groups[1] == []
    assert groups[2] == [0]
    assert groups[31] == [29]
    assert groups[32] == []
    assert groups[35] == []
    assert [index for group in groups for index in group] == list(range(30))
    assert assign_source_bars(30)[0] == [0]

    closes = [200.0 - index * 0.5 for index in range(30)]
    score = render([Bar(close, 1_000.0, close) for close in closes], variant="ambient")
    intro = next(note for note in score.lead if note.midi is not None and note.bar == 0)
    phrase = next(note for note in _onsets(score.lead) if note.bar >= 2)
    assert intro.midi % 12 == score.slots[0].chord.pitches[0] % 12 == 0
    assert phrase.midi != intro.midi
    outro = next(note for note in _onsets(score.lead) if note.bar >= 32)
    assert outro.bar == 32
    assert outro.midi % 12 == 0
    symphony = render([Bar(close, 1_000.0, close) for close in closes], variant="symphony")
    assert any(note.bar == 0 and note.midi is not None for note in symphony.lead)


def test_ambient_daily_playhead_holds_the_open_and_the_close() -> None:
    duration = piece_seconds(36, 60)
    assert duration == 144
    assert ambient_daily_candle_index(0, 100, duration) == 0
    assert ambient_daily_candle_index(7.9, 100, duration) == 0
    assert ambient_daily_candle_index(8.0, 100, duration) == 0
    assert ambient_daily_candle_index(8.0 + 60, 100, duration) == 50
    assert ambient_daily_candle_index(128, 100, duration) == 99
    assert ambient_daily_candle_index(143.9, 100, duration) == 99


def test_minimalist_score_stays_on_its_own_clock() -> None:
    bars = [Bar(100.0 + index * 0.2, 20.0, 100.0) for index in range(30)]
    minimalist = render(bars, variant="minimalist")
    ambient = render(bars, variant="ambient")
    assert minimalist.variant == "minimalist"
    assert minimalist.bpm == 118
    assert ambient.bpm == 60
    assert len(_onsets(minimalist.lead)) > len(_onsets(ambient.lead))
