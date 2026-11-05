"""Validate and preview an authored `SentenceSpec` against the real renderers.

Phase 0/1 treats the JSON as **authoring source plus fixture**. The runtime
still renders through the code paths in `guitar_torroba` / `guitar_sor`; this
module only answers two questions for the Studio UI:

* is this spec structurally registerable (`validate_spec`)?
* what does the spec select and sound like for one bounded fixture
  (`preview_spec`)?

Sandbox
-------
`validate_spec` checks structural rules without registering the spec in the
global registry. `preview_spec` plans and renders inside
`sentence_specs.use_registry`, a `ContextVar` carrying a local snapshot; the
per-bar realizers therefore see the authored spec, and `SENTENCE_SPECS` is
never mutated. The plan and the notes both come from that same snapshot.

Fixture
-------
A fixture is a plain mapping. Only `pattern`, `meter`, `length`, `n`, `closes`
and `rise` describe the selection; the other keys drive the bounded render:

===========  ==========================================================
key          default / meaning
===========  ==========================================================
`pattern`    the spec's pattern (must match)
`meter`      the spec's meter, or `4/4` for a `"*"` (meter-any) spec
`length`     the spec's full tile, else its shortest selectable length
`run_length` a cell/cycle alias for `length` (the UI sends this for galop)
`n`          the spec's parity/mod residue (0 for even/any, 1 for odd)
`closes`     `False` for `closes="open"`, `True` for `closes="close"`
`rise`       `select.rise_min`
`bars`       bars to render, capped at `MAX_RENDER_BARS` (default: length)
`length`     capped at `MAX_PLAN_BARS`; `run_length` is the cell/cycle alias
`character`  `"calm"` for Torroba figures, `"rally"` for a classic cell run
`mode`       `"minor"` for Torroba figures, `"major"` for a cell run
`bpm`        `96` for Torroba figures, `88` for a cell run
`profile`    `"torroba"` for figures, `"classic"` for cells
`matrix`     overrides the selection grid (see `_matrix_axes`)
===========  ==========================================================

The melody is a fixed contour (`_TORROBA_CONTOUR`) for figures and a held
pitch for the galop cell, matching the deterministic parity-test bodies. The
render is one phrase of `length` bars, but notes are only collected for the
first `bars` bars (at most 16): no full-span audio, no MuseScore export.

A `procedure` slot validates against `procedure_specs.PROCEDURES`, but a
procedure has no span plan and no preview renderer: `preview_spec` returns
`ok: false` with a `slots[i].procedure` error instead of inventing notes.

Notes come from the same per-bar realizers `render_guitar_score` dispatches to
(`render_torroba_figure` / `_render_torroba_bar` / `_render_galop_bar`). The
movement planner is deliberately **not** run: it chooses a pattern from mood
and meter, so it could render a different archetype than the authored one.
That keeps the preview a function of the spec, not of today's mood table.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import dataclass, replace
from typing import Any, Iterator, Mapping

from app.sonify.chords import C, CM
from app.sonify.form import METER_34, METER_44, METER_68, compose_meter
from app.sonify.guitar import _apex_eighths
from app.sonify.guitar_patterns import (
    _Ctx,
    _meter_kind,
    _render_galop_bar,
    _render_torroba_bar,
)
from app.sonify.guitar_torroba import render_torroba_figure, torroba_figure_plan
from app.sonify.keys import active_register
from app.sonify.model import Phrase, Run
from app.sonify import sentence_specs
from app.sonify.sentence_specs import METER_ANY, SentenceSpec
from app.studio.sentence_spec import parse_spec

MAX_RENDER_BARS = 16
MAX_PLAN_BARS = 64
MAX_MATRIX_LENGTH = 12
MAX_MATRIX_ROWS = 4096
_HASH_PREFIX = "sha256:"
_METERS = {"3/4": METER_34, "4/4": METER_44, "6/8": METER_68}
_PROFILES = {"torroba", "classic"}
_CHARACTERS = frozenset({None, "calm", "rally", "selloff", "volatile"})
_MODES = frozenset({"major", "minor"})
_TORROBA_CONTOUR = (67, 65, 64, 62, 60, 62, 64, 65)
_GALOP_PITCH = 67


class SpecParseError(ValueError):
    """The JSON mapping could not become a `SentenceSpec`."""


@dataclass(frozen=True)
class Error:
    """One validation error, addressed at the authored JSON path."""

    path: str
    message: str


@dataclass(frozen=True)
class PreviewResult:
    """Raw preview result. `as_response` owns the HTTP/JSON spelling."""

    ok: bool
    errors: tuple[Error, ...] = ()
    plan: dict[str, Any] | None = None
    row: list[str] | None = None
    notes: tuple[dict[str, Any], ...] = ()
    render_hash: str | None = None
    matrix: tuple[dict[str, Any], ...] = ()

    def as_response(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [{"path": error.path, "message": error.message} for error in self.errors],
            "plan": self.plan,
            "row": self.row,
            "notes": list(self.notes),
            "renderHash": self.render_hash,
            "matrix": list(self.matrix),
        }


# ---------------------------------------------------------------------------
# registry sandbox


def _load_owners() -> None:
    """Import the registries before snapshotting so a lazy import cannot leak."""
    for name in sentence_specs._OWNER_MODULES:
        importlib.import_module(name)


def _valid_realizers() -> tuple[frozenset[int], frozenset[str], frozenset[str]]:
    from app.sonify.guitar_sor import GALOP_CELL_1, GALOP_CELL_2
    from app.sonify.guitar_torroba import _FIGURES
    from app.sonify.procedure_specs import PROCEDURES

    return (
        frozenset(_FIGURES),
        frozenset({GALOP_CELL_1, GALOP_CELL_2}),
        frozenset(PROCEDURES),
    )


def _known_patterns() -> set[str]:
    _load_owners()
    return {pattern for pattern, _meter in sentence_specs.SENTENCE_SPECS}


def _shape_ok(spec: SentenceSpec) -> bool:
    """The dataclass fields a hand-built or parsed spec must actually carry."""
    return (
        isinstance(spec.pattern, str)
        and isinstance(spec.meter, str)
        and isinstance(spec.select, sentence_specs.Select)
        and isinstance(spec.span, sentence_specs.Span)
        and isinstance(spec.slots, tuple)
        and all(isinstance(slot, sentence_specs.Slot) for slot in spec.slots)
    )


# ---------------------------------------------------------------------------
# validation


def _error_path(message: str) -> str:
    """Best-effort JSON path for a `register()` message."""
    text = message.lower()
    if "pattern/meter" in text:
        return "pattern"
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
    if any(
        word in text
        for word in ("slot", "anchor", "overlap", "figure", "cell", "procedure")
    ):
        return "slots"
    if "duplicate ids" in text:
        return "id"
    return "spec"


def _strip_id(message: str, spec: SentenceSpec) -> str:
    prefix = f"{spec.id}: "
    return message[len(prefix):] if message.startswith(prefix) else message


def validate_spec(spec: SentenceSpec) -> list[Error]:
    """Schema and registry errors for one authored spec.

    The structural rules are the registry's: the spec is registered into a
    sandbox copy of `SENTENCE_SPECS`, so this cannot drift from
    `sentence_specs._validate`. Pattern/meter existence and figure/cell
    existence are checked first because they have precise JSON paths.
    """
    errors: list[Error] = []
    if not isinstance(spec.id, str) or not spec.id.strip():
        errors.append(Error("id", "id must be a non-empty string"))

    patterns = _known_patterns()
    if not isinstance(spec.pattern, str) or spec.pattern not in patterns:
        errors.append(
            Error("pattern", f"unknown pattern {spec.pattern!r} (Torroba/Sor only)")
        )
    if not isinstance(spec.meter, str) or (
        spec.meter not in _METERS and spec.meter != METER_ANY
    ):
        errors.append(
            Error(
                "meter",
                f"unknown meter {spec.meter!r}; expected one of {sorted(_METERS)} or '*'",
            )
        )
    elif (
        isinstance(spec.pattern, str)
        and spec.pattern in patterns
        and sentence_specs._lookup(spec.pattern, spec.meter) is None
    ):
        errors.append(
            Error(
                "meter",
                "pattern/meter pair "
                f"{spec.pattern!r}/{spec.meter!r} is not registered "
                "(Phase 1 edits existing pairs)",
            )
        )

    figures, cells, procedures = _valid_realizers()
    span_ok = isinstance(spec.span, sentence_specs.Span)
    tile = spec.span.tile if span_ok else None
    slots_ok = isinstance(spec.slots, tuple) and all(
        isinstance(slot, sentence_specs.Slot) for slot in spec.slots
    )
    if not slots_ok:
        errors.append(Error("slots", "slots must be a tuple of slot objects"))
    for index, slot in enumerate(spec.slots if slots_ok else ()):
        path = f"slots[{index}]"
        if sum(
            realizer is not None
            for realizer in (slot.figure, slot.cell, slot.procedure)
        ) != 1:
            errors.append(
                Error(path, "a slot needs exactly one of figure, cell, or procedure")
            )
        if slot.figure is not None and slot.figure not in figures:
            errors.append(
                Error(f"{path}.figure", f"figure {slot.figure!r} is not in _FIGURES")
            )
        if slot.cell is not None and slot.cell not in cells:
            errors.append(
                Error(f"{path}.cell", f"cell {slot.cell!r} is not a registered galop cell")
            )
        if slot.procedure is not None and (
            not isinstance(slot.procedure, str)
            or slot.procedure not in procedures
        ):
            errors.append(
                Error(
                    f"{path}.procedure",
                    f"procedure {slot.procedure!r} is not registered",
                )
            )
        if slot.anchor not in {"start", "middle", "end"}:
            errors.append(Error(f"{path}.anchor", f"unknown slot anchor {slot.anchor!r}"))
        elif slot.anchor == "start":
            if slot.start < 0 or slot.bars < 1:
                errors.append(
                    Error(path, "slot start/bars must be >= 0 / >= 1")
                )
            elif tile is not None and slot.start + slot.bars > tile:
                errors.append(
                    Error(path, f"slot runs past the {tile}-bar tile")
                )

    structural: list[Error] = []
    if not _shape_ok(spec):
        if not errors:
            errors.append(Error("spec", "spec fields do not have the expected types"))
        return errors
    try:
        sentence_specs._validate(spec, spec.pattern, spec.meter)
    except (ValueError, AttributeError, TypeError) as exc:
        message = _strip_id(str(exc), spec)
        structural.append(Error(_error_path(message), message))

    # Drop a registry duplicate of a precise pre-check (e.g. a bad figure).
    seen = {(error.path, error.message) for error in errors}
    for error in structural:
        if error.path == "slots" and any(
            prior.path.startswith("slots[") for prior in errors
        ):
            continue
        if (error.path, error.message) not in seen:
            errors.append(error)
            seen.add((error.path, error.message))
    return errors


# ---------------------------------------------------------------------------
# fixture resolution


def _default_length(spec: SentenceSpec, n: int, closes: bool, rise: int) -> int:
    """Prefer a full tile, then the shortest sentence, then the first match."""
    candidates: list[int] = []
    if spec.span.tile is not None:
        candidates.append(spec.span.tile)
    if spec.select.length_min >= 1:
        candidates.append(spec.select.length_min)
    candidates.extend(range(1, MAX_MATRIX_LENGTH + 1))
    for length in candidates:
        if sentence_specs._matches(spec, length, n, closes, rise):
            return length
    return max(1, spec.select.length_min)


def _default_n(spec: SentenceSpec) -> int:
    select = spec.select
    if select.n_mod is not None:
        return select.n_mod[1]
    if select.n_parity == "odd":
        return 1
    return 0


def _fixture_int(
    value: Any,
    path: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SpecParseError(f"{path} must be an integer")
    if minimum is not None and value < minimum:
        raise SpecParseError(f"{path} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise SpecParseError(f"{path} must be <= {maximum}")
    return value


def _fixture_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise SpecParseError(f"{path} must be a boolean")
    return value


def _resolve_fixture(spec: SentenceSpec, fixture: Mapping[str, Any] | None) -> dict[str, Any]:
    supplied = dict(fixture or {})
    profile = supplied.get("profile")
    if profile is None:
        profile = "classic" if spec.span.cycle else "torroba"
    if profile not in _PROFILES:
        raise SpecParseError(f"fixture.profile must be one of {sorted(_PROFILES)}")

    if spec.span.cycle and profile != "classic":
        raise SpecParseError("a cell/cycle spec previews with profile='classic'")
    if not spec.span.cycle and profile != "torroba":
        raise SpecParseError("a figure spec previews with profile='torroba'")

    pattern = supplied.get("pattern", spec.pattern)
    if pattern != spec.pattern:
        raise SpecParseError(
            f"fixture.pattern {pattern!r} does not match spec.pattern {spec.pattern!r}"
        )

    default_meter = spec.meter if spec.meter != METER_ANY else "4/4"
    meter = supplied.get("meter", default_meter)
    if meter not in _METERS:
        raise SpecParseError(
            f"fixture.meter {meter!r} is not renderable; expected {sorted(_METERS)}"
        )
    if spec.meter != METER_ANY and meter != spec.meter:
        raise SpecParseError(
            f"fixture.meter {meter!r} does not match spec.meter {spec.meter!r}"
        )

    n = _fixture_int(supplied.get("n", _default_n(spec)), "fixture.n", minimum=0)
    closes = _fixture_bool(
        supplied.get("closes", spec.select.closes == "close"), "fixture.closes"
    )
    rise = _fixture_int(
        supplied.get("rise", spec.select.rise_min), "fixture.rise", minimum=0
    )
    # The UI names the galop cycle fixture `run_length`; figures use `length`.
    length = _fixture_int(
        supplied.get(
            "run_length" if spec.span.cycle else "length",
            _default_length(spec, n, closes, rise),
        ),
        "fixture.length",
        minimum=1,
        maximum=MAX_PLAN_BARS,
    )
    bars = _fixture_int(supplied.get("bars", length), "fixture.bars", minimum=0)
    bars = min(bars, MAX_RENDER_BARS, length)

    character = supplied.get(
        "character", "rally" if profile == "classic" else "calm"
    )
    if character not in _CHARACTERS:
        raise SpecParseError(
            f"fixture.character must be one of {sorted(item or 'none' for item in _CHARACTERS)}"
        )
    mode = supplied.get("mode", "major" if profile == "classic" else "minor")
    if mode not in _MODES:
        raise SpecParseError(f"fixture.mode must be one of {sorted(_MODES)}")
    bpm = _fixture_int(
        supplied.get("bpm", 88 if profile == "classic" else 96),
        "fixture.bpm",
        minimum=1,
        maximum=400,
    )
    matrix = _matrix_axes(supplied.get("matrix"))

    return {
        "pattern": pattern,
        "meter": meter,
        "length": length,
        "n": n,
        "closes": closes,
        "rise": rise,
        "bars": max(0, bars),
        "character": character,
        "mode": mode,
        "bpm": bpm,
        "profile": profile,
        "matrix": matrix,
    }


# ---------------------------------------------------------------------------
# plan / render


def _figure_spans(plan: list[tuple[int, tuple[int, ...]]] | None) -> list[dict[str, Any]]:
    return [
        {"figure": figure, "bars": list(bars)}
        for figure, bars in (plan or [])
    ]


def _cell_spans(cells: list[str] | None) -> list[dict[str, Any]]:
    """Group one cell id per bar into contiguous spans."""
    spans: list[dict[str, Any]] = []
    for bar, cell in enumerate(cells or []):
        if spans and spans[-1]["cell"] == cell and spans[-1]["bars"][-1] == bar - 1:
            spans[-1]["bars"].append(bar)
        else:
            spans.append({"cell": cell, "bars": [bar]})
    return spans


def _plan_for(
    spec: SentenceSpec,
    fixture: Mapping[str, Any],
    registry: Mapping[tuple[str, str], tuple[SentenceSpec, ...]] | None = None,
) -> dict[str, Any]:
    """The authored spec's own selection, through the public planners."""
    length = int(fixture["length"])
    if spec.span.cycle:
        cells = sentence_specs.plan_run(
            spec.pattern, spec.meter, length, registry=registry
        )
        spans = _cell_spans(cells)
        kind = "cell"
    else:
        spans = _figure_spans(
            sentence_specs.plan_sentence(
                spec.pattern,
                spec.meter,
                length,
                int(fixture["n"]),
                closes=bool(fixture["closes"]),
                rise=int(fixture["rise"]),
                registry=registry,
            )
        )
        kind = "figure"
    return {
        "kind": kind,
        "length": length,
        "selected": bool(spans),
        "spans": spans,
    }


