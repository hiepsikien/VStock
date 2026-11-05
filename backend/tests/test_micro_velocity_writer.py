"""Feature-gated writer integration for the extracted micro-velocity contours.

`app.sonify.micro_velocity_writer` switches the four extracted figure families
to their neutral written level plus the data contour in
`app.sonify.micro_velocity_contours`. The flag is read at render time and is
off by default, so the committed golden manifest must stay exact in both
states.

These tests prove:

* flag off is byte-identical to the committed baseline;
* flag on reproduces the same note events and digests with no tolerance;
* the flag parser accepts only the documented truthy spellings;
* a meter without extracted data falls back to the writer;
* pinned entries are checked after the absolute writers;
* rendering does not touch the sentence or figure registries.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.sonify import guitar_sor, guitar_torroba
from app.sonify import micro_velocity_contours as contours_module
from app.sonify.micro_velocity_contours import (
    ETUDE1,
    ETUDE11,
    GALOP1,
    GALOP2,
    TREMOLO_44,
)
from app.sonify.micro_velocity_writer import (
    WRITERS_FLAG,
    WriterContourError,
    apply_etude1,
    apply_etude11,
    apply_galop,
    apply_tremolo,
    begin_occurrences,
    check_occurrences,
    record_occurrence,
    reset_occurrences,
    writers_enabled,
)
from app.sonify.model import NoteEvent
from app.sonify.sentence_specs import SENTENCE_SPECS
from app.studio.micro_velocity import MicroVelocity, VelocityOffset
from tests.micro_velocity_golden import FIXTURES, build_fixture, build_manifest

FIXTURE = Path(__file__).parent / "fixtures" / "micro_velocity_golden.json"
EXTRACTED = ("tremolo_44", "tremolo_34", "etude1", "etude11", "galop_1", "galop_2")
EXPECTED_PATTERN = {
    "tremolo_44": "tremolo",
    "tremolo_34": "tremolo",
    "etude1": "etude1",
    "etude11": "etude11",
    "galop_1": "galop",
    "galop_2": "galop",
}


def _committed() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _rows(manifest: dict) -> dict[str, dict]:
    return {row["id"]: row for row in manifest["fixtures"]}


def _event(
    bar: int = 0,
    beat: float = 0.0,
    midi: int | None = 64,
    velocity: int | None = 64,
    voice: int = 1,
    duration: float = 1.0,
    accent: bool = False,
) -> NoteEvent:
    return NoteEvent(
        bar=bar,
        beat=beat,
        midi=midi,
        duration_beats=duration,
        voice=voice,
        velocity=None if midi is None else velocity,
        accent=accent,
    )


# ---------------------------------------------------------------------------
# flag parsing
# ---------------------------------------------------------------------------


def test_flag_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(WRITERS_FLAG, raising=False)
    assert writers_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " On "])
def test_truthy_spellings_enable_the_path(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(WRITERS_FLAG, value)
    assert writers_enabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "maybe"])
def test_other_values_keep_the_historical_path(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(WRITERS_FLAG, value)
    assert writers_enabled() is False


# ---------------------------------------------------------------------------
# exact zero-diff
# ---------------------------------------------------------------------------


def test_flag_off_matches_the_committed_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(WRITERS_FLAG, raising=False)
    assert build_manifest() == _committed()


def test_flag_on_matches_the_committed_manifest_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(WRITERS_FLAG, "1")
    assert build_manifest() == _committed()


@pytest.mark.parametrize("fixture_id", EXTRACTED)
def test_flag_on_reproduces_every_event_and_digest(
    monkeypatch: pytest.MonkeyPatch, fixture_id: str
) -> None:
    expected = _rows(_committed())[fixture_id]
    monkeypatch.setenv(WRITERS_FLAG, "1")
    actual = _rows(build_manifest())[fixture_id]

    assert actual["patterns"] == expected["patterns"]
    assert actual["divisions"] == expected["divisions"]
    assert actual["note_counts"] == expected["note_counts"]
    assert actual["notes_digest"] == expected["notes_digest"]
    assert actual["score_digest"] == expected["score_digest"]
    for voice in ("lead", "support", "low"):
        assert actual["voices"][voice] == expected["voices"][voice]


def test_flag_off_and_on_render_the_same_extracted_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(WRITERS_FLAG, raising=False)
    off = _rows(build_manifest())
    monkeypatch.setenv(WRITERS_FLAG, "1")
    on = _rows(build_manifest())
    for fixture_id in EXTRACTED:
        for voice in ("lead", "support", "low"):
            assert on[fixture_id]["voices"][voice] == off[fixture_id]["voices"][voice]
        assert on[fixture_id]["notes_digest"] == off[fixture_id]["notes_digest"]


@pytest.mark.parametrize("fixture_id", EXTRACTED)
@pytest.mark.parametrize("band", ["mp", "f"])
def test_other_bands_stay_exact_between_flag_off_and_on(
    monkeypatch: pytest.MonkeyPatch, fixture_id: str, band: str
) -> None:
    """The contours read written levels and the bar band; both paths must agree."""
    base = next(recipe for recipe in FIXTURES if recipe["id"] == fixture_id)
    recipe = {**base, "id": f"{fixture_id}_{band}", "band": band}
    monkeypatch.delenv(WRITERS_FLAG, raising=False)
    off = build_fixture(recipe)
    monkeypatch.setenv(WRITERS_FLAG, "1")
    on = build_fixture(recipe)
    assert on["patterns"] == [EXPECTED_PATTERN[fixture_id]]
    assert on == off


def test_etude11_band_nudge_matches_in_every_band(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rule reads the bar's band, not a constant; the writer must agree."""
    base = next(recipe for recipe in FIXTURES if recipe["id"] == "etude11")
    for band in ("mp", "mf", "f"):
        recipe = {**base, "id": f"etude11_{band}", "band": band}
        monkeypatch.delenv(WRITERS_FLAG, raising=False)
        off = build_fixture(recipe)
        monkeypatch.setenv(WRITERS_FLAG, "1")
        on = build_fixture(recipe)
        assert on["patterns"] == ["etude11"], band
        assert on == off, band


