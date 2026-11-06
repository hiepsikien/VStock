"""Preview-only Villa sentence renderer.

The production planners do not know this module. It answers one question for
the Studio authoring loop: *what does this candidate Villa sentence select and
sound like for one bounded fixture?* It validates against the Villa figure
registry, plans the spec through a sandbox copy of `SENTENCE_SPECS`, and renders
one bar at a time through the real bar writers in `guitar_villa.py` (wrapped by
`app.sonify.guitar_villa_figures`).

Two deliberate limits:

* nothing is registered — `plan_sentence` only ever sees the spec through a
  sandbox mapping passed as `registry=`, so the global table never changes;
* a bar is rendered only when the plan assigns a figure to it. The sentence,
  not a mood table, decides the textures.

The body reuses the bounded fixture helpers from `app.studio.preview` (`_ctx`,
`_notes`, `_render_hash`, `_matrix`). Those helpers are renderer
agnostic; the Torroba preview owns the file but not the shape of a `_Ctx`.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any, Mapping

from app.sonify import sentence_specs
from app.sonify.form import METER_24, METER_34, METER_44, METER_68, compose_meter
from app.sonify.guitar_villa_figures import (
    VILLA_FIGURES,
    VILLA_FIGURE_NAMES,
    render_villa_figure,
)
from app.sonify.sentence_specs import METER_ANY, SentenceSpec
from app.studio.preview import (
    MAX_MATRIX_LENGTH,
    MAX_MATRIX_ROWS,
    Error,
    PreviewResult,
    _CHARACTERS,
    _MODES,
    _ctx,
    _matrix,
    _notes,
    _render_hash,
    _voice,
)
from app.studio.preview_fixture import (
    MAX_PLAN_BARS,
    MAX_RENDER_BARS,
    allowed_fixture_keys,
    fixture_bool as _fixture_bool,
    fixture_int as _fixture_int,
    matrix_axes,
)

VILLA_PATTERNS = frozenset({"villa_pattern", "chord_melody", "etude1", "etude11"})
VILLA_METERS = {
    "2/4": METER_24,
    "3/4": METER_34,
    "4/4": METER_44,
    "6/8": METER_68,
}

# A minor-mode contour in the guitar's singing range. It repeats to fill the
# fixture; the phrase is one continuous run, so the swell and apex are stable.
_VILLA_CONTOUR = (64, 67, 69, 71, 69, 67, 64, 62)
# The generated 2/4 sentence has no committed example; keep its lead in the
# source-music register so the preview does not sound bass-only.
_VILLA_CONTOUR_24 = tuple(note + 12 for note in _VILLA_CONTOUR)

# A context-free Villa sentence has no n/closes/rise input, so the preview
# matrix stays small: lengths 1-8 at n 0/1, open only, no rise.
_VILLA_MATRIX = {
    "lengths": list(range(1, 9)),
    "n": [0, 1],
    "closes": [False],
    "rise": [0],
}


def _shape_ok(spec: SentenceSpec) -> bool:
    return (
        isinstance(spec.id, str)
        and isinstance(spec.pattern, str)
        and isinstance(spec.meter, str)
        and isinstance(spec.select, sentence_specs.Select)
        and isinstance(spec.span, sentence_specs.Span)
        and isinstance(spec.slots, tuple)
        and all(isinstance(slot, sentence_specs.Slot) for slot in spec.slots)
    )


def _structural_path(message: str) -> str:
    text = message.lower()
    if "n_parity" in text or "n_mod" in text:
        return "select"
    if "closes" in text:
        return "select.closes"
    if "rise_min" in text:
        return "select.rise_min"
    if "length_max" in text or "length_min" in text:
        return "select.length"
    if any(word in text for word in ("tile", "remainder", "truncate", "cycle", "span")):
        return "span"
    if any(word in text for word in ("slot", "anchor", "overlap", "figure", "cell")):
        return "slots"
    if "duplicate ids" in text:
        return "id"
    return "spec"


def _strip_id(message: str, spec: SentenceSpec) -> str:
    prefix = f"{spec.id}: "
    return message[len(prefix):] if message.startswith(prefix) else message


def validate_villa_spec(
    spec: SentenceSpec,
    allowed_patterns: Collection[str] | None = None,
    allow_draft_pattern: bool = False,
) -> list[Error]:
    """Schema, Villa-pattern, and figure-registry errors for one candidate.

    `allowed_patterns` is the draft seam: a draft pattern created by the server
    is added to the committed Villa set for this call only. `allow_draft_pattern`
    accepts any non-empty pattern; callers that use it must have created or
    validated that id themselves. Neither option mutates `VILLA_PATTERNS`.
    """
    errors: list[Error] = []
    if not isinstance(spec.id, str) or not spec.id.strip():
        errors.append(Error("id", "id must be a non-empty string"))

    patterns = set(VILLA_PATTERNS)
    if allowed_patterns is not None:
        patterns.update(
            pattern
            for pattern in allowed_patterns
            if isinstance(pattern, str) and pattern
        )
    if (
        allow_draft_pattern
        and isinstance(spec.pattern, str)
        and spec.pattern
    ):
        patterns.add(spec.pattern)

    if not isinstance(spec.pattern, str) or spec.pattern not in patterns:
        errors.append(
            Error(
                "pattern",
                f"pattern {spec.pattern!r} is not a Villa pattern "
                f"({', '.join(sorted(patterns))})",
            )
        )
    if not isinstance(spec.meter, str) or (
        spec.meter not in VILLA_METERS and spec.meter != METER_ANY
    ):
        errors.append(
            Error(
                "meter",
                f"unknown meter {spec.meter!r}; expected one of "
                f"{sorted(VILLA_METERS)} or '*'",
            )
        )

    slots_ok = isinstance(spec.slots, tuple) and all(
        isinstance(slot, sentence_specs.Slot) for slot in spec.slots
    )
    span_ok = isinstance(spec.span, sentence_specs.Span)
    tile = spec.span.tile if span_ok else None
    if not slots_ok:
        errors.append(Error("slots", "slots must be a tuple of slot objects"))
    for index, slot in enumerate(spec.slots if slots_ok else ()):
        path = f"slots[{index}]"
        if (slot.figure is None) == (slot.cell is None):
            errors.append(Error(path, "a slot needs exactly one of figure or cell"))
        if slot.cell is not None:
            errors.append(
                Error(
                    f"{path}.cell",
                    "Villa has no cell realizer; every slot must name a figure",
                )
            )
        if slot.figure is not None and slot.figure not in VILLA_FIGURES:
            errors.append(
                Error(
                    f"{path}.figure",
                    f"figure {slot.figure!r} is not in VILLA_FIGURES",
                )
            )
        if slot.anchor not in {"start", "middle", "end"}:
            errors.append(Error(f"{path}.anchor", f"unknown slot anchor {slot.anchor!r}"))
        elif slot.anchor == "start":
            if slot.start < 0 or slot.bars < 1:
                errors.append(Error(path, "slot start/bars must be >= 0 / >= 1"))
            elif tile is not None and slot.start + slot.bars > tile:
                errors.append(Error(path, f"slot runs past the {tile}-bar tile"))

    if not _shape_ok(spec):
        if not errors:
            errors.append(Error("spec", "spec fields do not have the expected types"))
        return errors
    try:
        sentence_specs._validate(spec, spec.pattern, spec.meter)
    except (ValueError, AttributeError, TypeError) as exc:
        message = _strip_id(str(exc), spec)
        candidate = Error(_structural_path(message), message)
        if candidate not in errors:
            errors.append(candidate)
    return errors


# ---------------------------------------------------------------------------
# fixture resolution


def _default_n(spec: SentenceSpec) -> int:
    select = spec.select
    if select.n_mod is not None:
        return select.n_mod[1]
    return 1 if select.n_parity == "odd" else 0


def _default_length(spec: SentenceSpec) -> int:
    if spec.span.tile is not None:
        return spec.span.tile
    return max(1, spec.select.length_min)


def _villa_matrix_axes(supplied: Mapping[str, Any] | None) -> dict[str, list[Any]]:
    return matrix_axes(
        supplied,
        defaults=_VILLA_MATRIX,
        max_rows=MAX_MATRIX_ROWS,
        max_length=MAX_MATRIX_LENGTH,
    )


def _resolve_fixture(
    spec: SentenceSpec, fixture: Mapping[str, Any] | None
) -> dict[str, Any]:
    supplied = dict(fixture or {})
    allowed = {
        "pattern",
        "meter",
        "length",
        "n",
        "closes",
        "rise",
        "bars",
        "character",
        "mode",
        "bpm",
        "matrix",
    }
    allowed_fixture_keys(supplied, allowed)

    pattern = supplied.get("pattern", spec.pattern)
    if pattern != spec.pattern:
        raise ValueError(
            f"fixture.pattern {pattern!r} does not match spec.pattern {spec.pattern!r}"
        )

    default_meter = spec.meter if spec.meter != METER_ANY else "4/4"
    meter = supplied.get("meter", default_meter)
    if meter not in VILLA_METERS:
        raise ValueError(
            f"fixture.meter {meter!r} is not renderable; expected {sorted(VILLA_METERS)}"
        )
    if spec.meter != METER_ANY and meter != spec.meter:
        raise ValueError(
            f"fixture.meter {meter!r} does not match spec.meter {spec.meter!r}"
        )

    n = _fixture_int(supplied.get("n", _default_n(spec)), "fixture.n", minimum=0)
    closes = _fixture_bool(
        supplied.get("closes", spec.select.closes == "close"), "fixture.closes"
    )
    rise = _fixture_int(
        supplied.get("rise", spec.select.rise_min), "fixture.rise", minimum=0
    )
    length = _fixture_int(
        supplied.get("length", _default_length(spec)),
        "fixture.length",
        minimum=1,
        maximum=MAX_PLAN_BARS,
    )
    bars = _fixture_int(supplied.get("bars", length), "fixture.bars", minimum=0)
    bars = min(bars, MAX_RENDER_BARS, length)
    character = supplied.get("character")
    if character is None:
        character = "calm"
    if character not in _CHARACTERS:
        raise ValueError("fixture.character is not a known character")
    mode = supplied.get("mode", "minor")
    if mode not in _MODES:
        raise ValueError("fixture.mode must be major or minor")
    bpm = _fixture_int(supplied.get("bpm", 96), "fixture.bpm", minimum=1, maximum=400)

    return {
        "pattern": pattern,
        "meter": meter,
        "length": length,
        "n": n,
        "closes": closes,
        "rise": rise,
        "bars": bars,
        "character": character,
        "mode": mode,
        "bpm": bpm,
        "matrix": _villa_matrix_axes(supplied.get("matrix")),
    }


def resolve_fixture(
    spec: SentenceSpec, fixture: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Public alias for the bounded Villa fixture resolver.

    The draft endpoint needs the same defaults the preview applies, but not the
    leading underscore of the older internal helper.
    """
    return _resolve_fixture(spec, fixture)