def _joined(start: int, pitches: list[int]) -> Phrase:
    runs: list[Run] = []
    index = 0
    while index < len(pitches):
        nxt = index + 1
        while nxt < len(pitches) and pitches[nxt] == pitches[index]:
            nxt += 1
        runs.append(Run(start + index, nxt - index, pitches[index]))
        index = nxt
    return Phrase(start, start + len(pitches), tuple(runs), False)


def _melody(profile: str, length: int, epb: int) -> list[int]:
    if profile == "classic":
        return [_GALOP_PITCH] * (length * epb)
    return [
        _TORROBA_CONTOUR[index % len(_TORROBA_CONTOUR)]
        for index in range(length * epb)
    ]


def _ctx(
    *,
    meter: Any,
    length: int,
    character: str,
    mode: str,
    bpm: int,
    ensemble: str,
    melody: list[int],
) -> _Ctx:
    register = active_register()
    return _Ctx(
        melody=list(melody),
        raw=list(melody),
        chord_at={bar: CM if mode == "minor" else C for bar in range(length)},
        kind_at={bar: "phrase" for bar in range(length)},
        band_at={bar: "mf" for bar in range(length)},
        phrases=(_joined(0, melody),),
        bars=length,
        bpm=bpm,
        ensemble=ensemble,
        mode=mode,
        character=character,
        character_at=None,
        sections=(),
        rel_span=0.02,
        semitones=40 - register.guitar_floor,
        bass_low=register.guitar_floor,
        bass_high=register.guitar_bass_top,
        mid_low=register.guitar_mid_low,
        mid_high=register.guitar_mid_high,
        treble_floor=register.guitar_treble_floor,
        treble_top=register.guitar_treble_top,
        ceiling=register.guitar_ceiling,
        epb=meter.eighths_per_bar,
        kind=_meter_kind(meter),
        strong=tuple(meter.strong_eighths),
        bar_beats=meter.quarter_beats,
        regime_at={bar: "sideway" for bar in range(length)},
    )


