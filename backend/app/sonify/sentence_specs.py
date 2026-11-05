"""Sentence archetypes as data.

A sentence selects a figure for a span of bars. The migrated families are
`castillo` in 3/4 (two archetypes: walk on an even phrase number, cadence on an
odd one, nine-bar tile), `castillo` in 4/4 (nine Arada archetypes: type 7,
type 8 pairs, and a one-bar link), `sonatina` open/close, `fandanguillo` (two
archetypes: a four-bar type 5 on an even phrase number, a two-bar type 2 placed
relative to the phrase middle on an odd one), `danza` in 3/4 and 6/8 (one
four-bar type 6), and Sor's `galop` (a run-based cycle of two cells). The
bar-level figure renderers stay in `guitar_torroba.py`; the galop cells stay in
`guitar_sor.py`. Only the choice of realizer for a span lives here.

`plan_sentence()` returns `None` when the pattern/meter pair has no data yet, so
callers fall back to the code path during the migration. An empty list means the
registry covers the pair but the length/selection does not match.

A slot holds exactly one realizer: a `figure` (an id the owner renders through
its figure table), a `cell` (an id the owner resolves itself, like the galop
cells), or a `procedure` (an id the owner/renderer resolves through
`procedure_specs.PROCEDURES`). Only figures are planned by `plan_sentence`;
`plan_run()` plans cells for a run-based `cycle` archetype, which has no phrase
turn to select on. Neither planner emits a span for a procedure slot: a
procedure describes how a later renderer realizes a span, it does not fill one.

`previous_figure` is not an input here: `select_torroba_spans` rotates `n` when
the first figure repeats, which is a plan-level post-pass.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

# Owner modules call register() at import. plan_sentence() imports them lazily
# so a caller that only imports this module still gets a plan.
_OWNER_MODULES = ("app.sonify.guitar_torroba", "app.sonify.guitar_sor")

METER_ANY = "*"
_N_PARITY = frozenset({"any", "even", "odd"})
_ANCHORS = frozenset({"start", "middle", "end"})
_CLOSES = frozenset({"open", "close"})
_REMAINDER = frozenset({"same_figure", "truncate_cycle", "exact"})


@dataclass(frozen=True)
class Slot:
    """One figure inside a tile. `start`/`bars` are bar offsets inside the tile.

    `anchor="end"` places the slot at `length - bars`, for sentences whose tail
    starts relative to the phrase end (sonatina close). It requires an exact
    span and `start=0`; it cannot be used inside a repeating tile.

    `anchor="middle"` places the slot at `length // 2 + start`, for phrases
    whose figure is centred on the phrase length (fandanguillo's odd turn uses
    `start=-1`). It also requires an exact span, and `start` is an offset from
    the middle, so it may be negative.

    Exactly one of `figure`, `cell`, and `procedure` is set. `figure` resolves
    through the owner's `_FIGURES`; `cell` is an id the owner resolves on its
    own (galop); `procedure` is an id the owner/renderer resolves through
    `procedure_specs.PROCEDURES`. `plan_sentence` only emits figure spans;
    `plan_run` only emits cells; neither emits a procedure span.
    """

    start: int
    bars: int
    figure: int | None = None
    cell: str | None = None
    procedure: str | None = None
    anchor: str = "start"


@dataclass(frozen=True)
class Span:
    """How a sentence repeats.

    `tile` is the bar length of one repetition. `exact` (or remainder "exact")
    means the slots cover exactly `length` and never repeat. `cycle` marks a
    run-based archetype (galop); `remainder`/`cycle` are declarative: every
    non-exact span repeats and the last chunk is truncated when
    `truncate_to_length` is on. They exist so validation and tests can tell a
    one-figure tile from a cycle.
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
    if span.remainder == "truncate_cycle" and not span.cycle:
        raise ValueError(f"{spec.id}: truncate_cycle needs cycle=True")
    if span.cycle and span.remainder != "truncate_cycle":
        raise ValueError(f"{spec.id}: a cycle needs remainder='truncate_cycle'")
    if span.cycle and not span.truncate_to_length:
        raise ValueError(f"{spec.id}: a cycle needs truncate_to_length")
    if span.cycle and (
        select.n_parity != "any"
        or select.n_mod is not None
        or select.closes is not None
        or select.rise_min != 0
    ):
        # A run has no phrase turn, close, or rise to select on.
        raise ValueError(f"{spec.id}: a cycle cannot select on n, closes, or rise")
    if not spec.slots:
        raise ValueError(f"{spec.id}: at least one slot is required")
    for slot in spec.slots:
        if slot.anchor not in _ANCHORS:
            raise ValueError(f"{spec.id}: unknown slot anchor {slot.anchor!r}")
        if (
            sum(
                realizer is not None
                for realizer in (slot.figure, slot.cell, slot.procedure)
            )
            != 1
        ):
            raise ValueError(
                f"{spec.id}: a slot needs exactly one of figure, cell, or procedure"
            )
        if slot.cell is not None and (
            not isinstance(slot.cell, str) or not slot.cell
        ):
            raise ValueError(f"{spec.id}: a cell id must be a non-empty string")
        if slot.procedure is not None and (
            not isinstance(slot.procedure, str) or not slot.procedure
        ):
            raise ValueError(f"{spec.id}: a procedure id must be a non-empty string")
        if span.cycle and slot.cell is None:
            raise ValueError(f"{spec.id}: a cycle slot needs a cell realizer")
        if not span.cycle and slot.cell is not None:
            raise ValueError(f"{spec.id}: a cell realizer needs a cycle span")
        if span.cycle and slot.anchor != "start":
            raise ValueError(f"{spec.id}: a cycle slot must be start-anchored")

    start_slots = [slot for slot in spec.slots if slot.anchor == "start"]
    middle_slots = [slot for slot in spec.slots if slot.anchor == "middle"]
    end_slots = [slot for slot in spec.slots if slot.anchor == "end"]

    for slot in start_slots:
        if slot.start < 0 or slot.bars < 1:
            raise ValueError(f"{spec.id}: slot start/bars must be >= 0 / >= 1")
        if span.tile is not None and slot.start + slot.bars > span.tile:
            raise ValueError(f"{spec.id}: slot runs past the tile")

    start_high = max((slot.start + slot.bars for slot in start_slots), default=0)
    for slot in middle_slots:
        if not is_exact:
            raise ValueError(f"{spec.id}: a middle-anchored slot needs an exact span")
        if slot.bars < 1:
            raise ValueError(f"{spec.id}: slot bars must be >= 1")
        base = select.length_min // 2 + slot.start
        if base < 0 or base + slot.bars > select.length_min:
            raise ValueError(
                f"{spec.id}: middle slot falls outside the phrase at length_min"
            )
        # A middle slot drifts right by half a bar per extra length. If it
        # started left of a fixed start slot it would eventually collide, so
        # require it to clear them at length_min; then the distance only grows.
        if base < start_high:
            raise ValueError(
                f"{spec.id}: middle slot must clear the start slots at length_min"
            )

    for slot in end_slots:
        if not is_exact:
            raise ValueError(f"{spec.id}: an end-anchored slot needs an exact span")
        if slot.start != 0:
            raise ValueError(f"{spec.id}: an end-anchored slot must use start=0")
        if slot.bars < 1:
            raise ValueError(f"{spec.id}: slot bars must be >= 1")
        if select.length_min < slot.bars:
            raise ValueError(f"{spec.id}: length_min is below the end slot size")

    # Every anchor except `start` is length-relative, and each sits at its
    # leftmost position at length_min (middle: `length_min // 2 + start`,
    # end: `length_min - bars`). Middle slots are required to start after the
    # fixed start slots, so their distance only grows; end slots move right
    # faster than middle slots. One check at length_min therefore covers the
    # whole select range.
    placed: list[tuple[int, int]] = []
    previous_end = 0
    for slot in sorted(start_slots, key=lambda item: item.start):
        if slot.start < previous_end:
            raise ValueError(f"{spec.id}: slots overlap")
        previous_end = slot.start + slot.bars
        placed.append((slot.start, previous_end))
    for slot in sorted(middle_slots, key=lambda item: select.length_min // 2 + item.start):
        low = select.length_min // 2 + slot.start
        high = low + slot.bars
        if any(low < other_high and other_low < high for other_low, other_high in placed):
            raise ValueError(
                f"{spec.id}: middle slot overlaps an earlier slot at length_min"
            )
        placed.append((low, high))
    for slot in sorted(end_slots, key=lambda item: item.bars, reverse=True):
        low = select.length_min - slot.bars
        high = select.length_min
        if any(low < other_high and other_low < high for other_low, other_high in placed):
            raise ValueError(
                f"{spec.id}: end slot overlaps an earlier slot at length_min"
            )
        placed.append((low, high))


def register(
    pattern: str,
    meter: str,
    *specs: SentenceSpec,
    replace: bool = False,
    valid_figures: Collection[int] | None = None,
    valid_cells: Collection[str] | None = None,
    valid_procedures: Collection[str] | None = None,
) -> None:
    """Add archetypes for one pattern/meter pair.

    Called at import by the owner module. Re-registering identical specs is a
    no-op, so `importlib.reload` keeps working; a different value raises unless
    `replace=True`. When `valid_figures` is given, every slot figure must exist
    in it (the owner passes its `_FIGURES` keys); `valid_cells` does the same
    for a cell realizer and `valid_procedures` for a procedure id, so an
    owner's typo cannot register.
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
            slot.figure
            for spec in ordered
            for slot in spec.slots
            if slot.figure is not None
        } - set(valid_figures)  # type: ignore[arg-type]
        if missing:
            raise ValueError(f"{key}: figures {sorted(missing)} are not registered")
    if valid_cells is not None:
        missing_cells = {
            slot.cell
            for spec in ordered
            for slot in spec.slots
            if slot.cell is not None
        } - set(valid_cells)
        if missing_cells:
            raise ValueError(f"{key}: cells {sorted(missing_cells)} are not registered")
    if valid_procedures is not None:
        missing_procedures = {
            slot.procedure
            for spec in ordered
            for slot in spec.slots
            if slot.procedure is not None
        } - set(valid_procedures)
        if missing_procedures:
            raise ValueError(
                f"{key}: procedures {sorted(missing_procedures)} are not registered"
            )

    existing = SENTENCE_SPECS.get(key)
    if existing is not None:
        if existing == ordered:
            return
        if not replace:
            raise ValueError(f"sentence specs already registered for {key}")
    SENTENCE_SPECS[key] = ordered


def load_specs(
    path: str | Path, replace: bool = False
) -> tuple[SentenceSpec, ...]:
    """Load a v1 JSON wrapper and register its specs.

    Identical re-registration is a no-op, a new `(pattern, meter)` pair is
    added, and a changed existing pair raises unless `replace=True`. The whole
    file is checked before anything is registered, so a rejected file does not
    leave a partial update behind.

    The JSON is an authoring source and test fixture only: this function
    registers code specs, it does not install an interpreter. Use
    `app.studio.sentence_spec.parse_payload` to build specs without touching
    the global registry.
    """
    from app.studio.sentence_spec import parse_payload

    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    specs = parse_payload(payload)

    groups: dict[tuple[str, str], list[SentenceSpec]] = {}
    for spec in specs:
        groups.setdefault((spec.pattern, spec.meter), []).append(spec)

    ordered_groups = [
        (
            key,
            tuple(sorted(group, key=lambda spec: (spec.select.length_min, spec.id))),
        )
        for key, group in sorted(groups.items())
    ]
    for key, ordered in ordered_groups:
        existing = SENTENCE_SPECS.get(key)
        if existing is not None and existing != ordered and not replace:
            raise ValueError(
                f"{source}: sentence specs already registered for {key}; "
                "use replace=True to replace them"
            )

    for (pattern, meter), group in ordered_groups:
        register(pattern, meter, *group, replace=replace)
    return specs


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


def _range(slot: Slot, chunk: int, total: int) -> tuple[int, int] | None:
    """The clipped `(low, high)` bar range a slot covers inside one chunk."""
    if slot.anchor == "end":
        base = total - slot.bars
    elif slot.anchor == "middle":
        base = total // 2 + slot.start
    else:
        base = slot.start
    low = max(base, 0)
    high = min(base + slot.bars, chunk)
    if low >= high:
        return None
    return low, high


def _slots(
    spec: SentenceSpec, offset: int, chunk: int, total: int
) -> list[tuple[int, tuple[int, ...]]]:
    """Figure spans only.

    A cell slot is planned by `plan_run` instead, and a procedure slot is
    resolved by the owner/renderer, so neither is emitted here.
    """
    spans: list[tuple[int, tuple[int, ...]]] = []
    for slot in spec.slots:
        if slot.figure is None:
            continue
        found = _range(slot, chunk, total)
        if found is not None:
            low, high = found
            spans.append((slot.figure, tuple(range(offset + low, offset + high))))
    return spans


def _cells(
    spec: SentenceSpec, offset: int, chunk: int, total: int
) -> list[tuple[str, tuple[int, ...]]]:
    """Cell spans only. Mirrors `_slots` for the run-based realizer."""
    spans: list[tuple[str, tuple[int, ...]]] = []
    for slot in spec.slots:
        if slot.cell is None:
            continue
        found = _range(slot, chunk, total)
        if found is not None:
            low, high = found
            spans.append((slot.cell, tuple(range(offset + low, offset + high))))
    return spans


def _tile(
    spec: SentenceSpec,
    length: int,
    place: Callable[[SentenceSpec, int, int, int], list[tuple]] | None = None,
) -> list[tuple]:
    if place is None:
        place = _slots
    span = spec.span
    if span.exact or span.remainder == "exact":
        if span.tile is not None and length != span.tile:
            return []
        return place(spec, 0, length, length)

    tile = span.tile
    if tile is None:  # validated at register; guard for python -O
        return []
    if any(slot.anchor != "start" for slot in spec.slots):
        # register() rejects this; stay quiet on the render path if a spec was
        # built by hand.
        return []
    if not span.truncate_to_length and length % tile != 0:
        return []
    spans: list[tuple] = []
    start = 0
    while start < length:
        chunk = min(tile, length - start)
        spans.extend(place(spec, start, chunk, length))
        start += chunk
    return spans


def _lookup(
    pattern: str,
    meter: str,
    registry: Mapping[tuple[str, str], tuple[SentenceSpec, ...]] | None = None,
) -> tuple[SentenceSpec, ...] | None:
    table = SENTENCE_SPECS if registry is None else registry
    exact = table.get((pattern, meter))
    if exact is not None:
        return exact
    if registry is not None:
        # A sandbox registry is already complete; do not import owners into it.
        return table.get((pattern, METER_ANY))
    # Owner modules register at import. A caller that imports only this module
    # still gets the table once the owners have been loaded. Retry the exact key
    # before the wildcard, so a meter-specific registration always wins.
    for module in _OWNER_MODULES:
        importlib.import_module(module)
    exact = SENTENCE_SPECS.get((pattern, meter))
    if exact is not None:
        return exact
    return SENTENCE_SPECS.get((pattern, METER_ANY))


def plan_sentence(
    pattern: str,
    meter: str,
    length: int,
    n: int,
    *,
    closes: bool = False,
    rise: int = 0,
    registry: Mapping[tuple[str, str], tuple[SentenceSpec, ...]] | None = None,
) -> list[tuple[int, tuple[int, ...]]] | None:
    """Figure spans for one phrase, or `None` when the pair has no data yet."""
    specs = _lookup(pattern, meter, registry)
    if specs is None:
        return None
    for spec in specs:
        if _matches(spec, length, n, closes, rise):
            return _tile(spec, length)
    return []


def _run_cells(spec: SentenceSpec, run_length: int) -> list[str]:
    spans = _tile(spec, run_length, _cells)
    cells: list[str | None] = [None] * run_length
    for cell, bars in spans:
        for bar in bars:
            if 0 <= bar < run_length:
                cells[bar] = cell
    if any(cell is None for cell in cells):
        return []
    return [cell for cell in cells if cell is not None]


def plan_run(
    pattern: str,
    meter: str,
    run_length: int,
    *,
    registry: Mapping[tuple[str, str], tuple[SentenceSpec, ...]] | None = None,
) -> list[str] | None:
    """One cell id per bar of a run, or `None` when the pair has no run data.

    A run is a maximal stretch of consecutive bars the caller treats as one
    cycle: the galop run index resets at a pedal or study bar, so the caller
    passes the **full** run length, including the bars before and after the
    current one. Only a `cycle` span has a run plan. `None` means the pair has
    no entry at all (the caller stays on the code path); `[]` means the registry
    covers the pair but has no cycle that fills every bar at this run length.
    """
    specs = _lookup(pattern, meter, registry)
    if specs is None:
        return None
    if run_length < 1:
        return []
    for spec in specs:
        if not spec.span.cycle:
            continue
        select = spec.select
        if run_length < select.length_min:
            continue
        if select.length_max is not None and run_length > select.length_max:
            continue
        return _run_cells(spec, run_length)
    return []
