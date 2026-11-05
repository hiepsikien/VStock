"""Extraction harness for the default micro-velocity contours.

The golden artifact stores `render_patterned_voices` events after the guitar
wave and before humanize. The hardcoded contours live inside the figure
writers, so this harness proves the extraction in two steps:

1. Wrap the figure writer for the fixture. Rebuild its pre-wave output from a
   neutral written level plus the data contour, and assert the rebuilt events
   equal the writer's real output event-for-event.
2. Return the rebuilt events into the unchanged production pipeline (wave,
   snaps/stabs/trim, humanize) and compare the final fixture row, voices and
   digests to `fixtures/micro_velocity_golden.json`.

Step 1 is not a subtract-and-add trick: the neutral level is a declared
writer constant (58 for Tremolo, 52 for Étude No. 1, 44 for Étude No. 11, and
the 50/40 inner role centres for Cathedral Preludio) and the offsets are the
data under test. Galop flattens from the bar's written peak, Étude No. 11 from
the written hairpin, and Cathedral Preludio from the covering canto plus the
phrase raw level; each must reproduce the hardcoded contour function from the
same neutral input.

Nothing here changes production code: the wrappers exist only inside the
`patched_contours()` context.
"""

from __future__ import annotations

import json
import math
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from unittest.mock import patch

from app.sonify import guitar_patterns, guitar_sor
from app.sonify.form import active_meter
from app.sonify.micro_velocity_contours import (
    CATHEDRAL_PRELUDIO,
    ETUDE1,
    ETUDE11,
    GALOP1,
    GALOP2,
    NEUTRAL_LEVELS,
    TREMOLO_34,
    TREMOLO_44,
    UNEXTRACTED_REASONS,
    apply_flattened_rule,
    covering_canto,
)
from app.sonify.model import NoteEvent
from app.studio.micro_velocity import MicroVelocity, apply_relative_offsets
from tests.micro_velocity_golden import (
    EVENT_FIELDS,
    FIXTURES,
    build_fixture,
)

FIXTURE = Path(__file__).parent / "fixtures" / "micro_velocity_golden.json"

EXTRACTED_FIXTURES: tuple[str, ...] = (
    "tremolo_44",
    "tremolo_34",
    "etude1",
    "etude11",
    "galop_1",
    "galop_2",
    "catedral_preludio",
)


# ---------------------------------------------------------------------------
# result value
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Verification:
    """One fixture rendered through data-driven contours."""

    fixture_id: str
    actual: Mapping[str, Any]
    expected: Mapping[str, Any]

    @property
    def exact(self) -> bool:
        return dict(self.actual) == dict(self.expected)

    @property
    def notes_digest(self) -> str:
        return str(self.actual.get("notes_digest"))

    @property
    def expected_notes_digest(self) -> str:
        return str(self.expected.get("notes_digest"))

    @property
    def score_digest(self) -> str:
        return str(self.actual.get("score_digest"))

    @property
    def expected_score_digest(self) -> str:
        return str(self.expected.get("score_digest"))

    def first_mismatch(self) -> str | None:
        """A reviewable diff, or None when every compared field matches."""
        for key in ("patterns", "divisions", "note_counts"):
            if self.actual.get(key) != self.expected.get(key):
                return (
                    f"{self.fixture_id}.{key}: "
                    f"{self.actual.get(key)!r} != {self.expected.get(key)!r}"
                )
        for digest_key in ("fixture_digest", "notes_digest", "score_digest"):
            if self.actual.get(digest_key) != self.expected.get(digest_key):
                return (
                    f"{self.fixture_id}.{digest_key}: "
                    f"{self.actual.get(digest_key)!r} != "
                    f"{self.expected.get(digest_key)!r}"
                )
        for voice in ("lead", "support", "low"):
            want = self.expected["voices"][voice]
            got = self.actual["voices"][voice]
            if len(got) != len(want):
                return (
                    f"{self.fixture_id} voice {voice}: length {len(got)} "
                    f"!= expected {len(want)}"
                )
            for index, (actual, expected) in enumerate(zip(got, want)):
                if actual == expected:
                    continue
                return (
                    f"{self.fixture_id} voice {voice} first difference at "
                    f"index {index}\n  expected {EVENT_FIELDS}\n           "
                    f"{expected!r}\n  actual   {EVENT_FIELDS}\n           "
                    f"{actual!r}"
                )
        return None


# ---------------------------------------------------------------------------
# public verification
# ---------------------------------------------------------------------------


def verify_fixture(fixture_id: str) -> Verification:
    """Render one golden fixture through its extracted contour.

    Raises ``KeyError`` for a fixture that has no extraction; the caller should
    consult :data:`UNEXTRACTED_REASONS` instead of fabricating offsets.
    """
    recipe = _recipe(fixture_id)
    figure = str(recipe["figure"])
    if figure not in {
        "tremolo",
        "etude1",
        "etude11",
        "galop1",
        "galop2",
        "catedral_preludio",
    }:
        raise KeyError(f"{fixture_id}: no extracted contour for figure {figure!r}")
    expected = _expected()[fixture_id]
    with patched_contours(figure):
        actual = build_fixture(recipe)
    return Verification(fixture_id=fixture_id, actual=actual, expected=expected)