def _figure_notes(
    spec: SentenceSpec, fixture: Mapping[str, Any]
) -> tuple[list, list[str]]:
    meter = _METERS[fixture["meter"]]
    length = int(fixture["length"])
    rows = [spec.pattern] * length
    melody = _melody("torroba", length, meter.eighths_per_bar)
    with compose_meter(meter):
        ctx = _ctx(
            meter=meter,
            length=length,
            character=str(fixture["character"]),
            mode=str(fixture["mode"]),
            bpm=int(fixture["bpm"]),
            ensemble="torroba",
            melody=melody,
        )
        figure_at = torroba_figure_plan(ctx, rows)
        collect = min(int(fixture["bars"]), length)
        lead: list = []
        support: list = []
        low: list = []
        for bar in range(collect):
            phrase_here = ctx.phrases[0]
            placed = figure_at.get(bar)
            if placed is None:
                part_lead, part_support, part_low = _render_torroba_bar(
                    ctx, bar, phrase_here, spec.pattern, rows
                )
            else:
                figure, index, count = placed
                following = figure_at.get(bar + 1)
                part_lead, part_support, part_low = render_torroba_figure(
                    ctx,
                    bar,
                    phrase_here,
                    spec.pattern,
                    figure,
                    index=index,
                    count=count,
                    next_figure=following[0] if following is not None else None,
                )
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
    return _voice(lead, 1) + _voice(support, 2) + _voice(low, 3), rows


