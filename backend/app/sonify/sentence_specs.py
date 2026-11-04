"""Sentence archetypes as data (Phase 1: castillo 3/4).

A sentence selects a figure for a span of bars. The first migrated family is
`castillo` in 3/4: two archetypes, walk for an even phrase number and cadence
for an odd one, each tiling nine bars. The bar-level figure renderers stay in
`guitar_torroba.py`; only the choice of figure for a span lives here.

`plan_sentence()` returns `None` when the pattern/meter pair has no data yet, so
callers fall back to the code path during the migration. An empty list means the
registry covers the pair but the length/selection does not match.

`previous_figure` is not an input here: `select_torroba_spans` rotates `n` when
the first figure repeats, which is a plan-level post-pass.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

# Owner modules call register() at import. plan_sentence() imports them lazily
# so a caller that only imports this module still gets a plan. Add the galop
# owner here when guitar_sor registers its archetype.
_OWNER_MODULES = ("app.sonify.guitar_torroba",)

_N_PARITY = frozenset({"any", "even", "odd"})
_CLOSES = frozenset({"open", "close"})
_REMAINDER = frozenset({"same_figure", "truncate_cycle", "exact"})


@dataclass(frozen=True)
class Slot:
    """One figure inside a tile. `start`/`bars` are bar offsets inside the tile."""

    start: int
    bars: int
    figure: int


@dataclass(frozen=True)
class Span:
    """How a sentence repeats.

    `tile` is the bar length of one repetition. `exact` (or remainder "exact")
    means the slots cover exactly `length` and never repeat. `cycle` marks a
    run-based archetype (galop) whose slots repeat over any run length.
    """

    tile: int | None = None
    remainder: str = "same_figure"
    truncate_to_length: bool = True
    cycle: bool = False
    exact: bool = False


@dataclass(frozen=True)
class Select:
    """Which phrases the archetype serves. All conditions must hold."""

    length_min: int = 0
    length_max: int | None = None
    n_parity: str = "any"  # any | even | odd
    n_mod: tuple[int, int] | None = None  # (mod, value), e.g. (3, 0)
    closes: str | None = None  # None | open | close
    rise_min: int = 0


@dataclass(frozen=True)
class SentenceSpec:
    id: str
    pattern: str
    meter: str
    select: Select
    span: Span
    slots: tuple[Slot, ...]


SENTENCE_SPECS: dict[tuple[str, str], tuple[SentenceSpec, ...]] = {}


def _validate(spec: SentenceSpec, pattern: str, meter: str) -> None:
    if spec.pattern != pattern or spec.meter != meter:
        raise ValueError(f"{spec.id}: pattern/meter do not match the registry key")
    select = spec.select
    if select.n_parity not in _N_PARITY:
        raise ValueError(f"{spec.id}: n_parity must be one of {sorted(_N_PARITY)}")
    if select.n_mod is not None:
        mod, value = select.n_mod
        if mod < 1 or not 0 <= value < mod:
            raise ValueError(f"{spec.id}: n_mod must be (mod >= 1, 0 <= value < mod)")
        if select.n_parity != "any":
            raise ValueError(f"{spec.id}: use n_parity or n_mod, not both")
    if select.closes not in (None, *_CLOSES):
        raise ValueError(f"{spec.id}: closes must be None, 'open' or 'close'")
    if select.rise_min < 0:
        raise ValueError(f"{spec.id}: rise_min must be >= 0")
    if select.length_max is not None and select.length_max < select.length_min:
        raise ValueError(f"{spec.id}: length_max is below length_min")
    span = spec.span
    if span.remainder not in _REMAINDER:
        raise ValueError(f"{spec.id}: unknown remainder {span.remainder!r}")
    is_exact = span.exact or span.remainder == "exact"
    if is_exact and span.cycle:
        raise ValueError(f"{spec.id}: an exact span cannot also be a cycle")
    if is_exact and span.tile is not None and span.tile < 1:
        raise ValueError(f"{spec.id}: tile must be >= 1")
    if not is_exact and (span.tile is None or span.tile < 1):
        raise ValueError(f"{spec.id}: tile must be >= 1")
    if span.remainder == "truncate_cycle" and not span.truncate_to_length:
        raise ValueError(f"{spec.id}: truncate_cycle needs truncate_to_length")
    if span.cycle and not span.truncate_to_length:
        raise ValueError(f"{spec.id}: a cycle needs truncate_to_length")
    if not spec.slots:
        raise ValueError(f"{spec.id}: at least one slot is required")
    previous_end = 0
    for slot in sorted(spec.slots, key=lambda item: item.start):
        if slot.start < 0 or slot.bars < 1:
            raise ValueError(f"{spec.id}: slot start/bars must be >= 0 / >= 1")
        if span.tile is not None and slot.start + slot.bars > span.tile:
            raise ValueError(f"{spec.id}: slot runs past the tile")
        if slot.start < previous_end:
            raise ValueError(f"{spec.id}: slots overlap")
        previous_end = slot.start + slot.bars


def register(
    pattern: str,
    meter: str,
    *specs: SentenceSpec,
    replace: bool = False,
    valid_figures: object | None = None,
) -> None:
    """Add archetypes for one pattern/meter pair.

    Called at import by the owner module. Re-registering identical specs is a
    no-op, so `importlib.reload` keeps working; a different value raises unless
    `replace=True`. When `valid_figures` is given, every slot figure must exist
    in it (the owner passes its `_FIGURES` keys).
    """
    key = (pattern, meter)
    ordered = tuple(
        sorted(specs, key=lambda spec: (spec.select.length_min, spec.id))
    )
    for spec in ordered:
        _validate(spec, pattern, meter)
    ids = [spec.id for spec in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError(f"sentence specs for {key} contain duplicate ids")
    if valid_figures is not None:
        missing = {
            slot.figure for spec in ordered for slot in spec.slots
        } - set(valid_figures)  # type: ignore[arg-type]
        if missing:
            raise ValueError(f"{key}: figures {sorted(missing)} are not registered")

    existing = SENTENCE_SPECS.get(key)
    if existing is not None:
        if existing == ordered:
            return
        if not replace:
            raise ValueError(f"sentence specs already registered for {key}")
    SENTENCE_SPECS[key] = ordered


def _matches(spec: SentenceSpec, length: int, n: int, closes: bool, rise: int) -> bool:
    select = spec.select
    if length < select.length_min:
        return False
    if select.length_max is not None and length > select.length_max:
        return False
    span = spec.span
    is_exact = span.exact or span.remainder == "exact"
    if is_exact and span.tile is not None and length != span.tile:
        return False
    if (
        not is_exact
        and not span.truncate_to_length
        and span.tile is not None
        and length % span.tile != 0
    ):
        return False
    if select.n_parity == "even" and n % 2 != 0:
        return False
    if select.n_parity == "odd" and n % 2 == 0:
        return False
    if select.n_mod is not None:
        mod, value = select.n_mod
        if n % mod != value:
            return False
    if select.closes == "open" and closes:
        return False
    if select.closes == "close" and not closes:
        return False
    return rise >= select.rise_min


def _slots(spec: SentenceSpec, start: int, chunk: int) -> list[tuple[int, tuple[int, ...]]]:
    spans: list[tuple[int, tuple[int, ...]]] = []
    for slot in spec.slots:
        low = max(slot.start, 0)
        high = min(slot.start + slot.bars, chunk)
        if low < high:
            spans.append((slot.figure, tuple(range(start + low, start + high))))
    return spans


def _tile(spec: SentenceSpec, length: int) -> list[tuple[int, tuple[int, ...]]]:
    span = spec.span
    if span.exact or span.remainder == "exact":
        if span.tile is not None and length != span.tile:
            return []
        return _slots(spec, 0, length)

    tile = span.tile
    if tile is None:  # validated at register; guard for python -O
        return []
    if not span.truncate_to_length and length % tile != 0:
        return []
    spans: list[tuple[int, tuple[int, ...]]] = []
    start = 0
    while start < length:
        chunk = min(tile, length - start)
        spans.extend(_slots(spec, start, chunk))
        start += chunk
    return spans


def _lookup(pattern: str, meter: str) -> tuple[SentenceSpec, ...] | None:
    key = (pattern, meter)
    specs = SENTENCE_SPECS.get(key)
    if specs is None:
        # Owner modules register at import. A caller that imports only this
        # module still gets the table once the owners have been loaded.
        for module in _OWNER_MODULES:
            importlib.import_module(module)
        specs = SENTENCE_SPECS.get(key)
    return specs


def plan_sentence(
    pattern: str,
    meter: str,
    length: int,
    n: int,
    *,
    closes: bool = False,
    rise: int = 0,
) -> list[tuple[int, tuple[int, ...]]] | None:
    """Figure spans for one phrase, or `None` when the pair has no data yet."""
    specs = _lookup(pattern, meter)
    if specs is None:
        return None
    for spec in specs:
        if _matches(spec, length, n, closes, rise):
            return _tile(spec, length)
    return []