# ---------------------------------------------------------------------------
# plan / render


def _plan_for(spec: SentenceSpec, fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Plan the candidate through a sandbox registry, never the global one."""
    registry = {(spec.pattern, spec.meter): (spec,)}
    spans = sentence_specs.plan_sentence(
        spec.pattern,
        spec.meter,
        int(fixture["length"]),
        int(fixture["n"]),
        closes=bool(fixture["closes"]),
        rise=int(fixture["rise"]),
        registry=registry,
    )
    return {
        "kind": "figure",
        "length": int(fixture["length"]),
        "selected": bool(spans),
        "spans": [
            {"figure": figure, "bars": list(bars)} for figure, bars in (spans or [])
        ],
    }


def _figure_at(plan: Mapping[str, Any]) -> dict[int, int]:
    found: dict[int, int] = {}
    for span in plan["spans"]:
        for bar in span["bars"]:
            found[int(bar)] = int(span["figure"])
    return found


def _villa_notes(
    spec: SentenceSpec, fixture: Mapping[str, Any], plan: Mapping[str, Any]
) -> tuple[list, list[str]]:
    meter = VILLA_METERS[str(fixture["meter"])]
    length = int(fixture["length"])
    contour = _VILLA_CONTOUR_24 if meter == METER_24 else _VILLA_CONTOUR
    melody = [
        contour[index % len(contour)]
        for index in range(length * meter.eighths_per_bar)
    ]
    figures = _figure_at(plan)
    row = [
        VILLA_FIGURE_NAMES.get(figures.get(bar), spec.pattern) for bar in range(length)
    ]
    with compose_meter(meter):
        ctx = _ctx(
            meter=meter,
            length=length,
            character=str(fixture["character"]),
            mode=str(fixture["mode"]),
            bpm=int(fixture["bpm"]),
            ensemble="villa",
            melody=melody,
        )
        collect = min(int(fixture["bars"]), length)
        lead: list = []
        support: list = []
        low: list = []
        for bar in range(collect):
            figure = figures.get(bar)
            if figure is None:
                continue
            part_lead, part_support, part_low = render_villa_figure(
                ctx, bar, ctx.phrases[0], figure
            )
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
    return _voice(lead, 1) + _voice(support, 2) + _voice(low, 3), row


# ---------------------------------------------------------------------------
# public entry point


def preview_villa_sentence(
    spec: SentenceSpec,
    fixture: Mapping[str, Any] | None = None,
    allowed_patterns: Collection[str] | None = None,
    allow_draft_pattern: bool = False,
) -> PreviewResult:
    """Validate one candidate Villa spec and render one bounded fixture.

    The keyword options are the draft seam; see `validate_villa_spec`.
    """
    errors = validate_villa_spec(
        spec,
        allowed_patterns=allowed_patterns,
        allow_draft_pattern=allow_draft_pattern,
    )
    if errors:
        return PreviewResult(ok=False, errors=tuple(errors))

    try:
        resolved = _resolve_fixture(spec, fixture)
    except (TypeError, ValueError) as exc:
        return PreviewResult(ok=False, errors=(Error("fixture", str(exc)),))

    plan = _plan_for(spec, resolved)
    if not plan["selected"]:
        return PreviewResult(
            ok=False,
            errors=(
                Error(
                    "fixture",
                    "this fixture (length/n/closes/rise) is not selected by the spec",
                ),
            ),
        )

    events, row = _villa_notes(spec, resolved, plan)
    notes = _notes(events)
    render_hash = _render_hash(plan, row, notes)
    matrix = _matrix(spec, resolved, render_hash)
    return PreviewResult(
        ok=True,
        plan=plan,
        row=row,
        notes=notes,
        render_hash=render_hash,
        matrix=matrix,
    )
