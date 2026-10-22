"""Meters, frames, and parallel mode from the 1M plan."""

import xml.etree.ElementTree as ET

from app.sonify.chords import JAZZ_VOICING_BY_NAME
from app.sonify.form import (
    FormSection,
    FormSpec,
    METER_128,
    METER_34,
    METER_44,
    METER_54,
    METER_64,
    liquidity_windows_for,
    plan_slots,
    swing_for,
)
from app.sonify.keys import C_KEY, EB_KEY, jazz_month_keys, movement_mode, signature_fifths
from app.sonify.model import Bar
from app.sonify.musicxml import score_to_musicxml
from app.sonify.playback import span_candle_index
from app.sonify.render import render
from app.sonify.span import (
    SEASON_REST_SECONDS,
    YEAR_SEASON_REST_SECONDS,
    attach_frame,
    plan_month,
    plan_quarter,
    year_specs,
)


def _clock(movements) -> float:
    return sum(
        movement.spec.eighths * 30.0 / movement.spec.bpm + movement.rest_after
        for movement in movements
    )


def _year_clock(variant: str) -> float:
    specs = tuple(attach_frame(spec, "1Y") for spec in year_specs(variant))
    total = 0.0
    for index, spec in enumerate(specs):
        total += spec.eighths * 30.0 / spec.bpm
        if index == 11:
            continue
        season = index // 3
        next_season = (index + 1) // 3
        total += YEAR_SEASON_REST_SECONDS if next_season != season else SEASON_REST_SECONDS
    return total


def test_piece_clocks_include_the_frame_and_the_rests() -> None:
    expected = {
        "symphony": (970.0, 1530.0, 2841.0),
        "jazz": (970.0, 1530.0, 2820.0),
        "minimalist": (968.0, 1529.0, 2841.0),
        "ambient": (970.0, 1530.0, 2820.0),
    }
    for variant, (month, quarter, year) in expected.items():
        assert abs(_clock(plan_month([1, 1, 1, 1], variant)) - month) < 1.5
        assert abs(_clock(plan_quarter([1, 1, 1], variant)) - quarter) < 1.5
        assert abs(_year_clock(variant) - year) < 1.5


def test_month_frame_sits_outside_the_body_and_the_liquidity_windows() -> None:
    spec = plan_month([1, 1, 1, 1])[0].spec
    assert spec.bars == 104
    assert spec.sections[0] == FormSection(0, 4, "warmup", 0)
    assert spec.sections[-1].kind == "cooldown"
    assert spec.sections[-1].start == 100
    assert all(start >= 4 for start, _length in liquidity_windows_for(spec))


def test_parallel_minor_signature_and_jazz_step() -> None:
    assert signature_fifths(C_KEY, "minor") == -3
    assert signature_fifths(EB_KEY, "minor") == -6
    assert movement_mode("selloff", "uptrend") == "minor"
    assert movement_mode("volatile", "downtrend") == "minor"
    assert movement_mode("volatile", "uptrend") == "major"
    assert movement_mode("rally", "downtrend") == "major"
    keys = jazz_month_keys(
        C_KEY,
        ("rally", "calm", "rally", "calm"),
        (("sideway", "sideway"),) * 4,
    )
    assert [key.name for key in keys] == ["C", "C", "D", "C"]
    assert swing_for("jazz", METER_44) is True
    assert swing_for("jazz", METER_128) is False


def test_home_pedal_opens_on_the_parallel_tonic_and_the_bridge_prefers_the_fourth() -> None:
    month = plan_month([1, 1, 1, 1], "jazz")
    head = month[0].spec
    slots = plan_slots(
        ("downtrend", "downtrend", "downtrend"),
        [60] * head.eighths,
        spec=head,
        mode="minor",
        home_pedal=True,
        character="selloff",
    )
    assert slots[0].section == "warmup"
    assert slots[0].chord.name == "Cm"
    assert slots[-1].chord.name == "Cm"
    assert JAZZ_VOICING_BY_NAME["Cm"].name == "Cm9"
    ballad = month[1].spec
    bridge = next(section for section in ballad.sections if section.bridge)
    bridged = plan_slots(
        ("sideway", "sideway", "sideway"),
        [65] * ballad.eighths,
        spec=ballad,
        mode="major",
        home_pedal=True,
    )
    opening = next(slot for slot in bridged if slot.start == bridge.start)
    assert opening.chord.name in ("F", "Fmaj7")


