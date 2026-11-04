"""Sentence archetypes as data.

A sentence selects a figure for a span of bars. The first migrated family is
`castillo` in 3/4: two archetypes, walk for an even phrase number and cadence
for an odd one, each tiling nine bars. The bar-level figure renderers stay in
`guitar_torroba.py`; only the choice of figure for a span lives here.

`plan_sentence()` returns `None` when the pattern/meter pair has no data yet, so
callers can fall back to the code path during the migration. An empty list means
the registry covers the pair but the length or phrase number is unsupported.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    """One figure inside a tile. `start`/`bars` are bar offsets inside the tile."""

    start: int
    bars: int
    figure: int


@dataclass(frozen=True)
class Span:
    """How a sentence repeats. `tile` is the bar length of one repetition."""

    tile: int
    remainder: str = "same_figure"
    truncate_to_length: bool = True


@dataclass(frozen=True)
class Select:
    """Which phrases the archetype serves."""

    length_min: int = 0
    length_max: int | None = None
    n_parity: str = "any"  # any | even | odd


@dataclass(frozen=True)
class SentenceSpec:
    id: str
    pattern: str
    meter: str
    select: Select
    span: Span
    slots: tuple[Slot, ...]


SENTENCE_SPECS: dict[tuple[str, str], tuple[SentenceSpec, ...]] = {}


def register(pattern: str, meter: str, *specs: SentenceSpec) -> None:
    """Add archetypes for one pattern/meter pair. Called at import by the owner module."""
    SENTENCE_SPECS[(pattern, meter)] = tuple(specs)


def _matches(spec: SentenceSpec, length: int, n: int) -> bool:
    if length < spec.select.length_min:
        return False
    if spec.select.length_max is not None and length > spec.select.length_max:
        return False
    if spec.select.n_parity == "even" and n % 2 != 0:
        return False
    if spec.select.n_parity == "odd" and n % 2 == 0:
        return False
    return True


def _tile(spec: SentenceSpec, length: int) -> list[tuple[int, tuple[int, ...]]]:
    spans: list[tuple[int, tuple[int, ...]]] = []
    start = 0
    while start < length:
        chunk = min(spec.span.tile, length - start)
        for slot in spec.slots:
            low = max(slot.start, 0)
            high = min(slot.start + slot.bars, chunk)
            if low < high:
                spans.append((slot.figure, tuple(range(start + low, start + high))))
        start += chunk
    return spans


def plan_sentence(
    pattern: str,
    meter: str,
    length: int,
    n: int,
    *,
    closes: bool = False,
    rise: int = 0,
) -> list[tuple[int, tuple[int, ...]]] | None:
    """Figure spans for one phrase, or `None` when the pair has no data yet.

    `closes` and `rise` are accepted now so archetypes that need them can be
    added without changing the call site; the castillo 3/4 archetypes ignore
    them, exactly like `_castillo_34_spans`.
    """
    del closes, rise  # castillo 3/4 does not read them
    specs = SENTENCE_SPECS.get((pattern, meter))
    if specs is None:
        return None
    for spec in specs:
        if _matches(spec, length, n):
            return _tile(spec, length)
    return []
