"""Twelfth-grid playability and the 3:2 sixteenth-triplet bracket."""

import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest

from app.sonify.chords import C
from app.sonify.form import ChordSlot
from app.sonify.guitar_patterns import (
    Unplayable,
    _covers12,
    _dur12,
    _start12,
    assert_playable,
)
from app.sonify.model import NoteEvent, Score
from app.sonify.musicxml import (
    _sextuplet_roles,
    _triplet_sixteenth_roles,
    _tuplet_roles,
    score_to_musicxml,
)

_EPB = 8  # 4/4: eight eighths, forty-eight twelfths


def _sixth(beat: float, midi: int = 64, duration: float = 1.0 / 6.0) -> NoteEvent:
    return NoteEvent(
        bar=0,
        beat=beat,
        midi=midi,
        duration_beats=duration,
        voice=1,
        velocity=64,
    )


def _score(lead: list[NoteEvent]) -> Score:
    return Score(
        title="Torroba",
        bpm=96,
        bars=1,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=(ChordSlot(0, 1, C, "sideway", "phrase"),),
        high=(),
        lead=tuple(lead),
        support=(),
        comp=(),
        low=(),
        dynamics=(),
        harmonies=(),
        liquidity=("mf",),
        phrases=(),
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant="guitar",
        ensemble="torroba",
        divisions=12,
        beats=4,
        beat_type=4,
        bar_beats=4.0,
    )


def _mordent() -> list[NoteEvent]:
    """E–F–E inside the eighth that starts at beat 1.5."""
    origin = 1.5
    return [_sixth(origin, 64), _sixth(origin + 1.0 / 6.0, 65), _sixth(origin + 2.0 / 6.0, 64)]


def _spans(events: list[NoteEvent]) -> list[tuple[int, int]]:
    return [(_start12(event, _EPB), _dur12(event)) for event in events]


def _sounding(xml: str) -> list[ET.Element]:
    root = ET.fromstring(xml)
    measure = root.find("part").find("measure")
    return [
        note
        for note in measure.findall("note")
        if note.find("rest") is None and note.find("chord") is None
    ]


def _modification(note: ET.Element) -> tuple[str, str, str]:
    modification = note.find("time-modification")
    assert modification is not None
    return (
        modification.find("actual-notes").text,
        modification.find("normal-notes").text,
        modification.find("normal-type").text,
    )


def test_three_sixths_inside_one_eighth_do_not_overlap() -> None:
    notes = _mordent()
    assert _spans(notes) == [(18, 2), (20, 2), (22, 2)]
    for start, dur in _spans(notes):
        for other, other_dur in _spans(notes):
            if other == start:
                continue
            assert not (start <= other < start + dur)
    # Half-open: the next sixth begins where this one ends.
    assert _covers12(notes[0], 18, _EPB)
    assert _covers12(notes[0], 19, _EPB)
    assert not _covers12(notes[0], 20, _EPB)
    assert_playable(_score(notes), profiles="torroba")


def test_real_twelfth_overlap_is_still_unplayable() -> None:
    """A sixth that starts one twelfth later still sits inside the first."""
    notes = [_sixth(1.5, 64), _sixth(1.5 + 1.0 / 12.0, 65)]
    assert _spans(notes) == [(18, 2), (19, 2)]
    assert _covers12(notes[0], _start12(notes[1], _EPB), _EPB)
    with pytest.raises(Unplayable, match="two notes in the high voice"):
        assert_playable(_score(notes), profiles="torroba")


def test_rasgueado_window_stays_the_first_half_beat() -> None:
    """Twelfths 3, 4, and 5 are still inside the old two-sixteenth roll.

    A second inner note starting at beat 4/12 rings with the rolled chord.
    The loose roll limits allow it. A window of three twelfths would not.
    """
    lead = [
        NoteEvent(bar=0, beat=2.0 / 12.0, midi=64, duration_beats=4.0 / 12.0, voice=1, velocity=68),
    ]
    support = [
        NoteEvent(bar=0, beat=1.0 / 12.0, midi=55, duration_beats=5.0 / 12.0, voice=2, velocity=56),
        NoteEvent(bar=0, beat=4.0 / 12.0, midi=59, duration_beats=2.0 / 12.0, voice=2, velocity=56),
    ]
    low = [
        NoteEvent(bar=0, beat=0.0, midi=40, duration_beats=0.5, voice=3, velocity=54),
    ]
    score = replace(_score(lead), support=tuple(support), low=tuple(low))
    assert _start12(support[1], _EPB) == 4
    assert _covers12(low[0], 4, _EPB)
    assert _covers12(support[0], 4, _EPB)
    assert _covers12(lead[0], 4, _EPB)
    assert_playable(score, profiles="torroba")


def test_triplet_sixteenth_exports_three_over_two() -> None:
    notes = _mordent()
    assert _triplet_sixteenth_roles(notes) == ["start", None, "stop"]
    assert _tuplet_roles(notes) == ["start", None, "stop"]
    xml = score_to_musicxml(_score(notes))
    assert "<actual-notes>6</actual-notes>" not in xml
    sounding = _sounding(xml)
    assert len(sounding) == 3
    assert [_modification(note) for note in sounding] == [("3", "2", "16th")] * 3
    assert [note.find("type").text for note in sounding] == ["16th"] * 3
    assert [note.find("duration").text for note in sounding] == ["2"] * 3
    tuplets = [note.find("notations").find("tuplet") if note.find("notations") is not None else None for note in sounding]
    assert tuplets[0] is not None and tuplets[0].get("type") == "start"
    assert tuplets[1] is None
    assert tuplets[2] is not None and tuplets[2].get("type") == "stop"


def test_sextuplet_keeps_six_over_four() -> None:
    notes = [_sixth(index / 6.0, 64 + (index % 2)) for index in range(6)]
    assert _sextuplet_roles(notes) == ["start", None, None, None, None, "stop"]
    assert _triplet_sixteenth_roles(notes) == [None] * 6
    assert _tuplet_roles(notes) == ["start", None, None, None, None, "stop"]
    xml = score_to_musicxml(_score(notes))
    sounding = _sounding(xml)
    assert len(sounding) == 6
    assert [_modification(note) for note in sounding] == [("6", "4", "16th")] * 6
    assert "<actual-notes>3</actual-notes>" not in xml
    tuplets = [note.find("notations").find("tuplet") for note in (sounding[0], sounding[-1])]
    assert tuplets[0].get("type") == "start"
    assert tuplets[1].get("type") == "stop"


def test_lone_sixth_and_rasgueado_stay_out_of_the_triplet() -> None:
    lone = [_sixth(0.0)]
    assert _triplet_sixteenth_roles(lone) == [None]
    assert _sextuplet_roles(lone) == [None]
    xml = score_to_musicxml(_score(lone))
    sounding = _sounding(xml)
    assert len(sounding) == 1
    assert _modification(sounding[0]) == ("6", "4", "16th")
    assert sounding[0].find("notations") is None or sounding[0].find("notations").find("tuplet") is None

    off_eighth = [_sixth(0.25 + index / 6.0) for index in range(3)]
    assert _triplet_sixteenth_roles(off_eighth) == [None, None, None]

    roll = [
        NoteEvent(bar=0, beat=2.0 / 12.0, midi=64, duration_beats=4.0 / 12.0, voice=1),
    ]
    assert _triplet_sixteenth_roles(roll) == [None]
    assert _sextuplet_roles(roll) == [None]
    assert _tuplet_roles(roll) == [None]
