"""Slot/texture micro-velocity overrides on the gated production sentences.

The plan-slot seam keeps the authored slot index, origin, and contour without
changing `plan_sentence`. A gated sentence hands those contours to
`apply_default_contours`, which applies the figure default first, then the slot
override, then the texture override, all before the volume wave. Every applied
contour is recorded so the pinned check still runs after the absolute writers.

These tests pin:

* `plan_slots` covers the same bars as `plan_sentence` and keeps the origin;
* a slot override changes only that slot's occurrences;
* offset 0 and the canonical empty contour are byte-identical;
* a pinned slot entry is checked after the wave;
* Suite, Villa, and Brouwer all carry the override through their own gate;
* the figure/slot/texture order is the documented one;
* no test leaves a sentence in the global registry.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

import app.sonify.guitar_brouwer_production as brouwer
import app.sonify.guitar_suite_mazurka as suite
import app.sonify.guitar_villa_production as villa
from app.sonify import production_flags as flags
from app.sonify import sentence_specs as specs
from app.sonify.form import METER_34, METER_44, FormSection, FormSpec
from app.sonify.micro_velocity_writer import WriterContourError
from app.sonify.model import Bar, NoteEvent
from app.sonify.params import compose_params
from app.sonify.render import render
from app.sonify.sentence_production import (
    SentenceVoices,
    apply_default_contours,
)
from app.studio.micro_velocity import (
    EMPTY_MICRO_VELOCITY,
    MicroVelocity,
    VelocityOffset,
)


@pytest.fixture(autouse=True)
def _registry_does_not_leak():
    before = dict(specs.SENTENCE_SPECS)
    yield
    assert dict(specs.SENTENCE_SPECS) == before


def _bars(count: int) -> list[Bar]:
    """Enough source bars that every musical bar has a moving close."""
    return [Bar(100.0 + (index % 4) * 40, 250.0) for index in range(count * 4)]


def _form(bars: int, meter) -> FormSpec:
    return FormSpec(
        bars,
        120,
        (FormSection(0, bars, "phrase", 0),),
        meter=meter,
    )


def _render(ensemble: str, meter, bars: int):
    with compose_params({}):
        return render(
            _bars(bars),
            variant="guitar",
            ensemble=ensemble,
            form=_form(bars, meter),
            framed=True,
        )


def _digest(score) -> str:
    payload = [
        (
            event.voice,
            event.bar,
            round(event.beat, 6),
            round(event.duration_beats, 6),
            event.midi,
            event.velocity,
            event.tie_start,
            event.tie_stop,
        )
        for voice in (score.lead, score.comp, score.bass)
        for event in voice
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _by_bar(score) -> dict[int, list[tuple]]:
    found: dict[int, list[tuple]] = {}
    for voice in (score.lead, score.comp, score.bass):
        for event in voice:
            found.setdefault(event.bar, []).append(
                (
                    event.voice,
                    round(event.beat, 6),
                    round(event.duration_beats, 6),
                    event.midi,
                    event.velocity,
                    event.tie_start,
                    event.tie_stop,
                )
            )
    return found


def _contour(offset: int) -> MicroVelocity:
    return MicroVelocity(
        notes=(VelocityOffset(bar=0, beat=0.0, voice=1, offset=offset),)
    )


def _with_slot_contour(
    spec: specs.SentenceSpec,
    slot_index: int,
    contour: MicroVelocity | None,
) -> specs.SentenceSpec:
    slots = list(spec.slots)
    slots[slot_index] = replace(slots[slot_index], micro_velocity=contour)
    return dataclasses.replace(spec, slots=tuple(slots))


@contextmanager
def _installed(monkeypatch, module: Any, spec: specs.SentenceSpec):
    """Install one authored spec, bypassing the module's own fixed candidate.

    This mirrors what a future production candidate will do; the module's
    `ensure_registered` is pinned to a no-op so a different spec at the key is
    not treated as a shadowing error.
    """
    key = _registry_key(
        module, "VILLA_KEY", "SUITE_MAZURKA_KEY", "BROUWER_KEY"
    )
    previous = specs.SENTENCE_SPECS.get(key)
    monkeypatch.setattr(module, "ensure_registered", lambda: False)
    specs.SENTENCE_SPECS[key] = (spec,)
    try:
        yield
    finally:
        if previous is None:
            specs.SENTENCE_SPECS.pop(key, None)
        else:
            specs.SENTENCE_SPECS[key] = previous


def _registry_key(module: Any, *names: str) -> Any:
    for name in names:
        if hasattr(module, name):
            return getattr(module, name)
    raise AssertionError(f"{module!r} has none of {names}")


def _changed_bars(
    pattern: str, meter: str, bars: int, slot_index: int
) -> list[int]:
    planned = specs.plan_slots(pattern, meter, bars, 0)
    assert planned is not None
    return sorted(
        {
            bar
            for slot in planned
            if slot.slot_index == slot_index
            for bar in slot.bars
        }
    )


# ---------------------------------------------------------------------------
# Plan seam
# ---------------------------------------------------------------------------


def test_plan_slots_matches_plan_sentence_and_keeps_the_origin() -> None:
    with villa.use_villa_aba(True):
        spans = specs.plan_sentence("villa_pattern", "4/4", 6, 0)
        planned = specs.plan_slots("villa_pattern", "4/4", 6, 0)

    assert spans is not None and planned is not None
    assert [
        (slot.figure, slot.bars) for slot in planned
    ] == spans
    assert [
        (slot.slot_index, slot.slot_start) for slot in planned
    ] == [(0, 0), (1, 1), (2, 2), (0, 3), (1, 4), (2, 5)]


def test_plan_slots_returns_none_for_an_unregistered_pair() -> None:
    assert specs.plan_slots("no_such_pattern", "4/4", 6, 0) is None


def test_plan_slots_carries_the_authored_contour_per_occurrence() -> None:
    contour = _contour(10)
    slots = list(villa.VILLA_ABA.slots)
    slots[1] = replace(slots[1], micro_velocity=contour)
    spec = dataclasses.replace(villa.VILLA_ABA, slots=tuple(slots))
    registry = {("villa_pattern", "4/4"): (spec,)}

    planned = specs.plan_slots(
        "villa_pattern", "4/4", 6, 0, registry=registry
    )

    assert planned is not None
    carried = [
        (slot.slot_index, slot.slot_start, slot.micro_velocity)
        for slot in planned
        if slot.micro_velocity is not None
    ]
    assert carried == [(1, 1, contour), (1, 4, contour)]


# ---------------------------------------------------------------------------
# Production overrides
# ---------------------------------------------------------------------------


GATED = (
    pytest.param(
        villa,
        villa.VILLA_ABA,
        "villa",
        METER_44,
        6,
        1,
        flags.use_villa_production,
        "villa_pattern",
        "4/4",
        id="villa",
    ),
    pytest.param(
        suite,
        suite.SUITE_MAZURKA_AABA,
        "villa",
        METER_34,
        8,
        2,
        flags.use_suite_mazurka,
        suite.SUITE_MAZURKA_PATTERN,
        suite.SUITE_MAZURKA_METER,
        id="suite_mazurka",
    ),
    pytest.param(
        brouwer,
        brouwer.BROUWER_ABA,
        "brouwer",
        METER_44,
        6,
        1,
        flags.use_brouwer_production,
        "brouwer_etude",
        "4/4",
        id="brouwer",
    ),
)


@pytest.mark.parametrize(
    (
        "module",
        "spec",
        "ensemble",
        "meter",
        "bars",
        "slot_index",
        "flag_context",
        "pattern",
        "pattern_meter",
    ),
    GATED,
)
def test_slot_override_changes_only_its_occurrences(
    monkeypatch,
    module,
    spec,
    ensemble,
    meter,
    bars,
    slot_index,
    flag_context,
    pattern,
    pattern_meter,
) -> None:
    monkeypatch.setenv("VSTOCK_MICRO_VELOCITY_WRITERS", "on")
    with flag_context(True):
        with _installed(monkeypatch, module, spec):
            base = _render(ensemble, meter, bars)
        with _installed(
            monkeypatch,
            module,
            _with_slot_contour(spec, slot_index, _contour(10)),
        ):
            changed = _render(ensemble, meter, bars)
            changed_bars = _changed_bars(
                pattern, pattern_meter, bars, slot_index
            )

    assert changed_bars

    base_bars = _by_bar(base)
    changed_by_bar = _by_bar(changed)
    assert sorted(base_bars) == sorted(changed_by_bar)

    for bar, events in base_bars.items():
        if bar not in changed_bars:
            assert changed_by_bar[bar] == events, bar

    for bar in changed_bars:
        assert len(changed_by_bar[bar]) == len(base_bars[bar]), bar
        # The override is velocity-only; pitch, rhythm, and ties stay put.
        assert [
            event[:4] + event[5:] for event in changed_by_bar[bar]
        ] == [event[:4] + event[5:] for event in base_bars[bar]], bar
        assert changed_by_bar[bar] != base_bars[bar], bar
        lead = [event for event in base_bars[bar] if event[0] == 1]
        assert lead, bar
        leading = [event for event in changed_by_bar[bar] if event[0] == 1]
        assert all(
            after[4] >= before[4] for before, after in zip(lead, leading)
        ), bar
        assert any(
            after[4] > before[4] for before, after in zip(lead, leading)
        ), bar


def test_offset_zero_is_byte_identical(monkeypatch) -> None:
    monkeypatch.setenv("VSTOCK_MICRO_VELOCITY_WRITERS", "on")
    with flags.use_villa_production(True):
        with _installed(monkeypatch, villa, villa.VILLA_ABA):
            base = _render("villa", METER_44, 6)
        with _installed(
            monkeypatch,
            villa,
            _with_slot_contour(villa.VILLA_ABA, 1, _contour(0)),
        ):
            zero = _render("villa", METER_44, 6)
    assert _digest(zero) == _digest(base)


def test_pinned_slot_contour_is_checked_after_the_wave(monkeypatch) -> None:
    monkeypatch.setenv("VSTOCK_MICRO_VELOCITY_WRITERS", "on")
    pinned = MicroVelocity(
        notes=(
            VelocityOffset(
                bar=0, beat=0.0, voice=1, pinned=True, velocity=1
            ),
        )
    )
    with flags.use_villa_production(True):
        with _installed(
            monkeypatch,
            villa,
            _with_slot_contour(villa.VILLA_ABA, 1, pinned),
        ):
            with pytest.raises(WriterContourError, match="pinned velocity 1"):
                _render("villa", METER_44, 6)


def test_default_contours_stay_off_when_writers_are_off(monkeypatch) -> None:
    monkeypatch.delenv("VSTOCK_MICRO_VELOCITY_WRITERS", raising=False)
    with flags.use_villa_production(True):
        with _installed(monkeypatch, villa, villa.VILLA_ABA):
            base = _render("villa", METER_44, 6)
        with _installed(
            monkeypatch,
            villa,
            _with_slot_contour(villa.VILLA_ABA, 1, _contour(10)),
        ):
            off = _render("villa", METER_44, 6)
    assert _digest(off) == _digest(base)


# ---------------------------------------------------------------------------
# Layer order and the canonical empty contour
# ---------------------------------------------------------------------------


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        kind="4/4",
        bars=1,
        epb=8,
        band=lambda _bar: "mf",
    )


def _voices(
    *,
    contours: dict[int, str] | None = None,
    slot_contours: dict[int, MicroVelocity] | None = None,
    texture_contour: MicroVelocity | None = None,
) -> SentenceVoices:
    lead = [
        NoteEvent(bar=0, beat=0.0, midi=64, duration_beats=1.0, voice=1, velocity=64)
    ]
    support = [
        NoteEvent(
            bar=0,
            beat=0.25,
            midi=59,
            duration_beats=0.25,
            voice=2,
            velocity=64,
        )
    ]
    low = [
        NoteEvent(bar=0, beat=0.0, midi=40, duration_beats=1.0, voice=3, velocity=64)
    ]
    return SentenceVoices(
        lead,
        support,
        low,
        {0: 1},
        contours=contours or {},
        slot_contours=slot_contours or {},
        texture_contour=texture_contour,
    )


def _voice2(offset: int) -> MicroVelocity:
    return MicroVelocity(
        notes=(VelocityOffset(bar=0, beat=0.25, voice=2, offset=offset),)
    )


def test_figure_default_then_slot_then_texture_order() -> None:
    voices = _voices(
        contours={0: "etude1"},
        slot_contours={0: _voice2(10)},
        texture_contour=_voice2(5),
    )
    lead, support, low = apply_default_contours(_ctx(), voices, enabled=True)

    # Étude No. 1 neutral 52 plus arc -2 = 50, then slot +10, then texture +5.
    assert support[0].velocity == 65
    assert lead[0].velocity == 64
    assert low[0].velocity == 64


def test_canonical_empty_slot_and_texture_contours_are_identical() -> None:
    plain = _voices()
    empty = _voices(
        slot_contours={0: EMPTY_MICRO_VELOCITY},
        texture_contour=EMPTY_MICRO_VELOCITY,
    )
    before = apply_default_contours(_ctx(), plain, enabled=True)
    after = apply_default_contours(_ctx(), empty, enabled=True)
    assert after == before
