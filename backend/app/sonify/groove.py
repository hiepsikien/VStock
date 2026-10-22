"""Per-bar groove flags for market character. Empty when a render passes no character."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from app.sonify.form import METER_44, FormSpec
from app.sonify.keys import MovementCharacter

VariantName = str


@dataclass(frozen=True)
class BarGroove:
    tresillo: bool = False
    syncopate: bool = False
    chromatic: bool = False
    half: bool = False
    calm: bool = False
    volatile: bool = False
    rally: bool = False
    selloff: bool = False
    caesura: bool = False
    trio_thin: bool = False


_GROOVE: ContextVar[dict[int, BarGroove]] = ContextVar("sonify_groove", default={})


def groove_at(bar: int) -> BarGroove:
    return _GROOVE.get().get(bar, BarGroove())


@contextmanager
def compose_groove(plan: dict[int, BarGroove]):
    token = _GROOVE.set(plan)
    try:
        yield
    finally:
        _GROOVE.reset(token)


def build_groove(
    spec: FormSpec | None,
    windows: Sequence[tuple[int, int]],
    bands: Sequence[str],
    variant: VariantName,
    character: MovementCharacter | None,
    character_at: Sequence[MovementCharacter | None] | None = None,
    regimes: Sequence[str] | None = None,
) -> dict[int, BarGroove]:
    """Flags a bar only when that bar has a character. `None` leaves the written patterns alone."""
    if character is None and not character_at:
        return {}
    meter = METER_44 if spec is None else spec.meter
    bars = 30 if spec is None else spec.bars
    band_at: dict[int, str] = {}
    for (start, length), band in zip(windows, bands):
        for bar in range(start, start + length):
            band_at[bar] = band
    first_half: set[int] = set()
    caesura: set[int] = set()
    trio: set[int] = set()
    for section in () if spec is None else spec.sections:
        if section.kind == "phrase":
            mid = section.start + max(1, (section.end - section.start) // 2)
            first_half.update(range(section.start, mid))
        if section.bridge and section.end > section.start:
            caesura.add(section.end - 1)
        if section.trio:
            mid = section.start + max(1, (section.end - section.start) // 2)
            trio.update(range(section.start, mid))
    straight = (meter.beats, meter.beat_type) == (4, 4)
    plan: dict[int, BarGroove] = {}
    for bar in range(bars):
        chosen = character
        if character_at is not None and bar < len(character_at) and character_at[bar] is not None:
            chosen = character_at[bar]
        if chosen is None:
            continue
        band = band_at.get(bar, "p")
        busy = band in ("mf", "f")
        plan[bar] = BarGroove(
            tresillo=straight and chosen == "volatile" and busy and variant in ("symphony", "minimalist"),
            syncopate=straight and chosen == "volatile" and busy and variant == "jazz",
            chromatic=chosen == "volatile" and variant == "jazz",
            half=chosen == "calm" and band in ("p", "mp") and bar in first_half,
            calm=chosen == "calm",
            volatile=chosen == "volatile",
            rally=chosen == "rally",
            selloff=chosen == "selloff",
            caesura=bar in caesura,
            trio_thin=bar in trio,
        )
    if spec is not None and spec.bars == 34 and regimes:
        _daily_session(plan, spec, band_at, variant, character, regimes)
    return plan


def _daily_session(
    plan: dict[int, BarGroove],
    spec: FormSpec,
    band_at: dict[int, str],
    variant: VariantName,
    character: MovementCharacter | None,
    regimes: Sequence[str],
) -> None:
    """Morning half-feel and a midday volatile groove on the 34-bar day."""
    slot_regime: dict[int, str] = {}
    for section in spec.sections:
        if section.regime_slot >= len(regimes):
            continue
        for bar in range(section.start, section.end):
            slot_regime[bar] = regimes[section.regime_slot]
    morning = slot_regime.get(2)
    middle = slot_regime.get(12)
    flipped = {morning, middle} == {"uptrend", "downtrend"}
    straight = (spec.meter.beats, spec.meter.beat_type) == (4, 4)
    for bar in range(2, 12):
        if morning == "sideway" and band_at.get(bar) in ("p", "mp"):
            plan[bar] = _replace_groove(plan.get(bar), half=True)
    for bar in range(12, 20):
        if band_at.get(bar) not in ("mf", "f"):
            continue
        if character != "volatile" and not flipped:
            continue
        plan[bar] = _replace_groove(
            plan.get(bar),
            volatile=True,
            tresillo=straight and variant in ("symphony", "minimalist"),
            syncopate=straight and variant == "jazz",
            chromatic=variant == "jazz",
        )


def _replace_groove(groove: BarGroove | None, **flags: bool) -> BarGroove:
    if groove is None:
        return BarGroove(**flags)
    return BarGroove(**{**groove.__dict__, **flags})


def opening_median(closes: Sequence[float]) -> float | None:
    if not closes:
        return None
    ordered = sorted(closes)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def gap_direction(previous: float, opening: float | None) -> str | None:
    """`up` or `down` only inside the HOSE band. Splits and tiny opens stay silent."""
    if opening is None or previous <= 0:
        return None
    gap = (opening - previous) / previous
    if 0.008 <= gap <= 0.068:
        return "up"
    if -0.068 <= gap <= -0.008:
        return "down"
    return None