# ---------------------------------------------------------------------------
# writer helpers
# ---------------------------------------------------------------------------


def test_tremolo_without_extracted_meter_falls_back() -> None:
    events = [_event(midi=60, velocity=50, voice=1)]
    assert apply_tremolo(events, [], [], meter_kind="6/8") is None


def test_tremolo_applies_the_meter_contour_at_the_neutral_level() -> None:
    events = [_event(beat=0.0, midi=60, velocity=99, voice=1)]
    rebuilt = apply_tremolo(events, [], [], meter_kind="4/4")
    assert rebuilt is not None
    lead, _support, _low = rebuilt
    # Neutral 58 plus the 4/4 first-quarter thumb offset -4 and the first fill -6.
    assert lead[0].velocity == 48
    assert lead[0].midi == 60


def test_etude1_offsets_only_the_middle_voice_velocity() -> None:
    event = _event(bar=2, beat=0.25, midi=55, velocity=99, voice=2)
    rebuilt = apply_etude1([event], origin_bar=2)
    assert rebuilt[0] == replace(event, velocity=50)
    assert rebuilt[0].midi == event.midi
    assert rebuilt[0].voice == event.voice


def test_etude11_uses_the_written_hairpin_and_band() -> None:
    support = [_event(bar=1, beat=1 / 6, midi=59, velocity=44, voice=2)]
    rebuilt = apply_etude11(
        support,
        origin_bar=1,
        hairpin_at=lambda event: 60,
        band_at=lambda event: "mf",
    )
    # echo=max(44,60-8)=52, ceiling=51; shaped=min(51,max(44,60-10+0))=50;
    # tilt[1]=-1 -> 49.
    assert rebuilt[0].velocity == 49


def test_galop_rule_matches_the_hardcoded_step_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(WRITERS_FLAG, "0")
    lead = [
        _event(beat=0.0, midi=64, velocity=60, duration=0.25),
        _event(beat=0.25, midi=64, velocity=60, duration=0.25),
        _event(beat=3.0, midi=64, velocity=60, duration=0.25),
    ]
    low = [_event(beat=0.0, midi=40, velocity=56, voice=3, duration=0.5)]
    expected = guitar_sor._contour_galop1(list(lead), list(low))
    actual = apply_galop(lead, low, rule_id="galop1")
    assert actual == expected


# ---------------------------------------------------------------------------
# pinned checks
# ---------------------------------------------------------------------------


def test_pinned_occurrence_is_checked_against_the_final_events() -> None:
    contour = MicroVelocity(
        notes=(VelocityOffset(bar=0, beat=0.0, voice=1, pinned=True, velocity=70),)
    )
    token = begin_occurrences()
    record_occurrence(contour, 0)
    try:
        with pytest.raises(WriterContourError, match="pinned velocity 70"):
            check_occurrences([_event(velocity=66)])
    finally:
        reset_occurrences(token)


def test_pinned_occurrence_passes_on_the_absolute_writer_level() -> None:
    contour = MicroVelocity(
        notes=(VelocityOffset(bar=0, beat=0.0, voice=1, pinned=True, velocity=70),)
    )
    token = begin_occurrences()
    record_occurrence(contour, 2)
    try:
        assert check_occurrences([_event(bar=2, velocity=70)]) is None
    finally:
        reset_occurrences(token)


def test_default_contours_carry_no_pinned_entries() -> None:
    for contour in (TREMOLO_44, ETUDE1, ETUDE11, GALOP1, GALOP2):
        assert all(not entry.pinned for entry in (*contour.notes, *contour.thumb))


def test_a_pinned_entry_is_checked_after_the_absolute_writers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The render checks the recorded occurrence against the post-fan events."""
    pinned = MicroVelocity(
        thumb=(VelocityOffset(bar=0, beat=0.0, voice=3, pinned=True, velocity=1),)
    )
    monkeypatch.setitem(contours_module.TREMOLO_CONTOURS, "4/4", pinned)
    monkeypatch.setenv(WRITERS_FLAG, "1")
    recipe = next(recipe for recipe in FIXTURES if recipe["id"] == "tremolo_44")
    with pytest.raises(WriterContourError, match="pinned velocity 1"):
        build_fixture(recipe)


# ---------------------------------------------------------------------------
# inert registries
# ---------------------------------------------------------------------------


def test_render_does_not_touch_the_sentence_or_figure_registries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(WRITERS_FLAG, "1")
    sentences = copy.deepcopy(SENTENCE_SPECS)
    figures = copy.deepcopy(guitar_torroba._FIGURES)
    build_manifest()
    assert SENTENCE_SPECS == sentences
    assert guitar_torroba._FIGURES == figures
