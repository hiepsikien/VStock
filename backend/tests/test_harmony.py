"""Harmony recap: chord form, quantization, bass dynamics, MusicXML."""

from __future__ import annotations

import random
import xml.etree.ElementTree as ET
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.sonify.dynamics import DYNAMICS, MARKINGS, SOUND, marking_for_volume
from app.sonify.form import SECTION_STARTS, plan_slots
from app.sonify.model import Bar, WedgeEvent
from app.sonify.musicxml import BASS_WRITTEN_OCTAVES, score_to_musicxml
from app.sonify.phrasing import MAX_EIGHTHS, MIN_EIGHTHS, PERIOD, plan_phrases
from app.sonify.quantize import C_MAJOR_PCS, c_major_scale, price_to_scale_index, quantize_chord_tone
from app.sonify.regime import classify, moving_average
from app.sonify.chords import AM7, CMAJ7, DM7, EM7, FMAJ7, G7
from app.sonify.render import (
    STRONG_EIGHTHS,
    assign_source_bars,
    comp_pitches,
    fill_tones,
    flute_harmony_pitch,
    render,
)
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


def _sounding(score):
    notes = [note for note in score.violin + score.cello if note.midi is not None]
    return sorted(notes, key=lambda note: (note.bar, note.beat))


def _line(events, bar: int):
    return [note.midi for note in sorted(events, key=lambda note: note.beat) if note.bar == bar]


COMPING = {
    "Cmaj7": (48, (59, 64)),  # C3 | B3 E4
    "Fmaj7": (41, (57, 64)),  # F2 | A3 E4
    "G7": (43, (59, 65)),  # G2 | B3 F4
    "Am7": (45, (60, 67)),  # A2 | C4 G4
    "Dm7": (50, (60, 65)),  # D3 | C4 F4
    "Em7": (52, (62, 67)),  # E3 | D4 G4
}


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
    assert scale[0] == 48 and scale[-1] == 96
    assert len(scale) == 29
    assert price_to_scale_index(0, 0, 100, len(scale)) == 0
    assert price_to_scale_index(100, 0, 100, len(scale)) == len(scale) - 1
    assert price_to_scale_index(50, 50, 50, len(scale)) == len(scale) // 2
    indexes = [price_to_scale_index(value, 0, 100, len(scale)) for value in range(101)]
    assert indexes == sorted(indexes)


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
    for note in _sounding(score):
        assert note.midi % 12 in C_MAJOR_PCS
    bass_roots = [36, 36, 41, 38, 43, 45, 41, 38, 40, 36, 45, 36, 45, 36]
    for slot, root in zip(score.slots, bass_roots):
        for bar in slot.bars():
            line = _line(score.bass, bar)
            assert line[0] == root
            assert set(line) <= {root, root + 7, root + 12}
        bass_note, guide = COMPING[slot.chord.name]
        for offset, bar in enumerate(slot.bars()):
            right = [note for note in score.piano if note.bar == bar and note.staff == 1]
            left = [note for note in score.piano if note.bar == bar and note.staff == 2]
            assert [(note.beat, note.midi) for note in right[:2]] == [
                (0.0, guide[0]),
                (0.0, guide[1]),
            ]
            if not any(note.velocity for note in right):
                assert [(note.beat, note.midi, note.duration_beats) for note in right] == [
                    (0.0, guide[0], 2.0),
                    (0.0, guide[1], 2.0),
                    (2.0, None, 2.0),
                ]
            assert [(note.midi, note.duration_beats) for note in left] == [
                (bass_note if offset == 0 else None, 4.0)
            ]


