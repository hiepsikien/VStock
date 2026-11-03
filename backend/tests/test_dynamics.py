"""Dynamics and sound stay one table, and the knob stretches around 64."""

from __future__ import annotations

from math import sin
from xml.etree import ElementTree as ET

from app.sonify.dynamics import (
    BASE_VELOCITY,
    fill_velocity,
    piano_velocity_for,
    sound_for,
    velocity_for,
)
from app.sonify.model import Bar, DynamicEvent
from app.sonify.musicxml import _dynamic
from app.sonify.params import DEFAULT_PARAMS, compose_params
from app.sonify.render import render


def test_default_velocities_are_the_old_table() -> None:
    assert velocity_for("f") == 96
    assert velocity_for("mp") == 64
    assert velocity_for("p") == 49
    assert velocity_for("ppp") == 20
    assert sound_for("f") == 107
    assert sound_for("mp") == 71
    assert sound_for("p") == 54
    assert sound_for("ppp") == 22


def test_sound_is_derived_from_velocity() -> None:
    for marking in BASE_VELOCITY:
        assert sound_for(marking) == round(velocity_for(marking) / 90 * 100)


def test_contrast_expands_and_compresses_around_64() -> None:
    with compose_params({**DEFAULT_PARAMS, "dynamics": 1.5}):
        assert velocity_for("f") > 96
        assert velocity_for("p") < 49
        assert velocity_for("mp") == 64
        assert piano_velocity_for("f") > 68
    with compose_params({**DEFAULT_PARAMS, "dynamics": 0.5}):
        assert velocity_for("f") < 96
        assert velocity_for("p") > 49
    assert fill_velocity() == 64


def test_values_stay_in_midi_range() -> None:
    with compose_params({**DEFAULT_PARAMS, "dynamics": 1.5}):
        for marking in BASE_VELOCITY:
            assert 1 <= velocity_for(marking) <= 127


def _bars() -> list[Bar]:
    return [
        Bar(
            close=100 + index * 0.4 + sin(index / 2) * 1.2,
            volume=1000 + (index % 7) * 450,
        )
        for index in range(32)
    ]


def _velocities(score, field: str) -> list[int]:
    return [
        note.velocity
        for note in getattr(score, field)
        if note.velocity is not None
    ]


def _spread(score) -> int:
    values = [
        velocity
        for field in ("high", "lead", "support", "comp", "low")
        for velocity in _velocities(score, field)
    ]
    return max(values) - min(values)


def test_the_knob_stretches_every_part_not_just_the_piano() -> None:
    with compose_params(DEFAULT_PARAMS):
        base = render(_bars(), variant="symphony")
    with compose_params({**DEFAULT_PARAMS, "dynamics": 1.5}):
        wide = render(_bars(), variant="symphony")

    assert _spread(wide) > _spread(base)
    # The violin and piano must move too. Scaling only one bed would leave
    # one of these lists untouched.
    assert _velocities(wide, "lead") != _velocities(base, "lead")
    assert _velocities(wide, "support") != _velocities(base, "support")
    assert _velocities(wide, "comp") != _velocities(base, "comp")


def test_musicxml_dynamic_reads_the_knob_at_write_time() -> None:
    measure = ET.Element("measure")
    with compose_params({**DEFAULT_PARAMS, "dynamics": 1.5}):
        _dynamic(measure, DynamicEvent(bar=0, marking="p", sound=54))
        expected = str(sound_for("p"))
    sound = measure.find("direction/sound")
    assert sound is not None
    assert sound.get("dynamics") == expected
    assert sound.get("dynamics") != "54"
