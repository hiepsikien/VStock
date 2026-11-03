"""Dynamics and sound stay one table, and the knob stretches around 64."""

from __future__ import annotations

from app.sonify.dynamics import (
    BASE_VELOCITY,
    fill_velocity,
    piano_velocity_for,
    sound_for,
    velocity_for,
)
from app.sonify.params import DEFAULT_PARAMS, compose_params


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
