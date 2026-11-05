"""Shared, bounded fixture parsing for the Studio previews.

The preview pilots all accept the same small JSON fixture: a few integers and
booleans that select one sentence length, plus an optional selection matrix.
Each pilot used to carry its own copy of the same type checks and matrix
bounds. This module owns that shared core; the pilots keep only the parts that
are specific to their renderer (defaults, allowed profiles, meters, ...).

The helpers are deliberately small and concrete:

* `fixture_int` / `fixture_bool` validate one scalar and raise
  `SpecParseError` (a `ValueError`) with the authored JSON path.
* `allowed_fixture_keys` rejects unknown fixture keys.
* `matrix_axes` resolves and bounds one selection grid. It slices each raw
  axis before converting items, so a huge or hostile input cannot be
  materialised.

Bounds live here so every preview shares them:

* `MAX_PLAN_BARS` caps a planned sentence length.
* `MAX_RENDER_BARS` caps how many planned bars produce notes.

The pilots may still apply stricter limits (for example Barrios' exact period
length or its smaller matrix row cap) by passing them to this API.
"""

from __future__ import annotations

from typing import Any, Collection, Mapping

MAX_PLAN_BARS = 64
MAX_RENDER_BARS = 16


class SpecParseError(ValueError):
    """A fixture mapping could not become a bounded, typed preview fixture."""


def fixture_int(
    value: Any,
    path: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Return `value` as an int, or raise `SpecParseError` naming `path`.

    Booleans are rejected even though `bool` is an `int` subclass: a JSON
    `true` is never a valid length or bar count. Bounds are inclusive.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise SpecParseError(f"{path} must be an integer")
    if minimum is not None and value < minimum:
        raise SpecParseError(f"{path} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise SpecParseError(f"{path} must be <= {maximum}")
    return value


def fixture_bool(value: Any, path: str) -> bool:
    """Return `value` as a bool, or raise `SpecParseError` naming `path`."""
    if not isinstance(value, bool):
        raise SpecParseError(f"{path} must be a boolean")
    return value


def allowed_fixture_keys(
    supplied: Mapping[str, Any],
    allowed: Collection[str],
    *,
    path: str = "fixture",
) -> None:
    """Reject keys in `supplied` that are not in `allowed`.

    The message lists the unknown keys sorted, so the response is stable and
    the authored JSON can be corrected without guessing.
    """
    unknown = set(supplied) - set(allowed)
    if unknown:
        raise SpecParseError(f"{path}: unknown field(s) {sorted(unknown)}")


def matrix_axes(
    supplied: Mapping[str, Any] | None,
    *,
    defaults: Mapping[str, Any],
    max_rows: int,
    max_length: int,
    allowed_lengths: Collection[int] | None = None,
) -> dict[str, list[Any]]:
    """Resolve and bound the selection grid `{lengths, n, closes, rise}`.

    `defaults` must provide one value per axis; it is used only for axes the
    fixture omits. The raw axes are sliced before `int()`/`bool()` so a huge
    input list cannot be materialised:

    =========  =========================  ==================
    axis       raw slice                  parsed bound
    =========  =========================  ==================
    `lengths`  ``max_length * 2`` items   1 .. `max_length`
    `n`        8 items                    >= 0
    `closes`   2 items                    boolean
    `rise`     8 items                    >= 0
    =========  =========================  ==================

    `max_rows` caps the cartesian product. `allowed_lengths`, when given, is a
    whitelist: a parsed length outside it is rejected rather than silently
    dropped. All errors are `SpecParseError`s addressed at `fixture.matrix`.
    """
    supplied = supplied or {}
    if not isinstance(supplied, Mapping):
        raise SpecParseError("fixture.matrix must be a mapping")

    raw_lengths = supplied.get("lengths", defaults["lengths"])
    raw_n = supplied.get("n", defaults["n"])
    raw_closes = supplied.get("closes", defaults["closes"])
    raw_rise = supplied.get("rise", defaults["rise"])
    for name, raw in (
        ("lengths", raw_lengths),
        ("n", raw_n),
        ("closes", raw_closes),
        ("rise", raw_rise),
    ):
        if not isinstance(raw, (list, tuple)):
            raise SpecParseError(f"fixture.matrix.{name} must be a list")

    # Slice before converting so a huge input cannot be materialised.
    lengths = sorted(
        {
            value
            for value in (
                fixture_int(
                    item,
                    "fixture.matrix.lengths",
                    minimum=1,
                    maximum=max_length,
                )
                for item in raw_lengths[: max_length * 2]
            )
        }
    )
    n_values = [
        fixture_int(item, "fixture.matrix.n", minimum=0)
        for item in raw_n[:8]
    ]
    closes_values = [
        fixture_bool(item, "fixture.matrix.closes")
        for item in raw_closes[:2]
    ]
    rise_values = [
        fixture_int(item, "fixture.matrix.rise", minimum=0)
        for item in raw_rise[:8]
    ]
    if not lengths or not n_values or not closes_values or not rise_values:
        raise SpecParseError("fixture.matrix axes must be non-empty")
    if allowed_lengths is not None:
        permitted = frozenset(allowed_lengths)
        for length in lengths:
            if length not in permitted:
                raise SpecParseError(
                    f"fixture.matrix.lengths {length} is not an allowed length"
                )
    if len(lengths) * len(n_values) * len(closes_values) * len(rise_values) > max_rows:
        raise SpecParseError(f"fixture.matrix is capped at {max_rows} rows")
    return {
        "lengths": lengths,
        "n": n_values,
        "closes": closes_values,
        "rise": rise_values,
    }
