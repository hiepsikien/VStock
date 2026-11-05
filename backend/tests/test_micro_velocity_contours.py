"""Exact zero-diff proof for the extracted micro-velocity contour data.

`tests/micro_velocity_golden.py` is the committed oracle: the full
`NoteEvent` surface of the production render after the guitar wave and before
humanize. This module renders each extracted figure through
`app.sonify.micro_velocity_contours` and compares the fixture rows, every
event, and the digests with no tolerance.

The extraction harness in `tests/micro_velocity_extract.py` also checks the
pre-wave boundary: the data contour plus a declared neutral written level must
reproduce the hardcoded writer's output event-for-event. A contour that fails
that check is not a silent "close enough" offset; it raises before the golden
comparison.

Cathedral Preludio is extracted as a rule. Its cross-voice clamp
(`min(level, canto - 6)`) is flatten-time context: the harness reads the canto
from the writer's own lead events, and the rule stores only the cell shape.
The golden fixture's mf cells sit exactly on the clamp boundary, so the clamp
is exercised separately with synthetic events below.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import pytest

from app.sonify.micro_velocity_contours import (
    CATHEDRAL_PRELUDIO,
    DEFAULT_CONTOURS,
    ETUDE1,
    ETUDE11,
    EXTRACTED_FIGURES,
    GALOP1,
    GALOP2,
    NEUTRAL_LEVELS,
    TREMOLO_34,
    TREMOLO_44,
    TREMOLO_CONTOURS,
    UNEXTRACTED_REASONS,
    _etude11_slot,
    covering_canto,
    flatten_rule,
)
from app.sonify.model import NoteEvent
from app.studio.micro_velocity import (
    EMPTY_MICRO_VELOCITY,
    MicroVelocity,
    apply_relative_offsets,
    is_empty,
    micro_velocity_to_mapping,
    parse_micro_velocity,
    validate_micro_velocity,
)
from tests.micro_velocity_extract import (
    EXTRACTED_FIXTURES,
    unextracted_reason,
    verify_fixture,
)
from tests.micro_velocity_golden import build_manifest

FIXTURE = Path(__file__).parent / "fixtures" / "micro_velocity_golden.json"


def _committed() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _row(fixture_id: str) -> dict[str, Any]:
    for row in _committed()["fixtures"]:
        if row["id"] == fixture_id:
            return row
    raise AssertionError(f"missing fixture {fixture_id}")


# ---------------------------------------------------------------------------
# exact zero-diff
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_id", EXTRACTED_FIXTURES)
def test_each_extracted_fixture_is_zero_diff(fixture_id: str) -> None:
    verification = verify_fixture(fixture_id)
    assert verification.first_mismatch() is None, verification.first_mismatch()
    assert verification.exact, verification.first_mismatch()
    assert verification.notes_digest == verification.expected_notes_digest
    assert verification.score_digest == verification.expected_score_digest


def test_tremolo_44_and_34_both_reproduce_the_oracle() -> None:
    four = verify_fixture("tremolo_44")
    three = verify_fixture("tremolo_34")
    assert four.exact, four.first_mismatch()
    assert three.exact, three.first_mismatch()
    assert four.actual["patterns"] == ["tremolo"]
    assert three.actual["patterns"] == ["tremolo"]


def test_etude_fixtures_reproduce_the_oracle() -> None:
    for fixture_id in ("etude1", "etude11"):
        verification = verify_fixture(fixture_id)
        assert verification.exact, verification.first_mismatch()


def test_galop_cycle_reproduces_both_cells() -> None:
    for fixture_id in ("galop_1", "galop_2"):
        verification = verify_fixture(fixture_id)
        assert verification.exact, verification.first_mismatch()
    assert _row("galop_1")["cells"] == {"galop1": [1, 2, 3, 4]}
    assert _row("galop_2")["cells"] == {
        "galop1": [1, 2, 3, 4],
        "galop2": [5, 6, 7, 8],
    }


# ---------------------------------------------------------------------------
# Cathedral is extracted with cross-voice context
# ---------------------------------------------------------------------------


def test_cathedral_fixture_reproduces_the_oracle() -> None:
    verification = verify_fixture("catedral_preludio")
    assert verification.exact, verification.first_mismatch()
    assert verification.notes_digest == verification.expected_notes_digest
    assert verification.score_digest == verification.expected_score_digest


def test_every_required_figure_is_now_extracted() -> None:
    assert "catedral_preludio" in EXTRACTED_FIGURES
    assert set(EXTRACTED_FIGURES) == {
        "tremolo",
        "etude1",
        "etude11",
        "galop1",
        "galop2",
        "catedral_preludio",
    }
    assert UNEXTRACTED_REASONS == {}
    with pytest.raises(KeyError):
        unextracted_reason("catedral_preludio")


def _cathedral_events():
    """A canto attack covering the cell plus one attack from each inner role."""
    canto = NoteEvent(
        bar=0, beat=0.0, midi=72, duration_beats=1.5, voice=1, velocity=61
    )
    inner = [
        NoteEvent(
            bar=0, beat=0.25, midi=59, duration_beats=0.5, voice=2, velocity=50
        ),
        NoteEvent(
            bar=0, beat=0.5, midi=64, duration_beats=0.5, voice=4, velocity=40
        ),
    ]
    return canto, inner


def _cathedral_flatten(canto, inner, *, raw: int = 80):
    centres = NEUTRAL_LEVELS["catedral_preludio"]
    assert isinstance(centres, dict)
    return flatten_rule(
        CATHEDRAL_PRELUDIO,
        inner,
        base_at=lambda event: centres.get(event.voice),
        raw_at=lambda event: raw,
        canto_at=lambda event: covering_canto([canto], event.bar, event.beat),
        beats_per_bar=4,
    )


def test_cathedral_rule_has_no_base_field() -> None:
    assert CATHEDRAL_PRELUDIO.kind == "rule"
    assert CATHEDRAL_PRELUDIO.rule_id == "catedral_preludio"
    assert CATHEDRAL_PRELUDIO.rule_version == 1
    assert set(CATHEDRAL_PRELUDIO.params) == {
        "cellEighths",
        "nudges",
        "cantoDrop",
        "clampedVoices",
    }
    assert "base" not in CATHEDRAL_PRELUDIO.params
    mapping = micro_velocity_to_mapping(CATHEDRAL_PRELUDIO)
    assert "base" not in mapping and "base" not in mapping["params"]
    assert not CATHEDRAL_PRELUDIO.notes and not CATHEDRAL_PRELUDIO.thumb


def test_cathedral_rule_clamps_each_inner_voice_under_the_canto() -> None:
    canto, inner = _cathedral_events()
    flat = _cathedral_flatten(canto, inner)
    offsets = {(entry.beat, entry.voice): entry.offset for entry in flat.notes}
    # voice 2: 40..70 window keeps 50 + 80 - 64 = 66, +2 nudge = 68,
    #          then min(68, canto 61 - 6) = 55.
    # voice 4: 40 + 80 - 64 = 56, +3 nudge = 59, then min(59, 55) = 55.
    assert offsets == {(0.25, 2): 5, (0.5, 4): 15}
    applied = apply_relative_offsets(inner, flat)
    assert [(event.voice, event.velocity) for event in applied] == [(2, 55), (4, 55)]


def _targets(
    flat: MicroVelocity, inner: Sequence[NoteEvent]
) -> list[tuple[int, int | None]]:
    applied = apply_relative_offsets(inner, flat)
    return [(event.voice, event.velocity) for event in applied]


def test_cathedral_rule_target_moves_with_the_canto() -> None:
    canto, inner = _cathedral_events()
    high = NoteEvent(
        bar=0,
        beat=0.0,
        midi=76,
        duration_beats=1.5,
        voice=1,
        velocity=90,
    )
    clamped = _cathedral_flatten(canto, inner)
    free = _cathedral_flatten(high, inner)
    assert _targets(clamped, inner) == [(2, 55), (4, 55)]
    assert _targets(free, inner) == [(2, 68), (4, 59)]
    assert _targets(free, inner) != _targets(clamped, inner)


def test_cathedral_rule_skips_a_tail_outside_a_full_cell() -> None:
    tail = [
        NoteEvent(
            bar=1, beat=2.25, midi=59, duration_beats=0.25, voice=2, velocity=50
        )
    ]
    centres = NEUTRAL_LEVELS["catedral_preludio"]
    assert isinstance(centres, dict)
    flat = flatten_rule(
        CATHEDRAL_PRELUDIO,
        tail,
        base_at=lambda event: centres.get(event.voice),
        raw_at=lambda event: 64,
        canto_at=lambda event: 60,
        beats_per_bar=3,
    )
    assert flat.notes == ()


def test_cathedral_rule_requires_its_context() -> None:
    _canto, inner = _cathedral_events()
    with pytest.raises(ValueError, match="beats_per_bar"):
        flatten_rule(CATHEDRAL_PRELUDIO, inner)
    with pytest.raises(ValueError, match="phrase raw"):
        flatten_rule(CATHEDRAL_PRELUDIO, inner, beats_per_bar=4)
    with pytest.raises(ValueError, match="covering canto"):
        flatten_rule(CATHEDRAL_PRELUDIO, inner, beats_per_bar=4, raw_at=lambda e: 64)
    with pytest.raises(ValueError, match="role centre"):
        flatten_rule(
            CATHEDRAL_PRELUDIO,
            inner,
            beats_per_bar=4,
            raw_at=lambda e: 64,
            canto_at=lambda e: 60,
        )


def test_covering_canto_is_half_open_and_voice_scoped() -> None:
    canto, _inner = _cathedral_events()
    assert covering_canto([canto], 0, 1.49) == 61
    assert covering_canto([canto], 0, 1.5) is None
    assert covering_canto([canto], 0, 0.0) == 61
    assert covering_canto([canto], 1, 0.0) is None
    assert covering_canto([canto], 0, 0.0, voice=2) is None


# ---------------------------------------------------------------------------
# contour data itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(DEFAULT_CONTOURS))
def test_default_contours_round_trip_and_validate(name: str) -> None:
    contour = DEFAULT_CONTOURS[name]
    assert validate_micro_velocity(contour) == ()
    mapping = micro_velocity_to_mapping(contour)
    assert parse_micro_velocity(mapping) == contour


def test_tremolo_contours_are_bounded_by_their_meter() -> None:
    assert TREMOLO_CONTOURS == {"4/4": TREMOLO_44, "3/4": TREMOLO_34}
    assert validate_micro_velocity(TREMOLO_44, bars=1, beats_per_bar=4) == ()
    assert validate_micro_velocity(TREMOLO_34, bars=1, beats_per_bar=3) == ()
    assert validate_micro_velocity(ETUDE1, bars=1, beats_per_bar=4) == ()
    # The 4/4 arch does not fit a 3/4 bar; the 3/4 contour fits either.
    assert validate_micro_velocity(TREMOLO_44, bars=1, beats_per_bar=3)
    assert validate_micro_velocity(TREMOLO_34, bars=1, beats_per_bar=3) == ()
    assert validate_micro_velocity(TREMOLO_34, bars=1, beats_per_bar=4) == ()


def test_tremolo_thumb_lanes_are_distinct_per_meter() -> None:
    four = {
        (entry.bar, entry.beat, entry.voice): entry.offset
        for entry in (*TREMOLO_44.notes, *TREMOLO_44.thumb)
    }
    three = {
        (entry.bar, entry.beat, entry.voice): entry.offset
        for entry in (*TREMOLO_34.notes, *TREMOLO_34.thumb)
    }
    assert four[(0, 0.0, 3)] == three[(0, 0.0, 3)] == -4
    assert four[(0, 2.0, 3)] == 4
    assert four[(0, 3.0, 3)] == 1
    assert three[(0, 2.0, 3)] == 0
    assert {entry.beat for entry in TREMOLO_44.thumb} == {0.0, 1.0, 2.0, 3.0}
    assert {entry.beat for entry in TREMOLO_34.thumb} == {0.0, 1.0, 2.0}


def test_etude1_contour_is_the_fixed_sixteenth_arch() -> None:
    offsets = {(entry.beat, entry.voice): entry.offset for entry in ETUDE1.notes}
    assert offsets == {
        (0.25, 2): -2,
        (0.5, 2): -2,
        (0.75, 2): -2,
        (1.0, 2): 0,
        (1.25, 2): 0,
        (1.5, 2): 2,
        (2.0, 2): 2,
        (2.5, 2): 2,
        (2.75, 2): 0,
        (3.0, 2): 0,
        (3.25, 2): -2,
        (3.5, 2): -2,
        (3.75, 2): -2,
    }


def test_rules_declare_params_and_versions() -> None:
    for contour in (ETUDE11, GALOP1, GALOP2, CATHEDRAL_PRELUDIO):
        assert contour.kind == "rule"
        assert contour.rule_version == 1
        assert isinstance(contour.params, dict) and contour.params
        assert validate_micro_velocity(contour) == ()
    assert ETUDE11.rule_id == "etude11_middle"
    assert GALOP1.rule_id == "galop1"
    assert GALOP2.rule_id == "galop2"
    assert CATHEDRAL_PRELUDIO.rule_id == "catedral_preludio"
    assert set(GALOP1.params) == {"step", "floor", "peakQuarter"}
    assert set(GALOP2.params) == {"step", "floor"}
    assert CATHEDRAL_PRELUDIO.params["cantoDrop"] == 6
    assert CATHEDRAL_PRELUDIO.params["clampedVoices"] == [2, 4]


def test_neutral_levels_are_declared_for_every_extracted_family() -> None:
    assert NEUTRAL_LEVELS == {
        "tremolo": 58,
        "etude1": 52,
        "etude11": 44,
        "catedral_preludio": {2: 50, 4: 40},
    }


def test_etude11_slot_skips_off_sextuplet_attacks() -> None:
    assert _etude11_slot(1 / 6) == 1
    assert _etude11_slot(0.25) is None
    assert _etude11_slot(1.5) == 3


def test_flatten_rule_refuses_an_unknown_rule() -> None:
    event = NoteEvent(
        bar=0, beat=0.0, midi=60, duration_beats=1.0, voice=1, velocity=64
    )
    with pytest.raises(ValueError, match="unsupported rule id"):
        flatten_rule(
            MicroVelocity(kind="rule", rule_id="nope", rule_version=1, params={"x": 1}),
            [event],
        )
    with pytest.raises(ValueError, match="kind 'rule'"):
        flatten_rule(ETUDE1, [event])


# ---------------------------------------------------------------------------
# empty / absent contours and inert import
# ---------------------------------------------------------------------------


def test_absent_and_empty_contours_leave_events_identical() -> None:
    events = [
        NoteEvent(
            bar=0, beat=0.0, midi=64, duration_beats=1.0, voice=1, velocity=71
        ),
        NoteEvent(
            bar=0, beat=1.0, midi=60, duration_beats=1.0, voice=3, velocity=48
        ),
    ]
    assert is_empty(None)
    assert is_empty(EMPTY_MICRO_VELOCITY)
    original = list(events)
    for contour in (None, EMPTY_MICRO_VELOCITY):
        result = apply_relative_offsets(events, contour)
        assert result == events
        assert events == original
        assert len(result) == len(events)
        for actual, expected in zip(result, events):
            assert actual == expected


def test_importing_the_contours_is_inert_on_the_production_render() -> None:
    assert build_manifest() == _committed()
