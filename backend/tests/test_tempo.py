"""The tempo knob changes the BPM before any writer reads it."""

from __future__ import annotations

from app.sonify.params import DEFAULT_PARAMS, compose_params, tempo_bpm
from app.sonify.render import _tempo_bpm


def test_default_tempo_is_unchanged() -> None:
    assert _tempo_bpm(88) == 88
    assert tempo_bpm(88) == 88


def test_half_up_not_bankers_rounding() -> None:
    with compose_params({**DEFAULT_PARAMS, "tempo": 0.85}):
        assert _tempo_bpm(90) == 77  # 76.5 -> 77
    with compose_params({**DEFAULT_PARAMS, "tempo": 0.95}):
        assert _tempo_bpm(90) == 86  # 85.5 -> 86


def test_result_stays_an_int() -> None:
    with compose_params({**DEFAULT_PARAMS, "tempo": 1.03}):
        value = _tempo_bpm(88)
    assert isinstance(value, int)
    assert value == 91