def test_span_playhead_holds_the_ends() -> None:
    assert span_candle_index(1.0, 10, 100.0, 10.0, 10.0) == 0
    assert span_candle_index(50.0, 10, 100.0, 10.0, 10.0) == 5
    assert span_candle_index(95.0, 10, 100.0, 10.0, 10.0) == 9
    assert span_candle_index(40.0, 10, 100.0, 0.0, 0.0) == 4


def test_symphony_frame_layers_the_strings() -> None:
    spec = FormSpec(
        12,
        96,
        (
            FormSection(0, 4, "warmup", 0),
            FormSection(4, 8, "phrase", 0),
            FormSection(8, 12, "cooldown", 0),
        ),
        (12,),
        meter=METER_44,
    )
    score = render(
        [Bar(100.0, 10.0, 100.0) for _ in range(12)],
        variant="symphony",
        form=spec,
        home_pedal=True,
    )
    lead = {note.bar for note in score.lead if note.midi is not None}
    assert 0 not in lead and 1 not in lead
    assert 2 in lead and 11 in lead
    assert 0 in {note.bar for note in score.low if note.midi is not None}
    assert any(wedge.kind == "crescendo" and wedge.bar == 2 for wedge in score.lead_wedges)
    assert any(wedge.kind == "diminuendo" and wedge.bar == 8 for wedge in score.lead_wedges)


def test_long_form_ambient_writes_its_meter_mode_and_frame() -> None:
    slow = FormSpec(
        6,
        72,
        (
            FormSection(0, 1, "warmup", 0),
            FormSection(1, 5, "phrase", 0),
            FormSection(5, 6, "cooldown", 0),
        ),
        (6,),
        meter=METER_64,
    )
    scherzo = FormSpec(
        6,
        108,
        (
            FormSection(0, 1, "warmup", 0),
            FormSection(1, 5, "phrase", 0),
            FormSection(5, 6, "cooldown", 0),
        ),
        (6,),
        meter=METER_34,
    )
    prices = [Bar(40.0, 10.0, 40.0) for _ in range(6)]
    slow_score = render(prices, variant="ambient", form=slow, mode="minor", home_pedal=True)
    assert (slow_score.beats, slow_score.beat_type, slow_score.bar_beats, slow_score.mode) == (
        6,
        4,
        6.0,
        "minor",
    )
    assert 0 in {note.bar for note in slow_score.lead if note.midi is not None}
    root = ET.fromstring(score_to_musicxml(slow_score))
    assert {node.text for node in root.iter("beats")} == {"6"}
    assert {node.text for node in root.iter("beat-type")} == {"4"}
    assert {node.text for node in root.iter("fifths")} == {"-3"}
    waltz = render(prices, variant="ambient", form=scherzo, mode="major", home_pedal=True)
    assert (waltz.beats, waltz.beat_type, waltz.bar_beats) == (3, 4, 3.0)
    day = render([Bar(80.0, 0.0, 80.0) for _ in range(30)], variant="ambient")
    assert day.bars == 34
    assert (day.beats, day.beat_type, day.bar_beats, day.mode) == (4, 4, 4.0, "major")


def test_five_four_whole_rest_has_no_type() -> None:
    spec = FormSpec(
        2,
        96,
        (FormSection(0, 2, "phrase", 0),),
        (2,),
        meter=METER_54,
    )
    score = render(
        [Bar(40.0, 0.0, 40.0), Bar(40.0, 0.0, 40.0)],
        variant="minimalist",
        form=spec,
    )
    root = ET.fromstring(score_to_musicxml(score))
    whole = [
        note
        for note in root.iter("note")
        if any(child.tag == "rest" and child.get("measure") == "yes" for child in note)
    ]
    assert whole
    assert all(child.tag != "type" for note in whole for child in note)
    fifths = {node.text for node in root.iter("fifths")}
    assert "5" in {node.text for node in root.iter("beats")}
    assert fifths == {"0"}
