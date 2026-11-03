"""Schema v3, tiers, and the B/C knobs."""

from __future__ import annotations

import base64
import json
import pytest

from app.sonify.keys import C_REGISTER, shift_register
from app.sonify.model import Bar
from app.sonify.params import (
    DEFAULT_HASH,
    DEFAULT_PARAMS,
    FIELD_BY_KEY,
    SCHEMA_VERSION,
    TIERS,
    apply_tiers,
    compose_params,
    decode_params,
    encode_params,
    params_hash,
    schema_payload,
)
from app.sonify.render import render
from app.sonify.span import attach_frame, month_specs


@pytest.fixture(autouse=True)
def _all_tiers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VSTOCK_SONIFY_PARAMS_TIER", "A,B,C")


def _bars() -> list[Bar]:
    closes = [100 + ((i * 7) % 13) for i in range(240)]
    return [Bar(value, 100_000.0, value) for value in closes]


def test_schema_v3_is_pinned_and_typed() -> None:
    assert SCHEMA_VERSION == 3
    assert DEFAULT_HASH == "ce9ab87f3a0d"
    assert len(FIELD_BY_KEY) == 16
    assert FIELD_BY_KEY["harmony"].tier == "B"
    assert FIELD_BY_KEY["technique"].tier == "C"
    assert FIELD_BY_KEY["frame"].kind == "choice"
    payload = schema_payload(enabled=True, tiers=TIERS)
    assert payload["schema"] == 3
    assert payload["enabledTiers"] == list(TIERS)
    guitar = next(field for group in payload["groups"] for field in group["fields"] if field["key"] == "guitar_high")
    assert guitar["signed"] is True
    assert guitar["default"] == 0


def test_tier_a_hides_b_and_c(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VSTOCK_SONIFY_PARAMS_TIER", "A")
    raw = {**DEFAULT_PARAMS, "harmony": 0.0, "technique": 2.0}
    shaped = apply_tiers(raw, tiers=("A",))
    assert shaped["harmony"] == 1.0
    assert shaped["technique"] == 1.0
    assert params_hash(raw, tiers=("A",)) != params_hash(raw, tiers=TIERS)


def test_link_schema_2_still_reads_new_fields() -> None:
    payload = {
        "schema": 2,
        "params": {**DEFAULT_PARAMS, "harmony": 0.0, "guitar_high": 4.0},
    }
    text = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).decode().rstrip("=")
    shaped = decode_params(text)
    assert shaped["harmony"] == 0.0
    assert shaped["guitar_high"] == 4.0
    assert encode_params(shaped, schema=2).startswith(encode_params(DEFAULT_PARAMS, schema=2)[:4])


def test_register_shift_is_chromatic_and_zero_is_identity() -> None:
    assert shift_register(C_REGISTER, 0) is C_REGISTER
    moved = shift_register(C_REGISTER, 3)
    assert moved.violin_ceiling == C_REGISTER.violin_ceiling + 3
    assert moved.support_floor == C_REGISTER.support_floor + 3


def test_harmony_zero_uses_triads_only() -> None:
    with compose_params({**DEFAULT_PARAMS, "harmony": 0.0}):
        score = render(_bars(), regimes=("uptrend", "sideway", "downtrend"))
    assert all(len(slot.chord.pitches) <= 3 for slot in score.slots)


def test_harmony_two_can_use_borrowed_chords() -> None:
    with compose_params({**DEFAULT_PARAMS, "harmony": 1.0}):
        base = render(_bars(), regimes=("uptrend", "sideway", "downtrend"))
    with compose_params({**DEFAULT_PARAMS, "harmony": 2.0}):
        rich = render(_bars(), regimes=("uptrend", "sideway", "downtrend"))
    base_four = sum(1 for slot in base.slots if len(slot.chord.pitches) >= 4)
    rich_four = sum(1 for slot in rich.slots if len(slot.chord.pitches) >= 4)
    assert rich_four > base_four


def test_frame_and_meter_choices_apply() -> None:
    body = month_specs("symphony")[0]
    with compose_params({**DEFAULT_PARAMS, "frame": "none"}):
        no_frame = attach_frame(body, "1M")
    assert no_frame.bars == body.bars
    with compose_params({**DEFAULT_PARAMS, "frame": "short"}):
        short = attach_frame(body, "1M")
    with compose_params({**DEFAULT_PARAMS, "frame": "long"}):
        long = attach_frame(body, "1M")
    assert short.bars < long.bars

    with compose_params({**DEFAULT_PARAMS, "meter": "3/4"}):
        score = render(_bars(), variant="guitar", ensemble="torroba", regimes=("sideway",) * 3)
    assert (score.beats, score.beat_type) == (3, 4)


def test_schema_fixture_is_independent_of_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VSTOCK_SONIFY_PARAMS_TIER", "A")
    fixture = schema_payload(enabled=True, tiers=TIERS)
    assert fixture["enabledTiers"] == list(TIERS)
    runtime = schema_payload()
    assert runtime["enabledTiers"] == ["A"]


def _changes(score) -> int:
    return sum(1 for left, right in zip(score.slots, score.slots[1:]) if left.chord != right.chord)


def test_motion_is_monotone() -> None:
    counts = []
    for motion in (0.0, 1.0, 2.0):
        with compose_params({**DEFAULT_PARAMS, "motion": motion}):
            counts.append(_changes(render(_bars(), regimes=("uptrend", "sideway", "downtrend"))))
    assert counts[0] < counts[1] < counts[2]


def test_technique_renders_both_extremes() -> None:
    for technique in (0.0, 2.0):
        with compose_params({**DEFAULT_PARAMS, "technique": technique}):
            score = render(
                _bars(),
                variant="guitar",
                ensemble="barrios",
                regimes=("sideway",) * 3,
            )
        assert score.bars > 0


def test_register_changes_the_written_line() -> None:
    with compose_params({**DEFAULT_PARAMS, "register": 0.0}):
        low = render(_bars(), regimes=("uptrend", "sideway", "downtrend"))
    with compose_params({**DEFAULT_PARAMS, "register": 2.0}):
        high = render(_bars(), regimes=("uptrend", "sideway", "downtrend"))
    low_pitches = tuple(event.midi for event in low.lead if event.midi is not None)
    high_pitches = tuple(event.midi for event in high.lead if event.midi is not None)
    assert low_pitches != high_pitches
