"""Ambient score: section-sized lines, a tied bed, and chunk shimmer."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from app.sonify.ambient import promote_ambient_slots
from app.sonify.chords import C, CMAJ7
from app.sonify.form import ChordSlot
from app.sonify.model import Bar, NoteEvent
from app.sonify.musicxml import score_to_musicxml
from app.sonify.render import assign_source_bars, render
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


def test_flat_day_holds_one_glass_note_per_phrase_section() -> None:
    score = render([Bar(80.0, 0.0, 80.0) for _ in range(30)], variant="ambient")
    assert score.variant == "ambient"
    assert score.bpm == 60
    chains = _chains(score.lead)
    assert [chain[0].bar for chain in chains] == [0, 10, 18, 26]
    assert _beats(chains[0]) == 24
    assert _beats(chains[1]) == 16
    assert _beats(chains[2]) == 16
    assert _beats(chains[3]) == 16
    assert _sounding_eighths(score.high) == 0


def test_a_rising_phrase_section_keeps_at_most_four_glass_attacks() -> None:
    closes = [100.0 + index * 4.0 for index in range(30)]
    score = render([Bar(close, 1_000.0, close) for close in closes], variant="ambient")
    for start in (2, 10, 18):
        attacks = [note for note in _onsets(score.lead) if start <= note.bar < start + 8]
        assert 1 <= len(attacks) <= 4
        bars = [note.bar for note in attacks]
        assert bars == sorted(bars)
        assert len(bars) == len(set(bars))
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
    loud = bass.find("measure[@number='17']")
    assert quiet is not None and loud is not None
    assert quiet.find("note/chord") is None
    assert loud.find("note/chord") is not None
    for measure in bass.findall("measure"):
        non_chord = [note for note in measure.findall("note") if note.find("chord") is None]
        assert sum(int(note.find("duration").text) for note in non_chord) == 8

    swell = _part(xml, "P3")
    assert swell.find("measure/attributes/staves") is None
    assert any(measure.find("direction/direction-type/dynamics/f") is not None for measure in swell.findall("measure"))
    halo = _part(xml, "P2")
    assert halo.find("measure/attributes/clef/sign").text == "G"
    programs = {
        part.get("id"): part.find("midi-instrument/midi-program").text
        for part in ET.fromstring(xml).find("part-list").findall("score-part")
    }
    assert programs["P5"] == "9"


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
    assert [note.bar for note in _onsets(score.lead)] == [0, 32, 48]


def test_minimalist_score_stays_on_its_own_clock() -> None:
    bars = [Bar(100.0 + index * 0.2, 20.0, 100.0) for index in range(30)]
    minimalist = render(bars, variant="minimalist")
    ambient = render(bars, variant="ambient")
    assert minimalist.variant == "minimalist"
    assert minimalist.bpm == 118
    assert ambient.bpm == 60
    assert len(_onsets(minimalist.lead)) > len(_onsets(ambient.lead))