def unextracted_reason(fixture_id: str) -> str:
    """The precise reason a golden fixture has no extracted contour."""
    figure = str(_recipe(fixture_id)["figure"])
    try:
        return UNEXTRACTED_REASONS[figure]
    except KeyError as error:
        raise KeyError(f"{fixture_id}: no unextracted reason for {figure!r}") from error


# ---------------------------------------------------------------------------
# fixture plumbing
# ---------------------------------------------------------------------------


def _recipe(fixture_id: str) -> Mapping[str, Any]:
    for recipe in FIXTURES:
        if recipe["id"] == fixture_id:
            return recipe
    raise KeyError(f"unknown fixture id {fixture_id!r}")


def _expected() -> dict[str, dict[str, Any]]:
    if not FIXTURE.exists():
        raise FileNotFoundError(f"missing golden artifact {FIXTURE}")
    manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {row["id"]: row for row in manifest["fixtures"]}


# ---------------------------------------------------------------------------
# patched figure writers
# ---------------------------------------------------------------------------

_ORIGINAL_TREMOLO = guitar_patterns._tremolo
_ORIGINAL_ETUDE1 = guitar_patterns._render_etude1_bar
_ORIGINAL_ETUDE11 = guitar_patterns._render_etude11_bar
_ORIGINAL_GALOP1 = guitar_sor._contour_galop1
_ORIGINAL_GALOP2 = guitar_sor._contour_galop2
_ORIGINAL_CATEDRAL = guitar_patterns._render_catedral_preludio_bar


@contextmanager
def patched_contours(figure: str) -> Iterator[None]:
    """Install the contour reconstruction for one figure, then restore it."""
    with ExitStack() as stack:
        if figure == "tremolo":
            stack.enter_context(patch.object(guitar_patterns, "_tremolo", _tremolo_contour))
        elif figure == "etude1":
            stack.enter_context(
                patch.object(guitar_patterns, "_render_etude1_bar", _etude1_contour)
            )
        elif figure == "etude11":
            stack.enter_context(
                patch.object(guitar_patterns, "_render_etude11_bar", _etude11_contour)
            )
        elif figure in {"galop1", "galop2"}:
            stack.enter_context(
                patch.object(
                    guitar_sor,
                    "_contour_galop1",
                    _galop_contour(_ORIGINAL_GALOP1, GALOP1),
                )
            )
            stack.enter_context(
                patch.object(
                    guitar_sor,
                    "_contour_galop2",
                    _galop_contour(_ORIGINAL_GALOP2, GALOP2),
                )
            )
        elif figure == "catedral_preludio":
            stack.enter_context(
                patch.object(
                    guitar_patterns,
                    "_render_catedral_preludio_bar",
                    _catedral_contour(_ORIGINAL_CATEDRAL),
                )
            )
        else:
            raise KeyError(f"no contour patch for figure {figure!r}")
        yield