def _cell_notes(
    spec: SentenceSpec, fixture: Mapping[str, Any]
) -> tuple[list, list[str]]:
    meter = _METERS[fixture["meter"]]
    length = int(fixture["length"])
    rows = [spec.pattern] * length
    melody = _melody("classic", length, meter.eighths_per_bar)
    with compose_meter(meter):
        ctx = _ctx(
            meter=meter,
            length=length,
            character=str(fixture["character"]),
            mode=str(fixture["mode"]),
            bpm=int(fixture["bpm"]),
            ensemble="classic",
            melody=melody,
        )
        apex = _apex_eighths(ctx.phrases)
        collect = min(int(fixture["bars"]), length)
        lead: list = []
        support: list = []
        low: list = []
        for bar in range(collect):
            part_lead, part_support, part_low = _render_galop_bar(
                ctx, bar, apex, ctx.phrases[0], rows
            )
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
    return _voice(lead, 1) + _voice(support, 2) + _voice(low, 3), rows


def _voice(events: list, voice: int) -> list:
    return [
        replace(event, voice=voice)
        for event in events
        if getattr(event, "midi", None) is not None
    ]


def _note(event: Any) -> dict[str, Any]:
    return {
        "bar": int(event.bar),
        "beat": round(float(event.beat), 6),
        "duration": round(float(event.duration_beats), 6),
        "midi": int(event.midi),
        "voice": int(event.voice),
        "velocity": None if event.velocity is None else int(event.velocity),
        "accent": bool(event.accent),
        "staccato": bool(event.staccato),
        "tieStart": bool(event.tie_start),
        "tieStop": bool(event.tie_stop),
        "slurStart": bool(event.slur_start),
        "slurStop": bool(event.slur_stop),
        "staff": int(event.staff),
    }


