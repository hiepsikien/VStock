"""Harmony recap: chord form, quantization, bass dynamics, MusicXML."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.sonify.chords import CMAJ7, G7
from app.sonify.dynamics import DYNAMICS, MARKINGS, SOUND, marking_for_volume
from app.sonify.form import plan_slots
from app.sonify.model import Bar
from app.sonify.musicxml import score_to_musicxml
from app.sonify.quantize import c_major_scale, price_to_scale_index, quantize
from app.sonify.regime import classify, moving_average
from app.sonify.render import assign_source_bars, render
from app.sonify.session import bars_from_ohlc, is_auction_minute, is_recap_minute, session_bars

VN = ZoneInfo("Asia/Ho_Chi_Minh")
_STEPS = ["C", "", "D", "", "E", "F", "", "G", "", "A", "", "B"]


def _pitch(midi: int) -> tuple[str, int]:
    step = _STEPS[midi % 12]
    assert step
    return step, midi // 12 - 1


def _xml(score):
    text = score_to_musicxml(score)
    root = ET.fromstring(text)
    return text, root


def _part(root: ET.Element, part_id: str) -> ET.Element:
    part = root.find(f"part[@id='{part_id}']")
    assert part is not None
    return part


def test_moving_average_waits_for_a_full_window() -> None:
    assert moving_average([1, 2, 3, 4], 3) == [None, None, 2.0, 3.0]


def test_regime_uses_a_deadband_around_ma20() -> None:
    ma = 100.0
    band = 0.0015
    assert classify(ma, ma) == "sideway"
    assert classify(ma * (1 + band), ma) == "sideway"
    assert classify(ma * (1 + band) + 0.01, ma) == "uptrend"
    assert classify(ma * (1 - band), ma) == "sideway"
    assert classify(ma * (1 - band) - 0.01, ma) == "downtrend"
    assert classify(ma, None) == "sideway"


def test_source_bars_stay_in_order() -> None:
    assert [index for group in assign_source_bars(60) for index in group] == list(range(60))
    assert all(len(group) == 2 for group in assign_source_bars(60))
    assert assign_source_bars(1)[0] == [0]
    assert assign_source_bars(30) == [[index] for index in range(30)]


def test_price_walks_the_scale_from_low_to_high() -> None:
    scale = c_major_scale()
    assert scale[0] == 60 and scale[-1] == 84
    assert price_to_scale_index(0, 0, 100, len(scale)) == 0
    assert price_to_scale_index(100, 0, 100, len(scale)) == len(scale) - 1
    assert price_to_scale_index(50, 50, 50, len(scale)) == len(scale) // 2
    indexes = [price_to_scale_index(value, 0, 100, len(scale)) for value in range(101)]
    assert indexes == sorted(indexes)


def test_quantize_keeps_chord_tones_and_breaks_ties() -> None:
    scale = c_major_scale()
    assert quantize(64, CMAJ7, scale, None) == 64
    assert quantize(62, CMAJ7, scale, None) == 60
    assert quantize(62, CMAJ7, scale, 64) == 64
    assert quantize(62, CMAJ7, scale, 62) == 60
    assert quantize(65, CMAJ7, scale, None) == 64
    assert quantize(60, G7, scale, None) == 62


def test_phrase_regime_uses_the_downbeat_window() -> None:
    closes = [80.0] * 30
    closes[2:7] = [120.0] * 5
    closes[18:23] = [100.0] * 5
    score = render([Bar(close, 1.0, 100.0) for close in closes], title="VNM")
    assert score.regimes == ("uptrend", "downtrend", "sideway")
    assert score.regime_samples == (2, 10, 18)
    assert [slot.chord.name for slot in score.slots] == [
        "Cmaj7",
        "Cmaj7",
        "Fmaj7",
        "Dm7",
        "G7",
        "Am7",
        "Fmaj7",
        "Dm7",
        "Em7",
        "Cmaj7",
        "Am7",
        "Cmaj7",
        "Am7",
        "Cmaj7",
    ]
    assert [(slot.start, slot.length) for slot in score.slots] == [
        (0, 2),
        (2, 2),
        (4, 2),
        (6, 2),
        (8, 2),
        (10, 2),
        (12, 2),
        (14, 2),
        (16, 2),
        (18, 2),
        (20, 2),
        (22, 2),
        (24, 2),
        (26, 4),
    ]
    by_bar = {
        bar: slot.chord
        for slot in score.slots
        for bar in range(slot.start, slot.start + slot.length)
    }
    assert [by_bar[bar].name for bar in range(2, 10)] == [
        "Cmaj7",
        "Cmaj7",
        "Fmaj7",
        "Fmaj7",
        "Dm7",
        "Dm7",
        "G7",
        "G7",
    ]
    for note in score.piano:
        assert note.midi % 12 in by_bar[note.bar].pitch_classes
    bass_roots = [36, 36, 41, 38, 43, 45, 41, 38, 40, 36, 45, 36, 45, 36]
    for slot, root in zip(score.slots, bass_roots):
        notes = [note for note in score.bass if note.bar in slot.bars()]
        assert [note.midi for note in notes] == [root] * slot.length
        assert [note.midi for note in score.pad if note.bar == slot.start] == list(slot.chord.pitches)


def test_one_minute_twitch_does_not_flip_the_phrase() -> None:
    ma = 100.0
    above = ma * (1 + 0.0015) + 0.01
    below = ma * (1 - 0.0015) - 0.01
    closes = [ma] * 30
    closes[2] = above
    closes[10] = below
    closes[18] = above
    score = render([Bar(close, 1.0, ma) for close in closes])
    assert score.regimes == ("sideway", "sideway", "sideway")


def test_flat_session_on_the_sideway_loop_holds_c() -> None:
    score = render([Bar(50.0, 1.0, 50.0)] * 30)
    assert score.regimes == ("sideway", "sideway", "sideway")
    assert {note.midi for note in score.piano} == {72}


def test_flat_uptrend_only_leaves_c_on_g7() -> None:
    score = render(
        [Bar(50.0, 1.0, 50.0)] * 30,
        regimes=("uptrend", "uptrend", "uptrend"),
    )
    g7_bars = {8, 9, 16, 17, 24, 25}
    for note in score.piano:
        assert note.midi == (71 if note.bar in g7_bars else 72)


def test_bass_dynamics_follow_slot_volume() -> None:
    volumes = [1.0] * 30
    for index in (0, 1, 26, 27, 28, 29):
        volumes[index] = 1000.0
    score = render(
        [Bar(100.0, volume, 100.0) for volume in volumes],
        regimes=("uptrend", "uptrend", "uptrend"),
    )
    markings = [event.marking for event in score.dynamics]
    assert markings[0] == "fff"
    assert markings[1] == "ppp"
    assert markings[-1] == "fff"
    assert all(marking in MARKINGS for marking in markings)
    assert score.bass[0].midi == 36
    for marking, _percent, velocity in DYNAMICS:
        assert round(SOUND[marking] / 100 * 90) == velocity


def test_musicxml_writes_harmony_and_letter_dynamics() -> None:
    closes = [80.0] * 30
    closes[2:7] = [120.0] * 5
    closes[18:23] = [100.0] * 5
    volumes = [1.0] * 30
    for index in (0, 1, 26, 27, 28, 29):
        volumes[index] = 1000.0
    score = render(
        [Bar(close, volume, 100.0) for close, volume in zip(closes, volumes)],
        title="VNM 1-Day Recap",
    )
    text, root = _xml(score)
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert root.tag == "score-partwise"
    assert root.get("version") == "4.0"
    assert root.find("work/work-title").text == "VNM 1-Day Recap"

    piano = _part(root, "P1")
    bass = _part(root, "P2")
    piano_measures = piano.findall("measure")
    bass_measures = bass.findall("measure")
    assert [measure.get("number") for measure in piano_measures] == [str(n) for n in range(1, 31)]
    assert len(bass_measures) == 30

    attributes = piano_measures[0].find("attributes")
    assert attributes.find("divisions").text == "2"
    assert attributes.find("key/fifths").text == "0"
    assert attributes.find("key/mode").text == "major"
    assert attributes.find("time/beats").text == "4"
    assert attributes.find("time/beat-type").text == "4"
    assert attributes.find("clef/sign").text == "G"
    assert bass_measures[0].find("attributes/clef/sign").text == "F"
    assert piano_measures[0].find("direction/sound").get("tempo") == "90"

    harmonies = piano.findall("measure/harmony")
    assert len(harmonies) == 14
    assert bass.findall("measure/harmony") == []
    assert piano_measures[0].find("harmony/root/root-step").text == "C"
    assert piano_measures[0].find("harmony/kind").text == "major-seventh"
    assert piano_measures[0].find("harmony/kind").get("text") == "maj7"
    assert piano_measures[1].find("harmony") is None
    assert piano_measures[8].find("harmony/root/root-step").text == "G"
    assert piano_measures[8].find("harmony/kind").text == "dominant"
    assert piano_measures[8].find("harmony/kind").get("text") == "7"
    assert piano_measures[10].find("harmony/root/root-step").text == "A"
    assert piano_measures[10].find("harmony/kind").text == "minor-seventh"
    assert piano_measures[10].find("harmony/kind").get("text") == "m7"

    for measure, event in zip(
        (piano_measures[slot.start] for slot in score.slots),
        score.harmonies,
    ):
        kind = measure.find("harmony/kind")
        assert kind.text == event.chord.kind
        assert kind.get("text") == event.chord.kind_text
        assert measure.find("harmony/root/root-step").text == event.chord.root_step

    assert piano.findall(".//dynamics") == []
    dynamic_marks = []
    for measure in bass_measures:
        for direction in measure.findall("direction"):
            dynamics = direction.find("direction-type/dynamics")
            children = [child.tag for child in dynamics]
            assert children == [children[0]]
            assert children[0] in MARKINGS
            assert direction.get("placement") == "below"
            assert direction.find("sound").get("dynamics") == str(SOUND[children[0]])
            dynamic_marks.append(children[0])
    assert dynamic_marks == _changed([event.marking for event in score.dynamics])
    assert dynamic_marks[0] == "fff"
    assert "ppp" in dynamic_marks
    assert len(dynamic_marks) < len(score.dynamics)

    _assert_measure_timing(piano_measures, bass_measures, score)


def _assert_measure_timing(piano_measures, bass_measures, score) -> None:
    for bar, (piano_measure, bass_measure) in enumerate(zip(piano_measures, bass_measures)):
        notes = [note for note in piano_measure if note.tag == "note"]
        melody = [note for note in notes if note.find("chord") is None and note.find("voice").text == "1"]
        voicing = [note for note in notes if note.find("voice").text == "2"]
        assert len(melody) == 8
        assert len(voicing) == 4
        assert sum(int(note.find("duration").text) for note in melody) == 8
        assert voicing[0].find("chord") is None
        assert all(note.find("chord") is not None for note in voicing[1:])
        assert sum(int(note.find("duration").text) for note in melody) == int(
            piano_measure.find("backup/duration").text
        )
        written = []
        for note in voicing:
            step = note.find("pitch/step").text
            octave = int(note.find("pitch/octave").text)
            written.append((step, octave))
        expected = [_pitch(midi) for midi in score.slots[_slot_index(score, bar)].chord.pitches]
        assert written == expected

        bass_notes = [note for note in bass_measure if note.tag == "note"]
        assert len(bass_notes) == 1
        assert bass_notes[0].find("chord") is None
        assert bass_notes[0].find("type").text == "whole"
        assert int(bass_notes[0].find("duration").text) == 8
        step = bass_notes[0].find("pitch/step").text
        octave = int(bass_notes[0].find("pitch/octave").text)
        assert (step, octave) == _pitch(score.bass[bar].midi)
        assert _tie_types(bass_notes[0]) == _expected_ties(score, bar)
        assert _tied_types(bass_notes[0]) == _expected_ties(score, bar)


def _changed(markings: list[str]) -> list[str]:
    kept: list[str] = []
    for marking in markings:
        if kept and kept[-1] == marking:
            continue
        kept.append(marking)
    return kept


def _slot_index(score, bar: int) -> int:
    for index, slot in enumerate(score.slots):
        if bar in slot.bars():
            return index
    raise AssertionError(bar)


def _tie_types(note: ET.Element) -> list[str]:
    return [tie.get("type") for tie in note.findall("tie")]


def _tied_types(note: ET.Element) -> list[str]:
    return [tied.get("type") for tied in note.findall("notations/tied")]


def _expected_ties(score, bar: int) -> list[str]:
    note = score.bass[bar]
    kinds = []
    if note.tie_stop:
        kinds.append("stop")
    if note.tie_start:
        kinds.append("start")
    return kinds


def test_outro_bass_is_tied_across_four_bars() -> None:
    score = render([Bar(100.0, 1.0, 100.0)] * 30, regimes=("downtrend",) * 3)
    _text, root = _xml(score)
    bass_measures = _part(root, "P2").findall("measure")
    assert _tie_types(bass_measures[26].find("note")) == ["start"]
    assert _tie_types(bass_measures[27].find("note")) == ["stop", "start"]
    assert _tie_types(bass_measures[28].find("note")) == ["stop", "start"]
    assert _tie_types(bass_measures[29].find("note")) == ["stop"]
    assert bass_measures[26].find("note/pitch/step").text == "A"
    assert bass_measures[26].find("note/pitch/octave").text == "2"
    assert bass_measures[26].find("harmony") is None
    assert _part(root, "P1").findall("measure")[26].find("harmony/kind").text == "minor-seventh"


def test_session_drops_lunch_and_warms_up_ma20() -> None:
    def stamp(day: int, hour: int, minute: int) -> int:
        return int(datetime(2024, 1, day, hour, minute, tzinfo=VN).timestamp())

    samples = [(stamp(12, 9, minute), 100.0, 1.0) for minute in range(25)]
    samples.extend(
        [
            (stamp(15, 8, 59), 999.0, 50.0),
            (stamp(15, 11, 29), 110.0, 2.0),
            (stamp(15, 11, 30), 999.0, 50.0),
            (stamp(15, 12, 15), 999.0, 50.0),
            (stamp(15, 13, 0), 120.0, 3.0),
            (stamp(15, 14, 45), 130.0, 4.0),
            (stamp(15, 14, 46), 777.0, 9.0),
            (stamp(15, 15, 0), 999.0, 50.0),
        ]
    )
    bars = session_bars(samples, date(2024, 1, 15))
    assert [bar.close for bar in bars] == [110.0, 120.0, 130.0]
    assert bars[0].ma20 == (19 * 100 + 110) / 20
    assert bars[1].ma20 == (18 * 100 + 110 + 120) / 20
    assert bars[2].volume == 4.0
    assert bars[2].auction is True
    assert bars[0].auction is False
    assert bars[1].auction is False

    payload = {
        "t": [row[0] for row in samples],
        "c": [row[1] for row in samples],
        "v": [row[2] for row in samples],
    }
    assert [bar.close for bar in bars_from_ohlc(payload, date(2024, 1, 15))] == [110.0, 120.0, 130.0]


def test_progressions_match_the_locked_loops() -> None:
    assert [slot.chord.name for slot in plan_slots(("uptrend",) * 3) if slot.section == "phrase"][:4] == [
        "Cmaj7",
        "Fmaj7",
        "Dm7",
        "G7",
    ]
    assert [slot.chord.name for slot in plan_slots(("downtrend",) * 3) if slot.section == "phrase"][:4] == [
        "Am7",
        "Fmaj7",
        "Dm7",
        "Em7",
    ]
    assert [slot.chord.name for slot in plan_slots(("sideway",) * 3) if slot.section == "phrase"][:4] == [
        "Cmaj7",
        "Am7",
        "Cmaj7",
        "Am7",
    ]


def test_render_rejects_an_empty_session() -> None:
    with pytest.raises(ValueError):
        render([])


def test_equal_volume_does_not_follow_how_many_candles_a_slot_holds() -> None:
    score = render([Bar(100.0, 100.0, 100.0)] * 227, regimes=("sideway",) * 3)
    assert {event.marking for event in score.dynamics} == {"mf"}


def test_small_volume_gap_stays_at_mf() -> None:
    assert marking_for_volume(150_000, 150_000, 160_000) == "mf"
    assert marking_for_volume(160_000, 150_000, 160_000) == "mf"


def test_auction_prints_do_not_pin_the_body_quiet() -> None:
    bars = [Bar(100.0, 100.0, 100.0) for _ in range(227)]
    bars[0] = Bar(100.0, 3_000.0, 100.0, auction=True)
    bars[-1] = Bar(100.0, 3_000.0, 100.0, auction=True)
    score = render(bars, regimes=("sideway",) * 3)
    assert {event.marking for event in score.dynamics} == {"mf"}


def test_unlabeled_spike_is_clipped_before_the_scale_opens() -> None:
    bars = [Bar(100.0, 100.0, 100.0) for _ in range(227)]
    bars[0] = Bar(100.0, 3_000.0, 100.0)
    bars[-1] = Bar(100.0, 3_000.0, 100.0)
    score = render(bars, regimes=("sideway",) * 3)
    assert {event.marking for event in score.dynamics} == {"mf"}


def test_repeated_dynamics_are_printed_once() -> None:
    score = render([Bar(100.0, 100.0, 100.0)] * 30, regimes=("sideway",) * 3)
    _text, root = _xml(score)
    marks = [
        child.tag
        for dynamics in _part(root, "P2").findall(".//dynamics")
        for child in dynamics
    ]
    assert marks == ["mf"]
    assert _part(root, "P1").findall(".//dynamics") == []


def test_short_volume_array_keeps_every_close() -> None:
    def stamp(minute: int) -> int:
        return int(datetime(2024, 1, 15, 13, minute, tzinfo=VN).timestamp())

    closes = [100.0 + index for index in range(10)]
    payload = {"t": [stamp(minute) for minute in range(10)], "c": closes, "v": [5.0, 6.0]}
    bars = bars_from_ohlc(payload, date(2024, 1, 15))
    assert [bar.close for bar in bars] == closes
    assert [bar.volume for bar in bars] == [5.0, 6.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_recap_stops_at_the_closing_auction() -> None:
    assert is_recap_minute(datetime(2024, 1, 15, 14, 45, tzinfo=VN))
    assert not is_recap_minute(datetime(2024, 1, 15, 14, 46, tzinfo=VN))
    assert is_auction_minute(datetime(2024, 1, 15, 9, 0, tzinfo=VN))
    assert is_auction_minute(datetime(2024, 1, 15, 9, 15, tzinfo=VN))
    assert not is_auction_minute(datetime(2024, 1, 15, 9, 16, tzinfo=VN))
    assert is_auction_minute(datetime(2024, 1, 15, 14, 30, tzinfo=VN))
    assert is_auction_minute(datetime(2024, 1, 15, 14, 45, tzinfo=VN))
    assert not is_auction_minute(datetime(2024, 1, 15, 13, 0, tzinfo=VN))