def _tremolo_contour(*args: Any, **kwargs: Any):
    lead, inner, bass = _ORIGINAL_TREMOLO(*args, **kwargs)
    quarters = max(1, active_meter().eighths_per_bar // 2)
    contour = TREMOLO_44 if quarters >= 4 else TREMOLO_34
    base = NEUTRAL_LEVELS["tremolo"]
    rebuilt = tuple(
        _apply_per_bar(_neutralize(events, base), contour)
        for events in (lead, inner, bass)
    )
    _assert_same("tremolo", (lead, inner, bass), rebuilt)
    return rebuilt


def _etude1_contour(ctx, bar: int, phrase, breathe: bool):
    lead, support, low = _ORIGINAL_ETUDE1(ctx, bar, phrase, breathe)
    rebuilt = apply_relative_offsets(
        _neutralize(support, NEUTRAL_LEVELS["etude1"]),
        ETUDE1,
        origin_bar=bar,
    )
    _assert_same("etude1", (support,), (rebuilt,))
    return lead, rebuilt, low


def _etude11_contour(ctx, bar: int, phrase, breathe: bool):
    lead, support, low = _ORIGINAL_ETUDE11(ctx, bar, phrase, breathe)
    hairpins = {
        int(round(event.beat)): event.velocity
        for event in lead
        if event.midi is not None
        and event.velocity is not None
        and event.accent
        and abs(event.beat - round(event.beat)) <= 1e-9
    }

    def hairpin_at(event: NoteEvent) -> int | None:
        return hairpins.get(int(math.floor(event.beat + 1e-9)))

    def band_at(event: NoteEvent) -> str | None:
        return ctx.band(event.bar)

    base = NEUTRAL_LEVELS["etude11"]
    rebuilt = apply_flattened_rule(
        _neutralize(support, base),
        ETUDE11,
        origin_bar=bar,
        base_at=lambda event: base,
        hairpin_at=hairpin_at,
        band_at=band_at,
    )
    _assert_same("etude11", (support,), (rebuilt,))
    return lead, rebuilt, low


def _galop_contour(original, contour: MicroVelocity):
    def wrapper(lead: Sequence[NoteEvent], low: Sequence[NoteEvent]):
        expected = original(lead, low)
        peak = max(
            (
                event.velocity
                for event in lead
                if event.midi is not None and event.velocity is not None
            ),
            default=None,
        )
        if peak is None:
            return expected
        origin = lead[0].bar
        rebuilt_lead = apply_flattened_rule(
            lead,
            contour,
            origin_bar=origin,
            peak=peak,
            base_at=lambda event: event.velocity,
        )
        rebuilt_low = (
            apply_flattened_rule(
                low,
                contour,
                origin_bar=origin,
                peak=peak,
                base_at=lambda event: event.velocity,
            )
            if low
            else []
        )
        _assert_same(
            contour.rule_id or "galop",
            (expected[0], expected[1]),
            (rebuilt_lead, rebuilt_low),
        )
        return rebuilt_lead, rebuilt_low

    return wrapper


def _catedral_contour(original):
    """Rebuild the Preludio inner voices from role centres plus the rule.

    The canto is read from the writer's own lead events and the phrase level
    from the writer's plan, so the rule never stores a bar plan. Inner events
    are neutralised to their role centres first; the contour then supplies the
    phrase swell, the cell nudge and the cross-voice clamp.
    """

    def wrapper(ctx, bar: int, patterns, apex, phrase):
        lead, support = original(ctx, bar, patterns, apex, phrase)
        centres = NEUTRAL_LEVELS["catedral_preludio"]
        if not isinstance(centres, Mapping):
            raise TypeError("catedral_preludio needs per-voice neutral levels")
        neutral = [
            replace(event, velocity=centres[event.voice])
            if event.midi is not None
            and event.velocity is not None
            and event.voice in centres
            else event
            for event in support
        ]
        epb = ctx.epb

        def raw_at(event: NoteEvent) -> int | None:
            attack = event.bar * epb + int(math.floor(event.beat * 2 + 1e-9))
            return guitar_patterns._note_velocity(attack, 1, apex, phrase)

        def canto_at(event: NoteEvent) -> int | None:
            return covering_canto(lead, event.bar, event.beat)

        rebuilt = apply_flattened_rule(
            neutral,
            CATHEDRAL_PRELUDIO,
            origin_bar=bar,
            base_at=lambda event: centres.get(event.voice),
            raw_at=raw_at,
            canto_at=canto_at,
            beats_per_bar=ctx.epb / 2,
        )
        _assert_same("catedral_preludio", (support,), (rebuilt,))
        return lead, rebuilt

    return wrapper


# ---------------------------------------------------------------------------
# event helpers
# ---------------------------------------------------------------------------


def _neutralize(events: Sequence[NoteEvent], base: int) -> list[NoteEvent]:
    return [
        replace(event, velocity=base)
        if event.midi is not None and event.velocity is not None
        else event
        for event in events
    ]


def _apply_per_bar(
    events: Sequence[NoteEvent], contour: MicroVelocity
) -> list[NoteEvent]:
    """Apply a one-bar contour to every occurrence, preserving event order."""
    result = list(events)
    for bar in sorted({event.bar for event in result}):
        indexes = [index for index, event in enumerate(result) if event.bar == bar]
        group = [result[index] for index in indexes]
        updated = apply_relative_offsets(group, contour, origin_bar=bar)
        for index, event in zip(indexes, updated):
            result[index] = event
    return result


def _assert_same(
    label: str,
    expected_groups: Sequence[Sequence[NoteEvent]],
    actual_groups: Sequence[Sequence[NoteEvent]],
) -> None:
    """Fail at the pre-wave boundary if the contour lost any event detail."""
    for group_index, (expected, actual) in enumerate(
        zip(expected_groups, actual_groups)
    ):
        if len(expected) != len(actual):
            raise AssertionError(
                f"{label} group {group_index}: rebuilt {len(actual)} events, "
                f"writer emitted {len(expected)}"
            )
        for index, (want, got) in enumerate(zip(expected, actual)):
            if want == got:
                continue
            raise AssertionError(
                f"{label} group {group_index}: pre-wave difference at index "
                f"{index}\n  writer    {want!r}\n  contour   {got!r}"
            )


__all__ = [
    "EXTRACTED_FIXTURES",
    "Verification",
    "patched_contours",
    "unextracted_reason",
    "verify_fixture",
]