def test_comping_keeps_third_and_seventh_close() -> None:
    for chord in (CMAJ7, FMAJ7, G7, AM7, DM7, EM7):
        root, guide = comp_pitches(chord)
        assert (root, guide) == COMPING[chord.name]
        assert 41 <= root <= 52
        assert all(57 <= midi <= 68 for midi in guide)
        third, seventh = chord.pitches[1] % 12, chord.pitches[3] % 12
        assert {midi % 12 for midi in guide} == {third, seventh}


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
    assert {note.midi for note in score.violin} == {72, None}
    assert [(phrase.start // 8, phrase.end // 8) for phrase in score.phrases] == [
        (0, 2),
        (2, 6),
        (6, 10),
        (10, 14),
        (14, 18),
        (18, 22),
        (22, 26),
        (26, 30),
    ]
    assert [phrase.held_over for phrase in score.phrases] == [False] + [True, False] * 3 + [False]
    breaths = {1, 9, 17, 25}
    for bar in (6, 14, 22):
        downbeat = next(note for note in score.violin if note.bar == bar)
        assert downbeat.tie_stop and not downbeat.accent
    for bar in range(30):
        line = [(note.midi, note.duration_beats) for note in score.violin if note.bar == bar]
        if bar in breaths:
            assert line == [(72, 2.0), (72, 1.5), (None, 0.5)]
        else:
            assert line == [(72, 4.0)]
    assert not any(note.slur_start or note.slur_stop or note.accent for note in score.violin)
    assert score.violin_wedges == ()
    assert {note.velocity for note in score.violin if note.midi is not None} == {64}
    assert {note.midi for note in score.cello} == {None}


def _indexed_session(first_bar: list[int], rest: int) -> list[Bar]:
    """240 closes equal to C3–C7 scale indexes, so one close is one eighth."""
    closes = [float(index) for index in first_bar] + [float(rest)] * (240 - len(first_bar))
    closes[-1] = 28.0
    closes[-2] = 0.0
    return [Bar(close, 1.0, close) for close in closes]


def test_repeated_pitches_merge_into_held_notes() -> None:
    score = render(_indexed_session([14, 14, 14], 16), regimes=("sideway",) * 3)
    first = [note for note in score.violin if note.bar == 0]
    assert [note.duration_beats for note in first] == [1.5, 0.5, 2.0]
    assert [note.midi for note in first] == [72, 76, 76]
    assert not first[0].tie_start
    assert first[1].tie_start and first[2].tie_stop and first[2].tie_start
    assert first[0].slur_start
    assert first[1].accent and not first[2].accent
    second = [note for note in score.violin if note.bar == 1]
    assert [(note.midi, note.duration_beats) for note in second] == [
        (76, 2.0),
        (76, 1.5),
        (None, 0.5),
    ]
    assert second[0].tie_stop and second[1].tie_stop and second[1].slur_stop


def test_cello_takes_the_line_below_g3_until_c4() -> None:
    score = render(_indexed_session([28, 9, 0, 5, 6, 5, 7, 9], 9), regimes=("sideway",) * 3)
    assert _line(score.violin, 0) == [84, 64, None, None, 60, 64]
    assert _line(score.cello, 0) == [None, 48, 57, 59, 57, None]
    cello = [note for note in score.cello if note.midi is not None and note.bar == 0]
    assert cello[0].slur_start and cello[-1].slur_stop
    for part in (score.violin, score.cello, score.flute):
        for bar in range(30):
            assert sum(note.duration_beats for note in part if note.bar == bar) == 4.0
    assert all(55 <= note.midi <= 84 for note in score.violin if note.midi is not None)


def test_melody_snaps_strong_beats_to_chord_tones_and_keeps_weak_beat_passing_notes() -> None:
    scale = c_major_scale()
    assert quantize_chord_tone(64, CMAJ7.pitch_classes, scale) == 64
    assert quantize_chord_tone(62, AM7.pitch_classes, scale) == 60
    assert quantize_chord_tone(62, AM7.pitch_classes, scale, previous=60) == 64
    assert quantize_chord_tone(62, CMAJ7.pitch_classes, scale, step=2) == 64
    assert quantize_chord_tone(62, CMAJ7.pitch_classes, scale, step=-2) == 60
    assert quantize_chord_tone(65, AM7.pitch_classes, scale) == 64
    assert quantize_chord_tone(71, AM7.pitch_classes, scale) == 72

    score = render(
        [Bar(50.0, 1.0, 50.0)] * 30,
        regimes=("uptrend", "uptrend", "uptrend"),
    )
    g7_bars = {8, 9, 16, 17, 24, 25}
    for note in _sounding(score):
        assert note.midi == (71 if note.bar in g7_bars else 72)

    # On bar 0 (Cmaj7), strong beats (eighths 0 and 4) snap D4 (62) and F4 (65) to chord tones,
    # while weak-beat runs keep D4 (62), F4 (65), and A4 (69) as passing tones.
    passing = _indexed_session([8, 10, 9, 8, 10, 12, 11, 12], 7)
    score = render(passing, regimes=("sideway",) * 3)
    assert _line(score.violin, 0) == [60, 65, 64, 62, 67, 69, 67, 69]

    # When a strong-beat F4 (index 10) after G4 (index 11) at eighth 20 snaps down to E4 (64)
    # and is followed by a weak-beat E4 (index 9) at eighth 21, the two eighths stay two
    # separate attacks rather than merging into a fake held note; a genuine held note across
    # Cmaj7 -> Am7 (30..36) stays one note on G4 (67), shared by both chords.
    no_fake_merge = _session({19: (1, 11), 20: (1, 10), 21: (1, 9), 30: (6, 10)})
    score = render(no_fake_merge, regimes=("sideway",) * 3)
    bar_two = [
        (note.beat, note.midi, note.duration_beats, note.tie_start, note.tie_stop)
        for note in score.violin
        if note.bar == 2 and note.beat in (2.0, 2.5)
    ]
    assert bar_two == [(2.0, 64, 0.5, False, False), (2.5, 64, 0.5, False, False)]
    cross_chord = [
        (note.bar, note.beat, note.midi, note.duration_beats, note.tie_start, note.tie_stop)
        for note in score.violin
        if (note.bar == 3 and note.beat == 3.0) or (note.bar == 4 and note.beat == 0.0)
    ]
    assert cross_chord == [
        (3, 3.0, 67, 1.0, True, False),
        (4, 0.0, 67, 1.5, False, True),
    ]
    assert 67 % 12 in CMAJ7.pitch_classes & AM7.pitch_classes

    # When a held note on A4 (index 12, midi 69) spans Dm7 -> Em7 (bars 7..8 in downtrend),
    # the only shared chord tone D is four scale steps away, so each chord snaps within one step
    # (A4=69 on Dm7, B4=71 on Em7) rather than pulling the note down a fifth to D4.
    far_shared = _session({60: (8, 12)})
    score = render(far_shared, regimes=("downtrend",) * 3)
    assert [
        (note.bar, note.beat, note.midi)
        for note in score.violin
        if (note.bar == 7 and note.beat == 2.0) or (note.bar == 8 and note.beat == 0.0)
    ] == [(7, 2.0, 69), (8, 0.0, 71)]


def test_bass_dynamics_follow_slot_volume() -> None:
    volumes = [1.0] * 30
    for index in (0, 1, 26, 27, 28, 29):
        volumes[index] = 1000.0
    score = render(
        [Bar(100.0, volume, 100.0) for volume in volumes],
        regimes=("uptrend", "uptrend", "uptrend"),
    )
    assert MARKINGS == ("p", "mp", "mf", "f")
    assert score.liquidity[0] == "f"
    assert score.liquidity[1] == "p"
    assert score.liquidity[-1] == "f"
    markings = [event.marking for event in score.dynamics]
    assert markings[0] == "mp"
    assert markings[1] == "p"
    assert markings[-1] == "mp"
    assert {event.sound for event in score.dynamics} <= {SOUND["p"], SOUND["mp"]}
    assert score.bass[0].midi == 36
    for marking, _percent, velocity in DYNAMICS:
        assert round(SOUND[marking] / 100 * 90) == velocity


def _markings(volumes: list[float]) -> list[str]:
    score = render([Bar(100.0, volume, 100.0) for volume in volumes], regimes=("sideway",) * 3)
    assert score.regime_samples is None
    return list(score.liquidity)


def test_untraded_tail_does_not_push_the_session_to_f() -> None:
    ramp = [50_000 + 100_000 * index / 29 for index in range(30)]
    assert _markings(ramp) == ["p"] * 4 + ["mp"] * 2 + ["mf"] * 3 + ["f"] * 5

    wide = [20_000 + 180_000 * index / 21 for index in range(22)]
    with_tail = _markings(wide + [0.0] * 8)
    assert with_tail[-3:] == ["p"] * 3
    assert with_tail[:11] == sorted(with_tail[:11], key=MARKINGS.index)
    assert set(with_tail[:11]) == {"p", "mp", "mf", "f"}

    steady = [60_000.0, 180_000.0] * 11 + [0.0] * 8
    assert _markings(steady)[:11] == ["mf"] * 11


def test_session_without_any_volume_stays_neutral() -> None:
    assert set(_markings([0.0] * 30)) == {"mf"}


def test_nan_close_is_dropped_not_clamped_to_c3() -> None:
    def stamp(minute: int) -> int:
        return int(datetime(2024, 1, 15, 10, minute, tzinfo=VN).timestamp())

    payload = {
        "t": [stamp(minute) for minute in range(4)],
        "c": [100.0, "nan", float("inf"), 101.0],
        "v": [1.0, 1.0, "nan", 2.0],
    }
    bars = bars_from_ohlc(payload, date(2024, 1, 15))
    assert [bar.close for bar in bars] == [100.0, 101.0]
    samples = [(stamp(0), 100.0, float("nan")), (stamp(1), float("nan"), 1.0)]
    assert [(bar.close, bar.volume) for bar in session_bars(samples, date(2024, 1, 15))] == [
        (100.0, 0.0)
    ]


def test_bass_attacks_more_often_as_volume_rises() -> None:
    volumes = [1.0] * 30
    for index in (0, 1, 26, 27, 28, 29):
        volumes[index] = 1000.0
    score = render(
        [Bar(100.0, volume, 100.0) for volume in volumes],
        regimes=("uptrend", "uptrend", "uptrend"),
    )
    assert _line(score.bass, 0) == [36, 36, 48, 36, 43, 43, 48, 43]
    assert _line(score.bass, 2) == [36]
    assert _line(score.bass, 29) == [36, 36, 48, 36, 43, 43, 48, 43]

    steady = render([Bar(100.0, 100.0, 100.0)] * 30, regimes=("sideway",) * 3)
    assert set(steady.liquidity) == {"mf"}
    assert {event.marking for event in steady.dynamics} == {"mp"}
    assert _line(steady.bass, 10) == [36, 43, 48, 43]
    assert _line(steady.bass, 12) == [45, 52, 57, 52]
    for bar in range(30):
        assert sum(note.duration_beats for note in steady.bass if note.bar == bar) == 4.0
    assert not any(note.tie_start or note.tie_stop for note in steady.bass)


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

    names = [part.find("part-name").text for part in root.findall("part-list/score-part")]
    assert names == ["Violin", "Cello", "Piano", "Bass", "Flute"]
    programs = root.findall("part-list/score-part/midi-instrument/midi-program")
    assert [program.text for program in programs] == ["41", "43", "1", "34", "74"]

    violin = _part(root, "P1")
    cello = _part(root, "P2")
    piano = _part(root, "P3")
    bass = _part(root, "P4")
    flute = _part(root, "P5")
    violin_measures = violin.findall("measure")
    cello_measures = cello.findall("measure")
    piano_measures = piano.findall("measure")
    bass_measures = bass.findall("measure")
    flute_measures = flute.findall("measure")
    assert [measure.get("number") for measure in violin_measures] == [str(n) for n in range(1, 31)]
    assert len(cello_measures) == 30
    assert len(piano_measures) == 30
    assert len(bass_measures) == 30
    assert len(flute_measures) == 30
    assert cello_measures[0].find("attributes/clef/sign").text == "F"
    piano_attributes = piano_measures[0].find("attributes")
    assert piano_attributes.find("staves").text == "2"
    assert [
        (clef.get("number"), clef.find("sign").text) for clef in piano_attributes.findall("clef")
    ] == [("1", "G"), ("2", "F")]

    attributes = violin_measures[0].find("attributes")
    assert attributes.find("divisions").text == "2"
    assert attributes.find("key/fifths").text == "0"
    assert attributes.find("key/mode").text == "major"
    assert attributes.find("time/beats").text == "4"
    assert attributes.find("time/beat-type").text == "4"
    assert attributes.find("clef/sign").text == "G"
    assert bass_measures[0].find("attributes/clef/sign").text == "F"
    assert violin_measures[0].find("direction/sound").get("tempo") == "90"

    harmonies = violin.findall("measure/harmony")
    assert len(harmonies) == 14
    assert bass.findall("measure/harmony") == []
    assert violin_measures[0].find("harmony/root/root-step").text == "C"
    assert violin_measures[0].find("harmony/kind").text == "major-seventh"
    assert violin_measures[0].find("harmony/kind").get("text") == "maj7"
    assert violin_measures[1].find("harmony") is None
    assert violin_measures[8].find("harmony/root/root-step").text == "G"
    assert violin_measures[8].find("harmony/kind").text == "dominant"
    assert violin_measures[8].find("harmony/kind").get("text") == "7"
    assert violin_measures[10].find("harmony/root/root-step").text == "A"
    assert violin_measures[10].find("harmony/kind").text == "minor-seventh"
    assert violin_measures[10].find("harmony/kind").get("text") == "m7"

    for measure, event in zip(
        (violin_measures[slot.start] for slot in score.slots),
        score.harmonies,
    ):
        kind = measure.find("harmony/kind")
        assert kind.text == event.chord.kind
        assert kind.get("text") == event.chord.kind_text
        assert measure.find("harmony/root/root-step").text == event.chord.root_step

    for part in (violin, cello):
        dynamics = part.findall(".//dynamics")
        assert {child.tag for marks in dynamics for child in marks} == {"mp"}
        assert part.find("measure/direction/direction-type/dynamics") is not None
    assert [child.tag for child in piano.find(".//dynamics")] == ["p"]
    assert len(piano.findall(".//dynamics")) == 1
    for part in (cello, piano):
        assert part.findall("measure/harmony") == []
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
    assert dynamic_marks[0] == "mp"
    assert not {"mf", "f"} & set(dynamic_marks)
    assert "p" in dynamic_marks
    assert len(dynamic_marks) < len(score.dynamics)

    _assert_measure_timing(
        violin_measures, cello_measures, piano_measures, bass_measures, flute_measures, score
    )


def _written(notes: list[ET.Element]) -> list[tuple[str, int]]:
    return [
        (note.find("pitch/step").text, int(note.find("pitch/octave").text))
        for note in notes
        if note.find("rest") is None
    ]


def _assert_measure_timing(
    violin_measures, cello_measures, piano_measures, bass_measures, flute_measures, score
) -> None:
    for bar, (violin_measure, cello_measure, piano_measure, bass_measure, flute_measure) in enumerate(
        zip(violin_measures, cello_measures, piano_measures, bass_measures, flute_measures)
    ):
        for measure in (violin_measure, cello_measure, flute_measure):
            melody = [
                note for note in measure if note.tag == "note" and note.find("grace") is None
            ]
            assert melody
            assert all(note.find("chord") is None for note in melody)
            assert sum(int(note.find("duration").text) for note in melody) == 8
            assert measure.find("backup") is None

        assert piano_measure.find("backup/duration").text == "8"
        hands = [note for note in piano_measure if note.tag == "note"]
        right = [note for note in hands if note.find("staff").text == "1"]
        left = [note for note in hands if note.find("staff").text == "2"]
        assert len(right) + len(left) == len(hands)
        for hand in (right, left):
            attacks = [note for note in hand if note.find("chord") is None]
            assert sum(int(note.find("duration").text) for note in attacks) == 8
        slot = score.slots[_slot_index(score, bar)]
        root, guide = COMPING[slot.chord.name]
        assert _written(right[:2]) == [_pitch(midi) for midi in guide]
        assert right[1].find("chord") is not None
        assert all(note.get("dynamics") is None for note in right[:2])
        for note in right[2:]:
            if note.find("rest") is None:
                assert note.get("dynamics") == f"{64 * 100 / 90:.2f}"
        assert _written(left) == ([_pitch(root)] if bar == slot.start else [])

        bass_notes = [note for note in bass_measure if note.tag == "note"]
        assert all(note.find("chord") is None for note in bass_notes)
        assert sum(int(note.find("duration").text) for note in bass_notes) == 8
        assert _written(bass_notes) == [
            _pitch(midi + 12 * BASS_WRITTEN_OCTAVES) for midi in _line(score.bass, bar)
        ]


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


def test_outro_bass_restarts_the_root_every_bar() -> None:
    score = render([Bar(100.0, 1.0, 100.0)] * 30, regimes=("downtrend",) * 3)
    _text, root = _xml(score)
    bass_measures = _part(root, "P4").findall("measure")
    for measure in bass_measures[26:]:
        assert measure.find("note/tie") is None
        assert measure.find("note/pitch/step").text == "A"
    assert bass_measures[26].find("note/pitch/step").text == "A"
    assert bass_measures[26].find("note/pitch/octave").text == str(2 + BASS_WRITTEN_OCTAVES)
    transpose = bass_measures[0].find("attributes/transpose")
    assert transpose.find("chromatic").text == "0"
    assert transpose.find("octave-change").text == str(-BASS_WRITTEN_OCTAVES)
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
    assert set(score.liquidity) == {"mf"}


def test_small_volume_gap_stays_at_mf() -> None:
    assert marking_for_volume(150_000, 150_000, 160_000) == "mf"
    assert marking_for_volume(160_000, 150_000, 160_000) == "mf"


def test_auction_prints_do_not_pin_the_body_quiet() -> None:
    bars = [Bar(100.0, 100.0, 100.0) for _ in range(227)]
    bars[0] = Bar(100.0, 3_000.0, 100.0, auction=True)
    bars[-1] = Bar(100.0, 3_000.0, 100.0, auction=True)
    score = render(bars, regimes=("sideway",) * 3)
    assert set(score.liquidity) == {"mf"}


def test_unlabeled_spike_is_clipped_before_the_scale_opens() -> None:
    bars = [Bar(100.0, 100.0, 100.0) for _ in range(227)]
    bars[0] = Bar(100.0, 3_000.0, 100.0)
    bars[-1] = Bar(100.0, 3_000.0, 100.0)
    score = render(bars, regimes=("sideway",) * 3)
    assert set(score.liquidity) == {"mf"}


def test_repeated_dynamics_are_printed_once() -> None:
    score = render([Bar(100.0, 100.0, 100.0)] * 30, regimes=("sideway",) * 3)
    _text, root = _xml(score)
    marks = [
        child.tag
        for dynamics in _part(root, "P4").findall(".//dynamics")
        for child in dynamics
    ]
    assert marks == ["mp"]
    for part_id in ("P1", "P2"):
        melody = _part(root, part_id).findall(".//dynamics")
        assert [child.tag for marks in melody for child in marks] == ["mp"]


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


def _alternating(count: int) -> list[int]:
    return [60 + 2 * (index % 2) for index in range(count)]


def test_phrase_ends_on_the_first_held_note_after_one_bar() -> None:
    pitches = (
        _alternating(3) + [64] * 4 + _alternating(13) + [67] * 5
        + _alternating(15) + [65] * 4 + _alternating(20)
    )
    phrases = plan_phrases(pitches, (0,))
    assert [(phrase.start, phrase.end) for phrase in phrases] == [(0, 25), (25, 44), (44, 64)]
    assert [phrase.closes for phrase in phrases] == [True, True, False]
    assert phrases[0].cadence.midi == 67


def test_phrase_without_a_held_note_cuts_after_a_comma_then_at_four_bars() -> None:
    pitches = _alternating(18) + [65] * 3 + _alternating(27)
    assert [(p.start, p.end) for p in plan_phrases(pitches, (0,))] == [(0, 21), (21, 48)]
    assert [(p.start, p.end) for p in plan_phrases(_alternating(48), (0,))] == [(0, 32), (32, 48)]
    assert [(p.start, p.end) for p in plan_phrases([60] * 40, (24,))] == [(0, 24), (24, 40)]


def test_phrase_carries_across_section_bar_line_to_settle_before_a_leap() -> None:
    # A phrase ending right at section boundary 16 on a repeated eighth E5 -> D5 (2 eighths)
    # followed by a wide leap up to B5 settles after D5 at eighth 19, then closes on E5 at 34.
    before = [76, 76, 74, 74, 74, 74, 76, 76, 74, 74, 76, 81, 79, 77, 81, 76]
    after = [76, 74, 74, 83, 83, 76, 76, 74, 76, 76, 76, 83, 83, 81, 76, 76, 76, 76, 74] + [76] * 6 + _alternating(16)
    phrases = plan_phrases(before + after, (16,))
    assert [(p.start, p.end) for p in phrases] == [(0, 19), (19, 34), (34, 57)]
    assert [(r.midi, r.length) for r in phrases[0].runs[-2:]] == [(76, 2), (74, 2)]
    assert phrases[1].runs[0].midi == 83
    assert phrases[1].closes and phrases[1].cadence.midi == 76


def test_note_crossing_section_boundary_can_close_the_next_phrase() -> None:
    # A long note starting at 12 and running to 26 crosses section start 16:
    # 12..16 (4 eighths) closes the first phrase at 16, and 16..26 (10 eighths)
    # is counted from the section downbeat 16 and closes the second phrase at 26.
    pitches = _alternating(12) + [67] * 14 + _alternating(22)
    phrases = plan_phrases(pitches, (16,))
    assert [(p.start, p.end, p.closes, p.held_over) for p in phrases] == [
        (0, 16, True, False),
        (16, 26, True, False),
        (26, 48, False, False),
    ]


def _walk(seed: int) -> list[float]:
    rng = random.Random(seed)
    index = 14
    closes: list[float] = []
    for _ in range(240):
        if rng.random() > 0.35:
            index = min(28, max(0, index + rng.choice((-2, -1, 1, 2))))
        closes.append(float(index))
    closes[0], closes[-1] = 0.0, 28.0
    return closes


def _balanced(kinds: list[str]) -> bool:
    open_ = False
    for kind in kinds:
        if (kind == "stop") != open_:
            return False
        open_ = not open_
    return not open_


def test_phrases_stay_one_to_four_bars_and_settle_near_sections() -> None:
    for seed in range(20):
        closes = _walk(seed)
        score = render([Bar(close, 1.0, close) for close in closes])
        sections = [start * 8 for start in SECTION_STARTS] + [240]
        assert score.phrases[0].start == 0 and score.phrases[-1].end == 240
        for phrase, following in zip(score.phrases, score.phrases[1:]):
            assert phrase.end == following.start
            raw_same = closes[phrase.end] == closes[phrase.end - 1]
            same_note = following.runs[0].midi == phrase.cadence.midi
            assert phrase.held_over == (phrase.end not in sections and raw_same and same_note)
            assert not (phrase.held_over and phrase.closes)
        for part in (score.violin, score.cello, score.flute):
            for note, following in zip(part, part[1:]):
                assert note.tie_start == following.tie_stop
                if note.tie_start:
                    assert following.midi == note.midi
        for phrase in score.phrases:
            assert MIN_EIGHTHS <= phrase.end - phrase.start <= MAX_EIGHTHS
            assert not any(phrase.start < edge < phrase.end - PERIOD for edge in sections)
        chord_at = {bar: slot.chord for slot in score.slots for bar in slot.bars()}
        for note in score.violin + score.cello:
            if note.midi is None:
                continue
            start_eighth = note.bar * 8 + int(note.beat * 2)
            end_eighth = start_eighth + int(note.duration_beats * 2)
            for eighth in range(start_eighth, end_eighth):
                if eighth % 8 in STRONG_EIGHTHS:
                    assert note.midi % 12 in chord_at[note.bar].pitch_classes
        accents = [note for note in score.violin + score.cello if note.accent]
        assert len(accents) <= len(score.phrases)
        for wedges in (score.violin_wedges, score.cello_wedges):
            assert _balanced([wedge.kind for wedge in wedges])


def _session(spans: dict[int, int], volumes: list[float] | None = None) -> list[Bar]:
    """240 scale indexes: C4/D4 alternating, with spans of held indexes laid over it."""
    indexes = [7 + eighth % 2 for eighth in range(240)]
    for start, (length, index) in spans.items():
        indexes[start : start + length] = [index] * length
    indexes[-2], indexes[-1] = 0, 28
    volumes = volumes or [1.0] * 240
    return [Bar(float(index), volume, float(index)) for index, volume in zip(indexes, volumes)]


def test_held_note_ties_across_a_chord_change_and_breathes() -> None:
    score = render(_session({30: (6, 16)}), regimes=("sideway",) * 3)
    phrase = next(phrase for phrase in score.phrases if phrase.start == 16)
    assert (phrase.end, phrase.closes) == (36, True)
    held = [note for note in score.violin if note.midi == 76]
    assert [
        (note.bar, note.beat, note.duration_beats, note.tie_start, note.tie_stop) for note in held
    ] == [(3, 3.0, 1.0, True, False), (4, 0.0, 1.5, False, True)]
    assert held[0].accent and not held[1].accent
    assert held[1].slur_stop
    breath = next(note for note in score.violin if note.bar == 4 and note.beat == 1.5)
    assert (breath.midi, breath.duration_beats) == (None, 0.5)


def test_piano_answers_a_held_cadence_under_the_violin() -> None:
    score = render(_session({30: (6, 16)}), regimes=("sideway",) * 3)
    right = [note for note in score.piano if note.bar == 4 and note.staff == 1]
    assert [(note.beat, note.midi, note.duration_beats, note.velocity) for note in right] == [
        (0.0, 60, 0.5, None),
        (0.0, 67, 0.5, None),
        (0.5, 64, 0.5, 64),
        (1.0, 67, 0.5, 64),
        (1.5, 69, 0.5, 64),
        (2.0, None, 2.0, None),
    ]
    assert fill_tones(AM7, 76, "violin") == [64, 67, 69, 72]
    assert fill_tones(AM7, 50, "cello") == [60, 64, 67, 69]
    assert fill_tones(AM7, 59, "cello") == [64, 67, 69, 72]
    assert len(fill_tones(AM7, 59, "violin")) < 3


def test_fills_stay_in_the_cadence_tail_on_chord_tones() -> None:
    found = 0
    for seed in range(20):
        score = render([Bar(close, 1.0, close) for close in _walk(seed)])
        chord_at = {bar: slot.chord for slot in score.slots for bar in slot.bars()}
        tails = {
            eighth: phrase.cadence
            for phrase in score.phrases
            if phrase.closes
            for eighth in range(max(phrase.cadence.start + 2, phrase.cadence.end - 6), phrase.cadence.end)
        }
        violin_onsets = {
            (note.bar * 8 + int(note.beat * 2), note.midi) for note in score.violin if note.midi
        }
        cello_onsets = {
            (note.bar * 8 + int(note.beat * 2), note.midi) for note in score.cello if note.midi
        }
        for note in score.piano:
            if note.velocity is None:
                continue
            found += 1
            onset = note.bar * 8 + int(note.beat * 2)
            assert onset % 8 and onset in tails
            assert note.midi % 12 in {pitch % 12 for pitch in chord_at[note.bar].pitches}
            assert 55 <= note.midi <= 79
            cadence = tails[onset]
            if (cadence.start, cadence.midi) in violin_onsets:
                assert note.midi <= cadence.midi - 3
            if (cadence.start, cadence.midi) in cello_onsets:
                assert note.midi >= cadence.midi + 3
    assert found


def test_phrase_swells_to_its_apex_and_writes_hairpins() -> None:
    rising = {16 + step: (1, 7 + step) for step in range(8)}
    falling = {24 + step: (1, 13 - step) for step in range(6)}
    score = render(_session({**rising, **falling, 30: (6, 5)}), regimes=("sideway",) * 3)
    phrase = next(phrase for phrase in score.phrases if phrase.start == 16)
    assert (phrase.end, phrase.apex.start, phrase.apex.midi) == (36, 23, 72)
    attacks = {
        note.bar * 8 + int(note.beat * 2): note.velocity
        for note in score.violin
        if note.midi is not None and not note.tie_stop
    }
    assert attacks[16] == 64
    assert attacks[23] == 88
    assert [attacks[eighth] for eighth in range(16, 24)] == sorted(attacks[e] for e in range(16, 24))
    assert attacks[30] == 75 + 8
    assert list(score.violin_wedges[:4]) == [
        WedgeEvent(2, 0.0, "crescendo"),
        WedgeEvent(2, 3.5, "stop"),
        WedgeEvent(2, 3.5, "diminuendo"),
        WedgeEvent(4, 1.5, "stop"),
    ]

    _text, root = _xml(score)
    violin = _part(root, "P1")
    kinds = [wedge.get("type") for wedge in violin.iter("wedge")]
    assert kinds == [wedge.kind for wedge in score.violin_wedges]
    assert _balanced(kinds)
    bar_three = violin.findall("measure")[2]
    sequence = [
        child.find("direction-type/wedge").get("type") if child.tag == "direction" else "note"
        for child in bar_three
        if child.tag == "note" or child.find("direction-type/wedge") is not None
    ]
    assert sequence[:2] == ["crescendo", "note"]
    assert sequence[-3:] == ["stop", "diminuendo", "note"]
    sounding = [note for note in violin.iter("note") if note.find("rest") is None]
    assert all(note.get("dynamics") for note in sounding)
    assert len(violin.findall(".//accent")) == sum(note.accent for note in score.violin)


def test_unbalanced_hairpins_are_reset_so_the_melody_does_not_fade() -> None:
    """MuseScore moves one step per hairpin without a target and keeps it there."""
    resets = 0
    for seed in range(20):
        score = render([Bar(close, 1.0, close) for close in _walk(seed)])
        for notes, wedges, dynamics, part_id in (
            (score.violin, score.violin_wedges, score.violin_dynamics, "P1"),
            (score.cello, score.cello_wedges, score.cello_dynamics, "P2"),
        ):
            onsets = {
                note.bar * 8 + int(note.beat * 2)
                for note in notes
                if note.midi is not None and not note.tie_stop
            }
            for letter in dynamics:
                assert letter.marking == "mp"
                assert letter.bar * 8 + int(letter.beat * 2) in onsets
            resets += len(dynamics)
            timeline = sorted(
                [(w.bar * 8 + w.beat * 2, 0 if w.kind == "stop" else 2, w.kind) for w in wedges]
                + [(d.bar * 8 + d.beat * 2, 1, "reset") for d in dynamics]
            )
            level = 0
            for _position, _order, kind in timeline:
                if kind == "reset":
                    level = 0
                elif kind == "crescendo":
                    assert level == 0
                    level += 1
                elif kind == "diminuendo":
                    assert level in (0, 1)
                    level -= 1
            _text, root = _xml(score)
            printed = _part(root, part_id).findall(".//dynamics")
            assert len(printed) == 1 + len(dynamics)
    assert resets


def test_reset_after_a_held_over_note_waits_for_the_next_attack() -> None:
    spans = {16 + step: (1, 16 - step) for step in range(7)}
    spans[23] = (33, 9)
    score = render(_session(spans), regimes=("sideway",) * 3)
    assert [(p.start, p.end, p.held_over) for p in score.phrases[1:3]] == [
        (16, 48, True),
        (48, 80, False),
    ]
    tied = next(note for note in score.violin if note.bar == 6)
    assert (tied.midi, tied.duration_beats, tied.tie_stop) == (64, 4.0, True)
    assert (score.violin_dynamics[0].bar, score.violin_dynamics[0].beat) == (7, 0.0)
    assert [(w.bar, w.beat, w.kind) for w in score.violin_wedges[:4]] == [
        (2, 0.0, "diminuendo"),
        (5, 4.0, "stop"),
        (7, 0.0, "diminuendo"),
        (9, 4.0, "stop"),
    ]


def test_heavy_volume_stall_after_a_fall_is_a_tremolo() -> None:
    ramp = [50_000 + 100_000 * index / 239 for index in range(240)]
    score = render(_session({36: (6, 5), 196: (6, 5)}, ramp), regimes=("sideway",) * 3)
    band_at = {bar: band for slot, band in zip(score.slots, score.liquidity) for bar in slot.bars()}
    assert band_at[4] == "p" and band_at[24] == "f"
    held = [note for note in score.violin if note.midi == 57]
    assert [(note.bar, note.beat, note.tremolo) for note in held] == [
        (4, 2.0, False),
        (5, 0.0, False),
        (24, 2.0, True),
        (25, 0.0, True),
    ]
    assert {note.bar for note in score.violin if note.tremolo} == {24, 25}

    _text, root = _xml(score)
    tremolos = _part(root, "P1").findall(".//ornaments/tremolo")
    assert [(mark.get("type"), mark.text) for mark in tremolos] == [("single", "3")] * 2


def test_breakout_above_four_bars_is_accented_and_held_tenuto() -> None:
    spans = {47: (1, 9), 48: (1, 11), 49: (1, 12), 50: (5, 13)}
    score = render(_session(spans), regimes=("sideway",) * 3)
    phrase = next(phrase for phrase in score.phrases if phrase.start <= 50 < phrase.end)
    held = [note for note in score.violin if note.midi == 71]
    assert held[0].accent and held[0].tenuto
    assert not any(note.accent or note.tenuto for note in held[1:])
    accents = [
        note
        for note in score.violin
        if note.accent and phrase.start <= note.bar * 8 + note.beat * 2 < phrase.end
    ]
    assert accents == [held[0]]

    _text, root = _xml(score)
    marks = [
        [child.tag for child in articulations]
        for articulations in _part(root, "P1").iter("articulations")
        if articulations.find("tenuto") is not None
    ]
    assert marks == [["accent", "tenuto"]]


def test_held_notes_take_at_most_one_colour() -> None:
    for seed in range(20):
        volumes = [50_000 + 100_000 * ((index * 37) % 240) / 239 for index in range(240)]
        bars = [Bar(close, volume, close) for close, volume in zip(_walk(seed), volumes)]
        score = render(bars)
        for part in (score.violin, score.cello):
            for note in part:
                assert note.tremolo + note.tenuto <= 1
                assert not (note.tenuto and not note.accent)
                assert not (note.tremolo and note.accent)
        for phrase in score.phrases:
            inside = [
                note
                for note in score.violin + score.cello
                if phrase.start <= note.bar * 8 + note.beat * 2 < phrase.end
            ]
            assert sum(note.accent for note in inside) <= 1


def test_one_accent_per_phrase_on_its_longest_syncopation() -> None:
    score = render(
        _session({22: (3, 12), 27: (3, 9), 32: (4, 9)}),
        regimes=("downtrend",) * 3,
    )
    phrase = next(phrase for phrase in score.phrases if phrase.start == 16)
    assert phrase.end == 36
    accented = [
        (note.bar, note.beat, note.midi)
        for note in score.violin
        if note.accent and 16 <= note.bar * 8 + note.beat * 2 < 36
    ]
    assert accented == [(2, 3.0, 69)]
    tied = next(note for note in score.violin if note.bar == 3 and note.beat == 0.0)
    assert (tied.midi, tied.tie_stop, tied.accent) == (69, True, False)


def test_flute_enters_with_grace_notes_and_dovetails_with_violin_on_high_soar() -> None:
    # A phrase rising to G5 (index 18, midi 79) at eighth 20, then continuing on E5 (index 16, midi 76)
    # for 4 eighths: Violin plays the G5 peak with Flute, then yields the E5 tail to Flute.
    score = render(_session({20: (2, 18), 22: (4, 16), 26: (4, 9)}), regimes=("sideway",) * 3)
    flute_sounding = [note for note in score.flute if note.midi is not None and note.bar in (2, 3)]
    assert len(flute_sounding) >= 2
    first_flute = flute_sounding[0]
    assert first_flute.bar == 2 and first_flute.beat == 2.0
    # 3rd/5th above G5 (79) on Cmaj7 -> B5 (83, +4st major 3rd)
    assert first_flute.midi - 79 in (3, 4, 7)
    assert len(first_flute.grace_pitches) == 2
    assert list(first_flute.grace_pitches) == sorted(first_flute.grace_pitches)
    assert first_flute.grace_pitches[-1] < first_flute.midi
    assert first_flute.slur_start and first_flute.tenuto

    # Violin plays at 20..22 (overlap), then rests at 22..26 while Flute carries the soar
    v_at_20 = next(note for note in score.violin if note.bar == 2 and note.beat == 2.0)
    assert v_at_20.midi == 79
    v_at_22 = next(note for note in score.violin if note.bar == 2 and note.beat == 3.0)
    assert v_at_22.midi is None

    _text, root = _xml(score)
    flute_part = _part(root, "P5")
    measure_3 = flute_part.findall("measure")[2]
    graces = [note for note in measure_3.findall("note") if note.find("grace") is not None]
    assert len(graces) == 2
    assert graces[0].find("grace").get("slash") == "yes"
    assert graces[0].find("notations/slur").get("type") == "start"
    assert all(note.find("duration") is None for note in graces)
    regular = [note for note in measure_3.findall("note") if note.find("grace") is None]
    assert sum(int(note.find("duration").text) for note in regular) == 8


def test_flute_harmony_avoids_fourths_tritones_octave_drops_and_repeated_reattacks() -> None:
    scale = c_major_scale()
    for chord in (CMAJ7, FMAJ7, G7, AM7, DM7, EM7):
        for midi in scale:
            interval = flute_harmony_pitch(midi, chord, scale) - midi
            assert interval in (3, 4, 7), f"{midi} on {chord.name} gave interval +{interval}"

    # Rising above C6 (84): B5 (83) -> D6 (86) on G7 must ascend rather than drop an octave
    assert flute_harmony_pitch(86, G7, scale) >= flute_harmony_pitch(83, G7, scale)

    # Consecutive high notes mapping to the same Flute harmony pitch merge into one held note,
    # and a single long held peak (> FLUTE_OVERLAP) yields Violin to Flute after 2 eighths.
    long_peak = _session({20: (6, 21)})  # C6 (index 21, midi 84) held for 6 eighths
    score = render(long_peak, regimes=("sideway",) * 3)
    flute_bar2 = [note for note in score.flute if note.bar == 2 and note.midi is not None]
    assert [(n.beat, n.midi, n.duration_beats) for n in flute_bar2] == [(2.0, 88, 2.0)]
    violin_bar2_after_overlap = [
        note for note in score.violin if note.bar == 2 and note.beat >= 3.0
    ]
    assert all(note.midi is None for note in violin_bar2_after_overlap)