def _notes(events: list) -> tuple[dict[str, Any], ...]:
    ordered = [
        _note(event)
        for event in events
    ]
    ordered.sort(
        key=lambda note: (
            note["bar"],
            note["beat"],
            note["voice"],
            -1 if note["midi"] is None else note["midi"],
            note["duration"],
        )
    )
    return tuple(ordered)


def _render_hash(plan: dict[str, Any], row: list[str], notes: tuple[dict[str, Any], ...]) -> str:
    payload = {"plan": plan, "row": row, "notes": notes}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return _HASH_PREFIX + hashlib.sha256(encoded.encode("ascii")).hexdigest()


# ---------------------------------------------------------------------------
# selection/render matrix


def _matrix_axes(supplied: Mapping[str, Any] | None) -> dict[str, list[Any]]:
    """Resolve (and bound) the selection grid. Raises `SpecParseError`."""
    supplied = supplied or {}
    if not isinstance(supplied, Mapping):
        raise SpecParseError("fixture.matrix must be a mapping")
    raw_lengths = supplied.get("lengths", list(range(1, MAX_MATRIX_LENGTH + 1)))
    raw_n = supplied.get("n", [0, 1, 2, 3])
    raw_closes = supplied.get("closes", [False, True])
    raw_rise = supplied.get("rise", [0, 1, 2])
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
                _fixture_int(item, "fixture.matrix.lengths", minimum=1,
                             maximum=MAX_MATRIX_LENGTH)
                for item in raw_lengths[: MAX_MATRIX_LENGTH * 2]
            )
        }
    )
    n_values = [
        _fixture_int(item, "fixture.matrix.n", minimum=0)
        for item in raw_n[:8]
    ]
    closes_values = [
        _fixture_bool(item, "fixture.matrix.closes")
        for item in raw_closes[:2]
    ]
    rise_values = [
        _fixture_int(item, "fixture.matrix.rise", minimum=0)
        for item in raw_rise[:8]
    ]
    if not lengths or not n_values or not closes_values or not rise_values:
        raise SpecParseError("fixture.matrix axes must be non-empty")
    if len(lengths) * len(n_values) * len(closes_values) * len(rise_values) > MAX_MATRIX_ROWS:
        raise SpecParseError(f"fixture.matrix is capped at {MAX_MATRIX_ROWS} rows")
    return {
        "lengths": lengths,
        "n": n_values,
        "closes": closes_values,
        "rise": rise_values,
    }


