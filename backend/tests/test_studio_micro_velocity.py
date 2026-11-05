"""Tests for the optional micro-velocity model and relative applier.

The module is pure data: these tests never render, register, or import
``guitar_patterns``. They cover the §6.9 schema, the beat-coordinate and
duplicate rules, the zero-diff path, the relative/pinned split between
``apply_relative_offsets`` and ``check_pinned_attacks``, and the sixteenth /
triplet attacks that the old eighth-only applier could not address.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.sonify.model import NoteEvent
from app.studio.micro_velocity import (
    BEAT_EPSILON,
    EMPTY_MICRO_VELOCITY,
    MicroVelocity,
    MicroVelocityError,
    MicroVelocitySpecError,
    VelocityOffset,
    apply_relative_offsets,
    canonical_micro_velocity_mapping,
    check_pinned_attacks,
    is_empty,
    micro_velocity_to_mapping,
    parse_micro_velocity,
    validate_micro_velocity,
)

BACKEND = Path(__file__).resolve().parents[1]


def _entry(**overrides):
    data = {"bar": 0, "beat": 0.0, "voice": 1, "offset": -6}
    data.update(overrides)
    return data


def _contour(**overrides):
    data = {"kind": "offsets", "notes": [_entry()], "thumb": []}
    data.update(overrides)
    return data


def _note(*, bar=0, beat=0.0, voice=1, velocity=64, midi=60, **overrides):
    return NoteEvent(
        bar=bar,
        beat=beat,
        midi=midi,
        duration_beats=0.5,
        voice=voice,
        velocity=velocity,
        **overrides,
    )


# ---------------------------------------------------------------------------
# Parse + JSON round-trip
# ---------------------------------------------------------------------------


def test_offsets_json_round_trip():
    payload = _contour(
        notes=[
            _entry(bar=0, beat=0.0, voice=1, finger="a", offset=-6),
            _entry(bar=0, beat=0.25, voice=1, finger="m", offset=-3),
        ],
        thumb=[_entry(bar=0, beat=0.0, voice=3, finger="p", offset=-4)],
    )
    parsed = parse_micro_velocity(json.loads(json.dumps(payload)))

    assert isinstance(parsed, MicroVelocity)
    assert parsed.kind == "offsets"
    assert [entry.finger for entry in parsed.notes] == ["a", "m"]
    assert [entry.beat for entry in parsed.notes] == [0.0, 0.25]
    assert parsed.thumb[0].voice == 3
    assert micro_velocity_to_mapping(parsed) == payload
    assert parse_micro_velocity(micro_velocity_to_mapping(parsed)) == parsed


def test_canonical_mapping_sorts_entries_without_changing_their_spelling():
    authored = _contour(
        notes=[
            _entry(bar=1, beat=0.0, voice=1, offset=-2),
            _entry(bar=0, beat=0.5, voice=2, finger="i", offset=3),
            _entry(bar=0, beat=0.0, voice=1, finger="a", offset=-6),
            _entry(bar=0, beat=0.0, voice=1, offset=-1),
        ],
        thumb=[_entry(bar=2, beat=0.0, voice=3, finger="p", offset=-4)],
    )
    parsed = parse_micro_velocity(authored)

    canonical = canonical_micro_velocity_mapping(parsed)

    # Slot order is (bar, beat, voice, finger): a finger-agnostic entry sorts
    # before a finger-specific one at the same coordinate, then by finger.
    assert [
        (entry["bar"], entry["beat"], entry["voice"], entry.get("finger"))
        for entry in canonical["notes"]
    ] == [
        (0, 0.0, 1, None),
        (0, 0.0, 1, "a"),
        (0, 0.5, 2, "i"),
        (1, 0.0, 1, None),
    ]
    assert canonical["thumb"] == authored["thumb"]
    # Canonical sorting changes list order only, never an entry's fields.
    assert sorted(
        canonical["notes"], key=lambda entry: json.dumps(entry, sort_keys=True)
    ) == sorted(
        authored["notes"], key=lambda entry: json.dumps(entry, sort_keys=True)
    )
    assert canonical_micro_velocity_mapping(parsed) == canonical


def test_canonical_mapping_is_independent_of_authored_order():
    first = parse_micro_velocity(
        _contour(
            notes=[
                _entry(bar=0, beat=0.5, voice=1, offset=2),
                _entry(bar=0, beat=0.0, voice=1, offset=-2),
            ]
        )
    )
    second = parse_micro_velocity(
        _contour(
            notes=[
                _entry(bar=0, beat=0.0, voice=1, offset=-2),
                _entry(bar=0, beat=0.5, voice=1, offset=2),
            ]
        )
    )

    assert canonical_micro_velocity_mapping(first) == canonical_micro_velocity_mapping(
        second
    )
    assert micro_velocity_to_mapping(first) != micro_velocity_to_mapping(second)


def test_rule_json_round_trip():
    payload = {
        "kind": "rule",
        "ruleId": "galop1",
        "ruleVersion": 1,
        "params": {"step": 2, "floor": 40},
        "notes": [],
        "thumb": [],
    }
    parsed = parse_micro_velocity(payload)

    assert parsed.kind == "rule"
    assert parsed.rule_id == "galop1"
    assert parsed.rule_version == 1
    assert parsed.params == {"step": 2, "floor": 40}
    assert micro_velocity_to_mapping(parsed) == payload


def test_empty_thumb_round_trips_as_empty_list():
    payload = _contour(thumb=[])
    parsed = parse_micro_velocity(payload)
    assert parsed.thumb == ()
    assert micro_velocity_to_mapping(parsed)["thumb"] == []


def test_thumb_entry_defaults_to_voice_three():
    parsed = parse_micro_velocity(
        _contour(thumb=[{"bar": 0, "beat": 0.5, "finger": "p", "offset": -4}])
    )
    assert parsed.thumb[0].voice == 3
    assert micro_velocity_to_mapping(parsed)["thumb"][0]["voice"] == 3


def test_absurd_thumb_voice_is_still_validated():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(_contour(thumb=[_entry(voice=5)]))
    assert excinfo.value.path == "micro_velocity.thumb[0].voice"


def test_finger_absent_parses_and_serializes_without_finger():
    parsed = parse_micro_velocity(_contour(notes=[_entry()]))
    assert parsed.notes[0].finger is None
    assert "finger" not in micro_velocity_to_mapping(parsed)["notes"][0]


def test_integer_beat_is_normalized_to_float():
    parsed = parse_micro_velocity(
        _contour(notes=[{"bar": 0, "beat": 0, "voice": 1, "offset": -6}])
    )
    assert parsed.notes[0].beat == 0.0
    assert isinstance(parsed.notes[0].beat, float)


# ---------------------------------------------------------------------------
# Parse/validate rejections
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bar", [-1, -8])
def test_negative_bar_rejected(bar):
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(_contour(notes=[_entry(bar=bar)]))
    assert excinfo.value.path == "micro_velocity.notes[0].bar"


def test_negative_beat_rejected():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(_contour(notes=[_entry(beat=-0.25)]))
    assert excinfo.value.path == "micro_velocity.notes[0].beat"


@pytest.mark.parametrize("beat", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_beat_rejected(beat):
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(_contour(notes=[_entry(beat=beat)]))
    assert excinfo.value.path == "micro_velocity.notes[0].beat"


def test_beat_overflow_rejected_against_supplied_bounds():
    value = MicroVelocity(
        notes=(VelocityOffset(bar=0, beat=4.0, voice=1, offset=-3),)
    )
    errors = validate_micro_velocity(value, bars=2, beats_per_bar=4.0)
    assert [error.path for error in errors] == ["micro_velocity.notes[0].beat"]


def test_bar_overflow_rejected_against_supplied_bounds():
    value = MicroVelocity(
        notes=(VelocityOffset(bar=2, beat=0.0, voice=1, offset=-3),)
    )
    errors = validate_micro_velocity(value, bars=2, beats_per_bar=4.0)
    assert [error.path for error in errors] == ["micro_velocity.notes[0].bar"]


def test_beat_inside_bar_bound_is_accepted():
    value = MicroVelocity(
        notes=(VelocityOffset(bar=0, beat=3.75, voice=1, offset=-3),)
    )
    assert validate_micro_velocity(value, bars=2, beats_per_bar=4.0) == ()


def test_non_finite_beat_rejected_by_validate_directly():
    value = MicroVelocity(
        notes=(VelocityOffset(bar=0, beat=float("nan"), voice=1, offset=-3),)
    )
    errors = validate_micro_velocity(value)
    assert [error.path for error in errors] == ["micro_velocity.notes[0].beat"]


@pytest.mark.parametrize("voice", [0, 5, -1])
def test_invalid_voice_rejected(voice):
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(_contour(notes=[_entry(voice=voice)]))
    assert excinfo.value.path == "micro_velocity.notes[0].voice"


def test_invalid_finger_rejected():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(_contour(notes=[_entry(finger="x")]))
    assert excinfo.value.path == "micro_velocity.notes[0].finger"


def test_offset_and_pinned_together_rejected():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(
            _contour(notes=[_entry(pinned=True, velocity=70)])
        )
    assert excinfo.value.path == "micro_velocity.notes[0].offset"


def test_pinned_without_velocity_rejected():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(
            _contour(notes=[{"bar": 0, "beat": 0.25, "voice": 1, "pinned": True}])
        )
    assert excinfo.value.path == "micro_velocity.notes[0].velocity"


def test_velocity_without_pinned_rejected():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(_contour(notes=[_entry(velocity=70)]))
    assert excinfo.value.path == "micro_velocity.notes[0].velocity"


def test_entry_needs_offset_or_pinned():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(
            _contour(notes=[{"bar": 0, "beat": 0.5, "voice": 1}])
        )
    assert excinfo.value.path == "micro_velocity.notes[0].offset"


def test_duplicate_key_rejected():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(
            _contour(
                notes=[
                    _entry(beat=0.25, offset=-6),
                    _entry(beat=0.25, offset=-2),
                ]
            )
        )
    assert excinfo.value.path == "micro_velocity.notes[1]"
    assert "duplicate key" in excinfo.value.message


def test_duplicate_key_uses_beat_tolerance():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(
            _contour(
                notes=[
                    _entry(beat=0.5, offset=-6),
                    _entry(beat=0.5000001, offset=-2),
                ]
            )
        )
    assert excinfo.value.path == "micro_velocity.notes[1]"


def test_duplicate_thumb_key_rejected():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(
            _contour(
                thumb=[
                    _entry(voice=3, finger="p", offset=-4),
                    _entry(voice=3, finger="p", offset=-2),
                ]
            )
        )
    assert excinfo.value.path == "micro_velocity.thumb[1]"


def test_duplicate_key_across_notes_and_thumb_rejected():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(
            _contour(
                notes=[_entry(voice=3, offset=-6)],
                thumb=[_entry(voice=3, offset=-4)],
            )
        )
    assert excinfo.value.path == "micro_velocity.thumb[0]"


def test_distinct_sixteenth_beats_are_not_duplicates():
    parsed = parse_micro_velocity(
        _contour(
            notes=[
                _entry(beat=0.0, offset=-1),
                _entry(beat=0.25, offset=-2),
                _entry(beat=0.5, offset=-3),
                _entry(beat=0.75, offset=-4),
            ]
        )
    )
    assert [entry.beat for entry in parsed.notes] == [0.0, 0.25, 0.5, 0.75]


@pytest.mark.parametrize("field", ["ruleId", "ruleVersion", "params"])
def test_rule_missing_required_field_rejected(field):
    payload = {
        "kind": "rule",
        "ruleId": "galop1",
        "ruleVersion": 1,
        "params": {"step": 2},
        "notes": [],
        "thumb": [],
    }
    del payload[field]
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(payload)
    assert excinfo.value.path == f"micro_velocity.{field}"


def test_offsets_with_empty_notes_rejected():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity({"kind": "offsets", "notes": [], "thumb": []})
    assert excinfo.value.path == "micro_velocity.notes"


def test_rule_may_have_empty_notes():
    parsed = parse_micro_velocity(
        {
            "kind": "rule",
            "ruleId": "galop1",
            "ruleVersion": 2,
            "params": {"step": 2},
            "notes": [],
        }
    )
    assert parsed.notes == ()
    assert micro_velocity_to_mapping(parsed)["thumb"] == []


def test_offsets_kind_rejects_rule_fields():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(_contour(ruleId="galop1"))
    assert excinfo.value.path == "micro_velocity.ruleId"


def test_unknown_top_level_field_rejected():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(_contour(base=64))
    assert excinfo.value.path == "micro_velocity"


def test_unknown_entry_field_rejected():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity(_contour(notes=[_entry(delta=-2)]))
    assert excinfo.value.path == "micro_velocity.notes[0]"


def test_parse_error_is_value_error_with_path():
    with pytest.raises(MicroVelocitySpecError) as excinfo:
        parse_micro_velocity({"kind": "bogus", "notes": [], "thumb": []})
    assert isinstance(excinfo.value, ValueError)
    assert excinfo.value.path == "micro_velocity.kind"


def test_validate_collects_every_entry_error():
    value = MicroVelocity(
        notes=(
            VelocityOffset(bar=-1, beat=0.0, voice=0, offset=None),
            VelocityOffset(bar=0, beat=-0.25, voice=5, offset=1, pinned=True),
        )
    )
    errors = validate_micro_velocity(value)
    paths = {error.path for error in errors}
    assert "micro_velocity.notes[0].bar" in paths
    assert "micro_velocity.notes[0].voice" in paths
    assert "micro_velocity.notes[0].offset" in paths
    assert "micro_velocity.notes[1].beat" in paths
    assert "micro_velocity.notes[1].voice" in paths
    assert "micro_velocity.notes[1].offset" in paths


# ---------------------------------------------------------------------------
# is_empty / zero-diff
# ---------------------------------------------------------------------------


def test_is_empty_none_and_canonical_empty():
    assert is_empty(None) is True
    assert is_empty(EMPTY_MICRO_VELOCITY) is True
    assert validate_micro_velocity(EMPTY_MICRO_VELOCITY) == ()


def test_is_empty_false_for_authored_contour_and_rule():
    assert is_empty(parse_micro_velocity(_contour())) is False
    assert (
        is_empty(
            parse_micro_velocity(
                {
                    "kind": "rule",
                    "ruleId": "galop1",
                    "ruleVersion": 1,
                    "params": {"step": 2},
                    "notes": [],
                }
            )
        )
        is False
    )


def test_zero_offset_contour_is_not_empty_but_changes_nothing():
    contour = parse_micro_velocity(_contour(notes=[_entry(offset=0)]))
    events = [_note()]

    assert is_empty(contour) is False
    assert apply_relative_offsets(events, contour)[0].velocity == 64


# ---------------------------------------------------------------------------
# apply_relative_offsets
# ---------------------------------------------------------------------------


def test_apply_changes_only_the_matching_event():
    contour = parse_micro_velocity(_contour(notes=[_entry(offset=-6)]))
    events = [
        _note(bar=0, beat=0.0, voice=1),
        _note(bar=0, beat=0.25, voice=1),
        _note(bar=0, beat=0.0, voice=2),
    ]

    result = apply_relative_offsets(events, contour)

    assert [event.velocity for event in result] == [58, 64, 64]
    assert [event.midi for event in result] == [60, 60, 60]


def test_apply_does_not_mutate_input():
    contour = parse_micro_velocity(_contour(notes=[_entry(offset=-6)]))
    event = _note(velocity=64)
    events = [event]

    result = apply_relative_offsets(events, contour)

    assert events == [event]
    assert event.velocity == 64
    assert result is not events
    assert result[0] == NoteEvent(
        bar=0, beat=0.0, midi=60, duration_beats=0.5, voice=1, velocity=58
    )


def test_apply_without_contour_returns_identical_copy():
    events = [_note(), _note(bar=1, beat=1.0, voice=2)]

    result = apply_relative_offsets(events, None)

    assert result == events
    assert result is not events
    assert all(new is old for new, old in zip(result, events))


def test_apply_empty_contour_returns_identical_copy():
    events = [_note()]

    result = apply_relative_offsets(events, EMPTY_MICRO_VELOCITY)

    assert result == events
    assert result is not events
    assert result[0] is events[0]


def test_apply_ignores_pinned_entries():
    contour = parse_micro_velocity(
        _contour(
            notes=[
                {"bar": 0, "beat": 0.0, "voice": 1, "pinned": True, "velocity": 70}
            ]
        )
    )
    events = [_note(velocity=64)]

    result = apply_relative_offsets(events, contour)

    assert result[0].velocity == 64
    assert result[0] == events[0]


def test_apply_origin_bar_shift():
    contour = parse_micro_velocity(
        _contour(
            notes=[
                _entry(bar=0, beat=0.0, offset=-6),
                _entry(bar=1, beat=0.0, offset=-3),
            ]
        )
    )
    events = [
        _note(bar=2, beat=0.0),  # local bar 0, beat stays relative
        _note(bar=3, beat=0.0),  # local bar 1
        _note(bar=2, beat=0.5),  # local bar 0, no entry
    ]

    result = apply_relative_offsets(events, contour, origin_bar=2)

    assert [event.velocity for event in result] == [58, 61, 64]


def test_apply_origin_bar_does_not_shift_beat():
    contour = parse_micro_velocity(_contour(notes=[_entry(bar=0, beat=2.0, offset=-6)]))
    events = [
        _note(bar=4, beat=2.0),
        _note(bar=4, beat=0.0),
    ]

    result = apply_relative_offsets(events, contour, origin_bar=4)

    assert [event.velocity for event in result] == [58, 64]


def test_apply_finger_absent_matches_every_finger():
    contour = parse_micro_velocity(_contour(notes=[_entry(offset=-6)]))
    events = [_note(midi=60), _note(midi=64)]

    result = apply_relative_offsets(
        events, contour, finger_at=lambda event: "a" if event.midi == 60 else "m"
    )

    assert [event.velocity for event in result] == [58, 58]


def test_apply_finger_specific_wins_over_finger_agnostic():
    contour = parse_micro_velocity(
        _contour(
            notes=[
                _entry(offset=-2),
                _entry(finger="a", offset=-6),
            ]
        )
    )
    events = [_note(midi=60), _note(midi=64)]
    fingers = {60: "a", 64: "m"}

    result = apply_relative_offsets(
        events, contour, finger_at=lambda event: fingers[event.midi]
    )

    assert [event.velocity for event in result] == [58, 62]


def test_apply_finger_specific_without_resolver_does_not_match():
    contour = parse_micro_velocity(_contour(notes=[_entry(finger="a", offset=-6)]))
    events = [_note()]

    result = apply_relative_offsets(events, contour)

    assert result[0].velocity == 64


def test_apply_clamps_to_midi_velocity_range():
    high = parse_micro_velocity(_contour(notes=[_entry(offset=200)]))
    low = parse_micro_velocity(_contour(notes=[_entry(offset=-200)]))

    assert apply_relative_offsets([_note(velocity=120)], high)[0].velocity == 127
    assert apply_relative_offsets([_note(velocity=5)], low)[0].velocity == 1


def test_apply_tremolo_sixteenth_fill_hits_all_four_attacks():
    """Tremolo fills are sixteenth attacks; none of them may be skipped."""
    offsets = {-1: 63, -2: 62, -3: 61, -4: 60}
    contour = parse_micro_velocity(
        _contour(
            notes=[
                _entry(bar=0, beat=0.0, offset=-1),
                _entry(bar=0, beat=0.25, offset=-2),
                _entry(bar=0, beat=0.5, offset=-3),
                _entry(bar=0, beat=0.75, offset=-4),
            ]
        )
    )
    events = [
        _note(beat=0.0, voice=1),
        _note(beat=0.25, voice=1),
        _note(beat=0.5, voice=1),
        _note(beat=0.75, voice=1),
    ]
    original = list(events)

    result = apply_relative_offsets(events, contour)

    assert [event.velocity for event in result] == [63, 62, 61, 60]
    assert events == original
    assert [event.velocity for event in events] == [64, 64, 64, 64]
    assert result is not events


def test_apply_etude_sixteenth_run_hits_every_attack():
    """Etude1/11 fills run on sixteenths across the whole bar."""
    beats = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75]
    contour = parse_micro_velocity(
        _contour(
            notes=[
                _entry(bar=0, beat=beat, voice=2, offset=-index)
                for index, beat in enumerate(beats)
            ]
        )
    )
    events = [_note(beat=beat, voice=2) for beat in beats]
    original = list(events)

    result = apply_relative_offsets(events, contour)

    assert [event.velocity for event in result] == [64 - index for index in range(8)]
    assert events == original
    assert result is not events


def test_apply_triplet_coordinate_within_tolerance():
    contour = parse_micro_velocity(
        _contour(notes=[_entry(bar=0, beat=1.0 / 3.0, offset=-6)])
    )
    events = [
        _note(beat=1.0 / 3.0),
        _note(beat=2.0 / 3.0),
    ]

    result = apply_relative_offsets(events, contour)

    assert [event.velocity for event in result] == [58, 64]


def test_apply_beat_tolerance_is_bounded():
    contour = parse_micro_velocity(
        _contour(notes=[_entry(bar=0, beat=1.0 / 3.0, offset=-6)])
    )
    within = 1.0 / 3.0 + BEAT_EPSILON / 2
    outside = 1.0 / 3.0 + BEAT_EPSILON * 2
    events = [_note(beat=within), _note(beat=outside)]

    result = apply_relative_offsets(events, contour)

    assert [event.velocity for event in result] == [58, 64]


def test_apply_skips_rests_and_missing_velocity():
    contour = parse_micro_velocity(_contour(notes=[_entry(offset=-6)]))
    events = [
        _note(midi=None),
        _note(velocity=None),
    ]

    result = apply_relative_offsets(events, contour)

    assert result == events
    assert result[0] is events[0]
    assert result[1] is events[1]


def test_apply_thumb_lane_targets_voice_three():
    contour = parse_micro_velocity(
        _contour(
            notes=[_entry(voice=1, offset=-1)],
            thumb=[_entry(voice=3, finger="p", offset=-4)],
        )
    )
    events = [
        _note(voice=1, velocity=64),
        _note(voice=3, velocity=64),
    ]

    result = apply_relative_offsets(
        events, contour, finger_at=lambda event: "p" if event.voice == 3 else "a"
    )

    assert [event.velocity for event in result] == [63, 60]


def test_apply_preserves_flags_and_other_fields():
    contour = parse_micro_velocity(_contour(notes=[_entry(offset=-6)]))
    event = _note(accent=True, staccato=True, tie_start=True)

    result = apply_relative_offsets([event], contour)

    assert result[0].accent is True
    assert result[0].staccato is True
    assert result[0].tie_start is True
    assert result[0].velocity == 58


def test_apply_rejects_non_integer_origin():
    with pytest.raises(ValueError):
        apply_relative_offsets([_note()], parse_micro_velocity(_contour()), origin_bar=1.5)


# ---------------------------------------------------------------------------
# check_pinned_attacks
# ---------------------------------------------------------------------------


def _pinned_contour(velocity=70, **overrides):
    return parse_micro_velocity(
        _contour(
            notes=[
                {
                    "bar": 0,
                    "beat": 0.0,
                    "voice": 1,
                    "pinned": True,
                    "velocity": velocity,
                }
            ],
            **overrides,
        )
    )


def test_check_pinned_matches_final_velocity():
    errors = check_pinned_attacks([_note(velocity=70)], _pinned_contour(70))
    assert errors == ()


def test_check_pinned_reports_mismatch():
    errors = check_pinned_attacks([_note(velocity=66)], _pinned_contour(70))
    assert len(errors) == 1
    assert isinstance(errors[0], MicroVelocityError)
    assert errors[0].path == "micro_velocity.notes[0].velocity"
    assert "70" in errors[0].message and "66" in errors[0].message


def test_check_pinned_reports_missing_attack():
    errors = check_pinned_attacks([_note(bar=3)], _pinned_contour(70))
    assert len(errors) == 1
    assert "no matching event" in errors[0].message


def test_check_pinned_does_not_apply_anything():
    event = _note(velocity=66)
    errors = check_pinned_attacks([event], _pinned_contour(70))
    assert errors != ()
    assert event.velocity == 66


def test_check_pinned_ignores_relative_entries():
    contour = parse_micro_velocity(_contour(notes=[_entry(offset=-6)]))
    assert check_pinned_attacks([_note(velocity=64)], contour) == ()


def test_check_pinned_honours_origin_shift():
    contour = _pinned_contour(70)
    errors = check_pinned_attacks(
        [_note(bar=2, beat=0.0, velocity=70)],
        contour,
        origin_bar=2,
    )
    assert errors == ()


def test_check_pinned_uses_finger_resolver():
    contour = parse_micro_velocity(
        _contour(
            notes=[
                {
                    "bar": 0,
                    "beat": 0.0,
                    "voice": 1,
                    "finger": "a",
                    "pinned": True,
                    "velocity": 70,
                }
            ]
        )
    )
    events = [_note(midi=60, velocity=70), _note(midi=64, velocity=60)]

    assert check_pinned_attacks(events, contour) != ()
    assert (
        check_pinned_attacks(
            events,
            contour,
            finger_at=lambda event: "a" if event.midi == 60 else "m",
        )
        == ()
    )


def test_check_pinned_sixteenth_coordinate():
    contour = parse_micro_velocity(
        _contour(
            notes=[
                {
                    "bar": 0,
                    "beat": 0.25,
                    "voice": 1,
                    "pinned": True,
                    "velocity": 70,
                }
            ]
        )
    )
    events = [_note(beat=0.0, velocity=64), _note(beat=0.25, velocity=70)]

    assert check_pinned_attacks(events, contour) == ()


# ---------------------------------------------------------------------------
# Import stays inert
# ---------------------------------------------------------------------------


def test_import_does_not_pull_in_the_pattern_registry():
    code = (
        "import sys; import app.studio.micro_velocity; "
        "print('app.sonify.guitar_patterns' in sys.modules); "
        "print('app.studio.texture_spec' in sys.modules)"
    )
    output = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert output.split() == ["False", "False"]
