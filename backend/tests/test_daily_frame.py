"""1D symphony, jazz, and minimalist attach a tonic frame around the price body."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from app.sonify.form import DAILY_SPEC
from app.sonify.model import Bar, NoteEvent, Score
from app.sonify.musicxml import score_to_musicxml
from app.sonify.render import render

WARM = (0, 1)
COOL = (32, 33, 34, 35)


def _measures_fill(score: Score) -> None:
    root = ET.fromstring(score_to_musicxml(score))
    expected = 4 * score.divisions
    for part in root.findall("part"):
        for measure in part.findall("measure"):
            staves = {note.findtext("staff") or "1" for note in measure.findall("note")}
            for staff in staves:
                sounding = [
                    note
                    for note in measure.findall("note")
                    if (note.findtext("staff") or "1") == staff and note.find("chord") is None
                ]
                assert sum(int(note.findtext("duration")) for note in sounding) == expected


def _day() -> list[Bar]:
    closes = [200.0 - index * 0.5 for index in range(30)]
    return [Bar(close, 1_000.0, close) for close in closes]


def _sounding(notes: tuple[NoteEvent, ...], bar: int, staff: int | None = None) -> list[NoteEvent]:
    return [
        note
        for note in notes
        if note.bar == bar and note.midi is not None and (staff is None or note.staff == staff)
    ]


def _silent(notes: tuple[NoteEvent, ...], bars: tuple[int, ...], staff: int | None = None) -> bool:
    return all(not _sounding(notes, bar, staff) for bar in bars)


def _assert_join(notes: tuple[NoteEvent, ...], left: int, right: int) -> None:
    before = _sounding(notes, left)
    after = [note for note in _sounding(notes, right) if note.beat == 0.0]
    if not before or not after:
        return
    same = before[-1].midi == after[0].midi
    assert before[-1].tie_start is same
    assert after[0].tie_stop is same


def _assert_cool_join(notes: tuple[NoteEvent, ...]) -> None:
    reaching = [
        note
        for note in _sounding(notes, 31)
        if note.beat + note.duration_beats >= 4 - 1e-6
    ]
    cool = [note for note in _sounding(notes, 32) if note.beat == 0.0]
    assert cool
    same = bool(reaching) and reaching[-1].midi == cool[0].midi
    assert cool[0].tie_stop is same
    if same:
        assert reaching[-1].tie_start


def _root(score, bar: int) -> int:
    slot = next(slot for slot in score.slots if slot.start <= bar < slot.start + slot.length)
    return slot.chord.pitches[0] % 12


def test_a_caller_form_stays_on_the_thirty_bar_grid() -> None:
    score = render(_day(), form=DAILY_SPEC)
    assert score.bars == 30
    assert score.low_wedges == ()


def test_symphony_frame_is_a_tonic_pedal_around_the_price() -> None:
    score = render(_day(), variant="symphony")
    assert (score.bars, score.bpm) == (36, 90)
    assert score.slots[0].section == "intro"
    assert next(slot for slot in score.slots if slot.start == 2).section == "phrase"
    assert _silent(score.lead, (0,))
    assert _silent(score.high, WARM + COOL)
    assert _silent(score.comp, WARM + COOL)
    intro = _root(score, 0)
    outro = _root(score, 32)
    violin = _sounding(score.lead, 1)
    assert len(violin) == 1
    assert violin[0].duration_beats == 4
    assert violin[0].midi % 12 == intro
    for bar in WARM:
        cello = _sounding(score.support, bar)
        bass = _sounding(score.low, bar)
        assert len(cello) == 1 and cello[0].duration_beats == 4 and cello[0].midi % 12 == intro
        assert len(bass) == 1 and bass[0].duration_beats == 4 and bass[0].midi == score.slots[0].chord.bass_midi
    assert score.support[0].tie_start and _sounding(score.support, 1)[0].tie_stop
    for bar in COOL:
        for part in (score.lead, score.support):
            notes = _sounding(part, bar)
            assert len(notes) == 1 and notes[0].duration_beats == 4 and notes[0].midi % 12 == outro
        bass = _sounding(score.low, bar)
        assert len(bass) == 1 and bass[0].duration_beats == 4
    assert any(note.midi is not None and note.bar == 2 for note in score.lead + score.support + score.high)
    _assert_join(score.lead, 1, 2)
    _assert_join(score.support, 1, 2)
    _assert_cool_join(score.lead)
    _assert_cool_join(score.support)
    assert {wedge.kind for wedge in score.low_wedges} == {"crescendo", "diminuendo", "stop"}
    assert (score.dynamics[-1].bar, score.dynamics[-1].marking) == (35, "ppp")
    assert score.lead_dynamics[-1].marking == "ppp"
    _measures_fill(score)


def test_jazz_frame_is_a_vamp_then_a_tag() -> None:
    score = render(_day(), variant="jazz")
    assert (score.bars, score.bpm) == (36, 82)
    assert _silent(score.lead, WARM)
    assert _silent(score.support, WARM)
    assert _silent(score.high, WARM + COOL)
    for bar in WARM:
        bass = _sounding(score.low, bar)
        assert [(note.beat, note.duration_beats) for note in bass] == [(0.0, 2.0), (2.0, 2.0)]
        assert all(note.velocity is None for note in score.comp if note.bar == bar)
    for bar in COOL:
        bass = _sounding(score.low, bar)
        assert len(bass) == 1 and bass[0].duration_beats == 4
        assert bass[0].tie_start is (bar < 35)
        assert bass[0].tie_stop is (bar > 32 or _sounding(score.low, 31) and _sounding(score.low, 31)[-1].tie_start)
    right = [note for note in score.comp if 32 <= note.bar <= 35 and note.staff == 1 and note.midi is not None]
    assert right
    assert all(note.duration_beats == 4 for note in right)
    assert any(note.tie_start for note in right if note.bar == 32)
    sax = [note for note in score.lead + score.support if note.bar in COOL and note.midi is not None]
    assert sax
    assert {note.midi % 12 for note in sax} == {_root(score, 32)}
    assert all(note.duration_beats == 4 for note in sax)
    assert (score.dynamics[-1].bar, score.dynamics[-1].marking) == (35, "ppp")
    walking = [note for note in score.low if 4 <= note.bar < 28 and note.duration_beats == 1]
    assert walking
    _measures_fill(score)


def test_minimalist_frame_opens_on_the_sub_and_closes_the_filter() -> None:
    score = render(_day(), variant="minimalist")
    assert (score.bars, score.bpm) == (36, 118)
    assert _silent(score.lead, WARM + COOL)
    assert _silent(score.high, WARM + COOL)
    assert _silent(score.comp, WARM + COOL)
    assert _silent(score.support, WARM + (34, 35))
    assert _sounding(score.support, 32) and _sounding(score.support, 33)
    assert _sounding(score.lead, 4)
    for bar in WARM + COOL:
        quarters = _sounding(score.low, bar)
        assert [note.beat for note in quarters] == [0.0, 1.0, 2.0, 3.0]
        assert len({note.midi for note in quarters}) == 1
    assert (score.dynamics[-1].bar, score.dynamics[-1].marking) == (35, "ppp")
    assert score.support_dynamics[-1].marking == "ppp"
    assert any(wedge.bar == 32 and wedge.kind == "diminuendo" for wedge in score.support_wedges)
    _measures_fill(score)