def _matrix_row_spans(spec: SentenceSpec, length: int) -> list[dict[str, Any]]:
    if spec.span.cycle:
        return _cell_spans(sentence_specs._run_cells(spec, length))
    return _figure_spans(sentence_specs._tile(spec, length))


def _matrix(
    spec: SentenceSpec,
    fixture: Mapping[str, Any],
    render_hash: str | None,
) -> tuple[dict[str, Any], ...]:
    axes = fixture["matrix"]
    rows: list[dict[str, Any]] = []
    for length in axes["lengths"]:
        for n in axes["n"]:
            for closes in axes["closes"]:
                for rise in axes["rise"]:
                    selected = bool(
                        sentence_specs._matches(spec, length, n, closes, rise)
                    )
                    spans = _matrix_row_spans(spec, length) if selected else []
                    rendered = (
                        selected
                        and render_hash is not None
                        and length == int(fixture["length"])
                        and n == int(fixture["n"])
                        and closes == bool(fixture["closes"])
                        and rise == int(fixture["rise"])
                    )
                    row = {
                        "length": length,
                        "n": n,
                        "closes": closes,
                        "rise": rise,
                        "selected": selected,
                        "spans": spans,
                        "render": rendered,
                        "renderHash": render_hash if rendered else None,
                    }
                    rows.append(row)
    return tuple(rows)


# ---------------------------------------------------------------------------
# public entry point


def _procedure_slot(spec: SentenceSpec) -> Error | None:
    """A procedure realizer has no renderer yet, so there is nothing to preview."""
    for index, slot in enumerate(spec.slots):
        if slot.procedure is not None:
            return Error(
                f"slots[{index}].procedure",
                f"procedure {slot.procedure!r} preview not implemented",
            )
    return None


def preview_spec(
    spec: SentenceSpec, fixture: Mapping[str, Any] | None = None
) -> PreviewResult:
    """Validate one spec and render one bounded, deterministic fixture."""
    errors = validate_spec(spec)
    if errors:
        return PreviewResult(ok=False, errors=tuple(errors))

    blocked = _procedure_slot(spec)
    if blocked is not None:
        return PreviewResult(ok=False, errors=(blocked,))

    try:
        resolved = _resolve_fixture(spec, fixture)
    except (SpecParseError, TypeError, ValueError) as exc:
        return PreviewResult(ok=False, errors=(Error("fixture", str(exc)),))

    _load_owners()
    sandbox = dict(sentence_specs.SENTENCE_SPECS)
    sandbox[(spec.pattern, spec.meter)] = (spec,)
    # The per-bar realizers call plan_sentence/plan_run themselves. The
    # ContextVar makes them see the authored spec, not the production one.
    with sentence_specs.use_registry(sandbox):
        plan = _plan_for(spec, resolved)
        if spec.span.cycle:
            events, row = _cell_notes(spec, resolved)
        else:
            events, row = _figure_notes(spec, resolved)

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
